"""The replay on a scenario small enough to compute by hand, then the ledgers it must refuse."""
import copy

import pytest

from actes.replay import LedgerError, alias_index, replay

HOLDERS = {n: {"kind": "PERSON"} for n in ("Alice", "Bob", "Carol", "Dan")}


def entry(i, name):
    return {"id": i, "code": "SHAREHOLDER_ENTRY", "payload": {"holder_name": name}}


def end(i, name):
    return {"id": i, "code": "SHAREHOLDER_END", "payload": {"holder_name": name}}


def transfer(i, src, dst, n):
    return {"id": i, "code": "SHAREHOLDER_SHARE_TRANSFER", "from": src, "to": dst, "shares": n}


def increase(i, amount, after, issued, alloc):
    return {"id": i, "code": "CAPITAL_INCREASE", "allocations": alloc,
            "payload": {"amount_eur": amount, "capital_after_eur": after, "shares_issued": issued}}


def scenario():
    """1 incorporation, 2 entry of a new shareholder, 3 partial sale, 4 total sale, 5 capital increase."""
    return {"holders": HOLDERS, "step": [
        {"id": "1", "as_of": "2020-01-01", "status": "CONFIRMED",
         "formation": {"capital_eur": 1000, "nominal_eur": 10, "holders": {"Alice": 60, "Bob": 40}},
         "event": [entry("a", "Alice"), entry("b", "Bob")]},
        {"id": "2", "as_of": "2020-02-01", "status": "CONFIRMED",          # Bob sells 10 to newcomer Carol
         "event": [transfer("c", "Bob", "Carol", 10), entry("d", "Carol")]},
        {"id": "3", "as_of": "2020-03-01", "status": "CONFIRMED",          # Alice sells 20 of her 60 to Carol
         "event": [transfer("e", "Alice", "Carol", 20)]},
        {"id": "4", "as_of": "2020-04-01", "status": "CONFIRMED",          # Bob sells everything to Alice
         "event": [transfer("f", "Bob", "Alice", "all"), end("g", "Bob")]},
        {"id": "5", "as_of": "2020-05-01", "status": "CONFIRMED",          # 50 new shares, all to newcomer Dan
         "event": [increase("h", 500, 1500, 50, {"Dan": 50}), entry("i", "Dan")]},
    ]}


def held(state):
    return {h["name"]: h["shares"] for h in state["holders"]}


def test_scenario_by_hand():
    s = replay(scenario())
    assert [held(x) for x in s] == [
        {"Alice": 60, "Bob": 40},
        {"Alice": 60, "Bob": 30, "Carol": 10},
        {"Alice": 40, "Bob": 30, "Carol": 30},
        {"Alice": 70, "Carol": 30},
        {"Alice": 70, "Carol": 30, "Dan": 50},
    ]
    assert [(x["capital_eur"], x["shares_total"], x["nominal_eur"]) for x in s] == \
        [(1000, 100, 10)] * 4 + [(1500, 150, 10)]          # a sale never moves the capital
    assert {h["name"]: h["pct"] for h in s[-1]["holders"]} == {"Alice": 46.67, "Dan": 33.33, "Carol": 20.0}


def test_entry_alone_moves_nothing():
    """An entry is a consequence. Declared without the sale that causes it, the ledger is refused."""
    led = scenario()
    led["step"][1]["event"] = [entry("d", "Carol")]
    with pytest.raises(LedgerError, match="entries/exits"):
        replay(led)


def test_sale_without_its_entry_is_refused():
    led = scenario()
    led["step"][1]["event"] = [transfer("c", "Bob", "Carol", 10)]
    with pytest.raises(LedgerError, match="entries/exits"):
        replay(led)


def test_exit_must_be_declared():
    led = scenario()
    led["step"][3]["event"] = [transfer("f", "Bob", "Alice", "all")]
    with pytest.raises(LedgerError, match="entries/exits"):
        replay(led)


def test_cannot_sell_more_than_held():
    led = scenario()
    led["step"][2]["event"] = [transfer("e", "Alice", "Carol", 61)]
    with pytest.raises(LedgerError, match="holds 60"):
        replay(led)


def test_same_sale_twice_is_caught():
    """Bob has 30 shares after step 2: selling 'the same' 30 twice cannot go through."""
    led = scenario()
    led["step"][3]["event"] = [transfer("f", "Bob", "Alice", 30), transfer("f2", "Bob", "Alice", 30), end("g", "Bob")]
    with pytest.raises(LedgerError, match="holds 0"):
        replay(led)


def test_increase_must_reach_stated_capital_and_allocate_every_share():
    led = scenario()
    led["step"][4]["event"][0] = increase("h", 500, 1600, 50, {"Dan": 50})
    with pytest.raises(LedgerError, match="capital after"):
        replay(led)
    led["step"][4]["event"][0] = increase("h", 500, 1500, 50, {"Dan": 49})
    with pytest.raises(LedgerError, match="allocations"):
        replay(led)


def test_unknown_counts_stay_unknown_until_attested():
    led = scenario()
    led["step"][2]["event"] = [transfer("e", "Alice", "Carol", "?")]
    s = replay(copy.deepcopy(led))
    assert held(s[2]) == {"Alice": None, "Bob": 30, "Carol": None}
    assert all(h["pct"] is None for h in s[2]["holders"] if h["shares"] is None)
    led["step"][2]["attested"] = {"Alice": 45, "Carol": 25}
    assert held(replay(led)[2]) == {"Alice": 45, "Bob": 30, "Carol": 25}


def test_attested_figure_that_contradicts_the_replay_needs_a_reason():
    led = scenario()
    led["step"][2]["attested"] = {"Alice": 41}
    with pytest.raises(LedgerError, match="the document says 41"):
        replay(copy.deepcopy(led))
    led["step"][2]["attested"] = {"Alice": 41, "Carol": 29}
    led["step"][2]["restated"] = "the filing disagrees"
    assert held(replay(led)[2]) == {"Alice": 41, "Bob": 30, "Carol": 29}


def test_undeclared_holder_and_shared_alias_are_refused():
    led = scenario()
    led["step"][1]["event"] = [transfer("c", "Bob", "Carole", 10), entry("d", "Carole")]
    with pytest.raises(LedgerError, match="not a declared holder"):
        replay(led)
    with pytest.raises(LedgerError, match="claimed by"):
        alias_index({"Alice": {"aliases": ["A. Martin"]}, "Bob": {"aliases": ["a martin"]}})
