"""Rule-based detection over the OCR text. Two uses, both measurable:

triage()      pages worth a human read (capital and shareholder vocabulary). The reviewed ledger
              must cite only pages this flags: that is the recall test.
statements()  every sentence that states a capital change or level, parsed to numbers. Each one is
              then compared with the replayed timeline: it corroborates an event, or it
              contradicts one, or it is unexplained. Nothing is silently dropped.
"""
from __future__ import annotations

import re
import unicodedata

from .corpus import Doc, norm, page_sizes, page_text

TRIAGE = {
    "CAPITAL_INCREASE": r"augment\w* (?:de |du |le |ce )?capital[^.]{0,200}?\d{3,} ?(?:euros?|€)|a ete augmente de \d+",
    "CAPITAL_DECREASE": r"redu\w+ (?:de |du |le )?capital[^.]{0,200}?\d{3,} ?(?:euros?|€)|(?:a ete|est) reduit de \d+|"
                        r"actions rachetees",
    "SHAREHOLDER_SHARE_TRANSFER": r"ceder \d+ actions|cession de la totalite des actions|ordres? de mouvement|"
                                  r"apport de \d+ actions|fait apport de la pleine propriete|\d+ titres qu.il detient",
    "SHAREHOLDER_ENTRY": r"agree a devenir actionnaire|agrement d.un nouvel actionnaire",
    "HOLDERS": r"feuille de presence|associee? unique de la|integralement detenues par|repartition suivante|"
               r"\d+ actions sur les \d+ actions",
    "CAPITAL_DUAL_CLASS": r"cre(?:er|ation) d(?:es |.)actions de preference",
}
ALLOCATION_LINE = r"(?:pour )?\d+ actions"   # a table row that is only a share count

MONEY = r"(\d+) ?(?:euros?|€)"
PATTERNS = {
    # "augmenter le capital d'une somme de 50000 euros, pour le porter de 150000 euros a 200000 euros"
    "increase": rf"augment\w*[^.]{{0,200}}?\bde {MONEY}[^.]{{0,200}}?port\w+[^0-9.]{{0,40}}?(?:de {MONEY} )?"
                rf"a (?:la somme de )?{MONEY}",
    # "reduit de 150861 euros pour etre ramene de 368102 euros a 217241 euros"
    "decrease": rf"redu\w+[^.]{{0,200}}?\bde {MONEY}[^.]{{0,200}}?ramen\w+[^0-9.]{{0,40}}?(?:de {MONEY} )?"
                rf"a (?:la somme de )?{MONEY}",
    # "le capital est porte de 150000 a 200000 euros", "reduira le capital de 368102 euros a 217241 euros"
    "from_to": rf"capital[^.]{{0,80}}? de (\d+) (?:euros? )?a {MONEY}",
    # "le capital social est fixe a la somme de ... (150000) euros"
    "fixed": rf"capital social est fixe a[^.]{{0,90}}?\(?{MONEY}",
}


def canon(text: str) -> str:
    """Lowercase, no accents, one line, numbers without thousand separators or OCR letter-zeros."""
    t = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", t.lower().replace("’", "'"))

    def number(m: re.Match) -> str:  # OCR reads 0 as o, and a leading 1 as i or l
        return re.sub(r"[ .]", "", m.group(0).replace("o", "0").replace("i", "1").replace("l", "1"))

    t = re.sub(r"(?<![a-z0-9])(?:[il]\d{1,2}|\d{1,3})(?:[ .][\do]{3})+(?![a-z0-9])", number, t)  # 37.0o0 -> 37000
    t = re.sub(r"(\d),\d\d(?!\d)", r"\1", t)                                         # 150000,00 -> 150000
    return re.sub(r"(\d) ?\) ?(euros?|€)", r"\1 \2", t)                              # (150000) euros


def triage(doc: Doc) -> dict[int, list[str]]:
    """page -> codes whose operative vocabulary (with figures) appears on it."""
    out = {}
    for page in range(1, len(page_sizes(doc.pdf)) + 1):
        raw = page_text(doc, page)
        text = canon(raw)
        hits = [code for code, rx in TRIAGE.items() if re.search(rx, text)]
        if "HOLDERS" not in hits and any(re.fullmatch(ALLOCATION_LINE, canon(l)) for l in raw.split("\n")):
            hits.append("HOLDERS")
        if hits:
            out[page] = hits
    return out


def statements(doc: Doc) -> list[dict]:
    """[{kind, page, amount, before, after, text}] for every capital sentence in the document."""
    found = []
    for page in range(1, len(page_sizes(doc.pdf)) + 1):
        text = canon(page_text(doc, page))
        for kind, rx in PATTERNS.items():
            for m in re.finditer(rx, text):
                g = [int(x) if x else None for x in m.groups()]
                amount, before, after = g if len(g) == 3 else (None, g[0], g[1]) if len(g) == 2 else (None, None, g[0])
                found.append({"kind": kind, "inpi_id": doc.inpi_id, "page": page, "amount": amount,
                              "before": before, "after": after, "text": m.group(0)[:240]})
    return found


def crosscheck(found: list[dict], events: list[dict]) -> list[dict]:
    """Label each statement against the capital events of a results.json.

    corroborates  same figures as an event
    level         a capital level the timeline goes through
    contradicts   same target capital as an event, different amount (or the reverse)
    unexplained   matches nothing
    """
    moves = []
    capital = None
    for e in events:
        if e["event_code"] in ("CAPITAL_INCREASE", "CAPITAL_DECREASE"):
            p = e["payload"]
            sign = 1 if e["event_code"] == "CAPITAL_INCREASE" else -1
            moves.append({"id": e["event_id"], "amount": p["amount_eur"], "after": p["capital_after_eur"],
                          "before": p["capital_after_eur"] - sign * p["amount_eur"], "sign": sign})
    levels = {m["after"] for m in moves} | {m["before"] for m in moves}
    out = []
    for s in found:
        label, ref = "unexplained", None
        if s["kind"] == "fixed":
            label = "level" if s["after"] in levels else "unexplained"
        else:
            sign = {"increase": 1, "decrease": -1}.get(s["kind"])
            for m in moves:
                same_after = s["after"] == m["after"] and (sign is None or sign == m["sign"])
                ok_amount = s["amount"] is None or s["amount"] == m["amount"]
                ok_before = s["before"] is None or s["before"] == m["before"]
                if same_after and ok_amount and ok_before:
                    label, ref = "corroborates", m["id"]
                    break
                if same_after or (s["amount"] == m["amount"] and s["before"] == m["before"]):
                    label, ref = "contradicts", m["id"]
        out.append({**s, "label": label, "event_id": ref})
    return out


def cross_mentions(docs: dict, names: dict[str, set[str]]) -> set[tuple[str, str]]:
    """(a, b): a filing of company a names company b, by SIREN or by one of its full denominations.

    A mention proves nothing about ownership. Its absence on both sides is what lets the build call
    a company unrelated without anyone having to assert it.
    """
    wanted = {s: (re.compile(r"(?<!\d)" + r"[ .]?".join((s[:3], s[3:6], s[6:])) + r"(?!\d)"),
                  [n for n in map(norm, v) if len(n) >= 6]) for s, v in names.items()}
    found = set()
    for d in docs.values():
        for page in range(1, len(page_sizes(d.pdf)) + 1):
            text = page_text(d, page)
            if not text:
                continue
            flat = norm(text)
            for siren, (rx, variants) in wanted.items():
                if siren != d.siren and (rx.search(text) or any(v in flat for v in variants)):
                    found.add((d.siren, siren))
    return found
