import json
from pathlib import Path

import pytest

from actes import corpus
from actes.build import LEDGER, SCHEMA, load_ledger

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def results():
    return json.loads((ROOT / "results.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def ledger():
    return load_ledger(LEDGER)


@pytest.fixture(scope="session")
def docs():
    """The corpus is not shipped in this repository: tests that read it are skipped without it."""
    found = corpus.inventory()
    if not found:
        pytest.skip(f"no corpus under {corpus.data_dir()} (scripts/fetch_corpus.sh or ACTES_DATA_DIR)")
    return found
