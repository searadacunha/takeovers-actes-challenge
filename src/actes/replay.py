"""Replay the reviewed ledger into cap-table states.

Only mechanism events move shares: CAPITAL_INCREASE, CAPITAL_DECREASE, SHAREHOLDER_SHARE_TRANSFER.
SHAREHOLDER_ENTRY and SHAREHOLDER_END never do. They are consequences of a mechanism, so the
replay computes who appeared and who disappeared and refuses a ledger that declares anything else.
That is what prevents one movement from being counted twice.

A share count the documents do not give is None, and stays None until a document attests a figure.
"""
from __future__ import annotations

from .corpus import norm

ENTRY, END = "SHAREHOLDER_ENTRY", "SHAREHOLDER_END"
INCREASE, DECREASE, TRANSFER = "CAPITAL_INCREASE", "CAPITAL_DECREASE", "SHAREHOLDER_SHARE_TRANSFER"


class LedgerError(ValueError):
    pass


def unknown(v):
    """TOML has no null: the ledger writes "?" for a figure the documents do not give."""
    return None if v == "?" else v


def _add(a, b):
    return None if a is None or b is None else a + b


def alias_index(holders: dict) -> dict[str, str]:
    """normalized name or alias -> canonical name. One alias can never point at two holders."""
    index: dict[str, str] = {}
    for canonical, meta in holders.items():
        for name in [canonical, *meta.get("aliases", [])]:
            if index.setdefault(norm(name), canonical) != canonical:
                raise LedgerError(f"alias {name!r} is claimed by {index[norm(name)]!r} and {canonical!r}")
    return index


def replay(ledger: dict) -> list[dict]:
    holders_meta = ledger["holders"]
    alias_index(holders_meta)
    capital, shares, nominal = 0, 0, None
    held: dict[str, int | None] = {}
    classes: dict[str, str] = {}
    timeline = []

    def known(name: str) -> str:
        if name not in holders_meta:
            raise LedgerError(f"{name!r} is not a declared holder (declare it under [holders])")
        return name

    for step in ledger["step"]:
        sid, events = step["id"], step.get("event", [])
        before = set(held)

        if "formation" in step:
            f = step["formation"]
            capital, nominal = f["capital_eur"], f["nominal_eur"]
            held.update({known(k): v for k, v in f["holders"].items()})
            shares = sum(held.values())
        if "split" in step:
            shares, nominal = shares * step["split"], nominal / step["split"]
            held = {k: None if v is None else v * step["split"] for k, v in held.items()}

        for ev in events:
            code, p = ev["code"], ev.get("payload", {})
            if code == INCREASE:
                capital, shares = capital + p["amount_eur"], shares + p["shares_issued"]
                alloc = {known(k): unknown(v) for k, v in ev["allocations"].items()}
                if None not in alloc.values() and sum(alloc.values()) != p["shares_issued"]:
                    raise LedgerError(f"{ev['id']}: allocations do not add up to the shares issued")
                for k, v in alloc.items():
                    held[k] = _add(held.get(k, 0), v)
            elif code == DECREASE:
                capital, shares = capital - p["amount_eur"], shares - p["shares_cancelled"]
                if sum(ev["cancellations"].values()) != p["shares_cancelled"]:
                    raise LedgerError(f"{ev['id']}: cancellations do not add up to the shares cancelled")
                for k, v in ev["cancellations"].items():
                    if known(k) not in held or (held[k] is not None and v > held[k]):
                        raise LedgerError(f"{ev['id']}: cancels {v} shares that {k} does not hold")
                    held[k] = _add(held[k], -v)
            elif code == TRANSFER:
                src, n = known(ev["from"]), unknown(ev["shares"])
                if src not in held:
                    raise LedgerError(f"{ev['id']}: seller {src} is not in the cap table")
                if n == "all":
                    n, left = held[src], 0
                else:
                    if n is not None and held[src] is not None and n > held[src]:
                        raise LedgerError(f"{ev['id']}: {src} transfers {n} shares but holds {held[src]}")
                    left = _add(held[src], None if n is None else -n)
                held[src] = left
                buyers = ev["to"] if isinstance(ev["to"], list) else [ev["to"]]
                for b in buyers:  # several candidate buyers: who got how many is not documented
                    held[b] = _add(held.get(known(b), 0), n if len(buyers) == 1 else None)
            if code in (INCREASE, DECREASE) and capital != p["capital_after_eur"]:
                raise LedgerError(f"{ev['id']}: capital after is {capital}, ledger says {p['capital_after_eur']}")

        for k, v in step.get("attested", {}).items():
            if held.get(known(k)) is not None and held[k] != v and "restated" not in step:
                raise LedgerError(f"{sid}: replay gives {k} {held[k]} shares, the document says {v}")
            held[k] = v
        held = {k: v for k, v in held.items() if v != 0}
        classes.update(step.get("share_class", {}))

        if capital != shares * nominal:
            raise LedgerError(f"{sid}: capital {capital} != {shares} shares x {nominal}")
        if None not in held.values() and sum(held.values()) != shares:
            raise LedgerError(f"{sid}: holdings add up to {sum(held.values())}, not {shares}")
        declared = {c: {e["payload"]["holder_name"] for e in events if e["code"] == c} for c in (ENTRY, END)}
        if declared[ENTRY] != set(held) - before or declared[END] != before - set(held):
            raise LedgerError(f"{sid}: declared entries/exits {declared} do not match the replay: "
                              f"in {sorted(set(held) - before)}, out {sorted(before - set(held))}")

        state = {
            "as_of": step["as_of"],
            "capital_eur": capital,
            "shares_total": shares,
            "nominal_eur": int(nominal) if float(nominal).is_integer() else nominal,
            "holders": [
                {"name": k, "siren": holders_meta[k].get("siren"), "kind": holders_meta[k]["kind"], "shares": v,
                 "pct": None if v is None else round(100 * v / shares, 2),
                 **({"share_class": classes[k]} if k in classes else {})}
                for k, v in sorted(held.items(), key=lambda kv: (kv[1] is None, -(kv[1] or 0), kv[0]))
            ],
            "caused_by": [e["id"] for e in events],
            "state_id": sid,
            "status": step["status"],
        }
        if "split" in step:
            state["corporate_action"] = {"type": "NOMINAL_SPLIT", "ratio": step["split"]}
        if "restated" in step:
            state["restated"] = step["restated"]
        if "note" in step:
            state["note"] = step["note"]
        timeline.append(state)
    return timeline
