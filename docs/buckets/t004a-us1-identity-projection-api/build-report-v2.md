# T-004a v2 — Build Report (response to the refuter's send-back)

Supersedes nothing in `build-report.md` (v1 is untouched). Where a v2 result replaces a v1 statement it is named
below.

Base: `origin/main` at `1cdd8c4d` (the brief's `31fbaece` in every `git diff` was read as `1cdd8c4d`, as in v1).
Branch: `feat/t004a-us1-identity-projection-api`, built on the v1 head `b6c2885a`. Nothing was pushed or merged.
The only network access in this pass was one read-only `git fetch origin main` to obtain `f2d9918a` for the merge
check.

| Commit | Content |
|---|---|
| `124c9511` | v2 code and tests in one commit (B-1, B-3, D-6, D-7, D-10, D-4 docstring) |
| (the commit that adds this file) | This report only |

## Disposition of the refuter's items

| Item | Ruling | Done in v2 | Where proved |
|---|---|---|---|
| B-1 (high) sentence direction | Type-aware wording, inside `plain_terms.py` and `_attach_plain_terms` only | Yes | "The eleven-row wording table"; tests `test_sentence_names_the_right_element_first_for_every_type[*]`, `test_every_derived_type_reads_the_same_from_every_query_direction`; mutations V1-V6, V10, V11 |
| B-2 canonical endpoint changed | ACCEPTED (B6 amended); do not suppress the keys, do not edit `impact.py` | No code change, as ruled. `impact.py` and `test_impact_route.py` byte-identical | `git diff 1cdd8c4d..HEAD -- app/api/v1/impact.py app/modules/intelligence/tests/test_impact_route.py` is 0 bytes (also 0 bytes for `impact.py` against `31fbaece`) |
| B-3 pin the canonical shape | Pin by test | Yes | `test_canonical_include_derived_true_pins_the_exact_derived_relation_key_set`, `test_canonical_default_request_returns_no_derived_rows_and_none_of_the_new_keys[key_absent, explicit_false]`; mutations V12-V15 |
| D-4 one-generator check is a text tripwire | Accepted as a known limit; state it in the test docstring | Yes | Docstring of `test_the_sentence_is_assembled_in_exactly_one_place` |
| D-6 "1 hops away" | Fix | Yes: `1 hop away` | `test_one_hop_is_singular[*]`, `test_a_depth_one_derived_fact_reads_1_hop_through_the_service`; mutation V7 |
| D-7 scan memory-fragile and over-broad | Fix: size guard, source directories only | Yes | "The one-generator scan (D-7)"; mutations V17, V18, R1-R3 |
| D-10 `result["elements"]` | Fix | Yes: `result.get("elements") or {}` | `test_route_degrades_to_an_empty_map_if_the_service_omits_elements`; mutation V16 |
| D-5, D-8, D-9 | Not in this fix; one line each in Known Gaps | Behaviour unchanged | "Known gaps" |
| Journeys-harness hazard | Out of scope | Not touched | — |

## Files changed in v2

`git diff --stat b6c2885a..124c9511`:

```
 app/modules/intelligence/routes/api.py             |   2 +-
 app/modules/intelligence/services/plain_terms.py   | 113 ++++--
 app/modules/intelligence/services/query_service.py |  14 +-
 app/modules/intelligence/tests/test_plain_terms.py | 411 ++++++++++++++++++---
 .../tests/test_query_service_elements_map.py       | 135 ++++++-
 5 files changed, 584 insertions(+), 91 deletions(-)
```

- `query_service.py`: the two hunks are both inside `_attach_plain_terms` (`git diff -U0` shows `@@ -239,4 +239,5 @@`
  and `@@ -250,2 +251,3 @@`, nothing else). It now passes the fact's stored source name, stored target name and
  stored type through unchanged; the choice of which is named first moved into `plain_terms.py`.
- `routes/api.py`: one line, D-10 only.
- `plain_terms.py`: the wording table, `wording_family()`, `SUPPORTED_TYPES`, `1 hop away`, and the refusals below.
- Whole branch against base (`git diff --name-only 1cdd8c4d..HEAD`): the three source files, four test files and
  the bucket's build reports. `app/api/v1/impact.py` and `test_impact_route.py` untouched. Nothing under the
  design-audit wave-1 files.

## The eleven-row wording table

Produced from real output: every one of the eleven derived types (every member of the derivation engine's
`STRENGTH_ORDER`; a transparent link passes the other link's type through, so all are storable) was written into
the real derived-fact store with stored source `SourceEl` and stored target `TargetEl<type>`, confidence 0.95,
depth 2, and read back through `cross_layer_impact` twice: downstream from the stored source and upstream from the
stored target. Both reads gave the identical sentence for all eleven (`"same": true` eleven times).

| Type | Stored source | Stored target | Sentence produced | Direction right? |
|---|---|---|---|---|
| Serving | SourceEl | TargetElServing | We worked this out because TargetElServing depends on SourceEl, 2 hops away. Very confident (95%). | Yes. The source serves the target, so the target depends on the source |
| Realization | SourceEl | TargetElRealization | We worked this out because TargetElRealization depends on SourceEl, 2 hops away. Very confident (95%). | Yes (ruled dependency family; the realised element depends on what realises it) |
| Assignment | SourceEl | TargetElAssignment | We worked this out because TargetElAssignment depends on SourceEl, 2 hops away. Very confident (95%). | Yes (ruled dependency family; the assigned-to element depends on what is assigned to it) |
| Triggering | SourceEl | TargetElTriggering | We worked this out because TargetElTriggering depends on SourceEl, 2 hops away. Very confident (95%). | Yes. The triggered element depends on what triggers it |
| Flow | SourceEl | TargetElFlow | We worked this out because TargetElFlow depends on SourceEl, 2 hops away. Very confident (95%). | Yes. The receiver depends on the sender |
| Access | SourceEl | TargetElAccess | We worked this out because SourceEl accesses TargetElAccess, 2 hops away. Very confident (95%). | Yes. The stored source is the accessor. v1 had this reversed |
| Composition | SourceEl | TargetElComposition | We worked this out because SourceEl is made up of TargetElComposition, 2 hops away. Very confident (95%). | Yes. Whole first, part second. v1 had this reversed |
| Aggregation | SourceEl | TargetElAggregation | We worked this out because SourceEl includes TargetElAggregation, 2 hops away. Very confident (95%). | Yes. Whole first, part second. v1 had this reversed |
| Specialization | SourceEl | TargetElSpecialization | We worked this out because SourceEl is a specific kind of TargetElSpecialization, 2 hops away. Very confident (95%). | Yes. The stored source is the specific one, the target the general one. v1 had this reversed |
| Association | SourceEl | TargetElAssociation | We worked this out because SourceEl and TargetElAssociation are linked, 2 hops away. Very confident (95%). | No direction asserted. The stored source is spoken first, and the order carries no meaning (a test swaps the ends and asserts only the names exchange places). v1 invented a dependency |
| Influence | SourceEl | TargetElInfluence | We worked this out because SourceEl influences TargetElInfluence, 2 hops away. Very confident (95%). | Yes. The stored source is the influencer; says influence, not dependency |

"Direction right?" is my reading of ArchiMate 3.2's relationship meanings (source and target as stored by the
engine), not a review by a domain expert.

Wording families (`wording_family(type)`): `dependency` (Serving, Realization, Assignment, Triggering, Flow: stored
target first, "depends on"), `access`, `whole-part` (Composition "is made up of", Aggregation "includes"),
`general-specific`, `symmetric`, `influence`.

Other rows produced in the same run (real store, real service):

```
PROBE_EXTRA {"type": "Serving", "depth": 1, "plain_terms": "We worked this out because Billing depends on Ledger, 1 hop away. Very confident (100%)."}
PROBE_EXTRA {"type": "Uses", "depth": 2, "plain_terms": null}
```

### Decisions I made that the rulings did not cover

1. **A type with no wording gives `plain_terms: null`, not a guess.** The engine can carry a non-standard
   relationship type through a transparent chain unchanged (it copies the other link's type), so a `derived_type`
   such as `Uses` is reachable. Guessing a direction for it is the defect B-1 was raised for; a null makes the
   consuming surface render its absence state. The row keeps every other field (`derived_id`, names in the map).
   The match is exact and case-sensitive (`serving`, `SERVING`, `Serving ` all give null), because the engine emits
   Title-case. **This needs confirmation** (Open Question 1).
2. A non-integer, boolean or non-positive depth gives null (the store's CHECK forbids it; this is the same
   "no sentence with nonsense in it" rule).
3. "whole and part" is worded "is made up of" for Composition and "includes" for Aggregation, so the two are not
   collapsed into one phrase. This wording is mine; the rulings leave polish to content design.
4. `plain_terms_sentence` now takes `source_name`, `target_name`, `relation_type`, `depth`, `confidence`
   (keyword-only). Its only caller is `_attach_plain_terms`, updated in the same commit.

## Tests

`test_plain_terms.py` 31 -> 71 tests, `test_query_service_elements_map.py` 30 -> 34. The new ones:

- **B-1 (table-driven, all eleven types):** `test_sentence_names_the_right_element_first_for_every_type[<type>]` x 11
  (full sentence equality, which end is named first, the wording family, and that swapping the stored ends changes the
  sentence); `test_every_derived_type_has_wording_and_no_type_is_missing` (the table's types are asserted equal to
  the engine's `STRENGTH_ORDER` and to `SUPPORTED_TYPES`, so a type added to the engine without wording is red);
  `test_non_dependency_types_never_say_depends_on[Access|Composition|Aggregation|Specialization|Influence]`;
  `test_association_wording_asserts_no_direction`; `test_type_without_wording_yields_no_sentence[*]` x 7;
  `test_every_derived_type_reads_the_same_from_every_query_direction` (all eleven through the real store and service,
  from the source and from each target); `test_a_derived_type_without_wording_has_no_sentence_and_keeps_its_other_fields`.
  The expectation table is written in the test from ArchiMate's meanings, not read back from the module.
- **D-6:** `test_one_hop_is_singular[1|2|3|5]`, `test_depth_below_one_yields_no_sentence[*]` x 5,
  `test_a_depth_one_derived_fact_reads_1_hop_through_the_service`.
- **B-3:** the two canonical tests above. `include_derived: true` pins the top-level key set, "no `elements`", the
  `affected_elements` key set `{id, name, type, level}`, the derived row key set and the exact relation key set
  (13 keys, the three new ones present). The default request, both with the key absent and with
  `include_derived: false`, pins `derived_elements == []`, `derivation_state == "current"` (a real current
  derivation exists, so the empty list is not vacuous), the unchanged top-level key set, no `elements`, and that
  none of `derived_id`, `engine_version`, `plain_terms`, `elements` appears as a key anywhere in the JSON document.
- **D-10:** `test_route_degrades_to_an_empty_map_if_the_service_omits_elements`.
- **D-7:** three tests of the scan itself (below).

### The one-generator scan (D-7)

The scan is now a helper, `_scan_for_sentence`, with its own tests. It walks only these tracked source
directories: `app`, `code_templates`, `scripts`, `sdk`, `templates`, `tools`, `deploy` (not `migrations`, `tests`,
`docs`, or anything at the repository root); it skips a file over 2,000,000 bytes without reading it (reads are
otherwise one file at a time, by `read_bytes`); and the real-tree test fails if any Python file is ever skipped that
way. On the real tree:

```
scanned: 3479 | offenders: [] | generator_hits: 5 | seconds: 4.3
skipped_large: ['app/static/vendor/mermaid.min.js']
```

The known limit (D-4, accepted) is in that test's docstring: it reads source text for the wording, so a second
generator that words the sentence differently, assembles the same output from fragments, or is a client-side build
of either, is not detected; it is a tripwire, not a proof.

## Mutation checks

Run on a `git archive HEAD` copy of `124c9511` (4,726 files), against a private PostgreSQL 17.5 database, never in
the worktree. After the whole run the copy was compared with `git archive HEAD` byte for byte:

```
compared 4726 files against git archive HEAD: 0 differing/missing; extra files (excluding __pycache__): 0 []
```

Every mutation restored its file(s) byte-identical (hash compared) and removed anything it created. Control, the
two changed test files unmutated on the archive copy: `105 passed`.

The mutation the coordinator asked for first: **swap the direction for one type and confirm red.**

| Id | Mutation | Tests that went red | Result |
|---|---|---|---|
| V1 | Access names the stored TARGET first | `test_sentence_names_the_right_element_first_for_every_type[Access]`, `test_non_dependency_types_never_say_depends_on[Access]`, `test_every_derived_type_reads_the_same_from_every_query_direction` | `3 failed, 68 passed` |
| V2 | Composition names the stored TARGET first | the same three, for `[Composition]` | `3 failed, 68 passed` |
| V3 | Specialization names the stored TARGET first | the same three, for `[Specialization]` | `3 failed, 68 passed` |
| V4 | Serving (dependency) names the stored SOURCE first | 22 tests: `[Serving]`, the brief example, all ten confidence-band cases, the null-confidence, measured-zero and no-confidence-clause tests, `test_one_hop_is_singular[1,2,3,5]`, the identity-map and 1-hop service tests, the all-types service test | `22 failed, 49 passed` |
| V5 | Association given directional wording | `test_association_wording_asserts_no_direction`, `test_sentence_names_the_right_element_first_for_every_type[Association]`, all-types service test | `3 failed, 68 passed` |
| V6 | Influence worded as a dependency | `test_non_dependency_types_never_say_depends_on[Influence]`, `...first_for_every_type[Influence]`, all-types service test | `3 failed, 68 passed` |
| V7 | depth 1 rendered "1 hops away" | `test_one_hop_is_singular[1-...]`, `test_a_depth_one_derived_fact_reads_1_hop_through_the_service` | `2 failed, 69 passed` |
| V8 | a type with no wording falls back to "depends on" | `test_type_without_wording_yields_no_sentence[None, "", Uses, serving, SERVING, 7, "Serving "]` (7), `test_a_derived_type_without_wording_has_no_sentence_and_keeps_its_other_fields` | `8 failed, 63 passed` |
| V9 | depth < 1 no longer refused | `test_depth_below_one_yields_no_sentence[0]`, `[-1]` | `2 failed, 69 passed` |
| V10 | `_attach_plain_terms` hands source and target over swapped | `test_derived_row_sentence_names_both_ends_from_the_identity_map`, `test_every_derived_type_reads_the_same_from_every_query_direction`, `test_a_depth_one_derived_fact_reads_1_hop_through_the_service`, `test_derived_row_without_confidence_has_no_clause` | `4 failed, 67 passed` |
| V11 | `_attach_plain_terms` always passes type "Serving" | `test_every_derived_type_reads_the_same_from_every_query_direction`, `test_a_derived_type_without_wording_has_no_sentence_and_keeps_its_other_fields` | `2 failed, 69 passed` |
| V12 | the `include_derived` gate forced open (a default request returns derived rows) | `test_canonical_default_request_returns_no_derived_rows_and_none_of_the_new_keys[key_absent]`, `[explicit_false]` | `2 failed, 3 passed, 29 deselected` |
| V13 | `impact.py` adds an `elements` map (archive copy only) | the two default-request tests, `test_canonical_include_derived_true_pins_the_exact_derived_relation_key_set`, and v1's `test_canonical_impact_endpoint_does_not_return_elements` | `4 failed, 1 passed, 29 deselected` |
| V14 | an extra key added to derived relation objects | `test_canonical_include_derived_true_pins_the_exact_derived_relation_key_set`, `test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http` | `2 failed, 6 passed, 26 deselected` |
| V15 | the `derived_id` key dropped from derived relation objects | the same two | `2 failed, 4 passed, 28 deselected` |
| V16 | route reverts to `result["elements"]` | `test_route_degrades_to_an_empty_map_if_the_service_omits_elements` | `1 failed, 33 deselected` |
| V17 | scan helper: size guard removed | `test_scan_skips_oversized_files_without_reading_them` | `1 failed, 2 passed, 68 deselected` |
| V18 | scan helper: source roots widened to the whole tree | `test_scan_ignores_scratch_copies_outside_the_source_roots` | `1 failed, 2 passed, 68 deselected` |
| R1 | real tree: scratch and backup copies of the generator at the repo root, in `scratch/`, and under `backup/app/...` | (none: the scan ignores them) | `1 passed, 70 deselected` |
| R2 | real tree: a copy of the generator inside `app/` | `test_the_sentence_is_assembled_in_exactly_one_place` | `1 failed, 70 deselected` |
| R3 | real tree: a 5 MB file inside `app/` carrying the sentence | (none: skipped unread, no error) | `1 passed, 70 deselected` |

Notes: V12-V15's `-k` selections were chosen by test-name keywords, not by listing tests, so their "passed" counts
are of the selected subset only. R1 and R3 are expected-green experiments, recorded to show the D-7 behaviour on the
real tree; R2 is the expected-red counterpart. V13 edits `impact.py` in the archive copy only, to show the
canonical pin would catch it; the real file is untouched.

## Verification

Environment as in v1 (Windows 11, Git Bash, Python 3.12.10 private venv, PostgreSQL 17.5 private cluster on port 5571
with its own data directory; the system service on 5432 never touched). Databases: clones of one that had
`init-db`, `reconcile-schema` and `flask apply-unified-capability-provenance-migration` applied, so nothing in the
intelligence suite skips.

Intelligence suite at `124c9511`, in the worktree:

```
$ pytest app/modules/intelligence/tests/ -q -p no:randomly -p no:cacheprovider -rs
================= 254 passed, 2 warnings in 90.25s (0:01:30) ==================
```

254 = 210 (v1) + 44 added in v2 (40 in `test_plain_terms.py`, 4 in `test_query_service_elements_map.py`). No skips.

Merged with current main, in a scratch clone (a clone of the worktree, `git fetch` of `origin/main` = `f2d9918a`,
`git merge upstream/main` there; the real branch was not merged):

```
merge commit 12f2a55b (scratch clone only), no conflicts
overlap files merged automatically: routes/api.py, services/query_service.py, tests/test_api_routes.py
$ pytest app/modules/intelligence/tests/ -q -p no:randomly -p no:cacheprovider -rs
================= 286 passed, 2 warnings in 135.30s (0:02:15) =================
```

286 = 254 + the 32 tests main added (the refuter's 242 = 210 + 32). The merged tree carries T-005's
`derivation_yield` and `test_module_registers_exactly_four_routes` alongside this branch's `_attach_plain_terms`
and the three v1/v2 tests in `test_api_routes.py`. It is still clean.

`python scripts/verify.py --tag static` at `124c9511` (a **partial run**, not "clean"):

```
  ok    raw-sql-tenancy            11.2s  [0 <= 0]
  ok    tenant-scoping             10.8s  [0 <= 0]
  ok    evidence-contract           0.3s  [29 <= 30]
  ok    silent-data                 9.1s  [0 <= 0]
  ok    fabricated-data             3.6s  [0 <= 0]
  ok    lint-core / undefined-names / redefinitions  [0 <= 0]
  ok    docs-drift / smoke-coverage-on-change        [0 <= 0]
  skip  css-build   (no vendored Tailwind CLI)
48 passed, 0 failed, 1 skipped
```

`ruff check app/modules/intelligence/` (ruff 0.16.0): `All checks passed!`

## Known gaps

- **D-5, not fixed here (routed to a later decision):** the element the caller asked about is absent from the map
  when no row names it (an empty result, or a stored chain with no ids), so a consumer cannot name it from this
  response alone. Behaviour unchanged.
- **D-8, not fixed here (waits for a populated-data latency reading):** the map is unbounded, growing with the
  number of distinct elements the result names; the query count stays constant. Behaviour unchanged.
- **D-9, not fixed here (a product decision):** an element whose name is only whitespace is carried in the map
  verbatim (the sentence for a row ending at it is null). Behaviour unchanged.
- **D-4, accepted:** the one-generator check is a source-text tripwire and does not detect a differently worded or
  fragment-built generator (recorded in the test's docstring).
- The bare `python scripts/verify.py` was **not re-run** in v2, and the repository-wide `tests/` tree was not run.
  v1's result stands: not clean on this machine (the `tests` gate timed out; `nav-verified` depends on it; the
  `tests/journeys` login failures reproduce on the untouched base commit). The six runtime gates (`schema-drift`,
  `boot-health`, `store-agreement`, `csrf-coverage`, `broken-surfaces`, `dynamic-link-prefixes`) were not re-run
  either; v2 adds no route, model, column, table, template or script, so I expect no change but did not measure it.
- No NFR-5 latency verdict, and no re-measurement: v2's change to the request path is one in-memory function
  (`_attach_plain_terms` and the sentence builder); no query was added or changed.
- The journeys-harness hazard is out of scope and untouched.
- CI (Linux, gitleaks, bandit, browser jobs) did not run; everything here ran on Windows.

## Honesty section

- Every count and result line above was produced by a command run in this session against a real PostgreSQL 17.5;
  the eleven-row table is real service output, not typed.
- "Direction right?" is my reading of ArchiMate 3.2, not an expert review. Realization and Assignment read
  "depends on" because the ruling put them in the dependency family; I did not re-derive that.
- Decision 1 (unknown type gives null) goes beyond the letter of the ruling and is flagged for confirmation.
- The unknown-type null, exact-match casing, and depth refusals are new behaviour; they are covered by tests and
  mutations V8 and V9.
- V12-V15 select tests by keyword; the "passed" counts are for those subsets.
- The mutation and merge work used scratch copies outside the worktree; the worktree stayed clean (`git status
  --porcelain` empty) and `HEAD` unchanged during those runs.

## Open Questions

1. A derived type outside the eleven (for example `Uses`) currently gets no sentence. Should it instead get the
   symmetric "are linked" wording? Null keeps the absence state; symmetric keeps some information but says
   "linked" about a relationship whose meaning this module does not know.
2. Content design polish (does not block): "is made up of" / "includes", "is a specific kind of", "accesses",
   "influences", "are linked", and whether Realization and Assignment should keep "depends on".

## Handoff

Next role: `refuter`, scoped to the diff between `b6c2885a` and `124c9511` (plus this report). Gate conditions
believed met: B-1 closed (all eleven types, direction pinned and mutation-checked); B-3 closed (canonical shape
pinned for `include_derived: true` and for the default request); D-4 recorded, D-6, D-7, D-10 fixed; the diff stays
inside `plain_terms.py`, `_attach_plain_terms`, one line of `routes/api.py` and the tests; `app/api/v1/impact.py`
and `test_impact_route.py` byte-identical; intelligence suite 254 passed and, merged with `f2d9918a`, 286 passed.
Not demonstrated: a clean bare `verify.py` (unchanged from v1).
