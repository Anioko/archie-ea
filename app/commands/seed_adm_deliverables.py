"""
Flask CLI command for seeding ADM deliverables.
Run with: flask seed-adm-deliverables

Seeds 18 TOGAF ADM deliverables (1-2 per phase) with ArchiMate 3.2 viewpoint
and element metadata. Idempotent — skips records where deliverable_code exists.
"""

import click
from flask.cli import with_appcontext


# 18 deliverables across 10 ADM phases
_DELIVERABLES = [
    # PRELIM
    {
        "deliverable_code": "DEL-PRELIM-001",
        "name": "Architecture Principles Catalog",
        "description": "Defines the architecture principles that guide design decisions across the enterprise.",
        "deliverable_type": "standards_document",
        "phase_code": "PRELIM",
        "archimate_viewpoint": "Motivation",
        "archimate_elements": ["Principle", "Goal", "Constraint"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-PRELIM-002",
        "name": "Governance Framework",
        "description": "Establishes the governance bodies, processes, and compliance criteria for architecture work.",
        "deliverable_type": "guidelines",
        "phase_code": "PRELIM",
        "archimate_viewpoint": "Stakeholder",
        "archimate_elements": ["Stakeholder", "Assessment", "Goal"],
        "is_primary": False,
    },
    # Phase A
    {
        "deliverable_code": "DEL-A-001",
        "name": "Architecture Vision Document",
        "description": "High-level aspirational view of the target architecture aligned to business strategy.",
        "deliverable_type": "architecture_vision",
        "phase_code": "A",
        "archimate_viewpoint": "Motivation",
        "archimate_elements": ["Driver", "Goal", "Outcome"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-A-002",
        "name": "Statement of Architecture Work",
        "description": "Formal project plan defining scope, approach, deliverables, and timeline.",
        "deliverable_type": "implementation_plan",
        "phase_code": "A",
        "archimate_viewpoint": "Project",
        "archimate_elements": ["WorkPackage", "Deliverable", "Plateau"],
        "is_primary": False,
    },
    # Phase B
    {
        "deliverable_code": "DEL-B-001",
        "name": "Business Architecture Document",
        "description": "Documents business processes, capabilities, and organizational structure of the target state.",
        "deliverable_type": "business_architecture",
        "phase_code": "B",
        "archimate_viewpoint": "Business Process",
        "archimate_elements": ["BusinessProcess", "BusinessFunction", "BusinessService", "BusinessRole"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-B-002",
        "name": "Capability Gap Analysis",
        "description": "Identifies gaps between current and target business capability states.",
        "deliverable_type": "other",
        "phase_code": "B",
        "archimate_viewpoint": "Migration",
        "archimate_elements": ["Gap", "Plateau", "BusinessCapability"],
        "is_primary": False,
    },
    # Phase C
    {
        "deliverable_code": "DEL-C-001",
        "name": "Data Architecture Document",
        "description": "Defines the data entities, relationships, and data management policies of the target state.",
        "deliverable_type": "data_architecture",
        "phase_code": "C",
        "archimate_viewpoint": "Information Structure",
        "archimate_elements": ["DataObject", "BusinessObject", "Representation"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-C-002",
        "name": "Application Architecture Document",
        "description": "Describes the application components, interfaces, and interactions of the target state.",
        "deliverable_type": "application_architecture",
        "phase_code": "C",
        "archimate_viewpoint": "Application Cooperation",
        "archimate_elements": ["ApplicationComponent", "ApplicationInterface", "ApplicationService"],
        "is_primary": False,
    },
    # Phase D
    {
        "deliverable_code": "DEL-D-001",
        "name": "Technology Architecture Document",
        "description": "Specifies the technology infrastructure, platforms, and standards for the target state.",
        "deliverable_type": "technology_architecture",
        "phase_code": "D",
        "archimate_viewpoint": "Technology",
        "archimate_elements": ["Node", "Device", "SystemSoftware", "TechnologyService"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-D-002",
        "name": "Technology Standards Catalog",
        "description": "Catalogs approved, emerging, and retiring technology standards for the enterprise.",
        "deliverable_type": "standards_document",
        "phase_code": "D",
        "archimate_viewpoint": "Technology Usage",
        "archimate_elements": ["TechnologyService", "Artifact", "CommunicationNetwork"],
        "is_primary": False,
    },
    # Phase E
    {
        "deliverable_code": "DEL-E-001",
        "name": "Architecture Roadmap",
        "description": "Time-sequenced plan of work packages, plateaus, and transition architectures.",
        "deliverable_type": "migration_plan",
        "phase_code": "E",
        "archimate_viewpoint": "Migration",
        "archimate_elements": ["WorkPackage", "Plateau", "Gap", "Deliverable"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-E-002",
        "name": "Solution Building Blocks Catalog",
        "description": "Catalogs reusable solution building blocks identified during opportunity analysis.",
        "deliverable_type": "patterns",
        "phase_code": "E",
        "archimate_viewpoint": "Layered",
        "archimate_elements": ["ApplicationComponent", "TechnologyService", "Node"],
        "is_primary": False,
    },
    # Phase F
    {
        "deliverable_code": "DEL-F-001",
        "name": "Implementation & Migration Plan",
        "description": "Detailed project plan for implementing the target architecture through transition states.",
        "deliverable_type": "implementation_plan",
        "phase_code": "F",
        "archimate_viewpoint": "Implementation and Migration",
        "archimate_elements": ["WorkPackage", "Deliverable", "Plateau", "Gap"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-F-002",
        "name": "Transition Architecture Definition",
        "description": "Describes intermediate architecture states between baseline and target.",
        "deliverable_type": "migration_plan",
        "phase_code": "F",
        "archimate_viewpoint": "Migration",
        "archimate_elements": ["Plateau", "Gap", "ApplicationComponent"],
        "is_primary": False,
    },
    # Phase G
    {
        "deliverable_code": "DEL-G-001",
        "name": "Compliance Assessment Report",
        "description": "Evaluates implementation conformance against approved architecture specifications.",
        "deliverable_type": "other",
        "phase_code": "G",
        "archimate_viewpoint": "Goal Realization",
        "archimate_elements": ["Goal", "Requirement", "Constraint"],
        "is_primary": True,
    },
    # Phase H
    {
        "deliverable_code": "DEL-H-001",
        "name": "Architecture Change Request Log",
        "description": "Tracks all change requests, their impact assessments, and disposition decisions.",
        "deliverable_type": "other",
        "phase_code": "H",
        "archimate_viewpoint": "Stakeholder",
        "archimate_elements": ["Driver", "Assessment", "Goal"],
        "is_primary": True,
    },
    # REQ
    {
        "deliverable_code": "DEL-REQ-001",
        "name": "Requirements Catalog",
        "description": "Master catalog of all architecture requirements linked to stakeholder concerns.",
        "deliverable_type": "other",
        "phase_code": "REQ",
        "archimate_viewpoint": "Goal Realization",
        "archimate_elements": ["Requirement", "Goal", "Constraint"],
        "is_primary": True,
    },
    {
        "deliverable_code": "DEL-REQ-002",
        "name": "Requirements Traceability Matrix",
        "description": "Traces requirements to their source drivers, target components, and test evidence.",
        "deliverable_type": "other",
        "phase_code": "REQ",
        "archimate_viewpoint": "Motivation",
        "archimate_elements": ["Requirement", "Driver", "Goal", "Outcome"],
        "is_primary": False,
    },
]


@click.command("seed-adm-deliverables")
@with_appcontext
def seed_adm_deliverables_command():
    """Seed database with 18 TOGAF ADM deliverables."""
    from app import db
    from app.models.adm_kanban import ADMPhase
    from app.models.adm_portfolio import ADMDeliverable

    # Ensure table exists (no migrations allowed)
    db.create_all()

    # Build phase_code -> phase_id lookup
    phases = ADMPhase.query.all()
    phase_map = {p.code: p.id for p in phases}

    if not phase_map:
        click.echo("No ADM phases found. Run seed-adm-phases first.")
        return

    created = 0
    skipped = 0

    for spec in _DELIVERABLES:
        # Idempotent: skip if deliverable_code already exists
        existing = ADMDeliverable.query.filter_by(
            deliverable_code=spec["deliverable_code"]
        ).first()
        if existing:
            click.echo(f"  skip  {spec['deliverable_code']} (exists)")
            skipped += 1
            continue

        phase_id = phase_map.get(spec["phase_code"])
        if phase_id is None:
            click.echo(f"  WARN  Phase {spec['phase_code']} not found — skipping {spec['deliverable_code']}")
            skipped += 1
            continue

        deliv = ADMDeliverable(
            deliverable_code=spec["deliverable_code"],
            name=spec["name"],
            description=spec["description"],
            deliverable_type=spec["deliverable_type"],
            phase_id=phase_id,
            document_status="draft",
            document_version="0.1",
            archimate_viewpoint=spec["archimate_viewpoint"],
            archimate_elements=spec["archimate_elements"],
        )
        db.session.add(deliv)
        created += 1
        click.echo(f"  +     {spec['deliverable_code']}: {spec['name']}")

    db.session.commit()

    click.echo(f"\nDone. Created: {created}, Skipped: {skipped}, Total: {len(_DELIVERABLES)}")


def init_app(app):
    """Register CLI command with app."""
    app.cli.add_command(seed_adm_deliverables_command)
