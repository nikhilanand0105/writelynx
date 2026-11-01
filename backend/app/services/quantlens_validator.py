import re
from typing import Dict, Any, List, Tuple, Optional

# Core QuantLens-XAI empirical parameters that must remain protected
QUANTLENS_PROTECTED_ENTITIES = {
    "Macro F1": [r'\b0\.3410\b', r'\b0\.2897\b', r'\bMacro\s+F1\b'],
    "Features": [r'\b6\s+features\b', r'\b22\s+features\b'],
    "Temporal Lookback": [r'\b30[- ]bar\b', r'\b30[- ]day\b', r'\blookback\b'],
    "Channels": [r'\b10\s+temporal\s+(?:input\s+)?channels\b', r'\b10\s+channels\b'],
    "Latency": [r'\b14\.5\s*ms\b'],
    "Models": [r'\bXGBoost\b', r'\bSHAP\b', r'\bLIME\b', r'\b1D\s+Temporal\s+Grad[- ]CAM\b', r'\bTimeSeriesConv1D\b'],
    "Infrastructure": [r'\bMongoDB\b', r'\bOHLCV\b', r'\bclosed[- ]loop\b']
}

class QuantLensValidator:
    """
    Project-specific validation profile for QuantLens-XAI research manuscripts.
    Protects empirical benchmark numbers, enforces rigorous scientific distinction
    between feature attribution and market causality, and generates author interview questions.
    """

    @classmethod
    def validate_facts(cls, original_text: str, revised_text: str) -> Tuple[bool, List[str]]:
        """Verify that QuantLens-XAI experimental metrics are strictly preserved."""
        violations = []
        for entity_name, patterns in QUANTLENS_PROTECTED_ENTITIES.items():
            for pat in patterns:
                m_orig = re.search(pat, original_text, re.IGNORECASE)
                if m_orig:
                    m_rev = re.search(pat, revised_text, re.IGNORECASE)
                    if not m_rev:
                        violations.append(f"QuantLens-XAI protected entity omitted: '{entity_name}' ('{m_orig.group(0)}')")

        return len(violations) == 0, violations

    @classmethod
    def check_scientific_rigor(cls, text: str) -> List[Dict[str, Any]]:
        """Perform scientific sanity checks on explainability and financial causality."""
        issues = []

        # 1. Feature perturbation vs Market Causality check
        if re.search(r'\b(feature\s+perturbation|SHAP|LIME)\b', text, re.IGNORECASE):
            if re.search(r'\b(causes?|drives?|establishes?|proves?)\s+(?:real[- ]world\s+)?(?:market\s+price|financial|economic)\s+(?:causality|movement|behavior)\b', text, re.IGNORECASE):
                issues.append({
                    "type": "unsupported_causality_assertion",
                    "severity": "high",
                    "matched_text": text[:120],
                    "issue": "Feature perturbation and explainability attributions (SHAP/LIME) quantify model decision sensitivity, not external financial market causality.",
                    "recommended_action": "Clarify that attributions reflect internal model feature responsiveness, not macroeconomic price causation."
                })

        # 2. Chronological data split consistency check
        if re.search(r'\b(train[- ]test|validation\s+split|partition)\b', text, re.IGNORECASE):
            if re.search(r'\b(random\s+split|k[- ]fold\s+cross[- ]validation|shuffled)\b', text, re.IGNORECASE):
                if not re.search(r'\b(purged|embargo|chronological|time[- ]series)\b', text, re.IGNORECASE):
                    issues.append({
                        "type": "lookahead_bias_risk",
                        "severity": "high",
                        "matched_text": text[:120],
                        "issue": "Financial time-series data requires strict chronological train/test partitioning to prevent lookahead bias.",
                        "recommended_action": "Specify chronological walk-forward or purged train/test partition."
                    })

        # 3. Statistical significance check on Macro F1 improvement
        if re.search(r'\b(0\.3410|0\.2897)\b', text) and re.search(r'\b(significantly\s+(?:improved|better|outperformed))\b', text, re.IGNORECASE):
            if not re.search(r'\b(p\s*<|p-value|t-test|wilcoxon|statistically\s+significant\s+at)\b', text, re.IGNORECASE):
                issues.append({
                    "type": "unsupported_statistical_significance",
                    "severity": "medium",
                    "matched_text": text[:120],
                    "issue": "Claim of 'significant improvement' from 0.2897 baseline to 0.3410 requires documented statistical hypothesis test.",
                    "recommended_action": "State empirical gain as observed baseline improvement or provide test p-value."
                })

        return issues

    @classmethod
    def generate_author_questions(cls, text: str, section_id: str = "General") -> List[Dict[str, str]]:
        """
        Generates contextual author clarification questions tied to specific claims
        in the QuantLens-XAI report to assist the author in evidence-grounded revision.
        """
        questions = []

        # Question on F1 Score & Baseline
        if re.search(r'\b0\.3410\b', text) or re.search(r'\b0\.2897\b', text):
            questions.append({
                "topic": "Empirical Benchmark Run",
                "question": "Which experimental run or training seed produced the Macro F1 score of 0.3410 vs the 0.2897 baseline?",
                "suggested_evidence": "PyTorch evaluation test-set benchmark log or terminal run output"
            })

        # Question on SHAP vs LIME
        if "shap" in text.lower() and "lime" in text.lower():
            questions.append({
                "topic": "XAI Agreement & Disagreement",
                "question": "What did you observe when comparing SHAP with LIME across temporal feature attributions?",
                "suggested_evidence": "Attribution correlation plot or feature ranking table"
            })

        # Question on Lookback Window
        if re.search(r'\b30[- ]bar\b', text, re.IGNORECASE) or re.search(r'\blookback\b', text, re.IGNORECASE):
            questions.append({
                "topic": "Temporal Window Parameter",
                "question": "Why did you choose a 30-bar temporal lookback window for the 1D CNN architecture?",
                "suggested_evidence": "Ablation experiment comparing different lookback windows (e.g. 10, 30, 60 bars)"
            })

        # Question on Feature Filtering (22 to 6 features)
        if re.search(r'\b6\s+features\b', text, re.IGNORECASE) or re.search(r'\b22\s+features\b', text, re.IGNORECASE):
            questions.append({
                "topic": "Feature Selection & Latency",
                "question": "Did the model's inference throughput or classification accuracy change after filtering from 22 down to 6 features?",
                "suggested_evidence": "Feature importance ranking table and batch latency measurement (14.5 ms)"
            })

        # Question on Causality vs Attribution
        if re.search(r'\b(causality|causal|causes)\b', text, re.IGNORECASE):
            questions.append({
                "topic": "Scientific Attribution Clarification",
                "question": "Does this perturbation experiment establish real-world financial market causation, or feature sensitivity within your trained model?",
                "suggested_evidence": "Controlled perturbation methodology notes"
            })

        return questions
