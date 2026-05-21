"""Dataset ingest, parsing, and SQLite persistence."""

import csv
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from backend.app.exceptions import (
    EmptyDatasetError,
    InvalidPeriodValueError,
    NoDataRowsError,
    NoPeriodColumnsError,
)
from schemas.database import CellValue, Dataset, DatasetRow

PERIOD_HEADER = re.compile(r"^\d{6}$")
INGEST_ROW_BATCH = 1000
ROW_CHUNK_SIZE = 1000


@dataclass(frozen=True)
class DatasetSummaryRecord:
    id: UUID
    name: str
    uploaded_at: datetime
    period_columns: list[str]
    row_count: int


@dataclass(frozen=True)
class ParsedRow:
    row_index: int
    dimension_a: str | None
    dimension_b: str | None
    dimension_c: str | None
    periods: dict[str, float]


@dataclass(frozen=True)
class ParsedCsv:
    period_columns: list[str]
    rows: list[ParsedRow]


def _blank_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped if stripped else None


def _split_period_columns(header: list[str]) -> tuple[list[str], list[str]]:
    """Return (dimension_headers, period_columns)."""
    period_start: int | None = None
    for i, cell in enumerate(header):
        if PERIOD_HEADER.match(cell.strip()):
            period_start = i
            break
    if period_start is None:
        raise NoPeriodColumnsError("No YYYYMM period columns in header")
    dimensions = [h.strip() for h in header[:period_start]]
    periods = [h.strip() for h in header[period_start:]]
    if not all(PERIOD_HEADER.match(p) for p in periods):
        raise NoPeriodColumnsError("Period columns must be YYYYMM labels")
    return dimensions, periods


def _parse_row(
    *,
    header: list[str],
    period_columns: list[str],
    period_start: int,
    row_index: int,
    raw_row: list[str],
) -> ParsedRow | None:
    if not any(cell.strip() for cell in raw_row):
        return None
    if len(raw_row) != len(header):
        raw_row = raw_row + [""] * (len(header) - len(raw_row))
        raw_row = raw_row[: len(header)]

    dims = [_blank_to_none(raw_row[i]) for i in range(period_start)]
    while len(dims) < 3:
        dims.append(None)
    dimension_a, dimension_b, dimension_c = dims[0], dims[1], dims[2]

    periods: dict[str, float] = {}
    for offset, period in enumerate(period_columns):
        col_index = period_start + offset
        raw_value = raw_row[col_index].strip() if col_index < len(raw_row) else ""
        if not raw_value:
            periods[period] = 0.0
            continue
        try:
            periods[period] = float(raw_value)
        except ValueError as exc:
            raise InvalidPeriodValueError(row_index, period, raw_value) from exc

    return ParsedRow(
        row_index=row_index,
        dimension_a=dimension_a,
        dimension_b=dimension_b,
        dimension_c=dimension_c,
        periods=periods,
    )


def parse_csv(file_path: Path) -> ParsedCsv:
    """Read and validate CSV structure and numeric period cells."""
    period_columns: list[str] = []
    rows: list[ParsedRow] = []
    header: list[str] = []
    period_start = 0

    with file_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise EmptyDatasetError("File is empty")

        if not header or not any(cell.strip() for cell in header):
            raise EmptyDatasetError("Missing header row")

        _, period_columns = _split_period_columns(header)
        period_start = len(header) - len(period_columns)

        for row_index, raw_row in enumerate(reader):
            parsed = _parse_row(
                header=header,
                period_columns=period_columns,
                period_start=period_start,
                row_index=row_index,
                raw_row=raw_row,
            )
            if parsed is not None:
                rows.append(parsed)

    if not rows:
        raise NoDataRowsError("CSV has no data rows")

    return ParsedCsv(period_columns=period_columns, rows=rows)


def ingest_dataset(
    conn: sqlite3.Connection,
    uploads_dir: Path,
    source_path: Path,
    name: str,
) -> Dataset:
    """Parse CSV, store immutable copy, and persist grid rows + cell_values."""
    parsed = parse_csv(source_path)
    dataset_id = uuid4()
    uploaded_at = datetime.now(UTC)

    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest_path = uploads_dir / f"{dataset_id}_{name}"
    shutil.copy2(source_path, dest_path)

    insert_dataset(
        conn,
        dataset_id=dataset_id,
        name=name,
        uploaded_at=uploaded_at,
        original_path=str(dest_path),
        period_columns=parsed.period_columns,
    )

    batch: list[tuple[UUID, ParsedRow]] = []
    for row in parsed.rows:
        batch.append((uuid4(), row))
        if len(batch) >= INGEST_ROW_BATCH:
            _persist_row_batch(conn, dataset_id=dataset_id, batch=batch)
            batch.clear()
    if batch:
        _persist_row_batch(conn, dataset_id=dataset_id, batch=batch)

    conn.commit()
    return get_dataset(conn, dataset_id)


def row_count(conn: sqlite3.Connection, dataset_id: UUID) -> int:
    result = conn.execute(
        "SELECT COUNT(*) AS c FROM dataset_rows WHERE dataset_id = ?",
        (str(dataset_id),),
    ).fetchone()
    return int(result["c"])


def list_datasets(conn: sqlite3.Connection) -> list[DatasetSummaryRecord]:
    rows = conn.execute(
        """
        SELECT
            d.id,
            d.name,
            d.uploaded_at,
            d.period_columns,
            COUNT(dr.id) AS row_count
        FROM datasets d
        LEFT JOIN dataset_rows dr ON dr.dataset_id = d.id
        GROUP BY d.id
        ORDER BY d.uploaded_at DESC
        """
    ).fetchall()
    return [
        DatasetSummaryRecord(
            id=UUID(r["id"]),
            name=r["name"],
            uploaded_at=datetime.fromisoformat(r["uploaded_at"]),
            period_columns=json.loads(r["period_columns"]),
            row_count=int(r["row_count"]),
        )
        for r in rows
    ]


def insert_dataset(
    conn: sqlite3.Connection,
    *,
    dataset_id: UUID,
    name: str,
    uploaded_at: datetime,
    original_path: str,
    period_columns: list[str],
) -> None:
    conn.execute(
        """
        INSERT INTO datasets (id, name, uploaded_at, original_path, period_columns)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(dataset_id),
            name,
            uploaded_at.isoformat(),
            original_path,
            json.dumps(period_columns),
        ),
    )


def _persist_row_batch(
    conn: sqlite3.Connection,
    *,
    dataset_id: UUID,
    batch: list[tuple[UUID, ParsedRow]],
) -> None:
    row_params = [
        (
            str(row_id),
            str(dataset_id),
            row.row_index,
            row.dimension_a,
            row.dimension_b,
            row.dimension_c,
        )
        for row_id, row in batch
    ]
    conn.executemany(
        """
        INSERT INTO dataset_rows
            (id, dataset_id, row_index, dimension_a, dimension_b, dimension_c)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        row_params,
    )
    cell_params = [
        (str(row_id), period, value)
        for row_id, row in batch
        for period, value in row.periods.items()
    ]
    conn.executemany(
        """
        INSERT INTO cell_values (dataset_row_id, period, value)
        VALUES (?, ?, ?)
        """,
        cell_params,
    )


def insert_dataset_row(
    conn: sqlite3.Connection,
    *,
    row_id: UUID,
    dataset_id: UUID,
    row_index: int,
    dimension_a: str | None,
    dimension_b: str | None,
    dimension_c: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO dataset_rows
            (id, dataset_id, row_index, dimension_a, dimension_b, dimension_c)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(row_id),
            str(dataset_id),
            row_index,
            dimension_a,
            dimension_b,
            dimension_c,
        ),
    )


def insert_cell_value(
    conn: sqlite3.Connection,
    *,
    dataset_row_id: UUID,
    period: str,
    value: float,
) -> None:
    conn.execute(
        """
        INSERT INTO cell_values (dataset_row_id, period, value)
        VALUES (?, ?, ?)
        """,
        (str(dataset_row_id), period, value),
    )


def get_dataset(conn: sqlite3.Connection, dataset_id: UUID) -> Dataset:
    row = conn.execute(
        "SELECT id, name, uploaded_at, original_path, period_columns FROM datasets WHERE id = ?",
        (str(dataset_id),),
    ).fetchone()
    if row is None:
        raise KeyError(dataset_id)
    return Dataset(
        id=UUID(row["id"]),
        name=row["name"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        original_path=row["original_path"],
        period_columns=json.loads(row["period_columns"]),
    )


def _row_from_sqlite(r: sqlite3.Row) -> DatasetRow:
    return DatasetRow(
        id=UUID(r["id"]),
        dataset_id=UUID(r["dataset_id"]),
        row_index=r["row_index"],
        dimension_a=r["dimension_a"],
        dimension_b=r["dimension_b"],
        dimension_c=r["dimension_c"],
    )


def list_rows_with_negative_cells(
    conn: sqlite3.Connection, dataset_id: UUID
) -> list[DatasetRow]:
    """Rows that have at least one negative period cell (SQL pre-filter for negatives)."""
    rows = conn.execute(
        """
        SELECT DISTINCT
            dr.id, dr.dataset_id, dr.row_index,
            dr.dimension_a, dr.dimension_b, dr.dimension_c
        FROM dataset_rows dr
        INNER JOIN cell_values cv ON cv.dataset_row_id = dr.id
        WHERE dr.dataset_id = ? AND cv.value < 0
        ORDER BY dr.row_index
        """,
        (str(dataset_id),),
    ).fetchall()
    return [_row_from_sqlite(r) for r in rows]


def iter_row_chunks(
    conn: sqlite3.Connection,
    dataset_id: UUID,
    *,
    rows: list[DatasetRow] | None = None,
    chunk_size: int = ROW_CHUNK_SIZE,
):
    """Yield dataset rows in chunks (all rows, or a pre-filtered list)."""
    if rows is not None:
        for offset in range(0, len(rows), chunk_size):
            yield rows[offset : offset + chunk_size]
        return

    offset = 0
    while True:
        chunk = conn.execute(
            """
            SELECT id, dataset_id, row_index, dimension_a, dimension_b, dimension_c
            FROM dataset_rows
            WHERE dataset_id = ?
            ORDER BY row_index
            LIMIT ? OFFSET ?
            """,
            (str(dataset_id), chunk_size, offset),
        ).fetchall()
        if not chunk:
            break
        yield [_row_from_sqlite(r) for r in chunk]
        offset += chunk_size


def load_periods_for_rows(
    conn: sqlite3.Connection,
    row_ids: list[UUID],
    period_columns: list[str],
) -> dict[UUID, dict[str, float]]:
    """One query for many rows — avoids N+1 list_cell_values."""
    if not row_ids:
        return {}
    placeholders = ",".join("?" * len(row_ids))
    rows = conn.execute(
        f"""
        SELECT dataset_row_id, period, value
        FROM cell_values
        WHERE dataset_row_id IN ({placeholders})
        """,
        [str(row_id) for row_id in row_ids],
    ).fetchall()
    raw: dict[UUID, dict[str, float]] = {row_id: {} for row_id in row_ids}
    for r in rows:
        raw[UUID(r["dataset_row_id"])][r["period"]] = float(r["value"])
    return {
        row_id: {period: values.get(period, 0.0) for period in period_columns}
        for row_id, values in raw.items()
    }


def get_dataset_row(conn: sqlite3.Connection, row_id: UUID) -> DatasetRow | None:
    row = conn.execute(
        """
        SELECT id, dataset_id, row_index, dimension_a, dimension_b, dimension_c
        FROM dataset_rows
        WHERE id = ?
        """,
        (str(row_id),),
    ).fetchone()
    if row is None:
        return None
    return _row_from_sqlite(row)


def list_rows(conn: sqlite3.Connection, dataset_id: UUID) -> list[DatasetRow]:
    rows = conn.execute(
        """
        SELECT id, dataset_id, row_index, dimension_a, dimension_b, dimension_c
        FROM dataset_rows
        WHERE dataset_id = ?
        ORDER BY row_index
        """,
        (str(dataset_id),),
    ).fetchall()
    return [_row_from_sqlite(r) for r in rows]


def list_cell_values(conn: sqlite3.Connection, dataset_row_id: UUID) -> list[CellValue]:
    rows = conn.execute(
        """
        SELECT dataset_row_id, period, value
        FROM cell_values
        WHERE dataset_row_id = ?
        ORDER BY period
        """,
        (str(dataset_row_id),),
    ).fetchall()
    return [
        CellValue(
            dataset_row_id=UUID(r["dataset_row_id"]),
            period=r["period"],
            value=r["value"],
        )
        for r in rows
    ]
