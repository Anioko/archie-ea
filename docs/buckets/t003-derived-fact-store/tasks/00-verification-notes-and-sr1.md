# T-003 — tech-lead verification notes (read before task 01)

Not a task brief. This records what was re-verified against the code checked out on
branch `feat/t003-derived-fact-store`, which brief citations were wrong, and the
outcome of the SR-1 investigation. Every task file below assumes these corrections.

## Citation re-verification (all against this worktree, 18 Sep 2026)

| Brief claim | Verified | Correction |
|---|---|---|
| `app/models/__init__.py:360` `architecture_inference_relationship` import | drifted | now **`:365`** |
| `app/models/__init__.py:366` `acm_property_template` import | drifted | now **`:371`** |
| `app/models/acm_property_template.py:2` migration-exempt marker | correct | exact text below |
| `extensions.py:224-233` `init_scheduler` | correct | `def init_scheduler(app)` is still `:224`; `BackgroundScheduler()` at `:233` |
| `extensions.py:226-227` `app.testing` early return | correct | `if app.testing: return` at `:226-227` |
| `extensions.py:398-405` interval-job registration pattern | correct | typed-ARB waiver job, `max_instances=1` at `:404` |
| `tenant_safe_job.py:285` `run_for_each_tenant` | correct | |
| `tenant_safe_job.py:167` `tenant_scope` | correct | |
| `tenant_safe_job.py:199-246` `job_lock` / `pg_try_advisory_lock` | correct | `job_lock` `:199`, `pg_try_advisory_lock` `:231`, unlock `:246` |
| `tenant_safe_job.py:88-116` `JobRun` + `succeeded`/`failed` | correct | `JobRun` `:88`, `succeeded` `:105`, `failed` `:109` |

Why the scheduler line numbers did **not** move as the brief predicted: T-002's
`capability_projection` job was appended at `extensions.py:413-449`, i.e. *after*
every line the brief cites, immediately before `scheduler.start()` at `:451`. The
brief's warning was reasonable and simply did not come true — the numbers are live.

Exact marker text to replicate (`app/models/acm_property_template.py:2`):

```
# migration-exempt — new table created via db.create_all() (migration freeze)
```

It is line 2, directly under the module docstring, before any import.

## T-001 dependency — confirmed present, not assumed

- `app/modules/intelligence/services/derivation_runner.py` — `DerivationRunner`
  (`:50`), `DerivationRunner.run(organization_id) -> DerivationResult` (`:56`),
  `DerivationResult` (`:28`) with `explicit_count / derived_count / ratio /
  duration_ms / engine_version / derived`, and `ENGINE_VERSION = "1.0.0"` (`:24`).
  It computes and persists nothing — as documented. `run()` uses
  `tenant_scope(organization_id)` and adds no hand-written `organization_id`
  predicate.
- `app/services/archimate_derivation_service.py` — the ADR-002-v2 extended
  signature is genuinely present: `compute_derived` (`:95`) emits per-row
  `relationship_chain` (`:175`) and `rule_id` (`:176`, from `_rule_id` at `:69`),
  with `MAX_DEPTH = 5` (`:51`) and the `if depth >= MAX_DEPTH` cut at `:153`. The
  brief's note that the engine's real emitted depth range is 2..5 is correct.
- `app/modules/intelligence/__init__.py::register(app)` exists and is a no-op,
  explicitly reserving itself as T-003's wiring point. It **is** called —
  `app/_bootstrap/blueprints.py:174` → `_register_intelligence(app)` at `:1334`,
  which imports and calls it inside a try/except that logs and continues.
- `app/modules/intelligence/services/reason_codes.py` holds the closed vocabulary
  including `"derivation_stale"` and `validate_reason_code()`. **Use that function**
  for the read-path flag rather than writing the literal string at the call site.

## Brief claims that needed correcting

1. **`record_query_latency` does not exist.** Grepped the whole tree: the only hits
   are in the brief itself. There is no existing OA-2 structured record and
   therefore no "existing fields" to add `invalidated_rows` "alongside". Task 02
   treats this as a *new* module to create, not an extension.
2. **The advisory lock is per job *name*, not per tenant.** `job_lock(job_name)`
   hashes `f"archie_job:{job_name}"`, and `run_for_each_tenant` takes exactly one
   such lock for the whole sweep (`:313-318`). Acceptance item 9 ("one concurrent
   run *per tenant*", "a second concurrent tenant recompute reports
   `skipped_locked`") is therefore **not** satisfied by passing `use_lock=True` and
   hoping. The lock-naming design that does satisfy it is specified in task 03 and
   is binding — do not improvise a different one.
3. `run_for_each_tenant` calls `db.session.remove()` around every tenant
   (`_reset_session`, `:144`). The on-demand endpoint calls it from inside a
   request, so task 03 carries an explicit constraint about not letting that reach
   the request's own session or ORM objects.

## SR-1 — investigated, NOT found. State this in the build report.

The brief asks whether SR-1's condition ("the certification programme's
duplicate-authority collapse is confirmed scheduled on the same timeline as L0, or
FR-2 is re-priced as Shape-A scope") is knowable from anything in this codebase.

Searched, case-insensitively, across the whole worktree — `docs/adr/`,
`docs/buckets/`, `CLAUDE.md`, and every other tracked path — for: "certification
programme", "certification program", "certification gate", "duplicate-authority",
"duplicate authority", "Shape-A", "SR-1", "L0".

**Result: no such timeline exists in this repository.** Every hit for
"certification programme", "Shape-A" and "SR-1" is inside
`docs/buckets/t003-derived-fact-store/brief.md` itself — i.e. the brief is the only
document in the repo that mentions them, so it cannot corroborate itself. The two
non-brief hits are unrelated: `docs/ROADMAP_TO_BEST_IN_CLASS.md:51` uses "duplicate
authority" as a generic pointer to ADR 0008, and
`app/modules/capabilities/routes/mapping_routes.py:1243` uses the phrase in a code
comment about one fact having two relationship rows. Neither is a schedule, a
programme, or a commitment. `docs/adr/` contains ADRs 0001-0011 and none references
a certification programme.

**Conclusion and decision:** SR-1 is a genuinely external fact, not knowable from
here, and no answer is fabricated in either direction. Per the founder's explicit
authorization T-003 proceeds now. The builder **must** carry this forward verbatim
as an open item in the T-003 build report, under its own heading, worded as: *SR-1
remains unanswered; it was searched for in this repository and is not recorded
here; T-003 was built on explicit founder authorization to proceed, not on SR-1
being satisfied.* Do not soften it to "resolved", "N/A" or "assumed green".

The practical exposure if SR-1 later resolves the other way (FR-2 re-priced as
Shape-A) is bounded and worth stating: it would change T-002's maturity-authority
scope, which T-003 does not read or write. T-003's store is keyed on
`archimate_elements` / `archimate_relationships`, not on capability maturity. That
is an argument for the risk being low; it is not an argument for the question being
answered.
