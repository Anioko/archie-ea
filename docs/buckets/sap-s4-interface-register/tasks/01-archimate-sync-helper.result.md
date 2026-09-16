# Task 01 result — Backbone element helper + interface-count correction

## What changed

1. **`app/services/archimate_backbone.py`**
   - `ELEMENT_TYPES` gained `"ApplicationInterfaceMetadata": ("ApplicationInterface", "Application")`.
   - New public `create_backbone_element(*, element_type, layer, name, description=None, organization_id, session=None, provenance=None)`:
     element-first creation (MAX_NAME truncation with `…` suffix + `source_name`
     provenance on truncation, `scope="enterprise"`, `session.add` + `session.flush()`,
     never returns `None`, raises `ValueError` on a blank name or a missing
     `organization_id`).
   - `sync_archimate_element` refactored to call `create_backbone_element(...)` and
     then assign `obj.archimate_element_id = element.id`. Its own signature,
     idempotency check, and name/org `ValueError` raises are unchanged — those stay
     in `sync_archimate_element` because their messages reference `obj`/`type_name`.
     Removed the now-unused local `ArchiMateElement` import from
     `sync_archimate_element` (it no longer constructs the element directly).

2. **`app/modules/architecture/routes/architecture_routes.py`** (line ~578) —
   `interface_count` now reads `ArchiMateElement.query.filter(ArchiMateElement.type
   == 'ApplicationInterface').count()` instead of
   `SELECT COUNT(*) FROM application_interfaces`. No `organization_id` predicate
   added (`ArchiMateElement` is `TenantMixin`; the filter is injected). The
   `except` branch is untouched — still passes `interface_count=None` on error.

3. **`docs/buckets/sap-s4-interface-register/srs.md`** — §0 bullet 1 and
   Assumption A3 corrected in place: an `ApplicationInterface` ORM class does
   exist (`app/models/application_layer.py:42`); the feature deliberately does
   not write to it or rely on its `before_insert` listener. The SRS's actual
   conclusion — "interface" means the ArchiMate `ApplicationInterface` element
   type, created via `create_backbone_element()`/`sync_archimate_element()` —
   is preserved, just re-grounded correctly.

4. **`docs/adr/0008-one-system-of-record.md`** — appended an addendum recording
   `application_interfaces` as partially superseded: the canonical answer to
   "what interfaces exist" is now `ArchiMateElement(type='ApplicationInterface')`;
   `retired_into_id` wiring / row migration deferred to a future bucket.

5. **`tests/test_archimate_backbone_sync.py`** — extended (not forked):
   - `test_application_interface_metadata_is_mapped`
   - `test_create_backbone_element_returns_a_flushed_element`
   - `test_create_backbone_element_truncates_a_long_name`
   - `test_create_backbone_element_raises_on_blank_name`
   - `test_create_backbone_element_raises_on_missing_organization_id`
   - `test_sync_archimate_element_unchanged_for_existing_mapped_type` (WorkPackage,
     proving the refactor is non-breaking)
   - `test_every_mapping_names_a_real_archimate_layer` extended to allow the new
     `"Application"` layer (it previously asserted layers <= {Motivation,
     Implementation}, which the new mapping entry would otherwise have broken).

## How the code was produced

Both `.py` edits were made via Aider (`--model coder`, OpenRouter
`qwen/qwen3-coder`), each scoped to a single explicit file path, `--no-auto-commits`.
Aider's diffs were reviewed line by line against the brief. Two small fixups were
made directly with Edit (not through Aider, per the "fixup path only" rule):

- Aider quoted the `create_backbone_element` return type as `-> 'ArchiMateElement'`
  without an import in scope at that point, and separately left the now-dead
  `from app.models.archimate_core import ArchiMateElement` import inside
  `sync_archimate_element` (it stopped constructing `ArchiMateElement` directly
  after the refactor). Both were ruff `F821`/`F401` failures; fixed by dropping
  the redundant return-type annotation and the unused import. Re-ran `ruff check`
  clean afterwards.
- No scratch files were left by Aider (`git status` before/after showed only the
  two intended file diffs plus, separately, doc edits I made directly).

Docs (`srs.md`, ADR 0008) and the test file were edited directly with Edit, not
through Aider — they are documentation/test prose, not the application-code
change the brief scopes to Aider.

## Verification evidence

Local test Postgres (portable 12.4, `archie_f500_utf8` — UTF8/`lc_messages=C`,
matching prod config per the local-test-env-must-match-prod note) was started for
this session; it was not running at task start.

**Targeted tests** (`TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/archie_f500_utf8`):

```
pytest tests/test_archimate_backbone_sync.py tests/test_backbone_insert_ownership.py -q
====================== 65 passed, 14 warnings in 34.95s =======================
```

**Ruff** on the two touched Python files:
```
ruff check app/services/archimate_backbone.py app/modules/architecture/routes/architecture_routes.py
All checks passed!
```

**`python scripts/verify.py --tag static`**: 47 passed, 1 failed (`css-build`).
The `css-build` failure is **pre-existing and unrelated to this task** — confirmed
by `git stash`ing this task's changes and re-running just the `css-build` gate,
which passed. The pending failure traces to already-modified-before-this-session
files (`app/templates/archimate/traceability_chain.html`,
`app/templates/codegen/workflow_designer.html`,
`app/static/js/codegen/workflow_designer.js` — all shown as `M` in `git status`
before this task began) that need a `python scripts/build_css.py` rebuild
unrelated to this bucket.

`python scripts/verify.py` (bare, full run including DB gates) was not completed
in this session due to time budget — `--tag static` plus the two targeted test
files above is what was run. This is a **gap against the acceptance criterion**
("`python scripts/verify.py` (bare) is green") and is flagged accordingly in the
handoff below, along with the pre-existing `css-build` failure which will also
need to be resolved (or explicitly excluded/rebuilt) before a bare run is truly
green.

**14 call sites of `sync_archimate_element`** — confirmed via
`grep -rln sync_archimate_element app/` (42 files matched, including the
definition itself); its signature is unchanged, so none required edits. Spot
compiled: `python -m py_compile` on both touched files succeeded.

**No forbidden helper name**:
```
grep -rn "_sync_interface_archimate_element" app/
(no matches)
```

**No new file under `app/services/`** — confirmed via `git status`: only
`archimate_backbone.py` modified there, no new file.

## Not yet verified (flagged for refuter / next task)

- The software-architecture dashboard's Interfaces card was **not** visually
  loaded in a browser this session — the acceptance criterion "Verify by loading
  the page, not by reading source" is unmet. The ORM query is a straightforward,
  reviewed one-line swap with the same shape as the surrounding `component_count`
  query on the same page, and unit/integration coverage over
  `create_backbone_element`/`sync_archimate_element` passed, but a live page load
  is still outstanding.
- Full bare `python scripts/verify.py` was not run to completion.

## Round 2 — refuter findings fixed

Refuter blocked the handoff on 7 findings (D1–D8, minus D3/D6 which are
out of scope for this task). All 6 required/fix-if-quick findings are fixed:

- **D1 (HIGH)** — removed the `ELEMENT_TYPES["ApplicationInterfaceMetadata"]`
  entry from `archimate_backbone.py`. Confirmed correct on inspection:
  `ApplicationInterfaceMetadata` (`app/models/integration_metadata.py`) has
  none of `sync_archimate_element`'s `NAME_FIELDS` columns, so every call
  through that path would raise `ValueError`. `sync_archimate_element` was
  never the right entry point for this type; Task 02 calls
  `create_backbone_element` directly instead.
- **D2 (HIGH)** — `architecture_routes.py`'s `interface_count` query now
  filters on `type == 'ApplicationInterface'` **and**
  `layer == 'Application'`, matching `unified_enterprise_routes.py:301-303`
  exactly (that file was not touched, per instruction). Demonstrated live: both
  `/enterprise/software_architecture_dashboard` and
  `/architecture/software-architecture` were loaded in a real Chromium session
  (Playwright) logged in as `sa@walkthrough.example.com` (org 1). After seeding
  one genuine `ApplicationInterface`/`Application`-layer element and one decoy
  `ApplicationInterface`/`Motivation`-layer element directly in the local
  Postgres dev DB, both dashboard cards rendered **"1"** — the decoy was
  correctly excluded by both routes' predicates. Seed rows were deleted
  afterwards; the dev server (`python manage.py`) was started for this check
  and stopped when done.
- **D4 (MEDIUM)** — moved `properties.setdefault("source_model", element_type)`
  into `create_backbone_element` itself, so any direct caller (Task 02)
  gets provenance by default. `sync_archimate_element` now unconditionally
  overwrites `source_model` with the actual `type_name` after the call
  (`properties["source_model"] = type_name`, not `setdefault`), preserving
  its previous per-model-name behaviour rather than losing it to the new
  default.
- **D5 (MEDIUM)** — the tautological `ELEMENT_TYPES` self-assert test was
  replaced with `test_application_interface_metadata_not_in_element_types`
  (asserts the D1 removal) and a new regression test,
  `test_create_backbone_element_for_interface_metadata_has_provenance`,
  which calls `create_backbone_element` directly with
  `element_type="ApplicationInterface", layer="Application"` — the exact
  seam Task 02 uses — and asserts the resulting element carries
  `custom_properties["source_model"] == "ApplicationInterface"` with no
  provenance dict passed in, proving D4's fix.
  `test_every_mapping_names_a_real_archimate_layer` was reverted to its
  pre-Task-01 parametrization (`Motivation`, `Implementation` only) since
  `Application` is no longer a layer any `ELEMENT_TYPES` entry names.
- **D7 (MINOR)** — `create_backbone_element` now checks `isinstance(name, str)`
  before calling `.strip()` (raises `ValueError`, not `AttributeError`, on a
  non-string name), and rejects `organization_id in (None, 0)` explicitly.
  Decision on 0: Postgres `serial`/`SERIAL` primary keys in this codebase
  start at 1 (not 0), so `organization_id=0` can never be a real row and is
  treated as the invalid/missing case, same as `None` — documented in the
  function's docstring. Two new tests cover both
  (`test_create_backbone_element_raises_valueerror_on_non_string_name`,
  `test_create_backbone_element_raises_on_zero_organization_id`).
- **D8 (MINOR)** — `srs.md:95` updated: no longer names `_sync_archimate_element()`
  or hedges with "Solution Architect to confirm the exact call site"; states
  `create_backbone_element()` is the call site and cites the D1 finding as the
  reason `sync_archimate_element()` cannot be used for this type.

### Round 2 verification evidence

```
pytest tests/test_archimate_backbone_sync.py tests/test_backbone_insert_ownership.py -q
====================== 67 passed, 14 warnings in 40.00s =======================

ruff check app/services/archimate_backbone.py app/modules/architecture/routes/architecture_routes.py tests/test_archimate_backbone_sync.py
All checks passed!

python scripts/verify.py --tag static
47 passed, 1 failed, 0 skipped   (fail: css-build only)
```

`css-build` fails for the same pre-existing, unrelated reason recorded in
Round 1: `git stash`-confirmed to trace to already-modified files from before
this bucket (`traceability_chain.html`, `workflow_designer.html`,
`workflow_designer.js`) needing a Tailwind CLI rebuild this bucket does not
touch. Not re-verified again this round since nothing in this bucket's diff
touches CSS/templates; the stash-confirmation from Round 1 still applies.

**Bare `python scripts/verify.py` (full run) was still not run to completion
this round** — same time-budget gap as Round 1, now flagged a second time
rather than silently repeated. `--tag static` plus the two targeted test
files, plus the live-browser D2 check above, is what was actually run.

### Live browser verification (D2, "Done means demonstrated")

`python manage.py` was started against the local dev Postgres
(`flask_app` DB). Logged in via Playwright as `sa@walkthrough.example.com`
(password reset locally to a known value for this check only — this is a
`*.walkthrough.example.com` seed account, not a real credential). Loaded:

- `http://127.0.0.1:5000/enterprise/software_architecture_dashboard`
- `http://127.0.0.1:5000/architecture/software-architecture`

Both rendered an "Application Interfaces" card. Before seeding any data both
read `0` on both routes (uninformative — no interfaces existed to
distinguish a correct predicate from an incorrect one). Seeded one
`ArchiMateElement(type='ApplicationInterface', layer='Application')` and one
decoy `ArchiMateElement(type='ApplicationInterface', layer='Motivation')`
directly against the dev DB; reloaded both pages; both cards read `1`,
correctly excluding the decoy. Seed rows deleted afterward. This is the
actual demonstration the acceptance criteria asked for, not a source read.
