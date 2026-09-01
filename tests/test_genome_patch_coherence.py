"""Cross-layer COHERENCE grounding.

Two tiers of test:
  * pure unit tests of the layer-adjacency / realization rule tables — no DB,
    no app context; the rules are just lookups and are proved as such.
  * grounded tests through `ground_genome_patch` on a small seeded model —
    that the advisory warnings fire (floating element, incoherent anchor), that
    a coherent anchor does NOT warn, that it is org-scoped, and that the
    pre-existing hard blocks (wrong layer, exact duplicate) still fire.
"""
import pytest

from app.modules.genome.patch.coherence import (
    COHERENT_LAYERS,
    REALIZED_BY_LAYERS,
    is_floating,
    layers_can_relate,
    realizing_layers_for,
)
from app.modules.genome.patch.grounding import ground_genome_patch
from app.models.archimate_core import ArchiMateElement


# --------------------------------------------------------------------------- #
# Pure unit tests — the rule tables, no DB.                                    #
# --------------------------------------------------------------------------- #
def test_realizing_layers_downward():
    # A strategy Capability is realized by the business/application beneath it.
    assert realizing_layers_for("strategy") == {"business", "application"}
    # A business service is realized by the applications that automate it.
    assert realizing_layers_for("business") == {"application"}
    # Physical is the floor — nothing realizes it.
    assert realizing_layers_for("physical") == set()


def test_is_floating_only_when_no_realizer_present():
    # strategy needs business/application; an org holding only strategy floats it
    assert is_floating("strategy", {"strategy", "motivation"}) is True
    # once a business element exists, it is realized — not floating
    assert is_floating("strategy", {"strategy", "business"}) is False
    # physical can never float (bottom of the stack), even in an empty org
    assert is_floating("physical", set()) is False
    # an unknown layer has no realizing rule → never floating
    assert is_floating("nonsense", set()) is False


def test_layers_can_relate_adjacent_and_motivation():
    # adjacent layers relate
    assert layers_can_relate("strategy", "business") is True
    assert layers_can_relate("application", "technology") is True
    # motivation cross-cuts every layer
    assert layers_can_relate("motivation", "technology") is True
    assert layers_can_relate("physical", "motivation") is True
    # same layer relates to itself
    assert layers_can_relate("business", "business") is True


def test_layers_cannot_relate_when_far_apart():
    # strategy and physical are non-adjacent with no motivation involved
    assert layers_can_relate("strategy", "physical") is False
    assert layers_can_relate("physical", "strategy") is False
    # technology and strategy are two steps apart
    assert layers_can_relate("technology", "strategy") is False


def test_relate_is_symmetric_over_all_known_layers():
    for a in COHERENT_LAYERS:
        for b in COHERENT_LAYERS:
            assert layers_can_relate(a, b) == layers_can_relate(b, a)


def test_rule_tables_cover_the_same_layer_set():
    # every layer with a realizing rule is a known coherence layer
    assert set(REALIZED_BY_LAYERS) <= set(COHERENT_LAYERS)


# --------------------------------------------------------------------------- #
# Grounded tests — small seeded model.                                         #
# --------------------------------------------------------------------------- #
def _patch(org_id, *, a_type="Capability", layer="strategy", name="New Thing",
           op="add", anchor="Capability"):
    return {
        "target": {"organization_id": org_id, "domain": "business"},
        "operation": op,
        "element": {"archimate_type": a_type, "layer": layer, "name": name},
        "provenance": {"proposed_by": "1", "rationale": "because", "archimate_anchor": anchor},
    }


def _seed(session, org_id, name, a_type, layer):
    e = ArchiMateElement(name=name, type=a_type, layer=layer, organization_id=org_id)
    session.add(e)
    session.flush()
    return e


def test_floating_element_warns(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # org holds only a strategy element; a new strategy Capability has no
        # business/application beneath it to realize it → advisory floating warn
        _seed(db_session, org.id, "Order Management", "Capability", "strategy")
        r = ground_genome_patch(
            _patch(org.id, a_type="Capability", name="Payroll", anchor="Capability"),
            session=db_session,
        )
        assert r.ok  # advisory, never a hard block
        assert any("floating" in w for w in r.warnings), r.warnings


def test_coherent_realizer_present_does_not_warn(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # a business element realizes the proposed strategy Capability → no float
        _seed(db_session, org.id, "Fulfilment Service", "BusinessService", "business")
        r = ground_genome_patch(
            _patch(org.id, a_type="Capability", name="Payroll", anchor="Capability"),
            session=db_session,
        )
        assert r.ok, r.errors
        assert not any("floating" in w for w in r.warnings), r.warnings


def test_coherent_anchor_adjacent_layer_does_not_warn(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # anchor is a business element; proposing a strategy Capability that
        # hangs off it is a coherent (adjacent) cross-layer link → no anchor warn
        _seed(db_session, org.id, "Billing Service", "BusinessService", "business")
        r = ground_genome_patch(
            _patch(org.id, a_type="Capability", name="Revenue Mgmt", anchor="Billing Service"),
            session=db_session,
        )
        assert r.ok, r.errors
        assert not any("cannot coherently relate" in w for w in r.warnings), r.warnings


def test_incoherent_anchor_layer_warns(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # anchor is a physical-layer element; a strategy Capability cannot
        # coherently relate to physical under ArchiMate 3.2 → advisory warn
        _seed(db_session, org.id, "Data Centre", "Node", "physical")
        # also seed a business realizer so the ONLY warning is the anchor one
        _seed(db_session, org.id, "Ops Service", "BusinessService", "business")
        r = ground_genome_patch(
            _patch(org.id, a_type="Capability", name="Scaling Capability", anchor="Data Centre"),
            session=db_session,
        )
        assert r.ok  # advisory, not a hard block
        assert any("cannot coherently relate" in w for w in r.warnings), r.warnings


def test_coherence_is_org_scoped(db_session, make_org, tenant_ctx):
    org_a = make_org()
    org_b = make_org()
    # org_a has a realizing business layer; org_b does not
    with tenant_ctx(org_a.id):
        _seed(db_session, org_a.id, "A Service", "BusinessService", "business")
    with tenant_ctx(org_b.id):
        # org_b's proposed strategy Capability must not "see" org_a's business
        # element — it should float in org_b's own (empty) model
        r = ground_genome_patch(
            _patch(org_b.id, a_type="Capability", name="B Capability", anchor="Capability"),
            session=db_session,
        )
        assert r.ok
        assert any("floating" in w for w in r.warnings), r.warnings


def test_hard_blocks_still_fire_alongside_coherence(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # wrong layer for the type stays a hard ERROR, not downgraded to a warn
        r = ground_genome_patch(
            _patch(org.id, a_type="Capability", layer="business"), session=db_session
        )
        assert not r.ok and any("layer" in e for e in r.errors)

        # exact duplicate stays a hard ERROR
        _seed(db_session, org.id, "Billing", "Capability", "strategy")
        r2 = ground_genome_patch(
            _patch(org.id, a_type="Capability", name="billing", anchor="Capability"),
            session=db_session,
        )
        assert not r2.ok and any("already exists" in e for e in r2.errors)
