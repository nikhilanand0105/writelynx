import re
from typing import Dict, Any, Optional
from backend.app.providers.base import BaseLLMProvider
from backend.app.services.fact_validator import FactValidator
from backend.app.services.quantlens_validator import QuantLensValidator

# High-frequency academic wordiness and clarity replacements
MINIMAL_REPLACEMENTS = [
    (r'\bin order to\b', 'to'),
    (r'\bdue to the fact that\b', 'because'),
    (r'\ba large number of\b', 'many'),
    (r'\butilize\b', 'use'),
    (r'\butilized\b', 'used'),
    (r'\butilizing\b', 'using'),
    (r'\bat this point in time\b', 'currently'),
    (r'\bhas the capability to\b', 'can'),
    (r'\bhas the potential to\b', 'may'),
    (r'\bit is important to note that\b', 'notably,'),
    (r'\ba majority of\b', 'most'),
]

ACADEMIC_CLARITY_REPLACEMENTS = [
    (r'\ba lot of\b', 'numerous'),
    (r'\bvery good\b', 'favorable'),
    (r'\bgot worse\b', 'deteriorated'),
    (r'\bshowed up\b', 'emerged'),
    (r'\bbad results\b', 'suboptimal performance'),
    (r'\bbig difference\b', 'substantial disparity'),
    (r'\ba bit of\b', 'marginal'),
    (r'\blots of\b', 'substantial'),
    (r'\bkind of\b', 'somewhat'),
    (r'\bthings\b', 'factors'),
]

class NoLLMProvider(BaseLLMProvider):
    """
    Local deterministic academic writing assistant that runs completely offline
    with 0 API keys and 0 cloud dependencies.
    """

    async def test_connection(self) -> bool:
        return True

    async def generate_suggestion(
        self,
        block_id: str,
        original_text: str,
        context: str,
        mode: str,
        matched_source_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        text = original_text.strip()
        if len(text.split()) < 4:
            return None

        revised_text = text
        reason = ""
        issue_type = mode

        if mode in ("minimal", "proofreading", "light_copyediting"):
            for pat, repl in MINIMAL_REPLACEMENTS:
                if re.search(pat, revised_text, re.IGNORECASE):
                    revised_text = re.sub(pat, repl, revised_text, flags=re.IGNORECASE)
                    reason = "Streamlined wordy phrasing and improved conciseness."
            if revised_text == text:
                return None

        elif mode in ("clarity", "academic_revision", "natural_academic"):
            # Apply both minimal and academic clarity enhancements
            applied_reasons = []
            for pat, repl in MINIMAL_REPLACEMENTS:
                if re.search(pat, revised_text, re.IGNORECASE):
                    revised_text = re.sub(pat, repl, revised_text, flags=re.IGNORECASE)
                    applied_reasons.append("eliminated wordiness")
            for pat, repl in ACADEMIC_CLARITY_REPLACEMENTS:
                if re.search(pat, revised_text, re.IGNORECASE):
                    revised_text = re.sub(pat, repl, revised_text, flags=re.IGNORECASE)
                    applied_reasons.append("elevated to standard academic terminology")

            # Passive voice tightening check
            if re.search(r'\b(was conducted by us|was analyzed by the researchers)\b', revised_text, re.IGNORECASE):
                revised_text = re.sub(r'\bwas conducted by us\b', 'we conducted', revised_text, flags=re.IGNORECASE)
                revised_text = re.sub(r'\bwas analyzed by the researchers\b', 'the researchers analyzed', revised_text, flags=re.IGNORECASE)
                applied_reasons.append("converted awkward passive construct to active academic voice")

            if applied_reasons:
                reason = "Improved academic clarity: " + ", ".join(applied_reasons) + "."
            else:
                return None

        elif mode in ("natural_student_research", "evidence_review", "research_grounded"):
            # Natural Student Research Writing Mode:
            # Replaces promotional hype, tempers absolute claims, removes wordiness,
            # and emphasizes direct, authentic academic voice based on real implementation.
            applied_reasons = []

            # 1. Eliminate promotional buzzwords
            promo_subs = [
                (r'\b(groundbreaking|revolutionary|miraculous|unprecedented|game-changing)\b', 'novel', 'tempered promotional hype'),
                (r'\binstitutional-grade\b', 'production-tested', 'regrounded commercial claim'),
                (r'\bcompletely reliable\b', 'empirically tested', 'avoided absolute claim'),
                (r'\bhighly advanced\b', 'specialized', 'used precise technical descriptor'),
                (r'\bproves conclusively that\b', 'demonstrates that', 'avoided overconfident proof claim'),
                (r'\bestablishes real-world market causality\b', 'identifies temporal feature saliency', 'clarified attribution vs causality'),
                (r'\bno existing research has examined\b', 'prior benchmarks have rarely explored', 'qualified literature novelty assertion'),
            ]
            for pat, repl, reason_desc in promo_subs:
                if re.search(pat, revised_text, re.IGNORECASE):
                    revised_text = re.sub(pat, repl, revised_text, flags=re.IGNORECASE)
                    applied_reasons.append(reason_desc)

            # 2. Direct concise phrasing over wordiness
            for pat, repl in MINIMAL_REPLACEMENTS:
                if re.search(pat, revised_text, re.IGNORECASE):
                    revised_text = re.sub(pat, repl, revised_text, flags=re.IGNORECASE)
                    applied_reasons.append("streamlined phrasing")

            # 3. Active student research voice
            if re.search(r'\b(was conducted by us|was analyzed by the researchers)\b', revised_text, re.IGNORECASE):
                revised_text = re.sub(r'\bwas conducted by us\b', 'we conducted', revised_text, flags=re.IGNORECASE)
                revised_text = re.sub(r'\bwas analyzed by the researchers\b', 'we analyzed', revised_text, flags=re.IGNORECASE)
                applied_reasons.append("clarified author agency")

            if applied_reasons:
                reason = "Natural student research writing: " + ", ".join(applied_reasons) + "."
            else:
                return None

        elif mode == "substantive":
            # Recommend specifying experimental context or limitations if sweeping claims exist
            if re.search(r'\b(the best|perfect|completely solved|undeniably)\b', text, re.IGNORECASE):
                reason = "Temper categorical assertion; consider specifying implementation constraints or baseline comparisons."
                revised_text = re.sub(r'\bthe best\b', 'the leading observed', text, flags=re.IGNORECASE)
                revised_text = re.sub(r'\bcompletely solved\b', 'substantially addressed', revised_text, flags=re.IGNORECASE)
                revised_text = re.sub(r'\bundeniably\b', 'empirically', revised_text, flags=re.IGNORECASE)
            else:
                return None

        elif mode == "source_grounded":
            if matched_source_text:
                # If passage overlaps with source, recommend quotation encapsulation or clear attribution
                if not re.search(r'["“]', text):
                    revised_text = f'As noted in prior work, "{text.rstrip(".")}".'
                    reason = "Encapsulated overlapping verbatim passage in direct quotation with attribution framing."
                else:
                    return None
            else:
                return None

        # Verify fact preservation
        facts_ok, violations = FactValidator.compare_facts(original_text, revised_text)
        ql_ok, ql_violations = QuantLensValidator.validate_facts(original_text, revised_text)
        if not (facts_ok and ql_ok):
            # If our heuristic accidentally altered a protected fact or metric, discard the suggestion
            return None

        return {
            "block_id": block_id,
            "issue_type": issue_type,
            "original_text": original_text,
            "proposed_text": revised_text,
            "reason": reason,
            "citations_preserved": True,
            "protected_entities_preserved": True,
            "requires_user_review": True,
            "confidence": 0.95
        }
