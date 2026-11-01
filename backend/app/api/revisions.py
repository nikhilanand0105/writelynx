from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import Document, DocumentVersion, RevisionEvent
from backend.app.schemas.schemas import RevisionEventResponse
from backend.app.services.revision_manager import RevisionManager
from backend.app.api.suggestions import perform

router = APIRouter(prefix='/documents', tags=['Revisions'])


class RestoreRequest(BaseModel):
    block_id: Optional[str] = None
    version_id: Optional[str] = None

    @model_validator(mode='after')
    def exactly_one(self):
        if bool(self.block_id) == bool(self.version_id):
            raise ValueError('Specify exactly one block_id or version_id.')
        return self


@router.get('/{document_id}/revisions', response_model=List[RevisionEventResponse])
def get_document_revisions(document_id: str, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(404, 'Document not found.')
    return db.query(RevisionEvent).filter_by(document_id=document_id).order_by(RevisionEvent.timestamp.desc()).all()


@router.get('/{document_id}/versions')
def get_document_versions(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, 'Document not found.')
    RevisionManager.ensure_initial_version(db, doc)
    db.commit()
    return [{"id": v.id, "version_number": v.version_number, "label": v.label, "created_at": v.created_at,
             "is_current": v.id == (doc.doc_metadata or {}).get('current_version_id')}
            for v in db.query(DocumentVersion).filter_by(document_id=document_id).order_by(DocumentVersion.version_number.desc())]


@router.post('/{document_id}/restore')
def restore_document_or_block(document_id: str, req: RestoreRequest, db: Session = Depends(get_db)):
    if req.block_id:
        return perform(RevisionManager.restore_block_original, db, req.block_id, document_id=document_id)
    return perform(RevisionManager.navigate_version, db, document_id, 'restore_version', req.version_id)


@router.post('/{document_id}/undo')
def undo(document_id: str, db: Session = Depends(get_db)):
    return perform(RevisionManager.navigate_version, db, document_id, 'undo')


@router.post('/{document_id}/redo')
def redo(document_id: str, db: Session = Depends(get_db)):
    return perform(RevisionManager.navigate_version, db, document_id, 'redo')
