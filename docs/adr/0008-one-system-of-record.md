# ADR 0008: One system of record per concept

Status: proposed (31 Aug 2026)

## Context

The owner, who is not technical, found each of these by clicking:

- `/capability-map/` reporting **Total Capabilities 191** above a table reading
  **Showing 1-10 of 0 results**
- the Capability Roadmap counting **173 gaps** beside a Gap Analysis screen
  reading **0**
- Application Domain cards that looked pressable and did nothing
- a dialog whose every field was labelled `Field`

Seventy-plus gates were green throughout. They were green because each measures
a mechanism, and none measures the condition the user actually experiences:
*does this screen agree with that screen?*

The measurements behind those symptoms:

| Question | Stores that answer it |
|---|---|
| what capabilities exist? | `business_capability` (461 rows), `capabilities` (0), `unified_capabilities` (0), `enterprise_capabilities`, `archimate_capabilities`, `technical_capabilities` |
| who are the users? | three routes registered at `/api/users` |
| what is an empty state? | two `empty_state` macros with incompatible signatures |
| where does a domain live? | seven domains exist in `app/<domain>/` **and** `app/modules/<domain>/` |
| what is a gap? | one table, two meanings, until `gap_kind` was added today |

These are not five bugs. They are five instances of one condition: **more than
one component claims authority over the same concept, and nothing reconciles
them.** A screen picks a store, and which store it picked determines the number
it shows. The user cannot tell which is right, and neither can the next agent.

`UnifiedCapability` is the sharpest case, because the correct architecture is
already there and simply switched off. It carries `source_table`, `source_id`,
`source_checksum`, `reference_capability_id`, `retired_into_id` and a hybrid
reference/tenant scoping model with partial unique indexes. It was designed
precisely as the canonical store the others project into. It has **no
producer** — nothing populates it, so production holds 461 business
capabilities and zero unified ones, and `/api/v1/capabilities` answers from the
empty table. The design was right; the projection was never written.

The obvious remedy — repoint the API at the store that has data — was the one I
proposed first, and it is wrong. It would have deleted a correct architecture to
paper over an unrun migration, and left six stores instead of five.

## Decision

**Every domain concept has exactly one authoritative store and one
authoritative accessor. A second store answering the same question is legal only
as a declared projection, and must carry provenance back to its source.**

Concretely:

1. **Name the system of record.** For capabilities it is
   `unified_capabilities`, because it is the only one that can express
   provenance and the shared-reference/tenant-owned distinction. Write the
   missing projection from `business_capability`, idempotent on
   `(source_table, source_id)`.
2. **A projection declares itself.** Any table holding a copy carries
   `source_table` / `source_id`, so "where did this row come from?" is
   answerable by query rather than by reading code.
3. **One accessor per concept.** Three routes at `/api/users` is a defect
   regardless of which one wins; the winner is decided by blueprint
   registration order, which no reader can see. Same for two macros sharing a
   name and an import path.
4. **Retire, do not accumulate.** `enterprise_capabilities` (1 reference),
   `archimate_capabilities` (1) and `capabilities` (0 rows) are retired into the
   canonical store with `retired_into_id` set, never dropped in place.

## Consequences

The rule is worthless unwritten in prose — this repository already documents
that a paragraph does not hold a line where a ratchet does. Enforcement:

- a **`canonical-store`** gate that fails when a new table, route rule or macro
  name duplicates an existing authority without declaring provenance
- a **`store-agreement`** gate that asks the *condition*, not the mechanism:
  for each concept with a canonical store, every surface answering that
  question returns the same count. This is the gate that would have caught
  191-vs-0 and 173-vs-0 on the day they appeared, and it is the one class of
  gate this estate has never had.

The second is the important one. Every existing gate reads source. The defects
the owner found are disagreements between running surfaces, and only a gate that
compares answers can see them.

## What this does not cover

Making the AI *maintain* the model is a separate decision, taken in
[ADR 0009](0009-continuous-model-maintenance.md).
This one only guarantees that when the model says something, there is exactly
one answer. That is a precondition for an AI architect, not a substitute for
one: an assistant reasoning over six stores that disagree will confidently
produce six different answers, and today it would have no way to know which is
right.
