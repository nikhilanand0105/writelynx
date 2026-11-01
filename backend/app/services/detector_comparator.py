"""Compare observed report data without inferring unpublished vendor behavior."""
from pathlib import Path
from typing import Any, Dict, List
from rapidfuzz import fuzz
from backend.app.services.pdf_highlight_extractor import PDFHighlightExtractor
from backend.app.services.docx_aligner import DocxAligner


class DetectorComparator:
    DISCLAIMER = ('Imported highlights are third-party judgments, not proof of AI authorship. '
                  'Score differences are not evidence of better writing. Submitted text, evaluated scope, '
                  'and service version must be established before interpreting score changes.')

    @classmethod
    def extract_granular_fragments(cls, pdf_path: Path) -> List[Dict[str, Any]]:
        report = PDFHighlightExtractor.extract_highlights(pdf_path, merge_lines=False)
        return cls._fragments(report)

    @staticmethod
    def _fragments(report):
        return [{'id': h['id'], 'page_number': h['page_number'], 'text': h['highlight_text'],
                 'bbox': h['bbox'], 'word_count': len(h['highlight_text'].split()),
                 'extraction_method': h['extraction_strategy'], 'confidence': h['confidence']}
                for h in report['highlights']]

    @classmethod
    def compare_reports(cls, earlier_pdf_path: Path, latest_pdf_path: Path) -> Dict[str, Any]:
        reports = [PDFHighlightExtractor.extract_highlights(p, merge_lines=False) for p in (earlier_pdf_path, latest_pdf_path)]
        first, second = reports
        frags1, frags2 = [cls._fragments(r) for r in reports]
        unchanged, similar, matched2, matched1 = [], [], set(), set()
        # Exact normalized matches first; near matches are separately labelled because numbers may differ.
        for i, f1 in enumerate(frags1):
            norm = DocxAligner.normalize_str(f1['text'])
            found = next((j for j, f2 in enumerate(frags2) if j not in matched2 and DocxAligner.normalize_str(f2['text']) == norm), None)
            if found is not None:
                matched1.add(i); matched2.add(found)
                unchanged.append({'earlier_fragment': f1, 'latest_fragment': frags2[found],
                                  'similarity_ratio': 100.0, 'is_verbatim_identical': f1['text'] == frags2[found]['text']})
        for i, f1 in enumerate(frags1):
            if i in matched1:
                continue
            choices = [(fuzz.ratio(DocxAligner.normalize_str(f1['text']), DocxAligner.normalize_str(f['text'])), j)
                       for j, f in enumerate(frags2) if j not in matched2]
            if choices and max(choices)[0] >= 90:
                score, j = max(choices)
                similar.append({'earlier_fragment': f1, 'latest_fragment': frags2[j], 'similarity_ratio': round(score, 1),
                                'is_verbatim_identical': False, 'requires_review': True})
        removed = [f for i, f in enumerate(frags1) if i not in matched1]
        new = [f for j, f in enumerate(frags2) if j not in matched2]
        reasons, unknowns = [], []
        for key, label in [('detector_name', 'detector service'), ('analyzed_characters', 'analyzed character count'),
                           ('analyzed_words', 'analyzed word count'), ('service_version', 'service/model version')]:
            a, b = first.get(key), second.get(key)
            if a is None or b is None or a == 'Unknown' or b == 'Unknown':
                unknowns.append(f'{label.capitalize()} is not established in both reports.')
            elif a != b:
                reasons.append(f'The reports differ in {label}.')
        # Highlighted text alone cannot establish equality of the entire submitted input.
        identical_file = first['file_hash'] == second['file_hash']
        if not identical_file:
            unknowns.append('Complete submitted text equality cannot be established from highlighted fragments alone.')
        comparability = 'different_scope' if reasons else ('same_artifact' if identical_file else 'unverified')
        score_difference = None
        if first['detector_score'] is not None and second['detector_score'] is not None:
            score_difference = round(second['detector_score'] - first['detector_score'], 4)
        observed_same = bool(frags1 and frags2 and not removed and not new and score_difference == 0)
        if observed_same:
            conclusion = (f"Both reports show {first['detector_score']:g}% and the same extracted highlighted text. "
                          'The available reports do not demonstrate an improvement. Full input and service equivalence remain subject to the scope checks.')
        elif not frags1 or not frags2:
            conclusion = 'Highlight comparison is inconclusive because at least one report has no readable extracted highlights.'
        else:
            conclusion = 'The reports differ in extracted highlights or reported scores. These observations do not establish an improvement.'
        def public_meta(r, frags):
            return {'detector_name': r['detector_name'], 'reported_score': r['detector_score'],
                    'is_truncated': r['is_truncated'], 'total_fragments': len(frags),
                    'analyzed_characters': r['analyzed_characters'], 'analyzed_words': r['analyzed_words'],
                    'service_version': r['service_version'], 'extraction_notices': r['extraction_notices']}
        return {'earlier_report': public_meta(first, frags1), 'latest_report': public_meta(second, frags2),
                'comparison_summary': {'score_difference': score_difference, 'is_essentially_identical': observed_same,
                    'overlapping_fragments_count': len(unchanged),
                    'verbatim_identical_count': sum(m['is_verbatim_identical'] for m in unchanged),
                    'newly_highlighted_count': len(new), 'removed_highlighted_count': len(removed),
                    'both_truncated': first['is_truncated'] and second['is_truncated'], 'conclusion': conclusion,
                    'comparability': comparability, 'directly_comparable': identical_file and not reasons,
                    'scope_differences': reasons, 'scope_uncertainties': unknowns,
                    'submitted_text_status': 'identical_file' if identical_file else 'not_established'},
                'unchanged_highlights': unchanged, 'similar_highlights': similar,
                'newly_highlighted': new, 'removed_highlights': removed, 'disclaimer': cls.DISCLAIMER}
