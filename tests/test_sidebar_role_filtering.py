"""The shipped sidebar must show each archetype only its own sections.

HISTORY (shell-overhaul Wave 1, Task 3): `role_access.py` had defined
ROLE_SECTION_ACCESS for all nine enterprise roles since NS-006, and
`can_access_section` had been registered as a Jinja global - but the sidebar
that actually shipped, `components/admin_sidebar_northstar_phase2.html`
(included unconditionally by `layouts/admin_base.html` and therefore by 293
templates), never called it. Only `components/admin_sidebar.html` did, and
that file was included by `composer_base.html`, used by two templates.

The effect was that all nine archetypes saw one identical 92-link
navigation: the Enterprise Architect's, plus Administration. Two archetypes
- Procurement and Application Manager - had complete, correctly-guarded
modules (20 routes between them) that no link in the product pointed at.

MIGRATION (shell-overhaul Wave 3, Task 5): Task 3's fix replaced the
ROLE_SECTION_ACCESS / SECTION_HEADINGS taxonomy this file used to assert
against with a completely different model -
`app.utils.role_access.get_sidebar_zones(current_user)`, whose zones (Home,
My work, Library, Governance, Admin - see `_ZONE_TITLES`) share no headings
with the old SECTION_HEADINGS map (Home, Solutions, Portfolio, Architecture,
Governance, Data & Integration, Procurement, My Applications). Re-pointing
this file's `render_template("components/admin_sidebar_northstar_phase2.html", ...)`
call at `components/admin_sidebar.html` while keeping its old assertions
would therefore fail for the right reason but the wrong test: every
assertion here is about a taxonomy the shipped sidebar no longer has.

`admin_sidebar_northstar_phase2.html` has now been deleted outright (dead
since Wave 1 Task 3, confirmed by grep - nothing includes it). Real,
per-role sidebar-filtering coverage against the template that actually
ships now lives in `tests/test_sidebar_render.py`, which hits
`/dashboard/overview` as a logged-in user of each flagship persona and
asserts on `get_sidebar_zones` output (budget, zone presence/absence,
guarded-link zone suppression, All-modules fallback). This file is kept
only to pin that the dead template does not silently reappear.
"""

from __future__ import annotations

import os


def test_dead_northstar_phase2_sidebar_template_is_gone():
    """Guards against the deleted dead-code template being recreated by a
    merge/rebase without anyone noticing - see module docstring for why its
    replacement, test_sidebar_render.py, is the real coverage now."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(
        root, "app", "templates", "components", "admin_sidebar_northstar_phase2.html"
    )
    assert not os.path.exists(path), (
        "admin_sidebar_northstar_phase2.html was deleted as dead code "
        "(shell-overhaul Wave 3, Task 5) - if it's back, either it's an "
        "accidental merge artifact (delete it again) or someone reinstated "
        "it as a real feature (then this test, and this file's docstring, "
        "need updating alongside tests/test_sidebar_render.py)."
    )
