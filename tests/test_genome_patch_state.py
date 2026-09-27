"""The AI copilot can propose a to-be (or as-is) architecture through the gate.

A genome patch may carry an optional `architecture_state`; the applier maps it to
ArchiMateElement.togaf_plateau. This is what lets the governed copilot build a
TARGET architecture, not just untagged elements. Tests pin schema acceptance and
that applying an approved patch sets the plateau.
"""

import pytest

from app.models.archimate_core import ArchiMateElement
from app.modules.genome.patch.applier import apply_genome_patch
from app.modules.genome.patch.validator import validate_genome_patch


def _patch(org_id, state):
    return {
        "target": {"organization_id": org_id, "domain": "application"},
        "operation": "add",
        "element": {
            "archimate_type": "ApplicationComponent",
            "layer": "application",
            "name": "Salesforce Sales Cloud",
            "architecture_state": state,
        },
        "provenance": {
            "proposed_by": "ai_copilot",
            "rationale": "Target CRM in the Constellation to-be architecture",
            "archimate_anchor": "ApplicationComponent",
        },
    }


def test_schema_accepts_architecture_state():
    res = validate_genome_patch(_patch(1, "Target"))
    assert res.valid, res.errors


def test_schema_rejects_bad_state():
    res = validate_genome_patch(_patch(1, "Eventually"))
    assert not res.valid


@pytest.mark.usefixtures("db_session")
def test_apply_sets_plateau(db_session, make_org, tenant_ctx):
    org = make_org("genome")
    with tenant_ctx(org.id):
        result = apply_genome_patch(_patch(org.id, "Target"), user_id=1)
        assert result.get("success"), result
        el = (ArchiMateElement.query
              .filter_by(organization_id=org.id, name="Salesforce Sales Cloud").first())
        assert el is not None
        assert el.togaf_plateau == "Target"  # placed on the to-be plateau
