"""API models for dataset routes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetUploadResponse(BaseModel):
    """POST /datasets — created dataset summary."""

    id: UUID
    name: str
    period_columns: list[str]
    row_count: int = Field(ge=0)
    uploaded_at: datetime
