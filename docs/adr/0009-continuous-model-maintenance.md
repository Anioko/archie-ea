# ADR 0009: The labour to replace is maintenance, not modelling

Status: proposed (31 Aug 2026)

## Context

The owner's goal, stated 31 Aug 2026: Archie should do what a human ArchiMate
3.2 practitioner does, so that architecture is not exclusive to organisations
that can afford a team of architects.

Work to date has read that as a *modelling* problem, and by that reading it is
nearly solved. As of today the assistant can create all 58 ArchiMate element
types with tools that carry each type's definition, when to use it and what it
is confused with, and it validates relationships against the metamodel matrix
rather than emitting whatever it is asked for.

That reading is wrong, and it is worth being precise about why.

**Modelling is a one-off cost. Maintenance is the recurring one, and it is the
recurring one that makes architecture expensive.** A model is accurate the week
it is built. Then an application is decommissioned, a vendor is replaced, a team
reorganises, an integration is rerouted — and within a quarter the model
describes an estate that no longer exists. Every enterprise-architecture tool
ever sold has been accurate on day one. What organisations actually pay
architects for, year after year, is to keep the thing true.

So the labour that makes architecture exclusive is not "draw the diagram". It is
"notice that reality moved, and move the model with it". That is the job to
automate.

Measured today: `app/services/archimate_backbone_audit.py` and
`archimate_validity_service.py` exist and can assess the model, and **nothing
invokes them on a cadence**. Drift is detectable and never detected.

A correction, recorded because the first draft of this ADR asserted the
opposite and was wrong: this codebase **does** already run a scheduler.
`app/__init__.py:54` calls `init_scheduler()`
(`app/_bootstrap/extensions.py:224`), which starts an APScheduler carrying five
jobs — EA workflow schedules every five minutes, two Monday digests, and a
Teams renewal every twelve hours. The claim of "zero scheduled jobs" came from
a grep too narrow to match the actual call shape, and a null result was read as
evidence of absence.

That correction makes this ADR more urgent rather than less. Those jobs run
under `with app.app_context()` and not a request context, so
`has_request_context()` is false and **no tenant predicate is applied to
anything they touch**. One of them, `run_due_schedules`
(`app/services/ea_workflow_engine.py:4291`), handles this correctly and
deliberately — it passes `organization_id=schedule.organization_id` explicitly,
with a comment naming the hazard. But it never clears the session between
schedules, so the identity-map exposure survives across iterations of its loop:
`Session.get()` on a hit returns the cached object without emitting SQL, and
therefore without the filter.

So the harness below is not new infrastructure. It is remediation of five jobs
already running in production, and the first job this ADR proposes must not be
added until the four existing ones are migrated onto it.

## Decision

Treat the model as a **continuously reconciled projection of observed
reality**, not as a document users maintain by hand.

Three loops, in dependency order:

1. **Observe.** Sources that already exist — the application portfolio,
   integrations, imports, vendor records — are the ground truth for what the
   estate contains. Reconcile the ArchiMate model against them on a schedule and
   record each difference as a typed finding, not a log line.
2. **Propose.** Every difference becomes a proposed change with its evidence
   attached: *this application has had no owner and no traffic for two quarters;
   propose Plateau transition to decommissioned.* The assistant drafts the
   change; it does not silently apply it. This is the existing approval choke
   point, used for maintenance rather than only for creation.
3. **Govern.** Material proposals enter the ARB workflow that already exists,
   with the state machine fixed today. An architecture that changes itself
   without a decision record is not governed, and governance is the part
   enterprises cannot skip.

## Consequences

- The AI's value shifts from *authoring* to *noticing*, which is where the
  recurring human cost actually is.
- It requires [ADR 0008](0008-one-system-of-record.md) first. An assistant reconciling six capability stores
  that disagree will confidently produce six different answers and have no way
  to know which is right. One system of record is a precondition, not a
  parallel workstream.
- It needs a scheduler, which this codebase does not currently have, and any
  job it runs is outside a request context — so per CLAUDE.md it carries **no
  tenant filter**. Every reconciliation loop must scope `organization_id`
  explicitly and clear the session between tenants. This is the single most
  likely way to introduce a cross-tenant leak into a product that currently has
  none.
- The measurement of success is not "elements created". It is **model age**:
  the distribution of time since each element was last confirmed against a
  source. That number is publishable, it is what a buyer should ask about, and
  no EA tool reports it today.

## What this is not

It is not autonomy. The proposal-and-govern shape is deliberate: an AI that
edits the system of record without a decision record reproduces the failure this
product exists to fix, which is an architecture nobody can trace back to a
reason.
