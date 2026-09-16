# Archiet Ltd — customer zero dogfood log

Archiet Ltd runs its own company on Archie. The company's enterprise model (ArchiMate 3.2, all layers,
168 elements / 121 relationships as of 2026-09-17, source `archiet-strategy/ground-truth/model/`) is the
single machine-checkable truth its AI workforce must obey. Every place Archie does not yet serve that
job for a company of this size is written here as **problem → evidence → why it matters → solution →
status**, then fixed through Archie's own workforce and gates, and re-tested by clicking in the deployed
instance (Phase 0 rule in `docs/ROADMAP_TO_BEST_IN_CLASS.md`: done = demonstrated, not green).

Instance: `https://165-22-125-156.sslip.io` (build `2ba4aa1a`). Tenant: Archiet Ltd. Tester: the
strategy agent (`claude-code:cloud-credits-campaign`) in the founder's logged-in session, 2026-09-16 23:30–23:59Z.

## Job 1 — import the company model (OEF XML) and see it in the catalog

| # | Problem | Evidence | Why it matters for a small company | Solution | Status |
|---|---|---|---|---|---|
| DOGFOOD-001 | **Preview says "0 errors", execute fails wholesale.** One element name > 100 chars aborts the whole import: `created: 0`, raw SQL in the error (`StringDataRightTruncation ... character varying(100)`), transaction rolled back. | `POST /solutions/import/archimate/preview` → `summary {new:168, conflict:0, errors:[]}`; `POST /solutions/import/archimate/execute` → `{"created":0,"errors":["Database commit failed: ... value too long for type character varying(100) ... INSERT INTO archimate_elements ..."]}`. Column: `app/models/archimate_core.py:58` `name = db.Column(db.String(100))`. Our longest name: 269 chars. | A founder's first contact with the product is an import; an all-or-nothing failure with a database error is the moment they leave. Real models have long names. | (a) Preview validates every DB constraint the execute will hit (name ≤ 100 → report per element with a suggested cut); (b) execute per element with savepoints and return HTTP 207 with the failed ids, never a raw SQL string; (c) product decision: widen `name` to 255 (every other layer model already uses 255 — `app/models/application_layer.py:72`). Workaround used: `build_archimate.py --max-name=100` (full name preserved in documentation). | OPEN |
| DOGFOOD-002 | **Implementation & Migration elements import but disappear.** Catalog tiles show Motivation 50 / Strategy 19 / Business 20 / Application 26 / Technology 18 / **Implementation 0** and "133 elements total" after importing 168. | Importer maps WorkPackage/Deliverable/ImplementationEvent/Plateau/Gap to layer `"Implementation & Migration"` (`app/services/archimate_import_service.py:91-95`); the catalog page (`app/modules/architecture/routes/archimate_routes.py`, `/architecture/elements`) counts and filters on `Implementation`. 35 elements are stored and invisible. | Work packages, deliverables and plateaus are the part of the model a small company changes weekly (deadlines, credits landing, migration steps). Invisible = unmaintained = stale. | One canonical layer vocabulary (ADR 0008 "one system of record per concept" applies to enums too): the importer writes the same layer key the catalog reads, and `store-agreement` gains a check that every stored `layer` value is one the UI renders. Migration to normalise existing rows. | OPEN |
| DOGFOOD-003 | **Relationships are parsed, previewed, then never written.** Preview reports 121 relationships; after execute `GET /archimate/api/relationships` → `total: 0`; catalog banner "No relationships: 168". | `parse_oef_xml` collects relationships (`archimate_import_service.py:213-242`); `preview_import` counts them (`:314`); `execute_import` (`:322+`) iterates elements only — no relationship insert; the execute result has no relationship count. | An ArchiMate model without relationships is a list. Serving, Realization and Influence are what let an agent answer "what depends on this" and "which ruling constrains that offer". | `execute_import` writes relationships after elements (resolve source/target by imported identifier, honour `valid-relationship-types`), returns `relationships_created`, and the preview/execute contract is symmetric. Test: import → count == preview count. | OPEN |
| DOGFOOD-004 | **OEF `<properties>` are dropped on import** — the element's `status` (VERIFIED/RULED/…), `source` (path:line or "founder ruling YYYY-MM-DD") and `layer` properties never reach the record. | Importer reads `<name>` and `<documentation>` only (`archimate_import_service.py:182`, `:460`); no `properties`/`propertyDefinitions` handling. Result: provenance for 168 elements lost at the door; 124 elements show "No description". | Provenance and model age (ADR 0009) are Archie's stated differentiators. If import discards the source of every fact, the genome starts unverifiable. For an AI workforce the `source` property is the whole point — it is what a claim check cites. | Import `<properties>` into the element's `properties` JSON (the column exists on `archimate_elements`), map a `status`/`source`/`as_of` convention onto model-age fields, and show them on the element detail page. Export must round-trip them. | OPEN |
| DOGFOOD-005 | **The OEF importer has no entry point in the catalog.** "Import a diagram" is the Lucid/Visio importer; the OEF panel (`app/templates/solutions/partials/_import_preview.html`) is only included in `batch_import/job_detail.html` when `show_preview` is set. A user with a `.archimate` file cannot find where to put it. | Catalog empty state offers "Open the Composer" or "sync from Abacus"; `_import_preview.html` include search → one template. This log's import was done by calling the endpoint from the page (`Platform.fetch`). | The first thing a company with an existing model does is import it. | An "Import model (OEF XML)" action on the Element Catalog and the empty state, rendering the existing panel. | OPEN |

**Job 1 verdict:** the endpoint works; the product around it does not yet. Import works only for a model
with ≤100-char names, and what arrives is elements without relationships, without provenance, and with
one layer hidden. Fix order: 003 (relationships) → 004 (properties) → 002 (layer) → 001 (validation) → 005 (entry point).

## Job 2 — read one element with its provenance (pending)
Blocked by DOGFOOD-004: there is no provenance to read yet. Next test after the fix: open
`M-CON-10G-FREE-PILOTS` and see `status: RULED`, `source: founder ruling 2026-07-19 — strategy/10G-…`, and its age.

## Jobs queued
3. Record a founder ruling as a Constraint from the UI (not via import) with source and date.
4. Ask the AI architect a claim-check question ("can a design partner be charged $10k?") and get the constraint back with its source — the `check_claim` job; today's copilot has no read tool over constraints (`docs/CAPABILITY_GAP_REGISTER.md` G1).
5. Export the model back to OEF and diff it against the import (round-trip).
6. Model age on the catalog: which elements were last confirmed > 14 days ago.
7. An agent-facing surface (MCP or REST with a token) for `get_facts` / `check_claim` / `propose_change`.

## Conventions
- One row per problem; evidence is a route + response, a `path:line`, or a screenshot in `docs/screenshots/dogfood/`.
- A row is CLOSED only when the job is re-run in the deployed instance and works when clicked.
- Product decisions raised here (e.g. widening `name`) are decided by the founder; the row records the decision and date.
