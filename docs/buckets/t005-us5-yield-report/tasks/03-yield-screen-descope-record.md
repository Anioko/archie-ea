# T-005 / Task 03 — "Yield & health" screen: descope record and T-005b entry conditions

**This is a decision record, not a build task. No builder handoff. Nothing in
this file is to be implemented as part of T-005.**

## Objective
Record, with evidence, that the "Yield & health" screen does not exist in this
codebase; record the decision to move it to a follow-up T-005b; and state
exactly what T-005 does and does not claim, so a green T-005 is never read as
"US-5 is done" or as "Release 1 is demonstrated".

## Context
The parent brief listed the "Yield & health" screen as a deliverable and — to
its credit — explicitly asked tech-lead to confirm whether it exists first,
citing T-004's identical situation.

What the search found:

- `app/modules/intelligence/` still has **no `templates/` directory and no
  `routes/ui.py`**. `register(app)` registers the invalidation listener and the
  API blueprint only; the UI-blueprint slot its docstring reserves is still
  unused, exactly as T-004's task 03 required.
- No template, route or front-end JS under `app/` renders a derivation yield,
  ratio, staleness or health report. The single grep hit for "yield" under
  `app/templates/` (`archimate_crud/partials/_repository_workspace.html`) is
  unrelated prose.
- The adjacent primitive noted by T-004 — `app/templates/components/
  provenance.html`, badge macros for `measured` / `missing` / `ai` /
  `unavailable` — remains the only nearby artefact. It marks where a single
  value came from; it is not a report screen.

So the screen is greenfield, and it carries design decisions this repo has no
source for: where it lives in navigation, what a p95 with an estate-wide scope
looks like next to per-tenant counts without misleading anyone, and which
non-colour channel carries staleness.

## Constraints on the decision
- CLAUDE.md's three UI roles exist because a collapsed sidebar shipped with
  eight destinations behind one icon while seventy gates were green. Inventing a
  metrics screen from one sentence of a brief is that failure again.
- This screen is unusually easy to get dishonest. Its payload mixes a per-tenant
  measurement with a process-local estate-wide p95 (verification note D4), a
  `null`-not-`0` not-computed state, and a `null` p95 with two different
  reasons. Every one of those is a place a chart renders a plausible zero. That
  is a design problem to solve deliberately, not a builder instruction.
- "Done means DEMONSTRATED" is **not** satisfied by T-005 and T-005 does not
  claim it is. T-005 ships the endpoint T-005b will be demonstrated through.
- Descoping must not quietly drop acceptance criteria. Each one moved is named
  below with where its API half landed.

## Decision (taken, not proposed)
The screen is removed from T-005 and becomes **T-005b**, to be briefed after the
UI/interaction-architect, information-architect and content-designer questions
have been asked against the actual Screens & Surfaces source. T-005 ships
backend only: the run record, the aggregates, the yield endpoint, the p95 read
and the Shape-B trigger.

T-005b should be briefed **together with T-004b** — they are the same module's
first two screens and will share navigation placement, empty-state language and
the non-colour channel for derived/stale. Briefing them separately is how two
answers to one question get built.

## Deliverable
This file. No code, no template, no UI blueprint, no front-end JS.

## Acceptance Criteria (of the descope itself)
1. No task in this bucket asks a builder to create a template, a UI blueprint or
   front-end JS. Verified: tasks 01 and 02 contain none.
2. `app/modules/intelligence/__init__.py::register`'s reserved UI-blueprint slot
   remains unused and its comment is not edited to claim otherwise.
3. Every acceptance criterion moved out of T-005 is accounted for:
   - Parent item 7 ("screen honesty": renders "derivation not yet computed" not
     zeros; shows p95 with sample count; staleness on a non-colour channel) →
     **T-005b**. Its API half is task 02 criteria 2, 3, 5 and 7 — the payload
     makes every one of those renderable honestly, and makes a zero
     unrepresentable on the not-computed branch.
   - Parent item 8's eleven-persona authorisation matrix **stays in T-005**,
     scoped to the new REST route (task 02 criterion 9). It expands to the
     persona-visible page in T-005b.
   - Parent items 1–6 and 9–11 are all API-side and stay in T-005.
4. T-005's build report states in plain words that US-5 has no user-facing
   surface yet, that the feature is not claimed as demonstrated, and that
   "Release 1 complete" means its API surface, not a demonstrated journey.

## Handoff Target
None — no builder. Routes back to the orchestrator as input to a future
**T-005b** bucket (to be briefed jointly with T-004b), whose first role is the
UI/interaction architect, not `builder`.

## T-005b entry conditions
1. The Screens & Surfaces source for "Yield & health" is available and read.
2. T-005 tasks 01 and 02 are `approved` and the yield payload contract is
   fixed — the screen is built against a settled contract, not concurrently
   with one.
3. A decision is written down, before a builder brief exists, for how the
   estate-wide process-local p95 is presented beside per-tenant counts without a
   reader mistaking one for the other. This is the single highest-risk honesty
   question on the screen.
4. The non-colour channel for staleness is chosen and written down, shared with
   T-004b's non-colour channel for derived edges rather than chosen twice.
5. Navigation placement and label are settled by the information architect
   ("could someone who has never seen this app find it twice?"), and the label
   fits its space (content designer), jointly with T-004b's surfaces.
