# Task Brief: T-005 — US-5 Derivation Yield & Health Report

## Objective
Ship the US-5 answer — "how much does derivation add" — as
`GET /api/v1/intelligence/yield`, reporting per-tenant explicit and derived
counts, their ratio, freshness and the measured p95 as a baseline that is
reported and never targeted, with a "not yet computed" state distinguishable
from a measured zero, and completes Release 1.

## Context
Source: `docs/buckets/archie-ea-four-intelligences-extension/tasks/T-005-us5-yield-report.md`
in `Anioko/sdlc-orchestrator` (fetched verbatim, reproduced in full below).
Depends on T-004 (US-1 endpoint and the latency probe/histogram) and T-003
(derived-fact store and recompute), both shipped tonight — T-003 merged as
PR #34 (`bddfb5cc`), T-004 merged as PR #35 (`31fbaece`), both deployed and
verified live in production.

- Design source: SDD v2 §AA-5 (`derivation_yield` query over derived-store
  aggregates), §API-5 (the yield endpoint), §OA-2 (latency source), §OA-3
  (yield ratio reported-not-targeted; SLO rows), §OA-4 (failure modes),
  Screens & Surfaces ("Yield & health"). ADR-009 records that the p95
  breach is a Shape-B trigger event, not a build authorisation.
- API-5 shape: per tenant `explicit_count`, `derived_count`, `ratio`,
  `computed_at`, `engine_version`, `stale_count`,
  `last_recompute_duration_ms`, `p95_latency_seconds` with `sample_count`.
  When derivation has never run the response carries BOTH `"state":
  "not_computed"` AND `"reason": "derivation_not_computed"` (so the counts
  are `null`, not `0` — a `0` meaning "not computed" is indistinguishable
  from a measured zero). Below 100 latency samples,
  `p95_latency_seconds` is `null` with `"reason":
  "insufficient_samples_for_p95"`.
- p95 is read from the Prometheus histogram `archie_intelligence_query_seconds`
  populated by T-004's probe (verify this histogram's exact name/labels
  against what T-004 actually shipped tonight — the brief for T-004 assumed
  `["query", "depth"]` but a refuter found `include_derived` needed adding
  as a third label; confirm the current label set before building the yield
  query against it). p95 is never computed or averaged in application code.
- The yield ratio is a baseline only: the "2,197 from 600" figure is one
  author's ArchiSurance run, disclaimed as non-representative by its own
  source; inventing a target from it is the exact fabrication the
  no-fabrication rule exists to prevent (OA-3 last row). The report states
  the measured figures; it sets no target.
- A p95 breach at the NFR-5 measurement point is written to the yield
  report as a dated, logged Shape-B trigger event (ADR-009); it opens the
  decision, it does not start the work.
- The "Yield & health" screen states explicit, derived, ratio,
  `computed_at`, stale count, last recompute, p95 with sample count, plus
  drift findings and gaps to fix; it states "derivation not yet computed"
  rather than zeros. **Per T-004's own descope decision tonight, confirm
  whether this screen exists yet before assuming it does** — T-004 found
  the Ask/Twin-map/Provenance-drawer screens don't exist anywhere in this
  codebase and descoped them to T-004b. If "Yield & health" is in the same
  situation, apply the same judgment: ship the verified API and descope the
  screen to a follow-up rather than inventing UI with no design basis.

## Constraints
- No fabricated target anywhere (FR-15, NFR-2, OA-3): counts are `null`
  (never `0`) when derivation has never run; `p95_latency_seconds` is
  `null` with a reason below 100 samples; the ratio is reported, never
  targeted; no benchmark-derived target appears.
- The "not computed" response carries both `"state": "not_computed"` and
  `"reason": "derivation_not_computed"` (F-13).
- p95 is read from the histogram, never recomputed in application code and
  never averaged.
- The endpoint is `@login_required`; persona-gated UI extends
  `tests/smoke/test_authorisation_matrix.py` rather than adding a bespoke
  smoke test.
- Register the blueprint non-fatally (**use T-004's already-registered
  `intelligence_api` blueprint** — do not create a second one; this
  exact mistake was caught and fixed in T-004's tech-lead scoping and must
  not be reintroduced here). Guard template links per DESIGN.md "Guarded
  nav links". No new store, container or dependency (NFR-6).
- Release 1 exposes no query surface beyond US-1 and US-5; do not add
  L2/US-2/Risk/Coverage endpoints here (NFR-8).
- Live defects SR-11, SR-12, SR-13 are out of scope here.

## Deliverable
- `IntelligenceQueryService.derivation_yield` in
  `app/modules/intelligence/services/query_service.py` (DE-11) — per-tenant
  aggregates over the derived-fact store, wrapped by `record_query_latency`
  (both already exist from T-004 — extend, don't duplicate).
- `GET /api/v1/intelligence/yield` (API-5) with the full field set above,
  the dual `state` + `reason` "not computed" response, and the sub-100-
  sample p95 null-with-reason behaviour, `@login_required`.
- The "Yield & health" screen calling API-5 — **or a descope record
  matching T-004's task-03 pattern if it doesn't exist yet and has no
  design basis to build from.**
- The dated, logged Shape-B trigger event record written to the yield
  report when the NFR-5 p95 measurement breaches 2.0s (ADR-009).
- Tests under `app/modules/intelligence/tests/`, a smoke-matrix extension,
  and a build report linking FR-7 → DE-11 → acceptance items with the
  mutation-proof record; a statement that Release 1 (L0 → L1 → US-1 → US-5)
  is complete.

## Acceptance Criteria
1. Fields present (FR-7): response carries `explicit_count`,
   `derived_count`, `ratio`, `computed_at`, `engine_version`,
   `stale_count`, `last_recompute_duration_ms`, `p95_latency_seconds` with
   `sample_count`, per tenant.
2. Not-computed branch (F-13): when derivation has never run, response
   carries BOTH `"state": "not_computed"` AND `"reason":
   "derivation_not_computed"`, every count `null` not `0`; test asserts a
   measured zero is distinguishable from not-computed.
3. Insufficient-samples branch: below 100 latency samples,
   `p95_latency_seconds` is `null` with `"reason":
   "insufficient_samples_for_p95"`, never a number.
4. No fabricated target: ratio reported, no target set; no
   benchmark-derived figure; test asserts no target field for yield.
5. p95 source: read from the `archie_intelligence_query_seconds`
   histogram, not computed/averaged in application code.
6. Shape-B trigger (ADR-009): a simulated p95 breach at the NFR-5
   measurement point writes a dated, logged trigger event to the yield
   report and starts no build work.
7. Screen honesty (if the screen exists/is built this task): renders
   "derivation not yet computed" not zeros; shows p95 with sample count;
   staleness on a non-colour channel.
8. Authorisation: new route extends `tests/smoke/test_authorisation_matrix.py`
   across the eleven canonical personas; `@login_required`.
9. Tenancy (NFR-4): yield aggregates per calling tenant; cross-tenant read
   returns no other tenant's counts.
10. Mutation proof: force counts to `0` on the not-computed path, confirm
    item-2's distinguishability test goes red; re-enable; record test id.
11. Release 1 completeness: no query surface beyond US-1/US-5 present
    (NFR-8); build report states L0→L1→US-1→US-5 complete, all Release 1
    acceptance gates green.

## Handoff Target
`tech-lead` — verify this brief's assumptions against what T-003/T-004
actually shipped tonight (the histogram's real label set, the derived-fact
store's real accessor shape, whether the "Yield & health" screen exists),
flag anything stale, and decompose into buildable task files following the
same pattern as T-003/T-004 tonight. This is the last Release 1 item —
route to `builder` after task files are written, and note in the final
build report that Release 1 is complete once this bucket's acceptance
criteria are green.
