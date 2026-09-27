# Roadmap: from "novel capability on a maturing platform" to best-in-class

Written 1 Sep 2026, grounded in the defects this session actually found and the
gates/ADRs it actually built. The honest starting point: the platform had ~12
demo-path blockers and ~50 lesser defects behind 81 green gates, and needed a
frantic pre-demo fix marathon. This plan makes that state unrepeatable.

## The root cause (fix this or the rest is whack-a-mole)

"Done" meant **green + deployed**, not **demonstrated**. Agents optimise the
stated bar, so the estate filled with software that passes checks but does not
work when clicked: an ARB decision API with no button, a mapping endpoint with a
dead Save, `unified_capabilities` wired into eight APIs with nothing writing to
it. Every one of the 81 gates read SOURCE; not one clicked a button. The owner
became the QA function by accident. **Everything below serves changing that.**

## Phase 0 — Redefine "done" (CTO / delivery lead + QA lead) — DONE 1 Sep

CLAUDE.md now says done = a persona completed the real journey in the rendered
UI, clicked, persisted, seen. Mechanical enforcement:
- A write feature does not merge without a browser test that clicks its real
  control and asserts the result persisted after reload.
**Exit gate:** CI blocks a merge that adds a route without a passing browser
journey. Measurable, not cultural.

## Phase 1 — Make the invisible visible (QA lead — the reality-gate category)

81 gates were green over a broken UI because they read source. Build the gates
that read RENDERED REALITY (several already exist this session):
- `store-agreement` (built) — two surfaces answering one question differently.
- `canonical-route` (built) — duplicate accessors decided by registration order.
- interaction census — dead controls found in the live DOM, not a known pattern.
- per-persona browser smoke — clicks every modal/form, asserts persistence.
**Exit gate:** one tracked number — "demo-path defects found by clicking" —
ratcheted downward. Owner never finds a defect the build did not.

## Phase 2 — Pay down the catalogued debt (all architects, by area)

The ~50 majors are already enumerated in the four QA reports. Work them by area
with fix → verify-in-browser → prod-verify. Named now:
- Security genome slice: seed-idempotency bug (`uq_framework_control`) — bounded.
- AI Guide gives navigation help, not grounded answers (deferred, scoped w/ lines).
- traceability/data-architecture store disagreements (partially fixed).
**Exit gate:** each area's browser journey green; each fix demonstrated, not
asserted. No `docs/known-issues/` parking-lot entries (a documented defect is a
decision to leave it broken — this repo's own rule).

## Phase 3 — Kill the defect CLASSES, not instances (data + software architect)

The recurring shapes, each an ADR:
- Stores with no producer / duplicate authority → [ADR 0008] one system of
  record per concept, enforced by `store-agreement`.
- CSP-dead inline handlers → the `inline-handlers` gate @ 0 (built) + data-*
  delegation as the only pattern.
- Schema drift breaking prod → [ADR 0002] Alembic baseline + `db upgrade` on
  deploy (today `reconcile-schema` is nullable-add-only and drift 500s prod).
**Exit gate:** `store-agreement` and `canonical-route` at 0; no manual
`reconcile-schema` firefighting on a deploy.

## Phase 4 — Turn the differentiator into the product (AI / solution architect)

The Enterprise Genome ([ADR 0010]) is the genuinely novel, verifiable thing —
deterministic, provenance-carrying, model-derived artifacts. Make it the spine:
- The AI **reasons over and emits the genome**, schema-validated, not free text.
  That is how "the AI assists" becomes "the AI architects, human-governed" — the
  output is governable by construction. The LLM proposes genome patches through
  the approve gate; emitters stay deterministic (`llm-boundary` gate @ 0, built).
- The maintenance loop ([ADR 0009]) — drift = diff the genome against observed
  reality, per domain, on the tenant-safe scheduler harness (built, tenant-safe).
- The remaining domains (data, security, technology, motivation, implementation)
  behind the same deterministic emitter, each with the first-ever-style test.
**Exit gate:** the AI produces genome-shaped, provenance-traced output across ≥3
domains, each prod-verified by clicking — and the genome is the shared context
all AI surfaces read, replacing the relevance-scoped slice they read today.

## Phase 5 — Prove best-in-class externally (data/evidence analyst + product)

Best-in-class is not self-declared. Make the four verifiable genome properties —
determinism (spec_hash), traceability (element ids in the DOM), no-fabrication
(zero-LLM emit), single-source — reproducible by a third party on a real
dataset, and publish **model age** ([ADR 0009]): time since each element was
last confirmed against a source. No incumbent reports that.
**Exit gate:** an outside architect runs the four checks against Archie and
against a named incumbent, and the difference is demonstrable, not asserted.

## Role → phase map (per CLAUDE.md; a role is its family of gates)

| Role | Owns |
|---|---|
| CTO / delivery lead | Phase 0 (the "done" bar); sequencing; ship discipline |
| QA lead | Phase 1 reality gates; the per-persona browser smoke |
| Software / technical architect | Phase 2 wiring; Phase 3 classes; Phase 4 emitters |
| Data architect | Phase 3 one-system-of-record; genome schema/provenance |
| AI / ML architect | Phase 4 genome-as-substrate; governed AI writes |
| Security architect | tenant-safe scheduler; genome security slice |
| UI / interaction + information + content architect | Phase 1 rendered-legibility; the visual rubric |
| Data / evidence analyst | Phase 5 benchmarks; store-agreement measurements |
| Product architect | Phase 4/5 which domains, which artifacts, the sale |

## The one measure that means it worked

The owner stops finding defects by clicking. When the build finds what the owner
used to find — because "done" means demonstrated and the reality gates enforce
it — the platform is best-in-class on the axis that actually failed here:
trustworthy, verifiable software. The genome is the differentiator; this
discipline is what lets you claim it without being caught out.
