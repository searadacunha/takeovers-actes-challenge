"""results.json against the official schema and the business rules. No corpus needed."""
import copy
import json
import re

import pytest

from actes.build import ROOT
from actes.validate import check, luhn_ok

STATUSES = {"CONFIRMED", "SUPPORTED", "UNRESOLVED"}


def test_results_pass_schema_and_invariants(results, schema):
    assert check(results, schema) == []


def test_only_official_event_codes(results):
    official = {c["event_code"] for c in json.loads((ROOT / "schema" / "event_codes.json").read_text())["codes"]}
    assert {e["event_code"] for e in results["events"]} <= official


def test_every_event_and_state_is_qualified(results):
    assert {e["status"] for e in results["events"]} <= STATUSES
    assert {s["status"] for s in results["capital_timeline"]} <= STATUSES
    for e in results["events"]:
        if e["payload"].get("grounding") == "indirect":
            assert e.get("note"), f"{e['event_id']}: an indirectly grounded event must say so in a note"


def test_entries_and_exits_point_at_their_mechanism(results):
    """An entry or an exit is the consequence of a mechanism event of the same state, never a movement itself."""
    by_id = {e["event_id"]: e for e in results["events"]}
    state_of = {i: s["state_id"] for s in results["capital_timeline"] for i in s["caused_by"]}
    for e in results["events"]:
        if e["event_code"] in ("SHAREHOLDER_ENTRY", "SHAREHOLDER_END") and e["payload"]["mechanism"] != "CONSTITUTION":
            causes = e["payload"]["mechanism_event_ids"]
            assert causes and all(by_id[c]["event_code"] == e["payload"]["mechanism"] for c in causes)
            assert all(state_of[c] == state_of[e["event_id"]] for c in causes)


def test_capital_chain(results):
    chain = [(s["as_of"], s["capital_eur"], s["shares_total"]) for s in results["capital_timeline"]]
    assert chain == [
        ("2004-12-15", 37000, 370), ("2005-05-17", 150000, 1500), ("2005-08-16", 150000, 1500),
        ("2006-10-20", 150000, 1500), ("2006-10-20", 200000, 2000), ("2006-10-20", 200000, 2000),
        ("2007-09-07", 200000, 2000), ("2008-04-30", 200000, 2000), ("2008-06-27", 200000, 2000),
        ("2008-06-27", 200000, 200000), ("2008-06-27", 368102, 368102), ("2017-02-21", 217241, 217241),
        ("2018-03-23", 400000, 400000),
    ]
    last = results["capital_timeline"][-1]["holders"]
    assert [(h["name"], h["siren"], h["shares"], h["pct"]) for h in last] == [("HADEAN", "499979540", 400000, 100.0)]


def test_percentages_are_recomputed_from_shares(results):
    for s in results["capital_timeline"]:
        for h in s["holders"]:
            assert h["pct"] == (None if h["shares"] is None else round(100 * h["shares"] / s["shares_total"], 2))


def test_luhn():
    assert luhn_ok("480489707") and luhn_ok("499979540")
    assert not luhn_ok("480489708") and not luhn_ok("48048970") and not luhn_ok(480489707)


def state(r, sid):
    return next(s for s in r["capital_timeline"] if s["state_id"] == sid)


def holder(r, sid, name):
    return next(h for h in state(r, sid)["holders"] if h["name"] == name)


def dup_event(r):
    r["events"].append(copy.deepcopy(r["events"][0]))


def dangling(r):
    state(r, "S05")["caused_by"].append("E999")


def twice(r):
    state(r, "S13")["caused_by"].append("E14")


def bbox_pixels(r):
    r["events"][3]["source"]["bbox"] = [120, 340, 890, 410]


def bbox_inverted(r):
    r["events"][3]["source"]["bbox"] = [0.9, 0.5, 0.1, 0.6]


def bad_date(r):
    r["events"][3]["event_date"] = "2005-17-05"


def sale_moves_capital(r):
    state(r, "S06")["capital_eur"] = 222500


def entry_without_holder(r):
    s = state(r, "S06")
    s["holders"] = [h for h in s["holders"] if h["name"] != "Michel CAPGRAS"]


def contribution_counted_twice(r):  # HADEAN credited with the 822 shares as a transfer and again as an entry
    holder(r, "S07", "HADEAN")["shares"] = 1644


def seller_keeps_his_shares(r):     # the transfer credits the buyer but is not taken from the seller
    holder(r, "S06", "Xavier AUMONT")["shares"] = 967


def wrong_pct(r):
    holder(r, "S12", "HADEAN")["pct"] = 59.02


def name_variant(r):
    state(r, "S08")["holders"].append({"name": "Hadean", "siren": None, "kind": "COMPANY", "shares": None, "pct": None})


def negative(r):
    holder(r, "S08", "Antonio BLANCO MARINA")["shares"] = -953


def bad_siren(r):
    holder(r, "S13", "HADEAN")["siren"] = "499979541"


def unknown_code(r):
    r["events"][0]["event_code"] = "CAPITAL_SPLIT"


def out_of_order(r):
    t = r["capital_timeline"]
    t[11], t[12] = t[12], t[11]


def ownership_cycle(r):  # the subsidiary made a shareholder of its own parent
    edge = copy.deepcopy(r["group"]["edges"][0])
    r["group"]["edges"].append({**edge, "from": "ARCHEAN LABS", "to": "HADEAN"})


def edge_to_nowhere(r):
    r["group"]["edges"][0]["to"] = "ARCHEAN TECH"


def guessed_siren(r):  # a foreign company marked resolved with no SIREN to show for it
    next(n for n in r["group"]["nodes"] if n["name"] == "ARCHEAN MOTION")["resolved"] = True


def edge_without_evidence(r):
    del r["group"]["edges"][1]["source"]


def _event(r, event_id):
    return next(e for e in r["events"] if e["event_id"] == event_id)


def increase_before_previous_state(r):  # the 2018 increase moved before the 2017 buy-back state
    _event(r, "E39")["event_date"] = "2017-01-01"


def inverted_bounds(r):
    _event(r, "E24").update(earliest_date="2008-06-27", latest_date="2007-09-07")


def week_date_bound(r):
    _event(r, "E28")["latest_date"] = "2010-W48-2"


@pytest.mark.parametrize("mutate, expected", [
    (dup_event, "duplicate event_id"),
    (dangling, "is not an event"),
    (twice, "referenced by 2 timeline states"),
    (bbox_pixels, "schema:"),
    (bbox_inverted, "not a normalized top-left box"),
    (bad_date, "not YYYY-MM-DD"),
    (sale_moves_capital, "capital moves by"),
    (entry_without_holder, "SHAREHOLDER_ENTRY events"),
    (contribution_counted_twice, "counted twice"),
    (seller_keeps_his_shares, "counted twice"),
    (wrong_pct, "pct of HADEAN"),
    (name_variant, "spelling variant"),
    (negative, "negative holding"),
    (bad_siren, "not a valid SIREN"),
    (unknown_code, "schema:"),
    (out_of_order, "chronological order"),
    (ownership_cycle, "ownership cycle"),
    (edge_to_nowhere, "endpoint is not a node"),
    (guessed_siren, "resolved without a SIREN"),
    (edge_without_evidence, "no valid evidence box"),
    (increase_before_previous_state, "dated before the previous state"),
    (inverted_bounds, "earliest_date <= event_date <= latest_date"),
    (week_date_bound, "latest_date '2010-W48-2' is not YYYY-MM-DD"),
])
def test_validator_catches(results, schema, mutate, expected):
    broken = copy.deepcopy(results)
    mutate(broken)
    assert any(expected in e for e in check(broken, schema)), check(broken, schema)


def test_validator_reports_instead_of_raising_on_schema_valid_input(results, schema):
    """The official schema allows a null capital and a CAPITAL_INCREASE payload with only its official fields."""
    no_capital = copy.deepcopy(results)
    no_capital["capital_timeline"][-1]["capital_eur"] = None
    assert isinstance(check(no_capital, schema), list)
    official_payload = copy.deepcopy(results)
    e = _event(official_payload, "E39")
    e["payload"] = {k: e["payload"][k] for k in ("amount_eur", "capital_after_eur", "method")}
    assert isinstance(check(official_payload, schema), list)


def _printed(n, text):
    """n appears in text as a whole number, written 64655, 64 655, 64.655 or with a non-breaking space."""
    forms = {str(n)} | {f"{n:,}".replace(",", sep) for sep in (" ", ".", " ", " ")}
    return any(re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d])", text) for f in forms)


def test_confirmed_states_hold_only_stated_counts(results):
    """CONFIRMED is "stated by a filing": every holding of a CONFIRMED state is printed in a box it cites."""
    by_id = {e["event_id"]: e for e in results["events"]}
    for s in results["capital_timeline"]:
        if s["status"] != "CONFIRMED":
            continue
        cited = [x["snippet"] for x in s.get("evidence", [])]
        for i in s["caused_by"]:
            cited += [src["snippet"] for src in [by_id[i]["source"], *by_id[i].get("supporting_sources", [])]]
        text = " ".join(cited)
        for h in s["holders"]:
            if h["shares"] is not None and h["shares"] != s["shares_total"]:
                assert _printed(h["shares"], text), (s["state_id"], h["name"], h["shares"])


def test_status_follows_the_evidence(results):
    for e in results["events"]:
        if e["payload"].get("grounding") == "indirect":
            assert e["status"] != "CONFIRMED", e["event_id"]
    for s in results["capital_timeline"]:
        if any(h["shares"] is None for h in s["holders"]):
            assert s["status"] == "UNRESOLVED", s["state_id"]


def test_entry_and_exit_counts_match_the_timeline(results):
    """An entry's shares are held in the state it creates; an exit's shares were held in the state before."""
    states = results["capital_timeline"]
    position = {i: n for n, s in enumerate(states) for i in s["caused_by"]}
    for e in results["events"]:
        p = e["payload"]
        if e["event_code"] in ("SHAREHOLDER_ENTRY", "SHAREHOLDER_END") and p.get("shares") is not None:
            n = position[e["event_id"]] - (e["event_code"] == "SHAREHOLDER_END")
            held = {h["name"]: h["shares"] for h in states[n]["holders"]}
            assert held[p["holder_name"]] == p["shares"], e["event_id"]


def test_fund_entries_are_bounded_by_their_first_naming(results):
    """The four funds are first named on 21 February 2017; an earlier bound would rest on an assumption."""
    for i in ("E30", "E31", "E32", "E33"):
        assert _event(results, i)["latest_date"] >= "2017-02-21", i
