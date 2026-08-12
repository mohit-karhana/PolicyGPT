"""Tests for the reference cosine-similarity implementation.

This is the math pgvector's `<=>` operator performs (as a distance).
"""

from app.services.embedding_service import cosine_similarity


def test_identical_direction_is_one() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0


def test_orthogonal_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_opposite_is_minus_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_zero_vector_is_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_magnitude_does_not_matter() -> None:
    """Cosine compares direction (meaning), not length."""
    small = cosine_similarity([0.1, 0.2], [1.0, 1.0])
    large = cosine_similarity([100.0, 200.0], [1.0, 1.0])
    assert abs(small - large) < 1e-9
