"""results.json against the corpus: every cited box is where it says, and says what it says."""
import importlib.util
import json

from actes import corpus, detect
from actes.build import build
from actes.corpus import norm
from actes.replay import alias_index

SUBJECT = "480489707"


def sources(results):
    for e in results["events"]:
        yield e["event_id"], e["source"]
        for n, s in enumerate(e.get("supporting_sources", []), 1):
            yield f"{e['event_id']}.also{n}", s
    for st in results["capital_timeline"]:
        for n, s in enumerate(st.get("evidence", []), 1):
            yield f"{st['state_id']}.evidence{n}", s
    for n, e in enumerate(results.get("group", {}).get("edges", []), 1):
        yield f"edge{n}", e["source"]


def test_reviewed_corpus_is_unchanged(docs):
    """The ledger was written against 17 actes with OCR on every page. If that moves, review again."""
    actes = [d for d in docs.values() if d.siren == SUBJECT and d.kind == "actes"]
    assert len(actes) == 17
    assert sum(len(corpus.page_sizes(d.pdf)) for d in actes) == 293
    assert all(len(list(d.ocr_dir.glob("page_*.json"))) == len(corpus.page_sizes(d.pdf)) for d in actes)


def test_build_is_reproducible(results, ledger, docs):
    assert build(ledger, docs) == results


def test_documents_and_pages_exist(results, docs):
    for name, s in sources(results):
        assert s["inpi_id"] in docs, name
        assert 1 <= s["page"] <= len(corpus.page_sizes(docs[s["inpi_id"]].pdf)), name


def test_snippet_is_the_ocr_text_inside_the_box(results, docs):
    """Read the box back without the grounding code: the OCR lines inside it must spell the snippet."""
    for name, s in sources(results):
        x0, y0, x1, y1 = s["bbox"]
        rest = s["snippet"]
        for line in corpus.ocr_lines(docs[s["inpi_id"]], s["page"]):
            a, b, c, d = line["bbox"]
            if a >= x0 and b >= y0 and c <= x1 and d <= y1 and rest.startswith(line["text"].strip()):
                rest = rest[len(line["text"].strip()):].lstrip()
        assert rest == "", f"{name}: {rest!r} is not OCR text inside the cited box"


def test_boxes_match_the_official_viewer_conversion(results, docs):
    """Same polygons through tools/bbox_viewer.py's own polygon_to_norm."""
    path = corpus.data_dir().parent / "tools" / "bbox_viewer.py"
    spec = importlib.util.spec_from_file_location("bbox_viewer", path)
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)
    for inpi_id, page in {(s["inpi_id"], s["page"]) for _, s in sources(results)}:
        doc = docs[inpi_id]
        w, h = corpus.page_sizes(doc.pdf)[page - 1]
        raw = json.loads((doc.ocr_dir / f"page_{page:03d}.json").read_text(encoding="utf-8"))["ocr"]
        for line in raw:
            official = viewer.polygon_to_norm(line["polygon"], w, h)
            mine = corpus.px_to_norm(line["polygon"], w, h)
            assert all(abs(min(1, max(0, o)) - m) <= 5e-5 for o, m in zip(official, mine))


def test_boxes_sit_on_ink(results, docs):
    """Render each box from the PDF itself: a box on blank paper means a wrong page or a wrong scale."""
    import pymupdf

    for name, s in sources(results):
        with pymupdf.open(docs[s["inpi_id"]].pdf) as pdf:
            page = pdf[s["page"] - 1]
            r = page.rect
            clip = pymupdf.Rect(r.x0 + s["bbox"][0] * r.width, r.y0 + s["bbox"][1] * r.height,
                                r.x0 + s["bbox"][2] * r.width, r.y0 + s["bbox"][3] * r.height)
            zoom = 900 / r.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csGRAY)
        dark = sum(1 for v in pix.samples if v < 128) / len(pix.samples)
        assert dark > 0.01, f"{name}: only {dark:.1%} of the box is ink"


def test_parties_are_named_in_the_cited_passages(results, ledger):
    index = alias_index(ledger["holders"])
    names_of = {}
    for alias, canonical in index.items():
        names_of.setdefault(canonical, []).append(alias)
    for e in results["events"]:
        p = e["payload"]
        if e["event_code"] not in ("SHAREHOLDER_ENTRY", "SHAREHOLDER_END", "SHAREHOLDER_SHARE_TRANSFER") \
                or p.get("grounding") == "indirect":
            continue
        text = norm(" ".join([e["source"]["snippet"]] + [s["snippet"] for s in e.get("supporting_sources", [])]))
        parties = [p["holder_name"]] if "holder_name" in p else [p["from_name"], *(p.get("to_candidates") or [p["to_name"]])]
        for party in parties:
            assert any(a in text for a in names_of[party]), f"{e['event_id']}: {party} is not named in the cited text"


def test_detector_flags_every_cited_page_and_only_known_contradictions(results, ledger, docs):
    actes = [d for d in docs.values() if d.siren == SUBJECT and d.kind == "actes"]
    flagged = {(d.inpi_id, p) for d in actes for p in detect.triage(d)}
    cited = {(e["source"]["inpi_id"], e["source"]["page"]) for e in results["events"]
             if docs[e["source"]["inpi_id"]].siren == SUBJECT and docs[e["source"]["inpi_id"]].kind == "actes"}
    assert cited <= flagged, sorted(cited - flagged)

    labelled = detect.crosscheck([s for d in actes for s in detect.statements(d)], results["events"])
    assert not [s for s in labelled if s["label"] == "unexplained"]
    assert sum(s["label"] == "corroborates" for s in labelled) >= 30
    contradictions = {(s["inpi_id"], s["page"], s["amount"], s["after"]) for s in labelled if s["label"] == "contradicts"}
    assert contradictions == {(d["doc"], d["page"], d["amount"], d["after"]) for d in ledger["discrepancy"]}


def test_group_covers_the_whole_corpus_and_no_unrelated_company_is_named(results, docs):
    """Each of the 20 companies is a node, and a company is 'not in the group' only when no filing links it."""
    nodes = {n["siren"]: n for n in results["group"]["nodes"] if n.get("siren")}
    corpus_sirens = {d.siren for d in docs.values()}
    assert len(corpus_sirens) == 20 and corpus_sirens <= set(nodes)
    inside = {s for s in corpus_sirens if nodes[s]["in_group"]}
    assert inside == {"480489707", "499979540", "843071218", "352890354"}
    names = {s: {n["name"]} for s, n in nodes.items() if s in corpus_sirens}
    for a, b in detect.cross_mentions(docs, names):
        assert (a in inside) == (b in inside), f"{a} names {b}: one is in the group and the other is not"
