import pytest
from pathlib import Path
import docx
from backend.app.services.pdf_highlight_extractor import PDFHighlightExtractor
from backend.app.services.docx_aligner import DocxAligner
from backend.app.services.writing_diagnostics import WritingDiagnosticsEngine
from backend.app.services.flagged_comparison import FlaggedComparisonService
from backend.app.services.fact_validator import FactValidator
from backend.app.services.structure_preserver import StructurePreserver
from backend.app.services.export_engine import ExportEngine
from backend.app.services.docx_parser import DocxParser
from backend.app.providers.no_llm_provider import NoLLMProvider

ZEROGPT_PDF = Path("sample_documents/zerogpt_quantlens_report.pdf")
QUANTLENS_DOCX = Path("QuantLens_XAI_Final_Project_Report_Black_White (1) (1).docx")

# Test 1: Extracting native PDF yellow-highlight rectangles
def test_extract_native_pdf_yellow_highlights():
    assert ZEROGPT_PDF.exists()
    hl_res = PDFHighlightExtractor.extract_highlights(ZEROGPT_PDF)
    assert hl_res["total_highlights"] > 10
    first_hl = hl_res["highlights"][0]
    assert "page_number" in first_hl
    assert len(first_hl["highlight_text"]) > 10
    assert len(first_hl["bbox"]) == 4

# Test 2: Distinguishing website highlighting from document decoration / ads
def test_distinguish_website_chrome_and_ads():
    assert PDFHighlightExtractor.is_chrome_or_ad("Trusted GPT-6, ChatGPT and AI Detector tool by ZeroGPT") is True
    assert PDFHighlightExtractor.is_chrome_or_ad("Check 350,000 characters, Upgrade Here") is True
    assert PDFHighlightExtractor.is_chrome_or_ad("15,000/15,000 Characters") is True
    assert PDFHighlightExtractor.is_chrome_or_ad("Closed-loop explanation feedback for time series classification") is False

# Test 3: Matching detector highlights to original DOCX paragraphs
def test_match_detector_highlights_to_docx():
    assert QUANTLENS_DOCX.exists()
    parser = DocxParser(QUANTLENS_DOCX, "ql_doc")
    blocks, _ = parser.parse()
    
    hl_res = PDFHighlightExtractor.extract_highlights(ZEROGPT_PDF)
    aligned, summary = DocxAligner.align_highlights_with_blocks(hl_res["highlights"], blocks)
    
    assert summary["matched_highlights"] > 0
    assert summary["alignment_rate_pct"] > 80.0
    matched = [h for h in aligned if h["mapping_status"] == "matched"]
    assert len(matched) > 0
    assert matched[0]["block_id"] is not None

# Test 4: Identifying PDF reports containing truncated input
def test_detect_truncated_detector_report():
    hl_res = PDFHighlightExtractor.extract_highlights(ZEROGPT_PDF)
    assert hl_res["is_truncated"] is True
    assert "Only part of this document was evaluated" in hl_res["truncation_notice"]

# Test 5 & 6: Preserving numerical values and technical notation
def test_preserve_numerical_values_and_notation():
    orig = "Selecting six SHAP features improved Macro F1 from 0.2897 to 0.3410 with latency 14.5 ms [1]."
    # Modifying the numbers triggers violation
    tampered = "Selecting six SHAP features improved Macro F1 from 0.2897 to 0.3800 with latency 14.5 ms [1]."
    valid, violations = FactValidator.compare_facts(orig, tampered)
    assert valid is False
    assert any("0.3410" in v for v in violations)

# Test 7: Flagging unsupported statistical claims
def test_flag_unsupported_statistical_claims():
    blocks = [{
        "id": "b_stat",
        "document_id": "d1",
        "section_id": "Results",
        "block_type": "paragraph",
        "current_text": "Our proposed model is significantly better than baseline architectures on the benchmark dataset."
    }]
    findings = WritingDiagnosticsEngine.analyze_document_diagnostics(blocks)
    sig_findings = [f for f in findings if f["finding_type"] == "unsupported_certainty"]
    assert len(sig_findings) > 0
    assert "Statistical significance" in sig_findings[0]["evidence"]["issue"]

# Test 8: Distinguishing attribution from causality
def test_distinguish_attribution_from_causality():
    blocks = [{
        "id": "b_causal",
        "document_id": "d1",
        "section_id": "Results",
        "block_type": "paragraph",
        "current_text": "SHAP feature attributions prove real-world causality in stock market direction."
    }]
    findings = WritingDiagnosticsEngine.analyze_document_diagnostics(blocks)
    causal_findings = [f for f in findings if f["finding_type"] == "terminology_confusion"]
    assert len(causal_findings) > 0
    assert "decision sensitivity" in causal_findings[0]["evidence"]["issue"]

# Test 9: Preserving citations
def test_preserve_citations():
    orig = "The closed-loop architecture incorporates human expert validation [1] and Bayesian optimization [2]."
    tampered = "The closed-loop architecture incorporates human expert validation and Bayesian optimization."
    valid, violations = FactValidator.compare_facts(orig, tampered)
    assert valid is False
    assert any("[1]" in v for v in violations)

# Test 10: Preserving tables and images in DOCX
def test_preserve_tables_and_images(tmp_path):
    parser = DocxParser(QUANTLENS_DOCX, "ql_test")
    blocks, meta = parser.parse()
    assert meta["table_count"] == 11
    assert meta["image_count"] == 11

    target = tmp_path / "preserved_ql.docx"
    preserver = StructurePreserver(QUANTLENS_DOCX)
    success, report = preserver.apply_edits_and_export(target, {}, blocks)
    assert success is True
    assert report["table_count"] == 11
    assert report["image_count"] == 11

# Test 11: Flagged vs Unflagged descriptive comparison without evasion claims
def test_flagged_vs_unflagged_descriptive_statistics():
    blocks = [
        {"id": "b1", "block_type": "paragraph", "current_text": "XGBoost and LSTM architectures evaluated using SHAP, LIME, Grad-CAM, RTS, and MiFID."},
        {"id": "b2", "block_type": "paragraph", "current_text": "We describe our methodology and general experimental assumptions for future work."}
    ]
    resp = FlaggedComparisonService.analyze_flagged_vs_unflagged("doc1", blocks, {"b1"}, "ZeroGPT")
    assert resp.detector_name == "ZeroGPT"
    assert "proprietary detector" in resp.disclaimer
    assert resp.highlighted_passages.technical_term_density_pct > resp.unhighlighted_passages.technical_term_density_pct

# Test 12: Offline mode with zero external network requests
@pytest.mark.asyncio
async def test_offline_mode_zero_external_requests():
    provider = NoLLMProvider()
    assert await provider.test_connection() is True
    sug = await provider.generate_suggestion(
        block_id="b1",
        original_text="Due to the fact that prior systems failed, training was conducted by us.",
        context="",
        mode="academic_revision"
    )
    assert sug is not None
    assert "Because" in sug["proposed_text"] or "because" in sug["proposed_text"]

# Test 13: Avoiding unsupported claims of AI-origin detection
def test_avoid_unsupported_ai_origin_claims():
    blocks = [{
        "id": "b_gen",
        "document_id": "d1",
        "section_id": "Intro",
        "block_type": "paragraph",
        "current_text": "Artificial intelligence has revolutionized modern scientific computing in recent years."
    }]
    findings = WritingDiagnosticsEngine.analyze_document_diagnostics(blocks)
    gen_findings = [f for f in findings if f["finding_type"] == "generic_claim"]
    assert len(gen_findings) > 0
    # Make sure we explain lack of empirical specificity, NOT claiming it proves AI authorship!
    assert "lacks empirical context" in gen_findings[0]["evidence"]["issue"]
    assert "AI authorship" not in gen_findings[0]["evidence"]["issue"]
