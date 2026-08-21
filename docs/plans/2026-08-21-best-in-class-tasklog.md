# Archie Best-in-Class Task Log

## North-star outcome

Archie is the AI-native system an organisation uses to turn a changing IT estate into
governed, executable transformation decisions:

```text
Signal → Explain → Decide → Execute → Learn
```

The product succeeds when an executive or architect can quickly answer:

1. What changed or is at risk?
2. Why does it matter to the business?
3. What decision or action should happen next, who owns it, and what evidence supports it?

## Product guardrails

- Do not add standalone EA modules unless they strengthen a proven end-to-end journey.
- AI output must be tenant-scoped, evidence-backed, explicit about confidence and unknowns, and create reviewable drafts rather than silently changing architecture truth.
- Treat diagrams as explanation and scenario tools, not the default data-entry experience.
- Every key screen must identify a next action, accountable owner, and intended outcome.
- Billing is out of scope.
- A release is not complete until required verification and production checks are green.

## Current evidence — 2026-08-21

The earlier audit measured the deployed platform as broad but insufficiently focused:

| Measure | Observed state | Product implication |
|---|---:|---|
| Application Python | ~824k LOC | Complexity is a bigger risk than feature scarcity. |
| Route decorators | 3,861 | Internal module boundaries are leaking into user journeys. |
| Models / tables | 652 / 746 | The meta-model is much wider than verified customer use. |
| Live data | 63 non-empty tables, 8,282 rows | Prove workflows against active data before expanding the model. |
| Defined but unregistered blueprints | 25 | Remove, contain, or deliberately wire incomplete surfaces. |

## Workstreams

### 0. Restore the delivery baseline — complete

**Outcome:** A verified, production-safe base for all product work.

- Resolve failing verification gates truthfully; never relax a baseline to hide a regression.
- Make the deployed tip, working branch, and `origin/main` converge safely.
- Run unit and smoke suites serially against an available test database.
- Preserve tenant isolation and error-signalling in all new data and AI paths.

**Exit evidence:** static verification green; unit and smoke suites green; production health and login checks green.

### 1. Prove one exceptional transformation loop

**Outcome:** Application rationalisation is a complete, measurable journey—not a collection of screens.

1. Select a transformation objective.
2. Identify duplicate, high-cost, end-of-life, or risky applications.
3. Explain business-capability, dependency, owner, cost, and risk impact.
4. Compare options and their assumptions.
5. Produce an ARB-ready decision brief.
6. Create governed execution work and track the realised outcome.

**Measures:** time from question to decision brief; accepted/rejected recommendation rate; owner-attestation completion; realised versus expected outcome.

### 2. Make architecture data trustworthy with little manual effort

**Outcome:** Facts show provenance, freshness, confidence, and an accountable owner.

- Reconcile active source-system data against the architecture model.
- Detect conflicts: retired-but-active systems, missing owners, unreviewed interfaces, and conflicting lifecycle data.
- Give contributors a short attestation inbox rather than a complex meta-model to navigate.
- Surface fact source, timestamp, confidence, and change history on core entities.

### 3. Make AI operational, evidence-backed, and bounded

**Outcome:** AI advances governed work rather than merely answering chat prompts.

- Generate evidence-backed decision briefs, with citations into the tenant's graph.
- State uncertainty and missing evidence in every recommendation.
- Draft ARB packs, risk registers, attestation requests, and execution work packages.
- Use bounded agents for reconciliation and evidence collection; require approval for material changes.
- Measure acceptance, correction rate, abstention quality, time saved, and cost per completed decision.

### 4. Simplify the shell around user intent

**Outcome:** Users complete work without learning Archie’s module taxonomy.

- Establish an executive decision cockpit, architect workbench, and contributor inbox.
- Standardise entity pages: status, business relevance, impact, evidence, history, and next action.
- Build a decision queue: decide now, investigate, improve model.
- Remove or quarantine unreachable and duplicate product surfaces after customer-value review.

### 5. Scale only proven loops

**Outcome:** Performance and reliability support real adoption.

- Move imports, document analysis, and long-running AI work off request workers.
- Maintain off-host backup and a tested restore procedure.
- Measure journey completion, queue health, slow queries, errors, and AI-provider failures.
- Lazy-load large graphs and closed modals; hold critical journeys to explicit page-weight and interaction budgets.

## Decision rules

- Prefer deleting, consolidating, or hiding unproven surface area to adding another adjacent feature.
- A roadmap item needs a named persona, measurable outcome, evidence source, and end-to-end workflow.
- A recommendation is incomplete until it has an owner, approval path, and observable result.
- Any data or AI path that lacks tenant isolation, provenance, or honest error signalling is blocked from expansion.

## Activity log

### 2026-08-21 — Goal and task log established

- Created the persistent best-in-class product objective.
- Created a fresh isolated branch from current `main` (`75005f17`) after the prior worktree pointer proved stale.
- Billing explicitly excluded.
- Workstream 0 is active; no new product surface should begin until its exit evidence is recorded.

### 2026-08-21 — Local delivery baseline restored

- Repaired the local PostgreSQL test schema using the repository's additive setup and
  reconciliation commands; schema drift now measures zero. Removed the obsolete
  `archimate_audit_logs.viewpoint_id` foreign key with the existing idempotent command
  after measuring it before and after.
- Static verification: 31 passed, 0 failed, 0 skipped. Navigation evidence is now
  generated in the CI test lifecycle instead of being assumed to exist in a fresh
  checkout; 2,224 endpoints were exercised and unresolved navigation targets improved
  from the ratchet ceiling of 19 to 16.
- Server-side suite: 1,940 passed, 5 skipped. Three skips are legitimate
  configuration/extract conditions. Live-model factual/persona evaluation and official
  ArchiMate OEF XSD validation remain explicit evidence gaps and must become dedicated
  integration gates rather than being represented as completed coverage.
- Browser suite: 54 passed, 1 skipped. The skip is the opt-in accessibility-baseline
  rewrite utility, not a product journey. The run found and fixed a real capability-map
  CSP defect caused by a context-less macro emitting a blank style nonce.
- The consolidated verifier then exposed eight broken UI surfaces that the static-only
  run did not cover. All eight were repaired rather than baselined: a missing active
  duplicate-detection route, an unchecked governance delete response, a false-success
  CSP assignment, and five silent or misleading error paths. The `broken-surfaces`
  gate now measures zero, with focused regression coverage.
- Release `c4a4584a` passed all 39 consolidated gates (1,945 server-side tests and
  54 browser journeys), was deployed, and passed all 11 public production checks.

### 2026-08-21 — Transformation programme modelling decision

- A business transformation does not imply a technology transformation.
- `/solutions/new-programme` will evolve into the transformation intake and orchestration
  journey. The Programme owns business outcomes, benefits, capabilities, value streams,
  operating-model change, stakeholders, measures, funding, and governance.
- Process, policy/control, organisation/skills, data, supplier, and technology workstreams
  are optional children. A Solution is created only when a workstream genuinely requires
  technology architecture; it is no longer treated as the programme itself.
- The existing programme cockpit, rollups, snapshots, motivation elements, capability and
  application links, and governance workflow are foundations to consolidate—not a reason
  to create a competing module.

### 2026-08-21 — Governed AI and Chief Architect release candidate

- Unified the AI assistant's persona choices with all nine enterprise roles. The signed-in
  user's role now selects a governed charter by default, and user preferences remain usable
  when browser storage is unavailable.
- Added a tenant-scoped approval inbox for AI-proposed mutations, including requester
  attribution, exact operation evidence, explicit failure states, and at-most-once execution.
- Reframed `/solutions/architect-synthesis` as a truthful Solution Conformance Roll-up:
  coverage and unavailable evidence are explicit, aggregate scores are withheld when they
  would mislead, ARB ageing is derived from tenant-scoped records, and the attention queue
  links every item to its evidence and next action.
- Defined the next Chief Architect information architecture without adding another dashboard:
  executive posture; enterprise architecture posture; governance and delivery; ranked
  attention backlog; trends and scenarios; and evidence-backed advisory synthesis. These
  views will compose existing briefing, repository-health, programme-governance, conformance,
  and ARB services.
- Audited the AI-to-ARB path. The next hardening slice is one fail-closed submission service
  that derives workflow type from persisted state, binds solution/workspace/actor/tenant,
  requires named evidence, creates one official ARB review item transactionally, and stores
  an immutable evidence snapshot.

### 2026-08-22 — Evidence-gated ARB workflow UX

- Replaced optimistic ARB submission feedback on the blueprint and journey review surfaces
  with explicit loading, unavailable, blocked, retry, and canonical-success states.
- Missing-evidence entries returned by the governed service remain visible as an actionable
  evidence ledger. AI-assisted content requires an explicit human-review assertion before
  submission can be attempted.
- Success is withheld unless the response contains both the canonical review item ID and
  review number; the completed state links directly to that official ARB review. A failed
  attempt never changes the displayed governance state or produces a success toast.
- Focused journey contract: 2 passed. Template syntax, design-token, and air-gap gates passed;
  the committed Tailwind build was checked byte-for-byte with the repository's pinned CLI.

## Next verified actions

1. Complete independent review, consolidated verification, deployment, and production checks
   for the governed-AI and Chief Architect release candidate.
2. Implement the single fail-closed, evidence-gated AI-to-ARB submission service and route all
   chat, workbench, and direct submission paths through it.
3. Write and review the Application Rationalisation Transformation Room design, including
   the programme/workstream/optional-solution model, before implementing it.
4. Add dedicated runners for live-model quality and official ArchiMate OEF XSD validation.
