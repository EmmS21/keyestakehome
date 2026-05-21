"""Dataset upload and listing routes."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from backend.app import datasets as datasets_logic
from backend.app import sessions as sessions_logic
from backend.app.db.connection import connect
from backend.app.dependencies import get_db_path, get_uploads_dir
from backend.app.exceptions import (
    DatasetNotFoundError,
    DuplicateDatasetNameError,
    EmptyDatasetError,
    IngestError,
    InvalidPeriodValueError,
    NoDataRowsError,
    NoPeriodColumnsError,
)
from schemas.api import SessionCreateResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetSummary(BaseModel):
    id: UUID
    name: str
    period_columns: list[str]
    row_count: int = Field(ge=0)
    uploaded_at: datetime


class DatasetUploadResponse(DatasetSummary):
    """POST /datasets — created dataset summary."""


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List datasets",
    description="Returns all uploaded datasets for the file explorer.",
)
def list_datasets(db_path: Path = Depends(get_db_path)) -> DatasetListResponse:
    conn = connect(db_path)
    try:
        summaries = datasets_logic.list_datasets(conn)
    finally:
        conn.close()
    return DatasetListResponse(
        datasets=[
            DatasetSummary(
                id=s.id,
                name=s.name,
                period_columns=s.period_columns,
                row_count=s.row_count,
                uploaded_at=s.uploaded_at,
            )
            for s in summaries
        ]
    )


@router.post("", response_model=DatasetUploadResponse, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    db_path: Path = Depends(get_db_path),
    uploads_dir: Path = Depends(get_uploads_dir),
) -> DatasetUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    uploads_dir.mkdir(parents=True, exist_ok=True)
    staging_path = uploads_dir / f"_staging_{file.filename}"
    try:
        content = await file.read()
        if not content.strip():
            raise HTTPException(status_code=400, detail="File is empty")
        staging_path.write_bytes(content)

        conn = connect(db_path)
        try:
            from backend.app.db.connection import init_db

            init_db(conn)
            dataset = datasets_logic.ingest_dataset(
                conn,
                uploads_dir=uploads_dir,
                source_path=staging_path,
                name=file.filename,
            )
            count = datasets_logic.row_count(conn, dataset.id)
        finally:
            conn.close()
    except EmptyDatasetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoDataRowsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoPeriodColumnsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidPeriodValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "row_index": exc.row_index,
                "period": exc.period,
                "value": exc.raw_value,
            },
        ) from exc
    except DuplicateDatasetNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if staging_path.exists():
            staging_path.unlink()

    return DatasetUploadResponse(
        id=dataset.id,
        name=dataset.name,
        period_columns=dataset.period_columns,
        row_count=count,
        uploaded_at=dataset.uploaded_at,
    )


@router.post(
    "/{dataset_id}/sessions",
    response_model=SessionCreateResponse,
    summary="Start or resume cleaning session",
    description=(
        "One cleaning session per dataset. Returns existing session (200) or creates a new one (201). "
        "Use session_id for proposals, accept, and audit routes."
    ),
    responses={
        201: {"description": "New session created"},
        200: {"description": "Existing session resumed"},
        404: {"description": "Dataset not found"},
    },
)
def create_or_resume_session(
    dataset_id: UUID,
    response: Response,
    db_path: Path = Depends(get_db_path),
) -> SessionCreateResponse:
    conn = connect(db_path)
    try:
        session, created = sessions_logic.start_or_resume_session(conn, dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()

    response.status_code = 201 if created else 200
    return SessionCreateResponse(
        session_id=session.id,
        dataset_id=session.dataset_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
