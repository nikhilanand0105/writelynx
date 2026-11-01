import asyncio
import datetime
from pathlib import Path
from typing import Optional, Set
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    Document, DocumentBlock, ReferenceSource, AnalysisFinding, EditSuggestion, DetectorHighlight, AnalysisJob, Entitlement
)
from backend.app.services.similarity_engine import SimilarityEngine
from backend.app.services.citation_analyzer import CitationAnalyzer
from backend.app.services.writing_assistant import WritingAssistant
from backend.app.services.writing_diagnostics import WritingDiagnosticsEngine
from backend.app.services.pdf_highlight_extractor import PDFHighlightExtractor
from backend.app.services.docx_aligner import DocxAligner

async def run_document_analysis_job(
    document_id: str,
    editing_mode: str = "academic_revision",
    llm_provider: Optional[str] = None,
    job_id: Optional[str] = None
):
    """
    Comprehensive background worker that runs:
    1. Detector PDF extraction & alignment (if detector PDF attached)
    2. 12-Module Writing Diagnostics + QuantLens-XAI rules
    3. Evidence-based Similarity Matching against indexed sources
    4. Citation & Bibliography Integrity Audit
    5. Context-aware Academic Revision Engine (3 modes)
    """
    db: Session = SessionLocal()

    def check_cancelled() -> bool:
        if not job_id:
            return False
        j = db.get(AnalysisJob, job_id)
        if j and j.cancel_requested:
            j.status = "cancelled"
            j.stage = "Cancelled by user"
            j.finished_at = datetime.datetime.utcnow()
            d = db.get(Document, document_id)
            if d and d.processing_status == "analyzing":
                d.processing_status = "ready"
            db.commit()
            return True
        return False

    def update_stage(stage_name: str, progress_pct: int):
        if not job_id:
            return
        j = db.get(AnalysisJob, job_id)
        if j:
            j.stage = stage_name
            j.progress = progress_pct
            db.commit()

    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        doc.processing_status = "analyzing"
        db.commit()

        if check_cancelled():
            return

        # Fetch document blocks
        blocks_records = db.query(DocumentBlock).filter(DocumentBlock.document_id == document_id).order_by(DocumentBlock.block_index).all()
        blocks_data = [
            {
                "id": b.id,
                "document_id": b.document_id,
                "block_index": b.block_index,
                "section_id": b.section_id,
                "block_type": b.block_type,
                "current_text": b.current_text,
                "original_text": b.original_text,
                "is_protected": b.is_protected,
                "structure_metadata": b.structure_metadata or {}
            }
            for b in blocks_records
        ]

        # 1. Detector PDF Extraction & Alignment (if attached)
        update_stage("Checking external detector highlights", 15)
        if check_cancelled():
            return

        detector_highlight_blocks: Set[str] = set()
        if doc.detector_pdf_path and Path(doc.detector_pdf_path).exists():
            try:
                hl_result = PDFHighlightExtractor.extract_highlights(Path(doc.detector_pdf_path))
                doc.detector_name = hl_result["detector_name"]
                doc.detector_score = hl_result["detector_score"]
                doc.is_truncated = hl_result["is_truncated"]

                # Align with blocks
                aligned_hls, alignment_summary = DocxAligner.align_highlights_with_blocks(
                    hl_result["highlights"], blocks_data
                )

                # Clear previous highlights for this document
                db.query(DetectorHighlight).filter(DetectorHighlight.document_id == document_id).delete()

                for a_hl in aligned_hls:
                    b_id = a_hl.get("block_id")
                    if b_id:
                        detector_highlight_blocks.add(b_id)
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
                        metadata_json=a_hl.get("metadata_json", {})
                    )
                    db.add(dh)

                # Mark blocks that have detector highlights
                for b_rec in blocks_records:
                    if b_rec.id in detector_highlight_blocks:
                        b_rec.has_detector_highlight = True
                db.commit()
            except Exception as e:
                print(f"Error in detector PDF processing: {e}")

        # 2. 12-Module Writing Diagnostics Engine + QuantLens-XAI Rules
        update_stage("Running 12 writing diagnostic modules", 35)
        if check_cancelled():
            return

        diagnostic_findings = WritingDiagnosticsEngine.analyze_document_diagnostics(
            blocks=blocks_data,
            detector_highlight_blocks=detector_highlight_blocks
        )

        # 3. Similarity Engine against uploaded reference sources
        update_stage("Indexing reference sources & similarity", 55)
        if check_cancelled():
            return

        sources_records = db.query(ReferenceSource).filter(ReferenceSource.document_id == document_id).all()
        sources_data = [
            {
                "id": s.id,
                "title": s.title,
                "source_type": s.source_type,
                "extracted_text": s.extracted_text or "",
            }
            for s in sources_records
        ]
        sim_engine = SimilarityEngine()
        sim_findings, sim_metrics = sim_engine.analyze_document_against_sources(blocks_data, sources_data)

        # 4. Citation Analyzer
        update_stage("Auditing citation & bibliography integrity", 70)
        if check_cancelled():
            return

        cit_analyzer = CitationAnalyzer()
        cit_findings, cit_audit = cit_analyzer.analyze(blocks_data)

        # Combine all findings
        all_findings = diagnostic_findings + sim_findings + cit_findings

        # 5. Writing Assistant
        update_stage("Generating context-aware editorial suggestions", 85)
        if check_cancelled():
            return

        assistant = WritingAssistant(provider_name=llm_provider)
        suggestions = await assistant.generate_document_suggestions(
            blocks_data,
            mode="clarity" if editing_mode in ["academic_revision", "clarity"] else editing_mode,
            findings=all_findings,
            document_id=document_id,
            plan_tier=doc.plan_tier or "basic",
            db=db,
        )

        if check_cancelled():
            return

        update_stage("Persisting findings & suggestions", 95)

        # Clear existing unreviewed findings and suggestions
        db.query(AnalysisFinding).filter(
            AnalysisFinding.document_id == document_id,
            AnalysisFinding.review_status == "pending"
        ).delete()

        db.query(EditSuggestion).filter(
            EditSuggestion.document_id == document_id,
            EditSuggestion.review_status == "pending"
        ).delete()

        # Persist findings
        for f in all_findings:
            db_finding = AnalysisFinding(
                id=f["id"],
                document_id=f["document_id"],
                block_id=f["block_id"],
                source_id=f.get("source_id"),
                finding_type=f["finding_type"],
                issue_category=f.get("issue_category", "general"),
                severity=f["severity"],
                external_detector_highlight=f.get("external_detector_highlight", f["block_id"] in detector_highlight_blocks),
                matched_text=f.get("matched_text"),
                source_matched_text=f.get("source_matched_text"),
                similarity_score=f.get("similarity_score", 0.0),
                match_type=f.get("match_type", "exact"),
                evidence=f.get("evidence", {}),
                required_evidence=f.get("required_evidence", []),
                recommended_action=f.get("recommended_action", "verify_claim"),
                requires_author_input=f.get("requires_author_input", True),
                review_status=f.get("review_status", "pending")
            )
            db.add(db_finding)

        # Persist suggestions
        for s in suggestions:
            db_sug = EditSuggestion(
                id=s["id"],
                document_id=s["document_id"],
                block_id=s["block_id"],
                issue_type=s["issue_type"],
                original_text=s["original_text"],
                proposed_text=s["proposed_text"],
                reason=s["reason"],
                citations_preserved=s["citations_preserved"],
                protected_entities_preserved=s["protected_entities_preserved"],
                requires_user_review=s["requires_user_review"],
                confidence=s["confidence"],
                validation_status=s["validation_status"],
                review_status="pending"
            )
            db.add(db_sug)

        # Update document metrics
        doc_meta = dict(doc.doc_metadata or {})
        doc_meta["diagnostic_metrics"] = sim_metrics
        doc_meta["citation_audit"] = cit_audit
        doc_meta["diagnostic_findings_count"] = len(diagnostic_findings)
        doc.doc_metadata = doc_meta
        doc.processing_status = "analyzed"

        # Update job completion & Entitlement fulfillment
        if job_id:
            job = db.get(AnalysisJob, job_id)
            if job:
                job.status = "completed"
                job.stage = "Analysis complete"
                job.progress = 100
                job.finished_at = datetime.datetime.utcnow()

        if doc.entitlement_id:
            ent = db.query(Entitlement).filter(Entitlement.id == doc.entitlement_id).first()
            if ent:
                ent.status = "COMPLETED"

        db.commit()

    except Exception as e:
        db.rollback()
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.processing_status = "error"
                doc_meta = dict(doc.doc_metadata or {})
                doc_meta["last_error"] = str(e)
                doc.doc_metadata = doc_meta

            if job_id:
                job = db.get(AnalysisJob, job_id)
                if job:
                    job.status = "failed"
                    job.stage = "Analysis failed"
                    job.error = str(e)
                    job.finished_at = datetime.datetime.utcnow()

            db.commit()
        except Exception:
            pass
    finally:
        db.close()
