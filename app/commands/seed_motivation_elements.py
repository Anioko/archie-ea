"""
Seed enterprise-standard ArchiMate Driver, Stakeholder, and Constraint vocabulary.
Safe to run multiple times — uses upsert-by-name.
"""

DRIVERS = [
    {"name": "Digital Transformation", "element_type": "driver", "layer": "motivation", "description": "Imperative to modernise business processes and technology stack through digital capabilities."},
    {"name": "Regulatory Compliance", "element_type": "driver", "layer": "motivation", "description": "Obligation to meet legal, regulatory, and industry-standard requirements."},
    {"name": "Cost Optimisation", "element_type": "driver", "layer": "motivation", "description": "Pressure to reduce operational costs and improve return on technology investment."},
    {"name": "Customer Experience", "element_type": "driver", "layer": "motivation", "description": "Need to improve end-to-end customer journeys and satisfaction scores."},
    {"name": "Operational Excellence", "element_type": "driver", "layer": "motivation", "description": "Drive to streamline operations, reduce manual effort, and improve reliability."},
    {"name": "Cyber Security Risk", "element_type": "driver", "layer": "motivation", "description": "Growing threat landscape requiring enhanced security posture and resilience."},
]

GOALS = [
    {"name": "Achieve Full Capability Coverage", "element_type": "goal", "layer": "motivation", "description": "Ensure all business capabilities are adequately supported by technology."},
    {"name": "Reduce Technical Debt", "element_type": "goal", "layer": "motivation", "description": "Systematically eliminate legacy systems, outdated patterns, and deferred maintenance."},
    {"name": "Enable Cloud-First Architecture", "element_type": "goal", "layer": "motivation", "description": "Migrate workloads to cloud platforms to improve agility and reduce infrastructure costs."},
    {"name": "Improve Business Agility", "element_type": "goal", "layer": "motivation", "description": "Increase the speed at which the organisation can respond to market changes."},
    {"name": "Strengthen Data Governance", "element_type": "goal", "layer": "motivation", "description": "Implement robust data quality, lineage, and access-control frameworks."},
]

STAKEHOLDERS = [
    "CIO",
    "CTO",
    "CFO",
    "Enterprise Architect",
    "Business Analyst",
    "IT Operations Lead",
    "Compliance Officer",
    "Product Owner",
]

CONSTRAINTS = [
    "GDPR Compliance",
    "Budget Cap",
    "Legacy System Integration",
    "Cloud-Only Deployment",
    "On-Premises Only",
    "Vendor Lock-in Avoidance",
    "6-Month Delivery Window",
    "12-Month Delivery Window",
]


def seed_motivation_elements():
    """Upsert enterprise-standard ArchiMate Motivation vocabulary records."""
    from app import create_app, db
    from app.models.archimate import ArchitectureElement
    from app.models.archimate_motivation import MotivationConstraint, MotivationStakeholder

    app = create_app()
    with app.app_context():
        for d in DRIVERS:
            existing = ArchitectureElement.query.filter_by(name=d["name"]).first()
            if existing is None:
                db.session.add(ArchitectureElement(**d))

        for g in GOALS:
            existing = ArchitectureElement.query.filter_by(name=g["name"]).first()
            if existing is None:
                db.session.add(ArchitectureElement(**g))

        for name in STAKEHOLDERS:
            existing = MotivationStakeholder.query.filter_by(name=name).first()
            if existing is None:
                db.session.add(MotivationStakeholder(name=name))

        for name in CONSTRAINTS:
            existing = MotivationConstraint.query.filter_by(name=name).first()
            if existing is None:
                db.session.add(MotivationConstraint(name=name))

        db.session.commit()
        print("Motivation vocabulary seeded successfully.")


if __name__ == "__main__":
    seed_motivation_elements()
