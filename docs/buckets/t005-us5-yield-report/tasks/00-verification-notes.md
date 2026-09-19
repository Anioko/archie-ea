# T-005 / Task 00 — Tech-lead verification notes

**Not a build task.** This file records what was verified against the code as it
actually stands on this worktree (main + tonight's T-002/T-003/T-004 merges),
what the parent brief got wrong, and the corrected design decisions tasks 01–03
are written against. A builder reads this file first.

Everything below was read directly from source. Nothing is carried over from the
brief on trust.

---

## A. What the brief got right

- `intelligence_api` (`app/modules/intelligence/routes/api.py`, `url_prefix=
  "/api/v1/intelligence"`) is the single blueprint on that prefix, registered
  once and non-fatally in `app/modules/intelligence/__init__.py::register`. It
  is the correct and only place to add `GET /api/v1/intelligence/yield`. **No
  collision risk found** — no other blueprint claims this prefix, and no route
  named `yield`/`derivation_yield` exists anywhere. The T-004 D1 defect is not
  reintroduced. One thing to keep separate: the blueprint-local *view function*
  name must be `derivation_yield`; `cross_layer_impact` is already taken as a
  view name in that file (and as a `IntelligenceQueryService` method name — the
  two live in different modules, so `IntelligenceQueryService.derivation_yield`
  is unambiguous).
- Both reason codes the brief names — `derivation_not_computed` and
  `insufficient_samples_for_p95` — are **already members** of the DE-14 closed
  vocabulary in `app/modules/intelligence/services/reason_codes.py`. No addition
  needed for those two.
- `record_query_latency` exists (`services/latency_probe.py`) and is a context
  manager, exactly as the brief assumes.
- The store `archimate_derived_relationships` carries `computed_at`,
  `engine_version`, `stale`, `stale_since` per row — so `computed_at`,
  `engine_version` and `stale_count` are genuinely derivable per tenant.

## B. Defects found in the brief

### D1 — histogram label set: brief's guess is wrong (brief flagged this itself)

Verified in `app/services/prometheus_metrics.py` lines 120–133:

    INTELLIGENCE_QUERY_DURATION = Histogram(
        "archie_intelligence_query_seconds", ...,
        ["query", "depth", "include_derived"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        registry=REGISTRY)

and the recording call in `latency_probe.py` lines 102–106, which stringifies
`depth` (`"unknown"` when None) and `include_derived` (`"true"`/`"false"`).

**Three labels, not two.** The NFR-5 measurement point is therefore the exact
series `{query="cross_layer_impact", depth="4", include_derived="true"}` — a
p95 read that aggregates across label values mixes the cheap explicit-only
samples with the expensive derived walk and is meaningless, which is precisely
why T-004's refuter added the third label. Task 02 pins the selector.

### D2 — self-pollution: the yield query must not measure itself

The deliverable says `derivation_yield` is wrapped by `record_query_latency`.
That emits a **new** series `query="derivation_yield"`. If the p95 read
aggregated by `query` loosely, the yield endpoint would be reporting a p95
partly composed of its own cheap aggregate calls and drifting downward every
time someone loads the report. The p95 read is pinned to
`query="cross_layer_impact"` only. Non-obvious, and would not have failed any
test the brief specifies.

### D3 — "p95 never computed in application code" is not literally satisfiable here

`histogram_quantile` is a PromQL function; there is no Prometheus server in this
deployment and NFR-6 forbids adding a container. In-process, `prometheus_client`
exposes only cumulative bucket counters.

Resolution (binding): p95 is a **bucket-edge read**. Walk the histogram's own
cumulative `_bucket` counts for the pinned series; report the upper bound `le`
of the first bucket whose cumulative count reaches `0.95 * total`. No linear
interpolation, no averaging, no retention of raw samples, no arithmetic beyond
the comparison — the reported number is always one of the histogram's declared
boundaries, i.e. the metric's own value, not a derived statistic. The intent of
the constraint (no hand-rolled percentile over app-held samples) is honoured;
the letter of it is not achievable and pretending otherwise would be the
fabrication.

Consequence the brief does not cover: the top declared bucket is `5.0`. If the
95th percentile falls in `+Inf`, there is no honest number to report.
`p95_latency_seconds` is `null` with `"reason": "p95_above_highest_bucket"` and
`"p95_exceeds_seconds": 5.0` — never `5.0` reported as if measured. This is one
**new** member for the DE-14 vocabulary (see D7).

### D4 — p95 is process-local and estate-wide, NOT per tenant

`REGISTRY` is a module-level `CollectorRegistry` in the app process, and the
histogram carries **no `organization_id` label**. Production runs
`GUNICORN_WORKERS=3` with `preload_app = True`, so each worker holds its own
independent counts and a request is served by whichever worker answers.

Acceptance item 1 says every field is "per tenant". For `p95_latency_seconds`
and `sample_count` that is **false and unachievable** as built, and reporting a
process-local estate-wide number inside a per-tenant payload without saying so
is exactly the class of defect this repo's no-fabrication rule exists to stop —
the user cannot tell it apart from a tenant measurement.

Binding resolution: the p95 block is nested and self-describing —

    "p95": {"latency_seconds": ..., "sample_count": ...,
            "scope": "process_estate_wide", "query": "cross_layer_impact",
            "depth": 4, "include_derived": true, "reason": ...}

Adding an `organization_id` label to the histogram is explicitly **rejected**:
it is unbounded cardinality on the hottest metric this feature adds, and it
would change a metric T-004 shipped and deployed tonight. Task 02 carries a test
asserting `scope` is present and that the counts block and the p95 block are not
presented as the same measurement.

### D5 — `last_recompute_duration_ms` has no source at all (fabricated dependency)

This is the T-003/T-004-class defect in this brief. Traced end to end:

- `DerivationRunner.run()` measures `duration_ms` and puts it on a **frozen
  dataclass** `DerivationResult` (`derivation_runner.py` lines 96–108).
- `run_and_persist()` returns that dataclass. `_persist()` writes **no duration
  column** — `archimate_derived_relationships` has no such column (model read in
  full; columns are id, org, source/target, derived_type, rule_id, chain,
  chain_element_ids, depth, confidence, provenance, engine_version, computed_at,
  stale, stale_since, stale_reason).
- `recompute_job._recompute_one_tenant` puts it in a dict on `TenantResult.value`.
- `JobRun`/`TenantResult` (`app/jobs/tenant_safe_job.py`) are **in-memory
  dataclasses**. There is no job-run table. `run_for_each_tenant` returns the
  object and it is garbage-collected.
- The only place it ever reaches a human is the API-7 recompute response body,
  synchronously, to the caller who triggered it.

So `last_recompute_duration_ms` is **not readable** after the request that
produced it ends. The brief assumes it is.

### D6 — acceptance item 2 is unsatisfiable against the current store

Item 2 requires a measured zero to be distinguishable from "never computed".
From the derived store alone it is **not**: `DerivationRunner._persist`'s `else`
branch (lines 258–267) issues `DELETE FROM archimate_derived_relationships WHERE
organization_id = :organization_id` when the engine produces nothing. A tenant
that ran derivation and legitimately derived zero rows leaves **exactly zero
rows** — byte-identical to a tenant that never ran. The endpoint cannot tell
them apart, so it would either fabricate `not_computed` for a real measured zero
or fabricate a `0` for a never-run tenant. Item 2's own mutation-proof test
(item 10) would be unfalsifiable.

Note this is the same shape as the `unified_capabilities` failure CLAUDE.md
documents: the thing exists in the design and nothing produces it.

### D7 — resolution for D5 + D6: one small run-record table (decision, taken)

D5 and D6 have one common cause and one common fix: nothing in this codebase
records **that** derivation ran for a tenant, only what it left behind.

**Decision: add `intelligence_derivation_runs`** — one row per tenant per
completed `run_and_persist`, written by exactly one producer.

Why this overrides the brief's "no new store (NFR-6)": two acceptance criteria
(item 1's `last_recompute_duration_ms`, item 2's distinguishability) are
literally unbuildable without it, and the only alternatives are to fabricate a
value or to silently drop the criteria. CLAUDE.md's no-fabrication rule and
"a store with no producer is worse than no store" outrank a brief's constraint
shorthand. ADR 0008 is satisfied, not violated: no existing table or surface
answers "when did derivation last run for this tenant, and how long did it
take" — this is a first authority, not a second, and it ships with its producer
in the same task (task 01), never as an empty table wired into readers.

Rejected alternatives, for the record:
- *Column on `archimate_derived_relationships`* — the zero-row case is exactly
  the case that has no row to carry it. Fails D6 outright.
- *Column on `organizations`* — polluting a core tenant table with one feature's
  telemetry; worse blast radius than a scoped table.
- *Reuse an existing audit/event model* (`AuditLog`, `DecisionEvent`,
  `ARBAuditLog`, …) — each is the authority for a different question; bending
  one into a derivation-run log is the second-authority mistake in the other
  direction, and none carries a typed duration.
- *Report both fields as `null` forever* — hands the owner a report whose two
  headline honesty guarantees are permanently unmet, and quietly deletes items
  1 and 2.

Schema constraints it must respect (CLAUDE.md "Schema management"): new table,
so `create_all()` via `init-db` covers it; every non-key column nullable or
server-defaulted so `reconcile-schema` can add it to an existing database;
`TenantMixin`; carry the `# migration-exempt` marker the sibling model uses.

### D8 — `explicit_count` does not come from the derived store, and the ratio
must not become a second answer

`explicit_count` in `DerivationResult` is `len(relationships)` — a count of the
tenant's `ArchiMateRelationship` rows, not anything in the derived store. And
`ratio = derived_count / explicit_count`, `None` when explicit is zero.

`POST /api/v1/intelligence/derivation/recompute` **already returns
`explicit_count`, `derived_count` and `ratio`** (api.py lines 117–126). If the
yield endpoint computes these differently, two surfaces answer one question with
different numbers — the exact thing the `store-agreement` gate exists to catch.
Task 01 pins both to the same definitions and task 02 carries a test asserting
the two surfaces agree for the same tenant immediately after a recompute.

### D9 — `engine_version` must be read from the store, not the module constant

`ENGINE_VERSION = "1.0.0"` is a module constant in `derivation_runner.py`. A
tenant whose store was written by an older engine still holds the old value on
its rows. Reporting the constant would tell every tenant its facts are current
when they are not — a fabrication with the health report's name on it. Read the
distinct `engine_version` values present in the tenant's rows; when they differ
from the runner's current constant, that is a real finding the report states.

### D10 — the "Yield & health" screen does not exist (same situation as T-004)

Searched: `app/modules/intelligence/` has **no `templates/` directory and no
`routes/ui.py`**; `register(app)`'s reserved UI-blueprint slot is still unused
(its docstring still says "T-004 adds the UI blueprint" — T-004 descoped it and
correctly left the slot untouched). No template under `app/templates/` renders a
derivation yield or health report. The one grep hit for "yield" in templates
(`archimate_crud/partials/_repository_workspace.html`) is unrelated prose.

Identical to T-004's finding. Same judgment applies, and is taken: **the screen
is descoped to T-005b**, recorded in task 03. T-005 ships the endpoint.
Acceptance item 7 moves with it; item 8's authorisation-matrix row stays here,
scoped to the REST route.

### D11 — the Shape-B trigger event needs no new mechanism

There is no existing "architecture trigger event" record in this codebase, and
the brief is explicit that this is "a dated, logged trigger event", not a
workflow. The module already has the right pattern twice —
`observability.InvalidationRecord` and `latency_probe.QueryLatencyRecord`: a
frozen dataclass with `as_dict()`, logged at INFO. Task 02 follows it exactly
(`ShapeBTriggerRecord`, logged at WARNING since it is a breach, and echoed in
the response body so the report itself carries it). No table, no workflow, no
new dependency. Deliberately does **not** reuse `intelligence_derivation_runs` —
that store answers a different question.

### D12 — NFR-5 measurement point will usually have zero samples, and that is correct

The impact route defaults to `include_derived=false` and `max_depth=3`
(api.py lines 237–258), while the NFR-5 series is `depth="4",
include_derived="true"`. In a normal deployment the pinned series will often
hold **zero** observations. The correct output is then `latency_seconds: null`
with `insufficient_samples_for_p95` and `sample_count: 0` — not an error, not a
fallback to a looser selector. Builder must not "fix" an empty series by
widening the labels; task 02 forbids it in its constraints.

## C. Is this really the last Release 1 item?

Yes, with one L0 dependency the brief does not name — D9. Item 11 ("L0 → L1 →
US-1 → US-5 complete") cannot be asserted by counting merged buckets: L0's
`ENGINE_VERSION` is the value that makes the whole chain's output
interpretable, and the yield report is the first and only surface that reads it
back out of the store. So the Release-1 completeness check has a real L0 half:
the engine version on the tenant's persisted facts equals the runner's current
constant. Task 02 carries it as a test, not as a sentence in a report.

Item 11's other half — "no query surface beyond US-1/US-5" — needs a test that
enumerates `app.url_map` for `/api/v1/intelligence/*` and asserts **exactly
four** rules: the T-003 recompute POST, the T-003 provenance GET, T-004's impact
GET, and this task's yield GET. Recorded here so it is measured rather than
asserted: the provenance GET (API-2) is part of US-1's provenance answer and is
in scope; anything else appearing is an NFR-8 breach. T-002/T-003/T-004 have all
merged; nothing else in Release 1 is outstanding.

## D. Task files

- `01-run-record-and-yield-aggregates.md` — the run-record store with its
  producer, and the aggregate accessors. → `builder`
- `02-yield-endpoint-p95-read-and-shape-b-trigger.md` — the endpoint, the
  bucket-edge p95 read, the Shape-B record, the NFR-8 and Release-1 tests.
  → `builder`
- `03-yield-screen-descope-record.md` — decision record, no builder.
