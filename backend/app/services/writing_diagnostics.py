import re
from typing import List, Dict, Any, Tuple, Set, Optional

# Regex compilations for linguistic patterns
GENERIC_AI_PATTERNS = [
    re.compile(r'\b(artificial intelligence|machine learning|deep learning)\s+(?:has revolutionized|has transformed|plays a vital role in|is increasingly being used in)\b', re.IGNORECASE),
    re.compile(r'\b(in recent years|recently|nowadays|in modern times),?\s+(?:there has been|researchers have focused on|the widespread adoption of)\b', re.IGNORECASE),
    re.compile(r'\b(greatly improves?|significantly boosts?|dramatically enhances?)\s+(?:performance|accuracy|efficiency)\b', re.IGNORECASE),
]

ABSOLUTE_CERTAINTY_PATTERNS = [
    (re.compile(r'\b(always|never|guaranteed|undeniably|indisputably|flawless|perfect)\b', re.IGNORECASE), "Categorical certainty assertion without documented bounds."),
    (re.compile(r'\b(is proven to|has been conclusively proven that)\b', re.IGNORECASE), "Proof claim in empirical computing requires mathematical derivation or comprehensive verification."),
    (re.compile(r'\b(the first (?:to|architecture|framework|system))\b', re.IGNORECASE), "Novelty precedence claim ('the first') requires documented prior art and literature benchmarking."),
    (re.compile(r'\b(significantly (?:outperforms?|better|superior|higher|lower))\b', re.IGNORECASE), "Statistical significance claim requires documented statistical hypothesis test (e.g., paired t-test or Wilcoxon test with p-value)."),
]

PROMOTIONAL_TONE_PATTERNS = [
    re.compile(r'\b(groundbreaking|revolutionary|miraculous|unprecedented|game-changing|astonishing)\b', re.IGNORECASE),
]

CAUSALITY_CONFUSION_PATTERNS = [
    (re.compile(r'\b(SHAP|LIME|feature attributions?)\s+(?:proves?|causes?|reveals? real-world causality|establishes? causal relationships?)\b', re.IGNORECASE),
     "Feature attribution (SHAP/LIME) quantifies model decision sensitivity, not real-world economic or market causality."),
    (re.compile(r'\b(Grad-CAM|saliency maps?)\s+(?:proves? causality|causes? the market)\b', re.IGNORECASE),
     "Temporal Grad-CAM identifies activation gradients in convolutional layers, representing model visual/temporal saliency rather than real-world causal drivers."),
    (re.compile(r'\bconfidence\s+(?:equals?|is equivalent to)\s+calibration\b', re.IGNORECASE),
     "Model output softmax probability represents decision confidence, which must be calibrated separately via expected calibration error (ECE)."),
]

QUANTLENS_REGULATORY_PATTERNS = [
    (re.compile(r'MiFID\s*II\s*(?:RTS\s*25)?', re.IGNORECASE),
     "Verify regulatory context: MiFID II RTS 25 establishes strict business clock synchronization standards (microsecond accuracy), whereas SEC Rule 15c3-5 mandates pre-trade risk controls and capital limits."),
]

class WritingDiagnosticsEngine:
    """
    Executes the 12 comprehensive independent writing diagnostic modules
    plus the specialized QuantLens-XAI technical verification rules.
    """

    @classmethod
    def analyze_document_diagnostics(
        cls,
        blocks: List[Dict[str, Any]],
        detector_highlight_blocks: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        findings = []
        detector_blocks = detector_highlight_blocks or set()

        for b in blocks:
            b_id = b["id"]
            text = b.get("current_text") or b.get("original_text") or ""
            is_detector_flagged = b_id in detector_blocks
            b_type = b.get("block_type", "paragraph")

            # Skip pure reference entries or titles
            if b_type in ["reference_entry", "title"]:
                continue

            words = text.split()
            if len(words) < 5:
                continue

            # Run Module 1: Generic and underspecified claims
            cls._check_module_1_generic_claims(b, text, is_detector_flagged, findings)

            # Run Module 2: Unsupported certainty & significance claims
            cls._check_module_2_unsupported_certainty(b, text, is_detector_flagged, findings)

            # Run Module 3: Dense terminology & unexplained abbreviations
            cls._check_module_3_dense_terminology(b, text, is_detector_flagged, findings)

            # Run Module 4: Sentence readability & clause complexity
            cls._check_module_4_readability(b, text, is_detector_flagged, findings)

            # Run Module 7: Methodology specificity
            cls._check_module_7_methodology_specificity(b, text, is_detector_flagged, findings)

            # Run Module 8: Experimental claim verification
            cls._check_module_8_experimental_claims(b, text, is_detector_flagged, findings)

            # Run Module 10: Terminology consistency & Causality vs. Attribution
            cls._check_module_10_terminology_consistency(b, text, is_detector_flagged, findings)

            # Run Module 11: Original-contribution evidence
            cls._check_module_11_original_contributions(b, text, is_detector_flagged, findings)

            # Run Module 12: Academic clarity & promotional tone
            cls._check_module_12_clarity_and_tone(b, text, is_detector_flagged, findings)

            # Run Specialized QuantLens-XAI Verification Rules
            cls._check_quantlens_xai_rules(b, text, is_detector_flagged, findings)

        # Run Module 5: Repetition across document
        cls._check_module_5_repetition(blocks, detector_blocks, findings)

        # Run Module 6: Logical transitions between adjacent paragraphs
        cls._check_module_6_transitions(blocks, detector_blocks, findings)

        return findings

    @classmethod
    def _check_module_1_generic_claims(cls, block, text: str, is_detector: bool, findings: list):
        for pat in GENERIC_AI_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append({
                    "id": f"diag_m1_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "generic_claim",
                    "issue_category": "module_1_generic_claims",
                    "severity": "medium",
                    "external_detector_highlight": is_detector,
                    "matched_text": m.group(0),
                    "evidence": {
                        "passage": text[:140],
                        "issue": f"Generic claim ('{m.group(0)}') lacks empirical context, specific baseline comparisons, or citation.",
                    },
                    "required_evidence": ["Quantitative performance baseline", "Citation to domain survey"],
                    "recommended_action": "Clarify with specific domain metrics or ground with citation.",
                    "requires_author_input": True,
                    "review_status": "pending"
                })
                break

    @classmethod
    def _check_module_2_unsupported_certainty(cls, block, text: str, is_detector: bool, findings: list):
        has_stats_test = bool(re.search(r'\b(p\s*<\s*0\.0\d+|p-value|t-test|wilcoxon|f-statistic|confidence interval)\b', text, re.IGNORECASE))
        has_citation = bool(re.search(r'\[\d+\]|\([A-Z][a-zA-Z\s.-]+,\s*\d{4}\)', text))

        for pat, explanation in ABSOLUTE_CERTAINTY_PATTERNS:
            m = pat.search(text)
            if m:
                claim_word = m.group(1)
                # If it's a significance claim and has p-value, it's supported!
                if "significant" in claim_word.lower() and has_stats_test:
                    continue
                # If it's novelty and has citation, it's qualified
                if "first" in claim_word.lower() and has_citation:
                    continue

                findings.append({
                    "id": f"diag_m2_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "unsupported_certainty",
                    "issue_category": "module_2_unsupported_certainty",
                    "severity": "high" if "significant" in claim_word.lower() else "medium",
                    "external_detector_highlight": is_detector,
                    "matched_text": m.group(0),
                    "evidence": {
                        "term": claim_word,
                        "issue": explanation,
                    },
                    "required_evidence": ["Statistical significance test results" if "significant" in claim_word.lower() else "Literature benchmarking record"],
                    "recommended_action": "Qualify assertion or document significance test.",
                    "requires_author_input": True,
                    "review_status": "pending"
                })

    @classmethod
    def _check_module_3_dense_terminology(cls, block, text: str, is_detector: bool, findings: list):
        # Look for consecutive uppercase acronyms / abbreviations (e.g. SHAP, LIME, Grad-CAM, RTS, MiFID, ECE, AUC)
        abbreviations = re.findall(r'\b[A-Z]{3,8}\b', text)
        words = text.split()
        if len(words) >= 20 and len(abbreviations) >= 5:
            unique_abbr = set(abbreviations)
            density_ratio = len(abbreviations) / len(words)
            if density_ratio > 0.15:
                findings.append({
                    "id": f"diag_m3_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "dense_terminology",
                    "issue_category": "module_3_dense_terminology",
                    "severity": "low",
                    "external_detector_highlight": is_detector,
                    "matched_text": ", ".join(list(unique_abbr)[:5]),
                    "evidence": {
                        "abbreviation_count": len(abbreviations),
                        "unique_concepts": list(unique_abbr),
                        "density_pct": round(density_ratio * 100, 1),
                        "issue": f"High terminology density ({round(density_ratio * 100, 1)}% of words are acronyms). Ensure all abbreviations are defined on first mention.",
                    },
                    "required_evidence": ["Glossary or abbreviation definition"],
                    "recommended_action": "Verify abbreviations are defined on first use.",
                    "requires_author_input": False,
                    "review_status": "pending"
                })

    @classmethod
    def _check_module_4_readability(cls, block, text: str, is_detector: bool, findings: list):
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for s in sentences:
            s_words = s.split()
            if len(s_words) > 38:
                # Excessively long sentence with potential coordination overload
                findings.append({
                    "id": f"diag_m4_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "sentence_complexity",
                    "issue_category": "module_4_readability",
                    "severity": "low",
                    "external_detector_highlight": is_detector,
                    "matched_text": s[:120] + "...",
                    "evidence": {
                        "sentence_word_count": len(s_words),
                        "issue": f"Sentence contains {len(s_words)} words with multiple clauses. Breaking into focused sentences improves academic clarity.",
                    },
                    "required_evidence": [],
                    "recommended_action": "Split into two distinct, well-punctuated sentences.",
                    "requires_author_input": False,
                    "review_status": "pending"
                })
                break

    @classmethod
    def _check_module_5_repetition(cls, blocks: list, detector_blocks: set, findings: list):
        # Detect exact repeated sentences across distinct paragraphs
        seen_sentences = {}
        for b in blocks:
            b_text = b.get("current_text") or ""
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', b_text) if len(s.split()) >= 6]
            for s in sentences:
                norm_s = re.sub(r'\s+', ' ', s.lower())
                if norm_s in seen_sentences:
                    orig_b_id = seen_sentences[norm_s]
                    if orig_b_id != b["id"]:
                        findings.append({
                            "id": f"diag_m5_{b['id']}_{len(findings)}",
                            "document_id": b["document_id"],
                            "block_id": b["id"],
                            "finding_type": "repeated_passage",
                            "issue_category": "module_5_repetition",
                            "severity": "medium",
                            "external_detector_highlight": b["id"] in detector_blocks,
                            "matched_text": s,
                            "evidence": {
                                "issue": f"Passage is repeated verbatim from block '{orig_b_id}'. Redundant phrasing dilutes manuscript quality.",
                                "first_occurrence_block": orig_b_id
                            },
                            "required_evidence": [],
                            "recommended_action": "Consolidate repetition or replace with reference.",
                            "requires_author_input": True,
                            "review_status": "pending"
                        })
                else:
                    seen_sentences[norm_s] = b["id"]

    @classmethod
    def _check_module_6_transitions(cls, blocks: list, detector_blocks: set, findings: list):
        # Look for paragraphs in body that start abruptly without transitional phrase or topic context
        for i in range(1, len(blocks) - 1):
            curr = blocks[i]
            prev = blocks[i-1]
            if curr.get("block_type") == "paragraph" and prev.get("block_type") == "paragraph":
                curr_text = curr.get("current_text") or ""
                # If paragraph starts with 'Furthermore', 'Moreover', 'In addition' but previous paragraph was in different topic
                if re.match(r'^(Furthermore|Moreover|In addition|Consequently|Therefore),', curr_text):
                    prev_text = prev.get("current_text") or ""
                    # Check vocabulary overlap
                    curr_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', curr_text[:100].lower()))
                    prev_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', prev_text[-100:].lower()))
                    if len(curr_tokens.intersection(prev_tokens)) == 0:
                        findings.append({
                            "id": f"diag_m6_{curr['id']}_{len(findings)}",
                            "document_id": curr["document_id"],
                            "block_id": curr["id"],
                            "finding_type": "abrupt_transition",
                            "issue_category": "module_6_logical_transitions",
                            "severity": "low",
                            "external_detector_highlight": curr["id"] in detector_blocks,
                            "matched_text": curr_text[:60],
                            "evidence": {
                                "issue": "Transitional connective used without conceptual continuity from preceding paragraph.",
                            },
                            "required_evidence": [],
                            "recommended_action": "Introduce intermediate connective bridging the two distinct topics.",
                            "requires_author_input": False,
                            "review_status": "pending"
                        })

    @classmethod
    def _check_module_7_methodology_specificity(cls, block, text: str, is_detector: bool, findings: list):
        # For methodology section, check if implementation claims specify concrete parameters
        if "method" in block.get("section_id", "").lower() or "architecture" in block.get("section_id", "").lower():
            if re.search(r'\b(hyperparameters?|learning rate|batch size|epochs?)\b', text, re.IGNORECASE):
                # Check if numbers exist
                has_numbers = bool(re.search(r'\d+', text))
                if not has_numbers:
                    findings.append({
                        "id": f"diag_m7_{block['id']}_{len(findings)}",
                        "document_id": block["document_id"],
                        "block_id": block["id"],
                        "finding_type": "methodology_underspecified",
                        "issue_category": "module_7_methodology_specificity",
                        "severity": "medium",
                        "external_detector_highlight": is_detector,
                        "matched_text": text[:100],
                        "evidence": {
                            "issue": "Methodology mentions hyperparameters or training settings without reporting concrete numerical values.",
                        },
                        "required_evidence": ["Exact hyperparameter values, learning rate, and batch size"],
                        "recommended_action": "Provide specific hyperparameter settings.",
                        "requires_author_input": True,
                        "review_status": "pending"
                    })

    @classmethod
    def _check_module_8_experimental_claims(cls, block, text: str, is_detector: bool, findings: list):
        # Look for claims comparing models e.g. "improved Macro F1 from 0.2897 to 0.3410"
        m = re.search(r'\b(?:improved|increased|achieved)\s+(?:macro\s+)?F1(?:-score)?\s*(?:from\s+([0-9.]+)\s+to\s+([0-9.]+)|of\s+([0-9.]+))', text, re.IGNORECASE)
        if m:
            findings.append({
                "id": f"diag_m8_{block['id']}_{len(findings)}",
                "document_id": block["document_id"],
                "block_id": block["id"],
                "finding_type": "experimental_claim",
                "issue_category": "module_8_experimental_claims",
                "severity": "info",
                "external_detector_highlight": is_detector,
                "matched_text": m.group(0),
                "evidence": {
                    "metric_claim": m.group(0),
                    "issue": "Empirical metric improvement reported. Verifiable against project experiment logs and evaluation test partition.",
                },
                "required_evidence": ["Evaluation test set benchmark log", "Identical test partition confirmation"],
                "recommended_action": "Link to verified benchmark table.",
                "requires_author_input": False,
                "review_status": "verified"
            })

    @classmethod
    def _check_module_10_terminology_consistency(cls, block, text: str, is_detector: bool, findings: list):
        for pat, explanation in CAUSALITY_CONFUSION_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append({
                    "id": f"diag_m10_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "terminology_confusion",
                    "issue_category": "module_10_terminology_consistency",
                    "severity": "high",
                    "external_detector_highlight": is_detector,
                    "matched_text": m.group(0),
                    "evidence": {
                        "issue": explanation,
                    },
                    "required_evidence": ["Attribution vs. causality distinction phrasing"],
                    "recommended_action": "Clarify that attributions represent model decision sensitivity rather than empirical causal mechanisms.",
                    "requires_author_input": True,
                    "review_status": "pending"
                })

    @classmethod
    def _check_module_11_original_contributions(cls, block, text: str, is_detector: bool, findings: list):
        m = re.search(r'\b(our pointwise novel contributions|our primary novel contribution|we propose a novel)\b', text, re.IGNORECASE)
        if m:
            findings.append({
                "id": f"diag_m11_{block['id']}_{len(findings)}",
                "document_id": block["document_id"],
                "block_id": block["id"],
                "finding_type": "novel_contribution_claim",
                "issue_category": "module_11_original_contributions",
                "severity": "medium",
                "external_detector_highlight": is_detector,
                "matched_text": m.group(0),
                "evidence": {
                    "issue": "Author contribution claim identified. Requires supporting evidence (source code repository, implementation artifacts, or benchmark tables).",
                },
                "required_evidence": ["Source code repository", "Implementation artifact or benchmark logs"],
                "recommended_action": "Attach research implementation evidence in Evidence Review.",
                "requires_author_input": True,
                "review_status": "pending"
            })

    @classmethod
    def _check_module_12_clarity_and_tone(cls, block, text: str, is_detector: bool, findings: list):
        for pat in PROMOTIONAL_TONE_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append({
                    "id": f"diag_m12_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "promotional_tone",
                    "issue_category": "module_12_clarity_and_tone",
                    "severity": "low",
                    "external_detector_highlight": is_detector,
                    "matched_text": m.group(0),
                    "evidence": {
                        "issue": f"Promotional phrasing ('{m.group(0)}') is uncharacteristic of peer-reviewed academic manuscripts.",
                    },
                    "required_evidence": [],
                    "recommended_action": "Replace promotional adjective with objective empirical description.",
                    "requires_author_input": False,
                    "review_status": "pending"
                })

    @classmethod
    def _check_quantlens_xai_rules(cls, block, text: str, is_detector: bool, findings: list):
        # 1. Regulatory rule verification (MiFID II vs SEC Rule 15c3-5)
        for pat, explanation in QUANTLENS_REGULATORY_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append({
                    "id": f"diag_ql_reg_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "regulatory_description_audit",
                    "issue_category": "quantlens_xai_review",
                    "severity": "info",
                    "external_detector_highlight": is_detector,
                    "matched_text": m.group(0),
                    "evidence": {
                        "issue": explanation,
                    },
                    "required_evidence": ["Primary regulatory text reference (MiFID II RTS 25 / SEC 15c3-5)"],
                    "recommended_action": "Verify distinction between market-access risk controls and clock synchronization.",
                    "requires_author_input": False,
                    "review_status": "verified"
                })

        # 2. Grad-CAM temporal saliency vs tabular feature attribution
        if "grad-cam" in text.lower() and "temporal" in text.lower():
            if "1d" not in text.lower() and "cnn" not in text.lower() and "convolution" not in text.lower():
                findings.append({
                    "id": f"diag_ql_gradcam_{block['id']}_{len(findings)}",
                    "document_id": block["document_id"],
                    "block_id": block["id"],
                    "finding_type": "gradcam_architecture_precision",
                    "issue_category": "quantlens_xai_review",
                    "severity": "medium",
                    "external_detector_highlight": is_detector,
                    "matched_text": "Grad-CAM temporal",
                    "evidence": {
                        "issue": "Grad-CAM applied to time series requires convolutional activations (e.g. 1D CNN). Explicitly clarify the convolutional architecture.",
                    },
                    "required_evidence": ["TimeSeriesConv1D architecture specification"],
                    "recommended_action": "Clarify that Grad-CAM operates on 1D convolutional feature maps.",
                    "requires_author_input": True,
                    "review_status": "pending"
                })
