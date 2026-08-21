# Evidence-Gated ARB Submission Design

## Purpose

Make every solution submission to the Architecture Review Board one governed,
tenant-safe, evidence-backed operation. Chat, the AI workbench, and HTTP routes
must not be able to manufacture different meanings of "submitted".

## Authoritative records

- `Solution` is the governed subject.
- `SolutionAnalysisSession` is the optional AI-workbench context.
- `ARBReviewItem` is the only ARB queue record created by this flow.
- A new append-only `ARBSubmissionEvidenceSnapshot` records exactly what was
  evaluated and submitted. Mutable workspace metadata and `Solution.arb_snapshot`
  are not submission evidence.
- The parallel `SolutionARBReview` model is legacy and is not written by the
  new flow.

## Service boundary

`ARBSubmissionService.evaluate(...)` returns a structured readiness decision
without writes. `ARBSubmissionService.submit(...)` repeats the evaluation and,
only when it passes, atomically creates or returns the canonical review item,
inserts its evidence snapshot, updates the solution, and queues notification and
audit records.

Inputs are identifiers and trusted server context: `solution_id`, `actor_id`,
optional `workspace_id`, and explicit human-review/cost/resubmission evidence.
Workflow type is derived from persisted workspace metadata; callers cannot
choose it. Chat must carry a trusted workspace identifier injected by the
server, not an LLM-supplied identifier.

## Fail-closed evaluation

The evaluator must prove all of the following:

1. Actor, solution, and optional workspace exist in the same organization.
2. Actor can access the solution: creator, administrator, or a named solution
   stakeholder, matching the existing solution access contract.
3. Workspace belongs to the actor and is linked to the same solution.
4. Solution governance state is `draft` or `rejected`.
5. AI-generated content has an explicit human-review assertion.
6. A non-zero cost has a declared `tco_engine` or `manual_override` source.
7. Recommended vendor references resolve.
8. The existing governance completeness gate passes. Gate exceptions block.
9. Required named workbench artifacts exist at the required lifecycle states.
   Greenfield requires `brief`, `scope`, and `recommendation`; brownfield
   requires `portfolio_context`, `current_state`, `gap_analysis`, and
   `transition_plan`. Every required artifact must be at least `persisted`.
10. Workspace absence is allowed only for direct, non-workbench submissions;
    the snapshot then records the direct-route checks and their evidence.

All failures use stable reason codes and actionable missing-evidence entries.
No exception is converted to readiness or submission success.

## Transaction and idempotency

Submission locks the solution row, re-evaluates readiness, and looks for an
active review in `submitted`, `under_review`, or `pending_information` for the
same organization and solution. A retry returns that record and never creates a
second item or snapshot. New submission writes the review item, snapshot,
solution status/date/link, notification, and audit in one transaction. Any
required write failure rolls the transaction back.

The snapshot contains schema version, organization, solution, workspace,
workflow type, actor, capture time, normalized checks, named artifact states and
payloads, governance result, request assertions, and a SHA-256 content hash. It
is never updated through application code.

## Entry-point convergence

- AI tool execution resolves the solution, requires trusted workspace context,
  and delegates to the central service.
- `WorkbenchKernel.submit_to_arb` delegates directly; no internal Flask test
  client and no false-success artifact.
- The canonical `/solutions/<id>/submit-for-arb` route becomes a thin adapter.
- Other solution submission paths discovered by the audit—legacy chat command,
  journey v2, governance API, and `/arb/api/solution/<id>/submit_review`—must
  delegate or be explicitly disabled with a pointer to the canonical route.
  Canvas-only reviews remain a separate ARB
  review type because they have no governed `Solution` identity.

## User-facing contract

Failure responses distinguish authorization, workspace binding, missing
evidence, invalid state, and evaluator unavailability. They include no raw
exception text. Successful responses identify the canonical review number,
whether the call was idempotent, and the evidence snapshot ID.

## Verification

- Unit/integration tests cover cross-tenant IDs, actor ownership, workspace
  mismatch, workflow derivation, every evidence requirement, fail-closed
  exceptions, duplicate/concurrent retries, rollback, and immutable snapshots.
- Contract tests prove every in-scope entry point calls the central service and
  cannot mutate `Solution` or create `ARBReviewItem` independently.
- Browser coverage proves missing evidence is visible and a successful retry
  reaches one canonical review.
- Full repository verification must pass with PostgreSQL, followed by deployment
  and public production checks.
