import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.models.models import AnalysisJob, Document, SystemSetting


class JobQueueService:
    LEASE_TIMEOUT_SECONDS = 300  # 5 minutes

    @staticmethod
    def is_processing_paused(db: Session) -> bool:
        """Check emergency job processing pause."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == "PROCESSING_PAUSED").first()
        if setting and setting.value.lower() in ("true", "1", "yes"):
            return True
        return False

    @classmethod
    def can_user_start_job(cls, db: Session, user_id: Optional[str]) -> bool:
        """Enforce strict concurrency limit of 1 active analysis job per student."""
        if not user_id:
            return True

        active_job = db.query(AnalysisJob).join(Document, AnalysisJob.document_id == Document.id).filter(
            Document.user_id == user_id,
            AnalysisJob.status.in_(["queued", "processing"]),
        ).first()

        return active_job is None

    @classmethod
    def reap_stale_jobs(cls, db: Session) -> int:
        """Identify and recover crashed/orphaned workers older than 5-minute lease."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=cls.LEASE_TIMEOUT_SECONDS)
        stale_jobs = db.query(AnalysisJob).filter(
            AnalysisJob.status == "processing",
            AnalysisJob.started_at < cutoff,
        ).all()

        reaped_count = 0
        for job in stale_jobs:
            job.status = "failed"
            job.error_message = "Worker lease expired (timeout recovery)."
            reaped_count += 1

        if reaped_count > 0:
            db.commit()

        return reaped_count
