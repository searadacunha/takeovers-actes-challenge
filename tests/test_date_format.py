"""Regression tests for strict legal date validation."""

import pytest

from actes.validate import _is_date


@pytest.mark.parametrize("value", ["2004-12-15", "2024-02-29", "2018-03-23"])
def test_accepts_calendar_dates(value):
    assert _is_date(value)


@pytest.mark.parametrize(
    "value",
    [
        "2024-W01-1",  # date.fromisoformat accepts this ISO week date
        "2024-02-30",
        "2024-1-01",
        "2024-01-01T00:00:00",
        "2024-01-01Z",
        None,
        20240101,
    ],
)
def test_rejects_non_yyyy_mm_dd_dates(value):
    assert not _is_date(value)
