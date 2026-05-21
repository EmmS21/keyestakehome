"""
Pydantic models aligned with persisted tables — see docs/database-schema.md.

Use these for: DB row validation, repository layer, migrations documentation.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.types import CleaningPattern


class Dataset(BaseModel):
    """Uploaded file metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(min_length=1, description="Original filename")
    uploaded_at: datetime
    original_path: str = Field(description="Immutable CSV on disk or object store key")
    period_columns: list[str] = Field(
        min_length=1,
        description='Month headers in order, e.g. ["202401","202402"]',
    )


class DatasetRow(BaseModel):
    """One CSV line — dimensions identify the transaction."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    row_index: int = Field(ge=0, description="0-based line number in original file")
    dimension_a: str | None = None
    dimension_b: str | None = None
    dimension_c: str | None = None


class CellValue(BaseModel):
    """One numeric cell in the working (cleaned) grid."""

    model_config = ConfigDict(from_attributes=True)

    dataset_row_id: UUID
    period: str = Field(
        min_length=1,
        description="Period column label (YYYYMM), matches period_columns entry",
    )
    value: float = Field(description="Current revenue value after any accepted fixes")


class CleaningSession(BaseModel):
    """Cleaning run for a dataset. Which anomaly tab is active lives in the UI only."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    created_at: datetime
    updated_at: datetime


class AuditLogEntry(BaseModel):
    """One cell changed. Rows sharing submit_id = one Submit click."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    submit_id: UUID = Field(description="Groups all cells changed in one Submit")
    pattern: CleaningPattern
    dataset_row_id: UUID
    period: str
    value_before: float
    value_after: float
    created_at: datetime


class ExportEvent(BaseModel):
    """CSV download of the working copy — when and which cleaning version."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    session_id: UUID
    exported_at: datetime
    session_updated_at: datetime = Field(
        description="cleaning_sessions.updated_at at export time",
    )
    audit_entry_count: int = Field(
        ge=0,
        description="Cell-level audit rows before this export (version snapshot)",
    )
    export_number: int = Field(
        ge=1,
        description="Nth export for this dataset (1 = first download)",
    )
