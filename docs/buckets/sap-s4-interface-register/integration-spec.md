# Integration Spec: SAP S/4HANA Interface Register

Bucket: `sap-s4-interface-register`
Author: integration-architect
Source: `docs/buckets/sap-s4-interface-register/brief.md`,
`docs/buckets/sap-s4-interface-register/srs.md`
Scope: the integration/ArchiMate-sync/API-contract layer only. Screens, routes,
module placement and the register's list/edit UI are `solution-architect`'s
concern in parallel; `tech-lead` reconciles.

## 0. Correction to the SRS grounding notes — read this first

The SRS's Assumption A3 states *"there is no separate `ApplicationInterface`
ORM class in this codebase."* **That is not true**, and it changes the create
contract, so it is corrected here rather than silently worked around:

`app/models/application_layer.py:42` defines a full `ApplicationInterface`
model — `TenantMixin`, its own table (`application_interfaces`), ~40 columns
including `interface_type`, `protocol`, `data_format`, `message_pattern`,
`authentication_method`, `consumer_count` — **and it already has a
`before_insert` listener (`application_layer.py:618`,
`create_interface_archimate_element`) that auto-creates a matching
`ArchiMateElement(type='ApplicationInterface')` the moment a row is
inserted with `archimate_element_id is None`.** This is the exact mechanism
root CLAUDE.md calls `_sync_archimate_element()` for motivation entities —
there is no function literally named that for `ApplicationInterface`; this
`before_insert` listener is its real equivalent, and it already exists,
wired, and working (same pattern as `ApplicationEvent`, `ApplicationService`,
`ApplicationCollaboration`, `ApplicationFunction`, `ApplicationProcess`,
`ApplicationInteraction`, `DataObject` — all in the same file).

This means the codebase now has **three** things that can answer "what is
this interface":

1. `ApplicationInterface` (`application_layer.py`) — rich, TenantMixin,
   auto-syncs its own `ArchiMateElement`.
2. `ArchiMateElement` (`type='ApplicationInterface'`) — the backbone row,
   the actual ArchiMate element.
3. `ApplicationInterfaceMetadata` (`integration_metadata.py`) — a *second*
   1:1 extension of `ArchiMateElement`, **not** `TenantMixin`, no
   `organization_id` column at all, columns that substantially overlap (1):
   `interface_type`, `protocol`, `data_format`, `message_pattern`,
   `authentication_method`, `business_criticality` (~`consumer_count`).

The brief is explicit that `ApplicationInterfaceMetadata` "stays the only
store for interface technical detail" and is the one surface already reading
it (`archimate_routes.py:2627`). Per ADR-0008 ("one system of record"), this
feature **must not write to both (1) and (3)** — that recreates exactly the
six-capability-store defect CLAUDE.md names as the standing failure mode.

**Decision (integration architect, made here rather than deferred):**
`ApplicationInterface` (`application_layer.py`) is **not written by this
feature**. Its `before_insert` listener is not invoked. The write path
creates the `ArchiMateElement` directly — same pattern as
`StrategicService._sync_archimate_element()` in
`app/modules/solutions_strategic/v2/services/strategic_service.py:37`, a
small explicit helper, not a model insert that happens to trigger a listener
— and attaches `ApplicationInterfaceMetadata` to it. `ApplicationInterface`
the table is flagged as a pre-existing ADR-0008 duplicate outside this
bucket's authority to retire; `tech-lead`/`solution-architect` should decide
whether it gets a `retired_into_id` pointer to `ApplicationInterfaceMetadata`
in a later bucket. Not doing this — i.e. creating `ApplicationInterface` rows
for convenience because the auto-sync is already wired — is the single
highest-value mistake this spec exists to prevent; it would pass every gate
(`fabricated-data`, `store-agreement` measures *answers*, and both stores
would independently "answer" with real, non-fabricated, disagreeing data)
while quietly recreating the six-capability-store defect on day one.

## 1. Create-time contract: ArchiMateElement vs ApplicationInterfaceMetadata

### 1.1 Field split

| Field | Lives on | Why |
|---|---|---|
| `name`, `description`, `type='ApplicationInterface'`, `layer='Application'`, `organization_id`, `scope='enterprise'` | `ArchiMateElement` | the element *is* the interface, per CLAUDE.md |
| `interface_type`, `protocol`, `data_format`, `message_pattern`, `is_synchronous`, `authentication_method`, `business_criticality`, `transaction_volume_daily`, `operational_status`, `retirement_date`, everything else in `ApplicationInterfaceMetadata` | `ApplicationInterfaceMetadata` | technical/operational detail, per the brief's system-of-record constraint |
| source/target system links | `SystemDependency` (×2 rows) | reuses the existing junction, per brief |

Do not put `protocol`/`interface_type`/etc. into `ArchiMateElement.custom_properties`
as a shortcut — that would create a *fourth* place these fields could live,
and none of the existing read paths (`archimate_routes.py:2627`) look there.

### 1.2 The sync helper (adapting the motivation-entity pattern)

No existing helper does exactly this for `ApplicationInterface`; adapt
`StrategicService._sync_archimate_element()`'s shape (session-scoped,
flush-not-commit, returns the element) rather than the `ApplicationInterface`
model's `before_insert` listener (rejected in §0). Builder should add this to
whichever service module owns the new write route (solution-architect's
placement decision), not to `application_layer.py` (that file's listener is
for a different, unused-by-this-feature table) and not to
`archimate_backbone.py` (that module's naming — `_sync_archimate_element` —
does not actually exist there today; do not invent an import of a symbol
that isn't defined).

```python
def _sync_interface_archimate_element(session, *, organization_id, name, description):
    """Create the canonical ArchiMateElement for a new interface.

    Mirrors StrategicService._sync_archimate_element's shape: session-scoped,
    flushes (not commits) so it participates in the caller's transaction,
    returns the element for the caller to link. Does NOT go through
    ApplicationInterface's before_insert listener (see integration-spec §0).
    """
    from app.models.archimate_core import ArchiMateElement

    element = ArchiMateElement(
        organization_id=organization_id,
        name=name,
        type="ApplicationInterface",
        layer="Application",
        description=description or "",
        scope="enterprise",
    )
    session.add(element)
    session.flush()  # need element.id before the metadata/dependency rows
    return element
```

### 1.3 Full create transaction (US-2)

All of the following must be **one** `db.session` transaction, committed once,
not four independent commits:

1. `_sync_interface_archimate_element(...)` → flush → `element.id`.
2. `ApplicationInterfaceMetadata(archimate_element_id=element.id, **tech_fields)`.
3. `SystemDependency(source_system_id=source_component.archimate_element_id, target_system_id=element.id, interface_id=element.id, dependency_type='service')`.
4. `SystemDependency(source_system_id=element.id, target_system_id=target_component.archimate_element_id, interface_id=element.id, dependency_type='service')`.
5. The two `ArchiMateRelationship` rows from §3.
6. `db.session.commit()` once.

**Failure modes — every one of these must reach the user as a rejected
create, not a partial row:**

- **DB rejects the flush at step 1** (connection lost, constraint violation):
  nothing has committed yet; return the caught exception as a 4xx/5xx inline
  form error. No orphan `ArchiMateElement` exists because nothing was
  committed — this is why step 1 uses `flush()`, not `commit()`.
- **`ApplicationComponent` picker resolves to a component with no
  `archimate_element_id`** (a small number of legacy `ApplicationComponent`
  rows predate the backbone sync and have none — this is the same class of
  gap the ADR-0008 note documents for capabilities): reject the create with
  an explicit "this application has no ArchiMate element yet" error, not a
  `SystemDependency` row pointing `source_system_id` at `NULL` (the column is
  `nullable=False` so the DB would reject it anyway — catch that
  `IntegrityError` and surface it as the real cause, not a generic 500).
- **Two concurrent creates for the same name**: `ArchiMateElement.name` is
  not unique, so both succeed — this is an accepted, pre-existing platform
  behaviour (duplicate names are common across the backbone already), not a
  new failure this feature introduces or needs to solve.
- **`ApplicationInterfaceMetadata` insert fails after the element flushed**
  (e.g. `business_criticality` value outside expected set — the column has
  no DB-level check constraint, but a service-layer validator should reject
  out-of-set values before flush): whole transaction rolls back, including
  the already-flushed `ArchiMateElement` — Postgres rolls back a flush that
  hasn't committed, so no orphan element survives. **US-1 AC3's "element with
  no metadata is a valid row" is about a pre-existing element edited later
  (US-3), never about a failed create** — a failed create must not leave a
  half-formed row for AC3 to paper over.

## 2. Tenant scoping — the two models in this contract that are NOT `TenantMixin`

Flagged explicitly because CLAUDE.md's `tenant-scoping` gate (ratchet @ 0)
catches exactly this shape, and both of the following are load-bearing for
this feature:

- **`ApplicationInterfaceMetadata` has no `organization_id` column and is not
  `TenantMixin`.** It is only reachable inside a tenant boundary by **always
  joining through `ArchiMateElement`** (which is `TenantMixin` and gets the
  `do_orm_execute` filter). US-1's list query must be
  `ApplicationInterfaceMetadata.query.join(ArchiMateElement, ...)`, never
  `ApplicationInterfaceMetadata.query.filter(ApplicationInterfaceMetadata.archimate_element_id.in_(...))`
  fed by an un-scoped id list computed earlier in the request — that id list
  itself must have come from a tenant-filtered `ArchiMateElement` query, or
  the join adds nothing.
- **`SystemDependency` has no `organization_id` column and is not
  `TenantMixin`** either. Same rule: any query over `SystemDependency` for
  this feature (e.g. "what does this interface connect") must join to
  `ArchiMateElement` on `source_system_id`/`target_system_id`/`interface_id`
  and rely on that join's `TenantMixin` filter, not filter `SystemDependency`
  directly.
- **Outside a request context (a future bulk-import CLI path, §4.3)** neither
  model's write path is tenant-filtered at all — `organization_id` must be
  passed explicitly into `_sync_interface_archimate_element` and never
  inferred from `g.current_org_id`, which will not exist there.

## 3. `Gap.gap_kind` / `gap_type` classification

### 3.1 Correction to the SRS — `validate_gap_kind()` is not currently called anywhere

The SRS states the plateau-pair enforcement is *"already enforced in code
today, not just by convention"* via `validate_gap_kind()`
(`implementation_migration.py:550`). **`validate_gap_kind` is defined and
exported but has zero callers in the codebase** (confirmed by exhaustive
grep — it appears only in its own definition and in this bucket's SRS text).
It is not a SQLAlchemy `@validates` decorator and there is no
`before_insert`/`before_flush` listener registered for `Gap` anywhere. It is,
today, exactly the "store with no producer" pattern applied to a validator:
correctly written, never wired. This is a materially different starting
point than the SRS's "enforced today" — the enforcement this feature needs
does not yet exist and must be added, not merely relied upon.

**Contract:** the new gap-creation write path (US-5) must call
`validate_gap_kind(gap)` explicitly, after constructing the `Gap` object and
before `db.session.add()`/`commit()`, and must let `ValueError` propagate to
a caught 400 response with the raised message as the inline form error — not
swallow it into a generic "something went wrong," and not catch-and-retry
with defaulted plateau ids (that would recreate the exact ambiguity the
function exists to prevent). Recommend, but out of this bucket's write scope
to force: `tech-lead` should consider registering `validate_gap_kind` as a
real `before_insert`/`before_update` SQLAlchemy listener on `Gap` in a
follow-up, so every future caller gets the invariant for free instead of
each route needing to remember to call it.

### 3.2 `gap_kind` and `gap_type` values

Every interface gap raised by this feature:

- `gap_kind = 'plateau_transition'` (never `'capability_shortfall'`, the
  existing default — an interface gap is a difference between two plateaus
  by definition here, not a capability weakness).
- `originating_plateau_id` = the "Current Integration Landscape" plateau,
  `target_plateau_id` = the "S/4HANA-Integrated Landscape" plateau (US-4).
- `gap_type` ∈ `{'protocol_change', 'new_interface', 'retirement'}` — plain
  strings in the existing `String(30)` column, per SRS Assumption A2. No
  schema change.
- `archimate_element_id` = the interface's `ArchiMateElement.id` — use the
  `Gap.archimate_element_id` single FK column for "which interface does this
  gap concern," **not** the `gap_archimate_elements` many-to-many junction.
  The junction exists for gaps touching multiple elements at once (not this
  feature's case — each interface gap concerns exactly one interface); using
  the simpler FK avoids a second write path answering the same "which
  interface" question for no benefit.

### 3.3 Failure modes

- **Missing plateau id**: rejected server-side by `validate_gap_kind()`
  (once wired per §3.1) with a 400 and the exact reason string; client-side
  validation is a UX nicety, not the enforcement boundary.
- **`gap_type` outside the three literals**: not enforced by any DB
  constraint (the column has none) — the write route must validate against
  an explicit allow-list before insert, same reasoning as `business_criticality`
  in §1.3, or a bulk-import row (§4) with a typo silently creates a
  fourth, unrecognised `gap_type` that the UI's dropdown never shows and
  the rollup (§5) never explains.
- **Plateau pair not yet provisioned for the initiative (US-4 AC4)**: the
  gap-creation route must reject with "set up the As-Is/To-Be comparison
  first," not auto-create the pair as a side effect of a gap POST — GET
  must stay side-effect-free per US-4 AC4, and neither should this POST
  silently provision infrastructure the user didn't ask for from this screen.

## 4. Relationship wiring — real `ArchiMateRelationship` rows

`app/models/relationship_tables.py` holds domain-specific junction tables
(RACI, CRUD, vendor mappings) — **it is not the mechanism for ArchiMate
relationships between backbone elements.** The correct mechanism is
`ArchiMateRelationship` (`app/models/archimate_core.py:110` /
`app/models/models.py:468` — two definitions of the same table, selected by
which module loads first; both `source_id`/`target_id`/`type` against
`archimate_elements.id`). This is the same table the existing read-only code
at `archimate_routes.py:2605` already queries (`type="realization"`) to find
linked Requirements — confirming lowercase string `type` values are the
convention already in use, not the `ArchiMateRelationshipType` enum's
title-case values (`archimate_validation_engine.py`) which is a separate,
validation-only vocabulary.

### 4.1 Relationship types (ArchiMate 3.2 Application layer metamodel)

For each interface, two relationships are created (a third, conditional, for
the service it exposes):

1. **Providing `ApplicationComponent` → `ApplicationInterface`: Composition**
   (`type="composition"`, `source_id=provider_component.archimate_element_id`,
   `target_id=interface_element.id`). An Application Interface is structurally
   part of the component that exposes it — this is the standard ArchiMate 3.2
   reading, and matches the metamodel restriction (Composition is valid from
   Application Component to Application Interface; Assignment is not, since
   Assignment is reserved for active structure → behavior).
2. **`ApplicationInterface` → consuming `ApplicationComponent`: Serving**
   (`type="serving"`, `source_id=interface_element.id`,
   `target_id=consumer_component.archimate_element_id`). The interface serves
   (gives access to) the consuming component — this is the direction
   `SystemDependency`'s own docstring already describes (`source_system →
   target_system`, with `interface_id` "if applicable"), so the
   `ArchiMateRelationship` row and the `SystemDependency` row agree on
   direction; they must, or `store-agreement`-style reasoning about "what
   connects to what" disagrees depending which table answered.
3. **`ApplicationInterface` → `ApplicationService` it exposes: Realization**
   (`type="realization"`, `source_id=interface_element.id`,
   `target_id=service_element.id`) — **only created when an
   `ApplicationService` element for the exposed S/4HANA capability already
   exists** for the provider component (a known, pre-existing
   `ArchiMateElement(type='ApplicationService')`). This is conditional, not
   mandatory per interface: not every one of the ~18 interfaces necessarily
   has a modelled `ApplicationService` counterpart yet, and this feature must
   not fabricate one to satisfy a "must always create three relationships"
   rule — an interface with two relationships (composition + serving) and no
   service link is a valid, incomplete register entry, same reasoning as
   US-1 AC3 for missing metadata.

### 4.2 Failure modes

- **`provider_component`/`consumer_component` has no `archimate_element_id`**:
  same failure as §1.3 — reject the whole create, do not write a
  relationship with a `NULL` `source_id`/`target_id` (both FK columns allow
  NULL at the DB level, which is exactly the trap: a `NULL`-sourced
  relationship silently exists and never resolves to anything when read back,
  which is a `silent-data`-gate-shaped defect — a write that "succeeds" but
  produces an unusable row).
- **Duplicate relationship on re-edit** (US-3 editing an existing interface
  and its source/target systems change): the edit path must delete the two
  stale `ArchiMateRelationship` rows (matched by `source_id`/`target_id`/
  `type` triple) before inserting the new pair, not accumulate old
  relationships alongside new ones — an interface that used to connect App A
  to S/4HANA and now connects App B must not still show a live composition
  edge to App A on the diagram/element-detail page.
- **`ArchiMateRelationship` write succeeds but the corresponding
  `SystemDependency` write in the same transaction fails** (or vice versa):
  because both are in the single transaction from §1.3, a rollback takes
  both down together — this is precisely why they are not two independent
  commits. Two independent commits here would be the two-parallel-writes
  failure mode CLAUDE.md's role list calls out generally ("does it belong in
  `app/modules/`… is there now one way to do this thing, or two").

## 5. Bulk-create / import API contract (~18 interfaces onboarding)

One-by-one form entry for 18 interfaces is explicitly out of scope per the
brief's intent (an SAP programme onboarding a fixed interface list). This is
an API contract, not a UI concern — solution-architect owns whether it's
exposed as a bulk form, CSV upload, or both; this section defines what the
underlying write path guarantees regardless of which UI calls it.

### 5.1 Contract

`POST /integration/api/interface-register/bulk` (path prefix is
solution-architect's to finalise; this is the payload/response contract)

Request:
```json
{
  "initiative_id": 42,
  "interfaces": [
    {
      "name": "Customer Master Sync",
      "description": "...",
      "interface_type": "REST",
      "protocol": "HTTPS",
      "data_format": "JSON",
      "message_pattern": "Request-Response",
      "is_synchronous": true,
      "authentication_method": "OAuth2",
      "business_criticality": "Critical",
      "transaction_volume_daily": 15000,
      "source_application_component_id": 101,
      "target_application_component_id": 202,
      "gap_type": "new_interface"
    }
  ]
}
```

Response — **per-row status, never a bare `200` covering a mixed batch**
(this is the `error-signalling`/`silent-data` gates applied to a batch
shape):

```json
{
  "created": 16,
  "failed": 2,
  "results": [
    {"index": 0, "status": "created", "archimate_element_id": 9101, "interface_metadata_id": 55},
    {"index": 7, "status": "error", "reason": "source_application_component_id 999 has no archimate_element_id"}
  ]
}
```

### 5.2 Transaction shape and failure modes

- **Each interface row is its own transaction** (§1.3's full create
  sequence, `commit()`'d individually) — **not** one all-or-nothing batch
  transaction. Rationale: 18 rows from an SAP integration catalogue realistically
  arrive with a handful of bad component references (typo'd IDs, an app not
  yet onboarded to the portfolio); an all-or-nothing batch would let one bad
  row block the other 17 valid ones, which is worse for a programme trying
  to get its register populated than a partial success clearly reported. If
  `tech-lead`/product disagree and want strict all-or-nothing, that is a
  one-line change (wrap the loop in a single session instead of committing
  per row) — flagged as a decision made here, reversible.
- **A row that fails must never be silently dropped from the count.**
  `created` + `failed` must always equal `len(interfaces)`; a bulk endpoint
  that returns `{"created": 16}` with no accounting for the other 2 is the
  exact `fabricated-data`/`silent-data` shape CLAUDE.md names — the caller
  cannot tell "16 succeeded, rest ignored" from "16 succeeded, 2 explicitly
  rejected for a stated reason."
- **Idempotency / re-run of the same batch**: `ArchiMateElement.name` is not
  unique (§1.3), so re-POSTing the same batch creates 18 more interfaces, not
  an update. If the onboarding UI needs re-run safety (e.g. a CSV re-upload
  after fixing two bad rows), the caller must pass a natural key (e.g.
  `name` + `initiative_id`) and the route must upsert-by-lookup rather than
  blind-insert — call this out explicitly to solution-architect as a UI-path
  decision this contract does not make for them, since it changes the
  request/response shape (would need an `existing_archimate_element_id` in
  the request to distinguish "create" from "update" rows).
- **Whole-batch failure modes** (bad `initiative_id`, caller not
  authorised for the initiative's org): reject the entire batch before
  processing any row with a 4xx and no `results` array — do not process 5
  rows against an initiative the caller cannot prove they own and then
  discover the auth problem on row 6.
- **Partial network failure mid-batch** (client disconnects after row 9 of
  18): rows 1–9 are already individually committed (per-row transactions,
  above) and stay committed — this is intentional idempotent-partial-progress,
  not a bug, given the per-row commit design; a retry of the same batch with
  no natural-key upsert (previous bullet) would then double the first 9. This
  is the concrete tradeoff of the per-row-commit decision and must be stated
  to whichever UI consumes this endpoint, not discovered later.

## 6. Summary for tech-lead / solution-architect reconciliation

- The create/edit routes, sidebar entry, and screen layout are
  solution-architect's to place; this spec fixes what those routes must call
  underneath: `_sync_interface_archimate_element()` (new, session-scoped
  helper — not the `ApplicationInterface` model, not a non-existent
  `_sync_archimate_element()` import) → `ApplicationInterfaceMetadata` →
  2× `SystemDependency` → 2–3× `ArchiMateRelationship`, one transaction.
- `validate_gap_kind()` must be called explicitly by the new gap-creation
  route; it is not currently invoked anywhere and the SRS's claim that it is
  "already enforced" needed correcting (§3.1).
- `ApplicationInterfaceMetadata` and `SystemDependency` are both
  non-`TenantMixin`; every read must join through `ArchiMateElement` (§2).
- `ApplicationInterface` (`application_layer.py`) is a pre-existing,
  overlapping store this feature deliberately does not write to (§0) — worth
  a line in whatever ADR/known-issue tracking `tech-lead` keeps, since it
  will otherwise look like an oversight to the next person who finds it.
