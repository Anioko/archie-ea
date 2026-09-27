"""Grounded verification of a genome patch against the EXISTING model.

`validator.py` proves a patch is well-SHAPED (schema). That is necessary but not
sufficient: a schema-valid patch can still be *untrue* — a Capability declared in
the business layer, an anchor that hangs off an element which does not exist, or a
re-invention of something already in the model. Schema validation cannot catch any
of these because they depend on the org's real architecture, not on the patch's
shape.

This module closes that gap. It reuses what the platform already holds — the
`ArchiMateElement` store (the "one place for architecture") and the canonical
type→layer map in `schema.py` — to check a proposal against reality before it is
queued. It is deliberately conservative: it only raises on things that are
*provably* wrong given the current model, so it strengthens truthfulness without
inventing new rejections.

Kept separate from `validator.py` on purpose: the validator stays pure and
dependency-free; grounding needs the database. The proposer runs schema-validate
first, then grounding, and fails closed on either.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.genome.patch.schema import ARCHIMATE_TYPE_LAYER, ARCHIMATE_TYPES

# Lexical (Jaccard) similarity at/above which a proposed name is warned as a
# likely rephrased duplicate of an existing element. 0.5 catches token-supersets
# and reorderings ("Order Management" vs "Order Management System") without
# firing on merely-related names; synonyms are left to the embedding tier.
NEAR_DUPLICATE_THRESHOLD = 0.5


def _resolve_anchor(anchor, existing_query, ArchiMateElement):
    """Resolve a provenance anchor to ``(element, names_a_known_type)``.

    Mirrors the anchor grammar the anchor-existence check accepts: a bare
    ArchiMate type, a bare element name, or a ``"Type:Name"`` reference (the
    Name half is looked up in the org; the Type half is validated against
    ``ARCHIMATE_TYPES``). Returns the matched ``ArchiMateElement`` (or ``None``)
    and whether the anchor names a known ArchiMate type.

    Extracted so the anchor-existence check (below) and the coherence check
    (``coherence.assess_coherence``) read the anchor the *same* way — one
    grammar, one lookup, no drift between the two consumers.
    """
    anchor = (anchor or "").strip()
    if not anchor:
        return None, False
    if anchor in ARCHIMATE_TYPES:
        return None, True
    anchor_name = anchor.split(":", 1)[1].strip() if ":" in anchor else anchor
    known_type = anchor.split(":", 1)[0].strip() in ARCHIMATE_TYPES if ":" in anchor else False
    match = existing_query().filter(ArchiMateElement.name.ilike(anchor_name)).first()
    return match, known_type


class GroundingResult:
    """Outcome of grounding a patch against the existing model.

    `errors` are provable contradictions with the current architecture and block
    queuing. `warnings` are advisory (surfaced to the human approver, not fatal).
    """

    def __init__(self, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.errors = errors or []
        self.warnings = warnings or []

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok


def ground_genome_patch(patch: Dict[str, Any], session=None) -> GroundingResult:
    """Verify a (schema-valid) patch against the existing genome for `target.org`.

    Checks, all against the model already in the store:
      1. type↔layer consistency — the element's declared `layer` must be the layer
         its `archimate_type` actually belongs to.
      2. anchor existence — `provenance.archimate_anchor` must resolve: either a
         known ArchiMate *type*, or the *name* of an element that exists in the
         org. A specific name that is absent is a hallucinated anchor.
      3. no duplicate — an `add` whose (type, name) already exists in the org is a
         re-invention; the approver should modify the existing element instead.

    Never raises on a merely-unusual patch; only on a provable contradiction.
    Returns a GroundingResult (falsy when there are errors).
    """
    if session is None:
        from app.extensions import db

        session = db.session

    errors: List[str] = []
    warnings: List[str] = []

    element = patch.get("element") or {}
    target = patch.get("target") or {}
    provenance = patch.get("provenance") or {}
    operation = patch.get("operation")

    org_id = target.get("organization_id")
    a_type = element.get("archimate_type")
    layer = element.get("layer")
    name = (element.get("name") or "").strip()

    # 1. type <-> layer consistency -------------------------------------------
    canonical = ARCHIMATE_TYPE_LAYER.get(a_type)
    if canonical and layer and canonical != layer:
        errors.append(
            f"element.layer {layer!r} is wrong for archimate_type {a_type!r}: "
            f"a {a_type} belongs to the {canonical!r} layer"
        )

    # Nothing more can be grounded without an org to look in.
    if org_id is None:
        return GroundingResult(errors, warnings)

    from app.models.archimate_core import ArchiMateElement

    def _existing(**kw):
        # Explicit org filter — grounding may run for a target org that is not the
        # request's own, and it must never see another org's elements.
        return (
            session.query(ArchiMateElement)
            .filter(ArchiMateElement.organization_id == org_id)
            .filter_by(**kw)
        )

    # 2. anchor existence (ADVISORY) ------------------------------------------
    # A questionable anchor is surfaced to the human approver, not hard-blocked:
    # an anchor may legitimately reference something being introduced alongside,
    # and anchor free-text is looser than an element lookup. Provable
    # contradictions (wrong layer, exact duplicate) are the hard blocks.
    anchor = (provenance.get("archimate_anchor") or "").strip()
    if anchor and anchor not in ARCHIMATE_TYPES:
        # Accept a "Type:Name" reference by checking the Name half.
        match, known_type = _resolve_anchor(anchor, _existing, ArchiMateElement)
        if match is None and not known_type:
            warnings.append(
                f"provenance.archimate_anchor {anchor!r} does not resolve to an "
                f"existing element or a known ArchiMate type — confirm it hangs off "
                f"something real before approving"
            )

    # 3. duplicate / near-duplicate on add ------------------------------------
    if operation == "add" and name and a_type:
        dupe = _existing(type=a_type).filter(
            ArchiMateElement.name.ilike(name)
        ).first()
        if dupe is not None:
            errors.append(
                f"a {a_type} named {name!r} already exists in this org "
                f"(id={dupe.id}); propose a modify or a distinct name rather than "
                f"re-inventing it"
            )
        else:
            # Exact match is defeated by rephrasing, and silent NEAR-duplicate
            # proliferation is how a system of record rots. Warn the approver of
            # the closest lexical match (reusing the platform's duplicate utils —
            # whose fuzzy path this change also repairs). Lexical only: synonyms
            # (Billing vs Invoicing) are the embedding tier's job, not this one.
            from app.modules.duplicate_detection.services.duplicate_detection_utils import (
                DuplicateDetectionUtils,
            )

            best = None
            for (other,) in _existing(type=a_type).with_entities(
                ArchiMateElement.name
            ).all():
                if not other or other.strip().lower() == name.lower():
                    continue
                is_near, score = DuplicateDetectionUtils.is_duplicate(
                    name, other, mode="fuzzy", threshold=NEAR_DUPLICATE_THRESHOLD
                )
                if is_near and (best is None or score > best[0]):
                    best = (score, other)
            if best is not None:
                warnings.append(
                    f"{a_type} {name!r} closely resembles existing {best[1]!r} "
                    f"({int(best[0] * 100)}% similar) — confirm it is genuinely "
                    f"distinct, not a rephrased duplicate"
                )

    # 4. cross-layer coherence (ADVISORY) -------------------------------------
    # Architecture is the relationships: an element that is well-formed and
    # non-duplicate can still be *incoherent* with the model around it — a
    # capability with nothing below that could realize it, an anchor in a layer
    # that cannot validly relate to the proposed one. These are judgement aids
    # for the approver, never hard blocks, because ArchiMate permits far more
    # cross-layer wiring than any deterministic rule should presume to forbid.
    from app.modules.genome.patch.coherence import assess_coherence

    warnings.extend(
        assess_coherence(
            element, provenance, operation, _existing, ArchiMateElement, _resolve_anchor
        )
    )

    return GroundingResult(errors, warnings)
