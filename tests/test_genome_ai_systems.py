"""PILLAR 6 — the AI Systems genome projection.

Uses the shared fixtures in tests/conftest.py (db_session rolls back).
"""

from __future__ import annotations

import pytest

from app.modules.enterprise_genome.emit.ai_systems_register import emit_ai_systems_register
from app.modules.enterprise_genome.services.ai_system_profile import (
    RETIRED_MODEL_IDS,
    model_currency,
    profile_from_element,
    risk_flags,
)
from app.modules.enterprise_genome.services.ai_systems_seed import (
    ARCHIE_COPILOT_NAME,
    register_ai_system,
    seed_archie_copilot,
)
from app.modules.enterprise_genome.services.ai_systems_slice import build_ai_systems_slice


@pytest.fixture
def org(make_org):
    return make_org("genome-ai")


def _seed_three(session, org_id):
    """One retired-model system, one high-autonomy ungoverned system, one with
    no governance recorded at all."""
    retired = register_ai_system(
        session, org_id,
        name="Legacy Classifier",
        provider="anthropic",
        model_id="claude-3-5-sonnet-20241022",  # on the denylist
        purpose="ticket routing",
        autonomy_level="assisted",
        data_sensitivity="internal",
        approval_gate=True,
        human_review=True,
    )
    ungoverned = register_ai_system(
        session, org_id,
        name="Autonomous Trader",
        provider="openai",
        model_id="gpt-4o",
        purpose="executes trades",
        autonomy_level="autonomous",
        data_sensitivity="confidential",
        approval_gate=False,   # high autonomy + no approval gate = risk
        human_review=False,
    )
    bare = register_ai_system(
        session, org_id,
        name="Mystery Bot",
        provider="anthropic",
        model_id="claude-opus-5",
        purpose="unclear",
        # no autonomy, no data sensitivity, no governance recorded
    )
    session.flush()
    return retired, ungoverned, bare


def test_model_currency_uses_retired_denylist():
    # retired ids are exactly the denylist
    assert model_currency("claude-3-5-sonnet-20241022") == "retired"
    assert "claude-3-5-sonnet-20241022" in RETIRED_MODEL_IDS
    # a current default model
    assert model_currency("claude-opus-5") == "current"
    assert model_currency("gpt-4o") == "current"
    # a real-but-unsupported id
    assert model_currency("gpt-3.5-turbo") == "stale"
    # nothing recorded -> unknown, never a guess
    assert model_currency("") == "unknown"
    assert model_currency(None) == "unknown"


def test_slice_projects_with_provenance_and_hash(db_session, org):
    _seed_three(db_session, org.id)
    slice_data = build_ai_systems_slice(org.id, db_session)

    assert slice_data["kind"] == "ai_systems"
    assert slice_data["organization_id"] == org.id
    assert slice_data["counts"]["total"] == 3
    # every projected system carries structural provenance
    for s in slice_data["systems"]:
        assert isinstance(s["archimate_element_id"], int)
        assert s["archimate_element_id"] > 0
    assert slice_data["spec_hash"].startswith("sha256:")


def test_slice_is_deterministic_byte_identical(db_session, org):
    _seed_three(db_session, org.id)
    a = build_ai_systems_slice(org.id, db_session)
    b = build_ai_systems_slice(org.id, db_session)
    assert a == b
    assert a["spec_hash"] == b["spec_hash"]
    # emitter is deterministic too
    assert str(emit_ai_systems_register(a)) == str(emit_ai_systems_register(b))


def test_retired_model_flagged(db_session, org):
    retired, _, _ = _seed_three(db_session, org.id)
    slice_data = build_ai_systems_slice(org.id, db_session)
    by_id = {s["archimate_element_id"]: s for s in slice_data["systems"]}
    p = by_id[retired.id]
    assert p["model_currency"] == "retired"
    assert "retired-model" in p["risk_flags"]


def test_ungoverned_high_autonomy_flagged(db_session, org):
    _, ungoverned, _ = _seed_three(db_session, org.id)
    slice_data = build_ai_systems_slice(org.id, db_session)
    by_id = {s["archimate_element_id"]: s for s in slice_data["systems"]}
    p = by_id[ungoverned.id]
    assert p["autonomy_level"] == "autonomous"
    assert p["governance"]["approval_gate"] is False
    assert "ungoverned-high-autonomy" in p["risk_flags"]


def test_no_governance_shows_unknown_not_fabricated(db_session, org):
    _, _, bare = _seed_three(db_session, org.id)
    slice_data = build_ai_systems_slice(org.id, db_session)
    by_id = {s["archimate_element_id"]: s for s in slice_data["systems"]}
    p = by_id[bare.id]
    assert p["governance"]["approval_gate"] == "unknown"
    assert p["governance"]["human_review"] == "unknown"
    assert p["autonomy_level"] == "unknown"
    assert p["data_sensitivity"] == "unknown"
    # unknown conditions never fabricate a risk flag
    assert p["risk_flags"] == []


def test_regulated_no_human_review_flag():
    # unit-level: regulated data + human_review False fires the flag
    profile = {
        "autonomy_level": "assisted",
        "data_sensitivity": "regulated",
        "model_currency": "current",
        "governance": {"approval_gate": True, "human_review": False},
    }
    assert "regulated-no-human-review" in risk_flags(profile)
    # but not when human_review is merely unrecorded
    profile["governance"]["human_review"] = "unknown"
    assert "regulated-no-human-review" not in risk_flags(profile)


def test_archie_copilot_is_modelled_honestly(db_session, org):
    el = seed_archie_copilot(db_session, org.id)
    p = profile_from_element(el)
    assert p["name"] == ARCHIE_COPILOT_NAME
    assert p["provider"] == "anthropic"
    assert p["autonomy_level"] == "human-in-loop"
    assert p["governance"]["approval_gate"] is True
    # honest: human_review is not asserted, so it reads unknown
    assert p["governance"]["human_review"] == "unknown"
    assert p["model_currency"] == "current"


def test_org_scoped(db_session, make_org):
    org_a = make_org("a")
    org_b = make_org("b")
    register_ai_system(db_session, org_a.id, name="A-only", provider="anthropic",
                       model_id="claude-opus-5", autonomy_level="assisted")
    db_session.flush()
    slice_a = build_ai_systems_slice(org_a.id, db_session)
    slice_b = build_ai_systems_slice(org_b.id, db_session)
    assert slice_a["counts"]["total"] == 1
    assert slice_b["counts"]["total"] == 0


def test_seed_is_idempotent_on_name(db_session, org):
    seed_archie_copilot(db_session, org.id)
    seed_archie_copilot(db_session, org.id)
    slice_data = build_ai_systems_slice(org.id, db_session)
    names = [s["name"] for s in slice_data["systems"]]
    assert names.count(ARCHIE_COPILOT_NAME) == 1
