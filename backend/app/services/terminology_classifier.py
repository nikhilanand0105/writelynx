import re
from typing import Dict, Any, Optional, Tuple

UNIVERSITY_PATTERNS = [
    re.compile(r'\b(?:Vellore\s+Institute\s+of\s+Technology|VIT|School\s+of\s+Computer\s+Science|Department\s+of\s+Artificial\s+Intelligence|University|Institute|College|Faculty\s+of)\b', re.IGNORECASE),
    re.compile(r'\bAcademic\s+Year\s+\d{4}[–-]\d{4}\b', re.IGNORECASE),
]

COURSE_CODE_PATTERNS = [
    re.compile(r'\b[A-Z]{3,4}\d{3,4}[A-Z]?\b'),  # e.g. BCSE336L, CS101
    re.compile(r'\bCourse\s+Code\b', re.IGNORECASE),
]

PROJECT_TITLE_PATTERNS = [
    re.compile(r'\bQuantLens[-_ ]XAI\b', re.IGNORECASE),
    re.compile(r'\bClosed[- ]Loop\s+Explainable\s+Artificial\s+Intelligence\b', re.IGNORECASE),
    re.compile(r'\bProject\s+Report\b', re.IGNORECASE),
    re.compile(r'\bCapstone\s+Project\b', re.IGNORECASE),
]

HEADING_PATTERNS = [
    re.compile(r'^(?:Abstract|Introduction|Related\s+Work|Literature\s+Survey|Methodology|System\s+Architecture|Proposed\s+System|Experimental\s+Results|Discussion|Conclusion|References|Acknowledgements?)\b', re.IGNORECASE),
    re.compile(r'^\d+(\.\d+)*\s+[A-Z]', re.IGNORECASE),  # e.g. 1. Introduction, 3.2 Feature Selection
]

TECHNICAL_ENTITIES = [
    "XGBoost", "SHAP", "LIME", "Grad-CAM", "1D Temporal Grad-CAM",
    "TimeSeriesConv1D", "Closed-loop explanation feedback",
    "Feature perturbation", "Explanation-guided retraining",
    "Sensitivity analysis", "MongoDB", "Macro F1", "Micro F1",
    "OHLCV", "Temporal lookback", "Chronological train/test",
    "MiFID II RTS 25", "SEC Rule 15c3-5", "PyTorch", "scikit-learn"
]

METRIC_PATTERNS = [
    re.compile(r'\b(?:Macro\s+F1|F1[- ]score|accuracy|precision|recall|latency)\b', re.IGNORECASE),
    re.compile(r'\b0\.\d{3,4}\b'),      # e.g. 0.3410, 0.2897
    re.compile(r'\b\d+(\.\d+)?\s*(?:ms|milliseconds|seconds|%|bars?|features?)\b', re.IGNORECASE),
]

class TerminologyClassifier:
    """
    Classifies highlighted or extracted passages into standard academic exceptions
    vs substantive narrative paragraphs to prevent automatic rewriting of
    institution names, course codes, project titles, headings, and domain metrics.
    """

    @classmethod
    def classify(cls, text: str, block_type: str = "paragraph") -> Dict[str, Any]:
        cleaned = text.strip()
        word_count = len(cleaned.split())

        # 1. Academic Headings / Section titles
        if block_type in ("heading", "title") or any(p.search(cleaned) for p in HEADING_PATTERNS):
            if word_count < 15:
                return {
                    "is_terminology_exception": True,
                    "exception_category": "academic_heading",
                    "recommended_action": "preserve_as_domain_standard",
                    "explanation": "Standard academic section heading or chapter title; must remain invariant."
                }

        # 2. University / Faculty / Department metadata
        if any(p.search(cleaned) for p in UNIVERSITY_PATTERNS):
            return {
                "is_terminology_exception": True,
                "exception_category": "university_name",
                "recommended_action": "preserve_as_domain_standard",
                "explanation": "Official institutional affiliation, school, or department nomenclature."
            }

        # 3. Course codes / Academic markers
        if any(p.search(cleaned) for p in COURSE_CODE_PATTERNS) and word_count < 10:
            return {
                "is_terminology_exception": True,
                "exception_category": "course_code",
                "recommended_action": "preserve_as_domain_standard",
                "explanation": "Standard curriculum course code or registrar catalog identifier."
            }

        # 4. Project titles
        if any(p.search(cleaned) for p in PROJECT_TITLE_PATTERNS) and word_count < 25:
            return {
                "is_terminology_exception": True,
                "exception_category": "project_title",
                "recommended_action": "preserve_as_domain_standard",
                "explanation": "Authorized research project title; must not be paraphrased or rewritten."
            }

        # 5. Pure technical entity or metric enumeration
        matched_entities = [e for e in TECHNICAL_ENTITIES if re.search(r'\b' + re.escape(e) + r'\b', cleaned, re.IGNORECASE)]
        has_metrics = any(p.search(cleaned) for p in METRIC_PATTERNS)
        if matched_entities and word_count < 18:
            return {
                "is_terminology_exception": True,
                "exception_category": "technical_entity",
                "recommended_action": "preserve_as_domain_standard",
                "matched_entities": matched_entities,
                "explanation": f"Domain-standard technical entities ({', '.join(matched_entities[:3])}); protected from rewriting."
            }

        if has_metrics and word_count < 12:
            return {
                "is_terminology_exception": True,
                "exception_category": "numerical_metric",
                "recommended_action": "preserve_as_domain_standard",
                "explanation": "Empirical metric specification or parameter definition; must be preserved verbatim."
            }

        # Substantive narrative passage
        return {
            "is_terminology_exception": False,
            "exception_category": "substantive_narrative",
            "recommended_action": "evaluate_writing_quality",
            "explanation": "Substantive narrative paragraph subject to editorial quality and clarity review."
        }
