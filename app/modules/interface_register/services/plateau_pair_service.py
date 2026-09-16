"""Service for managing As-is/To-be plateau pairs for interface comparison."""

from __future__ import annotations

from flask import g
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.implementation_migration import Plateau
from app.modules.interface_register.services.interface_register_service import (
    resolve_initiative,
)
from app.services.archimate_backbone import sync_archimate_element

ASIS_PLATEAU_NAME = "Current Integration Landscape"
TOBE_PLATEAU_NAME = "S/4HANA-Integrated Landscape"


def get_plateau_pair(initiative_id) -> tuple | None:
    """Get the As-is/To-be plateau pair for an initiative.

    Keyed on initiative_id, not architecture_id: TechnologyRoadmapInitiative.
    architecture_id is a non-unique FK, so two initiatives can legitimately
    share one ArchitectureModel. Keying on architecture_id alone would
    silently resolve both initiatives to the same plateau pair, leaking one
    initiative's gaps onto the other's comparison screen.

    Returns:
        tuple: (as_is_plateau, to_be_plateau) if both exist, None otherwise
    """
    # resolve_initiative raises if the initiative doesn't exist/isn't in the
    # caller's org -- calling it here (even though its return value is only
    # used for the org-scoping side effect on the query below via
    # initiative_id being an FK we already trust) keeps 404 behaviour
    # consistent with the rest of this module for a bad/foreign id.
    resolve_initiative(initiative_id, g.current_org_id)

    # Look up the as-is plateau -- ordered by id so a pre-unique-index
    # duplicate (from before this fix) resolves deterministically to the
    # oldest pair rather than an arbitrary row.
    as_is = (
        Plateau.query.filter_by(
            initiative_id=initiative_id,
            name=ASIS_PLATEAU_NAME,
            sequence_order=1,
        )
        .order_by(Plateau.id.asc())
        .first()
    )

    if not as_is:
        return None

    # Look up the to-be plateau
    to_be = (
        Plateau.query.filter_by(
            initiative_id=initiative_id,
            name=TOBE_PLATEAU_NAME,
            sequence_order=2,
            baseline_plateau_id=as_is.id,
        )
        .order_by(Plateau.id.asc())
        .first()
    )

    if not to_be:
        return None

    return (as_is, to_be)


def provision_plateau_pair(initiative_id) -> tuple:
    """Create the As-is/To-be plateau pair for an initiative.

    Idempotent under concurrency: a unique partial index
    (uq_plateau_initiative_scope, on (initiative_id, name, sequence_order)
    WHERE initiative_id IS NOT NULL) is the actual guarantee, not the
    read-before-write check below -- two concurrent requests can both pass
    the initial get_plateau_pair() check under READ COMMITTED, but only one
    INSERT can win; the loser's IntegrityError is caught and the function
    re-reads and returns the winner's row instead of raising.

    Returns:
        tuple: (as_is_plateau, to_be_plateau)
    """
    existing_pair = get_plateau_pair(initiative_id)
    if existing_pair:
        return existing_pair

    initiative = resolve_initiative(initiative_id, g.current_org_id)

    try:
        as_is = Plateau(
            name=ASIS_PLATEAU_NAME,
            architecture_id=initiative.architecture_id,
            initiative_id=initiative_id,
            sequence_order=1,
        )
        db.session.add(as_is)
        db.session.flush()  # Get the ID without committing

        sync_archimate_element(
            as_is,
            provenance={
                "source_model": "InterfaceRegisterComparison",
                "initiative_id": initiative_id,
            },
        )

        to_be = Plateau(
            name=TOBE_PLATEAU_NAME,
            architecture_id=initiative.architecture_id,
            initiative_id=initiative_id,
            sequence_order=2,
            baseline_plateau_id=as_is.id,
        )
        db.session.add(to_be)
        db.session.flush()  # Get the ID without committing

        sync_archimate_element(
            to_be,
            provenance={
                "source_model": "InterfaceRegisterComparison",
                "initiative_id": initiative_id,
            },
        )

        db.session.commit()
        return (as_is, to_be)
    except IntegrityError:
        # Lost the race to a concurrent provisioner -- the unique partial
        # index rejected our insert, not a real error. Re-read and return
        # the winning pair rather than raising or leaving an orphan.
        db.session.rollback()
        winner = get_plateau_pair(initiative_id)
        if winner is None:
            # Genuinely unexpected: the index fired but no complete pair is
            # visible yet (e.g. the other transaction hasn't committed the
            # second row). Surface this rather than silently returning None.
            raise
        return winner
    except Exception:
        db.session.rollback()
        raise
