import pytest
from backend.app.services.fact_validator import FactValidator

def test_fact_preservation_valid():
    orig = "The proposed model achieved an F1-score of 0.92 and accuracy of 94.6% on the benchmark dataset [1]."
    # Harmless clarity edit that keeps all metrics, citations, and models
    revised = "On the benchmark dataset [1], our proposed model achieved an F1-score of 0.92 alongside an accuracy of 94.6%."
    
    is_valid, violations = FactValidator.compare_facts(orig, revised)
    assert is_valid is True
    assert len(violations) == 0

def test_metric_alteration_detected():
    """Ensure altering F1-score from 0.92 to 0.95 is caught."""
    orig = "The proposed model achieved an F1-score of 0.92 on the benchmark dataset."
    revised = "The proposed model achieved an F1-score of 0.95 on the benchmark dataset."
    
    is_valid, violations = FactValidator.compare_facts(orig, revised)
    assert is_valid is False
    assert any("Metric alteration detected" in v and "0.92" in v for v in violations)

def test_citation_dropping_detected():
    """Ensure removing [1] is caught."""
    orig = "Our methodology relies on transformer representations [1]."
    revised = "Our methodology relies on transformer representations."
    
    is_valid, violations = FactValidator.compare_facts(orig, revised)
    assert is_valid is False
    assert any("Citation dropped" in v and "[1]" in v for v in violations)

def test_model_name_omission_detected():
    """Ensure replacing BERT / SVM with generic words is caught."""
    orig = "We evaluated the baseline SVM and Random Forest models."
    revised = "We evaluated the baseline classical machine learning algorithms."
    
    is_valid, violations = FactValidator.compare_facts(orig, revised)
    assert is_valid is False
    assert any("Model/architecture name altered" in v for v in violations)
