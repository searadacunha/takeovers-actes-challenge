"""Command line: inventory, lines, detect, build, proofs.  `python -m actes <command>`"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

from . import corpus, detect
from .ground import ground
from .replay import TRANSFER, replay, unknown
from .validate import check

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "ledger" / "archean.toml"
SCHEMA = ROOT / "schema" / "results.schema.json"
EVENT_EXTRAS = ("note", "date_precision", "earliest_date", "latest_date")


def load_ledger(path: Path = LEDGER) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _source(docs: dict, ref: dict) -> dict:
    src = ground(docs[ref["doc"]], ref["page"], ref["lines"])
    return {**src, "says": ref["says"]} if "says" in ref else src


def _payload(ev: dict) -> dict:
    p = {k: unknown(v) for k, v in ev.get("payload", {}).items()}
    if ev["code"] == TRANSFER:
        to, n = ev["to"], unknown(ev["shares"])
        p = {"from_name": ev["from"], "to_name": " and/or ".join(to) if isinstance(to, list) else to,
             "shares": None if n == "all" else n, **p}
        if isinstance(to, list):
            p["to_candidates"] = to
        if n == "all":
            p["all_shares_of_seller"] = True
    for key in ("allocations", "cancellations"):
        rows = [{"holder_name": k, "shares": unknown(v)} for k, v in ev.get(key, {}).items()]
        if any(r["shares"] is not None for r in rows):  # an all-unknown list would read as a list of subscribers
            p[key] = rows
    return p


def _group(g: dict, docs: dict) -> dict:
    nodes = [dict(n) for n in g["node"]]
    edges = []
    for e in g["edge"]:
        edge = {k: v for k, v in e.items() if k not in ("doc", "page", "lines", "says", "shares_total", "pct")}
        edge["pct"] = round(100 * e["shares"] / e["shares_total"], 2) if "shares_total" in e else e.get("pct")
        edges.append({**edge, "source": _source(docs, e)})

    # Every other company of the corpus: unrelated only if no filing on either side names the other.
    seen: dict[str, Counter] = {}
    for d in docs.values():  # the registry index spells a company several ways, or not at all
        name = (d.meta.get("denomination") or "").strip().lstrip("*")
        seen.setdefault(d.siren, Counter()).update([name] if name and name != "NON RENSEIGNE" else [])
    variants = {s: set(c) | {g.get("names", {}).get(s, s)} for s, c in seen.items()}
    names = {s: g.get("names", {}).get(s) or c.most_common(1)[0][0] for s, c in seen.items()}
    linked = {n["siren"] for n in nodes if n.get("siren")}
    mentions = detect.cross_mentions(docs, variants)
    has_ocr = {d.siren for d in docs.values() if any(d.ocr_dir.glob("page_*.json"))}
    for siren in sorted({d.siren for d in docs.values()} - linked):
        if any({a, b} & linked for a, b in mentions if siren in (a, b)):
            raise ValueError(f"{siren} {names[siren]} and a group company name each other: classify it in the ledger")
        nodes.append({"name": names[siren], "siren": siren, "resolved": True, "kind": "COMPANY", "in_group": False,
                      "basis": "No filing of this company names a group company and no group filing names it "
                               "(SIREN or denomination, OCR of both sides)." if siren in has_ocr else
                               "No group filing names it. Its own filings have no OCR and were not read."})
    return {"nodes": nodes, "edges": edges, "notes": " ".join(g["notes"].split())}


def build(ledger: dict, docs: dict) -> dict:
    events = []
    for step in ledger["step"]:
        for ev in step.get("event", []):
            e = {"event_id": ev["id"], "event_code": ev["code"], "event_date": ev["date"],
                 "payload": _payload(ev), "source": _source(docs, ev), "status": ev["status"],
                 **{k: ev[k] for k in EVENT_EXTRAS if k in ev}}
            if "also" in ev:
                e["supporting_sources"] = [_source(docs, r) for r in ev["also"]]
            events.append(e)
    timeline = replay(ledger)
    for state, step in zip(timeline, ledger["step"]):
        if "evidence" in step:
            state["evidence"] = [_source(docs, r) for r in step["evidence"]]
    results = {"siren": ledger["siren"], "events": events, "capital_timeline": timeline}
    if "group" in ledger:
        results["group"] = _group(ledger["group"], docs)
    results["notes"] = " ".join(ledger["notes"].split())
    return results


def _subject_actes(docs: dict, siren: str) -> list:
    return sorted((d for d in docs.values() if d.siren == siren and d.kind == "actes"), key=lambda d: d.deposit_date)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="actes", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory", help="list the subject's actes with page and OCR coverage")
    ln = sub.add_parser("lines", help="print the OCR lines of one page with their normalized boxes")
    ln.add_argument("inpi_id")
    ln.add_argument("page", type=int)
    sub.add_parser("detect", help="triage pages and cross-check every capital sentence against the timeline")
    b = sub.add_parser("build", help="ground the ledger, replay it, validate, write results.json")
    b.add_argument("-o", "--out", default=str(ROOT / "results.json"))
    pr = sub.add_parser("proofs", help="draw every cited box on its page with the official bbox_viewer.py")
    pr.add_argument("-o", "--out", default=str(ROOT / "proofs"))
    args = ap.parse_args(argv)

    docs = corpus.inventory()
    if not docs:
        sys.exit(f"no corpus under {corpus.data_dir()}: run scripts/fetch_corpus.sh or set ACTES_DATA_DIR")
    if args.cmd == "lines":
        for l in corpus.ocr_lines(docs[args.inpi_id], args.page):
            print(f"{l['bbox']}  {l['text']}")
        return 0
    ledger = load_ledger()

    if args.cmd == "inventory":
        for d in _subject_actes(docs, ledger["siren"]):
            pages = len(corpus.page_sizes(d.pdf))
            ocr = len(list(d.ocr_dir.glob("page_*.json")))
            what = "; ".join(filter(None, ((t.get("decision") or t.get("typeActe") or "").strip()
                                           for t in d.meta.get("typeRdd") or []))) or "(registry gives no label)"
            print(f"{d.deposit_date}  {d.inpi_id}  {pages:>2} p.  OCR {ocr:>2}/{pages:<2}  {what[:110]}")
        return 0

    results = build(ledger, docs)
    problems = check(results, json.loads(SCHEMA.read_text(encoding="utf-8")))

    if args.cmd == "detect":
        actes = _subject_actes(docs, ledger["siren"])
        cited = Counter((e["source"]["inpi_id"], e["source"]["page"]) for e in results["events"])
        for d in actes:
            flagged = detect.triage(d)
            used = sorted(p for (i, p) in cited if i == d.inpi_id)
            print(f"{d.deposit_date} {d.inpi_id}: flagged {sorted(flagged) or '-'}, cited {used or '-'}")
        found = [s for d in actes for s in detect.statements(d)]
        labelled = detect.crosscheck(found, results["events"])
        print("\ncapital sentences:", dict(Counter(s["label"] for s in labelled)))
        for s in labelled:
            if s["label"] in ("contradicts", "unexplained"):
                print(f"  {s['label'].upper()} {s['event_id'] or ''} {s['inpi_id']} p{s['page']}: {s['text']}")
        return 0

    if args.cmd == "build":
        for p in problems:
            print("INVALID:", p, file=sys.stderr)
        if problems:
            return 1
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}: {len(results['events'])} events, {len(results['capital_timeline'])} states, "
              f"schema and invariants OK")
        return 0

    if args.cmd == "proofs":
        viewer = corpus.data_dir().parent / "tools" / "bbox_viewer.py"
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        cited = [(e["event_id"], e["source"]) for e in results["events"]]
        cited += [(f"{e['event_id']}_also{n}", src) for e in results["events"]
                  for n, src in enumerate(e.get("supporting_sources", []), 1)]
        cited += [(f"{s['state_id']}_evidence{n}", src) for s in results["capital_timeline"]
                  for n, src in enumerate(s.get("evidence", []), 1)]
        cited += [(f"edge{n}", e["source"]) for n, e in enumerate(results.get("group", {}).get("edges", []), 1)]
        for name, src in cited:
            doc = docs[src["inpi_id"]]
            dpi = round(1300 * 72 / corpus.page_sizes(doc.pdf)[src["page"] - 1][0])  # about 1300 px wide
            subprocess.run([sys.executable, "-I", str(viewer), "--pdf", str(doc.pdf), "--page", str(src["page"]),
                            "--ocr", str(doc.ocr_dir), "--bbox", ",".join(map(str, src["bbox"])),
                            "--dpi", str(dpi), "-o", str(out / f"{name}.png")], check=True, stdout=subprocess.DEVNULL)
        print(f"wrote {len(cited)} proof images to {out}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
