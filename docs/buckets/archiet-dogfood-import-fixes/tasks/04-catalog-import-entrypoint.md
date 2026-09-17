# Task 04 — Catalog import entrypoint (R5)

Handoff target: `builder` → `refuter`
Branch: `fix/archiet-dogfood-import` · separate PR · **land last**

## Objective

Put an "Import model (OEF XML)" action on the Element Catalog header and empty
state, rendering the existing OEF import panel, so a user can go from
`/architecture/elements` to a completed import in one click and land back on
the catalog with updated counts.

Land last: this exposes tasks 01-03's work to the user. Wiring the entry point
before the panel behind it is correct would ship a visible broken journey.

## Context — two corrections to the brief

### C1 — the panel is an orphan, not "reachable only from job_detail"

The brief says `app/templates/solutions/partials/_import_preview.html` is
reachable from `batch_import/job_detail.html`. It is not.
`app/templates/batch_import/job_detail.html:161` includes a **different file**:

```jinja
{% include 'batch_import/partials/_import_preview.html' %}
```

Both templates exist. `solutions/partials/_import_preview.html` is included by
**nothing** in the repo — grep confirms zero includes. So this task is not
"add a second entry point to a working panel", it is "wire an orphaned panel
in for the first time", and **the panel's own behaviour has never been
exercised by a browser test**. Do not assume it works. Verify each control in
it before claiming the journey.

The panel does post to real, registered endpoints —
`/solutions/import/archimate/preview` and `/execute`
(`_import_preview.html:221,249`, routes at
`app/modules/solutions_strategic/v2/routes/solution_import_routes.py:21,60`,
on `solution_design_bp` with `url_prefix=/solutions`).

**First decide, per ADR 0008, whether two import-preview partials should
exist at all.** Read both. If they are the same panel forked, reconcile to one
and state the other's fate; if `batch_import`'s is genuinely a different thing
(a job-result view rather than an upload panel), say so and keep both with a
comment at each explaining the distinction. Do not add a third.

### C2 — two routes are registered at `/architecture/elements`

- `architecture_crud.list_elements`
  (`app/modules/architecture/routes/architecture_crud_routes.py:51`) — computes
  `layer_stats`, data-quality counts, and renders
  `architecture/elements.html` with everything the page needs.
- `unified_low_priority.architecture_elements`
  (`app/routes/unified_low_priority_routes.py:95`) — renders the same template
  with only `elements=`, so `layer_stats` would be undefined.

Which one serves is decided by blueprint registration order and `url_prefix`,
neither visible to a reader of either file — the exact defect class ADR 0008
names. Note `architecture_crud_routes.py:1-4` declares itself `DEPRECATED ...
kept as fallback`, yet it is the one with the working stats: **do not trust
that header**, determine by boot which rule actually serves `/architecture/elements`.

**Boot the app and check `url_map` before adding a control.** Adding the button
to the template is not enough if the serving route does not pass what the
control needs. Record which rule wins, add the control to the surface that
actually renders, and state the loser's fate (retire it, or explain why both
remain). This is a genuine ADR 0008 finding surfaced by this bucket — if
retiring it is out of scope, say so explicitly rather than leaving it
undocumented.

## Constraints

- ADR 0008: extend the existing catalog page and the existing OEF panel. No
  new import page, no third preview partial, no duplicate route.
- **The diagram importer stays separate** (customer's explicit instruction).
  This action imports a *model*; do not merge it with or route it through any
  diagram-import flow.
- DESIGN.md is the UI contract — read it before editing the template. No
  native `confirm()`/`alert()`; notifications via `Platform.toast`; no
  `onclick=` attributes (this repo's CSP kills inline handlers silently — use
  Alpine `@click` or `data-` attributes); typed buttons; token colours only.
  If new Tailwind classes are introduced, rebuild CSS
  (`python scripts/build_css.py`) or `css-build` fails.
- `fetch` must go through `Platform.fetch` (`raw-fetch-sites` ratchet @ 0) and
  check the response (`if (!response.ok) throw`).
- The **empty state** matters as much as the header: a catalog with zero
  elements is exactly when a user needs the import action, and it is the state
  most likely to have been left unwired. Check what the page currently renders
  at zero elements before writing.
- `breadcrumb-coverage` and `shell-conformance` must not regress.
- Any new persona-visible route extends
  `tests/smoke/test_authorisation_matrix.py`, naming which archetypes should
  and should not reach it. If no new route is added, extend
  `tests/smoke/test_archetype_journeys.py` instead.

## Deliverable

1. An "Import model (OEF XML)" control on the Element Catalog header
   (`app/templates/architecture/elements.html`), rendering the existing OEF
   panel — as a modal/drawer on the catalog, or as a one-click navigation to
   a surface that already exists. One click from `/architecture/elements` to
   the panel.
2. The same action offered from the catalog's empty state.
3. After a successful import the user lands back on the catalog with counts
   reflecting the import (a reload is acceptable; a stale count is not).
4. A recorded decision on the two `_import_preview.html` partials and on the
   duplicate `/architecture/elements` route — in the PR description and as a
   comment at the relevant code sites.
5. Access control consistent with the rest of the catalog's write surface —
   check what `architecture_crud`'s write routes require
   (`@require_roles("admin", "architect")`, e.g.
   `architecture_crud_routes.py:145`) and do not let a viewer import a model.

## Acceptance criteria

Verbatim from the customer's brief:

- **R5**: from `/architecture/elements`, reach the OEF panel in one click,
  preview, import, land back on the catalog with new counts.

Additionally:

- The empty-state path is demonstrated too, not only the header path.
- A non-permitted archetype cannot reach the import action or the execute
  endpoint, asserted in `tests/smoke/test_authorisation_matrix.py`.
- `python scripts/verify.py` (bare) green, including `dead-interactions`
  (must be 0 — a control that silently does nothing is the exact defect this
  task risks introducing), `ui-contract`, and `broken-surfaces`.
- Playwright, as a permitted persona: start at `/architecture/elements`, click
  the real control **once**, upload
  `tests/fixtures/oef/archiet_shaped.xml`, click preview, click import, then
  **reload** and assert the catalog counts include the imported elements.
  A `curl` against the endpoint does not satisfy this.

## Handoff target

`refuter` — review focus: that the control is genuinely one click and not a
dead handler; that the empty state is wired, not just the header; that the
duplicate route and duplicate partial were resolved or explicitly documented
rather than ignored; and that the browser test reloads before asserting.
