"""Conservative fragment alignment with explicit ambiguous candidates."""
import re
import unicodedata
from typing import Any, Dict, List, Tuple
from rapidfuzz import fuzz


class DocxAligner:
    @staticmethod
    def normalize_str(text: str) -> str:
        text = unicodedata.normalize('NFKC', text).replace('\u00ad', '')
        text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)
        return re.sub(r'\s+', ' ', text).strip().casefold()

    @classmethod
    def align_highlights_with_blocks(cls, highlights: List[Dict[str, Any]], blocks: List[Dict[str, Any]],
                                     min_confidence_threshold: float = .90) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        # Never silently lower the automatic acceptance bar via a permissive caller.
        threshold = max(.90, min_confidence_threshold)
        indexed = []
        for block in blocks:
            # Detector reports concern the submitted original, not accepted edits made later.
            raw = block.get('original_text') if block.get('original_text') is not None else block.get('current_text', '')
            norm = cls.normalize_str(raw)
            if norm:
                indexed.append({**block, 'norm': norm, 'raw': raw})
        results = []
        for highlight in highlights:
            norm = cls.normalize_str(highlight.get('highlight_text', ''))
            candidates = []
            if len(norm) >= 8:
                for block in indexed:
                    target = block['norm']
                    if norm in target:
                        score, method = 1.0, 'exact_substring'
                    else:
                        # Ordered character matching avoids bag-of-words equivalence and tiny-block containment.
                        alignment = fuzz.partial_ratio_alignment(norm, target)
                        score = alignment.score / 100
                        if len(norm) > len(target):
                            score *= min(1, len(target) / len(norm))
                        method = 'fuzzy_fragment'
                    if score >= .65:
                        candidates.append({'block_id': block['id'], 'confidence': round(score, 4),
                                           'preview': block['raw'][:180], 'alignment_method': method,
                                           'block_index': block.get('block_index', 0)})
            candidates.sort(key=lambda c: (-c['confidence'], c['block_index']))
            best = candidates[0] if candidates else None
            unique = best and (len(candidates) == 1 or best['confidence'] - candidates[1]['confidence'] >= .08)
            enough_text = len(norm.split()) >= 3 or len(norm) >= 20
            reliable = bool(best and best['confidence'] >= threshold and unique and enough_text)
            status = 'matched' if reliable else ('ambiguous' if best and best['confidence'] >= threshold else 'unresolved')
            metadata = dict(highlight.get('metadata_json') or {})
            metadata.update({'candidate_blocks': candidates[:5], 'alignment_method': best['alignment_method'] if best else None,
                             'alignment_review_required': not reliable, 'alignment_text_basis': 'original'})
            results.append({**highlight, 'block_id': best['block_id'] if reliable else None,
                            'match_confidence': best['confidence'] if best else 0.0, 'mapping_status': status,
                            'alignment_method': best['alignment_method'] if best else None,
                            'candidate_blocks': candidates[:5], 'metadata_json': metadata})
        # Use two independently resolved neighboring passages to disambiguate repeated headings.
        # A single earlier anchor cannot distinguish repeated paragraphs reliably.
        positions = {b['id']: b.get('block_index', 0) for b in indexed}
        anchors = [(i, positions[h['block_id']]) for i, h in enumerate(results) if h['mapping_status'] == 'matched']
        for i, result in enumerate(results):
            if result['mapping_status'] != 'ambiguous':
                continue
            before = [a for a in anchors if a[0] < i]
            after = [a for a in anchors if a[0] > i]
            if not before or not after:
                continue
            lower, upper = before[-1][1], after[0][1]
            candidates = [c for c in result['candidate_blocks'] if lower <= c['block_index'] <= upper and c['confidence'] >= threshold]
            if lower <= upper and len(candidates) == 1:
                chosen = candidates[0]
                result.update(block_id=chosen['block_id'], mapping_status='matched', alignment_method='neighbor_context', match_confidence=.94)
                result['metadata_json'].update(alignment_method='neighbor_context', alignment_review_required=False,
                                               context_anchor_indices=[lower, upper])
        matched = [h for h in results if h['mapping_status'] == 'matched']
        return results, {'total_highlights': len(results), 'matched_highlights': len(matched),
                         'unresolved_highlights': len(results) - len(matched),
                         'ambiguous_highlights': sum(h['mapping_status'] == 'ambiguous' for h in results),
                         'matched_blocks_count': len({h['block_id'] for h in matched}),
                         'alignment_rate_pct': round(100 * len(matched) / max(1, len(results)), 1),
                         'coverage_notice': 'Alignment rate concerns extracted highlights only; it is not manuscript coverage.'}
