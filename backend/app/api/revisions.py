from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_authorized_document
from backend.app.models.models import Document, DocumentVersion, RevisionEvent, DocumentBlock
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
def get_document_revisions(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve audit trail of revisions for the authorized student's manuscript."""
    return db.query(RevisionEvent).filter_by(document_id=doc.id).order_by(RevisionEvent.timestamp.desc()).all()


@router.get('/{document_id}/versions')
def get_document_versions(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve version history snapshots for the authorized manuscript."""
    RevisionManager.ensure_initial_version(db, doc)
    db.commit()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "label": v.label,
            "created_at": v.created_at,
            "is_current": v.id == (doc.doc_metadata or {}).get('current_version_id')
        }
        for v in db.query(DocumentVersion).filter_by(document_id=doc.id).order_by(DocumentVersion.version_number.desc())
    ]


@router.post('/{document_id}/restore')
def restore_document_or_block(
    req: RestoreRequest,
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Restore specific block or snapshot version with strict ownership verification."""
    if req.block_id:
        block = db.query(DocumentBlock).filter(
            DocumentBlock.id == req.block_id,
            DocumentBlock.document_id == doc.id
        ).first()
        if not block:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target document block not found.")
        return perform(RevisionManager.restore_block_original, db, req.block_id, document_id=doc.id)
    return perform(RevisionManager.navigate_version, db, doc.id, 'restore_version', req.version_id)


@router.post('/{document_id}/undo')
def undo(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Revert last revision for the authorized student's manuscript."""
    return perform(RevisionManager.navigate_version, db, doc.id, 'undo')


@router.post('/{document_id}/redo')
def redo(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Re-apply previously undone revision for the authorized manuscript."""
    return perform(RevisionManager.navigate_version, db, doc.id, 'redo')
