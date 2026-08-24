"""Database-independent contracts for Chief Architect synthesis helpers."""

from app.modules.solutions_strategic.v2.services.chief_architect_service import (
    ChiefArchitectService,
)


def test_domain_summary_uses_only_successful_reads_as_coverage_denominator():
    """One failed catalogue read must be disclosed, not counted as no coverage."""
    evidence = [
        {
            "available": True,
            "layers": {"business", "application", "technology", "motivation"},
            "tables": {"data_objects"},
        },
        {
            "available": True,
            "layers": {"application"},
            "tables": set(),
        },
        {"available": False, "layers": set(), "tables": set()},
    ]

    summary = ChiefArchitectService._summarise_domain_evidence(evidence, in_scope=3)

    assert summary["state"] == "partial"
    assert summary["measured"] == 2
    assert summary["unavailable"] == 1
    domains = {item["key"]: item for item in summary["domains"]}
    assert {
        key: (domains[key]["covered"], domains[key]["denominator"])
        for key in ("business", "data", "application", "technology", "motivation")
    } == {
        "business": (1, 2),
        "data": (1, 2),
        "application": (2, 2),
        "technology": (1, 2),
        "motivation": (1, 2),
    }


def test_attention_prioritisation_orders_severity_then_oldest_known_age():
    """Critical work leads; equally severe aged work precedes newer work."""
    items = [
        {"id": 1, "severity": "high", "age_days": 3, "name": "Newer"},
        {"id": 2, "severity": "medium", "age_days": 90, "name": "Medium"},
        {"id": 3, "severity": "critical", "age_days": None, "name": "Critical"},
        {"id": 4, "severity": "high", "age_days": 15, "name": "Older"},
    ]

    ordered = ChiefArchitectService._prioritise_attention(items)

    assert [item["id"] for item in ordered] == [3, 4, 1, 2]
