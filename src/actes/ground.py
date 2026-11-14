"""Anchor -> evidence. A source is only ever built from OCR lines that exist on the cited page.

The ledger never stores coordinates. It stores, for each fact, the document, the page and a few
words copied from the OCR ("anchors"). This module finds the OCR lines carrying those words and
returns the union of their boxes. An anchor that matches no line, or more than one, is an error:
there is no fallback box.
"""
from __future__ import annotations

from .corpus import Doc, norm, ocr_lines


class GroundingError(ValueError):
    pass


def ground(doc: Doc, page: int, anchors: list) -> dict:
    """anchors: strings, or {"text": ..., "nth": k} to pick the k-th matching line (1-based)."""
    lines = ocr_lines(doc, page)
    picked: list[dict] = []
    for a in anchors:
        text, nth = (a["text"], a.get("nth")) if isinstance(a, dict) else (a, None)
        hits = [l for l in lines if norm(text) in norm(l["text"])]
        if (nth is None and len(hits) != 1) or (nth is not None and not 1 <= nth <= len(hits)):
            raise GroundingError(f"{doc.inpi_id} p{page}: anchor {text!r} matches {len(hits)} OCR line(s)"
                                 + (f" (nth={nth})" if nth else ""))
        hit = hits[(nth or 1) - 1]
        if hit not in picked:
            picked.append(hit)
    picked.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))
    return {
        "inpi_id": doc.inpi_id,
        "page": page,
        "bbox": [min(l["bbox"][0] for l in picked), min(l["bbox"][1] for l in picked),
                 max(l["bbox"][2] for l in picked), max(l["bbox"][3] for l in picked)],
        "snippet": " ".join(l["text"].strip() for l in picked),
    }
