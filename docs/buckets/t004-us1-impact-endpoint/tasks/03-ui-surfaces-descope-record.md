# T-004 / Task 03 — UI surfaces: descope record and T-004b entry conditions

**This is a decision record, not a build task. No builder handoff. Nothing in
this file is to be implemented as part of T-004.**

## Objective
Record, with evidence, that the three UI surfaces named in the parent brief
(Ask, Twin map, Provenance drawer) do not exist in this codebase; record the
decision to move them out of T-004 into a follow-up T-004b; and state exactly
what T-004 does and does not claim as a result, so a green T-004 is never read
as "US-1 is done".

## Context
The parent brief listed "UI surfaces for US-1 (Ask, Twin map, Provenance
drawer) calling API-1/API-2 per Screens & Surfaces, with derived edges distinct
on a non-colour channel and the hop-depth slider bound to `max_depth`" as a
deliverable, and explicitly asked tech-lead to confirm whether those screens
exist.

What the search found:

- `app/modules/intelligence/` has **no `templates/` directory at all**, and
  `register(app)` carries a comment reserving a UI blueprint slot for T-004
  that is still unused.
- No route, template or JS under `app/` implements an Ask surface, a twin map,
  or a derivation provenance drawer.
- The only adjacent artefact is `app/templates/components/provenance.html` — a
  set of badge macros (`measured` / `missing` / `ai` / `unavailable`) for
  marking where a *single value* came from. It is a genuinely useful primitive
  for rendering FR-15 reason codes later, but it knows nothing about
  derivation chains and is not a drawer.

So all three screens are greenfield. Each carries design decisions this repo
has no source for: what the Ask surface's question vocabulary is and how it
relates to the existing AI chat, how a twin map renders derived edges on a
non-colour channel, how a chain expands in a drawer. The Screens & Surfaces
spec those decisions come from lives in a repository that is not checked out
here.

## Constraints on the decision
- CLAUDE.md's three UI roles exist because a collapsed sidebar shipped with
  eight destinations behind one icon while seventy gates were green. Inventing
  three screens from one sentence of a brief is the same failure with more
  surface area.
- "Done means DEMONSTRATED" is not satisfied by T-004 and T-004 does not claim
  it is. T-004 ships the endpoint that T-004b will be demonstrated through.
- Descoping must not quietly drop acceptance criteria. Each one moved is named
  below with where its API half landed.

## Decision (taken, not proposed)
The UI is removed from T-004 and becomes **T-004b**, to be briefed after
`conversational-ux-designer` and the UI/interaction + information architect
questions have been asked against the actual Screens & Surfaces source.
T-004 ships backend only: query service, latency probe, metrics, US-1 route,
canonical-endpoint extension.

## Deliverable
This file. No code.

## Acceptance Criteria (of the descope itself)
1. No task in this bucket asks a builder to create a template, a UI blueprint,
   or front-end JS. Verified: tasks 01 and 02 contain none.
2. `app/modules/intelligence/__init__.py::register`'s reserved UI-blueprint
   slot remains unused and its comment is not edited to claim otherwise.
3. Every acceptance criterion moved out of T-004 is accounted for:
   - Parent item 6's Playwright "rendered screen shows the reason text" ->
     **T-004b**. Its API half (three distinct reason codes, no zeros) is task
     01 criterion 6 and task 02 criterion 5.
   - Parent item 7's "one-click run action" rendering -> **T-004b**. The
     `derivation_state` values it renders are task 01 criterion 7 and task 02
     criterion 5; the action it invokes is T-003's already-shipped
     `POST /api/v1/intelligence/derivation/recompute`.
   - Parent item 13 (eleven-persona authorisation matrix) **stays in T-004**,
     scoped to the new REST route (task 02 criterion 10). It expands to
     persona-visible pages in T-004b.
4. T-004's build report states in plain words that US-1 has no user-facing
   surface yet and that the feature is not claimed as demonstrated.

## Handoff Target
None — no builder. This file routes back to the orchestrator as input to a
future `T-004b` bucket, whose first role is `conversational-ux-designer` /
UI-architect, not `builder`.

## T-004b entry conditions
1. The Screens & Surfaces source for Ask, Twin map and Provenance drawer is
   available and read.
2. T-004 tasks 01 and 02 are `approved` and the API-1 payload contract is
   fixed — the UI is built against a settled contract, not concurrently with
   one.
3. A UI/interaction-architect pass has answered the non-default-state question
   for each screen (collapsed, narrow, empty, overflowing) and the
   information-architect question for where these live in navigation, before a
   builder brief exists.
4. The non-colour channel for derived edges is chosen and written down, not
   left to the builder.
