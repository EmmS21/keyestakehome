"""Dataset persistence."""

import json
import sqlite3
from datetime import datetime
from uuid import UUID

from schemas.database import CellValue, Dataset, DatasetRow


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


def count_rows(conn: sqlite3.Connection, dataset_id: UUID) -> int:
    result = conn.execute(
        "SELECT COUNT(*) AS c FROM dataset_rows WHERE dataset_id = ?",
        (str(dataset_id),),
    ).fetchone()
    return int(result["c"])


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
    return [
        DatasetRow(
            id=UUID(r["id"]),
            dataset_id=UUID(r["dataset_id"]),
            row_index=r["row_index"],
            dimension_a=r["dimension_a"],
            dimension_b=r["dimension_b"],
            dimension_c=r["dimension_c"],
        )
        for r in rows
    ]


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
