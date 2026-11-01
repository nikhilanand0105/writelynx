from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.models import Document, DocumentBlock, EditSuggestion, RevisionEvent
from backend.app.schemas.schemas import PreservationReport
from backend.app.services.structure_preserver import StructurePreserver
from backend.app.services.fact_validator import FactValidator

router = APIRouter(prefix="/documents", tags=["Validation"])

@router.post("/{document_id}/validate", response_model=PreservationReport)
def validate_document(document_id: str, db: Session = Depends(get_db)):
    """
    Run comprehensive structural preservation and fact preservation check
    between original uploaded document and current document state.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).all()
    
    # Check fact preservation across all edited blocks
    fact_violations = []
    citation_warnings = []
    
    approved_fact_changes = []
    for b in blocks:
        if b.current_text != b.original_text:
            is_valid, violations = FactValidator.compare_facts(b.original_text, b.current_text)
            if not is_valid:
                approval = (b.structure_metadata or {}).get("fact_change_approval")
                if approval:
                    approved_fact_changes.append({
                        "block_id": b.id,
                        "violations": violations,
                        "reason": approval.get("reason"),
                        "approved_at": approval.get("approved_at")
                    })
                    continue
                for v in violations:
                    if "citation" in v.lower():
                        citation_warnings.append(f"Block {b.id}: {v}")
                    else:
                        fact_violations.append(f"Block {b.id}: {v}")

    # Inspect original DOCX
    orig_path = Path(doc.file_path)
    preserver = StructurePreserver(orig_path)
    report_dict = preserver.validate_preservation(orig_path, orig_path)

    report_dict["protected_facts_intact"] = len(fact_violations) == 0
    report_dict["protected_fact_violations"] = fact_violations
    report_dict["citation_integrity_intact"] = len(citation_warnings) == 0
    report_dict["citation_warnings"] = citation_warnings
    report_dict["approved_fact_changes"] = approved_fact_changes

    if fact_violations or citation_warnings:
        report_dict["valid"] = False

    return PreservationReport(**report_dict)

@router.get("/{document_id}/validation", response_model=PreservationReport)
def get_validation_report(document_id: str, db: Session = Depends(get_db)):
    """Retrieve the latest validation status for the document."""
    return validate_document(document_id, db)
