import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename, calculate_file_hash, validate_zip_safety, save_upload
from backend.app.core.auth import get_current_user
from backend.app.core.dependencies import get_authorized_document
from backend.app.models.models import Document, DocumentBlock, User
from backend.app.schemas.schemas import DocumentResponse, DocumentStructureResponse
from backend.app.services.docx_parser import DocxParser
from backend.app.services.retention_service import RetentionService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Legacy direct upload route.
    STRICTLY DISABLED in production and staging environments.
    All student manuscript uploads must proceed through /api/upload-gate/upload with an active paid entitlement.
    In isolated test environments, requires authenticated user and binds directly to the student account.
    """
    if settings.ENVIRONMENT in ("production", "staging"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct document upload without an active paid entitlement is prohibited. Please use the paid upload gate at /api/upload-gate/upload."
        )

    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Microsoft Word (.docx) files are supported as primary manuscripts."
        )

    doc_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    dest_path = settings.DOCUMENTS_DIR / f"{doc_id}_{safe_name}"

    try:
        file_hash = await save_upload(file, dest_path, allowed_extensions={".docx"}, max_size_bytes=settings.MAX_FILE_SIZE_MB * 1024 * 1024)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save upload: {str(e)}")

    # Validate zip safety
    validate_zip_safety(dest_path)

    # Parse structural blocks with DocxParser
    try:
        parser = DocxParser(dest_path, doc_id)
        blocks_data, doc_meta = parser.parse()
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to parse DOCX structure: {str(e)}")

    # Create document record bound to the authenticated student
    document = Document(
        id=doc_id,
        user_id=user.id,
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
    user: User = Depends(get_current_user)
):
    """List manuscripts strictly isolated to the authenticated student."""
    query = db.query(Document)
    if not user.is_admin:
        query = query.filter(Document.user_id == user.id)
    return query.order_by(Document.uploaded_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    doc: Document = Depends(get_authorized_document)
):
    """Retrieve manuscript metadata by ID with multi-tenancy verification."""
    return doc


@router.get("/{document_id}/structure", response_model=DocumentStructureResponse)
def get_document_structure(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve full structural hierarchy of blocks, sections, and paragraphs."""
    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == doc.id).order_by(DocumentBlock.block_index).all()
    sections = list(dict.fromkeys(b.section_id for b in blocks))

    return DocumentStructureResponse(
        document_id=doc.id,
        sections=sections,
        total_blocks=len(blocks),
        blocks=blocks
    )


@router.delete("/{document_id}")
def delete_document(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Securely delete a document and associated local files."""
    # Remove files on disk synchronously (DOCX, exports, sources, detector PDF)
    RetentionService.hard_delete_document_files(doc, db)

    db.delete(doc)
    db.commit()
    return {"success": True, "message": "Document and all related findings deleted."}
