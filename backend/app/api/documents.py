import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename, calculate_file_hash, validate_zip_safety
from backend.app.core.auth import get_optional_user
from backend.app.models.models import Document, DocumentBlock, User
from backend.app.schemas.schemas import DocumentResponse, DocumentStructureResponse, DocumentBlockResponse
from backend.app.services.docx_parser import DocxParser

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a DOCX academic report. Validates format, runs security checks,
    and extracts structured blocks without destroying formatting.
    """
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only Microsoft Word (.docx) files are supported as primary manuscripts.")

    doc_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    dest_path = settings.DOCUMENTS_DIR / f"{doc_id}_{safe_name}"

    # Read and validate size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.")

    with open(dest_path, "wb") as f:
        f.write(content)

    # Validate zip safety
    validate_zip_safety(dest_path)
    file_hash = calculate_file_hash(dest_path)

    # Parse structural blocks with DocxParser
    try:
        parser = DocxParser(dest_path, doc_id)
        blocks_data, doc_meta = parser.parse()
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to parse DOCX structure: {str(e)}")

    # Create document record
    document = Document(
        id=doc_id,
        filename=file.filename,
        file_path=str(dest_path),
        file_hash=file_hash,
        processing_status="ready",
        word_count=doc_meta.get("word_count", 0),
        original_paragraph_count=doc_meta.get("paragraph_count", 0),
        table_count=doc_meta.get("table_count", 0),
        image_count=doc_meta.get("image_count", 0),
        doc_metadata=doc_meta
    )
    db.add(document)

    # Persist blocks
    for b in blocks_data:
        block = DocumentBlock(
            id=b["id"],
            document_id=doc_id,
            block_index=b["block_index"],
            section_id=b["section_id"],
            block_type=b["block_type"],
            original_text=b["original_text"],
            current_text=b["current_text"],
            is_protected=b["is_protected"],
            structure_metadata=b["structure_metadata"]
        )
        db.add(block)

    db.commit()
    db.refresh(document)
    return document

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """List manuscripts. If student authenticated, scopes to student's documents."""
    query = db.query(Document)
    if user and not user.is_admin:
        query = query.filter(Document.user_id == user.id)
    return query.order_by(Document.uploaded_at.desc()).all()

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """Retrieve manuscript metadata by ID with multi-tenancy verification."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id:
        if not user or (doc.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student manuscript.")
    return doc

@router.get("/{document_id}/structure", response_model=DocumentStructureResponse)
def get_document_structure(
    document_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """Retrieve full structural hierarchy of blocks, sections, and paragraphs."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id:
        if not user or (doc.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student manuscript.")

    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).order_by(DocumentBlock.block_index).all()
    sections = list(dict.fromkeys(b.section_id for b in blocks))
    
    return DocumentStructureResponse(
        document_id=document_id,
        sections=sections,
        total_blocks=len(blocks),
        blocks=blocks
    )

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """Securely delete a document and associated local files."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id:
        if not user or (doc.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=403, detail="Unauthorized access to student manuscript.")

    # Remove file on disk if exists
    try:
        p = Path(doc.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"success": True, "message": "Document and all related findings deleted."}
