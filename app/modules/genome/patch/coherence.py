"""Cross-layer COHERENCE grounding for a genome patch.

`grounding.py` checks a proposed element *in isolation*: is its layer right for
its type, does its anchor resolve, is it a duplicate. But architecture is the
*relationships* — an element that passes every isolated check can still be
incoherent with the model it would join: a Capability with nothing beneath it
that could realize it, or an anchor sitting in a layer that cannot validly
relate to the proposed one.

This module adds that relational judgement. It is deliberately, and only,
**advisory** — every finding here is a WARNING, never an error. Unlike the
provable contradictions in `grounding.py` (wrong layer for a type, an exact
duplicate), coherence is a matter of degree: ArchiMate 3.2 permits a very wide
range of cross-layer links, and a human approver may legitimately be
introducing the top of a brand-new chain. So we flag the *clearly* incoherent
to focus the approver's eye, and hard-block nothing.

The rules are two explicit, documented data structures derived from the
ArchiMate 3.2 layered framework, NOT invented here.

ArchiMate 3.2 basis
-------------------
The specification (§3, "Language Structure", the layered framework figure)
stacks the layers, most-abstract at the top, most-concrete at the bottom:

    motivation   (cross-cuts every layer — why)
    ─────────────
    strategy     (Capability, CourseOfAction, ValueStream, Resource)
    business     (BusinessService, BusinessProcess, …)
    application  (ApplicationComponent, ApplicationService, DataObject)
    technology   (Node, TechnologyService, …)
    physical     (Equipment, Facility — specialises technology)
    ─────────────
    implementation & migration (WorkPackage, Plateau — realises the above /
                                the motivation it delivers)

Realization runs UPWARD from the more-concrete layer to the more-abstract one
it makes real (an ApplicationComponent realizes a BusinessService; a Node
realizes an ApplicationComponent) — this is exactly the direction encoded in
`app/models/archimate_core.py::VALID_RELATIONSHIPS` for the `realization`
type. Serving, access and association additionally connect *adjacent* layers.
Motivation elements relate to elements in ANY layer (they are the "why" behind
everything), and implementation elements realize/associate across the strategy,
business and application layers plus the motivation they deliver.

The two structures below are the deterministic distillation of that figure.
They mention no relationship instances and read no LLM — they are pure lookups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.modules.genome.patch.schema import ARCHIMATE_TYPE_LAYER

# --------------------------------------------------------------------------- #
# Rule 1 — which layer(s) would normally REALIZE / SUPPORT an element of a     #
# given layer (i.e. sit one step more concrete and make it real).             #
#                                                                             #
# Read "an element in layer <key> is normally realized/supported by an        #
# element in one of layers <value>". Derived from the realization direction   #
# of the ArchiMate 3.2 framework (concrete → abstract) and the `realization`  #
# rows of VALID_RELATIONSHIPS in app/models/archimate_core.py:                #
#   application realizes business, technology realizes application,           #
#   strategy realizes business, motivation is realized by strategy/business,  #
#   implementation realizes motivation.                                       #
# An empty value means "bottom of the stack" — nothing below can realize it,  #
# so absence of a realizing layer is NOT a floating signal (it is the floor). #
# --------------------------------------------------------------------------- #
REALIZED_BY_LAYERS: Dict[str, Set[str]] = {
    # Goals/Requirements/Drivers are made real by capabilities and by the
    # business that carries them out.
    "motivation": {"strategy", "business"},
    # Capabilities/ValueStreams are realized by the business (and the
    # applications) that deliver them.
    "strategy": {"business", "application"},
    # Business services/processes are realized by the applications that
    # automate them.
    "business": {"application"},
    # Applications are realized by the technology they run on.
    "application": {"technology"},
    # Technology is realized by the physical equipment/facilities beneath it.
    "technology": {"physical"},
    # Physical is the floor of the concrete stack.
    "physical": set(),
    # Work packages / plateaus are carried out by the business & application
    # elements that do the work.
    "implementation": {"business", "application"},
}

# --------------------------------------------------------------------------- #
# Rule 2 — which layers can COHERENTLY relate to a given layer (adjacent in    #
# the stack, same layer, or motivation cross-cutting). Symmetric by intent;    #
# an anchor whose layer is NOT in the proposed layer's set (and vice-versa)    #
# is the "clearly incoherent" case we warn on. Everything involving motivation #
# is coherent — motivation cross-cuts every layer in ArchiMate 3.2.            #
# --------------------------------------------------------------------------- #
_ALL_LAYERS: Set[str] = {
    "motivation", "strategy", "business", "application",
    "technology", "physical", "implementation",
}

COHERENT_LAYERS: Dict[str, Set[str]] = {
    # Motivation cross-cuts everything.
    "motivation": set(_ALL_LAYERS),
    "strategy": {"motivation", "strategy", "business", "implementation"},
    "business": {"motivation", "strategy", "business", "application", "implementation"},
    "application": {"motivation", "business", "application", "technology", "implementation"},
    "technology": {"motivation", "application", "technology", "physical"},
    "physical": {"motivation", "technology", "physical"},
    # Implementation realizes strategy/business/application and delivers
    # motivation.
    "implementation": {"motivation", "strategy", "business", "application", "implementation"},
}


# --------------------------------------------------------------------------- #
# Pure helpers — no DB, unit-testable in isolation.                            #
# --------------------------------------------------------------------------- #
def realizing_layers_for(layer: Optional[str]) -> Set[str]:
    """Layers that would normally realize/support an element in `layer`."""
    return REALIZED_BY_LAYERS.get(layer or "", set())


def is_floating(layer: Optional[str], present_layers: Set[str]) -> bool:
    """True when `layer` needs a realizing layer and the org has none of them.

    A floating element is one proposed at layer L where L *has* a normal
    realizing/supporting layer (it is not the floor of the stack), yet the org
    holds ZERO elements in any layer that could realize it — so as modelled it
    would hang unsupported. Advisory only: the approver may be seeding the top
    of a new chain.
    """
    candidates = realizing_layers_for(layer)
    if not candidates:  # bottom of the stack — cannot float
        return False
    return not (candidates & present_layers)


def layers_can_relate(layer_a: Optional[str], layer_b: Optional[str]) -> bool:
    """True when two layers can coherently relate under ArchiMate 3.2.

    Symmetric: coherent if either layer lists the other (motivation, being
    cross-cutting, lists — and is listed by — every layer). Unknown layers are
    treated as coherent (we never warn on something we cannot classify).
    """
    if not layer_a or not layer_b:
        return True
    a = COHERENT_LAYERS.get(layer_a)
    b = COHERENT_LAYERS.get(layer_b)
    if a is None or b is None:
        return True
    return layer_b in a or layer_a in b


def _proposed_layer(element: Dict[str, Any]) -> Optional[str]:
    """The layer of the proposed element — canonical for its type if known,
    else its declared layer (grounding already hard-blocks a mismatch, so on a
    passing patch these agree)."""
    a_type = element.get("archimate_type")
    return ARCHIMATE_TYPE_LAYER.get(a_type) or element.get("layer")


# --------------------------------------------------------------------------- #
# The coherence check itself — the only DB-touching entry point.              #
# --------------------------------------------------------------------------- #
def assess_coherence(
    element: Dict[str, Any],
    provenance: Dict[str, Any],
    operation: Optional[str],
    existing_query,
    ArchiMateElement,
    resolve_anchor,
) -> List[str]:
    """Advisory cross-layer coherence warnings for a proposed patch.

    Reuses the org-scoped `existing_query` closure and the `resolve_anchor`
    helper built in `grounding.ground_genome_patch` — no new query path, no
    second anchor grammar. Returns a (possibly empty) list of warning strings;
    never raises on a merely-unusual patch, never returns an error.

    Two checks:
      * floating / unrealized — an `add` whose layer normally has a realizing
        layer, but the org holds no element in any such layer.
      * anchor layer-adjacency — when the anchor resolves to a real element,
        its layer should be able to coherently relate to the proposed layer.
    """
    warnings: List[str] = []
    layer = _proposed_layer(element)
    name = (element.get("name") or "").strip() or "(unnamed)"
    a_type = element.get("archimate_type")

    # -- floating / unrealized (adds only) --------------------------------
    if operation == "add" and layer:
        rows = (
            existing_query()
            .with_entities(ArchiMateElement.layer)
            .distinct()
            .all()
        )
        present_layers = {r[0] for r in rows if r[0]}
        if is_floating(layer, present_layers):
            realizers = ", ".join(sorted(realizing_layers_for(layer)))
            warnings.append(
                f"{a_type or 'element'} {name!r} would be a floating/unrealized "
                f"element: a {layer} element is normally realized by a "
                f"{realizers} element, and this org has none — confirm you are "
                f"deliberately introducing the top of a new chain"
            )

    # -- anchor layer-adjacency -------------------------------------------
    anchor = (provenance.get("archimate_anchor") or "").strip()
    if anchor and layer:
        match, _known_type = resolve_anchor(anchor, existing_query, ArchiMateElement)
        if match is not None and match.layer and not layers_can_relate(layer, match.layer):
            warnings.append(
                f"anchor {anchor!r} sits in the {match.layer!r} layer, which "
                f"cannot coherently relate to a {layer} element like "
                f"{name!r} under ArchiMate 3.2 — confirm the anchor is right"
            )

    return warnings


__all__ = [
    "REALIZED_BY_LAYERS",
    "COHERENT_LAYERS",
    "realizing_layers_for",
    "is_floating",
    "layers_can_relate",
    "assess_coherence",
]
