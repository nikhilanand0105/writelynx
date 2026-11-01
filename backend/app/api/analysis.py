import asyncio
import datetime
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.models import Document, AnalysisFinding, AnalysisJob, Entitlement
from backend.app.schemas.schemas import AnalysisRequest, AnalysisSummaryResponse, DiagnosticMetrics, AnalysisFindingResponse
from backend.app.workers.analysis_worker import run_document_analysis_job
from backend.app.services.job_queue import JobQueueService

router = APIRouter(prefix="/documents", tags=["Analysis"])
jobs_router = APIRouter(prefix="/jobs", tags=["Jobs"])
findings_router = APIRouter(prefix="/findings", tags=["Findings"])


class FindingReviewRequest(BaseModel):
    review_status: str  # user_reviewed, rejected, accepted, verified
    user_notes: Optional[str] = None


@router.post("/{document_id}/analyze")
async def start_analysis(
    document_id: str,
    req: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger similarity matching, citation analysis, and writing assistant suggestions.
    Runs asynchronously in the background with concurrency & maintenance checks.
    """
    # 1. System Maintenance Check
    if JobQueueService.is_processing_paused(db):
        raise HTTPException(
            status_code=503,
            detail="Document processing is temporarily paused for system maintenance."
        )

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 2. Concurrency Limit Check (1 active analysis per student)
    if doc.user_id and not JobQueueService.can_user_start_job(db, doc.user_id):
        raise HTTPException(
            status_code=429,
            detail="Concurrent processing limit reached. You can only analyze 1 document at a time."
        )

    # 3. Update Entitlement state to PROCESSING
    if doc.entitlement_id:
        ent = db.query(Entitlement).filter(Entitlement.id == doc.entitlement_id).first()
        if ent and ent.status in ("READY", "AVAILABLE", "RESERVED"):
            ent.status = "PROCESSING"

    doc.processing_status = "analyzing"
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        document_id=document_id,
        status="running",
        stage="Queued for analysis",
        progress=5,
        parameters={"editing_mode": req.editing_mode, "llm_provider": req.llm_provider, "profile": req.profile}
    )
    db.add(job)
    db.commit()

    background_tasks.add_task(
        run_document_analysis_job,
        document_id=document_id,
        editing_mode=req.editing_mode,
        llm_provider=req.llm_provider,
        job_id=job_id
    )

    return {
        "success": True,
        "job_id": job_id,
        "document_id": document_id,
        "status": "analyzing",
        "message": f"Analysis started in '{req.editing_mode}' mode."
    }


@router.get("/{document_id}/analysis/status")
def get_analysis_status(document_id: str, db: Session = Depends(get_db)):
    """Check processing status of document analysis."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    latest_job = db.query(AnalysisJob).filter(
        AnalysisJob.document_id == document_id
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
        "document_id": document_id,
        "status": doc.processing_status,
        "metadata": doc.doc_metadata or {},
        "job": job_data
    }


@router.get("/{document_id}/analysis", response_model=AnalysisSummaryResponse)
def get_analysis_results(document_id: str, db: Session = Depends(get_db)):
    """Retrieve diagnostic metrics and all detected textual overlap and citation findings."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    findings = db.query(AnalysisFinding).filter(AnalysisFinding.document_id == document_id).all()
    meta = doc.doc_metadata or {}
    metrics_dict = meta.get("diagnostic_metrics", {
        "total_document_words": doc.word_count,
        "analyzed_sources_count": len(doc.sources),
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
        document_id=document_id,
        status=doc.processing_status,
        metrics=DiagnosticMetrics(**metrics_dict),
        findings=findings
    )


@jobs_router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel an active or queued background analysis job safely."""
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found.")

    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.stage = "Cancelled by user"
        job.finished_at = datetime.datetime.utcnow()
        doc = db.get(Document, job.document_id)
        if doc and doc.processing_status == "analyzing":
            doc.processing_status = "ready"
    db.commit()
    return {"success": True, "job_id": job.id, "status": job.status, "cancel_requested": True}


@findings_router.post("/{finding_id}/review")
def review_finding(finding_id: str, req: FindingReviewRequest, db: Session = Depends(get_db)):
    """Mark an editorial finding as user-reviewed or rejected."""
    finding = db.get(AnalysisFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

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
