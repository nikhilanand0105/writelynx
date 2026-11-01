"""Conservative local invariants: a passed check is preservation, not scientific verification."""
import re
from collections import Counter
from typing import Any, Dict, List, Tuple


class FactValidator:
    NUMBER = r'[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?%?'
    METRIC_PATTERN = re.compile(
        r'\b((?:(?:macro|micro|weighted|baseline|test|train|validation)\s+)?(?:F1(?:[- ]score)?|accuracy|precision|recall|AUC|ROC|BLEU|ROUGE|loss|perplexity|mAP|top-1|top-5|r2|RMSE|MAE))\s*(?:(?:score\s+)?(?:of|=|:|is|was|reached|achieved)\s*)?(' + NUMBER + ')', re.I)
    UNIT_PATTERN = re.compile('(' + NUMBER + r')\s*[- ]?\s*(ms|s|seconds?|minutes?|hours?|GB|MB|KB|GHz|MHz|epochs?|layers?|parameters?|tokens?|samples?|features?|bars?|days?|channels?|years?|%|kg|mV|V|USD)\b', re.I)
    CITATION_NUMERIC = re.compile(r'\[\s*\d+(?:\s*[,;–—-]\s*\d+)*\s*\]')
    CITATION_AUTHOR_YEAR = re.compile(r'\([A-Z][a-zA-Z\s.&;-]+,?\s*(?:19|20)\d{2}[a-z]?(?:\s*[,;]\s*(?:19|20)\d{2}[a-z]?)*\)')
    FIGURE_TABLE_REF = re.compile(r'\b(?:Figure|Fig\.|Table|Equation|Eq\.)\s*\(?[0-9]+[a-z]?\)?', re.I)
    NUMERIC_VALUES = re.compile(r'(?<![\w.])' + NUMBER + r'(?!\w)')
    MODEL_NAMES = ['bert', 'roberta', 'gpt-3', 'gpt-4', 'llama', 'resnet', 'vgg', 'transformer',
                   'svm', 'random forest', 'lstm', 'gru', 'xgboost', 't5', 'gemini', 'claude', 'mistral',
                   'clip', 'alexnet', 'yolo', 'shap', 'lime', 'grad-cam', 'timeseriesconv1d', 'adam',
                   'quantlens-xai', 'ohclv', 'ohlcv', 'cnn', 'pytorch', 'tensorflow']

    @classmethod
    def extract_facts(cls, text: str) -> Dict[str, Any]:
        metrics = cls.METRIC_PATTERN.findall(text)
        units = cls.UNIT_PATTERN.findall(text)
        # Citation numbers are independently protected and must not count as measurements.
        without_citations = cls.CITATION_NUMERIC.sub('', text)
        equations = re.findall(r'\$[^$\n]+\$|\\\([^\n]+?\\\)|\b[A-Za-z][A-Za-z_0-9]*(?:\([^\n=]{1,30}\))?\s*=\s*[^.;\n]+', text)
        return {'metrics': [{'name': name.strip(), 'value': value} for name, value in metrics],
                'units': [{'value': value, 'unit': unit} for value, unit in units],
                'numeric_citations': cls.CITATION_NUMERIC.findall(text),
                'author_citations': cls.CITATION_AUTHOR_YEAR.findall(text),
                'fig_table_refs': cls.FIGURE_TABLE_REF.findall(text),
                'numbers': cls.NUMERIC_VALUES.findall(without_citations),
                'models': [name for name in cls.MODEL_NAMES if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I)],
                'equations': equations}

    @classmethod
    def compare_facts(cls, original_text: str, proposed_text: str) -> Tuple[bool, List[str]]:
        orig, prop = cls.extract_facts(original_text), cls.extract_facts(proposed_text)
        violations = []
        norm = lambda value: re.sub(r'\s+', ' ', value).strip().casefold()
        orig_metrics = Counter((norm(m['name']), m['value']) for m in orig['metrics'])
        prop_metrics = Counter((norm(m['name']), m['value']) for m in prop['metrics'])
        for metric, val in (orig_metrics - prop_metrics):
            same_name = [m['value'] for m in prop['metrics'] if norm(m['name']) == metric]
            if same_name:
                violations.append(f"Metric alteration detected: '{metric}' with value {val} is no longer preserved (revised: {', '.join(same_name)})")
            else:
                violations.append(f"Metric omitted: '{metric}' with value {val} is missing from revised text")
        for field, missing_label, added_label in [
            ('numbers', 'Empirical measurement missing', 'New numerical claim requires evidence'),
            ('numeric_citations', 'Citation dropped', 'New citation requires source verification'),
            ('author_citations', 'Citation dropped', 'New citation requires source verification'),
            ('models', 'Model/architecture name altered', 'New model/architecture requires evidence'),
            ('fig_table_refs', 'Reference dropped', 'New figure/table reference requires verification'),
            ('equations', 'Equation changed or omitted', 'New equation requires author verification'),
        ]:
            before, after = Counter(norm(x) for x in orig[field]), Counter(norm(x) for x in prop[field])
            for value, count in (before - after).items():
                violations.append(f"{missing_label}: '{value}' ({count} occurrence(s))")
            for value, count in (after - before).items():
                violations.append(f"{added_label}: '{value}' ({count} occurrence(s))")
        before_units = Counter((u['value'], norm(u['unit'])) for u in orig['units'])
        after_units = Counter((u['value'], norm(u['unit'])) for u in prop['units'])
        for value, unit in before_units - after_units:
            violations.append(f"Quantity/unit changed or omitted: '{value} {unit}'")
        for value, unit in after_units - before_units:
            violations.append(f"New quantity/unit requires verification: '{value} {unit}'")
        # Preserve numeric associations with a repeated metric (e.g. baseline vs proposed F1).
        repeated = {name for name, _ in orig_metrics if sum(n == name for n, _ in orig_metrics) > 1}
        for name in repeated:
            before = [m['value'] for m in orig['metrics'] if norm(m['name']) == name]
            after = [m['value'] for m in prop['metrics'] if norm(m['name']) == name]
            if before != after and Counter(before) == Counter(after):
                violations.append(f"Experimental context/order changed for repeated metric '{name}'; author approval is required")
        return not violations, violations
