import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Body, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename, save_upload
from backend.app.core.dependencies import (
    get_authorized_document,
    get_authorized_finding,
    get_authorized_block,
)
from backend.app.models.models import Document, ResearchEvidence, DocumentBlock
from backend.app.schemas.schemas import ResearchEvidenceResponse
from backend.app.services.evidence_manager import EvidenceManager
from backend.app.services.evidence_grounded_revision import EvidenceGroundedRevisionEngine

router = APIRouter(tags=["Research Evidence & Claim Verification"])


@router.post("/documents/{document_id}/evidence", response_model=ResearchEvidenceResponse)
async def add_research_evidence(
    title: str = Form(...),
    evidence_type: str = Form("experiment_log"),
    content: Optional[str] = Form(None),
    linked_blocks: Optional[str] = Form(None),  # comma-separated block ids
    file: Optional[UploadFile] = File(None),
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """
    Attach author research evidence: experiment logs, source code repositories,
    benchmark tables, screenshots, or lab notes. Enforces student document ownership.
    """
    file_path_str = None
    if file:
        safe_name = sanitize_filename(file.filename)
        dest_path = settings.STORAGE_DIR / "sources" / f"evidence_{uuid.uuid4()}_{safe_name}"
        ext = Path(file.filename or "").suffix.lower()
        allowed = {ext} if ext else {".txt", ".pdf", ".docx", ".png", ".jpg", ".csv"}
        await save_upload(file, dest_path, allowed_extensions=allowed, max_size_bytes=settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        file_path_str = str(dest_path)

    blocks_list = [b.strip() for b in linked_blocks.split(",")] if linked_blocks else []

    evidence = EvidenceManager.add_evidence(
        db=db,
        document_id=doc.id,
        title=title,
        evidence_type=evidence_type,
        content=content,
        file_path=file_path_str,
        linked_blocks=blocks_list
    )
    return evidence


@router.get("/documents/{document_id}/evidence", response_model=List[ResearchEvidenceResponse])
def list_research_evidence(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """List all research evidence artifacts attached to the authorized manuscript."""
    return db.query(ResearchEvidence).filter(ResearchEvidence.document_id == doc.id).all()


@router.post("/claims/{finding_id}/verify")
def verify_claim_with_evidence(
    evidence_id: str = Body(..., embed=True),
    user_notes: Optional[str] = Body(None, embed=True),
    finding_tuple=Depends(get_authorized_finding),
    db: Session = Depends(get_db)
):
    """Link research evidence to verify an unsupported claim finding with parent document authorization."""
    finding, doc = finding_tuple
    # Verify evidence belongs to the same document
    evidence = db.query(ResearchEvidence).filter(
        ResearchEvidence.id == evidence_id,
        ResearchEvidence.document_id == doc.id
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence artifact not found or does not belong to this manuscript."
        )

    try:
        return EvidenceManager.verify_finding_with_evidence(db, finding.id, evidence_id, user_notes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/documents/{document_id}/blocks/{block_id}/ground-revision")
def ground_block_revision(
    block_tuple=Depends(get_authorized_block),
    db: Session = Depends(get_db)
):
    """
    Executes the Evidence-Grounded Research Revision workflow on a specific block,
    linking attached evidence and proposing verified natural revisions with parent document ownership.
    """
    block, doc = block_tuple
    return EvidenceGroundedRevisionEngine.execute_9step_grounding(
        db=db,
        document_id=doc.id,
        block_id=block.id,
        original_text=block.current_text,
        section_id=block.section_id
    )
