import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.auth import get_optional_user
from backend.app.models.models import Document, DocumentBlock, Export, AnalysisFinding, RevisionEvent, User
from backend.app.schemas.schemas import ExportResponse
from backend.app.services.export_engine import ExportEngine

router = APIRouter(tags=["Exports"])

@router.post("/documents/{document_id}/export/docx", response_model=ExportResponse)
def export_revised_docx(document_id: str, db: Session = Depends(get_db)):
    """
    Generate the revised DOCX file with all accepted changes applied cleanly to OOXML text runs.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).all()
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

    export_id = str(uuid.uuid4())
    orig_path = Path(doc.file_path)
    output_filename = f"{orig_path.stem}_revised.docx"
    output_path = settings.EXPORTS_DIR / f"{export_id}_{output_filename}"

    engine = ExportEngine(orig_path)
    is_valid, pres_report = engine.export_docx(output_path, block_updates, blocks_meta)

    export_record = Export(
        id=export_id,
        document_id=document_id,
        user_id=doc.user_id,
        export_type="docx",
        file_path=str(output_path),
        preservation_report=pres_report
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    return ExportResponse(
        id=export_id,
        document_id=document_id,
        export_type="docx",
        download_url=f"/api/exports/{export_id}/download",
        created_at=export_record.created_at,
        preservation_report=pres_report
    )

@router.post("/documents/{document_id}/export/pdf", response_model=ExportResponse)
def export_revised_pdf(document_id: str, db: Session = Depends(get_db)):
    """
    Generate revised DOCX and convert it to a pristine PDF using headless LibreOffice.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).all()
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

    export_id = str(uuid.uuid4())
    orig_path = Path(doc.file_path)
    temp_docx_path = settings.EXPORTS_DIR / f"{export_id}_temp.docx"
    pdf_filename = f"{orig_path.stem}_revised.pdf"
    pdf_output_path = settings.EXPORTS_DIR / f"{export_id}_{pdf_filename}"

    engine = ExportEngine(orig_path)
    is_valid, pres_report = engine.export_docx(temp_docx_path, block_updates, blocks_meta)
    if not is_valid:
        raise HTTPException(status_code=500, detail="Document preservation check failed before PDF conversion.")

    pdf_success, pdf_info = engine.export_pdf(temp_docx_path, pdf_output_path)
    if not pdf_success:
        raise HTTPException(status_code=500, detail=pdf_info.get("error", "PDF conversion failed."))

    export_record = Export(
        id=export_id,
        document_id=document_id,
        user_id=doc.user_id,
        export_type="pdf",
        file_path=str(pdf_output_path),
        preservation_report=pres_report
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    return ExportResponse(
        id=export_id,
        document_id=document_id,
        export_type="pdf",
        download_url=f"/api/exports/{export_id}/download",
        created_at=export_record.created_at,
        preservation_report=pres_report
    )

@router.post("/documents/{document_id}/export/audit-csv", response_model=ExportResponse)
def export_citation_audit_csv_endpoint(document_id: str, db: Session = Depends(get_db)):
    """Export citation audit report as CSV."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    findings = db.query(AnalysisFinding).filter(AnalysisFinding.document_id == document_id).all()
    findings_data = [
        {
            "id": f.id,
            "block_id": f.block_id,
            "finding_type": f.finding_type,
            "severity": f.severity,
            "matched_text": f.matched_text,
            "review_status": f.review_status,
            "evidence": f.evidence or {}
        }
        for f in findings
    ]

    export_id = str(uuid.uuid4())
    csv_path = settings.EXPORTS_DIR / f"{export_id}_citation_audit.csv"
    ExportEngine.export_citation_audit_csv(csv_path, findings_data)

    export_record = Export(
        id=export_id,
        document_id=document_id,
        user_id=doc.user_id,
        export_type="audit_csv",
        file_path=str(csv_path),
        preservation_report={}
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    return ExportResponse(
        id=export_id,
        document_id=document_id,
        export_type="audit_csv",
        download_url=f"/api/exports/{export_id}/download",
        created_at=export_record.created_at
    )

@router.get("/exports/{export_id}/download")
def download_export(
    export_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """Download the exported file with appropriate media headers and authorization."""
    record = db.query(Export).filter(Export.id == export_id).first()
    if not record or not Path(record.file_path).exists():
        raise HTTPException(status_code=404, detail="Export file not found.")

    if record.user_id:
        if not user or (record.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student export.")

    path = Path(record.file_path)
    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "audit_csv": "text/csv",
        "log_json": "application/json"
    }
    media_type = media_types.get(record.export_type, "application/octet-stream")
    # Clean download filename (remove UUID prefix)
    clean_filename = "_".join(path.name.split("_")[1:]) if "_" in path.name else path.name
    return FileResponse(path=str(path), filename=clean_filename, media_type=media_type)
