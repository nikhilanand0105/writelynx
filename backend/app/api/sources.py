import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
import pymupdf as fitz
import docx

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename, validate_zip_safety
from backend.app.core.auth import get_optional_user
from backend.app.models.models import Document, ReferenceSource, User
from backend.app.schemas.schemas import ReferenceSourceResponse
from backend.app.services.external_report_parser import ExternalReportParser

router = APIRouter(prefix="/documents", tags=["Sources"])

@router.post("/{document_id}/sources", response_model=ReferenceSourceResponse)
async def upload_reference_source(
    document_id: str,
    file: UploadFile = File(...),
    is_external_report: bool = Form(False),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """
    Upload reference materials (PDF, DOCX, TXT) or an authorized external similarity report PDF.
    Extracts text and indexes it for evidence-based local matching.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.user_id:
        if not user or (doc.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student manuscript.")

    source_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    dest_path = settings.SOURCES_DIR / f"{source_id}_{safe_name}"

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    extracted_text = ""
    source_type = "upload_unknown"
    metadata = {}

    lower_filename = file.filename.lower()
    if lower_filename.endswith(".pdf"):
        source_type = "external_report_pdf" if is_external_report else "upload_pdf"
        try:
            pdf_doc = fitz.open(str(dest_path))
            for page in pdf_doc:
                extracted_text += page.get_text() + "\n"
            pdf_doc.close()

            if is_external_report:
                report_data = ExternalReportParser.parse_pdf_report(dest_path)
                metadata.update(report_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read PDF source: {str(e)}")

    elif lower_filename.endswith(".docx"):
        source_type = "upload_docx"
        validate_zip_safety(dest_path)
        try:
            docx_file = docx.Document(str(dest_path))
            extracted_text = "\n\n".join(p.text for p in docx_file.paragraphs if p.text.strip())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read DOCX source: {str(e)}")

    elif lower_filename.endswith((".txt", ".md", ".rtf")):
        source_type = "upload_txt"
        extracted_text = content.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=400, detail="Unsupported source format. Please upload PDF, DOCX, or TXT.")

    token_count = len(extracted_text.split())

    source = ReferenceSource(
        id=source_id,
        document_id=document_id,
        title=file.filename,
        source_type=source_type,
        file_path=str(dest_path),
        extracted_text=extracted_text,
        token_count=token_count,
        source_metadata=metadata
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source

@router.get("/{document_id}/sources", response_model=List[ReferenceSourceResponse])
def list_document_sources(
    document_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """List all indexed reference sources for this manuscript."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id:
        if not user or (doc.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student manuscript.")
    return db.query(ReferenceSource).filter(ReferenceSource.document_id == document_id).all()
