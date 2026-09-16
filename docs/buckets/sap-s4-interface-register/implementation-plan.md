# Implementation Plan: SAP S/4HANA Interface Register

Bucket: `sap-s4-interface-register`
Author role: `tech-lead`
Inputs, all `approval_status: approved`:
- `docs/buckets/sap-s4-interface-register/brief.md`
- `docs/buckets/sap-s4-interface-register/srs.md`
- `docs/buckets/sap-s4-interface-register/sdd.md` (+ `docs/handoffs/sap-s4-interface-register-solution-architect-to-tech-lead.json`)
- `docs/buckets/sap-s4-interface-register/integration-spec.md` (+ `docs/handoffs/sap-s4-interface-register-integration-architect-to-tech-lead.json`)
- `docs/adr/0011-derived-display-bands.md`

Output: five task briefs in `docs/buckets/sap-s4-interface-register/tasks/`,
executed in order by `builder`.

---

## 1. Arbitration — the element write path. Decided here, not deferred.

I read `app/models/application_layer.py` (the `ApplicationInterface` class at
line 42, its `before_insert` listener `create_interface_archimate_element` at
line 618) and `app/services/archimate_backbone.py` in full before deciding.
Both design agents were partly right and both were wrong about a load-bearing
fact.

### 1.1 What is actually true in the tree

1. **`sync_archimate_element` DOES exist** and is the single sanctioned
   implementation — `app/services/archimate_backbone.py:96`, imported by
   fourteen call sites (`unified_enterprise_routes.py`, `goal_service.py`,
   `gap_archimate_service.py`, `programme_setup_service.py`,
   `smart_defaults_service.py`, `roadmap_generator.py`, …). The
   integration-spec §1.2 instruction *"do not invent an import of a symbol that
   isn't defined"* is wrong on the substance: only the leading-underscore
   spelling is absent. The module docstring (lines 11–35) records that this
   module exists **precisely because** three bespoke `_sync_archimate_element`
   helpers previously existed with different signatures, and that
   "'call the helper' named an ambiguity, not a function."
2. **Solution-architect is correct on the two mechanical blockers.**
   `ELEMENT_TYPES` (`archimate_backbone.py:45-59`) has no `ApplicationInterface`
   and no `ApplicationInterfaceMetadata` key, so `sync_archimate_element(obj)`
   hits `if mapping is None: return None` at line 113 — a silent `None` on the
   one path in the module that is otherwise documented as never swallowing. And
   the ordering is genuinely backwards: the helper sets
   `obj.archimate_element_id` *after* creating the element (line 153), while
   `ApplicationInterfaceMetadata.archimate_element_id` is `nullable=False,
   unique=True`, so the element must exist first.
3. **Integration-architect is correct that the `ApplicationInterface` ORM class
   must not be the register's write target** — but the reasoning in
   integration-spec §0 is incomplete, and the real risk is larger than stated.

### 1.2 The decision

**Element creation for the Interface Register goes through
`app/services/archimate_backbone.py` — extended, not bypassed. No new
`_sync_interface_archimate_element` helper is added anywhere.**

Concretely (Task 01):

- Extract the element-construction body of `sync_archimate_element`
  (lines 136–154) into a new public, element-first entry point in the same
  module:
  `create_backbone_element(*, element_type, layer, name, description=None, organization_id, session=None, provenance=None) -> ArchiMateElement`.
  It does the name truncation at `MAX_NAME`, the `source_name` overflow
  property, `scope="enterprise"`, `custom_properties` provenance, `session.add`
  and `session.flush()`, and returns the element.
- `sync_archimate_element` is refactored to call it and then assign
  `obj.archimate_element_id = element.id`. Its public contract, signature,
  idempotency and raising behaviour are unchanged — all fourteen existing call
  sites keep working untouched.
- `ELEMENT_TYPES` gains
  `"ApplicationInterfaceMetadata": ("ApplicationInterface", "Application")`, so
  the object-keyed path stops silently returning `None` for the one model that
  is now a first-class backbone citizen.
- The interface write path calls `create_backbone_element(...)` first, then
  inserts `ApplicationInterfaceMetadata(archimate_element_id=element.id, ...)`.
  Ordering problem solved without inverting anyone's contract.

**Why this and not integration-spec §1.2's private helper.** Adding a fourth
bespoke element-creation function that mirrors
`StrategicService._sync_archimate_element()`'s shape re-opens, by hand, exactly
the defect `archimate_backbone.py` was written to close two weeks ago. It would
also silently drop three things the canonical helper does and the hand-written
snippet in the spec does not: `MAX_NAME` truncation against
`ArchiMateElement.name String(100)` (the SDD §6 truncation requirement depends
on it), the `custom_properties["source_name"]` overflow record, and
`custom_properties["source_model"]` provenance — which ADR 0008 rule 2 requires
of any derived row. Integration-architect's *intent* (one explicit, session-
scoped, flush-not-commit call that returns the element for the caller to link)
is preserved exactly; only its placement changes, from a private copy to the
module that already owns the concept.

**Why the `ApplicationInterface` ORM class is still not written — with the
reason integration-architect missed.** I agree with the conclusion. The
supporting facts are: `ApplicationInterfaceMetadata` is the brief's named
system of record and is keyed 1:1 (`unique=True`) to the backbone element,
whereas `application_interfaces.archimate_element_id` is `nullable=True` — a
row there can exist off the backbone entirely. And its `before_insert` listener
creates the element with a **raw core `connection.execute(insert(...))`**
(line 626), which bypasses the ORM: no `scope`, no `custom_properties`
provenance, and no `TenantMixin` flush hook on the element. It is a weaker
producer than the canonical helper, not an equivalent one.

**The consequence neither spec caught, and which this bucket must fix.**
`ApplicationInterface` is not a dead store. `app/factories/domain_model_factory.py:35`
registers it in `_MODEL_REGISTRY` and produces rows from element templates, and
`app/modules/architecture/routes/architecture_routes.py:578` renders
`interface_count` on the software-architecture dashboard from
`SELECT COUNT(*) FROM application_interfaces`. So if the register writes only
`ArchiMateElement` + metadata, that dashboard card answers "how many interfaces
exist" with a number that excludes every registered interface — two surfaces,
one question, different answers, on day one. That is a `store-agreement`
failure, and it is the exact shape ADR 0008 exists to stop.

**Fix, in scope, Task 01:** repoint `interface_count` at the canonical answer —
`ArchiMateElement` where `type='ApplicationInterface'`, tenant-scoped through
the ORM. This is a superset and therefore correct for both producers: rows
created by `DomainModelFactory` already carry an element (the factory creates
it first and passes `archimate_element_id`), and rows created any other way get
one from the `before_insert` listener. It is a read-side change only.
`application_interfaces` keeps its rows and its factory producer; it simply
stops being a second *answer*.

**Booked, not silently left** (Task 01 deliverable): a note appended to
`docs/adr/0008-one-system-of-record.md` recording `application_interfaces` as a
partially-superseded store whose canonical answer is now the backbone element,
with the `retired_into_id` pointer and any row migration deferred to its own
bucket. Prose alone is not acceptable per root `CLAUDE.md`, which is why the
`store-agreement` case in Task 05 is the actual enforcement.

## 2. The SRS's incorrect grounding claim

SRS §0 bullet 1 and Assumption A3 state there is no `ApplicationInterface` ORM
class. There is — `app/models/application_layer.py:42`, `TenantMixin`, ~40
columns, its own table. Integration-spec §0 is correct to correct it.

**Ruling: the SRS's *conclusion* survives its wrong premise.** "Interface" in
this feature still means `ArchiMateElement(type='ApplicationInterface')` +
`ApplicationInterfaceMetadata`, for the reasons in §1.2 above — but it is now a
deliberate choice between two real stores, not the absence of an alternative.
Task 01 corrects the SRS text in place (a wrong grounding note left standing is
how the next agent re-derives the wrong answer) and no story changes.

## 3. `validate_gap_kind()` has zero callers

Confirmed by grep across the tree: `validate_gap_kind`
(`app/models/implementation_migration.py:550`) appears only in its own
definition and in this bucket's markdown. Integration-spec §3.1 is right; the
SRS's "already enforced in code today" is wrong.

**Ruling — both halves, not the weaker one.** Integration-architect asked only
for an explicit service-layer call and *recommended* the listener as a
follow-up. I am taking the listener now (Task 03):

- Register `validate_gap_kind` as a SQLAlchemy `before_insert` **and**
  `before_update` listener on `Gap`, in `implementation_migration.py` directly
  below the function. This is safe with zero behaviour change for existing
  data: the function returns immediately unless
  `gap_kind == 'plateau_transition'` (line 563), and no code path in the tree
  writes that value today — the model comment at lines 526–545 records that the
  product has never recorded one.
- **And** call `validate_gap_kind(gap)` explicitly in
  `interface_gap_service.py` before `session.add()`, so the user gets the
  raised message as an inline 400 form error rather than a 500 from a flush.

The listener is the backstop that makes the invariant free for every future
caller; the explicit call is the user-facing error path. Leaving it as a
follow-up would ship the third instance in this bucket of "correctly written,
never wired."

## 4. `ROLE_SECTION_ACCESS` vs `ENTERPRISE_ROLE_SECTION_MAP`

Two authorities for one question, confirmed:
`app/utils/role_access.py:51` and
`app/_bootstrap/context_processors.py:457`. They disagree —
`security_architect` and `data_architect` have entries in the first and none in
the second, so those two personas fall through to the archetype map or to
`all_sections`.

**Ruling: it lands in this bucket, derived, minimally (Task 05).**
`ENTERPRISE_ROLE_SECTION_MAP` becomes a comprehension over
`ROLE_SECTION_ACCESS` unioned with a small, explicitly-named
`_LEGACY_SECTION_ALIASES` dict preserving the alias sets currently inlined
(`application`, `tools`, `data`, `utilities`, `admin`). No third copy, no
hand-edit of one side. Booking it as a finding is not available to me: root
`CLAUDE.md` is explicit that a note converts a bug into a bug plus a note, and
this feature adds a `data_integration` link whose visibility is decided by the
very map that disagrees.

Two related points settled:

- **No twelfth enterprise persona.** I uphold SDD §7.1. Note for the record
  that `integration_architect` *does* exist as a `role_archetype` key
  (`context_processors.py:443`) but not as an `enterprise_role`; that asymmetry
  is pre-existing and is not widened here. The Integration Architect actor maps
  to `solution_architect` / `enterprise_architect`, both of which already hold
  `data_integration`.
- **EA sidebar link: not added**, per SDD §7.2 and the in-file comment at
  `role_access.py:468-479`. Revisit only if the Task 05 walkthrough shows the
  EA persona cannot reach the register at all.

## 5. Tenancy — `ApplicationInterfaceMetadata` / `SystemDependency`

Both specs agree and so do I: neither carries `TenantMixin` or an
`organization_id` column, so **every** read roots at `ArchiMateElement` (which
is `TenantMixin` and gets the `do_orm_execute` filter) and joins outward. This
is binding on every query in Tasks 02, 03 and 04:

- `db.session.query(ArchiMateElement).outerjoin(ApplicationInterfaceMetadata, ...)`,
  never `ApplicationInterfaceMetadata.query...` as the primary entity, and
  never an `.in_(...)` fed by an id list that was not itself produced by a
  tenant-filtered element query.
- No hand-written `organization_id=` predicate on any `TenantMixin` model
  (`Plateau`, `Gap`, `WorkPackage`, `ArchiMateElement`) — that double-filters.
- `.filter_by(id=...).first()`, never `.get()`, for tenant-scoped loads.
- No new `tenancy-ok` / `tenant-scoping-ok` marker. If the builder believes one
  is needed, stop and escalate — it is a design change.
- `create_backbone_element` takes `organization_id` as a keyword and must be
  passed it explicitly from any non-request path.

The isolation argument is asserted by a cross-org negative case in Task 05, not
assumed.

## 6. Other reconciliations

- **Bulk import (integration-spec §5).** Deferred out of this bucket. No SRS
  story covers it, and a per-row-commit endpoint with no natural-key upsert has
  a stated double-write hazard on retry. Task 02 makes the single-create
  service function the reusable seam so a later bulk route calls it rather than
  reimplementing; the route itself is not built here.
- **`ArchiMateRelationship` rows (integration-spec §4).** In scope, Task 02,
  exactly as specified: `composition` provider→interface, `serving`
  interface→consumer, conditional `realization` interface→service. Lowercase
  `type` strings, matching `archimate_routes.py:2605`. Stale-pair deletion on
  edit is required.
- **Module placement.** SDD §3 stands unamended: new
  `app/modules/interface_register/`, one blueprint at `/interface-register`.
- **T-shirt band.** ADR 0011 thresholds, display-only pure function, `—` for
  NULL. Task 04.

## 7. Task order and dependencies

| # | Task | Depends on | Brief |
|---|---|---|---|
| 01 | Backbone element helper + store-agreement correction | — | `tasks/01-archimate-sync-helper.md` |
| 02 | Interface Register module, CRUD, relationships | 01 | `tasks/02-interface-register-crud.md` |
| 03 | Plateau pair provisioning + gap raising + `validate_gap_kind` wiring | 02 | `tasks/03-plateau-gap-provisioning.md` |
| 04 | WorkPackage rollup, derived band, over-budget state | 03 | `tasks/04-workpackage-rollup-and-bands.md` |
| 05 | Sidebar, section-map de-duplication, full browser walkthrough | 04 | `tasks/05-sidebar-and-tests.md` |

Each task ends with `python scripts/verify.py` (bare, never a `--tag` subset)
green before the next begins. Task 05 is the only one that can report the
feature done, and only on a clicked-through Playwright journey per
"Done means DEMONSTRATED".

## 8. SRS story coverage

| Story | Task |
|---|---|
| US-1 view register | 02 |
| US-2 create | 01 (element path) + 02 |
| US-3 edit / retire | 02 |
| US-4 plateau pair | 03 |
| US-5 raise gap | 03 |
| US-6 costing rollup | 04 |
| US-7 sidebar + personas | 05 |

Every story is owned by exactly one task. Gate condition
`all_srs_stories_covered_by_a_task` is satisfied.
