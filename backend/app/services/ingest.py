"""CSV parse and dataset ingest."""

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
from backend.app.repositories import datasets as datasets_repo
from schemas.database import Dataset

PERIOD_HEADER = re.compile(r"^\d{6}$")


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


def parse_csv(file_path: Path) -> ParsedCsv:
    """Read and validate CSV structure and numeric period cells."""
    text = file_path.read_text(encoding="utf-8")
    if not text.strip():
        raise EmptyDatasetError("File is empty")

    reader = csv.reader(text.splitlines())
    try:
        header = next(reader)
    except StopIteration:
        raise EmptyDatasetError("File is empty")

    if not header or not any(cell.strip() for cell in header):
        raise EmptyDatasetError("Missing header row")

    _, period_columns = _split_period_columns(header)
    period_start = len(header) - len(period_columns)

    rows: list[ParsedRow] = []
    for row_index, raw_row in enumerate(reader):
        if not any(cell.strip() for cell in raw_row):
            continue
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

        rows.append(
            ParsedRow(
                row_index=row_index,
                dimension_a=dimension_a,
                dimension_b=dimension_b,
                dimension_c=dimension_c,
                periods=periods,
            )
        )

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

    datasets_repo.insert_dataset(
        conn,
        dataset_id=dataset_id,
        name=name,
        uploaded_at=uploaded_at,
        original_path=str(dest_path),
        period_columns=parsed.period_columns,
    )

    for row in parsed.rows:
        row_id = uuid4()
        datasets_repo.insert_dataset_row(
            conn,
            row_id=row_id,
            dataset_id=dataset_id,
            row_index=row.row_index,
            dimension_a=row.dimension_a,
            dimension_b=row.dimension_b,
            dimension_c=row.dimension_c,
        )
        for period, value in row.periods.items():
            datasets_repo.insert_cell_value(
                conn,
                dataset_row_id=row_id,
                period=period,
                value=value,
            )

    conn.commit()
    return datasets_repo.get_dataset(conn, dataset_id)


def row_count(conn: sqlite3.Connection, dataset_id: UUID) -> int:
    return datasets_repo.count_rows(conn, dataset_id)
