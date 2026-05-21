"""Cleaning session routes (proposals, accept, audit)."""

from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app import accept as accept_logic
from backend.app import audit as audit_logic
from backend.app import proposals as proposals_logic
from backend.app.db.connection import connect
from backend.app.dependencies import get_db_path
from backend.app.exceptions import ProposalNotFoundError, SessionNotFoundError
from schemas.api import (
    AcceptRequest,
    AcceptResponse,
    AuditLogResponse,
    ProposalsResponse,
)
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


@router.post(
    "/{session_id}/steps/{pattern}/accept",
    response_model=AcceptResponse,
)
def accept_proposals(
    session_id: UUID,
    pattern: CleaningPattern,
    body: AcceptRequest,
    db_path: Path = Depends(get_db_path),
) -> AcceptResponse:
    if pattern == CleaningPattern.DONE:
        raise HTTPException(status_code=400, detail="Pattern 'done' cannot be accepted")

    conn = connect(db_path)
    try:
        result = accept_logic.accept_proposals(
            conn, session_id, pattern, body.proposal_ids
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()

    return AcceptResponse(submit_id=result.submit_id, changes=result.changes)


@router.get("/{session_id}/audit", response_model=AuditLogResponse)
def list_audit(
    session_id: UUID,
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
    db_path: Path = Depends(get_db_path),
) -> AuditLogResponse:
    conn = connect(db_path)
    try:
        page = audit_logic.list_audit(
            conn, session_id, limit=limit, offset=offset
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()

    return AuditLogResponse(entries=page.entries, total_count=page.total_count)
