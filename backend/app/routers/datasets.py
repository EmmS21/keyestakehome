"""Dataset upload and listing routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.db.connection import connect
from backend.app.exceptions import (
    EmptyDatasetError,
    IngestError,
    InvalidPeriodValueError,
    NoDataRowsError,
    NoPeriodColumnsError,
)
from backend.app.schemas.datasets import DatasetUploadResponse
from backend.app.services import ingest as ingest_service

router = APIRouter(prefix="/datasets", tags=["datasets"])

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "data" / "app.db"
DEFAULT_UPLOADS_DIR = REPO_ROOT / "uploads"


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def get_uploads_dir() -> Path:
    return DEFAULT_UPLOADS_DIR


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
            dataset = ingest_service.ingest_dataset(
                conn,
                uploads_dir=uploads_dir,
                source_path=staging_path,
                name=file.filename,
            )
            count = ingest_service.row_count(conn, dataset.id)
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
