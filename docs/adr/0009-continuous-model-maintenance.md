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

## Addendum (17 Sep 2026) — the property-import convention this ADR did not define

DOGFOOD-004 (`docs/buckets/archiet-dogfood-import-fixes/`): a customer's OEF
import carried `status`/`source`/`as_of`-shaped `<properties>` on individual
elements and cited this ADR as the spec for how they should land. **They do
not land anywhere per this ADR** — the "model age" measure above (Consequences,
above) names no field, no key, and no store; it is a target metric, not a
schema. This addendum is the minimal convention actually implemented, so the
gap is closed in writing rather than left to be inferred from a docstring.

**ADR 0010 was already taken** (`0010-enterprise-genome.md`) by the time this
was written, so this lands as an addendum rather than a new numbered ADR —
flagged here for the solution-architect to renumber into a standalone ADR
later if a fuller property-governance decision (allow-lists, type coercion,
a real model-age job reading `archie:imported_at`) is ever made.

The convention:

1. Every `<property>` parsed from an OEF import is stored as a literal key in
   `ArchiMateElement.custom_properties` (`db.JSON`), keyed by the referenced
   `<propertyDefinition>`'s `<name>`, value as the string found in `<value>`.
   No key renaming, no type coercion, no allow-list. `status`, `source`,
   `as_of`, or any other customer-defined key get no privileged storage —
   they are ordinary JSON keys like any other.
   **Correction (17 Sep 2026, found while wiring export):** the normal
   runtime mapping (`app/models/models.py:274`) additionally carries
   `ArchiMateElement.properties` — a *different*, older `db.Text` JSON-string
   column already populated by other features (e.g. `annual_cost`, `owner`
   financial tagging). This is a second store for the same concept and is
   flagged, not resolved, here: `ArchimateOEFService.export_model()` now
   reads and merges both (`custom_properties` wins on a key collision) so
   neither an OEF import nor a pre-existing `properties` value is silently
   dropped on export, but the underlying duplication is unresolved and
   belongs in a follow-up ADR-0008 cleanup, not this one.
2. One namespaced key is reserved for provenance: `archie:imported_at` (ISO
   8601, UTC), written by `ArchiMateImportService.execute_import`. Namespacing
   prevents a collision with a customer property genuinely called
   `imported_at`, and gives a future model-age job (the metric this ADR's
   body actually asks for) something to read.
3. **Round-trip rule.** `ArchiMateOEFService.export_model()` writes every
   `custom_properties` key back to `<propertyDefinitions>`/`<properties>`
   **except** the `archie:` namespace, so re-importing an exported file
   reproduces byte-identical `custom_properties` for the customer's own keys.
4. **Known collision, not resolved here:** a separate feature
   (`GET/PUT /architecture/api/elements/<id>/properties`, CMP-043) already
   stores user-entered "Properties" (tagged values) under a reserved
   `custom_properties["tags"]` sub-object, specifically so a generic
   properties editor cannot clobber `data_classification`/`contains_pii`/
   `lifecycle_history`. This import convention writes literal top-level keys,
   which is a *different* sub-space of the same JSON blob and does not
   collide with `"tags"` — but if a customer's OEF property is ever named
   `tags`, `data_classification`, `contains_pii`, or `lifecycle_history`
   itself, the import will silently occupy a reserved key. Out of scope for
   this task; flagged for the next property-governance pass rather than
   silently left undocumented.
