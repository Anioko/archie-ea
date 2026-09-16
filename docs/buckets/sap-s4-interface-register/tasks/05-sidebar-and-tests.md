# Task 05 — Sidebar entry, section-map de-duplication, and the full browser walkthrough (US-7)

## Objective

Make the register findable by the persona who needs it, collapse the two
disagreeing copies of section-to-role access into one, and demonstrate the
whole journey in a real browser. This is the only task that may report the
feature done.

## Context

Extends:
- **`app/utils/role_access.py`** — `NAVIGATION_SECTIONS` (line 29),
  `ROLE_SECTION_ACCESS` (line 51), `_MY_WORK_LINKS`, `SIDEBAR_LINK_BUDGET`.
- **`app/_bootstrap/context_processors.py`** — `ENTERPRISE_ROLE_SECTION_MAP`
  (line 457), consumed at lines 536–537.
- **`app/templates/components/admin_sidebar.html`** — the existing
  `selectattr('endpoint', 'in', flask.current_app.view_functions)` filter at
  ~line 150 already drops an unregistered link safely; no extra `{% if %}` is
  needed *in the sidebar*.
- **`tests/smoke/`** — `conftest.py`'s eleven canonical `ARCHETYPES`,
  `test_authorisation_matrix.py`, `test_archetype_journeys.py`.

Two decisions already made for you (`implementation-plan.md` §4) — implement,
do not re-litigate:
- **No twelfth enterprise persona.** `integration_architect` exists as a
  `role_archetype` key (`context_processors.py:443`) but not as an
  `enterprise_role`, and this feature does not widen that. The Integration
  Architect actor maps to `solution_architect` / `enterprise_architect`.
- **No enterprise-architect sidebar link.** The comment at
  `role_access.py:468-479` records EA at exactly 25 rendered links and requires
  a new one to be paid for by retiring an existing one. EA reaches the register
  via Library / All modules.

## Constraints

- **Do not add a third copy** of section-to-role access and do not edit only
  one side.
- **No new section.** `data_integration` already exists in
  `NAVIGATION_SECTIONS` (line 40) and is already granted to
  `solution_architect`, `enterprise_architect`, `business_architect` and
  `platform_admin`.
- The `sidebar-links` ratchet is 27 against `SIDEBAR_LINK_BUDGET = 28`. The
  solution-architect My-work zone holds 6 links; this is a 6→7 change that must
  move neither number. If it does, stop and escalate rather than raising the
  ratchet.
- Label and icon must be distinguishable at a glance, including collapsed. Do
  **not** label it "Integrations" — that already names the outbound-connector
  admin surface, and "Integ…" vs "Interf…" is not distinguishable.
- Read `DESIGN.md` before touching the sidebar template. Rebuild CSS with
  `python scripts/build_css.py` if any class changed.

## Deliverable

1. **`app/_bootstrap/context_processors.py`** — replace the literal
   `ENTERPRISE_ROLE_SECTION_MAP` dict with a derivation:
   ```python
   from app.utils.role_access import ROLE_SECTION_ACCESS

   _LEGACY_SECTION_ALIASES = {
       "enterprise_architect": {"application", "tools", "data", "utilities"},
       "portfolio_manager": {"application", "tools"},
       "procurement": {"application"},
       "application_manager": {"application"},
       "platform_admin": {"application", "tools", "data", "utilities", "admin"},
   }
   ENTERPRISE_ROLE_SECTION_MAP = {
       role: sections | _LEGACY_SECTION_ALIASES.get(role, set())
       for role, sections in ROLE_SECTION_ACCESS.items()
   }
   ```
   Add a comment naming this as the ADR-0008 correction: one system of record
   for "which sections does this role see". Note the deliberate consequence —
   `security_architect` and `data_architect`, which had entries in
   `ROLE_SECTION_ACCESS` and none here, now get their declared sections instead
   of falling through to the archetype map. Verify that consequence in a
   browser as each of those two personas before claiming the change is inert.
2. **`app/utils/role_access.py`** — one link added to
   `_MY_WORK_LINKS[ROLE_SOLUTION_ARCHITECT]`: label **"Interface Register"**,
   endpoint `interface_register.index`, section `data_integration`, icon
   `cable` (distinct from `git-merge`, `git-branch`, `waypoints`, `milestone`
   already in use). Nothing added for any other role.
3. **`tests/smoke/test_authorisation_matrix.py`** — add rows for all four GET
   routes (`interface_register.index`, `.new`, `.comparison`, `.costing`)
   across the eleven canonical archetypes: `solution_architect`,
   `enterprise_architect`, `business_architect` and `platform_admin` reach
   them; `procurement` and `application_manager` do not. Plus the §8.2 negative
   cases: an `initiative_id` belonging to another org resolves to 404, and an
   initiative with `architecture_id IS NULL` resolves to 404 — not to a visible
   page.
4. **`tests/smoke/test_archetype_journeys.py`** — consolidate Tasks 02–04's
   extensions into one end-to-end solution-architect journey that clicks real
   controls: sidebar link → register → create an interface → confirm it renders
   as an ArchiMate element on the element detail page → provision the As-Is/
   To-Be pair → raise a gap → attach a costed work package → **reload** →
   assert the rollup total changed. This journey *is* the acceptance criterion.
5. **`tests/smoke/test_rendered_legibility.py` / accessibility** — confirm the
   four new screens pass the axe-core audit without moving
   `tests/smoke/a11y_baseline.json`, and that the collapsed sidebar shows the
   new entry distinguishably (label not clipped to an ambiguous prefix, icon
   not a duplicate).

## Acceptance Criteria

- `python scripts/verify.py` bare and green — explicitly including
  `sidebar-links` (ratchet unmoved at 27), `nav-coverage`, `nav-verified`,
  `breadcrumb-coverage`, `duplicate-breadcrumb`, `shell-conformance`,
  `store-agreement`, `smoke-coverage-on-change`.
- `pytest tests/journeys/test_journey_persona_sections.py -q` passes — it
  asserts against `ENTERPRISE_ROLE_SECTION_MAP` directly and is the test most
  likely to catch a bad derivation.
- `pytest tests/smoke/ -q` passes locally, including the webkit journey run.
- `gh run list --limit 5` confirms CI green before anything is called done — do
  not rely on a local run or a memory note.
- The journey in deliverable 4 is demonstrated: a passing Playwright run, not a
  status line. "Green and deployed" is necessary, not sufficient.
- Then deploy, per "Done means deployed": `scripts/deploy_verified.sh <ref>`,
  and confirm the live site serves the register in the same session. Do not end
  by offering deployment as an option.

## Handoff target

`builder` → `qa-lead` (end-of-wave browser pass), then `release-manager`.
