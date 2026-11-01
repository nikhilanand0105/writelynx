import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.models import (
    Document,
    UploadReservation,
    Export,
    ReferenceSource,
)

logger = logging.getLogger("writelynx.retention")


class RetentionService:
    """
    Automated Ephemeral Retention & Privacy Purge Engine.
    Enforces Phase 18 retention policies:
    - Temporary abandoned uploads: purged after 1 hour.
    - Quarantined failed uploads: purged after 2 hours.
    - Completed outputs: retained for 7 days by default.
    - Minimal financial records retained as legally required.
    - Synchronous student hard-deletion for instant data sovereignty.
    """

    COMPLETED_DOC_RETENTION_DAYS: int = 7
    ABANDONED_UPLOAD_HOURS: int = 1
    FAILED_QUARANTINE_HOURS: int = 2

    @classmethod
    def purge_abandoned_upload_reservations(
        cls, db: Session, max_age_hours: Optional[int] = None
    ) -> int:
        """
        Purge pending upload reservations that were never completed.
        Unlinks any quarantined scratch files and marks reservations as EXPIRED.
        """
        hours = max_age_hours or cls.ABANDONED_UPLOAD_HOURS
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

        stale_reservations = (
            db.query(UploadReservation)
            .filter(
                UploadReservation.is_consumed == False,
                UploadReservation.created_at < cutoff,
            )
            .all()
        )

        purged_count = 0
        for res in stale_reservations:
            if res.destination_key:
                p = Path(res.destination_key)
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to unlink abandoned file {p}: {e}")

            res.status = "EXPIRED"
            res.is_consumed = True
            purged_count += 1

        if purged_count > 0:
            db.commit()
            logger.info(f"Purged {purged_count} abandoned upload reservations.")

        return purged_count

    @classmethod
    def purge_failed_quarantine_files(
        cls, max_age_hours: Optional[int] = None
    ) -> int:
        """
        Remove orphaned scratch files in quarantine older than configured threshold.
        """
        hours = max_age_hours or cls.FAILED_QUARANTINE_HOURS
        cutoff_timestamp = (
            datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        ).timestamp()

        purged_count = 0
        quarantine_dir = settings.QUARANTINE_DIR
        if quarantine_dir.exists():
            for item in quarantine_dir.glob("*"):
                if item.name == ".gitkeep":
                    continue
                if item.is_file():
                    try:
                        if item.stat().st_mtime < cutoff_timestamp:
                            item.unlink()
                            purged_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to clean quarantine file {item}: {e}")

        return purged_count

    @classmethod
    def purge_expired_completed_documents(
        cls, db: Session, retention_days: Optional[int] = None
    ) -> int:
        """
        Purge documents older than the 7-day retention period along with all
        associated disk artifacts (DOCX, exports, sources, detector PDFs).
        """
        days = retention_days or cls.COMPLETED_DOC_RETENTION_DAYS
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        expired_docs = (
            db.query(Document)
            .filter(Document.uploaded_at < cutoff)
            .all()
        )

        purged_count = 0
        for doc in expired_docs:
            cls.hard_delete_document_files(doc, db)
            db.delete(doc)
            purged_count += 1

        if purged_count > 0:
            db.commit()
            logger.info(f"Purged {purged_count} expired completed manuscripts (> {days} days old).")

        return purged_count

    @classmethod
    def hard_delete_document_files(cls, doc: Document, db: Session) -> None:
        """
        Safely remove all disk files belonging to a manuscript:
        - Primary DOCX file
        - Generated DOCX & PDF exports
        - Uploaded reference sources
        - Uploaded third-party detector PDFs
        """
        # 1. Primary file
        if doc.file_path:
            p = Path(doc.file_path)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except Exception as e:
                    logger.warning(f"Failed to unlink primary doc {p}: {e}")

        # 2. Detector PDF
        if doc.detector_pdf_path:
            p = Path(doc.detector_pdf_path)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except Exception as e:
                    logger.warning(f"Failed to unlink detector PDF {p}: {e}")

        # 3. Exports
        exports = db.query(Export).filter(Export.document_id == doc.id).all()
        for exp in exports:
            if exp.file_path:
                p = Path(exp.file_path)
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to unlink export {p}: {e}")

        # 4. Reference sources
        sources = db.query(ReferenceSource).filter(ReferenceSource.document_id == doc.id).all()
        for src in sources:
            if src.file_path:
                p = Path(src.file_path)
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to unlink source file {p}: {e}")

    @classmethod
    def run_all_purges(cls, db: Session) -> Dict[str, int]:
        """Execute complete retention lifecycle purge."""
        abandoned = cls.purge_abandoned_upload_reservations(db)
        quarantine = cls.purge_failed_quarantine_files()
        expired_docs = cls.purge_expired_completed_documents(db)

        return {
            "abandoned_reservations_purged": abandoned,
            "quarantine_files_purged": quarantine,
            "expired_documents_purged": expired_docs,
        }
