# Implementation Plan — Archiet Customer-Zero Dogfood Import Fixes

Bucket: `docs/buckets/archiet-dogfood-import-fixes/`
Source brief: `brief.md` (customer report, DOGFOOD-001..005)
Author: tech-lead · 17 Sep 2026
Handoff target: `builder` (per task), `refuter` review per task

## Branch

All work lands on `fix/archiet-dogfood-import` — **not** `main`, matching the
`sap-s4-interface-register` convention. `main` receives a task's work only
after `refuter` approval. tech-lead has no shell in this session, so the
branch does not exist yet: **builder creates it first**:

```
git checkout -b fix/archiet-dogfood-import
```

One PR per task (R1+R2 combined per the customer's own instruction).

## Verification findings — read before starting

The brief's file:line references were re-verified against current code during
this planning pass. All were accurate, and **five further findings** change
the shape of the work. These are corrections to the brief, not optional
context.

### F1 — R3's layer mismatch is confirmed, and worse than "a tile reads 0"

`ArchiMateImportService.TYPE_TO_LAYER` (`app/services/archimate_import_service.py:91-95`)
writes the literal `"Implementation & Migration"`. The catalog route
`architecture_crud.list_elements`
(`app/modules/architecture/routes/architecture_crud_routes.py:51-140`) builds
`_LAYER_ORDER` containing `"Implementation"` (line 70) and looks each tile up
in `count_map`, which is keyed on `lower(stored layer)` (line 79). So
`"implementation"` misses `"implementation & migration"` entirely.

Consequence, stated precisely: those 35 elements are counted in **no tile at
all**, so the tiles do not merely show a wrong number — they do not sum to the
total. The template confirms the same on the filter half:
`app/templates/architecture/elements.html:200` and `:488` both emit
`<option value="implementation">`, and `:628` computes `totalCount` as the sum
of the tiles — i.e. the headline total is itself computed from the broken map.

### F2 — `store-agreement` is NOT a registered gate

The brief (and root `CLAUDE.md`) describe `store-agreement` as "registered
31 Aug 2026 and ratcheted at 1". It is not. `scripts/check_store_agreement.py`
exists, but grepping `Gate("` in `scripts/verify.py:build_gates()` returns 56
gates and **none of them is `store-agreement`** — it is one of the checks
counted by the `unregistered-checks` ratchet (`scripts/check_unregistered_checks.py:13`
names it explicitly). R3 must therefore *create and register* its enforcement,
not extend something already running. See task 02.

### F3 — R1 has FIVE relationship-validation authorities, not two

The brief says two exist and must be reconciled. Found:

1. `ArchiMateImportService.VALID_RELATIONSHIP_TYPES` — flat `frozenset` of 11 OEF names (`archimate_import_service.py:99`)
2. `VALID_RELATIONSHIPS` in `app/models/archimate_core.py:212` — `(type, source_layer, target_layer) → bool`
3. `ARCHIMATE_RELATIONSHIP_TYPES` + `_normalize_rel_type` used by `POST /archimate/api/relationships` (`app/modules/architecture/routes/archimate_routes.py:1417-1427`)
4. `app/config/archimate_relationship_matrix.py` — `VALID_RELATIONSHIPS` at **element-type** granularity, plus `RELATIONSHIP_CARDINALITY`, `get_valid_relationships`, `get_all_valid_targets_for_source`
5. `RelationshipValidator` (`app/modules/architecture/services/relationship_validator.py`) and a grammar validator in `architecture_assistant/services/relationship_grammar_validator.py`

**Tech-lead ruling (#4/#5 is authoritative).** `app/config/archimate_relationship_matrix.py`,
consumed via `RelationshipValidator.validate_relationship(source_type,
target_type, relationship_type)`, is the system of record for relationship
validity. Rationale: it is the only one keyed on *element type* rather than
layer, which is the actual ArchiMate 3.2 constraint (the layer-triple matrix
in `archimate_core.py` cannot express that `Composition` is legal
BusinessProcess→BusinessProcess but the metamodel treats a
BusinessActor→BusinessObject composition differently); it carries cardinality;
and it already returns `suggestions`, which R4a needs verbatim for its
"suggested fix" column. The importer must call it and must not grow a sixth
table. See task 01 for the required disposition note on #1–#3.

### F4 — the R5 panel is an orphan, not "only reachable from job_detail"

The brief says `app/templates/solutions/partials/_import_preview.html` is
reachable from `batch_import/job_detail.html`. It is not.
`job_detail.html:161` includes a **different file** —
`batch_import/partials/_import_preview.html`. Both files exist; the
`solutions/` one is included by nothing in the repo. So R5 is not "add a
second entry point to a working panel", it is "wire an orphaned panel in for
the first time" — which also means the panel's own behaviour has never been
exercised by a browser test and cannot be assumed to work.

The panel posts to `/solutions/import/archimate/preview` and `/execute`
(`_import_preview.html:221,249`), which are real and registered on
`solution_design_bp` (`app/modules/solutions_strategic/v2/routes/solution_import_routes.py:21,60`).

### F5 — two routes are registered at `/architecture/elements`

`architecture_crud.list_elements` (`architecture_crud_routes.py:51`, the rich
one computing `layer_stats`) and `unified_low_priority.architecture_elements`
(`app/routes/unified_low_priority_routes.py:95`, which renders the same
template with only `elements=`). Which serves is decided by blueprint
registration order — exactly the ADR 0008 defect class. R5 must confirm by
boot which one serves before adding a control to it, and record the other's
fate. Note `architecture_crud_routes.py:1-4` marks itself `DEPRECATED ...
kept as fallback`, yet it is the one with the working stats — do not take that
header at face value.

### F6 — ADR 0009 confirmed: no `status`/`source`/`as_of` mapping exists

Read in full. ADR 0009 is about scheduled drift detection and does propose
**model age** as the success measure ("the distribution of time since each
element was last confirmed against a source", line 94-97) — which is the
nearest thing to the customer's `as_of`, but it defines no field, no key
names and no storage location. Nothing else in the tree defines one. The
customer's "(ADR 0009)" reference is aspirational. Task 01 proposes a minimal
convention rather than blocking; see its "Open question" section.

## Escalations — do not let the builder decide these

| # | Question | Owner | Blocking? |
|---|---|---|---|
| E1 | **R4c**: widen `ArchiMateElement.name` from `String(100)` to `String(255)`, or keep 100 and rely on preview validation? | founder / product | **No** — ship 01–04 first |
| E2 | Is the new `custom_properties` key convention (task 01) worth an ADR 0010, or an addendum to 0009? | solution-architect during implementation | No |

**E1 recommendation (tech-lead): ship (a) and (b) now, decide (c) after.**
Preview validation and savepoint-per-element partial commit are correct at
*either* name length — they change how a violation is reported, not what the
limit is. They also make the decision cheaper to take later, because after
they land the founder can see exactly which of their real elements the limit
bites, with the elements named, instead of choosing a number in the abstract.
Widening first would hide that evidence. Task 03 carries the escalation text.

## Ordered tasks

| # | Task | Covers | File |
|---|---|---|---|
| 01 | Relationship import + element properties | R1, R2 | `tasks/01-relationships-and-properties.md` |
| 02 | Layer vocabulary unification | R3 | `tasks/02-layer-vocabulary-unification.md` |
| 03 | Preview validation + partial commit | R4 | `tasks/03-preview-validation-and-partial-commit.md` |
| 04 | Catalog import entrypoint | R5 | `tasks/04-catalog-import-entrypoint.md` |

Order is the customer's (R1→R2→R3→R4→R5) and is also the dependency order:
02 normalises the layer values that 01's relationship validation reads, but
01's validator is keyed on element *type*, so they do not block each other and
01 may land first as the customer asked. 04 is last because it exposes
01–03's work to the user; wiring the entry point before the panel is correct
would ship a visible broken journey.

## Fixture — the real model is not in this repo

`ground-truth/model/archiet.archimate` is Archiet's proprietary file and is
not here. Every task builds against a **synthetic** OEF fixture at
`tests/fixtures/oef/archiet_shaped.xml`, constructed to the shape the
acceptance criteria describe: ~168 elements spanning all six layers plus
Other, ~121 relationships including at least three the metamodel must reject,
at least one element carrying `<properties>` in the `M-CON-10G-FREE-PILOTS`
shape (`status`, `source`, `layer`), and at least one element with a
>100-character name. Task 01 creates it; 02–04 extend it.

**Say so plainly in every result doc: these tests pass against a synthetic
file.** The actual acceptance gate is the customer's own re-test with their
real model against the deployed instance, logged in
`docs/dogfood/ARCHIET-CUSTOMER-ZERO.md`. That file is created by this plan as
an empty template with no row pre-filled as passing — this pipeline does not
self-certify against the customer's gate.

## Cross-cutting constraints (every task)

- **ADR 0008** — name the system of record before writing. No task may add a
  second table, route, macro or vocabulary answering a question something
  already answers. Where a duplicate is found, retire it or state why both
  remain.
- **Schema** — `reconcile-schema` is ADD-COLUMN-only and adds nullable
  columns without backfill. No non-nullable column, no column requiring a
  backfill to be correct. Code tolerates `NULL`.
- **Tenancy** — `ArchiMateElement` carries `TenantMixin`; do not hand-write
  `organization_id` predicates on it inside a request. `ArchiMateRelationship`
  as defined in `archimate_core.py` does **not** carry `TenantMixin` — task 01
  must check the normal-runtime mapping in `app/models/models.py` before
  assuming either way, and must not leak relationships across orgs.
- **Never invent data** — a missing property renders as `—`, never `0` or a
  plausible substitute. `fetch` does not reject on 404: `if (!response.ok) throw`.
- **Done means DEMONSTRATED** — each task ends with a Playwright test in
  `tests/smoke/` that clicks the real control and asserts the result persisted
  **after a reload**. A green unit test is not sufficient and the builder is
  never the sole verifier.
- **Verification** — bare `python scripts/verify.py` before any deploy claim,
  never a `--tag` subset. Any new persona-visible route extends
  `tests/smoke/test_authorisation_matrix.py`.
- **Staging** — `git add <file>`, never `git add -A`.
