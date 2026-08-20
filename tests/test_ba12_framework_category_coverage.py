"""BA-12: the category names this estate actually uses must map to a framework.

`FrameworkClassifier` matches APQC-style domain names ("Accounting", "Treasury
Management"). The capabilities in the field are named for the business
("Finance & Controlling", "Sales & Channel Management"), so eight real domains
covering 41 capabilities resolved to no framework and were invisible on the
frameworks overview — the page an evaluating architect judged the maturity
feature by.

These are the names measured in production on 20 Aug 2026. If someone edits the
classifier and drops one, that domain silently disappears from the overview
again; this test is what stops that being silent.
"""
import pytest

from app.utils.framework_classifier import FrameworkClassifier

# Measured in production 20 Aug 2026: SELECT category, COUNT(*) ... GROUP BY 1
PRODUCTION_DOMAINS = [
    "Manufacturing Operations",
    "Information Technology",
    "Finance & Controlling",
    "People & Organisation",
    "Customer Management",
    "Procurement",
    "Product & Innovation",
    "Sales & Channel Management",
    "Supply Chain & Logistics",
    "Health, Safety & Environment",
]

# The same column also carries capability *tiers*, which are a different axis
# entirely — not business domains. They are already routed to their own
# framework; this test pins that they stay recognised, not that they are
# reclassified as domains.
PRODUCTION_TIERS = ["operational", "tactical", "supporting", "strategic"]


def _known_categories() -> set[str]:
    return {
        category
        for framework in FrameworkClassifier.FRAMEWORKS.values()
        for domain in framework["domains"].values()
        for category in domain["categories"]
    }


@pytest.mark.parametrize("category", PRODUCTION_DOMAINS)
def test_real_business_domain_maps_to_a_framework(category):
    assert category in _known_categories(), (
        f"{category!r} is used by real capabilities but matches no framework, so "
        "they are invisible on /capability-maturity/frameworks"
    )


@pytest.mark.parametrize("tier", PRODUCTION_TIERS)
def test_capability_tier_is_still_recognised(tier):
    assert tier in _known_categories(), f"tier {tier!r} no longer resolves"


def test_classifier_returns_a_framework_for_every_production_category():
    """classify_category is the public entry point — exercise it, not just the dict."""
    unresolved = [
        c
        for c in PRODUCTION_DOMAINS + PRODUCTION_TIERS
        if not FrameworkClassifier.classify_category(c)
    ]
    assert not unresolved, f"classify_category returned nothing for: {unresolved}"
