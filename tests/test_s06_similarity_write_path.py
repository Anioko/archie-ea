"""S-06: near-duplicate advisory reused on the write path (UI + agent), not
only in the post-hoc rationalization sweep.

Composes with duplicate_guard's exact-match 409: this covers different-name
near-duplicates, and reuses SimpleDuplicateService._calculate_name_similarity
directly rather than a second detector.
"""
from __future__ import annotations


def test_find_similar_entities_reuses_simple_duplicate_service_scoring(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement
    from app.utils.duplicate_guard import find_similar_entities

    org = make_org("s06-sim")

    with tenant_ctx(org.id):
        existing = ArchiMateElement(
            name="Plasterboard Recycling System",
            type="ApplicationComponent",
            organization_id=org.id,
        )
        unrelated = ArchiMateElement(
            name="Payroll Engine",
            type="ApplicationComponent",
            organization_id=org.id,
        )
        db_session.add_all([existing, unrelated])
        db_session.flush()

        similar = find_similar_entities(
            ArchiMateElement,
            "Plasterboard Recycling Systems",  # typo/plural variant, not exact
            organization_id=org.id,
        )

        ids = {row["id"] for row in similar}
        assert existing.id in ids
        assert unrelated.id not in ids
        assert all(0.0 <= row["score"] < 1.0 for row in similar)


def test_find_similar_entities_excludes_exact_matches(db_session, make_org, tenant_ctx):
    """Exact matches are duplicate_guard's 409 job, not this advisory's."""
    from app.models.solution_models import Solution
    from app.utils.duplicate_guard import find_similar_entities

    org = make_org("s06-exact")

    with tenant_ctx(org.id):
        exact = Solution(name="Customer 360 Platform", organization_id=org.id)
        db_session.add(exact)
        db_session.flush()

        similar = find_similar_entities(Solution, "Customer 360 Platform", organization_id=org.id)
        assert similar == []


def test_find_similar_entities_blank_name_returns_empty(db_session):
    from app.models.solution_models import Solution
    from app.utils.duplicate_guard import find_similar_entities

    assert find_similar_entities(Solution, "") == []
    assert find_similar_entities(Solution, None) == []
