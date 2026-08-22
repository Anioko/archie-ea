# Task 5 report — candidate discovery and acceptance

## Outcome

Implemented deterministic application-rationalisation discovery and fenced
candidate acceptance. Discovery is a pure read over canonical tenant records;
acceptance creates one `TransformationCandidate`, immutable cited
`CandidateSignal` rows, and—only when ownership is absent—a required
`application_owner` `EvidenceRequest`. It never copies an application and never
advances the workstream lifecycle.

Commit subject: `feat: add rationalisation candidate discovery` (the commit hash
is recorded in the parent handoff because this report is itself part of that
commit).

## RED evidence

- Initial focused command:
  `pytest -q tests/test_rationalisation_discovery_service.py tests/test_tenant_isolation.py -k candidate`
- Expected collection failure:
  `ModuleNotFoundError: No module named 'app.models.transformation_evidence'`.
- After the model boundary was added, the same command failed on the next absent
  interface:
  `ModuleNotFoundError: No module named 'app.modules.transformation_room.discovery_service'`.
- Steward-selection refinement was also test-first: two focused tests failed
  because the implementation selected the first `portfolio_manager` instead of
  the explicitly configured steward, and guessed that portfolio user instead of
  falling back to the workstream lead when no steward was configured.

## GREEN evidence

- `pytest -q tests/test_rationalisation_discovery_service.py tests/test_tenant_isolation.py tests/test_transformation_db_guards.py`
  — **47 passed**, 0 failed.
- `python scripts/verify.py --gate raw-sql-tenancy`
  — **1 passed**, measurement `0 <= 0`, no skips.
- `python scripts/verify.py --gate lint-core`
  — **1 passed**, measurement `0 <= 0`, no skips.
- `python scripts/verify.py --gate schema-drift`
  — **1 passed**, measurement `0 <= 0`, no skips.
- `python scripts/verify.py --gate compile`
  — **1 passed**, no skips.
- `python scripts/verify.py --gate undefined-exports`
  — **1 passed**, measurement `0 <= 0`, no skips.
- Focused Ruff over every changed Python/test file — **all checks passed**.
- `git diff --check` — clean.

An additional repository-wide `python scripts/verify.py --json` run was started.
It reached the full pytest gate and was confirmed actively consuming CPU, but it
was intentionally bounded after roughly thirteen minutes on the parent owner's
instruction so this scoped task could finish. It produced no final summary and
is not represented as a pass or a skip; the required focused/gate evidence above
is the commit basis.

## Scoring and source evidence

`RationalisationDiscoveryService.signal_rules()` returns seven stable,
inspectable rules in deterministic order:

1. capability overlap;
2. total cost of ownership;
3. end-of-life exposure;
4. technical/business/vendor/obsolescence risk;
5. technical health;
6. dependency concentration; and
7. owner/data gaps.

Every signal exposes its rule code/version, canonical observed values, exact
source record IDs grouped by source table, one evaluation timestamp, confidence,
named unknown code, and SHA-256 content hash. The tests seed real application,
capability-mapping and dependency rows and assert those exact IDs and observed
values. Missing cost, lifecycle, risk, health, capability and dependency inputs
produce named unknowns with `None` confidence and `None` observations—not
invented numeric zeroes. Discovery writes zero candidate/signal rows.

## Digest and acceptance evidence

The digest binds application ID, rule code/version, sorted source IDs, observed
values, confidence and unknown code in canonical JSON. Evaluation time is stored
as immutable provenance but is deliberately outside the digest, allowing the
same current facts to be recomputed in the fenced acceptance transaction.

Acceptance locks and tenant-loads the workstream, programme and application,
requires the workstream to remain at `discover`, recomputes every selected
signal, and rejects any unmatched current digest as
`candidate_signals_stale`. Persisted signal rows retain the recomputed evaluation
time and digest. The database guard installer adds an UPDATE/DELETE trigger to
`candidate_signals`; a direct PostgreSQL mutation test proves it raises the
append-only error.

The candidate natural key is
`candidate:<workstream_id>:application:<application_id>`, while database
uniqueness enforces `(organization_id, workstream_id, subject_type, subject_id)`.
A same-key/same-payload replay returns the original immutable result with no new
candidate, signals, request, application or outbox row. A different command key
for the same subject is rejected as `candidate_already_accepted`.

## Authorisation, tenancy, and lifecycle evidence

`authorise_candidate_acceptance(workstream_id, application_id)` is the mandatory
named `OperationAuthorizer`. It requires the exact operation and natural key,
tenant-loads both records using the supplied command session, verifies the
rationalisation workstream and application scope, and rechecks the persisted
programme/workstream authority. A replay after the actor loses their persisted
architect role is denied; client-supplied `ActorContext.roles` cannot authorize
it.

Every application, mapping, dependency, owner, user, candidate and workstream
query carries the explicit `actor.organization_id`. The shared tenant-isolation
test proves foreign-tenant candidate and signal primary-key reads return no row.
Application dependencies additionally tenant-check both graph endpoints.

Acceptance keeps the workstream at `discover` and revision 1. Missing ownership
creates a required open request assigned to the tenant-validated
`TRANSFORMATION_PORTFOLIO_STEWARD_ID`; if it is absent or invalid for the tenant,
the request goes to the tenant-validated workstream lead. It does not satisfy or
advance the Discover → Evidence gate.

## Self-review

- Scope: only Task 5 model/service/domain/guard/test interfaces and this report.
- Mutation check: tests catch a removed rule, hidden/default score, stale digest,
  missing source citation, duplicate acceptance, replay write, replay auth bypass,
  copied application, lifecycle advance, wrong steward fallback, mutable signal,
  and tenant-filter removal.
- Persistence: candidates reference canonical application IDs; no parallel
  application model or copied inventory row exists.
- Command integrity: all acceptance writes occur inside `CommandService`; no
  route/session commit was introduced.
- Existing guard compatibility: the complete pre-existing Task 3 database-guard
  suite remains green.

## Concerns / handoff

- Task 6 is expected to extend the deliberately minimal `EvidenceRequest` shell
  with the complete evidence-chain, submission, acceptance, acknowledgement and
  waiver persistence. Its stable identity/status fields already match that
  interface.
- The broad all-gates verifier was bounded without a result as described above;
  the parent integration wave should run it to completion after all SDD tasks are
  assembled.
