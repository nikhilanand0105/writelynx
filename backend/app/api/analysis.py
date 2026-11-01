import asyncio
import datetime
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import (
    get_authorized_document,
    get_authorized_job,
    get_authorized_finding,
)
from backend.app.models.models import Document, AnalysisFinding, AnalysisJob, Entitlement
from backend.app.schemas.schemas import AnalysisRequest, AnalysisSummaryResponse, DiagnosticMetrics
from backend.app.workers.analysis_worker import run_document_analysis_job
from backend.app.services.job_queue import JobQueueService

router = APIRouter(prefix="/documents", tags=["Analysis"])
jobs_router = APIRouter(prefix="/jobs", tags=["Jobs"])
findings_router = APIRouter(prefix="/findings", tags=["Findings"])


class FindingReviewRequest(BaseModel):
    review_status: str  # user_reviewed, rejected, accepted, verified
    user_notes: Optional[str] = None


def check_processing_not_paused(db: Session = Depends(get_db)):
    if JobQueueService.is_processing_paused(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document processing is temporarily paused for system maintenance."
        )


@router.post("/{document_id}/analyze", dependencies=[Depends(check_processing_not_paused)])
async def start_analysis(
    req: AnalysisRequest,
    background_tasks: BackgroundTasks,
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """
    Trigger similarity matching, citation analysis, and writing assistant suggestions.
    Enforces student manuscript ownership, entitlement validity, concurrency limits, and durable queueing.
    """
    # 1. System Maintenance Check
    if JobQueueService.is_processing_paused(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document processing is temporarily paused for system maintenance."
        )

    # 2. Concurrency Limit Check (1 active analysis per student)
    if doc.user_id and not JobQueueService.can_user_start_job(db, doc.user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Concurrent processing limit reached. You can only analyze 1 document at a time."
        )

    # 3. Validate Entitlement state
    if doc.entitlement_id:
        ent = db.query(Entitlement).filter(Entitlement.id == doc.entitlement_id).first()
        if ent:
            if ent.status in ("COMPLETED", "REFUNDED", "OVER_LIMIT_PENDING_UPGRADE"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This manuscript's entitlement is in '{ent.status}' state and cannot be re-analyzed."
                )
            ent.status = "PROCESSING"

    doc.processing_status = "analyzing"
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        document_id=doc.id,
        status="queued",
        stage="Queued for durable analysis",
        progress=5,
        parameters={"editing_mode": req.editing_mode, "llm_provider": req.llm_provider, "profile": req.profile}
    )
    db.add(job)
    db.commit()

    # Reconciled execution: Launch asynchronous task to claim and execute the job
    background_tasks.add_task(
        run_document_analysis_job,
        document_id=doc.id,
        editing_mode=req.editing_mode,
        llm_provider=req.llm_provider,
        job_id=job_id
    )

    return {
        "success": True,
        "job_id": job_id,
        "document_id": doc.id,
        "status": "analyzing",
        "message": f"Analysis started in '{req.editing_mode}' mode."
    }


@router.get("/{document_id}/analysis/status")
def get_analysis_status(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Check processing status of document analysis for the authorized student."""
    latest_job = db.query(AnalysisJob).filter(
        AnalysisJob.document_id == doc.id
    ).order_by(AnalysisJob.created_at.desc()).first()

    job_data = None
    if latest_job:
        job_data = {
            "id": latest_job.id,
            "status": latest_job.status,
            "stage": latest_job.stage,
            "progress": latest_job.progress,
            "cancel_requested": latest_job.cancel_requested,
            "error": latest_job.error
        }

    return {
        "document_id": doc.id,
        "status": doc.processing_status,
        "metadata": doc.doc_metadata or {},
        "job": job_data
    }


@router.get("/{document_id}/analysis", response_model=AnalysisSummaryResponse)
def get_analysis_results(
    doc: Document = Depends(get_authorized_document),
    db: Session = Depends(get_db)
):
    """Retrieve diagnostic metrics and detected textual overlap and citation findings."""
    findings = db.query(AnalysisFinding).filter(AnalysisFinding.document_id == doc.id).all()
    meta = doc.doc_metadata or {}
    metrics_dict = meta.get("diagnostic_metrics", {
        "total_document_words": doc.word_count,
        "analyzed_sources_count": len(doc.sources) if doc.sources else 0,
        "matching_passages_count": len([f for f in findings if "overlap" in f.finding_type]),
        "exact_match_words": 0,
        "approximate_match_count": 0,
        "missing_citations_count": len([f for f in findings if "citation" in f.finding_type]),
        "unattributed_overlap_count": len([f for f in findings if f.finding_type == "unattributed_overlap"]),
        "reviewed_findings_count": len([f for f in findings if f.review_status != "pending"]),
        "unresolved_findings_count": len([f for f in findings if f.review_status == "pending"]),
        "local_textual_overlap_percentage": 0.0,
    })

    return AnalysisSummaryResponse(
        document_id=doc.id,
        status=doc.processing_status,
        metrics=DiagnosticMetrics(**metrics_dict),
        findings=findings
    )


@jobs_router.post("/{job_id}/cancel")
def cancel_job(
    job_tuple=Depends(get_authorized_job),
    db: Session = Depends(get_db)
):
    """Cancel an active or queued background analysis job safely for the authorized student."""
    job, doc = job_tuple
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.stage = "Cancelled by user"
        job.finished_at = datetime.datetime.utcnow()
        if doc and doc.processing_status == "analyzing":
            doc.processing_status = "ready"
    db.commit()
    return {"success": True, "job_id": job.id, "status": job.status, "cancel_requested": True}


@findings_router.post("/{finding_id}/review")
def review_finding(
    req: FindingReviewRequest,
    finding_tuple=Depends(get_authorized_finding),
    db: Session = Depends(get_db)
):
    """Mark an editorial finding as user-reviewed or rejected with parent document authorization."""
    finding, doc = finding_tuple
    finding.review_status = req.review_status
    finding.requires_author_input = req.review_status not in ["user_reviewed", "resolved", "accepted", "rejected"]
    ev = dict(finding.evidence or {})
    if req.user_notes:
        ev["author_review_notes"] = req.user_notes
    finding.evidence = ev
    db.commit()
    db.refresh(finding)
    return {
        "success": True,
        "finding_id": finding.id,
        "review_status": finding.review_status,
        "requires_author_input": finding.requires_author_input
    }
