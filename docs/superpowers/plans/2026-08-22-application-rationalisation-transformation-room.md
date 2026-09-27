# Application Rationalisation Transformation Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Release 1 of a reusable, business-first Transformation Room whose first complete workstream is Application Rationalisation, including governed evidence, typed ARB decisions, canonical execution and measured outcomes without requiring a technology Solution.

**Architecture:** `StrategicInitiative` is the Transformation Programme aggregate root; focused tenant-scoped children hold workstreams, roles, outcomes, candidates, evidence, options and decision briefs. Thin HTML/API routes call transactional domain services through a fenced idempotent command runner; the existing `ARBSubmissionService` becomes the sole typed governance writer, while `WorkPackage`, `RoadmapItem`, `Benefit` and optional `Solution` remain canonical downstream records. Release 1 uses compatibility bridges and a measured production-like migration rehearsal, but does not retire `EnterpriseInitiative` or legacy rationalisation reads.

**Tech Stack:** Python 3, Flask, Flask-Login, Flask-WTF/CSRF, SQLAlchemy 2.0, PostgreSQL constraints/functions/triggers, Jinja2, Alpine.js, Tailwind/shadcn design tokens, pytest, Playwright/axe-core, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-22-application-rationalisation-transformation-room-design.md`

## Global Constraints

- Release 1 delivers the canonical programme/workstream journey, application-rationalisation flow, non-Solution ARB subject, execution/outcomes, compatibility reads and production proof for newly created and safely mapped records. It does not claim `EnterpriseInitiative` or legacy rationalisation retirement.
- `StrategicInitiative` is the target aggregate now. `EnterpriseInitiative` is a migration source bridged into it and later retired as a programme meaning. There is no indefinite dual-write or façade preserving two authorities.
- No slice may introduce a temporary alternative source of truth. Partial UI remains hidden until its end-to-end command path and failure states are real.
- Every tenant-scoped child inherits `TenantMixin`; every supplied identifier is loaded with an explicit `organization_id` predicate, and background or migration loops clear the SQLAlchemy identity map between organisations.
- Unauthenticated HTTP is `401`; an authenticated actor lacking a general action receives `403`; an identifier outside the active tenant receives `404` without disclosing its tenant, title or existence.
- Payload identity and state fields (`organization_id`, `created_by_id`, `decision_by_id`, readiness, review status and lifecycle status) are ignored or rejected; authenticated server context supplies identity and persisted state.
- Browser mutations retain CSRF protection. JSON mutations require `Idempotency-Key`, use `(organization_id, actor_id, operation, idempotency_key)` uniqueness, bind a request digest, and reject digest reuse with `409`.
- Command claims use a monotonically increasing `lease_generation` and cryptographically random `claim_token`; a worker checks both under a locked receipt before domain writes and finalisation. Domain mutation, immutable `OperationResult`/outbox insertion and receipt success finalisation commit atomically.
- Each command has a database-enforced natural key. On lease expiry, reconcile `OperationResult` and the natural-key record before re-execution. `retryable_failure` is never returned as business success.
- Every public command entry requires a callable, operation-specific `OperationAuthorizer`. It runs before receipt creation, immutable-result replay, natural-key resolution or the mutation handler; `None`, non-callables and permissive defaults are forbidden.
- `EvidenceRecord`, `EvidenceHeadEvent`, `TransformationOptionVersion`, `DecisionBriefVersion`, brief citations, `DecisionEvent`, `ARBSubjectEvidenceSnapshot`, `OutcomeMeasurement`, `OperationResult` and completed `DeliveryExportAttempt` are append-only; PostgreSQL rejects direct `UPDATE` and `DELETE`.
- Evidence head movement occurs only through the fixed-search-path `SECURITY DEFINER` guarded function, with same-chain identity, predecessor, exact revision increment, current fenced command and same-transaction `EvidenceHeadEvent` checks.
- `source_identity` is non-null and canonically normalised. Manual attestations use `attestation:user:<user_id>`; unknowns use `unknown:<responsible-role>:<stable-scope-key>`; empty, whitespace-only or non-canonical values are rejected.
- A decision brief is the logical governed subject, and every ARB cycle pins one immutable `DecisionBriefVersion`. Existing Solution, ArchitectureModel and ADR governance remains supported through typed adapters; `ARBSubmissionService` is the sole public submission writer.
- Any ARB condition produces `ApprovedWithConditions`. Execution remains blocked until every condition has accepted evidence or an authorised, reasoned, expiring waiver and the projection moves to `Approved`.
- Programme creation at `/solutions/new-programme` persists programme, owner, initial outcome/measure and first workstream in one transaction and never creates a `Solution`.
- A `Solution` is created only from an approved option with `technology_architecture_required = true` and only after an authorised architect explicitly selects **Create technology solution**.
- Canonical delivery uses `WorkPackage`, `RoadmapItem` and `Benefit`; programme/workstream deletion is `RESTRICT`, archive preserves history, and compatibility reads prefer canonical foreign keys.
- Monetary values use `Numeric(18,2)` with ISO-4217 currency; percentages and quantities use `Numeric(24,6)`. Binary float is not used for Transformation Room facts.
- Missing, unknown or not-computable values remain `None`/JSON `null` and display as an em dash (`—`) with an unavailable reason; no missing value is coerced to zero.
- AI may draft and rank with citations and confidence, but may not attest, approve, choose a governing source, assert human review, decide, materialise execution or fabricate success.
- Read `DESIGN.md` completely before changing any template, CSS or front-end JavaScript. Use shadcn tokens, accessible landmarks/labels/focus, keyboard operation, server-rendered fallbacks, local assets and `Platform.toast`; never use native `alert()`/`confirm()` or shipped `console.log`.
- Every motivation or implementation entity created through an existing ArchiMate-backed service, including `WorkPackage`, continues to call the canonical `_sync_archimate_element()` path.
- New behaviour is test-first against shared fixtures in `tests/conftest.py`; PostgreSQL is required. A skipped gate is not a pass.
- Stage files explicitly; never use `git add -A`. Commit messages use a temporary message file with `git commit -F`, never PowerShell here-strings or shell-interpreted backticks.
- Release 1 is not complete until focused tests, PostgreSQL race/trigger tests, tenancy/authorisation/schema gates, templates/CSS/accessibility, `python scripts/verify.py --json`, CI-only gates, independent review, production-like migration rehearsal, exact-commit deployment, and production synthetic journeys are all green.

## File and dependency map

Create one canonical module at `app/modules/transformation_room/`; do not add another programme or ARB blueprint. Models remain in `app/models/` because both canonical and compatibility services consume them.

| File | Responsibility |
|---|---|
| `app/models/transformation_programme.py` | Programme workstreams, roles, outcomes and measures |
| `app/models/transformation_evidence.py` | Candidates, immutable evidence, claim heads/events and requests |
| `app/models/transformation_decision.py` | Options/versions, briefs/versions/citations/events and ARB cycles/snapshots |
| `app/models/transformation_execution.py` | Idempotency receipts/results, export attempts and outcome measurements |
| `app/models/transformation_migration.py` | Legacy bridge, migration attachment/conflict/run records |
| `app/modules/transformation_room/domain.py` | Enums, `ActorContext`, result/error types and transition vocabulary |
| `app/modules/transformation_room/command_service.py` | Fenced claim/reconcile/execute protocol and immutable result envelope |
| `app/modules/transformation_room/programme_service.py` | Programme intake, roles, outcomes, read/update/archive and roll-up |
| `app/modules/transformation_room/gate_service.py` | Pure, versioned lifecycle gate evaluation and transitions |
| `app/modules/transformation_room/discovery_service.py` | Deterministic candidate signals and acceptance |
| `app/modules/transformation_room/evidence_service.py` | Source adapters, requests, attestations, conflicts and guarded head movement |
| `app/modules/transformation_room/decision_service.py` | Option drafts/versions, comparison and immutable brief freezing |
| `app/modules/transformation_room/arb_adapters.py` | Four typed ARB subject adapters |
| `app/modules/transformation_room/execution_service.py` | Canonical work/roadmap/benefit materialisation and optional Solution |
| `app/modules/transformation_room/outcome_service.py` | Append-only measurements, compatible Benefit projection and variance |
| `app/modules/transformation_room/migration_service.py` | Profile, dry-run, safely map, verify and compatibility resolution |
| `app/modules/transformation_room/routes.py` | Stable server-rendered room and deep-link routes |
| `app/modules/transformation_room/api.py` | Versioned JSON resources and consistent envelopes |
| `app/modules/transformation_room/read_models.py` | Stage pages, portfolio discovery and Chief Architect synthesis projections |

Dependency order is Tasks 1–3 foundations; Tasks 4–7 programme/evidence/decision; Task 8 typed governance; Task 9 execution/outcomes; Task 10 API; Task 11 UI/IA; Task 12 AI integration; Task 13 migration/compatibility; Task 14 full journey/rehearsal; Task 15 final review, release and production proof.

## Shared type contract

Task 3 creates these immutable boundary types in `app/modules/transformation_room/domain.py`; every later task imports them rather than redefining response or identity shapes:

```python
@dataclass(frozen=True)
class ActorContext:
    user_id: int
    organization_id: int
    roles: frozenset[str]
    request_id: str

@dataclass(frozen=True)
class CommandClaim:
    receipt_id: int
    generation: int
    claim_token: str
    request_digest: str
    natural_key: str

@dataclass(frozen=True)
class DomainMutationResult:
    object_ids: Mapping[str, int]
    response: Mapping[str, Any]
    outbox_events: Sequence[Mapping[str, Any]]

@dataclass(frozen=True)
class CommandResult:
    created: bool
    idempotent: bool
    operation_result_id: int
    object_ids: Mapping[str, int]
    response: Mapping[str, Any]

@dataclass(frozen=True)
class GateBlocker:
    code: str
    message: str
    resource_type: str | None
    resource_id: int | None
    action_url: str | None

@dataclass(frozen=True)
class GateResult:
    allowed: bool
    current_stage: str
    target_stage: str
    policy_version: str
    blockers: Sequence[GateBlocker]
    warnings: Sequence[GateBlocker]
    evidence_ids: Sequence[int]

@dataclass(frozen=True)
class ProgrammeIntake:
    name: str
    objective: str
    owner_id: int
    target_date: date | None
    target_date_unavailable_reason: str | None
    workstream_type: str
    scope_expression: Mapping[str, Any]
    outcome: Mapping[str, Any]

@dataclass(frozen=True)
class ProgrammeView:
    programme_id: int
    workstream_ids: Sequence[int]
    lifecycle: str
    owner_id: int
    next_action: GateBlocker | None

@dataclass(frozen=True)
class DiscoveryFilters:
    business_unit_ids: Sequence[int]
    capability_ids: Sequence[int]
    include_archived: bool = False

@dataclass(frozen=True)
class DiscoveryCandidate:
    application_id: int
    signal_digests: Sequence[str]
    confidence: Decimal | None
    unknown_codes: Sequence[str]

@dataclass(frozen=True)
class TypedEvidenceValue:
    value_type: str
    value: Any
    unit: str | None
    currency: str | None

@dataclass(frozen=True)
class SourceResolution:
    source_identity: str
    canonical_subject_type: str
    canonical_subject_id: int

@dataclass(frozen=True)
class SourceVersion:
    version: str
    checksum: str
    observed_at: datetime
    value: TypedEvidenceValue

@dataclass(frozen=True)
class FreshnessResult:
    status: str
    expires_at: datetime | None
    rule_version: str

@dataclass(frozen=True)
class HumanAssertions:
    reviewed_ai_material: bool
    acknowledged_unknown_codes: Sequence[str]
    acknowledged_superseded_evidence_ids: Sequence[int]
    rationale: str

@dataclass(frozen=True)
class OptionComparison:
    option_version_ids: Sequence[int]
    comparable_currency: str | None
    cost_range: tuple[Decimal, Decimal] | None
    benefit_range: tuple[Decimal, Decimal] | None
    conflicts: Sequence[str]

@dataclass(frozen=True)
class BriefReadiness:
    ready: bool
    gate: GateResult
    option_version_ids: Sequence[int]
    evidence_ids: Sequence[int]

@dataclass(frozen=True)
class GovernedSubject:
    subject_type: str
    subject_id: int
    organization_id: int
    title: str
    logical_version_id: int | None

@dataclass(frozen=True)
class PinnedEvidence:
    evidence_type: str
    evidence_id: int
    content_hash: str

@dataclass(frozen=True)
class ApprovedAction:
    action_key: str
    option_version_id: int
    title: str
    owner_id: int
    start_date: date | None
    target_date: date | None
    scheduling_applicable: bool

@dataclass(frozen=True)
class StageView:
    programme: ProgrammeView
    workstream_id: int
    stage: str
    gate: GateResult
    resources: Mapping[str, Sequence[Mapping[str, Any]]]
    unavailable_reasons: Mapping[str, str]

@dataclass(frozen=True)
class TransformationPortfolioView:
    programmes: Sequence[ProgrammeView]
    evidence_debt: Mapping[str, int | None]
    decision_ageing: Mapping[str, Decimal | None]
    delivery_confidence: Mapping[str, Decimal | None]
    outcome_variance: Mapping[str, Decimal | None]

class TransformationError(Exception):
    code: str
    http_status: int

class CommandConflict(TransformationError):
    code, http_status = "conflict", 409

class StaleClaim(CommandConflict):
    code = "stale_claim"

class KnownPreCommitTransient(TransformationError):
    code, http_status = "retryable_failure", 503

class NotAuthorised(TransformationError):
    code, http_status = "not_authorised", 403

class NotFound(TransformationError):
    code, http_status = "not_found", 404

class BlockedByEvidence(TransformationError):
    code, http_status = "blocked_by_evidence", 422

class AuthenticationRequired(TransformationError):
    code, http_status = "not_authenticated", 401
```

The public service signatures are fixed before implementation and are used unchanged by later tasks:

| Service | Exact public signature |
|---|---|
| Programme | `create_programme(*, actor: ActorContext, command_key: str, request: ProgrammeIntake) -> CommandResult` |
| Programme | `get_programme(*, actor: ActorContext, programme_id: int) -> ProgrammeView` |
| Programme | `update_objective(*, actor: ActorContext, workstream_id: int, objective: str, scope_expression: Mapping[str, Any], expected_revision: int, command_key: str) -> CommandResult` |
| Programme | `assign_role(*, actor: ActorContext, programme_id: int, workstream_id: int | None, user_id: int, role: str, effective_from: date, effective_to: date | None, expected_revision: int, command_key: str) -> CommandResult` |
| Programme | `archive(*, actor: ActorContext, programme_id: int, reason: str, expected_revision: int, command_key: str) -> CommandResult` |
| Gate | `evaluate(*, actor: ActorContext, workstream_id: int, target_stage: str) -> GateResult` |
| Gate | `transition(*, actor: ActorContext, workstream_id: int, target_stage: str, expected_revision: int, command_key: str) -> CommandResult` |
| Gate | `next_action(*, actor: ActorContext, workstreams: Sequence[ProgrammeWorkstream]) -> GateBlocker | None` |
| Discovery | `discover(*, actor: ActorContext, workstream_id: int, filters: DiscoveryFilters) -> Sequence[DiscoveryCandidate]` |
| Discovery | `accept_candidate(*, actor: ActorContext, workstream_id: int, application_id: int, signal_digests: Sequence[str], inclusion_reason: str, command_key: str) -> CommandResult` |
| Evidence | `record_observation(*, actor: ActorContext, candidate_id: int, claim_key: str, adapter_key: str, source_key: str, expected_head_revision: int, command_key: str) -> CommandResult` |
| Evidence | `submit_attestation(*, actor: ActorContext, request_id: int, value: TypedEvidenceValue, expected_head_revision: int, command_key: str) -> CommandResult` |
| Evidence | `accept_request(*, actor: ActorContext, request_id: int, evidence_id: int, expected_revision: int, command_key: str) -> CommandResult` |
| Evidence | `resolve_conflict(*, actor: ActorContext, conflict_evidence_id: int, governing_evidence_id: int, rationale: str, command_key: str) -> CommandResult` |
| Evidence | `active_evidence(*, actor: ActorContext, subject_type: str, subject_id: int) -> Sequence[EvidenceRecord]` |
| Option | `freeze_version(*, actor: ActorContext, option_id: int, expected_revision: int, command_key: str) -> CommandResult` |
| Option | `compare(*, actor: ActorContext, option_version_ids: Sequence[int]) -> OptionComparison` |
| Brief | `evaluate(*, actor: ActorContext, brief_id: int) -> BriefReadiness` |
| Brief | `freeze(*, actor: ActorContext, brief_id: int, option_version_ids: Sequence[int], evidence_ids: Sequence[int], assertions: HumanAssertions, expected_revision: int, command_key: str) -> CommandResult` |
| Brief | `verify_hash(version: DecisionBriefVersion) -> bool` |
| ARB | `evaluate(*, subject_type: str, subject_id: int, actor: ActorContext, assertions: Mapping[str, Any]) -> ARBReadinessResult` |
| ARB | `submit(*, subject_type: str, subject_id: int, actor: ActorContext, assertions: Mapping[str, Any], command_key: str) -> ARBSubmissionResult` |
| Execution | `materialise(*, actor: ActorContext, decision_brief_version_id: int, actions: Sequence[ApprovedAction], command_key: str) -> CommandResult` |
| Execution | `create_technology_solution(*, actor: ActorContext, decision_brief_version_id: int, option_version_id: int, command_key: str) -> CommandResult` |
| Outcomes | `record(*, actor: ActorContext, benefit_id: int, value: Decimal | None, unavailable_reason: str | None, observed_at: datetime, source_identity: str, source_version: str, command_key: str) -> CommandResult` |
| Migration | `profile(*, organization_id: int) -> MigrationProfile` |
| Migration | `plan(*, organization_id: int, resume_cursor: str | None) -> MigrationPlan` |
| Migration | `apply(*, organization_id: int, migration_plan: MigrationPlan, command_key: str) -> MigrationReport` |
| Migration | `verify(*, organization_id: int, migration_run_id: int) -> MigrationVerification` |
| Room read | `stage(*, actor: ActorContext, programme_id: int, workstream_id: int, stage: str) -> StageView` |
| Chief Architect read | `portfolio(*, actor: ActorContext) -> TransformationPortfolioView` |

Task 13 defines `MigrationProfile`, `MigrationPlan`, `MigrationReport` and `MigrationVerification` as frozen dataclasses whose fields are respectively: source counts/references/nulls/duplicates/invalid-FKs/currency totals/fingerprints; deterministic ordered row actions/conflicts/resume cursor; run ID/mapped IDs/unmapped IDs/conflict IDs/checksums; and before/after reconciliation/differences/verified boolean. No route or caller consumes an untyped dictionary for migration truth.

## Spec Coverage Matrix

| Approved specification section | Implemented and proved by |
|---|---|
| 1. Outcome and design principles | Tasks 4–12; end-to-end proof in Task 14 |
| 2. Personas, jobs and success measures | Tasks 11–12 projections/telemetry; all persona journeys in Task 14 |
| 3. Release 1 scope and non-goals | Global Constraints; compatibility boundary in Task 13; release assertion in Task 15 |
| 4.1 Aggregate ownership | Tasks 1, 5–9 and 13 |
| 4.2 Relationships and ownership rules | Task 1 FK/tenant constraints; Tasks 6–9 membership/race constraints |
| 5. Lifecycle and gates | Task 4 pure policy/transition service; Tasks 6–9 gate evidence; Task 14 journey transitions |
| 6. Objective | Task 4 service and Task 11 intake |
| 6. Discover | Task 5 |
| 6. Evidence | Task 6 |
| 6. Options | Task 7 |
| 6. Decision/Govern | Tasks 7–8 |
| 6. Execute | Task 9 canonical materialisation/export |
| 6. Outcomes | Task 9 measurement and corrective follow-up |
| 7. Evidence, provenance and immutability | Tasks 3 and 6–7 direct-SQL and concurrency proof |
| 7.1 Source adapters and conflicts | Task 6 |
| 7.2 UnifiedCapability tenancy cutover | Task 2 plus production-like rehearsal in Task 14 |
| 8. Tenant isolation, identity and authorisation | Every model/service task; API matrix in Task 10; integrated matrix in Task 14 |
| 9. Service/API and fenced idempotency boundaries | Tasks 3–10; crash/reclaim proof in Tasks 3 and 14 |
| 10. User experience and information architecture | Task 11; browser proof in Task 14 |
| 11. Release 1 migration and compatibility phases A–C | Task 13; production-like backup rehearsal in Task 14 |
| 11. Retirement phase D | Explicitly excluded from Release 1; Task 13 retains measured bridges and zero dual-write |
| 12. Failure handling and observability | Tasks 10 and 12; synthetic failure assertions in Task 14 |
| 13. Release 1 acceptance and repository/production gates | Tasks 14–15 |
| 13. Retirement Release acceptance | Explicitly excluded; no retirement claim in Tasks 13 or 15 |
| 14. Rollout and rollback | Task 15 schema-hidden rollout, cohort enablement and rollback rehearsal |
| 15. Delivery slices | Tasks 1–15 in dependency order |
| 16. Independent review resolutions 1–4 | Tasks 1–9 schema, conditions, fencing, evidence-head and four-adapter proofs; final independent review in Task 15 |

---

### Task 1: Canonical programme, workstream, outcome and delivery-link schema

**Files:**
- Create: `app/models/transformation_programme.py`
- Modify: `app/models/strategic.py`
- Modify: `app/models/implementation_migration.py`
- Modify: `app/models/benefit.py`
- Modify: `app/models/solution_models.py`
- Modify: `app/models/__init__.py`
- Modify: `app/commands/reconcile_schema.py`
- Test: `tests/test_transformation_programme_models.py`
- Test: `tests/test_schema_reconciliation.py`
- Test: `tests/test_tenant_isolation.py`

**Interfaces:**
- Consumes: existing `TenantMixin`, `StrategicInitiative`, `WorkPackage`, `RoadmapItem`, `Benefit`, `Solution` and additive `reconcile-schema` conventions.
- Produces: `ProgrammeWorkstream`, `ProgrammeRoleAssignment`, `ProgrammeOutcomeCommitment`, `MeasureDefinition`; nullable `StrategicInitiative.record_kind`; canonical delivery FKs and `materialisation_key`; nullable `Solution.workstream_id`.

- [ ] **Step 1: Write failing model and tenant tests**

Add fixtures that create two organisations and prove the following exact invariants:

```python
def test_transformation_programme_graph_is_tenant_scoped(db_session, make_org, tenant_ctx):
    org_a, org_b = make_org("A"), make_org("B")
    with tenant_ctx(org_a):
        programme = StrategicInitiative(name="Reduce run cost", record_kind="transformation_programme")
        db_session.add(programme); db_session.flush()
        stream = ProgrammeWorkstream(
            organization_id=org_a.id, programme_id=programme.id,
            workstream_type="application_rationalisation", objective="Remove avoidable run cost",
            lifecycle_stage="objective", revision=1,
        )
        db_session.add(stream); db_session.flush()
    db_session.expunge_all()
    with tenant_ctx(org_b):
        assert db_session.scalar(db.select(ProgrammeWorkstream).where(ProgrammeWorkstream.id == stream.id)) is None

def test_nullable_metrics_do_not_become_zero():
    measure = MeasureDefinition(metric_name="Annual run cost", unit="GBP")
    assert measure.baseline_value is None
    assert measure.target_value is None
    assert measure.to_dict()["baseline_value"] is None
```

Also assert: all parent/child IDs belong to one tenant; `RoadmapItem` now inherits `TenantMixin`; a RoadmapItem programme must equal its workstream programme; WorkPackage/Benefit/Solution workstream and programme must agree; duplicate non-null materialisation keys fail; deletes are restricted; Benefit legacy FK is `SET NULL`; existing rows with null additive columns still serialize.

- [ ] **Step 2: Run the tests to prove the schema is absent**

Run: `pytest -q tests/test_transformation_programme_models.py tests/test_schema_reconciliation.py tests/test_tenant_isolation.py -k 'transformation or roadmap or benefit'`

Expected: collection/import failures for the new model classes or assertion failures for absent fields and tenant scoping.

- [ ] **Step 3: Add the programme model with exact columns and constraints**

Implement the four tenant models with nullable deployment-safe columns, explicit `ondelete="RESTRICT"`, check constraints and uniqueness. The defining skeleton is:

```python
class ProgrammeWorkstream(TenantMixin, OptimisticLockMixin, db.Model):
    __tablename__ = "programme_workstreams"
    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(db.Integer, db.ForeignKey("strategic_initiatives.id", ondelete="RESTRICT"), nullable=False, index=True)
    workstream_type = db.Column(db.String(40), nullable=False)
    objective = db.Column(db.Text, nullable=False)
    scope_expression = db.Column(db.JSON, nullable=False, default=dict)
    lifecycle_stage = db.Column(db.String(40), nullable=False, default="objective")
    lead_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    target_date = db.Column(db.Date)
    target_date_unavailable_reason = db.Column(db.Text)
    archived_at = db.Column(db.DateTime)

class ProgrammeOutcomeCommitment(TenantMixin, OptimisticLockMixin, db.Model):
    __tablename__ = "programme_outcome_commitments"
    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(db.Integer, db.ForeignKey("strategic_initiatives.id", ondelete="RESTRICT"), nullable=False)
    workstream_id = db.Column(db.Integer, db.ForeignKey("programme_workstreams.id", ondelete="RESTRICT"))
    statement = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    improvement_direction = db.Column(db.String(20), nullable=False)
    target_date = db.Column(db.Date)
    lifecycle = db.Column(db.String(30), nullable=False, default="committed")

class MeasureDefinition(TenantMixin, OptimisticLockMixin, db.Model):
    __tablename__ = "measure_definitions"
    id = db.Column(db.Integer, primary_key=True)
    outcome_commitment_id = db.Column(db.Integer, db.ForeignKey("programme_outcome_commitments.id", ondelete="RESTRICT"), nullable=False)
    metric_name = db.Column(db.String(255), nullable=False)
    unit = db.Column(db.String(64), nullable=False)
    currency = db.Column(db.String(3))
    aggregation = db.Column(db.String(30), nullable=False)
    baseline_value = db.Column(db.Numeric(24, 6))
    target_value = db.Column(db.Numeric(24, 6))
    baseline_date = db.Column(db.Date)
    target_date = db.Column(db.Date)
    cadence = db.Column(db.String(30))
    source_adapter = db.Column(db.String(80))
    source_key = db.Column(db.String(512))
    tolerance = db.Column(db.Numeric(24, 6))
    unavailable_reason = db.Column(db.Text)
```

`ProgrammeRoleAssignment` contains `programme_id`, optional `workstream_id`, `user_id`, `role`, `effective_from`, optional `effective_to`, `assigned_by_id`, and a uniqueness constraint over the active assignment identity. Validate workstream type, lifecycle, role, direction and aggregation with checks. Financial measures use a service-normalised `Numeric(18,2)` value field or reject non-ISO currency; non-financial values use `Numeric(24,6)`.

- [ ] **Step 4: Harden canonical roots and delivery links**

Add `StrategicInitiative.record_kind`, leaving old rows null. Add exact links from the spec to `WorkPackage`, `RoadmapItem`, `Benefit` and `Solution`. Make `RoadmapItem(TenantMixin, db.Model)`. Add partial unique PostgreSQL indexes:

```python
db.Index("uq_work_package_materialisation", WorkPackage.organization_id, WorkPackage.materialisation_key,
         unique=True, postgresql_where=WorkPackage.materialisation_key.isnot(None))
```

Repeat for RoadmapItem and Benefit. Add check/constraint-trigger validation in the schema installer for same-tenant and same-programme parent membership because ordinary foreign keys cannot express it. Rename the Python attribute `Benefit.initiative_id` to `legacy_enterprise_initiative_id` while retaining the physical column name with `db.Column("initiative_id", db.Integer, db.ForeignKey("enterprise_initiatives.id", ondelete="SET NULL"), nullable=True, index=True)`; recreate its database FK as `ON DELETE SET NULL` through an explicit privileged migration helper invoked by reconciliation. Reads prefer canonical links; writes never populate the legacy field.

- [ ] **Step 5: Register models and reconcile both fresh and existing schemas**

Import the new models in `app/models/__init__.py`. Extend `reconcile-schema` so new tables are created, additive columns are added safely, the Benefit FK is inspected/replaced idempotently, membership constraints are installed, and `--dry-run` reports without writes. Test fresh `create_all`, an existing pre-feature schema, two reconciliation runs, and database FK/check definitions through `pg_constraint`.

- [ ] **Step 6: Run focused gates and commit**

Run:

```bash
pytest -q tests/test_transformation_programme_models.py tests/test_schema_reconciliation.py tests/test_tenant_isolation.py
python scripts/verify.py --gate schema-drift
python scripts/verify.py --gate raw-sql-tenancy
ruff check app/models/transformation_programme.py app/models/strategic.py app/models/implementation_migration.py app/models/benefit.py
```

Expected: all tests and gates pass; no skip is counted as success.

Commit only the listed files with subject `feat: add transformation programme foundations`.

---

### Task 2: UnifiedCapability hybrid-tenancy maintenance cutover

**Files:**
- Modify: `app/models/unified_capability.py`
- Create: `app/commands/cutover_capability_tenancy.py`
- Modify: `app/_bootstrap/cli.py`
- Create: `scripts/migrations/capability_tenancy_cutover.sql`
- Create: `scripts/migrations/capability_tenancy_reverse.sql`
- Test: `tests/test_capability_tenancy_cutover.py`
- Modify: `tests/test_tenant_isolation.py`

**Interfaces:**
- Consumes: existing `UnifiedCapability`, application/capability mappings and organisation provenance.
- Produces: `UnifiedCapability.scope`, nullable `organization_id`, `reference_capability_id`, provenance fields; `flask --app manage cutover-capability-tenancy --dry-run|--apply --report <path>`.

- [ ] **Step 1: Write failing classification, uniqueness and isolation tests**

Create fixtures for reference rows, provably tenant-authored rows, ambiguous rows, duplicate tenant codes, duplicate reference codes and relationships. Assert dry-run changes nothing, ambiguous active links block apply, tenant rows are invisible to another tenant, reference rows remain readable but tenant read-only, and partial indexes enforce:

```sql
UNIQUE (code) WHERE organization_id IS NULL;
UNIQUE (organization_id, code) WHERE organization_id IS NOT NULL;
UNIQUE (archimate_id) WHERE organization_id IS NULL AND archimate_id IS NOT NULL;
UNIQUE (organization_id, archimate_id) WHERE organization_id IS NOT NULL AND archimate_id IS NOT NULL;
```

- [ ] **Step 2: Run tests to prove old global ownership is unsafe**

Run: `pytest -q tests/test_capability_tenancy_cutover.py tests/test_tenant_isolation.py -k capability`

Expected: failures because global uniqueness and unclassified ownership remain.

- [ ] **Step 3: Add compatible read shape and deterministic classifier**

Add nullable `organization_id`, `scope`, `reference_capability_id`, `source_table`, `source_id`, `source_org_id`, `source_checksum`, `retired_into_id`. Keep code compatible with null `scope` until the cutover finishes. Define:

```python
@dataclass(frozen=True)
class CapabilityClassification:
    capability_id: int
    scope: Literal["reference", "tenant", "ambiguous"]
    organization_id: int | None
    evidence: Sequence[str]

def classify_capability(connection, capability_id: int) -> CapabilityClassification:
    row = connection.execute(
        db.text("SELECT id FROM unified_capabilities WHERE id = :id FOR SHARE"),
        {"id": capability_id},
    ).mappings().one()
    owners = tuple(sorted(load_relationship_organization_ids(connection, row["id"])))
    provenance = load_capability_provenance(connection, row["id"])
    if provenance.is_seeded_reference and not owners:
        return CapabilityClassification(row["id"], "reference", None, provenance.citations)
    if len(owners) == 1 and provenance.supports_tenant(owners[0]):
        return CapabilityClassification(row["id"], "tenant", owners[0], provenance.citations)
    return CapabilityClassification(row["id"], "ambiguous", None, provenance.citations)
```

Implement `load_relationship_organization_ids()` as the union of explicit organisation IDs reached through current application, benefit, work-package and capability-mapping FKs, and `load_capability_provenance()` as a frozen row containing seeded-import checksum/source citations and `supports_tenant(org_id)`. Classification uses those audited relationships only; it never guesses from name/code. Duplicate resolution emits a report mapping, locks source/target plus every discovered FK row, records before counts, repoints only rows whose organisation matches the target, re-counts every FK table, then sets `retired_into_id` on the duplicate. A count mismatch rolls back.

- [ ] **Step 4: Implement the explicit maintenance command and reversible SQL**

The command requires `--dry-run` or `--apply`, obtains one advisory lock, emits before/after counts and checksums, refuses apply without a backup path recorded in `--backup-manifest`, and stops before constraint swap if ambiguous active links remain. The SQL drops named global unique constraints only after classification, creates partial indexes (concurrently when outside the transaction), installs write checks, and verifies all FKs. Reverse SQL restores the compatible old uniqueness only when there are no tenant duplicates; otherwise it exits non-zero without mutation.

- [ ] **Step 5: Prove the cutover against a cloned schema**

Run:

```bash
pytest -q tests/test_capability_tenancy_cutover.py tests/test_tenant_isolation.py -k capability
flask --app manage cutover-capability-tenancy --dry-run --report capability-cutover-dry-run.json
python scripts/verify.py --gate schema-drift
```

Expected: tests pass; dry-run report has `writes: 0`, classified/reference/tenant/ambiguous counts and stable checksums; schema gate passes after test teardown.

- [ ] **Step 6: Commit**

Commit only the listed files with subject `feat: enforce capability ownership boundaries`.

---

### Task 3: Fenced commands, immutable operation results and database guards

**Files:**
- Create: `app/models/transformation_execution.py`
- Create: `app/modules/transformation_room/__init__.py`
- Create: `app/modules/transformation_room/domain.py`
- Create: `app/modules/transformation_room/command_service.py`
- Create: `app/models/transformation_db_guards.py`
- Modify: `app/models/__init__.py`
- Modify: `app/commands/reconcile_schema.py`
- Test: `tests/test_transformation_command_service.py`
- Test: `tests/test_transformation_db_guards.py`

**Interfaces:**
- Consumes: Task 1 tenant schema and PostgreSQL reconciliation hook.
- Produces: `ActorContext`, `CommandClaim`, `CommandResult`, `CommandConflict`, `StaleClaim`, `OperationAuthorizer = Callable[[Session, ActorContext, str, str], None]`, `OperationNaturalKeyResolver = Callable[[Session, ActorContext, str, CommandClaim], DomainMutationResult | None]`, the three public `CommandService` entries below, `OperationResult`, and idempotent trigger installation.

- [ ] **Step 1: Write the seven crash-point and stale-worker tests first**

Use two independent SQLAlchemy sessions/threads and explicit barriers. Cover: claim then crash before work; domain insert then fail before result; result then fail before commit; commit then simulated lost HTTP response; expired lease with result; expired lease with natural-key row and damaged receipt; `retryable_failure` recovery. Add the required pause/reclaim/resume test:

```python
worker_a = claim(key="same", digest=digest)  # generation 1
pause_before_write.wait()
expire(worker_a)
worker_b = reconcile_and_claim(key="same", digest=digest)  # generation 2
assert worker_b.execute(create_domain_row).created
resume_worker_a.set()
assert raises(StaleClaim, worker_a.execute, create_domain_row)
assert count_domain_rows() == 1
assert count_operation_results() == 1
```

Also test same-key/different-digest `409`, active lease retry metadata, immutable digest/identity/natural-key/result fields, outbox event IDs and exact canonical replay response. For each of `execute`, `execute_claim` and `claim_or_reconcile`, pass both `None` and a non-callable authorizer and assert `TypeError("authorizer must be callable")` occurs before receipt, resolver or handler work.

- [ ] **Step 2: Run to establish RED**

Run: `pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py`

Expected: imports fail for command models/services.

- [ ] **Step 3: Implement exact command types and protocol**

Define:

```python
@dataclass(frozen=True)
class ActorContext:
    user_id: int
    organization_id: int
    roles: frozenset[str]
    request_id: str

@dataclass(frozen=True)
class CommandClaim:
    receipt_id: int
    generation: int
    claim_token: str
    request_digest: str
    natural_key: str

OperationAuthorizer: TypeAlias = Callable[
    [Session, ActorContext, str, str], None
]
OperationNaturalKeyResolver: TypeAlias = Callable[
    [Session, ActorContext, str, CommandClaim], DomainMutationResult | None
]

class CommandService:
    @classmethod
    def execute(cls, *, actor: ActorContext, operation: str, idempotency_key: str,
                payload: Mapping[str, Any], natural_key: str,
                authorizer: OperationAuthorizer,
                handler: Callable[[Session, CommandClaim], DomainMutationResult],
                natural_key_resolver: OperationNaturalKeyResolver | None = None,
                ) -> CommandResult:
        authorizer = cls._require_authorizer(authorizer)
        digest = canonical_request_digest(payload)
        claim_or_result = cls.claim_or_reconcile(
            actor=actor, operation=operation, idempotency_key=idempotency_key,
            request_digest=digest, natural_key=natural_key, authorizer=authorizer,
        )
        if isinstance(claim_or_result, CommandResult):
            return claim_or_result
        return cls._execute_claim(
            actor=actor, operation=operation, claim=claim_or_result,
            authorizer=None,  # private only: execute already authorized above
            handler=handler, natural_key_resolver=natural_key_resolver,
        )

    @classmethod
    def execute_claim(cls, *, actor: ActorContext, operation: str,
                      claim: CommandClaim, authorizer: OperationAuthorizer,
                      handler: Callable[[Session, CommandClaim], DomainMutationResult],
                      natural_key_resolver: OperationNaturalKeyResolver | None = None,
                      ) -> CommandResult: ...

    @classmethod
    def claim_or_reconcile(cls, *, actor: ActorContext, operation: str,
                           idempotency_key: str, request_digest: str,
                           natural_key: str,
                           authorizer: OperationAuthorizer,
                           ) -> CommandClaim | CommandResult: ...
```

`_require_authorizer()` is the first executable statement in all three public entries and raises `TypeError("authorizer must be callable")`; only the private `_execute_claim()` accepts the `None` sentinel after `execute()` has already authorized. Define `canonical_request_digest()` as SHA-256 over sorted canonical JSON; `claim_or_reconcile()` as a constraint-backed PostgreSQL upsert on `(organization_id, actor_id, operation, idempotency_key)` in a short independent session; and `execute_claim()` as one independent transaction containing resolver/handler mutation, immutable result/outbox insertion and final fenced receipt update. `claim_or_reconcile()` invokes the authorizer before receipt creation or `OperationResult` lookup; public `execute_claim()` invokes it before resolver/handler work. On conflict the service returns an existing authorized success, rejects a changed digest, returns retry guidance for an active lease, or reconciles `OperationResult` and an operation-specific natural-key resolver before retry. Validation/auth failures call `mark_non_retryable()` only after a claim exists; known pre-commit transient failures call `mark_retryable()`; uncertain commit outcomes leave the receipt reconcilable and never assert failure or success.

Every downstream service supplies an operation-specific authorizer factory. The returned callable must tenant-load every captured ID using its supplied `Session`, verify the exact `operation` and canonical `natural_key`, and recheck current server-side role/assignment authority. It raises `NotFound` or `NotAuthorised` on failure and returns `None` only after success. It must not check mutable mutation preconditions such as draft/open/not-yet-materialised state, because those may legitimately differ during replay; the locked handler checks those after reconciliation. A shared permissive authorizer, `lambda: None`, truthy flag or client-provided authorization result is forbidden.

- [ ] **Step 4: Install database immutability and fencing triggers**

Create idempotent `ensure_transformation_db_guards(connection)` under a transaction-scoped advisory lock. Revoke direct mutation where applicable and install fixed-search-path functions. Triggers reject update/delete of `OperationResult` and its outbox payload, protect immutable receipt identity/digest/result, and permit heartbeat/reclaim/finalise only with valid generation/token transitions. Test direct psycopg connections using comment-prefixed, CTE and schema-qualified statements.

- [ ] **Step 5: Run focused tests and gates**

Run:

```bash
pytest -q tests/test_transformation_command_service.py tests/test_transformation_db_guards.py
python scripts/verify.py --gate schema-drift
python scripts/verify.py --gate raw-sql-tenancy
ruff check app/modules/transformation_room/domain.py app/modules/transformation_room/command_service.py app/models/transformation_execution.py app/models/transformation_db_guards.py
```

Expected: every crash/race/direct-SQL case passes and exactly one result/outbox/domain row exists.

- [ ] **Step 6: Commit**

Commit with subject `feat: add fenced transformation commands`.

---

### Task 4: Business-first programme intake, roles, outcomes and lifecycle gates

**Files:**
- Create: `app/modules/transformation_room/programme_service.py`
- Create: `app/modules/transformation_room/gate_service.py`
- Modify: `app/modules/solutions_strategic/v2/routes/solution_wizard_routes.py`
- Modify: `app/modules/solutions_strategic/v2/services/programme_setup_service.py`
- Test: `tests/test_transformation_programme_service.py`
- Test: `tests/test_transformation_gate_service.py`
- Modify: `tests/test_programme_setup_service.py`

**Interfaces:**
- Consumes: Tasks 1 and 3 models, `ActorContext`, `CommandService.execute`.
- Produces: `TransformationProgrammeService.create_programme -> CommandResult`, `assign_role`, `update_objective`, `archive`; `TransformationGateService.evaluate(workstream_id, target_stage, actor) -> GateResult` and `transition -> CommandResult`.

- [ ] **Step 1: Write failing intake, policy and atomicity tests**

Test a non-technology intake with objective, outcome, measure, owner and first rationalisation workstream. Assert one programme graph, `record_kind="transformation_programme"`, no Solution, exact canonical replay, role authorization, cross-tenant `NotFound`, forged identity ignored, and rollback when each subordinate insert is forced to fail. Test nullable target date requires a persisted unavailable reason.

Define test payload:

```python
payload = {
    "name": "Simplify the application estate",
    "objective": "Reduce duplicated capability cost without service loss",
    "owner_id": owner.id,
    "target_date": "2027-06-30",
    "workstream_type": "application_rationalisation",
    "scope_expression": {"business_units": ["Retail"]},
    "outcome": {"statement": "Reduce annual run cost", "owner_id": owner.id,
                "direction": "decrease", "measure": {"metric_name": "Annual run cost",
                "unit": "GBP", "currency": "GBP", "aggregation": "sum",
                "baseline_value": None, "unavailable_reason": "Finance baseline requested",
                "target_value": "900000.00"}},
}
```

- [ ] **Step 2: Run RED tests**

Run: `pytest -q tests/test_transformation_programme_service.py tests/test_transformation_gate_service.py tests/test_programme_setup_service.py`

Expected: new service imports fail and the legacy wizard still creates a Solution.

- [ ] **Step 3: Implement the programme service**

Use exact public signatures:

```python
class TransformationProgrammeService:
    @classmethod
    def create_programme(cls, *, actor: ActorContext, command_key: str,
                         request: ProgrammeIntake) -> CommandResult:
        validated = cls.validate_intake(actor=actor, request=request)
        natural_key = f"programme-intake:{command_key}"
        return CommandService.execute(
            actor=actor, operation="programme.create", idempotency_key=command_key,
            payload=asdict(validated), natural_key=natural_key,
            authorizer=cls.authorise_create_programme(validated, natural_key),
            handler=lambda session, claim: cls._insert_intake_graph(
                session=session, actor=actor, request=validated, claim=claim,
            ),
        )
    @classmethod
    def assign_role(cls, *, actor: ActorContext, programme_id: int,
                    workstream_id: int | None, user_id: int, role: str,
                    effective_from: date, effective_to: date | None,
                    expected_revision: int, command_key: str) -> CommandResult:
        programme, workstream, user = cls.load_assignment_scope(
            actor=actor, programme_id=programme_id,
            workstream_id=workstream_id, user_id=user_id,
        )
        cls.authorise_role_assignment(actor, programme, workstream, role)
        payload = {"programme_id": programme.id, "workstream_id": workstream_id,
                   "user_id": user.id, "role": role,
                   "effective_from": effective_from.isoformat(),
                   "effective_to": effective_to.isoformat() if effective_to else None,
                   "expected_revision": expected_revision}
        return CommandService.execute(
            actor=actor, operation="programme.assign_role", idempotency_key=command_key,
            payload=payload, natural_key=canonical_role_assignment_key(payload),
            authorizer=cls.authorise_role_assignment_replay(payload),
            handler=lambda session, claim: cls._insert_role_assignment(
                session, actor, programme, workstream, user, payload, claim),
        )
    @classmethod
    def get_programme(cls, *, actor: ActorContext, programme_id: int) -> ProgrammeView:
        programme = cls.load_programme_for_tenant(actor, programme_id)
        cls.authorise_read(actor, programme)
        workstreams = cls.load_workstreams_for_tenant(actor, programme.id)
        next_action = TransformationGateService.next_action(actor=actor, workstreams=workstreams)
        return ProgrammeView(programme.id, tuple(row.id for row in workstreams),
                             programme.status, programme.owner_id, next_action)
```

`validate_intake()` accepts the eight workstream types, canonical roles, valid ISO currency and same-tenant users. `_insert_intake_graph()` creates `StrategicInitiative(record_kind="transformation_programme")`, the owner assignment, first workstream, outcome and measure; flushes once; and returns `DomainMutationResult` containing all four canonical IDs and one `programme.created` outbox event. It never commits. The named load helpers always include `organization_id == actor.organization_id`; the authorization helpers apply the role table from the spec. `canonical_role_assignment_key()` hashes programme/workstream/user/role/effective-from. `update_objective()` delegates through `CommandService.execute`, locks the workstream, checks revision/role, changes only objective/scope/revision and emits `workstream.objective_updated`. `archive()` similarly locks the programme, requires the archive role and retention invariants, sets `archived_at/status`, and emits `programme.archived`. Keep `ProgrammeSetupService` as a compatibility adapter that delegates business-first creation and does not create a Solution; retain its old technology-specific methods only for explicit legacy solution journeys.

`authorise_create_programme(validated, natural_key)` returns an `OperationAuthorizer` that requires exact operation `programme.create`, exact captured natural key, the server-side programme-create role and a same-tenant owner loaded through its supplied session. `authorise_role_assignment_replay(payload)` requires exact operation/key, tenant-loads programme, optional workstream and assigned user from payload, then applies current role-assignment authority. `update_objective()` and `archive()` must likewise pass `authorise_objective_update(workstream_id, expected_revision)` and `authorise_programme_archive(programme_id, expected_revision)` factories; neither may reuse pre-command authorization as a boolean or skip replay authorization.

- [ ] **Step 4: Implement pure versioned gate evaluation and locked transition**

Use the shared `GateResult`, define `POLICY_VERSION = "transformation-r1.1"`, stable blocker codes and these exact methods:

```python
class TransformationGateService:
    @classmethod
    def evaluate(cls, *, actor: ActorContext, workstream_id: int,
                 target_stage: str) -> GateResult:
        snapshot = cls.load_policy_snapshot(actor=actor, workstream_id=workstream_id)
        transition = cls.require_valid_transition(snapshot.workstream.lifecycle_stage, target_stage)
        blockers, warnings, evidence_ids = cls.evaluate_requirements(snapshot, transition)
        return GateResult(not blockers, transition.source, transition.target,
                          cls.POLICY_VERSION, tuple(blockers), tuple(warnings),
                          tuple(sorted(evidence_ids)))

    @classmethod
    def transition(cls, *, actor: ActorContext, workstream_id: int,
                   target_stage: str, expected_revision: int,
                   command_key: str) -> CommandResult:
        request = {"workstream_id": workstream_id, "target_stage": target_stage,
                   "expected_revision": expected_revision}
        return CommandService.execute(
            actor=actor, operation="workstream.transition", idempotency_key=command_key,
            payload=request,
            natural_key=f"transition:{workstream_id}:{expected_revision}:{target_stage}",
            authorizer=cls.authorise_transition(
                workstream_id, target_stage, expected_revision),
            handler=lambda session, claim: cls._locked_transition(
                session, actor, request, claim),
        )
```

`load_policy_snapshot()` explicitly tenant-loads the workstream plus accepted candidates, active evidence heads, requests/waivers, immutable options/briefs, ARB cycle/conditions, work/roadmap/benefits and measurements. `evaluate_requirements()` implements each persisted requirement in the approved gate table and never mutates. `_locked_transition()` reloads the workstream `FOR UPDATE`, checks `expected_revision`, reruns evaluation inside that transaction, raises `BlockedByEvidence` with stable blockers when denied, updates stage/revision and inserts its audit event, then returns `DomainMutationResult`. `next_action()` evaluates the single valid forward transition for each non-terminal workstream in stage order and returns the first blocker/action; it returns null only when every workstream is terminal. No request may set lifecycle directly.

`authorise_transition(workstream_id, target_stage, expected_revision)` returns an `OperationAuthorizer` that requires exact operation/key, tenant-loads the workstream and programme, and rechecks current transition authority. It deliberately does not require the old revision or gate readiness; `_locked_transition()` owns those mutable preconditions after replay reconciliation.

- [ ] **Step 5: Convert the create route to the canonical service**

`POST /solutions/create-programme` reads `Idempotency-Key`, builds `ActorContext` from current user/current tenant, rejects legacy client identity/status fields, calls `create_programme`, and returns `programme_id`, `workstream_id`, `outcome_commitment_id`, `operation_result_id` and `/solutions/programmes/<id>/workstreams/<wid>/objective`. It must never return `solution_id` for the business-first flow.

- [ ] **Step 6: Run and commit**

Run focused tests plus `python scripts/verify.py --gate boot-health`; expect green and route registration intact. Commit with subject `feat: create business-first transformation programmes`.

---

### Task 5: Candidate discovery and acceptance with inspectable signals

**Files:**
- Create: `app/models/transformation_evidence.py`
- Create: `app/modules/transformation_room/discovery_service.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_rationalisation_discovery_service.py`
- Modify: `tests/test_tenant_isolation.py`

**Interfaces:**
- Consumes: programme/workstream graph, canonical `ApplicationComponent`, capability mappings and application dependencies.
- Produces: `TransformationCandidate`, immutable `CandidateSignal`, `RationalisationDiscoveryService.discover` and `.accept_candidate`.

- [ ] **Step 1: Write failing deterministic discovery tests**

Seed applications with explicit capability overlap, cost, EOL, risk, health, dependency and missing-owner facts. Assert each signal includes `rule_code`, `rule_version`, source record IDs, evaluated time, observed values and confidence; missing inputs yield a named unknown rather than zero. Assert discovery itself writes nothing, acceptance creates only a candidate/signal citations, subject uniqueness prevents duplicates, replay is idempotent and no copied Application row is created.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_rationalisation_discovery_service.py tests/test_tenant_isolation.py -k candidate`

Expected: model/service imports fail.

- [ ] **Step 3: Implement candidate and immutable signal persistence**

`TransformationCandidate` has tenant, workstream, `subject_type`, `subject_id`, inclusion status/reason, accepted by/time and revision, with unique `(organization_id, workstream_id, subject_type, subject_id)`. `CandidateSignal` has rule/version, canonical JSON payload, source IDs, evaluation timestamp and content hash; it rejects mutation through Task 3's guard installer.

- [ ] **Step 4: Implement rules and candidate acceptance**

Define:

```python
class RationalisationDiscoveryService:
    RULESET_VERSION = "app-rationalisation-r1.1"
    @classmethod
    def discover(cls, *, actor: ActorContext, workstream_id: int,
                 filters: DiscoveryFilters) -> Sequence[DiscoveryCandidate]:
        workstream = cls.load_rationalisation_workstream(actor, workstream_id)
        applications = cls.load_scoped_applications(actor, workstream, filters)
        candidates = []
        for application in applications:
            signals = tuple(rule.evaluate(actor, application)
                            for rule in cls.signal_rules())
            candidates.append(cls.to_discovery_candidate(application, signals))
        return tuple(sorted(candidates, key=lambda item: item.application_id))
    @classmethod
    def accept_candidate(cls, *, actor: ActorContext, workstream_id: int,
                         application_id: int, signal_digests: Sequence[str],
                         inclusion_reason: str, command_key: str) -> CommandResult:
        request = {"workstream_id": workstream_id, "application_id": application_id,
                   "signal_digests": tuple(sorted(signal_digests)),
                   "inclusion_reason": inclusion_reason.strip()}
        return CommandService.execute(
            actor=actor, operation="candidate.accept", idempotency_key=command_key,
            payload=request, natural_key=f"candidate:{workstream_id}:application:{application_id}",
            authorizer=cls.authorise_candidate_acceptance(
                workstream_id, application_id),
            handler=lambda session, claim: cls._accept_recomputed_candidate(
                session, actor, request, claim),
        )
```

`signal_rules()` returns seven named rule objects for capability overlap, cost, EOL, risk, technical health, dependency concentration and owner/data gaps. Each `evaluate()` uses explicit tenant-constrained queries, returns source IDs/rule version/evaluated time, and emits a named unknown with null confidence when inputs are absent. `_accept_recomputed_candidate()` locks the workstream/application, checks authorization, recomputes all selected signals inside the command transaction, compares canonical digests, inserts the unique candidate and immutable signal rows, and returns their IDs in `DomainMutationResult`. If application owner is absent it also inserts the required `application_owner` EvidenceRequest assigned first to the configured portfolio steward, otherwise the workstream architect; it does not advance the gate.

`authorise_candidate_acceptance(workstream_id, application_id)` returns an `OperationAuthorizer` that requires exact operation/key, tenant-loads both records with the supplied session, verifies rationalisation-workstream membership and rechecks the current programme/workstream role. Signal freshness and absence of an existing candidate remain locked handler preconditions, not replay authorization.

- [ ] **Step 5: Verify and commit**

Run focused tests, raw-SQL tenancy, lint and schema-drift. Expected green with no duplicate candidates. Commit with subject `feat: add rationalisation candidate discovery`.

---

### Task 6: Versioned evidence, requests, attestations and guarded claim heads

**Files:**
- Modify: `app/models/transformation_evidence.py`
- Create: `app/modules/transformation_room/evidence_service.py`
- Modify: `app/models/transformation_db_guards.py`
- Modify: `app/commands/reconcile_schema.py`
- Test: `tests/test_transformation_evidence_service.py`
- Test: `tests/test_evidence_head_concurrency.py`
- Modify: `tests/test_transformation_db_guards.py`

**Interfaces:**
- Consumes: Task 3 fenced claims and Task 5 candidates.
- Produces: `EvidenceRecord`, `EvidenceClaimHead`, `EvidenceHeadEvent`, `EvidenceRequest`, `EvidenceSourceAdapter`; `record_observation`, `submit_attestation`, `accept_request`, `resolve_conflict`, `active_evidence`.

- [ ] **Step 1: Write failing evidence-chain and request tests**

Cover versioned/unversioned adapters, source normalization, agreement, disagreement/conflict, governed canonical correction, request `open -> submitted -> accepted`, decline/expiry remaining incomplete, authorised expiring unavailable waiver, stale revision `409`, and cross-tenant/other-assignee denial. Two concurrent corrections from revision N must produce one successor/head move/event and no orphan row for the loser; concurrent roots produce one head.

Use separate direct PostgreSQL connections to attempt arbitrary-current, historical, cross-tenant, wrong-subject pointers, revision jump, wrong predecessor and head move without matching event/command. Every invalid attempt must fail; one valid function call advances exactly once.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_evidence_service.py tests/test_evidence_head_concurrency.py tests/test_transformation_db_guards.py -k evidence`

Expected: absent models/functions and concurrency assertions fail.

- [ ] **Step 3: Add complete evidence schema**

Use JSON typed values with explicit `value_type`, `unit`, `currency`, classification, canonical source identity/version/checksum, collector/AI metadata, observed/valid/freshness times, confidence method, `supersedes_id` and immutable creation fields. `EvidenceClaimHead` unique key is `(organization_id, subject_type, subject_id, claim_key, source_identity)`. `EvidenceHeadEvent` records old/new IDs, actor, command receipt/generation, reason, revision and `created_txid`. Requests have exact statuses and accepted evidence pointer; waiver fields include authority, reason, expiry and interim accountability.

- [ ] **Step 4: Implement adapters and service methods**

```python
class EvidenceSourceAdapter(Protocol):
    resolve: Callable[[str, ActorContext], SourceResolution]
    read_version: Callable[[SourceResolution], SourceVersion]
    canonical_uri: Callable[[SourceResolution], str]
    freshness: Callable[[SourceVersion], FreshnessResult]
    authorise_correction: Callable[[ActorContext, SourceResolution], bool]

class ApplicationInventoryEvidenceAdapter:
    def resolve(self, source_key: str, actor: ActorContext) -> SourceResolution:
        application_id = parse_positive_int(source_key)
        application = load_application_for_tenant(actor, application_id)
        return SourceResolution(f"application:{application.id}", "application", application.id)

    def read_version(self, resolution: SourceResolution) -> SourceVersion:
        application = lock_application(resolution.canonical_subject_id)
        value = TypedEvidenceValue("json", canonical_inventory_fields(application), None, None)
        checksum = sha256_canonical(value)
        return SourceVersion(str(application.updated_at.isoformat()), checksum,
                             application.updated_at, value)

    def canonical_uri(self, resolution: SourceResolution) -> str:
        return f"archie://application/{resolution.canonical_subject_id}"

    def freshness(self, version: SourceVersion) -> FreshnessResult:
        expiry = version.observed_at + INVENTORY_FRESHNESS
        return FreshnessResult("fresh" if utcnow() <= expiry else "stale",
                               expiry, "inventory-r1.1")

    def authorise_correction(self, actor: ActorContext,
                             resolution: SourceResolution) -> bool:
        return bool(actor.roles & frozenset({"application_owner", "application_architect",
                                             "enterprise_architect", "chief_architect"}))

class TransformationEvidenceService:
    @classmethod
    def submit_attestation(cls, *, actor: ActorContext, request_id: int,
                           value: TypedEvidenceValue, expected_head_revision: int,
                           command_key: str) -> CommandResult:
        request = cls.load_assigned_open_request(actor, request_id)
        source_identity = f"attestation:user:{actor.user_id}"
        payload = cls.attestation_payload(request, value, expected_head_revision,
                                          source_identity)
        return CommandService.execute(
            actor=actor, operation="evidence.attest", idempotency_key=command_key,
            payload=payload,
            natural_key=cls.evidence_natural_key(payload),
            authorizer=cls.authorise_attestation(request.id, payload),
            handler=lambda session, claim: cls._append_and_advance(
                session, actor, request, payload, claim),
        )
```

Set `INVENTORY_FRESHNESS = timedelta(days=90)`. Implement `parse_positive_int`, `load_application_for_tenant`, `lock_application`, `canonical_inventory_fields` and `sha256_canonical` as strict module helpers; the latter uses the same canonical JSON rules as Task 3. `_append_and_advance()` locks/upserts the claim head, verifies expected revision, inserts the immutable evidence row and `EvidenceHeadEvent`, calls the guarded database function, and returns `DomainMutationResult`; any guard failure rolls back the inserted row. `record_observation()` resolves the registered adapter, reads/checksums the source under lock and calls `_append_and_advance()`. `accept_request()` locks request/evidence, verifies assignment or architect override, same claim/subject and current head, then marks accepted and links the evidence in one command. `resolve_conflict()` requires decision authority, verifies the selected evidence is one cited leaf, records the governing-source rationale as a new immutable resolution record and advances its own resolution head. `active_evidence()` joins only through `EvidenceClaimHead.current_record_id` and verifies tenant/subject membership. Canonicalize source identities with NFC normalization, lower-cased adapter/URI scheme/host and adapter-specific opaque-key preservation. Attestations remain separate sources. A disagreement appends a conflict row citing both heads; only governed source correction or decision-authority source selection resolves the gate.

`authorise_attestation(request_id, payload)` returns an `OperationAuthorizer` that requires exact `evidence.attest` operation/key, tenant-loads the request without requiring mutable `open` state, and rechecks assignee/architect authority. The handler alone locks and requires `open`. `record_observation()`, `accept_request()` and `resolve_conflict()` each pass their own source/request/conflict-specific authorizer factory that tenant-loads captured IDs and rechecks adapter correction, assignee/override or decision authority before any result replay.

- [ ] **Step 5: Install exact guarded head function and append-only triggers**

The `SECURITY DEFINER` function fixes `search_path`, locks head and receipt, checks tenant/subject/claim/source/predecessor, exact `revision + 1`, generation/token/unexpired lease and same-transaction event via `txid_current()`, then performs the CAS update. Revoke direct app-role head update. Add immutable triggers for records/events and prevent head deletion with history. Installation is advisory-locked and idempotent for fresh/existing databases.

- [ ] **Step 6: Verify and commit**

Run all three test files, schema-drift, raw-SQL tenancy and lint. Expected every race/direct-SQL case green. Commit with subject `feat: govern transformation evidence chains`.

---

### Task 7: Immutable options and decision briefs

**Files:**
- Create: `app/models/transformation_decision.py`
- Create: `app/modules/transformation_room/decision_service.py`
- Modify: `app/models/transformation_db_guards.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_transformation_option_service.py`
- Test: `tests/test_decision_brief_service.py`
- Modify: `tests/test_transformation_db_guards.py`

**Interfaces:**
- Consumes: active evidence heads, candidates, outcomes/measures and Task 3 commands.
- Produces: `TransformationOption`, `TransformationOptionVersion`, `DecisionBrief`, `DecisionBriefVersion`, citation tables, `DecisionEvent`; `TransformationOptionService.freeze_version`, `compare`; `DecisionBriefService.evaluate`, `freeze`, `verify_hash`.

- [ ] **Step 1: Write failing option/brief tests**

Assert at least two genuinely distinct option versions unless a named policy/legal exception is persisted; Decimal ranges/currency, assumptions, dependencies, impacts, reversibility and technology flag are mandatory. Assert comparisons derive from stored versions and ignore/reject client totals. Freeze must pin exact option/evidence/outcome/measure IDs, unknowns/conflicts/human assertions/policy version and calculate a deterministic canonical hash. Mutation/direct SQL fails and altered loaded payload fails hash verification. A stale/superseded citation without acknowledgement blocks.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_option_service.py tests/test_decision_brief_service.py`

Expected: imports fail.

- [ ] **Step 3: Add mutable logical roots and immutable version schema**

Option versions carry `option_id`, monotonic version, canonical content JSON, cost/benefit/risk min/max, currency, technology flag, captured by/time and hash, unique `(option_id, version)`. Brief versions carry `brief_id`, version, frozen payload, recommendation option-version ID, policy version, creator/time/hash and immutable many-to-many citation rows with exact evidence and option versions. `DecisionEvent` belongs only to brief/ARB workflow history.

- [ ] **Step 4: Implement server-derived comparison and freeze**

```python
class TransformationOptionService:
    @classmethod
    def freeze_version(cls, *, actor: ActorContext, option_id: int,
                       expected_revision: int, command_key: str) -> CommandResult:
        option = cls.load_option_for_tenant(actor, option_id)
        cls.authorise_draft(actor, option)
        payload = cls.canonical_option_payload(option, expected_revision)
        return CommandService.execute(
            actor=actor, operation="option.freeze", idempotency_key=command_key,
            payload=payload, natural_key=f"option:{option.id}:version:{expected_revision}",
            authorizer=cls.authorise_option_freeze(option.id, expected_revision),
            handler=lambda session, claim: cls._lock_validate_and_insert_version(
                session, actor, option.id, payload, claim),
        )
    @classmethod
    def compare(cls, *, actor: ActorContext,
                option_version_ids: Sequence[int]) -> OptionComparison:
        versions = cls.load_versions_for_tenant(actor, option_version_ids)
        cls.require_same_decision_scope(versions)
        currency = cls.single_currency_or_none(versions)
        return OptionComparison(
            tuple(row.id for row in versions), currency,
            cls.aggregate_range(versions, "cost", currency),
            cls.aggregate_range(versions, "benefit", currency),
            tuple(cls.comparison_conflicts(versions, currency)),
        )

class DecisionBriefService:
    @classmethod
    def evaluate(cls, *, actor: ActorContext, brief_id: int) -> BriefReadiness:
        brief = cls.load_brief_for_tenant(actor, brief_id)
        option_ids = cls.current_option_version_ids(brief)
        evidence_ids = cls.current_evidence_ids(brief)
        gate = TransformationGateService.evaluate(
            actor=actor, workstream_id=brief.workstream_id, target_stage="decision_ready")
        return BriefReadiness(gate.allowed, gate, option_ids, evidence_ids)
    @classmethod
    def freeze(cls, *, actor: ActorContext, brief_id: int,
               option_version_ids: Sequence[int], evidence_ids: Sequence[int],
               assertions: HumanAssertions, expected_revision: int,
               command_key: str) -> CommandResult:
        request = cls.build_freeze_request(
            actor, brief_id, option_version_ids, evidence_ids,
            assertions, expected_revision)
        return CommandService.execute(
            actor=actor, operation="brief.freeze", idempotency_key=command_key,
            payload=request, natural_key=f"brief:{brief_id}:version:{expected_revision}",
            authorizer=cls.authorise_brief_freeze(brief_id, expected_revision),
            handler=lambda session, claim: cls._freeze_locked_snapshot(
                session, actor, request, claim),
        )
    @classmethod
    def verify_hash(cls, version: DecisionBriefVersion) -> bool:
        payload = cls.reconstruct_canonical_payload(version)
        return hmac.compare_digest(version.content_hash, sha256_canonical(payload))
```

`_lock_validate_and_insert_version()` checks option revision, required ranges/currency/assumptions/dependencies/impacts/reversibility/technology flag, inserts the next immutable version plus hash and returns `DomainMutationResult`. `load_versions_for_tenant()` requires exact input cardinality and same tenant; range aggregation returns null unless currency and operands are comparable. `build_freeze_request()` rejects duplicate IDs and client totals. `_freeze_locked_snapshot()` locks the brief, option versions, evidence heads, outcome and measure rows; reruns the gate; requires two distinct options or the persisted exception; verifies human AI review and acknowledgements; inserts version/citations/event with canonical hash; and returns their IDs. Canonical serialization uses sorted keys, Decimal strings, UTC timestamps and explicit nulls. Re-read/lock cited rows immediately before insert and fail closed on membership, freshness or head changes.

`authorise_option_freeze(option_id, expected_revision)` and `authorise_brief_freeze(brief_id, expected_revision)` return distinct `OperationAuthorizer` callables. Each requires its exact operation/canonical key, tenant-loads the option/brief and parent workstream, and rechecks current draft/decision role; neither requires the captured revision or mutable readiness state before replay.

- [ ] **Step 5: Add database immutability and verify**

Extend Task 3 guards for option versions, brief versions, citations and DecisionEvents. Run focused tests, trigger tests, schema drift and lint; expect green. Commit with subject `feat: freeze transformation decision briefs`.

---

### Task 8: Generalized typed ARB cycles preserving every governed subject

**Files:**
- Modify: `app/models/architecture_review_board.py`
- Modify: `app/models/transformation_decision.py`
- Create: `app/modules/transformation_room/arb_adapters.py`
- Modify: `app/modules/solutions_strategic/v2/services/arb_submission_service.py`
- Modify: `app/modules/solutions_strategic/v2/routes/governance_api_routes.py`
- Modify: `app/modules/architecture/routes/arb_routes.py`
- Test: `tests/test_typed_arb_submission_service.py`
- Modify: `tests/test_arb_submission_service.py`
- Modify: `tests/test_arb_governance_routes.py`

**Interfaces:**
- Consumes: immutable brief versions and existing Solution evidence submission.
- Produces: `ARBReviewCycle`, `ARBSubjectEvidenceSnapshot`, four `ARBSubjectAdapter` implementations; generalized `ARBSubmissionService.evaluate(subject, actor, assertions)` and `.submit` while retaining existing Solution call compatibility.

- [ ] **Step 1: Write the full typed-cycle matrix before implementation**

Parameterize `decision_brief`, `solution`, `architecture_model`, `adr`. Prove exactly-one logical subject FK and adapter-specific pinned evidence, tenant/type/FK/membership constraints, one open cycle race, canonical route delegation, four legacy backfills, terminal same-version replay, new Decision Brief version after return/rejection even with unchanged content, and preservation of existing Solution behavior.

For missing legacy snapshots in Solution/ArchitectureModel/ADR, assert migration produces only `historical_unverified` with immutable gap/source IDs; it cannot transition/resubmit or contribute verified posture. A separate verified successor opens only after current evidence evaluation creates a real snapshot.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_typed_arb_submission_service.py tests/test_arb_submission_service.py tests/test_arb_governance_routes.py`

Expected: typed cycle and non-Solution submissions fail while existing Solution tests remain a regression baseline.

- [ ] **Step 3: Add cycle schema and commit-time shape/membership constraints**

`ARBReviewCycle` contains `subject_type`, real nullable FKs for DecisionBrief/Solution/ArchitectureModel/ADR, review number, cycle number, pinned DecisionBriefVersion or Solution snapshot or model/ADR snapshot, status, historical gap fields and timestamps. Exactly one logical subject and exactly one adapter-appropriate snapshot is required; partial unique indexes allow one open cycle per typed subject. A deferrable PostgreSQL constraint trigger verifies same tenant and version membership at commit. `ARBReviewItem` remains the sole governance review and gains one-to-one cycle linkage rather than a parallel status owner.

- [ ] **Step 4: Implement adapter protocol and four adapters**

```python
class ARBSubjectAdapter(Protocol):
    subject_type: str
    load: Callable[[ActorContext, int], GovernedSubject]
    evaluate: Callable[[ActorContext, GovernedSubject, Mapping[str, Any]], ARBReadinessResult]
    snapshot: Callable[[ActorContext, GovernedSubject, ARBReadinessResult], PinnedEvidence]
    canonical_url: Callable[[GovernedSubject], str]

class DecisionBriefARBAdapter:
    subject_type = "decision_brief"

    def load(self, actor: ActorContext, subject_id: int) -> GovernedSubject:
        brief = DecisionBriefService.load_brief_for_tenant(actor, subject_id)
        version = DecisionBriefService.require_latest_frozen_version(brief)
        return GovernedSubject(self.subject_type, brief.id, brief.organization_id,
                               brief.title, version.id)

    def evaluate(self, actor: ActorContext, subject: GovernedSubject,
                 assertions: Mapping[str, Any]) -> ARBReadinessResult:
        readiness = DecisionBriefService.evaluate(actor=actor, brief_id=subject.subject_id)
        return decision_brief_arb_readiness(readiness, assertions)

    def snapshot(self, actor: ActorContext, subject: GovernedSubject,
                 readiness: ARBReadinessResult) -> PinnedEvidence:
        version = DecisionBriefService.require_version_for_tenant(
            actor, subject.logical_version_id)
        if not DecisionBriefService.verify_hash(version):
            raise CommandConflict("decision_brief_hash_mismatch")
        return PinnedEvidence("decision_brief_version", version.id, version.content_hash)

    def canonical_url(self, subject: GovernedSubject) -> str:
        return f"/solutions/programmes/{load_programme_id(subject)}/workstreams/{load_workstream_id(subject)}/decision"
```

Implement `decision_brief_arb_readiness()` as a pure conversion that combines the gate blockers with asserted human review but never accepts client readiness. `load_programme_id()` and `load_workstream_id()` resolve the already tenant-validated brief parents. Implement the other three adapters with the same four concrete operations: Solution delegates its current evaluator/snapshot creation and reuses `ARBSubmissionEvidenceSnapshot`; ArchitectureModel and ADR tenant-load their real FK row, run their established evidence policies and insert `ARBSubjectEvidenceSnapshot`; all return their existing canonical URLs. Keep existing Solution method parameters as a typed adapter wrapper so callers do not fork behavior.

- [ ] **Step 5: Generalize the sole submission transaction and decisions**

`submit` locks the subject/cycle, verifies the snapshot/hash and authorization, creates cycle + canonical `ARBReviewItem` + `DecisionEvent` atomically, and returns the same result for same-version terminal replay. Decision authority comes from server roles/assignment and cannot equal a forged client field. Return-for-evidence/options closes the cycle; the next Decision Brief submission requires a new version. Conditions create canonical `ARBCondition` rows and `ApprovedWithConditions`; fulfilment/waiver service records evidence, authority, reason and expiry before projection to `Approved`.

Every ARB submission, decision, return, condition fulfilment and waiver mutation delegates through `CommandService.execute` with its own `ARBSubmissionService.authorise_<operation>(subject_type, subject_id, captured_version_or_cycle_id)` factory. The callable verifies exact operation/key, tenant-loads the typed subject and rechecks current submitter/decision/condition authority before replay; cycle openness, terminal state, snapshot freshness and condition status remain locked handler preconditions.

- [ ] **Step 6: Delegate compatibility routes**

Every generic or legacy Solution/ArchitectureModel/ADR route calls the typed service or rejects unsupported subjects; none constructs `ARBReviewItem` directly. Preserve canonical deep links and response envelopes.

- [ ] **Step 7: Verify and commit**

Run focused tests plus schema-drift, boot-health, tenant isolation and raw-SQL gates. Expected all four adapters green and no Solution regression. Commit with subject `feat: unify typed ARB review cycles`.

---

### Task 9: Canonical execution, benefits, measured outcomes and optional Solution

**Files:**
- Create: `app/modules/transformation_room/execution_service.py`
- Create: `app/modules/transformation_room/outcome_service.py`
- Modify: `app/models/transformation_execution.py`
- Modify: `app/modules/solutions_strategic/v2/services/strategic_service.py`
- Test: `tests/test_transformation_execution_service.py`
- Test: `tests/test_outcome_measurement_service.py`

**Interfaces:**
- Consumes: approved typed ARB cycles, Task 1 delivery links, Task 3 command runner.
- Produces: `TransformationExecutionService.materialise`, `.create_technology_solution`, `OutcomeMeasurementService.record`, `DeliveryExportAttempt`.

- [ ] **Step 1: Write failing materialisation and outcome tests**

Cover non-technology approval through Completed with zero Solution rows; explicit technology-required creation with exactly one Solution and inherited programme/workstream/constraints/evidence; technology-false rejection; `ApprovedWithConditions` blocking, fulfilment and expired waiver blocking; one WorkPackage/RoadmapItem/Benefit per accepted action/outcome natural key; retry/concurrent materialisation; forced subordinate-write rollback; export provider failure leaving canonical work pending with immutable attempt; and cross-tenant IDs.

Outcome tests append a measured miss, update compatible Benefit actual projection in the same transaction, set `not_realised`, retain the row, create owner follow-up, and return variance only for comparable unit/baseline. Missing facts remain null.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_execution_service.py tests/test_outcome_measurement_service.py`

Expected: service imports fail.

- [ ] **Step 3: Implement atomic materialisation**

```python
class TransformationExecutionService:
    @classmethod
    def materialise(cls, *, actor: ActorContext, decision_brief_version_id: int,
                    actions: Sequence[ApprovedAction], command_key: str) -> CommandResult:
        request = cls.validate_materialisation_request(
            actor, decision_brief_version_id, actions)
        return CommandService.execute(
            actor=actor, operation="execution.materialise", idempotency_key=command_key,
            payload=request,
            natural_key=f"materialise:{decision_brief_version_id}:{sha256_canonical(request)}",
            authorizer=cls.authorise_materialisation(
                decision_brief_version_id, request),
            handler=lambda session, claim: cls._materialise_locked(
                session, actor, request, claim),
        )
    @classmethod
    def create_technology_solution(cls, *, actor: ActorContext,
                    decision_brief_version_id: int, option_version_id: int,
                    command_key: str) -> CommandResult:
        request = {"decision_brief_version_id": decision_brief_version_id,
                   "option_version_id": option_version_id,
                   "explicit_action": "create_technology_solution"}
        return CommandService.execute(
            actor=actor, operation="execution.create_solution", idempotency_key=command_key,
            payload=request,
            natural_key=f"solution:{decision_brief_version_id}:{option_version_id}",
            authorizer=cls.authorise_solution_creation(
                decision_brief_version_id, option_version_id),
            handler=lambda session, claim: cls._create_solution_if_required(
                session, actor, request, claim),
        )
```

Lock the approved cycle/version, verify all conditions at command time, create canonical WorkPackages through the existing ArchiMate sync service, RoadmapItems where scheduling applies, and Benefits from pre-existing outcome commitments/measures. Use `materialisation_key = sha256(tenant, decision-version, action/outcome, option)` and canonical partial unique indexes. Do not populate legacy Enterprise Initiative fields. Solution creation additionally requires true technology flag and an explicit action; populate `initiative_id` and `workstream_id`, copy only cited constraints/context, and create no programme replacement.

- [ ] **Step 4: Implement append-only export attempts and measurements**

```python
class OutcomeMeasurementService:
    @classmethod
    def record(cls, *, actor: ActorContext, benefit_id: int, value: Decimal | None,
               unavailable_reason: str | None, observed_at: datetime,
               source_identity: str, source_version: str,
               command_key: str) -> CommandResult:
        request = cls.validate_measurement(
            actor, benefit_id, value, unavailable_reason,
            observed_at, source_identity, source_version)
        return CommandService.execute(
            actor=actor, operation="outcome.measure", idempotency_key=command_key,
            payload=request,
            natural_key=f"measurement:{benefit_id}:{source_identity}:{observed_at.isoformat()}:{source_version}",
            authorizer=cls.authorise_measurement(
                benefit_id, source_identity, observed_at, source_version),
            handler=lambda session, claim: cls._append_measurement_and_project(
                session, actor, request, claim),
        )
```

`validate_materialisation_request()` same-tenant loads the frozen version, approved cycle, actions, outcomes and active conditions and rejects any unresolved/expired condition. `_materialise_locked()` locks that graph, repeats authorization/gate checks, calls the canonical ArchiMate-backed WorkPackage creator, inserts RoadmapItems when scheduling applies and Benefits from the existing commitments/measures, and returns every ID in `DomainMutationResult`; unique materialisation keys handle races. `_create_solution_if_required()` additionally locks the selected captured option, requires its technology flag and explicit action, and creates one linked Solution. `validate_measurement()` authorizes the benefit owner/delegate, normalizes source identity and requires exactly one of value/unavailable reason. `_append_measurement_and_project()` locks Benefit, inserts immutable measurement, updates actual projection/status, records not-realised follow-up when measured target is missed, and returns canonical IDs. Completed DeliveryExportAttempt rows become immutable; retries create successor attempts.

`authorise_materialisation(decision_brief_version_id, request)`, `authorise_solution_creation(decision_brief_version_id, option_version_id)` and `authorise_measurement(benefit_id, source_identity, observed_at, source_version)` each return a distinct `OperationAuthorizer`. They require their exact operation/key, tenant-load the captured version/option/benefit graph and recheck execution architect or benefit owner/delegate authority. Approval/conditions, technology flag, duplicate materialisation and measurement shape remain locked handler preconditions. Export/retry commands likewise use delivery-export-specific authorizers that tenant-load the work item and recheck export authority.

- [ ] **Step 5: Verify and commit**

Run focused tests, trigger/schema/tenant/raw-SQL gates and lint. Expected exact one-row sets and no false success. Commit with subject `feat: materialise transformation decisions and outcomes`.

---

### Task 10: Versioned Transformation Room API and authorization matrix

**Files:**
- Create: `app/modules/transformation_room/api.py`
- Create: `app/modules/transformation_room/http.py`
- Modify: `app/modules/solutions_strategic/v2/__init__.py`
- Modify: `app/_bootstrap/blueprints.py`
- Test: `tests/test_transformation_api.py`
- Modify: `tests/smoke/test_authorization_matrix.py`

**Interfaces:**
- Consumes: Tasks 4–9 domain services.
- Produces: `/api/v1/transformation-programmes` resources and a uniform `{data, meta, errors, request_id}` envelope.

- [ ] **Step 1: Write route-contract tests for every resource and failure state**

Test programmes, workstreams, candidates, evidence requests/attestations, options/versioning, briefs/freezing/submission, transitions, execution, Solution creation and outcomes. For each mutation assert missing Idempotency-Key `400`, same replay exact success, changed digest `409`, stale `If-Match` `409`, CSRF/auth policy, no client-controlled identity/status, and error distinction: `not_authorised`, `not_found`, `conflict`, `blocked_by_evidence`, `validation_failed`, `provider_failed`, `retryable_failure`.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_api.py tests/smoke/test_authorization_matrix.py -k transformation`

Expected: endpoints 404.

- [ ] **Step 3: Add actor/envelope/error adapters and thin routes**

```python
def actor_context() -> ActorContext:
    if not current_user.is_authenticated:
        raise AuthenticationRequired()
    organization_id = getattr(g, "current_org_id", None)
    if organization_id is None:
        raise AuthenticationRequired()
    return ActorContext(current_user.id, organization_id,
                        frozenset(resolve_enterprise_roles(current_user)),
                        request.headers.get("X-Request-ID") or str(uuid.uuid4()))

def api_success(data: Mapping[str, Any], *, status: int, request_id: str,
                meta: Mapping[str, Any] | None = None) -> Response:
    response = jsonify({"data": dict(data), "meta": dict(meta or {}),
                        "errors": [], "request_id": request_id})
    response.status_code = status
    return response

def api_error(code: str, message: str, *, status: int,
              request_id: str, field: str | None = None) -> Response:
    error = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    response = jsonify({"data": None, "meta": {}, "errors": [error],
                        "request_id": request_id})
    response.status_code = status
    return response
```

Define `AuthenticationRequired` as a `TransformationError` with code `not_authenticated` and status 401 in Task 3, and `resolve_enterprise_roles()` as the existing role-access mapper plus effective programme assignments. No route issues `db.session.commit()` or creates a model. It parses, rejects server-owned fields, delegates, maps domain error types to exact HTTP semantics and emits opaque security audit events. Add per-user/tenant repeated foreign-ID probe rate limiting through the established limiter when configured.

Routes never construct, accept or pass an authorization result. Each mutation delegates to the operation-specific public domain service, and that service constructs the mandatory `OperationAuthorizer` passed to `CommandService.execute`. A request field, route flag or permissive callback cannot replace that authorizer; replay authorization is therefore evaluated from current server-side identity, tenant and assignments before a prior result or natural-key recovery can be returned.

- [ ] **Step 4: Register without a second programme blueprint**

Register the API blueprint through `app/modules/transformation_room/register(app)` from the canonical solutions-strategic bootstrap path. Add critical endpoint checks for programme list/detail and API intake. Preserve CSRF for browser endpoints and use established API protection.

- [ ] **Step 5: Verify and commit**

Run route/authorization tests, boot-health, template references and tenancy gates. Commit with subject `feat: expose governed transformation APIs`.

---

### Task 11: Transformation Room information architecture, deep links and Chief Architect roll-up

**Files:**
- Read before edits: `DESIGN.md`
- Create: `app/modules/transformation_room/routes.py`
- Create: `app/modules/transformation_room/read_models.py`
- Create: `app/templates/solutions/transformation_room/layout.html`
- Create: `app/templates/solutions/transformation_room/overview.html`
- Create: `app/templates/solutions/transformation_room/workstreams.html`
- Create: `app/templates/solutions/transformation_room/objective.html`
- Create: `app/templates/solutions/transformation_room/discover.html`
- Create: `app/templates/solutions/transformation_room/evidence.html`
- Create: `app/templates/solutions/transformation_room/options.html`
- Create: `app/templates/solutions/transformation_room/decision.html`
- Create: `app/templates/solutions/transformation_room/execute.html`
- Create: `app/templates/solutions/transformation_room/outcomes.html`
- Create: `app/templates/solutions/transformation_room/governance.html`
- Create: `app/templates/solutions/transformation_room/roadmap.html`
- Modify: `app/templates/solutions/programme_wizard.html`
- Modify: `app/templates/solutions/programmes.html`
- Modify: `app/templates/solutions/architect_synthesis.html`
- Modify: `app/templates/components/admin_sidebar.html`
- Modify: `app/modules/solutions_strategic/v2/routes/programme_routes.py`
- Modify: `app/static/css/tailwind-output.css`
- Test: `tests/test_transformation_room_routes.py`
- Test: `tests/test_transformation_room_templates.py`
- Create: `tests/smoke/test_transformation_room_journeys.py`

**Interfaces:**
- Consumes: API/domain/read services; DESIGN contract.
- Produces: all stable room URLs, business-first intake, intent-led navigation and Chief Architect portfolio projection.

- [ ] **Step 1: Read `DESIGN.md` completely and record the applicable contract in the task ledger**

Record base template, button/form/card/status macros, token names, Alpine ownership rule, entity-picker endpoint and accessibility requirements. Do not edit UI before this read is complete.

- [ ] **Step 2: Write failing route/template/smoke tests**

Assert every stable URL in the spec renders and is refreshable; header includes objective/lifecycle/owner/next action/evidence posture/expected outcome/breadcrumb; stages are inspectable without implying readiness; blocker links target exact request; loading/unavailable/failure/unknown are distinct; null displays `—`; server-rendered forms work; keyboard/focus/landmarks/labels satisfy the axe audit. Assert intake creates no Solution and redirects to Objective. Assert Chief Architect sees non-Solution programmes, evidence debt, decision ageing, cross-domain dependencies, delivery confidence and outcome variance.

- [ ] **Step 3: Build read models with honest nullable projections**

```python
class TransformationRoomReadModel:
    @classmethod
    def stage(cls, *, actor: ActorContext, programme_id: int,
              workstream_id: int, stage: str) -> StageView:
        programme = TransformationProgrammeService.get_programme(
            actor=actor, programme_id=programme_id)
        if workstream_id not in programme.workstream_ids:
            raise NotFound()
        resources = cls.load_stage_resources(actor, workstream_id, stage)
        gate = TransformationGateService.evaluate(
            actor=actor, workstream_id=workstream_id,
            target_stage=cls.next_stage(stage))
        return StageView(programme, workstream_id, stage, gate,
                         resources, cls.unavailable_reasons(resources))

class ChiefArchitectTransformationReadModel:
    @classmethod
    def portfolio(cls, *, actor: ActorContext) -> TransformationPortfolioView:
        cls.require_chief_or_enterprise_architect(actor)
        programmes = cls.load_programmes(actor)
        return TransformationPortfolioView(
            programmes=tuple(programmes),
            evidence_debt=cls.evidence_debt(actor, programmes),
            decision_ageing=cls.decision_ageing(actor, programmes),
            delivery_confidence=cls.delivery_confidence(actor, programmes),
            outcome_variance=cls.outcome_variance(actor, programmes),
        )
```

`load_stage_resources()` dispatches from an allowlisted stage-to-query mapping and every query includes tenant/workstream membership; `next_stage()` uses Task 4's transition map; `unavailable_reasons()` records why each empty metric is unavailable. The four portfolio aggregators group only comparable facts and return null entries when inputs are missing. Compute no metrics in templates. Segment by organisation/workstream and return `None` plus reason when no measure exists. Verify evidence hashes on read and render unavailable if verification fails.

- [ ] **Step 4: Implement stable room routes and compatibility-safe programme root**

Add `/solutions/programmes/<id>/overview`, `/workstreams`, each workstream stage, `/governance` and `/roadmap`. Existing `/solutions/programmes/<id>` redirects to overview with 302. Every load uses explicit tenant predicate and maps foreign IDs to 404. ARB return URLs target decision stage.

- [ ] **Step 5: Replace technology-first intake and create accessible stage templates**

Intake fields are objective, intended outcome/measure, scope, owner picker, target date/unavailable reason and first workstream. Technology platform/vendor appears only when workstream type is technology. Copy explicitly states that a technology Solution can be added after approval. Templates use existing macros/tokens, progressive stage rail, persisted canonical IDs and exact recovery links. Alpine sends `Idempotency-Key` and `If-Match`, checks `response.ok`, renders server errors and only toasts success after canonical IDs return.

Room routes and browser code call only the Task 4–9 public services; they cannot call `CommandService` directly or supply an authorizer. Any later read-model mutation must likewise delegate to an operation-specific public service whose mandatory `OperationAuthorizer` is evaluated before command replay.

- [ ] **Step 6: Make navigation intent-led and broaden architect synthesis**

Add guarded navigation for **Transform**, **Decisions**, **Execute**, **Outcomes**. Extend existing Chief Architect service/template rather than replace its Solution insights; add Transformation posture alongside them. No role is removed and no solution-only metric is relabelled as enterprise posture.

- [ ] **Step 7: Rebuild CSS and verify visual/static gates**

Run:

```bash
python scripts/build_css.py
python scripts/build_css.py --check
pytest -q tests/test_transformation_room_routes.py tests/test_transformation_room_templates.py tests/smoke/test_transformation_room_journeys.py
python scripts/verify.py --gate template-syntax
python scripts/verify.py --gate template-references
python scripts/verify.py --gate design-tokens
python scripts/verify.py --gate air-gap
python scripts/verify.py --gate css-build
```

Expected: CSS check byte-identical, templates/gates green, axe baseline not worsened.

- [ ] **Step 8: Commit**

Commit listed files with subject `feat: deliver the transformation room experience`.

---

### Task 12: Evidence-backed AI actions and operational observability

**Files:**
- Modify: `app/modules/ai_chat/tools/executor.py`
- Modify: `app/modules/ai_chat/services/workbench_kernel.py`
- Modify: `app/modules/ai_chat/services/architect_persona_charters.py`
- Create: `app/modules/transformation_room/telemetry.py`
- Modify: `app/modules/solutions_strategic/v2/services/chief_architect_service.py`
- Test: `tests/test_transformation_ai_tools.py`
- Test: `tests/test_transformation_observability.py`

**Interfaces:**
- Consumes: canonical services and actor permissions.
- Produces: AI tool wrappers returning allowed actions/citations/abstentions; structured logs and metrics without raw evidence/prompts.

- [ ] **Step 1: Write failing AI boundary and telemetry tests**

Assert AI can request discovery, explain cited signals, draft option/brief content and abstain when required evidence is absent. Assert it cannot construct models, attest, choose conflict truth, assert human review, submit as a different user, decide, materialise or report success without canonical IDs. Provider failure is `provider_failed`, never a blocker/success. Capture logs and assert request/command ID, tenant, actor, programme/workstream, transition, policy, idempotency disposition, duration/error class, but no evidence values or prompts.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_ai_tools.py tests/test_transformation_observability.py`

Expected: missing tool actions/telemetry and boundary failures.

- [ ] **Step 3: Route AI through canonical services only**

Expose narrow tool operations that build `ActorContext` from authenticated runtime and call the same discovery/evidence/option/brief services. Draft responses contain `citations`, `confidence`, `unknowns`, `abstained`, `allowed_actions` and canonical deep link. Remove/directly reject model-constructor and client-state shortcuts for Transformation Room subjects.

AI tools cannot construct, select or bypass an `OperationAuthorizer`. Every mutating tool calls the same operation-specific public domain service as HTTP, and that service supplies its mandatory authorizer to `CommandService.execute`; replay therefore rechecks the authenticated runtime actor before returning any prior or reconstructed result.

- [ ] **Step 4: Add logs, metrics and audit hooks**

Instrument command/transition rate/latency/failures, blockers, evidence age/completeness, ARB ageing/idempotent collisions, execution/optional-Solution rate, migration counts, page/API errors, AI invocation/abstention/correction/token cost/provider failure. Add alerts through the existing monitoring interface for repeated transition failures, immutability violations, denial spikes, migration divergence, ARB queue failure and overdue outcome jobs.

- [ ] **Step 5: Verify and commit**

Run focused tests, fabricated-data, lint-core and boot-health. Expected no fake fallback and no sensitive payload logging. Commit with subject `feat: govern transformation AI assistance`.

---

### Task 13: Profiled Release 1 migration, compatibility bridges and deep-link preservation

**Files:**
- Create: `app/models/transformation_migration.py`
- Create: `app/modules/transformation_room/migration_service.py`
- Create: `app/commands/migrate_transformation_room.py`
- Modify: `app/_bootstrap/cli.py`
- Modify: `app/modules/applications/routes/rationalization_routes.py`
- Modify: `app/modules/solutions_strategic/v2/routes/programme_routes.py`
- Test: `tests/test_transformation_migration.py`
- Test: `tests/test_transformation_compatibility_routes.py`
- Create: `scripts/verify_transformation_migration.py`

**Interfaces:**
- Consumes: canonical graph and legacy `StrategicInitiative`, `EnterpriseInitiative`, Solution programme links, wizard JSON and rationalisation records.
- Produces: `LegacyProgrammeBridge`, immutable migration attachments/conflicts/runs; `flask --app manage migrate-transformation-room profile|dry-run|apply|verify`; compatibility resolver.

- [ ] **Step 1: Write the complete fixture matrix and failing tests**

Cover Strategic-only, Enterprise-only, provably matching, conflicting, Solution-linked, wizard JSON, all active rationalisation score/audit/replacement/dossier/benefit states, exact canonical delivery links and ambiguous status. Assert dry-run has zero writes, row fingerprints and target IDs make reruns identical, one-organisation runs never touch another, conflicts stop only their row, and unknown JSON is retained in immutable attachment.

Release 1 safely maps only records whose identity/status/semantics are provable. It does not switch universal reads or delete/disable Enterprise Initiative or legacy rationalisation records.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_transformation_migration.py tests/test_transformation_compatibility_routes.py`

Expected: migration command/models absent and old routes do not resolve canonical stages.

- [ ] **Step 3: Implement profiler and deterministic mapping policies**

Profile per-tenant counts, references, nulls, duplicates, invalid FKs, money by currency and fingerprints. Implement the spec's exact status maps and retain source status, policy version and reason. Classify existing `initiative_type` or Solution-linked Strategic initiatives as Transformation Programme; bridge Enterprise Initiative only through proven identity; map durable wizard JSON into typed records and retain unmapped keys. Do not infer lifecycle advancement from prose.

- [ ] **Step 4: Map rationalisation records without promoting pseudo-governance**

Scores become derived Evidence with formula/config/time; overrides/audits retain actor/time/provenance; replacement plans become option drafts or approved versions only when authoritative state proves it; dossier becomes draft Decision Brief; pseudo-ARB status becomes imported historical event only. Only verifiable canonical ARB creates governed state. Benefit trackers map only when unit/baseline/target/actual semantics are provable; otherwise create an evidence gap and retain read-only legacy view. Link WorkPackage/RoadmapItem only by proven source identity.

- [ ] **Step 5: Implement compatibility reads and preserved deep links**

Canonical writes only. Legacy mutation endpoints delegate to canonical services where a mapping exists, otherwise return explicit read-only/migration-required response; no dual-write. `/applications/rationalization` remains discovery entry. Workbench/planning/tracking routes redirect to mapped persisted stages or render a non-destructive chooser. Existing programme drift/fit-gap/snapshot links map to room views. Application-specific legacy links remain read-only until mapped, then redirect with provenance banner. Add redirect-loop and cross-tenant tests.

Compatibility endpoints never call `CommandService` directly and cannot pass a client-derived authorizer. Canonical delegates use the destination operation's public service and mandatory operation-specific authorizer. If the migration runner uses command receipts for an apply step, it supplies a dedicated maintenance authorizer that validates the authenticated deployment actor, exact organisation, operation and natural key from server-side state; a permissive migration callback is forbidden.

- [ ] **Step 6: Add machine-verifiable reports and rollback evidence**

`scripts/verify_transformation_migration.py` compares counts, source/target links, statuses, money totals by currency, fingerprints, unmapped/conflict lists and sampled dossier hashes. CLI supports `--organization-id`, `--resume-cursor`, `--json-report`, `--dry-run`; apply records every row. Rollback disables feature reads/writes and leaves additive canonical history intact; it does not undo governance/outcomes or return writes to a second authority.

- [ ] **Step 7: Verify and commit**

Run migration and compatibility tests twice, schema/tenant/raw-SQL/boot gates and a JSON dry-run. Expected identical second targets, zero unexplained loss, zero foreign-tenant mutation. Commit with subject `feat: bridge legacy transformation records`.

---

### Task 14: Release 1 end-to-end journeys and production-like migration rehearsal

**Files:**
- Create: `tests/journeys/test_transformation_room_release1.py`
- Modify: `tests/smoke/test_transformation_room_journeys.py`
- Create: `tests/fixtures/transformation_migration_matrix.py`
- Create: `deploy/verify_transformation_room.py`
- Modify: `docs/plans/2026-08-21-best-in-class-tasklog.md`

**Interfaces:**
- Consumes: all Release 1 features.
- Produces: persona journey proof, production synthetic verifier and recorded migration before/after artifact references.

- [ ] **Step 1: Write journey tests for every named persona**

Implement exact journeys: Enterprise Architect creates non-Solution programme; Application Architect accepts cited candidate, requests/records attestation, compares options and freezes brief; Business Owner can attest only assigned claim; ARB member returns for evidence then approves a new version with conditions; Delivery Lead materialises after condition resolution; Solution Architect creates Solution only for explicit technology option; Benefit Owner records a miss; Chief Architect sees full posture; AI drafts/cites/abstains without privileged acts.

- [ ] **Step 2: Add invariant journeys around concurrency and failure**

Exercise command crash points, lease fencing, root/correction evidence races, typed ARB cycle races, materialisation races, subordinate rollback, foreign-ID 404, forged state/identity rejection, immutable direct SQL and null preservation as integrated flows.

For HTTP, UI, AI and compatibility entry points, include replay-bypass journeys proving a missing, non-callable, permissive or client-supplied authorizer cannot reach claim, prior-result reconciliation, natural-key reconciliation or handler work. Assert the operation-specific service authorizer runs first for both same-receipt replay and domain-row-only crash recovery, and that a now-unauthorised actor receives no canonical result or existence disclosure.

- [ ] **Step 3: Build the production synthetic verifier**

`deploy/verify_transformation_room.py <base-url>` authenticates a dedicated synthetic tenant/user, creates a uniquely keyed business programme, completes Objective through Outcomes without Solution, follows every deep link, records a not-realised measurement, validates Chief Architect roll-up, then repeats a second technology-required flow and proves exactly one linked Solution. It verifies canonical IDs and response states after each mutation and exits non-zero on false success, missing citation, redirect loop, revision mismatch or foreign data.

- [ ] **Step 4: Rehearse migration on a production-like backup**

Capture database revision, row counts, links, per-currency totals, schema constraints and backup checksum before work. Restore the backup into an isolated PostgreSQL database, run capability cutover dry-run/apply and Transformation Room profile/dry-run/apply/verify for every tenant, rerun apply, and execute compatibility/deep-link smoke. Record reports outside git if they contain data; commit only sanitized counts/checksums/exception categories in the task log. Expected: zero ambiguous active capability links, zero unexplained migration loss, identical rerun targets and no change to source database.

- [ ] **Step 5: Run all Release 1 focused suites**

Run:

```bash
pytest -q tests/test_transformation_*.py tests/test_rationalisation_discovery_service.py tests/test_evidence_head_concurrency.py tests/test_typed_arb_submission_service.py tests/test_outcome_measurement_service.py tests/journeys/test_transformation_room_release1.py
pytest -q tests/smoke/test_transformation_room_journeys.py tests/smoke/test_authorization_matrix.py
python deploy/verify_transformation_room.py http://127.0.0.1:5000
```

Expected: all tests pass, no skip counted as success, synthetic journey exits 0.

- [ ] **Step 6: Commit**

Commit test/verifier/task-log files with subject `test: prove transformation room release one`.

---

### Task 15: Independent review, full verification, exact-commit deployment and production proof

**Files:**
- Modify only as required by review findings: files introduced in Tasks 1–14
- Modify: `docs/plans/2026-08-21-best-in-class-tasklog.md`

**Interfaces:**
- Consumes: verified candidate branch and production deployment tooling.
- Produces: zero-open-Critical/Important review, fully green release evidence, deployed exact revision and production journey proof.

- [ ] **Step 1: Request an independent whole-branch review**

Give the reviewer the approved spec, this plan and the complete base-to-head diff. Require requirement-by-requirement architecture, security, tenant, data-integrity, failure-state, migration, UX and backward-compatibility review. Do not proceed with any open Critical or Important finding.

- [ ] **Step 2: Resolve findings test-first and repeat review once**

For each accepted finding, add a test that fails for the reported defect, implement the smallest spec-faithful correction, run its focused suite, and record disposition. Submit one consolidated re-review; expected result is no Critical or Important finding.

- [ ] **Step 3: Finalise candidate-known release evidence before verification**

Update the best-in-class task log with the approved spec/plan paths, task commit list, independent review disposition, focused test counts and the sanitized production-like migration rehearsal counts/checksums/exception categories. State explicitly that Release 1 retains Enterprise Initiative and legacy rationalisation bridges and makes no Retirement Release claim. Commit this documentation with subject `docs: record transformation room release candidate`, then run the independent diff reviewer over that documentation-only tip to preserve the zero-open-Critical/Important condition. This commit becomes part of the candidate SHA; no tracked file changes are permitted after Step 4 begins unless verification restarts from Step 1.

- [ ] **Step 4: Run every local verification gate against the exact candidate**

Set both `TEST_DATABASE_URL` and `DATABASE_URL` to the configured PostgreSQL test database, then run:

```bash
python scripts/verify.py --json
python scripts/build_css.py --check
pytest -q tests/journeys/test_transformation_room_release1.py
```

Expected: every applicable gate reports passed; no skipped gate is represented as a pass; full behavioural suite is green; committed CSS is byte-identical.

- [ ] **Step 5: Prove CI-only gates**

Run/publish the candidate and require green `secret-scan`, `security-sast`, Playwright smoke, axe accessibility, authorization matrix, dependency audit, database gates and SBOM generation. Inspect coverage output for unexplained regression even though it is not gated.

- [ ] **Step 6: Merge and push only the reviewed commit graph**

Verify `git status --short`, preserve unrelated user changes, merge with `--ff-only` where possible, stage files explicitly and push main. Record the verified SHA. Do not amend or sweep staged files.

- [ ] **Step 7: Deploy schema-hidden, run maintenance foundations, then enable the room**

Take a production backup and before-measurement. Deploy the exact verified SHA with Transformation Room UI/write controls hidden. Run privileged schema reconciliation and verify triggers/constraints. Run capability cutover profile/dry-run; apply only when zero ambiguous active links and backup verification are green. Run Transformation Room migration profile/dry-run/apply/verify tenant by tenant for safely mappable Release 1 records. Enable canonical writes for the internal/test organisation, execute the complete synthetic cycle, then enable the intended cohort. No legacy read retirement occurs in Release 1.

- [ ] **Step 8: Verify production health and synthetic journeys**

Run:

```bash
python deploy/verify_production.py https://165-22-125-156.sslip.io
python deploy/verify_transformation_room.py https://165-22-125-156.sslip.io
```

Confirm production `git rev-parse HEAD` equals the verified SHA, application/container health is healthy, login works, Objective-to-Outcomes and technology-optional journeys succeed, legacy deep links resolve, database before/after measurements reconcile and alerts show no tenant/immutability/migration anomaly. Write production-only results to ignored `deploy-reports/transformation-room-<verified-sha>.json` and include the same concise evidence in the final response; do not commit this report.

- [ ] **Step 9: Exercise and report rollback readiness without reversing governance**

Prove feature controls can pause canonical writes and restore compatible legacy reads while additive canonical records remain authoritative and intact. Verify counts, referential integrity, deep links and health after the rehearsal; re-enable the release. Append the rollback rehearsal to the ignored deployment report and final response. Database restore is reserved for demonstrated additive schema/data corruption and uses the captured backup after recording failure state. End with the running SHA still equal to the SHA independently reviewed in Steps 1–3, fully verified in Steps 4–5 and deployed in Step 7. If any tracked production-result documentation is required, create that commit, return to Step 1, re-review, rerun every gate and CI, redeploy the new exact SHA, and repeat production verification before reporting completion.
