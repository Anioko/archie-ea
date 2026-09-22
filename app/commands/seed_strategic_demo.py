"""flask seed-strategic-demo — a demonstration data set for T-S1 / T-S4.

No existing seeder creates a value stream: `flask seed-demo-mappings` maps
entities that already exist and is pinned never to create one;
`flask seed-capabilities` creates capability catalogues and creates no value
stream and sets no per-tenant maturity. Without this command, the answer is
correct on day one but has nothing to show (design § 8, SR-S2) -- the
demonstration fixture is T-S1's own acceptance item, not a general seeding
concern.

Writes, for one organisation only:

  * two value streams, each with two stages, through
    ``value_stream_service.create_value_stream`` / ``create_stage``;
  * six ``UnifiedCapability`` rows owned by that organisation, each with
    ``current_maturity_level`` and ``target_maturity_level`` set -- at least
    two below 3 and at least two at 3 or above, so the answer shows both a
    scored at-risk capability and a scored safe one;
  * eight mapping rows across the four stages, through
    ``value_stream_service.upsert_mapping_cell``, with ``support_type``,
    ``support_level`` and ``impact_level`` varied across the eight;
  * (T-S4) four ``ArchiMateElement`` rows mirroring four of the six
    capabilities -- the two capability listeners this codebase already has
    are on ``BusinessCapability``, not ``UnifiedCapability``, so nothing
    mirrors a seeded capability into the model without this section;
  * (T-S4) three ``PortfolioInitiative`` rows tied to those elements (two to
    capability elements, one to a value stream's own element), and three
    ``InitiativeSuccessMetric`` rows on two of them, so
    ``value_streams_at_risk``'s Path C answer is shown working: one
    capability with an initiative and two metrics, one initiative with no
    metric, one capability with no initiative, one value stream with no
    initiative, and two capabilities with no element at all.

It creates no capability it did not create itself, never touches a row whose
``organization_id`` is null, and never touches another organisation's row.
Neither ``PortfolioInitiative`` nor ``InitiativeSuccessMetric`` carries a
tenant column at all (DA-S3), so the three initiative codes this run would
use are looked up FIRST, before any writer below runs at all: an existing
row whose ``archimate_element_id`` does not resolve to an ``ArchiMateElement``
this organisation owns aborts the whole run before a single value stream,
stage, capability or mapping is written, naming the code -- the seed never
touches a row it does not own. All names are plainly invented, prefixed
``Demonstration:`` like the rest of this fixture.

Idempotent: re-running it creates nothing new and changes nothing. A mapping
row present with different values from a previous run counts as
``mappings_updated``, never as ``mappings_created``, and is upserted to the
current spec's values. ``--dry-run`` writes nothing at all -- no writer
function below is even called in that mode, so a value-stream/stage/mapping
writer's own internal commit can never fire under ``--dry-run``.

    flask --app manage seed-strategic-demo --org-id 7 --dry-run
    flask --app manage seed-strategic-demo --org-id 7
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app import db

# Two value streams, two stages each. Names and codes are plainly invented,
# in the style the repository's other demonstration fixtures use.
_VALUE_STREAMS = [
    {
        "code": "DEMO-VSR-FULFIL",
        "name": "Demonstration: Order Fulfilment",
        "stages": [
            {"name": "Demo Intake", "order": 1},
            {"name": "Demo Delivery", "order": 2},
        ],
    },
    {
        "code": "DEMO-VSR-SERVICE",
        "name": "Demonstration: Service Request Handling",
        "stages": [
            {"name": "Demo Triage", "order": 1},
            {"name": "Demo Resolution", "order": 2},
        ],
    },
]

# Six capabilities. Three below the default threshold of 3, three at or
# above it, so a seeded answer always shows both a scored at-risk capability
# and a scored safe one (T-S1 acceptance item 15).
_CAPABILITIES = [
    {"code": "DEMO-CAP-ORDER-CAPTURE", "name": "Demonstration: Order Capture", "current": 2, "target": 4},
    {"code": "DEMO-CAP-INVENTORY", "name": "Demonstration: Inventory Tracking", "current": 4, "target": 5},
    {"code": "DEMO-CAP-DELIVERY-SCHED", "name": "Demonstration: Delivery Scheduling", "current": 1, "target": 3},
    {"code": "DEMO-CAP-CASE-TRIAGE", "name": "Demonstration: Case Triage", "current": 3, "target": 4},
    {"code": "DEMO-CAP-ISSUE-RESOLUTION", "name": "Demonstration: Issue Resolution", "current": 5, "target": 5},
    {"code": "DEMO-CAP-KNOWLEDGE-BASE", "name": "Demonstration: Knowledge Base", "current": 2, "target": 3},
]

# Eight mapping rows across the four stages, support fields varied across
# the eight so the payload's curated fields are visibly populated rather
# than uniform.
_MAPPINGS = [
    {
        "value_stream_code": "DEMO-VSR-FULFIL", "stage_name": "Demo Intake",
        "capability_code": "DEMO-CAP-ORDER-CAPTURE",
        "support_type": "primary", "support_level": 5, "impact_level": "critical",
    },
    {
        "value_stream_code": "DEMO-VSR-FULFIL", "stage_name": "Demo Intake",
        "capability_code": "DEMO-CAP-INVENTORY",
        "support_type": "secondary", "support_level": 3, "impact_level": "medium",
    },
    {
        "value_stream_code": "DEMO-VSR-FULFIL", "stage_name": "Demo Delivery",
        "capability_code": "DEMO-CAP-DELIVERY-SCHED",
        "support_type": "primary", "support_level": 4, "impact_level": "high",
    },
    {
        "value_stream_code": "DEMO-VSR-FULFIL", "stage_name": "Demo Delivery",
        "capability_code": "DEMO-CAP-INVENTORY",
        "support_type": "supporting", "support_level": 2, "impact_level": "low",
    },
    {
        "value_stream_code": "DEMO-VSR-SERVICE", "stage_name": "Demo Triage",
        "capability_code": "DEMO-CAP-CASE-TRIAGE",
        "support_type": "primary", "support_level": 5, "impact_level": "high",
    },
    {
        "value_stream_code": "DEMO-VSR-SERVICE", "stage_name": "Demo Triage",
        "capability_code": "DEMO-CAP-KNOWLEDGE-BASE",
        "support_type": "secondary", "support_level": 3, "impact_level": "medium",
    },
    {
        "value_stream_code": "DEMO-VSR-SERVICE", "stage_name": "Demo Resolution",
        "capability_code": "DEMO-CAP-ISSUE-RESOLUTION",
        "support_type": "primary", "support_level": 4, "impact_level": "critical",
    },
    {
        "value_stream_code": "DEMO-VSR-SERVICE", "stage_name": "Demo Resolution",
        "capability_code": "DEMO-CAP-KNOWLEDGE-BASE",
        "support_type": "supporting", "support_level": 1, "impact_level": "low",
    },
]

# T-S4: four of the six capabilities get an ArchiMate element mirror.
# DEMO-CAP-CASE-TRIAGE and DEMO-CAP-ISSUE-RESOLUTION are deliberately left
# unlinked, so capability_not_linked_to_model is visible on the seeded
# answer.
_CAPABILITY_ELEMENTS = [
    "DEMO-CAP-ORDER-CAPTURE",
    "DEMO-CAP-DELIVERY-SCHED",
    "DEMO-CAP-KNOWLEDGE-BASE",
    "DEMO-CAP-INVENTORY",
]

# T-S4: three initiatives. Two tied to a capability's element, one tied to
# the Order Fulfilment value stream's own element. Knowledge Base's element
# gets no initiative (no_initiative_linked on a capability); the Service
# Request stream gets none (no_initiative_linked on a row). Codes are
# suffixed with the organisation id below, because portfolio_initiatives.code
# is globally unique on a table with no tenant column.
_INITIATIVES = [
    {
        "code_prefix": "DEMO-INI-ORDER",
        "name": "Demonstration: Order Capture Modernisation",
        "capability_code": "DEMO-CAP-ORDER-CAPTURE",
        "status": "Active",
        "health_status": "Amber",
        "expected_roi_percentage": 12.5,
        "business_value_score": 70,
        "risk_score": 40,
        "strategic_alignment_score": 80,
    },
    {
        "code_prefix": "DEMO-INI-DELIVERY",
        "name": "Demonstration: Delivery Scheduling Replacement",
        "capability_code": "DEMO-CAP-DELIVERY-SCHED",
        "status": "Approved",
        "health_status": "Red",
        "expected_roi_percentage": None,
        "business_value_score": 65,
        "risk_score": 75,
        "strategic_alignment_score": None,
    },
    {
        "code_prefix": "DEMO-INI-FULFIL",
        "name": "Demonstration: Fulfilment Flow Programme",
        "value_stream_code": "DEMO-VSR-FULFIL",
        "status": "Proposed",
        "health_status": None,
        "expected_roi_percentage": None,
        "business_value_score": None,
        "risk_score": None,
        "strategic_alignment_score": None,
    },
]

# T-S4: three metrics, two on the Order Capture initiative (one measured,
# one honestly unmeasured -- actual_value null), one on the Delivery
# initiative. The Fulfilment Flow initiative gets none, so
# no_success_metric_recorded is visible.
_METRICS = [
    {
        "initiative_code_prefix": "DEMO-INI-ORDER",
        "metric_name": "Order entry error rate",
        "metric_type": "KPI",
        "baseline_value": "4.2",
        "target_value": "1.0",
        "actual_value": "3.1",
        "unit_of_measure": "%",
        "status": "At Risk",
    },
    {
        "initiative_code_prefix": "DEMO-INI-ORDER",
        "metric_name": "Orders captured without rework",
        "metric_type": "KPI",
        "baseline_value": "78",
        "target_value": "95",
        "actual_value": None,
        "unit_of_measure": "%",
        "status": None,
    },
    {
        "initiative_code_prefix": "DEMO-INI-DELIVERY",
        "metric_name": "On-time delivery",
        "metric_type": "OKR",
        "baseline_value": "81",
        "target_value": "97",
        "actual_value": "84",
        "unit_of_measure": "%",
        "status": "Behind",
    },
]


def seed_strategic_demo(org_id: int, dry_run: bool = False) -> dict:
    """Write (or, under ``--dry-run``, only count) the demonstration data set
    for *org_id*. Returns counts: ``value_streams_created``,
    ``stages_created``, ``capabilities_created``, ``mappings_created``,
    ``mappings_updated``, ``elements_created``, ``initiatives_created``,
    ``metrics_created``, ``already_present``.

    Runs inside ``tenant_scope(org_id)`` (constraint: the command's whole
    write surface is one tenant). Every lookup and every write below names
    ``org_id`` explicitly rather than relying only on the ambient tenant
    context, matching this repository's belt-and-braces tenancy pattern --
    except ``PortfolioInitiative`` and ``InitiativeSuccessMetric``, which
    carry no tenant column at all (DA-S3): those are reached only through
    the element ids this same run just resolved, in memory, never by a
    fresh lookup that could cross a tenant boundary.

    The three initiative codes this run would use are looked up FIRST,
    before the value-stream section (or any other writer) runs at all,
    against exactly the element its own spec's capability or value stream
    already resolves to (a fresh lookup by code, not this run's own
    in-memory dict, since nothing has been created yet): an existing row
    whose ``archimate_element_id`` does not match that -- including a
    capability or value stream with no element of its own yet, which no
    successful prior run would ever leave behind -- aborts the WHOLE run
    (an exception, raised genuinely before any write) rather than touching
    a row it does not own. Value-stream, stage and mapping creation each
    commit internally (``value_stream_service``'s own writers), so checking
    this only once the initiatives section was reached left a half-seeded
    organisation behind on abort; the pre-flight guard below is what keeps
    this true. Everything this run flushed but did not commit is discarded
    by ``tenant_scope``'s own rollback on the way out.
    """
    from app.jobs.tenant_safe_job import tenant_scope
    from app.models import ArchiMateElement
    from app.models.enterprise_intelligence import InitiativeSuccessMetric, PortfolioInitiative
    from app.models.unified_capability import (
        CapabilityValueStreamMapping,
        UnifiedCapability,
        ValueStream,
        ValueStreamStage,
    )
    from app.modules.capabilities.services import value_stream_service

    stats = {
        "value_streams_created": 0,
        "stages_created": 0,
        "capabilities_created": 0,
        "mappings_created": 0,
        "mappings_updated": 0,
        "elements_created": 0,
        "initiatives_created": 0,
        "metrics_created": 0,
        "already_present": 0,
    }

    with tenant_scope(org_id):
        # -- pre-flight guard --------------------------------------------------
        # Look up the three initiative codes this run would use BEFORE any
        # writer below runs -- not merely before the initiatives section's
        # own write. Each code's own spec names a capability or a value
        # stream; a fresh lookup by that code (not this run's own in-memory
        # dict, since nothing has been created yet) resolves the element it
        # already has, if any. An existing initiative row is a conflict
        # unless its archimate_element_id exactly matches that -- a
        # capability or value stream with no element of its own yet is
        # itself a conflict too, since no successful prior run would ever
        # leave an initiative behind without also giving its own target an
        # element. Checked here, before a single value stream, stage,
        # capability or mapping is written, so an abort never leaves an
        # organisation half-seeded.
        for ini_spec in _INITIATIVES:
            code = f"{ini_spec['code_prefix']}-{org_id}"
            existing_initiative = PortfolioInitiative.query.filter_by(code=code).first()
            if existing_initiative is None:
                continue
            if "capability_code" in ini_spec:
                target = UnifiedCapability.query.filter_by(
                    organization_id=org_id, code=ini_spec["capability_code"]
                ).first()
            else:
                target = ValueStream.query.filter_by(
                    organization_id=org_id, code=ini_spec["value_stream_code"]
                ).first()
            target_element_id = target.archimate_element_id if target is not None else None
            if (
                target_element_id is None
                or existing_initiative.archimate_element_id != target_element_id
            ):
                raise RuntimeError(
                    f"seed-strategic-demo: existing initiative code {code!r} points "
                    f"at a different element than this organisation's own capability "
                    f"or value stream resolves to -- refusing to touch a row it does "
                    f"not own, before any write"
                )

        # -- value streams -------------------------------------------------
        vs_by_code = {}
        for vs_spec in _VALUE_STREAMS:
            existing = ValueStream.query.filter_by(
                organization_id=org_id, code=vs_spec["code"]
            ).first()
            if existing is not None:
                vs_by_code[vs_spec["code"]] = existing
                stats["already_present"] += 1
                continue
            if dry_run:
                stats["value_streams_created"] += 1
                continue
            vs = value_stream_service.create_value_stream(
                {
                    "name": vs_spec["name"],
                    "code": vs_spec["code"],
                    "value_stream_type": "customer_facing",
                }
            )
            vs_by_code[vs_spec["code"]] = vs
            stats["value_streams_created"] += 1

        # -- stages ----------------------------------------------------------
        stage_by_key = {}
        for vs_spec in _VALUE_STREAMS:
            vs = vs_by_code.get(vs_spec["code"])
            for stage_spec in vs_spec["stages"]:
                if vs is None:
                    # dry-run: the parent value stream was only counted, not
                    # created, so there is no id to check a stage against.
                    stats["stages_created"] += 1
                    continue
                existing_stage = ValueStreamStage.query.filter_by(
                    value_stream_id=vs.id, name=stage_spec["name"]
                ).first()
                if existing_stage is not None:
                    stage_by_key[(vs_spec["code"], stage_spec["name"])] = existing_stage
                    stats["already_present"] += 1
                    continue
                if dry_run:
                    stats["stages_created"] += 1
                    continue
                stage = value_stream_service.create_stage(
                    vs.id,
                    {"name": stage_spec["name"], "stage_order": stage_spec["order"]},
                )
                stage_by_key[(vs_spec["code"], stage_spec["name"])] = stage
                stats["stages_created"] += 1

        # -- capabilities ------------------------------------------------
        cap_by_code = {}
        for cap_spec in _CAPABILITIES:
            existing_cap = UnifiedCapability.query.filter_by(
                organization_id=org_id, code=cap_spec["code"]
            ).first()
            if existing_cap is not None:
                cap_by_code[cap_spec["code"]] = existing_cap
                stats["already_present"] += 1
                continue
            if dry_run:
                stats["capabilities_created"] += 1
                continue
            cap = UnifiedCapability(
                name=cap_spec["name"],
                code=cap_spec["code"],
                organization_id=org_id,
                scope="tenant",
                level=1,
                current_maturity_level=cap_spec["current"],
                target_maturity_level=cap_spec["target"],
            )
            db.session.add(cap)
            db.session.flush()
            cap_by_code[cap_spec["code"]] = cap
            stats["capabilities_created"] += 1

        # -- mappings ------------------------------------------------------
        for mapping_spec in _MAPPINGS:
            vs = vs_by_code.get(mapping_spec["value_stream_code"])
            stage = stage_by_key.get(
                (mapping_spec["value_stream_code"], mapping_spec["stage_name"])
            )
            cap = cap_by_code.get(mapping_spec["capability_code"])

            if vs is None or stage is None or cap is None:
                # dry-run on a FRESH organisation: nothing above was actually
                # created, so there is nothing concrete to look an existing
                # mapping up against -- counted only. This branch is not
                # reachable outside dry-run, because a real run always
                # resolves all three from the rows it just created above.
                stats["mappings_created"] += 1
                continue

            # Look up the existing row BEFORE branching on dry_run: on an
            # already-seeded organisation, vs/stage/cap above are all
            # resolved from EXISTING rows even under --dry-run, so the
            # lookup below is real and "would create" must not claim work
            # that is already done.
            existing_mapping = CapabilityValueStreamMapping.query.filter_by(
                capability_id=cap.id,
                value_stream_id=vs.id,
                value_stream_stage_id=stage.id,
            ).first()
            if (
                existing_mapping is not None
                and existing_mapping.support_type == mapping_spec["support_type"]
                and existing_mapping.support_level == mapping_spec["support_level"]
                and existing_mapping.impact_level == mapping_spec["impact_level"]
            ):
                # Already present with the same values -- skip the upsert
                # call entirely so a re-run does not even touch updated_at
                # (constraint: re-running changes nothing).
                stats["already_present"] += 1
                continue

            # A row present with DIFFERENT values is an update, not a
            # creation -- counted separately, never folded into
            # mappings_created.
            stat_key = "mappings_updated" if existing_mapping is not None else "mappings_created"

            if dry_run:
                # Absent, or present with different values: real work this
                # run would do, reported honestly, but not written.
                stats[stat_key] += 1
                continue

            value_stream_service.upsert_mapping_cell(
                cap.id,
                vs.id,
                stage.id,
                {
                    "support_type": mapping_spec["support_type"],
                    "support_level": mapping_spec["support_level"],
                    "impact_level": mapping_spec["impact_level"],
                },
            )
            stats[stat_key] += 1

        # -- capability elements (T-S4) ------------------------------------
        # Neither element-mirroring listener this codebase already has is
        # callable for a UnifiedCapability (one runs on a Core connection
        # inside a ValueStream's own flush event, the other listens on
        # BusinessCapability, not UnifiedCapability) -- the seed writes the
        # same four values either listener writes, directly.
        for cap_code in _CAPABILITY_ELEMENTS:
            cap = cap_by_code.get(cap_code)
            if cap is None:
                # dry-run on a fresh organisation: the capability itself was
                # only counted above, not created -- counted only.
                stats["elements_created"] += 1
                continue
            if cap.archimate_element_id is not None:
                stats["already_present"] += 1
                continue
            if dry_run:
                stats["elements_created"] += 1
                continue
            name = cap.name if len(cap.name) <= 100 else cap.name[:99] + "…"
            element = ArchiMateElement(
                name=name,
                type="Capability",
                layer="Strategy",
                description=f"Capability: {cap.name}",
                organization_id=org_id,
            )
            db.session.add(element)
            db.session.flush()
            cap.archimate_element_id = element.id
            stats["elements_created"] += 1

        # -- initiatives (T-S4) ---------------------------------------------
        initiative_by_code: dict = {}
        for ini_spec in _INITIATIVES:
            code = f"{ini_spec['code_prefix']}-{org_id}"

            if "capability_code" in ini_spec:
                cap = cap_by_code.get(ini_spec["capability_code"])
                element_id = cap.archimate_element_id if cap is not None else None
            else:
                vs = vs_by_code.get(ini_spec["value_stream_code"])
                element_id = vs.archimate_element_id if vs is not None else None

            if element_id is None:
                # dry-run on a fresh organisation: the element this
                # initiative needs was only counted above, not created --
                # counted only, and no metric below can be resolved against
                # it either.
                stats["initiatives_created"] += 1
                initiative_by_code[code] = None
                continue

            # The pre-flight guard above already confirmed, before any writer
            # ran, that an existing row for this code (if any) points at
            # exactly this element -- so a row found here is always the
            # already-present case, never a conflict to re-check.
            existing_initiative = PortfolioInitiative.query.filter_by(code=code).first()
            if existing_initiative is not None:
                initiative_by_code[code] = existing_initiative
                stats["already_present"] += 1
                continue

            if dry_run:
                stats["initiatives_created"] += 1
                initiative_by_code[code] = None
                continue

            initiative = PortfolioInitiative(
                name=ini_spec["name"],
                code=code,
                archimate_element_id=element_id,
                status=ini_spec["status"],
                health_status=ini_spec["health_status"],
                expected_roi_percentage=ini_spec["expected_roi_percentage"],
                business_value_score=ini_spec["business_value_score"],
                risk_score=ini_spec["risk_score"],
                strategic_alignment_score=ini_spec["strategic_alignment_score"],
            )
            db.session.add(initiative)
            db.session.flush()
            initiative_by_code[code] = initiative
            stats["initiatives_created"] += 1

        # -- success metrics (T-S4) -----------------------------------------
        for metric_spec in _METRICS:
            code = f"{metric_spec['initiative_code_prefix']}-{org_id}"
            initiative = initiative_by_code.get(code)
            if initiative is None:
                # dry-run, or this run never resolved the initiative's own
                # element -- nothing concrete to look an existing metric up
                # against -- counted only.
                stats["metrics_created"] += 1
                continue

            existing_metric = InitiativeSuccessMetric.query.filter_by(
                initiative_id=initiative.id, metric_name=metric_spec["metric_name"]
            ).first()
            if existing_metric is not None:
                stats["already_present"] += 1
                continue

            if dry_run:
                stats["metrics_created"] += 1
                continue

            metric = InitiativeSuccessMetric(
                initiative_id=initiative.id,
                metric_name=metric_spec["metric_name"],
                metric_type=metric_spec["metric_type"],
                baseline_value=metric_spec["baseline_value"],
                target_value=metric_spec["target_value"],
                actual_value=metric_spec["actual_value"],
                unit_of_measure=metric_spec["unit_of_measure"],
                status=metric_spec["status"],
            )
            db.session.add(metric)
            stats["metrics_created"] += 1

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    return stats


@click.command("seed-strategic-demo")
@click.option(
    "--org-id", type=int, required=True,
    help="Organisation to seed. Mandatory -- this writes sample data.",
)
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def seed_strategic_demo_command(org_id, dry_run):
    """Write the demonstration data set for one organisation."""
    from app.models.organization import Organization

    org = db.session.get(Organization, org_id)
    if org is None:
        raise click.ClickException(f"No organization with id={org_id}.")

    click.echo(f"  organisation {org_id} ({org.name})")

    stats = seed_strategic_demo(org_id, dry_run=dry_run)

    verb = "would create" if dry_run else "created"
    click.echo(
        f"  {verb} {stats['value_streams_created']} value stream(s), "
        f"{stats['stages_created']} stage(s), "
        f"{stats['capabilities_created']} capability row(s), "
        f"{stats['mappings_created']} mapping row(s) "
        f"({stats['mappings_updated']} updated), "
        f"{stats['elements_created']} element(s), "
        f"{stats['initiatives_created']} initiative(s), "
        f"{stats['metrics_created']} metric(s); "
        f"{stats['already_present']} already present."
    )


def init_app(app):
    app.cli.add_command(seed_strategic_demo_command)
