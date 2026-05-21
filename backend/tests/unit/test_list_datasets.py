"""Unit tests for dataset listing (GET /datasets brain)."""

from backend.app import datasets as datasets_logic

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


def test_list_datasets_returns_empty_list_when_database_has_no_uploads(tmp_db):
    conn, _ = tmp_db
    assert datasets_logic.list_datasets(conn) == []


def test_list_datasets_returns_summary_with_row_count_after_ingest(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "sample.csv", VALID_CSV)
    ingested = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="sample.csv",
    )

    summaries = datasets_logic.list_datasets(conn)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == ingested.id
    assert summary.name == "sample.csv"
    assert summary.period_columns == [
        "202401",
        "202402",
        "202403",
        "202404",
        "202405",
    ]
    assert summary.row_count == 5
