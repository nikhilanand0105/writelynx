from typing import Tuple, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.auth import get_current_user, require_admin
from backend.app.models.models import (
    User,
    Document,
    DocumentBlock,
    EditSuggestion,
    AnalysisFinding,
    DetectorHighlight,
    AnalysisJob,
    Export,
    ReferenceSource,
)


def get_authorized_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    """
    Authoritative multi-tenancy dependency.
    Enforces that the authenticated user owns the document or is a system administrator.
    In production and staging, access to unowned/legacy records is strictly blocked.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manuscript not found.",
        )

    # Deny access to unowned legacy records in production/staging
    if not doc.user_id:
        if settings.ENVIRONMENT in ("production", "staging"):
            if not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Unassigned legacy manuscript access is prohibited.",
                )
        else:
            # In test/dev mode, assign to current user if unclaimed
            if doc.user_id is None:
                doc.user_id = current_user.id
                db.commit()

    if doc.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access or modify this student manuscript.",
        )

    return doc


def get_authorized_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[EditSuggestion, Document]:
    """Resolve edit suggestion and verify ownership of the parent manuscript."""
    suggestion = db.query(EditSuggestion).filter(EditSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edit suggestion not found.",
        )

    doc = get_authorized_document(suggestion.document_id, db=db, current_user=current_user)
    return suggestion, doc


def get_authorized_block(
    block_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[DocumentBlock, Document]:
    """Resolve document block and verify ownership of the parent manuscript."""
    block = db.query(DocumentBlock).filter(DocumentBlock.id == block_id).first()
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document block not found.",
        )

    doc = get_authorized_document(block.document_id, db=db, current_user=current_user)
    return block, doc


def get_authorized_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[AnalysisFinding, Document]:
    """Resolve analysis finding and verify ownership of the parent manuscript."""
    finding = db.query(AnalysisFinding).filter(AnalysisFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Editorial finding not found.",
        )

    doc = get_authorized_document(finding.document_id, db=db, current_user=current_user)
    return finding, doc


def get_authorized_highlight(
    highlight_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[DetectorHighlight, Document]:
    """Resolve detector highlight and verify ownership of the parent manuscript."""
    highlight = db.query(DetectorHighlight).filter(DetectorHighlight.id == highlight_id).first()
    if not highlight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detector highlight not found.",
        )

    doc = get_authorized_document(highlight.document_id, db=db, current_user=current_user)
    return highlight, doc


def get_authorized_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[AnalysisJob, Document]:
    """Resolve analysis job and verify ownership of the parent manuscript."""
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )

    doc = get_authorized_document(job.document_id, db=db, current_user=current_user)
    return job, doc


def get_authorized_export(
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[Export, Document]:
    """Resolve export record and verify ownership of the parent manuscript."""
    export_rec = db.query(Export).filter(Export.id == export_id).first()
    if not export_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file record not found.",
        )

    doc = get_authorized_document(export_rec.document_id, db=db, current_user=current_user)
    return export_rec, doc


def get_authorized_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tuple[ReferenceSource, Document]:
    """Resolve reference source and verify ownership of the parent manuscript."""
    source_rec = db.query(ReferenceSource).filter(ReferenceSource.id == source_id).first()
    if not source_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference source not found.",
        )

    doc = get_authorized_document(source_rec.document_id, db=db, current_user=current_user)
    return source_rec, doc
