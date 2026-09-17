# Task 01 result — Run the producer that already exists

## What was done

1. **New CLI command** `app/commands/apply_unified_capability_provenance_migration.py`
   (`flask --app manage apply-unified-capability-provenance-migration`) applies
   `scripts/migrate_unified_capability_provenance.sql` verbatim, inside the ORM's
   own transaction, so no `psql -f` step was introduced. Registered in
   `app/_bootstrap/cli.py`.
2. **Wired into `scripts/database/deploy-schema.sh`**, after `reconcile-schema`
   and after every `backfill-*-tenancy` step, in this order:
   `apply-unified-capability-provenance-migration` (unconditional, not
   `|| echo WARN`-suppressed — it only creates an index and is a no-op on a
   database where it already ran), then
   `project-capabilities --apply --report /tmp/project-capabilities-report.json`
   (also unconditional, per the brief's constraint — a failed projection means
   the canonical store is wrong and must not be silently swallowed).
3. **`_SOURCE_CTE` refactor** in `app/commands/project_capabilities.py`: added a
   `CAST(:single_id AS INTEGER) IS NULL OR id = CAST(:single_id AS INTEGER)`
   predicate so the same CTE (and therefore `_PROJECT_SQL` byte-for-byte) serves
   both the CLI's `--limit` path (`single_id=None`) and Task 02's write-time
   listener (`single_id=<row id>`). All five call sites updated to bind
   `single_id`; `--limit` behaviour is unchanged (verified below).
4. **New test** `test_deploy_chain_ordering_contract` in
   `tests/test_capability_projection.py`, applying the real migration SQL file
   (not a hand-rolled index) inside the disposable cloned-schema fixture, and
   asserting refuse-before / succeed-after on the identical connection — the
   literal ordering contract the deploy chain depends on.

## Measurement (local flask_test database, 3094 business_capability rows)

| step | business_capability | unified_capabilities (source_table=business_capability) |
|---|---|---|
| before | 3094 | 0 |
| after 1st `--apply` | 3094 | 3094 |
| after 2nd `--apply` (idempotency) | 3094 | 3094, `writes.inserted_or_updated == 0` |

- `select count(*) from unified_capabilities where source_table='business_capability' and (source_id is null or source_checksum is null or source_org_id is null or scope<>'tenant' or organization_id is distinct from source_org_id)` = **0** (malformed rows).
- `select count(*) from unified_capabilities where source_table='business_capability' and organization_id is null` = **0** (no projected row claims shared/reference status).
- Second run's report: `writes: {"inserted_or_updated": 0, "reparented": 0, "backlinked": 0}` — idempotency is measured, not assumed.

## Tests

`pytest tests/test_capability_projection.py -q` → **15 passed** (12 pre-existing
+ 3 new, listed under Task 02 below), including alone (`-p no:randomly` not
needed — no ordering dependency introduced; ran standalone and passed).

## Acceptance criteria — status

- [x] Fresh run leaves projected count == business_capability count, zero
      `_verify` failures.
- [x] Second run writes zero rows.
- [x] Every projected row's provenance/scope/org invariants hold; zero NULL org.
- [x] `python scripts/verify.py --tag static` green (48 passed, 1 skipped —
      `css-build`, pre-existing, no vendored Tailwind CLI in this environment).
- [ ] `python scripts/verify.py` (bare, full) — running; see Task 03 result for
      the combined full-suite outcome, since Tasks 01/02/03 land together in
      this session.
- [x] No change to what business_capability-reading screens report (not
      touched; `tests/smoke/test_capability_journey.py`'s existing
      BusinessCapability-surface assertions still pass unmodified).

## Known caveat for refuter

- The local `flask_test` database is long-lived and shared across many past
  sessions (per repo memory notes). It already held 95 pre-existing
  `unified_capabilities` rows (various seeders/importers/test artifacts,
  0 of which were `source_table='business_capability'`) before this task ran.
  Those are untouched by this projection and are the subject of Task 03's
  `store-agreement` finding, not this task's.

## Round 3 (17 Sep 2026)

Refuter's round 2 review found R2-1 (HIGH, blocker): the D5 write-time skip
(Task 02) correctly stopped the wrong write, but `flask project-capabilities
--apply` still hit blocker 2 (`owner_or_code_changed_since_projection`) on
exactly the moved row and raised `ProjectionBlocked`, aborting the *entire*
batch for *every* tenant, with no resolver command for that blocker. Combined
with Task 03's `deploy-schema.sh` `|| echo WARN`, a single org-move froze the
projection for the whole database, announced only as a stderr WARN line.

Fixed in `app/commands/project_capabilities.py`:

- `_plan()`'s blocker-2 check now also collects the actual `business_capability.id`
  values that moved (`source_ids`, capped at 5000), and every blocker dict now
  carries `"blocking": True/False` — blocker 2 is the only one marked
  `False` (`"blocking": False`). Every other blocker (ownerless_source_rows,
  tenant_code_collision, archimate_id_collision, source_hierarchy_cycle) is
  still a hard, whole-batch block.
- `run_projection()` splits `plan["blockers"]` into `hard_blockers` (still
  raise `ProjectionBlocked`, nothing written) and `skippable` (reported in a
  new `report["skipped"]` key, visible in both `--dry-run` and `--apply`
  output; the CLI's `project_capabilities` command now echoes it).
- `excluded_ids` — the union of every skippable blocker's `source_ids` — is
  now threaded into `_SOURCE_CTE` (a new `NOT (id = ANY(CAST(:excluded_ids AS
  INTEGER[])))` predicate, bound via `_source_params()`/every call site),
  `_PARENT_SQL` and `_BACKLINK_SQL` (`AND bc.id != ALL(CAST(:excluded_ids AS
  INTEGER[]))`), and `_verify()`'s unprojected-row check, so a deliberately
  skipped row: (a) is not written to, reparented, or back-linked this run,
  (b) does not trip post-write verification, and (c) every OTHER row —
  including brand-new, never-projected rows — still projects normally in the
  same run.
- `app/models/business_capabilities.py`'s write-time `_project_capability_row`
  now passes `"excluded_ids": []` explicitly to `_PROJECT_SQL`/`_PARENT_SQL`
  (it only ever narrows to its own `single_id`, so there is nothing else in
  its row set to exclude — this is a mechanical parameter-shape update, not a
  behaviour change for that listener).

R2-3 (MEDIUM, empty-string code edge case) fixed in the same listener: the
"moved" check's `"code": target.code or f"BC-{target.id}"` fell through on
`code=''` the same as `code=None`, but the CLI's actual comparison is
`COALESCE(bc.code, 'BC-' || bc.id)`, which only substitutes on `NULL`. Changed
to `target.code if target.code is not None else f"BC-{target.id}"` to match
COALESCE semantics exactly. No code path currently sets `code=''` (confirmed
by re-reading the model and every writer in this bucket), so this was latent,
not live, but is a one-token fix worth landing now rather than leaving a known
false-positive "moved" classification for whenever it does become live.

Tests added to `tests/test_capability_projection.py`
(`test_moved_row_is_skipped_not_blocking_the_whole_run`,
`test_moved_row_does_not_block_a_dry_run_either`): create two capabilities,
project both, move one to a different org via raw SQL (bypassing the
write-time listener, to reproduce the state the listener's own skip freezes),
add a third never-projected capability, then run `run_projection` again and
assert (a) it does not raise, (b) only the new row is written
(`writes.inserted_or_updated == 1`), (c) the moved row's projected data is
untouched (still the old org, not corrupted or silently updated), (d)
`report["skipped"]` names the moved row's `source_ids`, and the same for
`apply=False`.

`pytest tests/test_capability_projection.py -q` → **17 passed** (15 from
round 2 + 2 new).
