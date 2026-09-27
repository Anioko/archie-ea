"""
ADM phase -> SAP Activate stage mapping.

Display-only labelling, not a second phase model: TOGAF ADM remains the
system of record for phase governance (app/models/adm_kanban.py,
app/services/kanban_projection_service.py). This module is the single place
that says which Activate stage a given ADM phase code corresponds to, so a
steering-committee-facing screen can show Activate language without renaming
the ADM phases architects work against.

Source: Capgemini SAP S/4HANA Platform Suitability Assessment (10 Sep 2026),
Stage 1 recommendation 7.1 / risk register row 1 (ADM/Activate label
confusion).
"""

ADM_PHASE_TO_ACTIVATE_STAGE = {
    "PRELIM": "Prepare",
    "A": "Prepare",
    "B": "Explore",
    "C": "Explore",
    "D": "Explore",
    "E": "Realize",
    "F": "Realize",
    "G": "Deploy",
    "H": "Run",
    "REQ": "Run",
}


def get_activate_stage(phase_code: str) -> str | None:
    """SAP Activate stage for an ADM phase code, or None if unmapped."""
    return ADM_PHASE_TO_ACTIVATE_STAGE.get(phase_code)
