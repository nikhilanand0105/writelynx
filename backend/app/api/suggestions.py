from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.dependencies import (
    get_authorized_document,
    get_authorized_suggestion,
    get_authorized_block,
)
from backend.app.models.models import Document, EditSuggestion
from backend.app.schemas.schemas import EditSuggestionResponse, SuggestionReviseRequest, ManualBlockEditRequest
from backend.app.services.revision_manager import RevisionManager, RevisionConflict

router = APIRouter(tags=["Suggestions & Editing"])


class ApprovalRequest(BaseModel):
    user_notes: Optional[str] = None
    approve_fact_changes: bool = False


def perform(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except RevisionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get('/documents/{document_id}/suggestions', response_model=List[EditSuggestionResponse])
def list_suggestions(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve suggestions for the authorized manuscript."""
    return db.query(EditSuggestion).filter_by(document_id=doc.id).all()


@router.post('/suggestions/{suggestion_id}/accept')
def accept_suggestion(
    req: ApprovalRequest = ApprovalRequest(),
    sugg_tuple=Depends(get_authorized_suggestion),
    db: Session = Depends(get_db)
):
    """Accept an editing suggestion with parent manuscript ownership validation."""
    suggestion, doc = sugg_tuple
    return perform(RevisionManager.accept_suggestion, db, suggestion.id, **req.model_dump())


@router.post('/suggestions/{suggestion_id}/reject')
def reject_suggestion(
    req: ApprovalRequest = ApprovalRequest(),
    sugg_tuple=Depends(get_authorized_suggestion),
    db: Session = Depends(get_db)
):
    """Reject an editing suggestion with parent manuscript ownership validation."""
    suggestion, doc = sugg_tuple
    return perform(RevisionManager.reject_suggestion, db, suggestion.id, user_notes=req.user_notes)


@router.post('/suggestions/{suggestion_id}/edit')
@router.post('/suggestions/{suggestion_id}/revise')
def revise_suggestion(
    req: SuggestionReviseRequest,
    sugg_tuple=Depends(get_authorized_suggestion),
    db: Session = Depends(get_db)
):
    """Modify and accept an editing proposal with parent manuscript authorization."""
    suggestion, doc = sugg_tuple
    return perform(RevisionManager.accept_suggestion, db, suggestion.id, **req.model_dump())


@router.post('/blocks/{block_id}/revise')
def revise_block_manually(
    req: ManualBlockEditRequest,
    block_tuple=Depends(get_authorized_block),
    db: Session = Depends(get_db)
):
    """Perform direct manual revision on a block with parent manuscript authorization."""
    block, doc = block_tuple
    return perform(RevisionManager.revise_block_manually, db, block.id, **req.model_dump())
