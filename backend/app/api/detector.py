import uuid
import datetime
from pathlib import Path
from typing import List, Set, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename, calculate_file_hash
from backend.app.models.models import Document, DocumentBlock, DetectorHighlight, DetectorReport
from backend.app.schemas.schemas import (
    DetectorHighlightResponse,
    DetectorHighlightManualMapRequest,
    FlaggedVsUnflaggedResponse
)
from backend.app.services.pdf_highlight_extractor import PDFHighlightExtractor
from backend.app.services.docx_aligner import DocxAligner
from backend.app.services.flagged_comparison import FlaggedComparisonService
from backend.app.services.detector_comparator import DetectorComparator
from backend.app.services.terminology_classifier import TerminologyClassifier

router = APIRouter(prefix="/documents", tags=["External Detector Highlights"])

@router.post("/{document_id}/detector-pdf")
async def upload_detector_pdf(
    document_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a third-party AI detector PDF export (e.g. ZeroGPT or Turnitin).
    Extracts native highlight rectangles, detects truncation, and aligns with DOCX blocks.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF detector reports are supported.")

    pdf_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    dest_path = settings.STORAGE_DIR / "sources" / f"{pdf_id}_{safe_name}"

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    doc.detector_pdf_path = str(dest_path)

    # Extract highlights
    hl_res = PDFHighlightExtractor.extract_highlights(dest_path)
    doc.detector_name = hl_res["detector_name"]
    doc.detector_score = hl_res["detector_score"]
    doc.is_truncated = hl_res["is_truncated"]

    # Align with DOCX blocks
    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).order_by(DocumentBlock.block_index).all()
    blocks_data = [
        {"id": b.id, "block_index": b.block_index, "section_id": b.section_id, "current_text": b.current_text}
        for b in blocks
    ]

    aligned_hls, summary = DocxAligner.align_highlights_with_blocks(hl_res["highlights"], blocks_data)

    # Clear previous highlights
    db.query(DetectorHighlight).filter(DetectorHighlight.document_id == document_id).delete()

    matched_block_ids: Set[str] = set()
    terminology_exceptions_count = 0
    for a_hl in aligned_hls:
        b_id = a_hl.get("block_id")
        if b_id:
            matched_block_ids.add(b_id)
        
        # Classify terminology & heading exceptions
        term_class = TerminologyClassifier.classify(a_hl["highlight_text"])
        is_exc = term_class.get("is_terminology_exception", False)
        if is_exc:
            terminology_exceptions_count += 1

        meta = a_hl.get("metadata_json", {})
        meta.update(term_class)

        dh = DetectorHighlight(
            id=f"{document_id[:8]}_{a_hl['id']}",
            document_id=document_id,
            block_id=b_id,
            page_number=a_hl["page_number"],
            highlight_text=a_hl["highlight_text"],
            bbox=a_hl.get("bbox", []),
            match_confidence=a_hl.get("match_confidence", 0.0),
            mapping_status=a_hl.get("mapping_status", "unresolved"),
            detector_name=doc.detector_name or "ZeroGPT",
            extraction_strategy=a_hl.get("extraction_strategy", "native_rectangles"),
            metadata_json=meta
        )
        db.add(dh)

    # Update blocks
    for b in blocks:
        b.has_detector_highlight = b.id in matched_block_ids

    # Store persistent DetectorReport record
    try:
        report_record = DetectorReport(
            id=str(uuid.uuid4()),
            document_id=document_id,
            filename=file.filename,
            file_path=str(dest_path),
            file_hash=calculate_file_hash(dest_path),
            created_at=datetime.datetime.utcnow(),
            metadata_json={
                "detector_name": doc.detector_name,
                "detector_score": doc.detector_score,
                "is_truncated": doc.is_truncated,
                "total_highlights": len(aligned_hls),
                "terminology_exceptions_count": terminology_exceptions_count
            }
        )
        db.add(report_record)
    except Exception as e:
        pass

    db.commit()
    db.refresh(doc)

    summary["terminology_exceptions_count"] = terminology_exceptions_count

    return {
        "success": True,
        "detector_name": doc.detector_name,
        "detector_score": doc.detector_score,
        "is_truncated": doc.is_truncated,
        "truncation_notice": hl_res.get("truncation_notice"),
        "alignment_summary": summary,
        "total_highlights": len(aligned_hls),
        "terminology_exceptions_count": terminology_exceptions_count
    }

@router.get("/{document_id}/detector-reports")
def list_detector_reports(document_id: str, db: Session = Depends(get_db)):
    """List all imported detector PDF reports for this document."""
    reports = db.query(DetectorReport).filter(DetectorReport.document_id == document_id).order_by(DetectorReport.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "filename": r.filename,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "metadata": r.metadata_json or {}
        }
        for r in reports
    ]

@router.get("/{document_id}/detector-highlights", response_model=List[DetectorHighlightResponse])
def list_detector_highlights(document_id: str, db: Session = Depends(get_db)):
    """List all extracted detector highlights and their mapped DOCX paragraphs."""
    return db.query(DetectorHighlight).filter(DetectorHighlight.document_id == document_id).all()

@router.post("/detector-highlights/{highlight_id}/map")
def manually_map_highlight(
    highlight_id: str,
    req: DetectorHighlightManualMapRequest,
    db: Session = Depends(get_db)
):
    """Manually assign or correct the DOCX block alignment for a highlight."""
    hl = db.query(DetectorHighlight).filter(DetectorHighlight.id == highlight_id).first()
    if not hl:
        raise HTTPException(status_code=404, detail="Detector highlight not found.")

    block = db.query(DocumentBlock).filter(DocumentBlock.id == req.block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Target document block not found.")

    hl.block_id = req.block_id
    hl.mapping_status = "manually_corrected"
    hl.match_confidence = 1.0
    block.has_detector_highlight = True
    db.commit()

    return {"success": True, "highlight_id": highlight_id, "block_id": req.block_id, "status": "manually_corrected"}

@router.get("/{document_id}/flagged-comparison", response_model=FlaggedVsUnflaggedResponse)
def get_flagged_vs_unflagged_comparison(document_id: str, db: Session = Depends(get_db)):
    """
    Retrieve descriptive statistical comparison between passages highlighted by the detector
    and unflagged passages within the manuscript.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    blocks = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).all()
    blocks_data = [
        {"id": b.id, "block_type": b.block_type, "current_text": b.current_text, "original_text": b.original_text}
        for b in blocks
    ]

    highlights = db.query(DetectorHighlight).filter(DetectorHighlight.document_id == document_id).all()
    flagged_block_ids = {h.block_id for h in highlights if h.block_id}

    return FlaggedComparisonService.analyze_flagged_vs_unflagged(
        document_id=document_id,
        blocks=blocks_data,
        detector_highlight_block_ids=flagged_block_ids,
        detector_name=doc.detector_name or "ZeroGPT"
    )

@router.post("/{document_id}/compare-reports")
async def compare_detector_reports(
    document_id: str,
    file2: UploadFile = File(...),
    file1: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Compare two detector PDF reports (e.g. an earlier ZeroGPT PDF vs a newer ZeroGPT PDF)
    on the same manuscript.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Determine earlier report path
    path1: Path
    if file1 is not None:
        p1_id = str(uuid.uuid4())
        safe_name1 = sanitize_filename(file1.filename)
        dest1 = settings.STORAGE_DIR / "sources" / f"{p1_id}_{safe_name1}"
        content1 = await file1.read()
        with open(dest1, "wb") as f:
            f.write(content1)
        path1 = dest1
    elif doc.detector_pdf_path and Path(doc.detector_pdf_path).exists():
        path1 = Path(doc.detector_pdf_path)
    else:
        raise HTTPException(
            status_code=400,
            detail="Earlier report not found. Please provide both file1 and file2."
        )

    # Save latest report path
    p2_id = str(uuid.uuid4())
    safe_name2 = sanitize_filename(file2.filename)
    dest2 = settings.STORAGE_DIR / "sources" / f"{p2_id}_{safe_name2}"
    content2 = await file2.read()
    with open(dest2, "wb") as f:
        f.write(content2)
    path2 = dest2

    return DetectorComparator.compare_reports(path1, path2)
