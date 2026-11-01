import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session
from backend.app.core.auth import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import sanitize_filename, calculate_file_hash
from backend.app.models.models import (
    User,
    Entitlement,
    UploadReservation,
    Document,
    DocumentBlock,
)
from backend.app.services.entitlement_service import EntitlementService
from backend.app.services.payment_service import PaymentService
from backend.app.services.quarantine_inspector import QuarantineInspector
from backend.app.services.docx_parser import DocxParser

router = APIRouter(prefix="/upload-gate", tags=["Upload Gate & Quarantine"])


@router.post("/request-token")
def request_upload_token(
    entitlement_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtain single-use upload reservation token for an active paid entitlement."""
    reservation = EntitlementService.request_upload_authorization(
        db=db,
        user=user,
        entitlement_id=entitlement_id,
    )
    return {
        "upload_token": reservation.upload_token,
        "entitlement_id": reservation.entitlement_id,
        "plan_tier": reservation.plan_tier,
        "operating_mode": reservation.operating_mode,
        "expires_at": reservation.expires_at.isoformat(),
        "max_file_size_bytes": reservation.max_file_size_bytes,
    }


@router.post("/upload")
async def authorized_upload(
    response: Response,
    upload_token: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Quarantines, inspects, validates plan limits, and securely ingests DOCX manuscripts.
    If over plan limits, returns 422 OVER_LIMIT without consuming the entitlement.
    """
    # 1. Authoritatively validate upload token
    reservation = EntitlementService.validate_upload_token(
        db=db,
        user=user,
        upload_token=upload_token,
    )

    entitlement = db.query(Entitlement).filter(
        Entitlement.id == reservation.entitlement_id,
        Entitlement.user_id == user.id,
    ).first()

    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked entitlement not found."
        )

    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Microsoft Word (.docx) files are supported."
        )

    # 2. Stage to Quarantine Directory with bounded streaming
    quarantine_filename = f"{reservation.id}_{sanitize_filename(file.filename)}"
    quarantine_path = settings.QUARANTINE_DIR / quarantine_filename

    from backend.app.core.security import save_upload
    try:
        await save_upload(
            file=file,
            path=quarantine_path,
            allowed_extensions={".docx"},
            max_size_bytes=reservation.max_file_size_bytes
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to stream quarantined upload: {str(e)}"
        )

    # 3. Comprehensive Quarantine Inspection (Malware, Macros, Zip Bomb, XXE)
    try:
        metrics = QuarantineInspector.inspect_file(
            file_path=quarantine_path,
            max_file_size_bytes=reservation.max_file_size_bytes,
        )
    except HTTPException:
        quarantine_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        quarantine_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quarantine audit failed: {str(e)}"
        )

    # 4. Check Plan Limits (Pages & Characters)
    char_count = metrics["character_count"]
    page_count = metrics["page_count"]
    is_over_characters = char_count > entitlement.max_characters
    is_over_pages = page_count > entitlement.max_pages

    if is_over_characters or is_over_pages:
        # Check if exceeds all available tiers (Priority 3.3)
        if (
            char_count > settings.PLAN_CONFIGS["extended"]["max_characters"]
            or page_count > settings.PLAN_CONFIGS["extended"]["max_pages"]
        ):
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {
                "status": "UNSUPPORTED_OVER_LIMIT",
                "message": "Manuscript exceeds the maximum 50-page / 160,000-character capacity of all Writelynx plans. Please split your document into chapters. Your entitlement is preserved.",
                "entitlement_id": entitlement.id,
                "current_tier": entitlement.plan_tier,
                "actual_pages": page_count,
                "max_pages": 50,
                "actual_characters": char_count,
                "max_characters": 160000,
                "recommended_tier": None,
                "upgrade_difference_paise": 0,
                "upgrade_difference_rupees": 0,
            }

        # Determine appropriate upgraded plan
        recommended_tier = "standard"
        if (
            char_count > settings.PLAN_CONFIGS["standard"]["max_characters"]
            or page_count > settings.PLAN_CONFIGS["standard"]["max_pages"]
        ):
            recommended_tier = "extended"

        # Calculate upgrade difference
        upgrade_diff_paise = 0
        try:
            upgrade_diff_paise = PaymentService.calculate_upgrade_difference(
                current_tier=entitlement.plan_tier,
                target_tier=recommended_tier,
            )
        except Exception:
            pass

        # Mark entitlement as pending upgrade, preserving student money
        entitlement.status = "OVER_LIMIT_PENDING_UPGRADE"
        db.commit()

        # Return 422 with full upgrade details
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return {
            "status": "OVER_LIMIT",
            "message": "Your manuscript exceeds the capacity of your purchased plan.",
            "entitlement_id": entitlement.id,
            "current_tier": entitlement.plan_tier,
            "actual_pages": page_count,
            "max_pages": entitlement.max_pages,
            "actual_characters": char_count,
            "max_characters": entitlement.max_characters,
            "recommended_tier": recommended_tier,
            "upgrade_difference_paise": upgrade_diff_paise,
            "upgrade_difference_rupees": upgrade_diff_paise // 100,
        }

    # 5. Promoted to Document Storage
    doc_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    promoted_filename = f"{doc_id}_{safe_name}"
    promoted_path = settings.DOCUMENTS_DIR / promoted_filename

    shutil.move(str(quarantine_path), str(promoted_path))
    file_hash = calculate_file_hash(promoted_path)

    # 6. Parse Document Blocks and Structure
    try:
        parser = DocxParser(promoted_path, doc_id)
        blocks_data, doc_meta = parser.parse()
    except Exception as e:
        promoted_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract document blocks: {str(e)}"
        )

    # Augment doc_meta with authoritative server counts
    doc_meta["character_count"] = char_count
    doc_meta["page_count"] = page_count
    doc_meta["plan_tier"] = entitlement.plan_tier
    doc_meta["operating_mode"] = entitlement.operating_mode

    # 7. Persist Document Record
    document = Document(
        id=doc_id,
        user_id=user.id,
        entitlement_id=entitlement.id,
        plan_tier=entitlement.plan_tier,
        operating_mode=entitlement.operating_mode,
        filename=file.filename,
        file_path=str(promoted_path),
        file_hash=file_hash,
        processing_status="ready",
        word_count=metrics["word_count"],
        character_count=char_count,
        page_count=page_count,
        original_paragraph_count=metrics["paragraph_count"],
        table_count=metrics["table_count"],
        image_count=metrics["image_count"],
        doc_metadata=doc_meta,
    )
    db.add(document)

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
            structure_metadata=b["structure_metadata"],
        )
        db.add(block)

    # 8. Transition Entitlement to READY and Mark Token Consumed
    entitlement.document_id = doc_id
    entitlement.status = "READY"
    reservation.is_consumed = True
    db.commit()

    return {
        "status": "success",
        "document_id": doc_id,
        "filename": file.filename,
        "entitlement_id": entitlement.id,
        "plan_tier": entitlement.plan_tier,
        "operating_mode": entitlement.operating_mode,
        "word_count": metrics["word_count"],
        "character_count": char_count,
        "page_count": page_count,
        "paragraph_count": metrics["paragraph_count"],
        "table_count": metrics["table_count"],
        "image_count": metrics["image_count"],
    }
