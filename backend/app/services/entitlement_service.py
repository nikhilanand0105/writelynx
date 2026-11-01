import datetime
import secrets
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.models.models import (
    User,
    Entitlement,
    UploadReservation,
    SystemSetting,
)


class EntitlementService:
    VALID_TRANSITIONS = {
        "AVAILABLE": ["UPLOAD_AUTHORIZED", "OVER_LIMIT_PENDING_UPGRADE", "REFUNDED", "REVOKED"],
        "UPLOAD_AUTHORIZED": ["FILE_VALIDATING", "AVAILABLE", "OVER_LIMIT_PENDING_UPGRADE", "REVOKED"],
        "FILE_VALIDATING": ["READY", "OVER_LIMIT_PENDING_UPGRADE", "AVAILABLE", "REVOKED"],
        "READY": ["RESERVED", "OVER_LIMIT_PENDING_UPGRADE", "AVAILABLE", "REVOKED"],
        "RESERVED": ["PROCESSING", "READY", "FAILED_RETRYABLE", "REVOKED"],
        "PROCESSING": ["COMPLETED", "FAILED_RETRYABLE", "RESERVED", "REVOKED"],
        "FAILED_RETRYABLE": ["READY", "RESERVED", "PROCESSING", "REFUNDED", "REVOKED"],
        "OVER_LIMIT_PENDING_UPGRADE": ["AVAILABLE", "READY", "REVOKED"],
        "COMPLETED": [],
        "REFUNDED": [],
        "REVOKED": [],
    }

    @classmethod
    def transition(
        cls,
        entitlement: Entitlement,
        new_status: str,
        db: Session,
    ) -> Entitlement:
        """Atomic state machine transition with validation."""
        curr = entitlement.status
        allowed = cls.VALID_TRANSITIONS.get(curr, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Illegal entitlement state transition from '{curr}' to '{new_status}'. Allowed: {allowed}"
            )
        entitlement.status = new_status
        db.commit()
        db.refresh(entitlement)
        return entitlement

    @classmethod
    def check_uploads_allowed(cls, db: Session) -> bool:
        """Check emergency kill switch for uploads."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == "UPLOADS_PAUSED").first()
        if setting and setting.value.lower() in ("true", "1", "yes"):
            return False
        return True

    @classmethod
    def request_upload_authorization(
        cls,
        db: Session,
        user: User,
        entitlement_id: str,
    ) -> UploadReservation:
        """Reserve upload slot for an available entitlement with single-use token."""
        if not cls.check_uploads_allowed(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document uploads are temporarily paused for maintenance."
            )

        # Atomic select
        entitlement = db.query(Entitlement).filter(
            Entitlement.id == entitlement_id,
            Entitlement.user_id == user.id,
        ).first()

        if not entitlement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entitlement not found or does not belong to you."
            )

        if entitlement.status != "AVAILABLE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Entitlement cannot authorize upload. Current status: '{entitlement.status}'. Single-use quota already claimed."
            )

        # Invalidate any old pending reservations for this entitlement
        db.query(UploadReservation).filter(
            UploadReservation.entitlement_id == entitlement.id,
            UploadReservation.is_consumed == False,
        ).update({"is_consumed": True})

        # Create new upload reservation valid for 15 minutes
        token = secrets.token_urlsafe(32)
        reservation = UploadReservation(
            id=f"res_{secrets.token_hex(12)}",
            user_id=user.id,
            entitlement_id=entitlement.id,
            upload_token=token,
            plan_tier=entitlement.plan_tier,
            operating_mode=entitlement.operating_mode,
            max_file_size_bytes=entitlement.max_file_size_mb * 1024 * 1024,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
            is_consumed=False,
        )
        db.add(reservation)

        # Transition state
        cls.transition(entitlement, "UPLOAD_AUTHORIZED", db)
        return reservation

    @classmethod
    def validate_upload_token(
        cls,
        db: Session,
        user: User,
        upload_token: str,
    ) -> UploadReservation:
        """Authoritatively validate single-use upload reservation."""
        reservation = db.query(UploadReservation).filter(
            UploadReservation.upload_token == upload_token,
            UploadReservation.user_id == user.id,
        ).first()

        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid upload authorization token."
            )

        if reservation.is_consumed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Upload token has already been consumed (single-use protection)."
            )

        if reservation.expires_at < datetime.datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Upload authorization token has expired. Please request a new upload slot."
            )

        return reservation
