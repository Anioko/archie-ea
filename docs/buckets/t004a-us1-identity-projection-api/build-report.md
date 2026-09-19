# T-004a — US-1 identity projection and provenance fields on the impact API: Build Report

Base: `origin/main` at `1cdd8c4d` (the brief names `31fbaece`; `main` has since gained one unrelated
dashboard commit, so every `git diff 31fbaece..HEAD` in the brief was run as `git diff 1cdd8c4d..HEAD`, and
the `31fbaece` form was also run for `app/api/v1/impact.py` and returned the same empty result).
Branch: `feat/t004a-us1-identity-projection-api`. Nothing was pushed or merged.

Commits (oldest first):

| Commit | Content |
|---|---|
| `9006f164` | The three source changes, the two new test files, and the two extensions of existing test files |
| `d55f9d9f` | Test-only: one assertion narrowed to what the tenant predicate actually defends (see "Mutation proof", note 3) |
| `ff8acfb9` | Test-only: exact row and relation key sets pinned (see "Mutation proof", M15) |
| (the commit that adds this file) | This report only |

## Summary

`GET /api/v1/intelligence/impact/<element_id>` now returns, inside `data`, a top-level `elements` map
(`{"<id>": {"id", "name", "type", "layer"}}`) for every id that appears as a row's `element_id` or inside a
row's `relation.chain_elements`. The map is one batched `select` of exactly those four columns over
`ArchiMateElement`, executed inside the `record_query_latency` scope, with the ORM tenant listener plus an
explicit `organization_id` predicate. An id that does not resolve in the caller's tenant (another tenant's,
soft-deleted, hard-deleted, never existed) is absent from the map. Derived rows additionally carry
`relation.derived_id`, `relation.engine_version` and `relation.plain_terms`; explicit rows carry `null` for all
three. The sentence is generated only in the new `plain_terms.py`, from names in the same response's map, and is
`null` when either end's name is absent. `app/api/v1/impact.py` and `test_impact_route.py` are byte-identical to
base. No route, template, script, parameter, table, column, dependency or reason code was added.

The mutation proof asked for in acceptance item 11 gave a **split** result that the brief anticipated as a
possibility: with the explicit predicate removed, the two-tenant test that goes through the response stays
green (the ORM listener alone fences it); only the two tests that call the private lookup directly, outside the
listener's reach, go red. See "Mutation proof".

## Files changed

`git diff --stat 1cdd8c4d..ff8acfb9` (everything except this report):

```
 app/modules/intelligence/routes/api.py             |   7 +-
 app/modules/intelligence/services/plain_terms.py   | 104 +++
 app/modules/intelligence/services/query_service.py | 131 +++-
 app/modules/intelligence/tests/test_api_routes.py  |  53 ++
 app/modules/intelligence/tests/test_plain_terms.py | 324 +++++++++
 .../intelligence/tests/test_query_service.py       |  57 ++
 .../tests/test_query_service_elements_map.py       | 742 +++++++++++++++++++++
 7 files changed, 1415 insertions(+), 3 deletions(-)
```

- `services/query_service.py` — `_resolve_elements_batch`, `_element_ids_in_rows`, `_name_in`,
  `_attach_plain_terms`; `_explicit_row` / `_derived_row` carry the three new `relation` keys;
  `cross_layer_impact` resolves the map inside the latency scope and returns it under `elements`
  (`{}` on the early-return branches). `_derived_row` also carries the internal `_endpoints` join key, popped by
  the existing per-row loop exactly as the explicit rows' is.
- `services/plain_terms.py` (new) — `plain_terms_sentence(*, dependent_name, dependency_name, depth, confidence)`.
- `routes/api.py` — `success_response` payload gains `"elements": result["elements"]`. Nothing else.
- Tests: two new files, plus three functions appended (no existing line touched: `--numstat` shows `53 0` and
  `57 0` deletions for the two extended files).

## How the map is built (the security-relevant part)

```python
stmt = db.select(ArchiMateElement.id, ArchiMateElement.name, ArchiMateElement.type, ArchiMateElement.layer).where(
    ArchiMateElement.id.in_(distinct_ids),
    ArchiMateElement.organization_id == org_id,      # explicit predicate, defence in depth
)
```

- Four **columns** are selected, not the entity. `description`, `documentation`, `properties`, `scope`, the cost /
  scoring / strategic columns and `deleted_at` are never read from the database, let alone serialised. The
  four-key ceiling is therefore enforced at the query and again by the dict literal.
- The SQL that actually runs (printed by a temporary statement-capturing test, since removed) carries three
  predicates, two of them from the listeners:
  `... WHERE archimate_elements.id IN (...) AND archimate_elements.organization_id = %(organization_id_1)s AND archimate_elements.deleted_at IS NULL AND archimate_elements.organization_id = %(current_org_id_1)s`.
  The `deleted_at IS NULL` is the unconditional soft-delete listener; the last predicate is the tenant listener;
  the first is mine.
- `org_id is None` returns `{}`. No raw SQL is used, so the `raw-sql-tenancy` obligations (marker, per-arm
  predicate) do not arise. The function performs no writes.
- `layer` comes back from the column as a `str` subclass with case-insensitive equality; the map hands out a plain
  `str` (asserted by `type(...) is str`).

## Traceability: FR -> DE -> acceptance item -> test id

FR mapping is my reading of the brief's header "(FR-5, FR-15)": items 1-7 serve FR-5 (identity and provenance
reachable on a row), items 8-9 serve FR-15 (the server-side sentence). All tests are under
`app/modules/intelligence/tests/`; `elements_map` = `test_query_service_elements_map.py`, `plain_terms` =
`test_plain_terms.py`.

| # | FR | DE / rule | Acceptance item | Test id(s) |
|---|---|---|---|---|
| 1 | FR-5 | DE-9 | Map present on 200; covers every row / chain id, nothing else | `elements_map::test_map_covers_every_row_and_chain_element_and_nothing_else`, `elements_map::test_http_data_carries_elements_beside_rows_summary_reasons`, `elements_map::test_map_is_empty_object_when_no_rows_and_on_early_return_branches` |
| 2 | FR-5 | DE-9, SEC-02 | Exactly four keys; forbidden keys asserted absent individually | `elements_map::test_every_map_entry_has_exactly_four_keys`; `elements_map::test_forbidden_key_is_absent_from_every_map_entry[<key>]` for `description`, `scope`, `tco`, `criticality`, `app_name`, `estimated_financial_risk` (the six the brief names) plus `documentation`, `properties`, `tco_annual`, `estimated_cost`, `business_value_score`, `organization_id`, `deleted_at` (13 parametrised cases, each asserted on the service result and the HTTP body); `elements_map::test_no_element_column_value_beyond_the_four_reaches_the_response` (values, not just key names, seeded into every sensitive column) |
| 3 | FR-5 | DE-9, NFR-5 | One batched select, not N; >= 10 distinct elements | `elements_map::test_map_is_one_batched_select_however_many_elements` (a 3-leaf and a 12-leaf star: one `IN (...)` select over `archimate_elements` in each, 13 elements in the larger map, statement count on that table equal at 2 for both) |
| 4 | FR-5 | DE-18, NFR-5 | Inside the latency scope | `elements_map::test_identity_resolution_runs_inside_the_latency_scope` (an 80 ms sleep injected into the resolver shows up in `summary.latency_ms`; the resolver is observed running while the scope is open; the histogram `archie_intelligence_query_seconds_count` rises by exactly 1 with the unchanged labels) |
| 5 | FR-5 | B3 tenancy | Cross-tenant absence | `elements_map::test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http` (two-tenant fixture; org B's name and description appear nowhere in the response body), `elements_map::test_cross_tenant_element_is_absent_from_the_service_map`, `plain_terms::test_derived_row_sentence_is_null_when_an_endpoint_is_another_tenants`; predicate-level: `elements_map::test_identity_lookup_is_tenant_correct_with_no_ambient_request_context`, `elements_map::test_identity_lookup_holds_when_the_ambient_tenant_diverges` |
| 6 | FR-5 | B3 tenancy | Deleted-element absence, 200 not 500 | `elements_map::test_deleted_and_nonexistent_elements_are_absent_not_500` (one stored chain naming a hard-deleted id, a soft-deleted id and an id that never existed) |
| 7 | FR-5 | DE-9 | `derived_id` / `engine_version` restored; null on explicit rows | `elements_map::test_derived_row_carries_derived_id_and_engine_version_from_the_store`, `elements_map::test_explicit_row_carries_null_for_the_derived_only_fields`, `test_query_service.py::test_derived_row_carries_derived_id_and_engine_version`, `test_query_service.py::test_explicit_row_carries_null_derived_id_and_engine_version`, `test_api_routes.py::test_impact_row_derived_id_addresses_the_provenance_endpoint` (the restored id opens `GET /derived/<id>` and both report the same `engine_version`) |
| 8 | FR-15 | DE-9 | Sentence at band boundaries 0.95 / 0.90 / 0.85 / 0.70 / 0.69; null confidence omits the clause, never `0%`; null on absent name; null on explicit rows | `plain_terms::test_the_sentence_matches_the_brief_example_exactly`, `plain_terms::test_confidence_bands_at_the_boundaries[*]` (10 cases incl. `Decimal` as the store returns), `plain_terms::test_percent_is_confidence_rounded_half_up_to_a_whole_number[*]`, `plain_terms::test_null_confidence_omits_the_clause_and_never_prints_zero_percent`, `plain_terms::test_measured_zero_confidence_is_shown_as_zero_and_is_not_null`, `plain_terms::test_absent_name_or_depth_makes_the_whole_sentence_null[*]`, `plain_terms::test_a_confidence_that_is_not_a_number_is_a_loud_error`, `plain_terms::test_derived_row_sentence_names_both_ends_from_the_identity_map`, `plain_terms::test_derived_row_without_confidence_has_no_clause`, `plain_terms::test_explicit_rows_carry_null_plain_terms` |
| 9 | FR-15 | ADDENDUM-UX s2 | One generator | `plain_terms::test_the_sentence_is_assembled_in_exactly_one_place` |
| 10 | — | SEC-02 | Canonical endpoint untouched | `git diff 1cdd8c4d..HEAD -- app/api/v1/impact.py` empty (also empty against `31fbaece`); `test_impact_route.py` unmodified and green incl. `test_projection_integrity_no_commercially_sensitive_fields` (`:240` equality) and `test_app_id_branch_characterisation_untouched` (`:304` equality); `elements_map::test_canonical_impact_endpoint_does_not_return_elements`. **See Deviations, item 4: the canonical endpoint's `derived_elements` rows do gain the three keys.** |
| 11 | — | OA-6 | Mutation proof | Next section |
| 12 | — | no fabrication | No placeholder / zero-filled / invented entry | `elements_map::test_a_null_named_element_is_absent_not_a_null_entry`, `elements_map::test_layer_is_plain_canonical_lower_case_or_null_and_type_may_be_null`, item 5/6 tests; gates `fabricated-data` and `silent-data` at `0 <= 0` |
| 13 | — | scope | Nothing out of scope moved | diff stat above: three source files, tests, this report |
| 14 | — | — | Suite green, verify clean | Intelligence suite: 210 passed (below). **`verify.py` bare is not clean here** (`tests` timed out, `nav-verified` had no data, `dependency-cves` needed a tool absent from the venv and passes once installed): see "The bare `python scripts/verify.py`" |

## Mutation proof (acceptance item 11) and further mutations

All mutations below were run on a `git archive HEAD` copy of `d55f9d9f` (the final source; `ff8acfb9` adds test
assertions only, and its one mutation, M15, was run with that test file copied into the same archive copy),
against a private PostgreSQL 17
cluster, never in the worktree. The harness compared the SHA-256 of every file it touched before and after each
mutation (all restored byte-identical), and after mutations M1-M14 all 4,725 files of the copy were compared
against `git archive HEAD` again: 0 differing, 0 missing. The later probes and M15 restored the files they touched
and compared them individually. `git status --porcelain` and
`git diff HEAD` in the worktree were empty throughout. (An earlier round of the same mutations was run in the
worktree before this discipline was set, and restored with `git checkout --`; it produced the same failing test
ids for the predicate, batching, latency-scope and widening mutations. The archive-copy results are the ones
recorded here.)

Control (unmutated archive copy, unmigrated DB): `204 passed, 6 skipped` (the 6 skips are named below).

### The mutation the brief requires — explicit `organization_id` predicate removed

Change: delete the line `ArchiMateElement.organization_id == org_id,` from `_resolve_elements_batch`.
Run: the whole `app/modules/intelligence/tests/` directory.

```
FAILED app/modules/intelligence/tests/test_query_service_elements_map.py::test_identity_lookup_is_tenant_correct_with_no_ambient_request_context - AssertionError: assert {'1420', '1419'} == {'1419'}
FAILED app/modules/intelligence/tests/test_query_service_elements_map.py::test_identity_lookup_holds_when_the_ambient_tenant_diverges - AssertionError: assert '1422' not in {'1422': {'id': 1422, 'name': 'ORGB-SECRET-ELEMENT-NAME', 'type': 'ApplicationComponent', 'layer': 'application'}}
====== 2 failed, 202 passed, 6 skipped, 2 warnings in 134.74s (0:02:14) =======
```

**What this says, plainly.** With the predicate disabled, the two-tenant tests that go through
`cross_layer_impact` and through the HTTP route **stay green**:

```
...::test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http PASSED
...::test_cross_tenant_element_is_absent_from_the_service_map PASSED
plain_terms::test_derived_row_sentence_is_null_when_an_endpoint_is_another_tenants PASSED
```

The ORM tenant listener alone keeps them green, because inside a request `org_id` and the listener's
`g.current_org_id` are the same value. The predicate is observable only where the listener cannot help, and the
only tests that reach that are the two that call the private `_resolve_elements_batch(ids, org_id)` directly:

1. `..._with_no_ambient_request_context` — no `g.current_org_id` at all, so the listener no-ops and the lookup is
   otherwise unfiltered. Red with the predicate removed (org B's element returned to a caller acting for org A).
2. `..._when_the_ambient_tenant_diverges` — `g.current_org_id` is org B while the caller resolves for org A. Red
   with the predicate removed (org B's element, id and name, returned).

**What the predicate is actually defending:** a caller of `_resolve_elements_batch` that is not a request — a job,
a CLI command, a test looping tenants in one session — where the listener does not apply, or applies a different
tenant. **No shipped call path reaches that today.** The only caller of `_resolve_elements_batch` is
`cross_layer_impact`, which reads `org_id` from the same `g.current_org_id` the listener uses and returns before the
lookup when it is `None`; that method is in turn called only by the route and by `impact.py`'s
`_derived_elements_for_element`. The predicate is therefore
defence in depth with no reachable divergent-input scenario in the current call graph, and is stated as such. The
two direct-call tests are the same shape as the existing SEC-09 owner tests in `test_query_service.py`
(`test_sec09_tenant_check_blocks_real_cross_tenant_resolution`); they are direct calls to a private function, not
scenarios any request produces, and are labelled that way in their docstrings. No test was invented to make the
predicate look reachable through the endpoint.

### Both layers, and the listener alone

The same cross-tenant tests (5 selected: the HTTP, service, no-context, diverging and derived-sentence tests):

| Mutation | Result | Reading |
|---|---|---|
| Predicate removed, listener on (the mutation above) | the 2 direct-call tests red; the 3 request-shaped tests green | listener alone fences requests |
| Listener off (`_add_tenant_filter` returns at once), predicate on | `5 passed, 56 deselected in 48.43s` | predicate alone also fences requests, and the direct-call cases |
| Both off | `5 failed, 56 deselected in 50.81s` — every one of the five red, e.g. `assert '1460' not in {'1458': ..., ...}` and `plain_terms...another_tenants: assert 'We worked this out because TheirsOrgB depends on Mine, 2 hops away. Very co...` | each layer is sufficient for a request; with neither, org B's element name and a sentence naming it leak. The fixture is real, not vacuous |

### Other mutations (test sensitivity, run on the same archive copy)

| Id | Mutation | Tests that went red | Result line |
|---|---|---|---|
| M4 | one `select` per id instead of one batch | `elements_map::test_map_is_one_batched_select_however_many_elements` | `1 failed, 29 deselected` |
| M5 | map resolved after the latency scope closes | `elements_map::test_identity_resolution_runs_inside_the_latency_scope` | `1 failed, 29 deselected` |
| M6 | `description` added to the projection | `test_every_map_entry_has_exactly_four_keys`, `test_forbidden_key_is_absent_from_every_map_entry[description]`, `test_no_element_column_value_beyond_the_four_reaches_the_response` | `3 failed, 12 passed, 15 deselected` |
| M7 | `relation.derived_id` set to `None` | `test_api_routes.py::test_impact_row_derived_id_addresses_the_provenance_endpoint`, `test_query_service.py::test_derived_row_carries_derived_id_and_engine_version`, `elements_map::test_derived_row_carries_derived_id_and_engine_version_from_the_store` | `3 failed, 1 passed, 56 deselected` |
| M8 | `relation.engine_version` set to `None` | `test_query_service.py::test_derived_row_carries_derived_id_and_engine_version`, `elements_map::test_derived_row_carries_derived_id_and_engine_version_from_the_store` | `2 failed, 1 passed, 57 deselected` |
| M9 | null confidence rendered as 0% | `plain_terms::test_derived_row_without_confidence_has_no_clause`, `test_measured_zero_confidence_is_shown_as_zero_and_is_not_null`, `test_null_confidence_omits_the_clause_and_never_prints_zero_percent` | `3 failed, 28 deselected` |
| M10 | top band `>= 0.90` made `> 0.90` | `plain_terms::test_confidence_bands_at_the_boundaries[0.9-...]` and the `Decimal("0.90")` case | `2 failed, 8 passed, 21 deselected` |
| M11 | middle band `>= 0.70` made `> 0.70` | `plain_terms::test_confidence_bands_at_the_boundaries[0.7-...]` and the `Decimal("0.70")` case | `2 failed, 8 passed, 21 deselected` |
| M12 | sentence built even when a name is absent | `test_absent_name_or_depth_makes_the_whole_sentence_null[kwargs0..kwargs4]`, `test_derived_row_sentence_is_null_when_an_endpoint_is_another_tenants` | `6 failed, 1 passed, 24 deselected` |
| M13 | a second module carrying the sentence wording | `plain_terms::test_the_sentence_is_assembled_in_exactly_one_place` | `1 failed, 30 deselected` |
| M14 | unconditional soft-delete listener off | `elements_map::test_deleted_and_nonexistent_elements_are_absent_not_500` | `1 failed, 29 deselected` |
| M15 | `row.pop("_endpoints")` removed, so the internal join key leaks into every row | `elements_map::test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http`, `elements_map::test_derived_row_carries_derived_id_and_engine_version_from_the_store`, `elements_map::test_explicit_row_carries_null_for_the_derived_only_fields` (control with the unmutated source: `3 passed, 27 deselected`) | `3 failed, 27 deselected` |

Notes:

1. M14 shows where the soft-deleted branch of item 6 comes from: the unconditional `deleted_at IS NULL` listener
   in `app/middleware/tenant_isolation.py`, not code in this task. The test would catch that listener being
   removed; this task adds no explicit `deleted_at` predicate (the brief asks for none).
2. M10/M11 had no other boundary test red: the 0.95, 0.85, 0.69 cases are away from the boundaries by design,
   the boundary cases are `0.90` and `0.70` as float and `Decimal`.
3. Commit `d55f9d9f` narrowed the diverging-tenant test's assertion from `got == {}` to "org B's id is absent and
   its name appears nowhere". The old assertion also depended on the listener intersecting with the predicate,
   which made it red for the wrong reason when the listener was switched off in the "listener off" experiment. The
   predicate-removal result is unchanged by the edit (red either way).

## Verification

Environment: Windows 11, Git Bash, Python 3.12.10 in a private venv with `requirements.txt` and
`requirements-test.txt` installed, PostgreSQL 17.5 in a **private cluster on port 5571** (own data directory,
default socket settings, the system service on 5432 never touched). Two databases in it: `archie_test`
(`init-db`, `reconcile-schema`) and `archie_mut`, a `TEMPLATE` clone of it that additionally had
`flask apply-unified-capability-provenance-migration` applied (see the skips). Env for every command:
`TEST_DATABASE_URL` and `DATABASE_URL` pointing at the private cluster, `FLASK_CONFIG=testing`,
`SECRET_KEY` set, `REDIS_URL` pointed at a closed local port so the cache probe fails fast.

Environment adaptations (none touch the repository): (a) `python-magic-bin` was uninstalled from the venv — with
it installed `import magic` crashed the interpreter on this Windows / Python 3.12 combination (access violation in
`magic/compat.py`), which is the failure `requirements.txt`'s own comment describes for 3.13; (b) `init-db` without
`FLASK_CONFIG=testing` fails on `TRANSFORMATION_COMMAND_CAPABILITY_SECRET is required`; (c) the `vector`
extension is **not installed** in this PostgreSQL (`CREATE EXTENSION vector` -> `extension "vector" is not
available`). `init-db`, `reconcile-schema`, `schema-drift` and the suite all ran to completion regardless, but
nothing that genuinely needs pgvector was exercised.

### Full intelligence suite at the final code, real PostgreSQL

```
$ pytest app/modules/intelligence/tests/ -q -p no:randomly -p no:cacheprovider -rs      (worktree at ff8acfb9, DB archie_mut)
================= 210 passed, 2 warnings in 301.66s (0:05:01) =================
```

(The same command at `d55f9d9f`, before the last test-only commit, gave `210 passed, 2 warnings in 146.96s`; the
longer time above is contention with a concurrent run on the same machine.)

Same suite on the same database before the migration command was applied (the mutation harness's control run, on
the archive copy of `d55f9d9f`):

```
SKIPPED [6] app\modules\intelligence\tests\test_capability_projection_job.py:109: uq_unified_capabilities_provenance is absent on this database; run `flask apply-unified-capability-provenance-migration` first
=========== 204 passed, 6 skipped, 2 warnings in 180.12s (0:03:00) ============
```

The 6 skips are `test_capability_projection_job.py`, unrelated to this task; they need an index that only the
deploy chain's migration command creates. They ran (and passed) once that command was applied. Test counts: 210 =
the brief's 146 at base + 64 added here (31 in `test_plain_terms.py`, 30 in `test_query_service_elements_map.py`,
2 in `test_query_service.py`, 1 in `test_api_routes.py`).

Acceptance-item tests plus the unmodified canonical-endpoint tests, verbose:

```
$ pytest test_impact_route.py test_query_service_elements_map.py test_plain_terms.py \
    test_query_service.py::test_derived_row_carries_derived_id_and_engine_version \
    test_query_service.py::test_explicit_row_carries_null_derived_id_and_engine_version \
    test_api_routes.py::test_impact_row_derived_id_addresses_the_provenance_endpoint -v
======================== 77 passed in 66.61s (0:01:06) ========================
app/modules/intelligence/tests/test_impact_route.py::test_route_returns_full_api1_payload PASSED [  1%]
app/modules/intelligence/tests/test_impact_route.py::test_projection_integrity_no_commercially_sensitive_fields PASSED [  9%]
app/modules/intelligence/tests/test_impact_route.py::test_app_id_branch_characterisation_untouched PASSED [ 11%]
```

### `verify.py`

`python scripts/verify.py --tag static` (run at `9006f164`; `d55f9d9f` changed one test file only). **This is a
partial run and is not reported as clean.** Its own output at this commit does not say so (see Deviations,
item 6):

```
Archie verification
----------------------------------------------------------------------
  ok    compile                     5.8s
  ok    undefined-exports           0.1s  [0 <= 0]
  ok    undefined-names             0.1s  [0 <= 0]
  ok    redefinitions               0.1s  [0 <= 0]
  ok    lint-core                   0.1s  [0 <= 0]
  ok    design-tokens               1.4s  [0 <= 0]
  ok    raw-fetch-sites             1.1s  [0 <= 0]
  ok    design-tokens-extended      0.9s  [0 <= 0]
  ok    shell-conformance           0.7s  [3 <= 3]
  ok    nav-coverage               12.4s  [0 <= 0]
  ok    air-gap                     1.3s  [0 <= 0]
  ok    raw-sql-tenancy            13.9s  [0 <= 0]
  ok    tenant-scoping             13.9s  [0 <= 0]
  ok    llm-boundary                0.2s  [0 <= 0]
  ok    evidence-contract           0.3s  [30 <= 30]
  ok    role-gate-coverage          0.2s  [7 <= 7]
  ok    ai-evidence-rules           0.1s  [0 <= 0]
  ok    ai-tool-guard               2.9s  [0 <= 0]
  ok    ai-untrusted-content       18.4s  [0 <= 0]
  ok    ai-approval-honoured        3.8s  [0 <= 0]
  ok    sidebar-links              45.0s  [27 <= 27]
  ok    template-syntax             4.1s  [0 <= 0]
  ok    template-references        19.9s  [0 <= 0]
  ok    canonical-store             1.6s  [0 <= 0]
  ok    fetch-guards                0.5s  [0 <= 0]
  ok    ui-contract                 1.6s  [0 <= 0]
  ok    error-signalling           14.9s  [0 <= 0]
  ok    silent-data                12.2s  [0 <= 0]
  ok    dead-interactions          29.0s  [0 <= 0]
  ok    macro-import-context        5.2s  [0 <= 0]
  ok    asset-urls                  0.3s  [0 <= 0]
  ok    qa-register                 0.2s  [0 <= 0]
  ok    docs-drift                  0.2s  [0 <= 0]
  ok    unregistered-checks         0.2s  [33 <= 33]
  ok    null-filters                0.4s  [0 <= 0]
  ok    fabricated-data             4.5s  [0 <= 0]
  ok    breadcrumb-coverage         0.5s  [0 <= 0]
  ok    raw-repr-in-template        2.1s  [0 <= 0]
  ok    duplicate-breadcrumb        0.5s  [0 <= 0]
  ok    raw-html-escaping           1.3s  [0 <= 0]
  ok    smoke-coverage-on-change    0.8s  [0 <= 0]
  ok    stale-models                4.5s  [0 <= 0]
  ok    js-build                    0.1s
  ok    console-reporting           0.4s  [0 <= 0]
  ok    js-syntax                   5.2s
  skip  css-build                   0.0s
  ok    sri                         0.4s  [0 <= 0]
  ok    vendor-integrity            0.3s
  ok    csrf-coverage              43.6s
----------------------------------------------------------------------

1 gate(s) skipped and therefore NOT verified:
    css-build: no vendored Tailwind CLI at scripts/bin/tailwindcss[.exe]; an npm-resolved Tailwind is not byte-reproducible against the committed build (caniuse-lite floats), so this cannot be verified here
    CI runs with --require-db so these cannot be silently skipped there.

48 passed, 0 failed, 1 skipped
```

The six runtime gates the brief names (live database required), also at `9006f164`:

```
$ python scripts/verify.py --gate schema-drift --gate boot-health --gate store-agreement --gate csrf-coverage --gate broken-surfaces --gate dynamic-link-prefixes
Archie verification
-------------------------------------------------------------------
  ok    broken-surfaces         57.4s  [0 <= 0]
  ok    dynamic-link-prefixes   43.4s  [0 <= 0]
  ok    store-agreement         41.2s  [0 <= 1]
  ok    boot-health             47.2s
  ok    csrf-coverage           42.9s
  ok    schema-drift           156.4s  [0 <= 0]
-------------------------------------------------------------------

6 passed, 0 failed, 0 skipped
```

`ruff check app/modules/intelligence/` (ruff 0.16.0, the version the repo pins): `All checks passed!`

### The bare `python scripts/verify.py` — NOT clean, and why

The only run whose green means "clean" did not come back green:

```
$ python scripts/verify.py --json        (worktree, DB archie_test; started with HEAD at 9006f164, HEAD became d55f9d9f during the run, which changed one test file only)
{"ok": false, ..., "summary": {"pass": 54, "fail": 3, "skip": 1}}
```

The three failures and the one skip, verbatim from the JSON:

| Gate | Status | Detail |
|---|---|---|
| `dependency-cves` | fail | `pip-audit could not run: pip-audit produced no output: ...python.exe: No module named pip_audit` |
| `tests` | fail | `timed out` |
| `nav-verified` | fail | `no audit data: run the behavioural suite with -p scripts.route_verification_audit` |
| `css-build` | skip | `no vendored Tailwind CLI at scripts/bin/tailwindcss[.exe] ... cannot be verified here` |

- `dependency-cves`: my venv did not contain `pip-audit`. That is an environment gap, not a finding. After
  `pip install pip-audit`, the gate alone: `ok    dependency-cves  120.8s  [0 <= 0]` / `1 passed, 0 failed, 0 skipped`.
  This task changes no dependency.
- `tests`: the gate runs the whole `tests/` tree (497 top-level entries) with a 3600 s timeout and it timed out. It was
  running on a Windows machine that was at the same time running this task's mutation runs and other work, so the
  time-out says nothing about pass or fail: **the repository-wide test result is unknown from this run.** The gate's
  second half (`tests/smoke`, Playwright browsers) never started.
- `nav-verified`: it reads the audit data the `tests` gate writes; with `tests` timed out there was none. Unverified,
  not failed on merit.
- All other 54 gates passed, including `raw-sql-tenancy 0`, `tenant-scoping 0`, `fabricated-data 0`, `silent-data 0`,
  `evidence-contract 30 <= 30`, `store-agreement 0 <= 1`, `schema-drift` ("no drift detected"), `boot-health`,
  `csrf-coverage`, `deployed-deps` ("All 86 pinned package(s) match the local environment").

A supplementary, visible-progress run of the same repository-wide tree (excluding `tests/smoke` and
`tests/test_boot_health.py`, exactly as the gate does) stopped at its `--maxfail=30` after 38 tests:

```
$ python -m pytest tests -q -p no:cacheprovider -p no:randomly --ignore=tests/smoke --ignore=tests/test_boot_health.py --maxfail=30 --timeout=300
============ 30 failed, 8 passed, 3 warnings in 310.82s (0:05:10) =============
```

All 30 are `tests/journeys/*` (login-dependent journeys answering `302` / `401` where `200` / `201` / `400` is
expected). **They fail identically on the untouched base commit**, so they are not caused by this task. Control, on
a `git archive 1cdd8c4d` copy with none of this task's code, same database and environment:

```
FAILED tests/journeys/test_journey_cto.py::test_cto_classifies_a_technology_and_the_radar_shows_it
FAILED tests/journeys/test_journey_cto.py::test_the_radar_refuses_to_classify_something_that_is_not_modelled
FAILED tests/journeys/test_journey_cto.py::test_a_cto_cannot_classify_another_orgs_technology
FAILED tests/journeys/test_journey_cto.py::test_the_classify_api_still_answers_in_json
FAILED tests/journeys/test_journey_close_and_decide.py::test_a_journey_not_yet_at_deliver_cannot_be_closed
FAILED tests/journeys/test_journey_close_and_decide.py::test_a_journey_at_deliver_can_be_closed_and_it_sticks
FAILED tests/journeys/test_journey_close_and_decide.py::test_an_unsupported_status_value_is_refused
=================== 7 failed, 1 passed in 65.34s (0:01:05) ====================
```

I did not find the cause of the journey failures (the journey harness mints a session id like the shared fixture
does; the failure is a lost login on this Windows / private-cluster setup, but that is a description, not a
diagnosis). The consequence for this report is plain: **the repository-wide test tree was not run to completion
here, and the repository-wide result is unverified.** The only suite that ran to completion and is claimed green is
the intelligence suite the brief names.

## Measured effect on the NFR-5 path

No populated database was available, so **there is no NFR-5 verdict from this task.** What was measured is a
synthetic fixture on an empty local database: 1 root, 10 first-level and 40 second-level elements, 50 explicit
relationships, 40 derived facts; the NFR-5 call shape (`include_derived=True`, `max_depth=4`, `with_owner=True`);
1 warm-up call then 40 timed calls; `summary.latency_ms` as reported by the endpoint. "Before" is the base
`query_service.py` with everything else at `HEAD`.

| | statements per call | of which `archimate_elements` selects | rows | latency_ms median / p95 / min / max |
|---|---|---|---|---|
| before (base `query_service.py`) | 16 (8 data statements incl. 1 savepoint + 8 tenant `set_config`) | 1 | 90 | 25.4 / 28.9 / 23.7 / 30.0 |
| after (`HEAD`) | 18 (9 + 9) | 2 | 90 | 29.7 / 31.9 / 26.6 / 33.5 |

Query count: **+1 data select (and the tenant listener's `set_config` it triggers), constant however many
elements the result names** — asserted by item 3's test, not inferred. Latency: +4.3 ms median in this run. An
earlier measurement of the same fixture on a quieter machine gave median 16.7 ms before and 18.0 ms after
(`p95` 24.8 and 21.7); this run was taken while a long `verify.py` was running on the same machine, so both
figures are noisy and the second is inflated by contention. Read them as "one extra indexed select adds low
single-digit milliseconds on a 90-row result", not as a measurement of NFR-5.

## Deviations from the brief

1. **Base commit.** `1cdd8c4d` instead of `31fbaece` in every `git diff` (instruction from the caller); the
   `31fbaece` form for `app/api/v1/impact.py` was also run and is empty.
2. **`plain_terms_sentence` is not module-private in the Python sense.** The brief calls it "module-private";
   `query_service.py` must import it from `plain_terms.py`, so it is a public name of that module
   (`__all__ = ["plain_terms_sentence"]`), private to the intelligence module and called from one place.
3. **Which endpoint is `{A}` and which is `{B}` is not stated in the brief.** Chosen: `{A}` is the derived fact's
   *target* and `{B}` its *source* ("target depends on source", the reading of a `Serving` chain), independent of
   the direction the caller queried in, so one fact yields one sentence from every surface. Consequence: for
   derived types where the source depends on the target (`Access`) or the relation is undirected (`Association`,
   and arguably `Composition`), "A depends on B" reads the wrong way round. That is a wording/product decision
   the template cannot settle; it is recorded as an open question below rather than resolved silently.
4. **The canonical endpoint's response does change, inside `derived_elements`.** The brief (B6) says
   `POST /api/v1/impact/analyze` keeps the response it has today. It calls `cross_layer_impact` and returns the
   derived rows verbatim under `derived_elements`; those rows now carry `derived_id`, `engine_version` and
   `plain_terms`, and `plain_terms` contains two element names. Verified on the running endpoint:

   ```
   CANON data keys: ['affected_elements', 'analysis_id', 'breakdown', 'derivation_state', 'derived_elements', 'diagram', 'risk_level', 'summary', 'total_score']
   CANON 'elements' in data: False
   CANON affected_elements key sets: [('id', 'level', 'name', 'type')]
   CANON derived_elements[0].relation keys: ['chain', 'chain_elements', 'computed_at', 'confidence', 'depth', 'derived_id', 'engine_version', 'kind', 'plain_terms', 'provenance', 'rule_id', 'stale', 'type']
   CANON derived_elements[0].relation.plain_terms: We worked this out because Charlie depends on Alpha, 2 hops away. Very confident (100%).
   ```

   No `elements` map is added, `affected_elements` is still exactly `{id, name, type, level}`, no other tenant's
   name can appear (the names come from the same fenced lookup), and the names are the same class of data as
   `affected_elements`' `name`. But the letter of B6 is not met, and it cannot be met without editing
   `impact.py` (forbidden) or adding a parameter to `cross_layer_impact` (forbidden by B1). I did not pin this
   behaviour with a test, because whether it is acceptable is not mine to decide. It needs a ruling before merge.
5. **Item 3's "the same way the existing owner-batching assertion does" has no referent.** No test in the tree
   counts owner-resolution queries. The counter here is modelled on `test_invalidation.py`'s
   `before_cursor_execute` statement counter.
6. **`--tag static` and the "partial run" banner.** The brief (and this repository's `CLAUDE.md`) say a filtered
   `verify.py` run prints `PARTIAL RUN`. `scripts/verify.py` at this commit contains no such text; a filtered run
   prints only "N gate(s) skipped and therefore NOT verified" for gates that skipped, and nothing for gates that
   were simply not selected. The static and six-gate runs above are therefore stated as partial here, by me.
7. **Repository guidance tension.** `CLAUDE.md` says not to hand-write `organization_id` filters on `TenantMixin`
   models (double filter); the brief and `derived_facts.list_derived_facts` say to. I followed the brief. The
   double filter is visible in the captured SQL and is harmless.
8. **One added rule.** `plain_terms_sentence` also returns `None` when `depth` is not an integer, and raises
   `TypeError` for a non-numeric `confidence`. The brief specified neither; both follow its "no sentence with a
   gap" and no-fabrication rules, and neither is reachable through the store (`depth` and `confidence` are NOT
   NULL there).

## Known gaps

- No NFR-5 latency verdict (no populated database); see above.
- `pgvector` is not installed in the local PostgreSQL; anything depending on it is unexercised here.
- `css-build` skipped (no vendored Tailwind CLI). This task changes no CSS.
- GitHub Actions was not run (nothing pushed). CI-only jobs — `secret-scan` (gitleaks), `security-sast` (bandit),
  `dependency-audit`, the browser jobs — did not run.
- This task adds no template or JavaScript, so the `tests/smoke/` browser tier was not extended and **no
  user-facing outcome is claimed**.
- Item 9's static check finds the sentence by its wording. A second generator that words it differently, or
  assembles it from fragments, would not be caught.
- An element whose name is an empty string is not "absent": the model allows it, the map carries it (a real
  value, not an invented one), and the sentence for a row ending at it is `null`.
- Everything above ran on Windows; CI runs on Linux.
- The repository-wide `tests/` tree did not run to completion (see the bare `verify.py` subsection); the
  `tests/journeys` failures seen there reproduce on the untouched base commit and were not diagnosed.

## Honesty section

- Every result in this report was produced by a command run in this session against a real PostgreSQL; the logs
  are the sources of the pasted lines. Nothing is estimated.
- The predicate mutation did **not** turn the request-shaped cross-tenant test red; it turned red only two direct
  calls to a private function. That is stated above and is the honest answer to item 11.
- Two tests (`..._with_no_ambient_request_context`, `..._when_the_ambient_tenant_diverges`) exercise a state no
  shipped path produces. One further test (`test_a_null_named_element_is_absent_not_a_null_entry`) stubs the
  result set because the database cannot produce a null name (`name` is NOT NULL); it pins a branch, not a
  reachable scenario.
- `test_derived_row_without_confidence_has_no_clause` wraps the store accessor to return a null confidence,
  because the store forbids one; same reason.
- The direction of "A depends on B" (Deviation 3) and the changed canonical `derived_elements` (Deviation 4) are
  judgment calls I could not settle from the brief.
- The bare `verify.py` did not come back clean, and the repository-wide test tree did not run to completion; both
  are reported above with what did and did not run. Acceptance item 14's second half ("`verify.py` runs clean") is
  therefore **not demonstrated** by this build.

## Open Questions

1. Deviation 4: is the canonical endpoint's `derived_elements` carrying `derived_id`, `engine_version` and a
   `plain_terms` sentence acceptable, or must the service gain a way to leave them off (which needs a brief
   change, since B1 and B6 forbid the obvious ways)?
2. Deviation 3: should `{A}` / `{B}` follow the fact's direction as built, or should the wording adapt to the
   derived relationship type?

## Handoff

Next role: `refuter`. Gate conditions believed met: `tests_reported_passing` for the suite the brief names (the
intelligence suite: 210 passed on a migrated database, 204 passed and 6 named skips on an unmigrated one); 54 of 58
`verify.py` gates green in the bare run; the 3 that are not are explained above (one is a missing tool, two follow
from the repository-wide `tests` gate timing out, which I did not reproduce on the base commit, so I cannot say the
timeout is independent of this change; the journey failures behind it are);
the four-key ceiling asserted per forbidden key; another tenant's name asserted absent from the response body;
unresolvable ids asserted absent on the cross-tenant and deleted branches; one query, inside the latency scope;
`impact.py` and `test_impact_route.py` byte-identical to base; the diff confined to the three source files, their
tests and this report. Items the refuter should look at first: Deviation 4, Deviation 3, and the split
mutation-proof result.
