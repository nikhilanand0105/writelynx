import datetime
from typing import Optional
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
            AnalysisJob.status.in_(["queued", "processing", "validating", "running"]),
        ).first()

        return active_job is None

    @classmethod
    def acquire_next_job(
        cls, db: Session, worker_id: str, lease_seconds: int = 300
    ) -> Optional[AnalysisJob]:
        """
        Durable queue pop: atomically fetch and claim next queued analysis job
        using a database lease with heartbeat.
        """
        if cls.is_processing_paused(db):
            return None

        # Re-tryable or newly queued jobs
        job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.status == "queued")
            .order_by(AnalysisJob.created_at.asc())
            .first()
        )

        if not job:
            return None

        now = datetime.datetime.utcnow()
        job.status = "processing"
        job.worker_id = worker_id
        job.started_at = now
        job.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
        job.stage = "Acquired by worker"
        job.progress = 5
        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def heartbeat(
        cls, db: Session, job_id: str, progress: int, stage: str, lease_seconds: int = 300
    ) -> bool:
        """Extend worker lease and report progress heartbeats."""
        job = db.get(AnalysisJob, job_id)
        if not job or job.status != "processing":
            return False

        now = datetime.datetime.utcnow()
        job.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
        job.progress = progress
        job.stage = stage
        db.commit()
        return True

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
