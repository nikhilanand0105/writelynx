import re
import string
from typing import List, Dict, Any, Tuple, Optional
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

COMMON_ACADEMIC_PHRASES = {
    "in this paper we propose",
    "in this paper, we propose",
    "the remainder of this paper is organized as follows",
    "to the best of our knowledge",
    "experimental results demonstrate that",
    "state of the art",
    "state-of-the-art",
    "deep learning",
    "neural networks",
    "convolutional neural network",
    "machine learning algorithms",
    "future work will focus on",
    "as shown in figure",
    "as shown in table",
    "the results are summarized in",
    "cross entropy loss",
    "natural language processing",
    "computer vision",
    "support vector machine",
    "random forest classifier",
}

class SimilarityEngine:
    """
    Evidence-based local textual overlap analyzer comparing documents against
    explicitly indexed reference sources.
    """

    def __init__(self, ngram_size: int = 5, fuzzy_threshold: float = 75.0):
        self.ngram_size = ngram_size
        self.fuzzy_threshold = fuzzy_threshold

    @staticmethod
    def normalize_text(text: str) -> str:
        """Lowercases and cleans whitespace for consistent n-gram matching."""
        text = text.lower()
        # remove punctuation
        text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
        tokens = text.split()
        return ' '.join(tokens)

    def extract_ngrams(self, text: str, n: Optional[int] = None) -> List[str]:
        n = n or self.ngram_size
        tokens = self.normalize_text(text).split()
        if len(tokens) < n:
            return [' '.join(tokens)] if tokens else []
        return [' '.join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]

    def analyze_document_against_sources(
        self,
        blocks: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Compare each document block with all provided reference sources.
        Returns (findings, diagnostic_metrics).
        """
        findings = []
        total_document_words = 0
        exact_matched_words = 0
        approximate_match_count = 0
        matching_passages_count = 0
        missing_citations_count = 0
        unattributed_overlap_count = 0

        # Build corpus of sources for TF-IDF candidate retrieval
        source_records = []
        for s in sources:
            source_text = s.get("extracted_text") or ""
            if not source_text.strip():
                continue
            # Break source into paragraphs/sentences for fine-grained matching
            paragraphs = [p.strip() for p in source_text.split("\n\n") if len(p.strip().split()) >= 4]
            if not paragraphs:
                paragraphs = [p.strip() for p in source_text.split("\n") if len(p.strip().split()) >= 4]
            for p_idx, para in enumerate(paragraphs):
                source_records.append({
                    "source_id": s["id"],
                    "source_title": s["title"],
                    "para_index": p_idx,
                    "text": para,
                    "norm_text": self.normalize_text(para),
                    "ngrams": set(self.extract_ngrams(para, self.ngram_size)),
                })

        # Calculate total doc words
        for b in blocks:
            text = b.get("current_text", "")
            words = len(text.split())
            total_document_words += words

        # If no sources provided, return empty findings with zero metrics
        if not source_records:
            metrics = {
                "total_document_words": total_document_words,
                "analyzed_sources_count": len(sources),
                "matching_passages_count": 0,
                "exact_match_words": 0,
                "approximate_match_count": 0,
                "missing_citations_count": 0,
                "unattributed_overlap_count": 0,
                "reviewed_findings_count": 0,
                "unresolved_findings_count": 0,
                "local_textual_overlap_percentage": 0.0,
            }
            return findings, metrics

        # TF-IDF candidate retriever across source paragraphs
        tfidf_docs = [r["norm_text"] for r in source_records]
        vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
        try:
            source_matrix = vectorizer.fit_transform(tfidf_docs)
        except Exception:
            source_matrix = None

        # Analyze each block
        for b in blocks:
            block_type = b.get("block_type", "paragraph")
            # Don't flag table headers or pure references as plagiarism
            if block_type in ["reference_entry"]:
                continue

            text = b.get("current_text", "").strip()
            if len(text.split()) < 4:
                continue

            norm_text = self.normalize_text(text)
            block_ngrams = set(self.extract_ngrams(text, self.ngram_size))
            has_citation = bool(re.search(r'\[\s*\d+\s*\]|\([A-Z][a-zA-Z\s.-]+,\s*\d{4}\)', text))
            is_quoted = bool(re.search(r'["“][^"”]{8,}["”]', text))

            # Check if text is just common academic phrasing
            is_common = any(phrase in norm_text for phrase in COMMON_ACADEMIC_PHRASES)

            best_match: Optional[Dict[str, Any]] = None
            best_score = 0.0
            match_type = "exact"
            matched_segment = ""
            source_segment = ""

            # 1. Exact N-Gram Matching
            if block_ngrams:
                for s_rec in source_records:
                    common_ngrams = block_ngrams.intersection(s_rec["ngrams"])
                    if common_ngrams:
                        ngram_overlap_ratio = len(common_ngrams) / max(len(block_ngrams), 1)
                        if ngram_overlap_ratio > 0.4 or len(common_ngrams) >= 3:
                            score = float(ngram_overlap_ratio) * 100.0
                            if score > best_score:
                                best_score = score
                                best_match = s_rec
                                match_type = "exact"
                                matched_segment = list(common_ngrams)[0]
                                source_segment = s_rec["text"]

            # 2. Fuzzy lexical similarity if no high exact match
            if best_score < 70.0 and source_matrix is not None:
                try:
                    q_vec = vectorizer.transform([norm_text])
                    cos_sims = cosine_similarity(q_vec, source_matrix)[0]
                    top_indices = cos_sims.argsort()[-3:][::-1]
                    for idx in top_indices:
                        if cos_sims[idx] > 0.25:
                            candidate = source_records[idx]
                            # Use RapidFuzz token_set_ratio
                            fuzz_score = fuzz.token_set_ratio(text, candidate["text"])
                            if fuzz_score >= self.fuzzy_threshold and fuzz_score > best_score:
                                best_score = fuzz_score
                                best_match = candidate
                                match_type = "fuzzy"
                                matched_segment = text
                                source_segment = candidate["text"]
                except Exception:
                    pass

            # Classify finding if match meets threshold
            if best_match and best_score >= 50.0:
                matching_passages_count += 1
                words_in_block = len(text.split())

                # Classification taxonomy
                is_mostly_common_phrase = is_common and any(p in norm_text for p in COMMON_ACADEMIC_PHRASES)
                if is_mostly_common_phrase and (best_score < 95.0 or len(text.split()) < 15):
                    category = "common_terminology"
                    severity = "info"
                elif is_quoted and has_citation:
                    category = "cited_quote"
                    severity = "low"
                elif is_quoted and not has_citation:
                    category = "direct_quote"
                    severity = "high"
                    missing_citations_count += 1
                elif has_citation:
                    category = "cited_paraphrase"
                    severity = "low"
                else:
                    category = "unattributed_overlap"
                    severity = "high" if best_score > 75.0 else "medium"
                    unattributed_overlap_count += 1
                    missing_citations_count += 1

                if category != "common_terminology":
                    if match_type == "exact":
                        exact_matched_words += int(words_in_block * (best_score / 100.0))
                    else:
                        approximate_match_count += 1

                finding_id = f"find_{b['id']}_{len(findings)}"
                findings.append({
                    "id": finding_id,
                    "document_id": b["document_id"],
                    "block_id": b["id"],
                    "source_id": best_match["source_id"],
                    "finding_type": category,
                    "severity": severity,
                    "matched_text": matched_segment or text[:120],
                    "source_matched_text": source_segment[:200],
                    "similarity_score": round(best_score / 100.0, 2),
                    "match_type": match_type,
                    "evidence": {
                        "source_title": best_match["source_title"],
                        "score_percentage": round(best_score, 1),
                        "has_citation": has_citation,
                        "is_quoted": is_quoted,
                        "classification": category,
                        "explanation": f"Matched text against '{best_match['source_title']}' with {round(best_score, 1)}% {match_type} overlap."
                    },
                    "review_status": "pending"
                })

        overlap_pct = (exact_matched_words / max(total_document_words, 1)) * 100.0

        metrics = {
            "total_document_words": total_document_words,
            "analyzed_sources_count": len(sources),
            "matching_passages_count": matching_passages_count,
            "exact_match_words": exact_matched_words,
            "approximate_match_count": approximate_match_count,
            "missing_citations_count": missing_citations_count,
            "unattributed_overlap_count": unattributed_overlap_count,
            "reviewed_findings_count": 0,
            "unresolved_findings_count": len(findings),
            "local_textual_overlap_percentage": round(min(overlap_pct, 100.0), 1),
        }

        return findings, metrics
