import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_authorized_document
from backend.app.models.models import Document, DocumentBlock, Export
from backend.app.schemas.schemas import PreservationReport
from backend.app.services.structure_preserver import StructurePreserver
from backend.app.services.fact_validator import FactValidator
from backend.app.services.export_engine import ExportEngine

router = APIRouter(prefix="/documents", tags=["Validation"])


@router.post("/{document_id}/validate", response_model=PreservationReport)
def validate_document(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """
    Run comprehensive structural preservation and fact preservation check
    between original uploaded document and actual revised DOCX artifact.
    Compares the original DOCX with the generated revised artifact (Priority 9).
    """
    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == doc.id).all()

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

    orig_path = Path(doc.file_path)
    preserver = StructurePreserver(orig_path)

    # Priority 9: Compare original with the actual exported revised artifact
    latest_export = db.query(Export).filter(
        Export.document_id == doc.id,
        Export.export_type == "docx"
    ).order_by(Export.created_at.desc()).first()

    temp_file = None
    target_path = None

    if latest_export and Path(latest_export.file_path).exists():
        target_path = Path(latest_export.file_path)
    else:
        # Generate a candidate revised artifact to test real preservation against current blocks
        block_updates = {b.id: b.current_text for b in blocks if b.current_text != b.original_text}
        blocks_meta = [
            {
                "id": b.id,
                "document_id": b.document_id,
                "block_index": b.block_index,
                "section_id": b.section_id,
                "structure_metadata": b.structure_metadata or {},
                "allow_fact_changes": bool((b.structure_metadata or {}).get("fact_change_approval"))
            }
            for b in blocks
        ]
        temp_fd = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        temp_fd.close()
        temp_file = Path(temp_fd.name)
        engine = ExportEngine(orig_path)
        engine.export_docx(temp_file, block_updates, blocks_meta)
        target_path = temp_file

    try:
        report_dict = preserver.validate_preservation(orig_path, target_path)
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)

    report_dict["protected_facts_intact"] = len(fact_violations) == 0
    report_dict["protected_fact_violations"] = fact_violations
    report_dict["citation_integrity_intact"] = len(citation_warnings) == 0
    report_dict["citation_warnings"] = citation_warnings
    report_dict["approved_fact_changes"] = approved_fact_changes

    if fact_violations or citation_warnings:
        report_dict["valid"] = False

    return PreservationReport(**report_dict)


@router.get("/{document_id}/validation", response_model=PreservationReport)
def get_validation_report(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve the latest validation status for the authorized student's manuscript."""
    return validate_document(doc=doc, db=db)
