"""Pure tests over _orphan_link_choice: which connected layer an orphan
element links to, and with what relationship type, once its stored layer
value has been resolved through ArchiMateLayer.canonical the same way
_link_orphan_elements resolves it before looking anything up in
VALID_RELATIONSHIPS. No database is needed.
"""

from __future__ import annotations

import pytest

from app.models.archimate_core import VALID_RELATIONSHIPS
from app.models.constants import ArchiMateLayer
from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import (
    _orphan_link_choice,
)


@pytest.mark.parametrize(
    "stored_spelling", ["implementation", "Implementation", "implementation_migration"]
)
def test_orphan_on_implementation_migration_links_to_motivation_by_realization(stored_spelling):
    """An orphan Work Package on Implementation & Migration, with one
    connected Motivation element, links by Realization -- for every stored
    spelling of the seventh layer.
    """
    orphan_layer = ArchiMateLayer.canonical(stored_spelling)
    connected_layers = [ArchiMateLayer.canonical("motivation")]

    chosen_layer, relationship_type = _orphan_link_choice(
        orphan_layer, connected_layers, VALID_RELATIONSHIPS
    )

    assert chosen_layer == "motivation"
    assert relationship_type == "Realization"


@pytest.mark.parametrize(
    "orphan_spelling, connected_spelling",
    [
        ("implementation", "implementation_migration"),
        ("implementation_migration", "implementation"),
    ],
)
def test_same_layer_different_spelling_links_by_association(orphan_spelling, connected_spelling):
    """An orphan and a connected element genuinely on the same layer, stored
    under two different spellings of that layer's name, must still meet --
    linking by Association, the same way two rows stored under the identical
    spelling already do.
    """
    orphan_layer = ArchiMateLayer.canonical(orphan_spelling)
    connected_layers = [ArchiMateLayer.canonical(connected_spelling)]

    chosen_layer, relationship_type = _orphan_link_choice(
        orphan_layer, connected_layers, VALID_RELATIONSHIPS
    )

    assert chosen_layer == "implementation_migration"
    assert relationship_type == "Association"


def test_control_untouched_layers_return_todays_result():
    """An orphan on motivation with a connected strategy element -- a
    pairing this task does not touch -- resolves exactly as it does today.
    """
    chosen_layer, relationship_type = _orphan_link_choice(
        "motivation", ["strategy"], VALID_RELATIONSHIPS
    )

    assert chosen_layer == "strategy"
    assert relationship_type == "Association"


def test_no_matrix_entry_either_direction_returns_no_link():
    """An orphan on Implementation & Migration with a connected business
    element has no matrix entry for the pairing and returns no link, as it
    does today.
    """
    chosen_layer, relationship_type = _orphan_link_choice(
        "implementation_migration", ["business"], VALID_RELATIONSHIPS
    )

    assert chosen_layer is None
    assert relationship_type is None
