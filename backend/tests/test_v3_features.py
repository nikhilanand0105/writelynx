import pytest
from pathlib import Path
import pymupdf
import docx

from backend.app.services.pdf_highlight_extractor import PDFHighlightExtractor
from backend.app.services.docx_aligner import DocxAligner
from backend.app.services.detector_comparator import DetectorComparator
from backend.app.services.terminology_classifier import TerminologyClassifier
from backend.app.services.writing_diagnostics import WritingDiagnosticsEngine
from backend.app.services.fact_validator import FactValidator
from backend.app.services.quantlens_validator import QuantLensValidator
from backend.app.services.docx_parser import DocxParser
from backend.app.services.structure_preserver import StructurePreserver
from backend.app.services.export_engine import ExportEngine
from backend.app.providers.no_llm_provider import NoLLMProvider

QUANTLENS_DOCX = Path("QuantLens_XAI_Final_Project_Report_Black_White (1) (1).docx")
ZEROGPT_PDF1 = Path("sample_documents/zerogpt_quantlens_report.pdf")
ZEROGPT_PDF2 = Path("sample_documents/zerogpt_quantlens_report_v2.pdf")

# 1. Load an original DOCX
def test_1_load_original_docx():
    assert QUANTLENS_DOCX.exists(), "Target QuantLens DOCX manuscript must exist."
    doc = docx.Document(str(QUANTLENS_DOCX))
    assert len(doc.paragraphs) > 50
    assert len(doc.tables) >= 11

# 2. Load a corresponding ZeroGPT PDF
def test_2_load_zerogpt_pdf():
    assert ZEROGPT_PDF1.exists(), "Target ZeroGPT detector PDF must exist."
    pdf = pymupdf.open(str(ZEROGPT_PDF1))
    assert pdf.page_count == 17
    pdf.close()

# 3. Extract highlighted regions (63+ fragments)
def test_3_extract_highlighted_regions():
    res = PDFHighlightExtractor.extract_highlights(ZEROGPT_PDF1)
    assert res["detector_name"] == "ZeroGPT"
    assert res["detector_score"] == 40.9
    assert res["is_truncated"] is True
    assert len(res["highlights"]) >= 20

# 4. Ignore website advertisement highlights & chrome
def test_4_ignore_website_ad_highlights():
    chrome_text = "Trusted GPT-6, ChatGPT and AI Detector tool by ZeroGPT Detect Text 15,000/15,000 Characters"
    assert PDFHighlightExtractor.is_chrome_or_ad(chrome_text) is True
    academic_text = "Closed-loop explainable artificial intelligence for stock market direction prediction."
    assert PDFHighlightExtractor.is_chrome_or_ad(academic_text) is False

# 5. Map each highlighted passage to its DOCX paragraph
def test_5_map_highlights_to_docx():
    hl_res = PDFHighlightExtractor.extract_highlights(ZEROGPT_PDF1)
    parser = DocxParser(QUANTLENS_DOCX, "quantlens_test")
    blocks_data, meta = parser.parse()
    aligned_hls, summary = DocxAligner.align_highlights_with_blocks(hl_res["highlights"], blocks_data)
    assert summary["matched_highlights"] >= 20
    assert summary["alignment_rate_pct"] >= 90.0

# 6. Compare two imported detector reports
def test_6_compare_two_detector_reports():
    assert ZEROGPT_PDF1.exists() and ZEROGPT_PDF2.exists()
    comp = DetectorComparator.compare_reports(ZEROGPT_PDF1, ZEROGPT_PDF2)
    assert comp["earlier_report"]["reported_score"] == 40.9
    assert comp["latest_report"]["reported_score"] == 40.9
    assert comp["comparison_summary"]["overlapping_fragments_count"] >= 60
    assert comp["comparison_summary"]["is_essentially_identical"] is True

# 7. Detect matching results across repeated exports
def test_7_detect_matching_results():
    comp = DetectorComparator.compare_reports(ZEROGPT_PDF1, ZEROGPT_PDF2)
    assert comp["comparison_summary"]["score_difference"] == 0.0
    assert comp["comparison_summary"]["newly_highlighted_count"] == 0

# 8. Preserve all numerical results
def test_8_preserve_all_numerical_results():
    orig = "Our QuantLens-XAI architecture achieved a Macro F1 of 0.3410 compared to the baseline 0.2897 with 14.5 ms latency."
    revised = "In our experiments, the proposed QuantLens-XAI architecture achieved a Macro F1 of 0.3410 compared to the baseline 0.2897 with 14.5 ms latency."
    ok, violations = QuantLensValidator.validate_facts(orig, revised)
    assert ok is True
    assert len(violations) == 0

    # Tampered metric check
    tampered = "Our QuantLens-XAI architecture achieved a Macro F1 of 0.3800 compared to the baseline 0.2897."
    ok_t, viol_t = QuantLensValidator.validate_facts(orig, tampered)
    assert ok_t is False
    assert any("0.3410" in v for v in viol_t)

# 9. Preserve equations and citations
def test_9_preserve_equations_and_citations():
    orig = "Closed-loop feedback was integrated into the training objective [1], [5]."
    rev_valid = "We integrated closed-loop feedback into the training objective [1], [5]."
    ok, _ = FactValidator.compare_facts(orig, rev_valid)
    assert ok is True

    rev_dropped = "We integrated closed-loop feedback into the training objective."
    ok_bad, viol_bad = FactValidator.compare_facts(orig, rev_dropped)
    assert ok_bad is False

# 10. Identify unsupported claims (causality overreach & statistical overstatement)
def test_10_identify_unsupported_claims():
    text = "Feature perturbation with SHAP proves real-world market price causality."
    issues = QuantLensValidator.check_scientific_rigor(text)
    assert len(issues) >= 1
    assert any(i["type"] == "unsupported_causality_assertion" for i in issues)

# 11. Identify research evidence gaps & author clarifying questions
def test_11_identify_evidence_gaps_and_questions():
    text = "The model achieved a Macro F1 score of 0.3410 using 6 features with a 30-bar temporal lookback."
    questions = QuantLensValidator.generate_author_questions(text)
    assert len(questions) >= 2
    topics = [q["topic"] for q in questions]
    assert "Empirical Benchmark Run" in topics or "Temporal Window Parameter" in topics

# 12. Generate context-aware revision suggestions (Natural Student Research Mode)
@pytest.mark.asyncio
async def test_12_natural_student_research_revision():
    provider = NoLLMProvider()
    orig = "This groundbreaking framework is institutional-grade and completely reliable due to the fact that prior models failed."
    sug = await provider.generate_suggestion(
        block_id="b1",
        original_text=orig,
        context="methodology",
        mode="natural_student_research"
    )
    assert sug is not None
    proposed = sug["proposed_text"]
    assert "groundbreaking" not in proposed.lower()
    assert "institutional-grade" not in proposed.lower()
    assert "because" in proposed.lower()

# 13. Terminology & heading exceptions classification
def test_13_terminology_exceptions():
    univ = "VELLORE INSTITUTE OF TECHNOLOGY (VIT) SCHOOL OF COMPUTER SCIENCE AND ENGINEERING"
    c_univ = TerminologyClassifier.classify(univ)
    assert c_univ["is_terminology_exception"] is True
    assert c_univ["exception_category"] == "university_name"

    heading = "1. Introduction"
    c_head = TerminologyClassifier.classify(heading, block_type="heading")
    assert c_head["is_terminology_exception"] is True
    assert c_head["exception_category"] == "academic_heading"

# 14. Validate the final document
def test_14_validate_final_document(tmp_path):
    out_docx = tmp_path / "validated.docx"
    engine = ExportEngine(QUANTLENS_DOCX)
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks_data, meta = parser.parse()
    is_valid, report = engine.export_docx(out_docx, {}, blocks_data)
    assert is_valid is True
    assert report["protected_facts_intact"] is True

# 15. Export DOCX
def test_15_export_docx(tmp_path):
    out_docx = tmp_path / "exported.docx"
    engine = ExportEngine(QUANTLENS_DOCX)
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks_data, meta = parser.parse()
    is_valid, report = engine.export_docx(out_docx, {}, blocks_data)
    assert out_docx.exists()
    assert out_docx.stat().st_size > 100_000

# 16. Export PDF via LibreOffice headless
def test_16_export_pdf(tmp_path):
    out_docx = tmp_path / "exported.docx"
    out_pdf = tmp_path / "exported.pdf"
    engine = ExportEngine(QUANTLENS_DOCX)
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks_data, meta = parser.parse()
    engine.export_docx(out_docx, {}, blocks_data)
    is_valid, report = engine.export_pdf(out_docx, out_pdf)
    assert is_valid is True
    assert out_pdf.exists()

# 17. Reopen exported files
def test_17_reopen_exported_files(tmp_path):
    out_docx = tmp_path / "reopen.docx"
    out_pdf = tmp_path / "reopen.pdf"
    engine = ExportEngine(QUANTLENS_DOCX)
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks_data, meta = parser.parse()
    engine.export_docx(out_docx, {}, blocks_data)
    engine.export_pdf(out_docx, out_pdf)

    # Reopen docx
    reopened_doc = docx.Document(str(out_docx))
    assert len(reopened_doc.paragraphs) > 50

    # Reopen pdf
    reopened_pdf = pymupdf.open(str(out_pdf))
    assert reopened_pdf.page_count >= 15
    reopened_pdf.close()

# 18. Verify that no unrelated report content disappeared
def test_18_verify_content_integrity(tmp_path):
    out_docx = tmp_path / "integrity.docx"
    engine = ExportEngine(QUANTLENS_DOCX)
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks_data, meta = parser.parse()
    engine.export_docx(out_docx, {}, blocks_data)

    orig_doc = docx.Document(str(QUANTLENS_DOCX))
    new_doc = docx.Document(str(out_docx))

    assert len(orig_doc.paragraphs) == len(new_doc.paragraphs)
    assert len(orig_doc.tables) == len(new_doc.tables)
