"""Unit tests for CSV ingest (POST /datasets brain)."""

import pytest

from backend.app import datasets as datasets_logic
from backend.app.exceptions import (
    EmptyDatasetError,
    InvalidPeriodValueError,
    NoDataRowsError,
    NoPeriodColumnsError,
)

VALID_CSV = """\
A,B,C,202401,202402,202403,202404,202405
Dog,China,Line,100,-200,0,50,30
Dog,Shine,Lime,0,50,-100,25,10
Cat,USA,Retail,0,200,-200,10,10
Bird,UK,Online,200,-200,5,5,5
,,,100,0,42,55,48
"""


def _write_csv(tmp_path, filename: str, content: str):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_ingest_sample_csv_persists_dataset_rows_and_cell_values(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "sample.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="sample.csv",
    )

    assert dataset.name == "sample.csv"
    assert dataset.period_columns == [
        "202401",
        "202402",
        "202403",
        "202404",
        "202405",
    ]
    assert (tmp_uploads / f"{dataset.id}_sample.csv").exists()

    rows = datasets_logic.list_rows(conn, dataset.id)
    assert len(rows) == 5

    first = rows[0]
    assert first.row_index == 0
    assert first.dimension_a == "Dog"
    assert first.dimension_b == "China"
    assert first.dimension_c == "Line"

    blank_dims = next(r for r in rows if r.row_index == 4)
    assert blank_dims.dimension_a is None
    assert blank_dims.dimension_b is None
    assert blank_dims.dimension_c is None

    cells = datasets_logic.list_cell_values(conn, first.id)
    by_period = {c.period: c.value for c in cells}
    assert by_period["202402"] == -200.0
    assert len(cells) == 5


def test_ingest_raises_when_csv_file_is_empty(tmp_path):
    empty = _write_csv(tmp_path, "empty.csv", "")
    with pytest.raises(EmptyDatasetError):
        datasets_logic.parse_csv(empty)


def test_ingest_raises_when_csv_has_header_but_no_data_rows(tmp_path):
    header_only = _write_csv(tmp_path, "header.csv", "A,B,C,202401,202402\n")
    with pytest.raises(NoDataRowsError):
        datasets_logic.parse_csv(header_only)


def test_ingest_raises_when_csv_has_no_yyyymm_period_columns(tmp_path):
    no_periods = _write_csv(tmp_path, "dims.csv", "A,B,C\nDog,China,Line\n")
    with pytest.raises(NoPeriodColumnsError):
        datasets_logic.parse_csv(no_periods)


def test_ingest_raises_when_period_cell_is_not_numeric(tmp_path):
    bad = _write_csv(
        tmp_path,
        "bad.csv",
        "A,B,C,202401,202402\nDog,China,Line,100,abc\n",
    )
    with pytest.raises(InvalidPeriodValueError) as exc_info:
        datasets_logic.parse_csv(bad)
    assert exc_info.value.row_index == 0
    assert exc_info.value.period == "202402"
