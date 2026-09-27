# -*- coding: utf-8 -*-
"""Phase 5: transformation programme (initiative) + milestones + roadmap plateaus,
with the SAP/SFDC solutions linked to the programme. Idempotent."""
from datetime import datetime, timedelta
from manage import app
from app import db


def colset(model):
    return {c.name for c in model.__table__.columns}


def main():
    with app.app_context():
        from app.models.strategic import StrategicInitiative, StrategicMilestone
        from app.models.solution_models import Solution
        from app.models.organization import Organization
        from app.models.implementation_migration import Plateau

        org_id = Organization.query.order_by(Organization.id.asc()).first().id
        base = datetime(2026, 7, 1)

        # ---- Programme / initiative ----
        INAME = "S/4HANA + Salesforce Customer 360 Programme"
        init = StrategicInitiative.query.filter_by(name=INAME).first()
        ic = colset(StrategicInitiative)
        if not init:
            kwargs = {"name": INAME}
            for k, v in {
                "description": "Brownfield transformation establishing a single customer golden record across SAP S/4HANA (system of record) and Salesforce (system of engagement), brokered via MuleSoft + SAP CPI.",
                "initiative_type": "brownfield", "target_platform": "SAP S/4HANA + Salesforce",
                "vendor_key": "SAP", "status": "in_progress", "priority": "high",
                "owner_id": 1, "business_value_score": 88, "risk_level": "medium",
                "budget_allocated": 4200000, "budget_spent": 1150000,
                "start_date": base, "target_completion_date": base + timedelta(days=420),
            }.items():
                if k in ic:
                    kwargs[k] = v
            init = StrategicInitiative(**kwargs)
            db.session.add(init); db.session.flush()

        # ---- Milestones (the 4 plateaus of the migration) ----
        MILES = [
            ("Foundation — BTP + Named Credentials + object model", 60, "completed"),
            ("Coexistence — bidirectional Customer Master sync live", 180, "in_progress"),
            ("Cutover — Salesforce as system of engagement", 300, "pending"),
            ("Optimise — retire Siebel + legacy billing", 420, "pending"),
        ]
        mc = colset(StrategicMilestone)
        for name, day, status in MILES:
            if not StrategicMilestone.query.filter_by(initiative_id=init.id, name=name).first():
                kwargs = {"initiative_id": init.id, "name": name}
                for k, v in {"due_date": base + timedelta(days=day), "status": status,
                             "description": name}.items():
                    if k in mc:
                        kwargs[k] = v
                db.session.add(StrategicMilestone(**kwargs))

        # ---- Link the SAP/SFDC solutions to the programme ----
        linked = 0
        for sid in (11, 9, 10, 8):
            s = Solution.query.get(sid)
            if s and getattr(s, "initiative_id", None) != init.id:
                s.initiative_id = init.id; linked += 1

        # ---- Roadmap plateaus ----
        pc = colset(Plateau)
        PLATEAUS = [
            ("Foundation", 1, 60), ("Coexistence", 2, 180),
            ("Cutover", 3, 300), ("Optimise", 4, 420),
        ]
        pmade = 0
        for name, seq, day in PLATEAUS:
            if not Plateau.query.filter_by(name=name, organization_id=org_id).first():
                kwargs = {"name": name}
                for k, v in {"description": f"{name} plateau of the Customer 360 programme",
                             "sequence_order": seq, "target_date": base + timedelta(days=day),
                             "organization_id": org_id,
                             "state_summary": f"{name} transition state"}.items():
                    if k in pc:
                        kwargs[k] = v
                db.session.add(Plateau(**kwargs)); pmade += 1

        db.session.commit()
        nmiles = StrategicMilestone.query.filter_by(initiative_id=init.id).count()
        print(f"PHASE5_OK initiative={init.id} milestones={nmiles} solutions_linked={linked} plateaus_new={pmade}")


if __name__ == "__main__":
    main()
