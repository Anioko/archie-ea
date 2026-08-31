"""Compatibility shim. The Architecture Decision Record model lives next door.

This module used to declare a SECOND ArchitectureDecision class mapped to the
same `architecture_decisions` table as app/models/architecture_decision.py. The
file's own comment recorded what that cost:

    "Both classes share one Table via extend_existing, so whichever imports last
     wins, and declaring NOT NULL here made the effective spec depend on import
     order."

A schema whose effective definition depends on module import order is not a
schema. The class here declared 20 columns against the canonical class's 32, so
anything holding this one could not see twelve of the table's fields --
including decision_id, adm_phase, authority_level and the ARB session link.

Resolved 31 Aug 2026 by making this a re-export: one mapped class, one Table,
one definition. Nothing imported this module directly (measured: zero call
sites), so nothing needed repointing -- but the name is kept so that any path
that finds it still lands on the canonical model rather than a stale copy.
"""

from app.models.architecture_decision import ArchitectureDecision  # noqa: F401

__all__ = ["ArchitectureDecision"]
