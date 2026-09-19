"""T-004a acceptance tests for the plain-terms sentence (FR-15).

Maps to the T-004a brief's acceptance items 8 and 9:

    8  -> test_confidence_bands_at_the_boundaries[*],
          test_percent_is_confidence_rounded_half_up_to_a_whole_number[*],
          test_null_confidence_omits_the_clause_and_never_prints_zero_percent,
          test_measured_zero_confidence_is_shown_as_zero_and_is_not_null,
          test_absent_name_or_depth_makes_the_whole_sentence_null[*],
          test_a_confidence_that_is_not_a_number_is_a_loud_error,
          test_derived_row_sentence_names_both_ends_from_the_identity_map,
          test_derived_row_sentence_is_null_when_an_endpoint_is_another_tenants,
          test_derived_row_without_confidence_has_no_clause,
          test_explicit_rows_carry_null_plain_terms
    9  -> test_the_sentence_is_assembled_in_exactly_one_place
"""

from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.intelligence.services.plain_terms import plain_terms_sentence

# Fixtures (app, db_session, make_org, ...) come from this directory's conftest.py.

HEAD = "We worked this out because Billing depends on Ledger, 2 hops away."


def _sentence(confidence, *, a="Billing", b="Ledger", depth=2):
    return plain_terms_sentence(dependent_name=a, dependency_name=b, depth=depth, confidence=confidence)


# --- the shape and the three bands ------------------------------------------


def test_the_sentence_matches_the_brief_example_exactly():
    assert _sentence(0.82) == (
        "We worked this out because Billing depends on Ledger, 2 hops away. Fairly confident (82%)."
    )


@pytest.mark.parametrize(
    "confidence, clause",
    [
        (1.0, "Very confident (100%)."),
        (0.95, "Very confident (95%)."),
        (0.90, "Very confident (90%)."),  # boundary: >= 0.90 is the top band
        (0.85, "Fairly confident (85%)."),
        (0.70, "Fairly confident (70%)."),  # boundary: >= 0.70 is the middle band
        (0.69, "Worth a second look — we are less confident (69%)."),  # boundary: just under
        (0.01, "Worth a second look — we are less confident (1%)."),
        (Decimal("0.90"), "Very confident (90%)."),  # what the store's Numeric(3,2) hands back
        (Decimal("0.70"), "Fairly confident (70%)."),
        (Decimal("0.69"), "Worth a second look — we are less confident (69%)."),
    ],
)
def test_confidence_bands_at_the_boundaries(confidence, clause):
    assert _sentence(confidence) == f"{HEAD} {clause}"


@pytest.mark.parametrize(
    "confidence, pct",
    [(0.825, 83), (0.835, 84), (0.845, 85), (0.005, 1), (0.994, 99), (0.996, 100)],
)
def test_percent_is_confidence_rounded_half_up_to_a_whole_number(confidence, pct):
    # Half-up, not banker's rounding, and not at the mercy of binary floats:
    # 0.845 * 100 is 84.49999999999999 as a float, yet reads as 85%.
    assert f"({pct}%)." in _sentence(confidence)


# --- honesty: null confidence, absent names ---------------------------------


def test_null_confidence_omits_the_clause_and_never_prints_zero_percent():
    sentence = _sentence(None)
    assert sentence == HEAD
    assert "%" not in sentence
    assert "0%" not in sentence
    assert "confident" not in sentence.lower()


def test_measured_zero_confidence_is_shown_as_zero_and_is_not_null():
    """A real 0.0 is a measurement and is rendered; only ``None`` (not
    recorded) is omitted -- the two are never conflated."""
    assert _sentence(0.0) == f"{HEAD} Worth a second look — we are less confident (0%)."
    assert _sentence(0) != _sentence(None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"a": None},
        {"b": None},
        {"a": None, "b": None},
        {"a": ""},
        {"b": "   "},
        {"depth": None},
    ],
)
def test_absent_name_or_depth_makes_the_whole_sentence_null(kwargs):
    # Never a sentence with a gap in it.
    assert _sentence(0.82, **kwargs) is None
    assert _sentence(None, **kwargs) is None


def test_a_confidence_that_is_not_a_number_is_a_loud_error():
    with pytest.raises(TypeError):
        _sentence("high")
    with pytest.raises(TypeError):
        _sentence(True)


# --- through cross_layer_impact ---------------------------------------------


def _element(db_session, org_id, name):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type="ApplicationComponent", layer="application", organization_id=org_id)
    db_session.add(el)
    db_session.flush()
    return el


def _derived(db_session, org_id, source, target, chain_element_ids, *, confidence, depth=2):
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    row = DerivedRelationship(
        organization_id=org_id,
        source_element_id=source.id,
        target_element_id=target.id,
        derived_type="Serving",
        rule_id="R-07",
        chain=list(range(1, depth + 1)),
        chain_element_ids=list(chain_element_ids),
        depth=depth,
        confidence=confidence,
        provenance="derivation",
        engine_version="1.2.0",
        computed_at=_dt.datetime.utcnow(),
        stale=False,
        stale_since=None,
        stale_reason=None,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _impact(app, org_id, element_id, **kwargs):
    from flask import g

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    with app.test_request_context("/"):
        g.current_org_id = org_id
        return IntelligenceQueryService.cross_layer_impact(element_id, with_owner=False, **kwargs)


def test_derived_row_sentence_names_both_ends_from_the_identity_map(app, db_session, make_org):
    org = make_org("pt-names")
    ledger = _element(db_session, org.id, "Ledger")
    mid = _element(db_session, org.id, "Mid")
    billing = _element(db_session, org.id, "Billing")
    _derived(db_session, org.id, ledger, billing, [ledger.id, mid.id, billing.id], confidence=0.82)
    db_session.commit()

    # Started from Ledger (downstream) and from Billing (upstream): one fact,
    # one sentence -- A is the fact's target, B its source, whichever end the
    # caller started from.
    downstream = _impact(app, org.id, ledger.id, include_derived=True, direction="downstream")
    upstream = _impact(app, org.id, billing.id, include_derived=True, direction="upstream")
    expected = (
        "We worked this out because Billing depends on Ledger, 2 hops away. Fairly confident (82%)."
    )
    for result in (downstream, upstream):
        derived = [r for r in result["rows"] if r["relation"]["kind"] == "derived"]
        assert [r["relation"]["plain_terms"] for r in derived] == [expected]
        # The names in the sentence are the ones in the same response's map.
        assert result["elements"][str(billing.id)]["name"] == "Billing"
        assert result["elements"][str(ledger.id)]["name"] == "Ledger"


def test_derived_row_sentence_is_null_when_an_endpoint_is_another_tenants(app, db_session, make_org):
    org_a = make_org("pt-xt-a")
    org_b = make_org("pt-xt-b")
    mine = _element(db_session, org_a.id, "Mine")
    mid = _element(db_session, org_a.id, "Mid")
    theirs = _element(db_session, org_b.id, "TheirsOrgB")
    _derived(db_session, org_a.id, mine, theirs, [mine.id, mid.id, theirs.id], confidence=1.0)
    db_session.commit()

    result = _impact(app, org_a.id, mine.id, include_derived=True)
    derived = [r for r in result["rows"] if r["relation"]["kind"] == "derived"]
    assert len(derived) == 1
    assert derived[0]["relation"]["plain_terms"] is None
    assert "TheirsOrgB" not in str(result)


def test_derived_row_without_confidence_has_no_clause(app, db_session, make_org, monkeypatch):
    """The store pins ``confidence`` NOT NULL, so a null one cannot be
    written; the store accessor is wrapped to return one so the row-building
    path (not just the unit function) is shown to omit the clause."""
    from app.modules.intelligence.services import query_service

    org = make_org("pt-nullconf")
    ledger = _element(db_session, org.id, "Ledger")
    mid = _element(db_session, org.id, "Mid")
    billing = _element(db_session, org.id, "Billing")
    _derived(db_session, org.id, ledger, billing, [ledger.id, mid.id, billing.id], confidence=1.0)
    db_session.commit()

    real = query_service.list_derived_facts

    def _without_confidence(*args, **kwargs):
        facts = real(*args, **kwargs)
        for fact in facts:
            fact["confidence"] = None
        return facts

    monkeypatch.setattr(query_service, "list_derived_facts", _without_confidence)
    result = _impact(app, org.id, ledger.id, include_derived=True)
    derived = [r for r in result["rows"] if r["relation"]["kind"] == "derived"]
    assert [r["relation"]["plain_terms"] for r in derived] == [HEAD]
    assert derived[0]["relation"]["confidence"] is None
    assert "%" not in derived[0]["relation"]["plain_terms"]


def test_explicit_rows_carry_null_plain_terms(app, db_session, make_org):
    from app.models import ArchiMateRelationship

    org = make_org("pt-explicit")
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Bravo")
    db_session.add(ArchiMateRelationship(source_id=a.id, target_id=b.id, type="Serving", organization_id=org.id))
    db_session.commit()

    result = _impact(app, org.id, a.id, include_derived=True)
    explicit = [r for r in result["rows"] if r["relation"]["kind"] == "explicit"]
    assert explicit and all(r["relation"]["plain_terms"] is None for r in explicit)


# --- acceptance 9: one generator --------------------------------------------

# Wording specific enough not to collide with unrelated copy (the solution
# explainability service already says "Very confident" / "Less confident" with
# no percentage, so those bare words are not the signature).
_SIGNATURES = (
    re.compile(r"we\s+worked\s+this\s+out\s+because", re.IGNORECASE),
    re.compile(r"hops\s+away", re.IGNORECASE),  # plural only: "one hop away" is ordinary prose elsewhere
    re.compile(r"(very|fairly)\s+confident\s*\(", re.IGNORECASE),
    re.compile(r"less\s+confident\s*\(", re.IGNORECASE),
    re.compile(r"worth\s+a\s+second\s+look", re.IGNORECASE),
)
_CODE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".html", ".htm", ".jinja", ".jinja2", ".j2"}
_SKIP_DIRS = {
    ".git",
    ".claude",
    ".kilo",
    "node_modules",
    "docs",
    "playwright-report",
    "__pycache__",
    "site-packages",
    "venv",
    ".venv",
}


def _repo_root() -> Path:
    # app/modules/intelligence/tests/<this file> -> repository root
    return Path(__file__).resolve().parents[4]


def _is_test_file(path: Path) -> bool:
    return any(part in {"tests", "test"} for part in path.parts) or path.name.startswith("test_")


def test_the_sentence_is_assembled_in_exactly_one_place():
    """No other module, template or script in the tree builds this sentence.

    Scans every Python, JavaScript/TypeScript and template file (tests and
    documentation excluded -- tests assert on the wording, they do not
    produce it) for the sentence's signature phrases. Only ``plain_terms.py``
    may carry them.
    """
    import os

    root = _repo_root()
    generator = root / "app" / "modules" / "intelligence" / "services" / "plain_terms.py"
    assert generator.is_file()

    scanned = 0
    offenders = []
    generator_hits = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in _CODE_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if _is_test_file(relative):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hits = [sig.pattern for sig in _SIGNATURES if sig.search(text)]
            if path == generator:
                generator_hits = len(hits)
            elif hits:
                offenders.append((relative.as_posix(), hits))

    # The scan is not vacuous: it walked the tree and found the generator's own wording.
    assert scanned > 500, scanned
    assert generator_hits == len(_SIGNATURES)
    assert offenders == [], offenders
