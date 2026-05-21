"""Cleaning session routes (proposals, accept, audit)."""

from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app import proposals as proposals_logic
from backend.app.db.connection import connect
from backend.app.dependencies import get_db_path
from backend.app.exceptions import SessionNotFoundError
from schemas.api import ProposalsResponse
from schemas.types import CleaningPattern

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "/{session_id}/steps/{pattern}/proposals",
    response_model=ProposalsResponse,
)
def list_proposals(
    session_id: UUID,
    pattern: CleaningPattern,
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    db_path: Path = Depends(get_db_path),
) -> ProposalsResponse:
    if pattern == CleaningPattern.DONE:
        raise HTTPException(status_code=400, detail="Pattern 'done' has no proposals")

    conn = connect(db_path)
    try:
        page = proposals_logic.list_proposals(
            conn, session_id, pattern, limit=limit, offset=offset
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()

    return ProposalsResponse(
        pattern=page.pattern,
        proposals=page.proposals,
        total_count=page.total_count,
        limit=page.limit,
        offset=page.offset,
    )
