# Reference projects looked at, and what each one changed

Eight public repositories were read before deciding whether to add or replace anything. One check was
adopted. Nothing else changed, and the reasons are below.

How they were read: a sub-agent of Claude Code read the files listed for each project through the
GitHub API (no clone, no install, no code run). I then confirmed each commit hash against the API, and
read the Luhn helper of Citrus myself. Where a point was not verified, it says so.

## Decision matrix

| need | what the pipeline does | reference | change |
|---|---|---|---|
| read the PDFs | PyMuPDF 2.1: page sizes in points, page rendering | PyMuPDF | none, already used |
| text positions | the shipped OCR polygons (pixels at 300 dpi), converted to 0-1 boxes | PyMuPDF `get_text("words")` | not applicable: the 17 PDFs are image scans with 0 embedded characters (measured) |
| OCR | the shipped OCR: 293 of 293 pages, 11 254 lines, mean confidence 0.971 | OCRmyPDF, docTR | none: coverage is complete and there is no reference text to compare a second engine against |
| layout and tables | OCR lines in reading order; table cells are cited one by one with explicit anchors | Docling | none: PyTorch and model downloads for a handful of three-row tables that the anchors already ground |
| JSON validation | `jsonschema` 4.26, `Draft202012Validator.iter_errors`, then business rules in `validate.py` | jsonschema | none, already used. The format checker was not turned on: the official schema declares no `format` |
| company graph | 26 nodes, 9 edges, checks in 30 lines of standard library (endpoints, duplicates, ownership cycle) | NetworkX | none |
| SIREN and names | canonical names with explicit aliases, no fuzzy matching | Citrus (INSEE) | **adopted: Luhn checksum on every SIREN**, in `validate.luhn_ok` |
| provenance, resume | anchors resolved at build time; the build is deterministic and takes 6 seconds | legal-ocr-pipeline | none |

## Coordinates: PyMuPDF against the shipped OCR

PyMuPDF cannot give text coordinates for these files, because none of the 17 PDFs has a text layer.
What could be compared is the geometry:

- With the page size PyMuPDF reports (points) and the factor 300 / 72, the largest OCR coordinate of
  every one of the 17 documents falls between 0.887 and 1.000 of the page. The convention holds for
  both families of files: 10 with A4 pages (595 x 842 points, 578 x 825 for one) and 7 whose pages are
  about 1 653 x 2 352 points, the scan's pixel grid stored as points.
- Every cited box, rendered from the PDF by PyMuPDF, contains ink (`test_boxes_sit_on_ink`).
- Every OCR line of every cited page converts to the same box as `polygon_to_norm` in the official
  `tools/bbox_viewer.py` (`test_boxes_match_the_official_viewer_conversion`).

## Per project

### pymupdf/PyMuPDF

- https://github.com/pymupdf/PyMuPDF , release 2.1 (installed), commit `f318af511d1860d88ac84f7f4ac71d59648a873a`
- Read: `README.md`, `docs/page.rst`, `docs/textpage.rst`, `docs/recipes-ocr.rst` (search only)
- Kept: `page.rect` for the page size in points (it already accounts for rotation and crop box) and
  `get_pixmap` for rendering, including the clipped renders of the ink test.
- Not used: `get_textpage_ocr` (needs Tesseract and its language data, not installed) and
  `find_tables` (its default strategy reads vector lines, which a scan does not have).
- Limit: no cited page is rotated. A rotated page exists elsewhere in the corpus and would need a check
  of which frame the OCR polygons use. Licence is AGPL-3.0.

### docling-project/docling

- https://github.com/docling-project/docling , release v2.150.0, commit `a7760abf0ca53321a3fb5ae9b1a65b584bb743b9`
- Read: `README.md`, `pyproject.toml`, `docs/concepts/OCR.md`, `docs/concepts/docling_document.md`,
  `docs/getting_started/installation.md`, `docs/usage/index.md`
- Declined. It would re-run OCR and layout models (PyTorch, downloaded weights) on pages that already
  have a complete OCR, and its boxes would then have to be reconciled with the shipped ones.
- Not verified: the coordinate origin of its bounding boxes (it lives in `docling-core`, not read) and
  the install size.

### ocrmypdf/OCRmyPDF

- https://github.com/ocrmypdf/OCRmyPDF , release v17.14.1, commit `3343116ba204c99c9fee762d538dc1b668711bfb`
- Read: `README.md`, `docs/cookbook.md`, `docs/introduction.md`, `docs/installation.md`, `pyproject.toml`
- Declined. It needs Tesseract, and it writes a new PDF: with `--deskew` or `--rotate-pages` the page
  content moves, which would break the mapping between the shipped OCR polygons and the page.
- Would be the first thing to try on a document with no OCR, on a copy, with `--skip-text`.

### mindee/doctr

- https://github.com/mindee/doctr , release v1.1.0, commit `dbcee0d7604009b034eb91c5185eb13cee3fd0bc`
- Read: `README.md`, `doctr/io/elements.py`
- Reference only. Its word geometry is already relative to the page, `((xmin, ymin), (xmax, ymax))`,
  the same convention as the boxes submitted here. Not installed: PyTorch and model downloads, and no
  ground truth to decide between two OCR outputs.

### python-jsonschema/jsonschema

- https://github.com/python-jsonschema/jsonschema , release v4.26.0 (installed), commit `8c27862e39683696847884524483f929de3caabe`
- Read: `README.rst`, `docs/validate.rst`
- Already used: `Draft202012Validator(schema).iter_errors(results)` reports every error at once.
- `format` is not asserted unless a format checker is passed. The official schema has no `format`
  keyword (dates are described as "YYYY-MM-DD" in prose), so the checker would do nothing here. Dates
  are parsed in `validate.py` instead.

### networkx/networkx

- https://github.com/networkx/networkx , release networkx-3.7, commit `5f9d15fb7e40d00f75908760725fb0c7dc1f50d4`
- Read: `pyproject.toml`, `networkx/algorithms/cycles.py`, `networkx/algorithms/dag.py` (search only)
- Declined for now. `MultiDiGraph` and `is_directed_acyclic_graph` are the right tools once the graph
  has dated edges for many companies. For 9 edges, the endpoint, duplicate and cycle checks fit in
  `validate._check_group`.

### InseeFrLab/citrus

- https://github.com/InseeFrLab/citrus , no release, commit `e2f8ffacafbd6b8c751debe08ecc0f0b3738875a`
- Read: `README.md`, `src/bodacc/normalization.py`, `docs/coherence_prompts.md`, `evaluate.py` (search
  only), and the two lines of `is_luhn_valid` in `src/utils.py`
- **Adopted, as an idea and not as code:** a SIREN is nine digits with a Luhn checksum. `luhn_ok` runs
  on every holder and every group node, and the tests inject an off-by-one SIREN to prove it bites.
  It would have stopped nothing in this submission, but it is the check that catches a misread digit.
- Also noted: Citrus scores its extraction against human-annotated operations. This repository has no
  annotated reference (the challenge has no answer key), which is why its tests are invariants and
  cross-checks between documents, not accuracy figures.
- Not applicable: its source is the BODACC, one model call per announcement.

### OpenLegalCore/legal-ocr-pipeline

- https://github.com/OpenLegalCore/legal-ocr-pipeline , release v0.1.2, commit `f3299840449123cca3e8a01db3b1441ad01d5eb0`
- Read: `README.md`, `vertex_parallel_pdf_ocr.py` (search only), `requirements.txt`
- Declined. It sends each page to a paid Google Vertex AI model and returns page-level text with no
  boxes, so it cannot ground anything. Its two ideas worth keeping for a pipeline that does call a
  model: reject a page response that does not end with an exact sentinel, and checkpoint each validated
  page so a rerun does not pay twice. Neither is needed by a build that calls nothing.
