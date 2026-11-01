from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
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
        raise HTTPException(409, exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/documents/{document_id}/suggestions', response_model=List[EditSuggestionResponse])
def list_suggestions(document_id: str, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(404, 'Document not found.')
    return db.query(EditSuggestion).filter_by(document_id=document_id).all()


@router.post('/suggestions/{suggestion_id}/accept')
def accept_suggestion(suggestion_id: str, req: ApprovalRequest = ApprovalRequest(), db: Session = Depends(get_db)):
    return perform(RevisionManager.accept_suggestion, db, suggestion_id, **req.model_dump())


@router.post('/suggestions/{suggestion_id}/reject')
def reject_suggestion(suggestion_id: str, req: ApprovalRequest = ApprovalRequest(), db: Session = Depends(get_db)):
    return perform(RevisionManager.reject_suggestion, db, suggestion_id, user_notes=req.user_notes)


@router.post('/suggestions/{suggestion_id}/edit')
@router.post('/suggestions/{suggestion_id}/revise')
def revise_suggestion(suggestion_id: str, req: SuggestionReviseRequest, db: Session = Depends(get_db)):
    return perform(RevisionManager.accept_suggestion, db, suggestion_id, **req.model_dump())


@router.post('/blocks/{block_id}/revise')
def revise_block_manually(block_id: str, req: ManualBlockEditRequest, db: Session = Depends(get_db)):
    return perform(RevisionManager.revise_block_manually, db, block_id, **req.model_dump())
