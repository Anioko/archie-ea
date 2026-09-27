# Architecture Journeys wave — implementation plan

## What is already true (verified, not assumed)

The premise "replace the weak standalone Business Architecture experience with an
Architecture Journey product" is **half-done already**, and the finished half is
good. Building a second journey product would duplicate a system of record.

- `ArchitectureJourney` (`app/models/architecture_journey.py:49`) is the spine and
  is correctly shaped: eight `ARCHITECTURE_LAYERS` including `governance`, seven
  `JOURNEY_INTENTS`, `OUTCOME_TYPES` including `architecture_only` and
  `no_change_recommended`, stages frame/discover/shape/decide/deliver. Tenant-scoped,
  optimistically locked, four CHECK constraints.
- `/business-architecture/` **already 301s** to
  `/architecture-journey/?intent=business-transformation`, and
  `tests/test_architecture_journey_generalisation.py:29` pins it.
- A hub and a workspace template exist and render.

## The actual gap

The journey has **two typed edges — `solution_id` and `programme_id` — and nothing
else**. Everything else in the repo is keyed on `solution_id`. So a journey whose
outcome is `architecture_only` cannot own an element, a document, a decision, a risk
or a participant.

That gap is exactly the brief's requirement list. The journey home must show
purpose, stage, progress, **participants, evidence, decisions, risks** and next
action; today the workspace shows purpose, stage, progress, scope, deliverables and
a free-text evidence list.

Measured against the brief:

| Required on the journey home | Today |
|---|---|
| Purpose | present (intent) |
| Current stage + progress | present |
| Next action | partial — stage guidance only |
| Participants | **absent** — one `owner_id`, no membership |
| Evidence | free-text JSON strings, not links to real records |
| Decisions | **absent** |
| Risks | **absent** |
| Governance / ARB | **absent** |
| Programme link | column exists, never surfaced |

## Design decisions

**1. One link table, not a dozen FK columns.** The alternative was
`architecture_journey_id` on `risks`, `architecture_decision_records`,
`work_packages`, `plateaus`, `gaps`, `strategic_roadmap_items`, `decision_briefs`,
`arb_review_items` … Eleven nullable columns across eleven tables, each needing its
own migration, backfill story and query. A single association table
(`architecture_journey_links`) expresses the same edges, adds one table that
`init-db` creates, and keeps every system of record untouched — which is the point:
the journey **references** records, it does not own or copy them.

**2. Participants get a real table** (`architecture_journey_members`), mirroring
`ProgrammeRoleAssignment`. A JSON blob of names would be fabricated data the moment
a user is deleted or renamed.

**3. Evidence stays where it is for now.** `evidence_records` demands NOT NULL
`programme_id`/`workstream_id`/`candidate_id`, so a journey genuinely cannot write
one. Rather than loosen a governed table under deadline, journey evidence is
expressed as links to records that already exist, and the free-text manifest stays
as the fallback it already is — labelled as such in the UI so nobody mistakes a
typed-in string for a governed evidence record.

**4. No new intents this wave.** The brief names business transformation,
operating-model change, technology transformation, regulatory response and
continuous improvement. Four of the five already map onto existing intents
(`business_transformation`, `operating_model`, `risk_and_compliance`,
`portfolio_change`). Adding `technology_transformation` and
`continuous_improvement` means editing a CHECK constraint, which `reconcile-schema`
will not do — it is ADD-COLUMN only. That is a real migration and it is recorded
here rather than half-done.

**5. Never fabricate a count.** Every number on the journey home is either a real
count from a real query or `None`, rendered as an em dash. A journey with no linked
decisions shows "—", not "0", because a zero that means "not computed" is
indistinguishable from a measured zero.

## Sequence

1. `architecture_journey_links` + `architecture_journey_members` models, tenant-scoped.
2. A read model returning the home view, with `None` for anything not computed.
3. The journey home template on `page_shell` (single `<h1>`, one breadcrumb).
4. Route wiring, permission and error states.
5. Behavioural tests + a Playwright journey.
6. Gates.
