"""
API / domain objects — not persisted by default.

Proposal is computed from cell_values + detection rules when the UI opens a step.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.types import CleaningPattern


class CellChange(BaseModel):
    """Single cell before/after — used in proposals, Submit response, and audit."""

    period: str
    value_before: float
    value_after: float


class Proposal(BaseModel):
    """
    Suggestion for one dataset row on the active pattern.
    NOT a database table (default): recompute when step opens or cell_values changes.
    """

    id: str = Field(description="Stable ID for this step's accept payload")
    pattern: CleaningPattern
    dataset_row_id: UUID
    row_index: int = Field(ge=0)
    dimension_a: str | None = None
    dimension_b: str | None = None
    dimension_c: str | None = None
    changes: list[CellChange] = Field(
        default_factory=list,
        description="Cells to fix on this row if the user checks the box",
    )


class AcceptRequest(BaseModel):
    """POST .../accept — client sends decisions only, not new values."""

    session_updated_at: datetime = Field(
        description="Must match cleaning_sessions.updated_at from when proposals were loaded",
    )
    proposal_ids: list[str] = Field(
        default_factory=list,
        description="Checked rows; empty = Submit with none accepted",
    )


class AppliedCellChange(BaseModel):
    """One persisted change (mirrors audit_log_entries + cell_values update)."""

    dataset_row_id: UUID
    period: str
    value_before: float
    value_after: float


class AcceptResponse(BaseModel):
    """POST .../accept — server returns only cells that changed."""

    submit_id: UUID = Field(description="Shared by all audit rows from this Submit")
    changes: list[AppliedCellChange]


class AuditLogEntryView(BaseModel):
    """Audit line for UI — maps from AuditLogEntry."""

    id: UUID
    submit_id: UUID
    pattern: CleaningPattern
    dataset_row_id: UUID
    period: str
    value_before: float
    value_after: float
    created_at: datetime


class AuditLogResponse(BaseModel):
    """GET .../audit — paginated change log."""

    entries: list[AuditLogEntryView]
    total_count: int = Field(ge=0)


class SessionCreateResponse(BaseModel):
    """POST /datasets/{id}/sessions — start or resume cleaning."""

    session_id: UUID
    dataset_id: UUID
    created_at: datetime
    updated_at: datetime


class ProposalsResponse(BaseModel):
    """GET .../proposals — one page; full file stays on server."""

    pattern: CleaningPattern
    session_updated_at: datetime = Field(
        description="Send back on accept; 409 if session changed since load",
    )
    proposals: list[Proposal]
    total_count: int = Field(
        ge=0,
        description="Total proposals for this pattern (all rows scanned)",
    )
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
