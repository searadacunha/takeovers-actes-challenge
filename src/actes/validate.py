"""Independent checks on a results.json. It knows nothing about the ledger or the replay.

check() re-derives every transition from the published events alone, so a results.json produced
by any other means (or edited by hand) is held to the same rules.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from jsonschema import Draft202012Validator

ENTRY, END = "SHAREHOLDER_ENTRY", "SHAREHOLDER_END"
INCREASE, DECREASE, TRANSFER = "CAPITAL_INCREASE", "CAPITAL_DECREASE", "SHAREHOLDER_SHARE_TRANSFER"


def _is_date(s) -> bool:
    try:
        return isinstance(s, str) and len(s) == 10 and bool(date.fromisoformat(s))
    except ValueError:
        return False


def luhn_ok(siren) -> bool:
    """A SIREN is 9 digits with a Luhn checksum (check borrowed from InseeFrLab/citrus)."""
    if not (isinstance(siren, str) and len(siren) == 9 and siren.isdigit()):
        return False
    digits = [int(c) for c in reversed(siren)]
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits)) % 10 == 0


def _key(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


def _moved(name: str, events: list[dict]):
    """Net shares the events give to `name`. None when one of them has an undocumented count."""
    total = 0
    for e in events:
        p = e["payload"]
        if e["event_code"] == TRANSFER:
            buyers = p.get("to_candidates") or [p["to_name"]]
            if name == p["from_name"] or name in buyers:
                if p.get("shares") is None or len(buyers) > 1:
                    return None
                total += p["shares"] * ((name in buyers) - (name == p["from_name"]))
        for key, sign in (("allocations", 1), ("cancellations", -1)):
            for a in p.get(key, []):
                if a["holder_name"] == name:
                    if a["shares"] is None:
                        return None
                    total += sign * a["shares"]
    return total


def _check_group(group: dict) -> list[str]:
    errs = []
    nodes = [n["name"] for n in group.get("nodes", [])]
    if len({_key(n) for n in nodes}) != len(nodes):
        errs.append("group: a node is listed twice (same name, or a spelling variant of it)")
    for node in group.get("nodes", []):
        if node.get("siren") is not None and not luhn_ok(node["siren"]):
            errs.append(f"group node {node['name']}: SIREN {node['siren']!r} is not a valid SIREN")
        if node.get("resolved") and not node.get("siren"):
            errs.append(f"group node {node['name']}: resolved without a SIREN")
    owns: dict[str, set[str]] = {}
    seen = set()
    for e in group.get("edges", []):
        key = (e["from"], e["to"], e["relation"])
        if e["from"] not in nodes or e["to"] not in nodes:
            errs.append(f"group edge {key}: endpoint is not a node")
        if e["from"] == e["to"] or key in seen:
            errs.append(f"group edge {key}: self-loop or duplicate")
        seen.add(key)
        if e.get("pct") is not None and not 0 < e["pct"] <= 100:
            errs.append(f"group edge {key}: pct {e['pct']} out of range")
        x0, y0, x1, y1 = (e.get("source") or {}).get("bbox") or (1, 1, 0, 0)
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            errs.append(f"group edge {key}: no valid evidence box")
        if e["relation"] == "shareholder_of":
            owns.setdefault(e["from"], set()).add(e["to"])

    def reaches(start: str, goal: str, visited: set) -> bool:  # a company cannot own itself through a chain
        return any(n == goal or (n not in visited and reaches(n, goal, visited | {n})) for n in owns.get(start, ()))

    errs += [f"group: ownership cycle through {n}" for n in owns if reaches(n, n, {n})]
    return errs


def check(results: dict, schema: dict) -> list[str]:
    errs = [f"schema: {e.message} at /{'/'.join(map(str, e.absolute_path))}"
            for e in Draft202012Validator(schema).iter_errors(results)]
    if errs:
        return errs  # the checks below assume the shape the schema guarantees

    events: dict[str, dict] = {}
    for e in results["events"]:
        i = e["event_id"]
        if i in events:
            errs.append(f"{i}: duplicate event_id")
        events[i] = e
        if not _is_date(e["event_date"]):
            errs.append(f"{i}: event_date {e['event_date']!r} is not YYYY-MM-DD")
        x0, y0, x1, y1 = e["source"]["bbox"]
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            errs.append(f"{i}: bbox {e['source']['bbox']} is not a normalized top-left box")
        if not e["source"].get("snippet"):
            errs.append(f"{i}: source has no snippet")

    used: Counter = Counter()
    prev = None
    for n, s in enumerate(results["capital_timeline"]):
        tag = f"timeline[{n}] {s['as_of']}"
        if not _is_date(s["as_of"]):
            errs.append(f"{tag}: as_of is not YYYY-MM-DD")
            continue
        caused = s.get("caused_by", [])
        for i in caused:
            used[i] += 1
            if i not in events:
                errs.append(f"{tag}: caused_by {i!r} is not an event")
            elif _is_date(events[i]["event_date"]) and events[i]["event_date"] > s["as_of"]:
                errs.append(f"{tag}: caused by {i}, dated after the state")
        evs = [events[i] for i in caused if i in events]

        held = {h["name"]: h.get("shares") for h in s["holders"]}
        total, nominal, capital = s.get("shares_total"), s.get("nominal_eur"), s["capital_eur"]
        if len({_key(h["name"]) for h in s["holders"]}) != len(s["holders"]):
            errs.append(f"{tag}: a holder is listed twice (same name, or a spelling variant of it)")
        if any(v is not None and v < 0 for v in held.values()):
            errs.append(f"{tag}: negative holding")
        for h in s["holders"]:
            if h.get("siren") is not None and not luhn_ok(h["siren"]):
                errs.append(f"{tag}: SIREN {h['siren']!r} of {h['name']} is not a valid SIREN")
        if None not in held.values() and total is not None and sum(held.values()) != total:
            errs.append(f"{tag}: holdings add up to {sum(held.values())}, shares_total is {total}")
        pcts = [h.get("pct") for h in s["holders"]]
        if None not in pcts and abs(sum(pcts) - 100) > 0.05:
            errs.append(f"{tag}: percentages add up to {sum(pcts):.2f}")
        for h in s["holders"]:
            if None not in (h.get("shares"), h.get("pct"), total) and abs(h["pct"] - 100 * h["shares"] / total) > 0.005:
                errs.append(f"{tag}: pct of {h['name']} does not match its shares")
        if None not in (capital, total, nominal) and abs(capital - total * nominal) > 1e-6:
            errs.append(f"{tag}: capital {capital} != {total} shares x {nominal}")

        if prev is None:
            before, prev_held, prev_capital, prev_total = set(), {}, 0, 0
        else:
            before = set(prev["holders_map"])
            prev_held, prev_capital, prev_total = prev["holders_map"], prev["capital_eur"], prev.get("shares_total")
            if s["as_of"] < prev["as_of"]:
                errs.append(f"{tag}: timeline is not in chronological order")

        delta = sum(e["payload"]["amount_eur"] * (1 if e["event_code"] == INCREASE else -1)
                    for e in evs if e["event_code"] in (INCREASE, DECREASE))
        if prev is not None and capital - prev_capital != delta:
            errs.append(f"{tag}: capital moves by {capital - prev_capital} but its capital events sum to {delta}")
        for code, got in ((ENTRY, set(held) - before), (END, before - set(held))):
            declared = {e["payload"]["holder_name"] for e in evs if e["event_code"] == code}
            if declared != got:
                errs.append(f"{tag}: {code} events {sorted(declared)} != holder change {sorted(got)}")

        ratio = (s.get("corporate_action") or {}).get("ratio", 1)
        issued = sum(e["payload"]["shares_issued"] for e in evs if e["event_code"] == INCREASE) \
            - sum(e["payload"]["shares_cancelled"] for e in evs if e["event_code"] == DECREASE)
        if prev is not None and None not in (total, prev_total) and total != prev_total * ratio + issued:
            errs.append(f"{tag}: shares_total moves without a matching issue, cancellation or split")
        if prev is not None and not s.get("restated"):
            for name in sorted(set(held) | before):
                a, b, moved = prev_held.get(name, 0), held.get(name, 0), _moved(name, evs)
                if None not in (a, b, moved) and a * ratio + moved != b:
                    errs.append(f"{tag}: {name} goes {a} -> {b} but its events move {moved} "
                                f"(a movement is missing or counted twice)")
        prev = {**s, "holders_map": held}

    errs += _check_group(results.get("group", {}))
    for i in events:
        if used[i] != 1:
            errs.append(f"{i}: referenced by {used[i]} timeline states, expected exactly 1")
    return errs
