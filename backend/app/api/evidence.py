import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Body
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename
from backend.app.models.models import Document, ResearchEvidence
from backend.app.schemas.schemas import ResearchEvidenceResponse, ResearchEvidenceCreate
from backend.app.services.evidence_manager import EvidenceManager
from backend.app.services.evidence_grounded_revision import EvidenceGroundedRevisionEngine
from backend.app.models.models import DocumentBlock

router = APIRouter(tags=["Research Evidence & Claim Verification"])

@router.post("/documents/{document_id}/evidence", response_model=ResearchEvidenceResponse)
async def add_research_evidence(
    document_id: str,
    title: str = Form(...),
    evidence_type: str = Form("experiment_log"),
    content: Optional[str] = Form(None),
    linked_blocks: Optional[str] = Form(None),  # comma-separated block ids
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Attach author research evidence: experiment logs, source code repositories,
    benchmark tables, screenshots, or lab notes.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path_str = None
    if file:
        safe_name = sanitize_filename(file.filename)
        dest_path = settings.STORAGE_DIR / "sources" / f"evidence_{uuid.uuid4()}_{safe_name}"
        data = await file.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        file_path_str = str(dest_path)

    blocks_list = [b.strip() for b in linked_blocks.split(",")] if linked_blocks else []

    evidence = EvidenceManager.add_evidence(
        db=db,
        document_id=document_id,
        title=title,
        evidence_type=evidence_type,
        content=content,
        file_path=file_path_str,
        linked_blocks=blocks_list
    )
    return evidence

@router.get("/documents/{document_id}/evidence", response_model=List[ResearchEvidenceResponse])
def list_research_evidence(document_id: str, db: Session = Depends(get_db)):
    """List all research evidence artifacts attached to this manuscript."""
    return db.query(ResearchEvidence).filter(ResearchEvidence.document_id == document_id).all()

@router.post("/claims/{finding_id}/verify")
def verify_claim_with_evidence(
    finding_id: str,
    evidence_id: str = Body(..., embed=True),
    user_notes: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    """Link research evidence to verify an unsupported claim or novel contribution finding."""
    try:
        return EvidenceManager.verify_finding_with_evidence(db, finding_id, evidence_id, user_notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/documents/{document_id}/blocks/{block_id}/ground-revision")
def ground_block_revision(
    document_id: str,
    block_id: str,
    db: Session = Depends(get_db)
):
    """
    Executes the Phase 5 Evidence-Grounded Research Revision workflow on a specific block,
    linking attached evidence, identifying missing information, generating author clarifying
    questions, and proposing verified natural revisions.
    """
    block = db.query(DocumentBlock).filter(
        DocumentBlock.id == block_id,
        DocumentBlock.document_id == document_id
    ).first()
    if not block:
        raise HTTPException(status_code=404, detail="Document block not found.")

    return EvidenceGroundedRevisionEngine.execute_9step_grounding(
        db=db,
        document_id=document_id,
        block_id=block_id,
        original_text=block.current_text,
        section_id=block.section_id
    )
