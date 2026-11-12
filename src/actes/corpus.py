"""Corpus access: inventory, registry metadata, OCR lines, pixel -> normalized boxes."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

OCR_DPI = 300          # the shipped OCR polygons are pixels at 300 dpi
POINTS_PER_INCH = 72   # PDF page sizes are in points


def data_dir() -> Path:
    env = os.environ.get("ACTES_DATA_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "upstream" / "data"


@dataclass(frozen=True)
class Doc:
    siren: str
    kind: str            # "actes" or "bilans"
    inpi_id: str
    deposit_date: str    # registry deposit date, from the file name. Never used as an event date.
    pdf: Path
    meta: dict = field(compare=False, hash=False)

    @property
    def ocr_dir(self) -> Path:
        return self.pdf.parents[1] / "ocr" / self.inpi_id


def inventory(root: Path | None = None) -> dict[str, Doc]:
    """Every acte and bilan of every company in the corpus, keyed by its 24-character INPI id."""
    docs: dict[str, Doc] = {}
    for pdf in sorted((root or data_dir()).glob("*/*/pdf/*.pdf")):
        _, deposit, inpi_id = pdf.stem.split("_")
        meta_path = pdf.parents[1] / "meta" / f"{pdf.stem}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        if inpi_id in docs:
            raise ValueError(f"INPI id {inpi_id} appears twice in the corpus")
        docs[inpi_id] = Doc(pdf.parents[2].name, pdf.parents[1].name, inpi_id, deposit, pdf, meta)
    return docs


@lru_cache(maxsize=None)
def page_sizes(pdf: Path) -> tuple[tuple[float, float], ...]:
    import pymupdf

    with pymupdf.open(pdf) as d:
        return tuple((p.rect.width, p.rect.height) for p in d)


def px_to_norm(polygon, w_pt: float, h_pt: float) -> list[float]:
    """Four [x, y] points in 300-dpi pixels -> [x0, y0, x1, y1] as fractions of the page."""
    scale = OCR_DPI / POINTS_PER_INCH
    xs = [p[0] / (w_pt * scale) for p in polygon]
    ys = [p[1] / (h_pt * scale) for p in polygon]
    return [round(min(1.0, max(0.0, v)), 4) for v in (min(xs), min(ys), max(xs), max(ys))]


@lru_cache(maxsize=None)
def ocr_lines(doc: Doc, page: int) -> tuple[dict, ...]:
    """OCR lines of one page (1-indexed), top to bottom, each with its normalized box."""
    path = doc.ocr_dir / f"page_{page:03d}.json"
    if not path.exists():
        return ()
    w, h = page_sizes(doc.pdf)[page - 1]
    raw = json.loads(path.read_text(encoding="utf-8")).get("ocr") or []
    lines = [{"text": l["text"], "bbox": px_to_norm(l["polygon"], w, h), "score": l.get("score")}
             for l in raw if l.get("polygon") and l.get("text")]
    return tuple(sorted(lines, key=lambda l: (l["bbox"][1], l["bbox"][0])))


def page_text(doc: Doc, page: int) -> str:
    return "\n".join(l["text"] for l in ocr_lines(doc, page))


def norm(s: str) -> str:
    """Case-, accent- and punctuation-insensitive form, used to match anchors against noisy OCR."""
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
