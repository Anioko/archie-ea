"""Regression: the fuzzy duplicate path was dead — calculate_jaccard_similarity
was called by is_duplicate()/find_duplicates() but never defined."""
from app.modules.duplicate_detection.services.duplicate_detection_utils import (
    DuplicateDetectionUtils as D,
)


def test_jaccard_exists_and_is_bounded():
    assert hasattr(D, "calculate_jaccard_similarity")
    assert D.calculate_jaccard_similarity("a b c", "a b c") == 1.0
    assert D.calculate_jaccard_similarity("a b c", "x y z") == 0.0
    assert 0.0 < D.calculate_jaccard_similarity("order management", "order management system") < 1.0


def test_fuzzy_is_duplicate_no_longer_raises():
    is_dup, score = D.is_duplicate("Order Management", "Order Management System", mode="fuzzy", threshold=0.5)
    assert is_dup and score > 0.5
    is_dup2, _ = D.is_duplicate("Billing", "Invoicing", mode="fuzzy", threshold=0.5)
    assert not is_dup2  # lexical, not semantic
