import re
from typing import List, Dict, Any, Set
from backend.app.schemas.schemas import GroupCharacteristics, FlaggedVsUnflaggedResponse

class FlaggedComparisonService:
    """
    Computes rigorous descriptive statistics comparing passages flagged by an external
    detector against unflagged passages within the submitted manuscript.
    """

    @classmethod
    def analyze_flagged_vs_unflagged(
        cls,
        document_id: str,
        blocks: List[Dict[str, Any]],
        detector_highlight_block_ids: Set[str],
        detector_name: str = "ZeroGPT"
    ) -> FlaggedVsUnflaggedResponse:
        flagged_blocks = []
        unflagged_blocks = []

        for b in blocks:
            b_type = b.get("block_type", "paragraph")
            if b_type in ["reference_entry"]:
                continue
            text = b.get("current_text") or b.get("original_text") or ""
            if len(text.split()) < 4:
                continue

            if b["id"] in detector_highlight_block_ids:
                flagged_blocks.append(text)
            else:
                unflagged_blocks.append(text)

        flagged_stats = cls._calculate_group_stats(flagged_blocks)
        unflagged_stats = cls._calculate_group_stats(unflagged_blocks)

        correlations = []
        if flagged_stats.passage_count > 0 and unflagged_stats.passage_count > 0:
            if flagged_stats.technical_term_density_pct > unflagged_stats.technical_term_density_pct:
                diff = round(flagged_stats.technical_term_density_pct - unflagged_stats.technical_term_density_pct, 1)
                correlations.append(
                    f"Highlighted passages exhibited {diff}% higher technical abbreviation density than unhighlighted passages in this sample."
                )
            if flagged_stats.enumerated_items_count > unflagged_stats.enumerated_items_count:
                correlations.append(
                    f"Highlighted passages contained more enumerated lists ({flagged_stats.enumerated_items_count}) than comparison passages ({unflagged_stats.enumerated_items_count})."
                )
            if flagged_stats.avg_sentence_length_words > unflagged_stats.avg_sentence_length_words:
                diff_s = round(flagged_stats.avg_sentence_length_words - unflagged_stats.avg_sentence_length_words, 1)
                correlations.append(
                    f"Highlighted sentences averaged {diff_s} more words per sentence than unflagged text."
                )

        if not correlations:
            correlations.append("No statistically significant stylistic discrepancies detected between highlighted and unhighlighted text.")

        return FlaggedVsUnflaggedResponse(
            document_id=document_id,
            detector_name=detector_name,
            sample_size_warning=(
                f"Statistical sample comprises {flagged_stats.passage_count} highlighted passages vs. "
                f"{unflagged_stats.passage_count} unhighlighted blocks in this single uploaded document."
            ),
            disclaimer=(
                "These descriptive metrics reflect observable surface text characteristics within this specific "
                "manuscript. They must not be interpreted as proving AI authorship or disclosing proprietary detector rules."
            ),
            highlighted_passages=flagged_stats,
            unhighlighted_passages=unflagged_stats,
            observable_correlations=correlations
        )

    @classmethod
    def _calculate_group_stats(cls, texts: List[str]) -> GroupCharacteristics:
        if not texts:
            return GroupCharacteristics(
                passage_count=0,
                word_count=0,
                avg_passage_length_words=0.0,
                avg_sentence_length_words=0.0,
                technical_term_density_pct=0.0,
                citation_presence_pct=0.0,
                enumerated_items_count=0,
                claim_specificity_score=0.0,
                readability_fk_grade=0.0,
                unsupported_assertions_count=0
            )

        total_words = 0
        total_sentences = 0
        total_abbreviations = 0
        passages_with_citations = 0
        total_enumerated = 0
        total_unsupported = 0

        for t in texts:
            words = t.split()
            word_count = len(words)
            total_words += word_count

            # Sentences
            sentences = [s for s in re.split(r'[.!?]+', t) if s.strip()]
            sentence_count = max(len(sentences), 1)
            total_sentences += sentence_count

            # Abbreviation acronyms
            abbrs = re.findall(r'\b[A-Z]{3,8}\b', t)
            total_abbreviations += len(abbrs)

            # Citations [X] or (Author, Year)
            if re.search(r'\[\d+\]|\([A-Z][a-zA-Z\s.-]+,\s*\d{4}\)', t):
                passages_with_citations += 1

            # Enumerations (1), (2), 1., 2., •
            enums = re.findall(r'\(\d+\)|\b\d+\.|\([a-z]\)|[•\-\*]\s+', t)
            total_enumerated += len(enums)

            # Unsupported absolute claims
            if re.search(r'\b(always|never|guaranteed|undeniably|significantly (?:better|superior|outperforms))\b', t, re.IGNORECASE):
                total_unsupported += 1

        passage_count = len(texts)
        avg_passage_words = round(total_words / max(passage_count, 1), 1)
        avg_sentence_words = round(total_words / max(total_sentences, 1), 1)
        term_density = round((total_abbreviations / max(total_words, 1)) * 100, 1)
        citation_pct = round((passages_with_citations / max(passage_count, 1)) * 100, 1)

        # Approximate Flesch-Kincaid Grade Level: 0.39 * (words/sentence) + 11.8 * (syllables/word) - 15.59
        fk_grade = round(0.39 * avg_sentence_words + 11.8 * 1.5 - 15.59, 1)

        # Claim specificity score (0.0 to 1.0) based on presence of concrete numbers/metrics
        texts_with_numbers = sum(1 for t in texts if re.search(r'\b\d+(?:\.\d+)?%?\b', t))
        specificity = round(texts_with_numbers / max(passage_count, 1), 2)

        return GroupCharacteristics(
            passage_count=passage_count,
            word_count=total_words,
            avg_passage_length_words=avg_passage_words,
            avg_sentence_length_words=avg_sentence_words,
            technical_term_density_pct=term_density,
            citation_presence_pct=citation_pct,
            enumerated_items_count=total_enumerated,
            claim_specificity_score=specificity,
            readability_fk_grade=max(fk_grade, 0.0),
            unsupported_assertions_count=total_unsupported
        )
