# Task 02 — Layer vocabulary unification (R3)

Handoff target: `builder` → `refuter`
Branch: `fix/archiet-dogfood-import` · separate PR

## Objective

One canonical ArchiMate layer vocabulary shared by importer, models, catalog
and filters; existing rows normalised onto it; and a registered verify.py gate
that fails when a stored layer value is one the UI does not render.

## Context — the mismatch is confirmed, and it is worse than a wrong tile

Verified during planning, against current code:

- **Producer**: `ArchiMateImportService.TYPE_TO_LAYER`
  (`app/services/archimate_import_service.py:91-95`) maps `WorkPackage`,
  `Deliverable`, `ImplementationEvent`, `Plateau`, `Gap` to the literal string
  `"Implementation & Migration"`.
- **Consumer**: `architecture_crud.list_elements`
  (`app/modules/architecture/routes/architecture_crud_routes.py:51`) builds
  `_LAYER_ORDER` containing `"Implementation"` (line 70), groups actual rows
  into `count_map` keyed on `lower(layer)` (line 79), and looks each tile up
  by `layer_name.lower()` (line 97). `"implementation"` never matches
  `"implementation & migration"`.
- **Consequence**: those elements land in **no tile**, and because
  `app/templates/architecture/elements.html:628` computes `totalCount` as the
  sum of the tiles, the headline total is short by exactly that number. The
  tiles do not sum to the element count — precisely the class of
  self-contradicting screen ADR 0008 exists to stop.
- **Filter half**: `elements.html:200` and `:488` both emit
  `<option value="implementation">`, and the per-layer top-3 query filters
  `func.lower(layer) == layer_name.lower()` (line 89) — so the filter is
  broken by the same mismatch, not just the count.

### Tech-lead ruling: the canonical value is `"Implementation"`

Not `"Implementation & Migration"`. Reasons: it is what the catalog, the
filter options and the top-3 query already use; it matches the `implementation`
layer key in `RelationshipValidator.LAYER_MAPPING`
(`app/modules/architecture/services/relationship_validator.py:108`) and
`IMPLEMENTATION_ELEMENTS` in `app/config/archimate_relationship_matrix.py`,
which task 01 makes authoritative for relationship validity; and it is the
shorter migration (one producer changes, N consumers do not).

**There must be exactly one definition.** Put the canonical list where the
matrix config already lives (`app/config/archimate_relationship_matrix.py`) or
in a single new module imported by both producer and consumers — and then
`TYPE_TO_LAYER`, `_LAYER_ORDER` and the template's `<option>` values all read
from it. Do **not** add a translation/alias map that converts one spelling to
the other: that is a second authority wearing a fix's clothing, and the brief
forbids it explicitly.

### The gate does not exist yet — build it

The brief and root `CLAUDE.md` both describe `store-agreement` as registered
and ratcheted at 1. **It is not registered.** `scripts/check_store_agreement.py`
exists but grepping `Gate("` in `scripts/verify.py:build_gates()` yields 56
gates and none is `store-agreement`; `scripts/check_unregistered_checks.py:13`
names it as one of the unregistered checks. So this task must register
enforcement, not extend a running gate.

Prefer **registering the existing `check_store_agreement.py`** (read it first)
and adding the layer-vocabulary question to it, over writing a new checker —
that both closes R3 and reduces the `unregistered-checks` ratchet. If it is
unfit, say why in the PR and add a focused checker instead. Registering it
will change `docs-drift`'s expectations and the gate table in `CLAUDE.md` and
`docs/DELIVERY_CONTRACT.md` — update both in the same PR or `docs-drift` goes
red. A `scripts/`-only change is exempt from the evidence-contract trailer
requirement; the template/route changes in this task are not.

## Constraints

- ADR 0008: one vocabulary, one definition site. No alias/translation map.
- Migration normalises existing rows (`UPDATE archimate_elements SET layer =
  'Implementation' WHERE lower(layer) = 'implementation & migration'`), and
  must be **tenant-safe**: it runs outside a request context, so no tenant
  predicate is applied automatically — scope explicitly or state clearly that
  it is a deliberate all-org normalisation. Per this repo's destructive-change
  rules: record the before-count, run it, record the after-count, report both.
  This is reversible in principle but capture the prior state first.
- Do not silently drop `Location`/`Grouping` handling: `_LAYER_ORDER` includes
  `Physical` and `Other` deliberately (see the comment at lines 60-66,
  written after a repository showed 59 of 74 elements). Preserve that.
- The template change requires a Tailwind rebuild only if classes change;
  `smoke-coverage-on-change` requires a `tests/smoke/` touch in the same diff.

## Deliverable

1. A single canonical layer vocabulary module/constant, with `TYPE_TO_LAYER`,
   `_LAYER_ORDER` and the template filter options all deriving from it.
2. `ArchiMateImportService.TYPE_TO_LAYER` emits `"Implementation"`.
3. A normalisation migration for existing rows, with before/after counts
   recorded in the PR.
4. `store-agreement` registered in `scripts/verify.py:build_gates()`, covering
   the question "is every stored `archimate_elements.layer` value one the
   catalog renders?", failing when it is not. Gate tables in `CLAUDE.md` and
   `docs/DELIVERY_CONTRACT.md` updated in the same PR.
5. A Playwright test asserting the rendered tiles sum to the rendered total.

## Acceptance criteria

Verbatim from the customer's brief:

- **R3**: catalog tiles sum to 168; Implementation tile shows 35 with
  WorkPackage/Deliverable/Plateau/ImplementationEvent/Gap breakdown;
  "All Layers" filter lists it.

Against the synthetic fixture: after importing
`tests/fixtures/oef/archiet_shaped.xml`, the tiles on `/architecture/elements`
sum to the fixture's element count with no element in no tile; the
Implementation tile shows the fixture's implementation-layer count and its
top-types breakdown names WorkPackage/Deliverable/Plateau/ImplementationEvent/Gap;
and selecting Implementation in the layer filter returns those rows rather
than an empty list.

Additionally:

- The registered `store-agreement` gate **fails** on a deliberately
  mis-spelled layer value and passes after normalisation — demonstrate both,
  per "a gate carries its proof".
- `python scripts/verify.py` (bare) green, including `docs-drift`.
- Playwright: import the fixture, reload `/architecture/elements`, assert
  tile-sum == total and the Implementation tile is non-zero.

## Handoff target

`refuter` — review focus: that no alias map was introduced; that the
vocabulary has exactly one definition site; that the migration's before/after
counts are recorded and its tenant scope stated; and that the gate was
demonstrated failing, not just registered.
