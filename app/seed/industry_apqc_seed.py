from datetime import date

from app import db
from app.models.industry_apqc import IndustryAPQCFramework, IndustryAPQCProcess


def seed_industry_apqc():
    # Clear existing if any (simple, safe approach; in real seeds use migrations)
    IndustryAPQCProcess.query.delete()
    IndustryAPQCFramework.query.delete()
    db.session.commit()

    # Create sample frameworks
    mfg = IndustryAPQCFramework(
        industry_code="MFG",
        industry_name="Manufacturing",
        description="Discrete/Process manufacturing variant",
        pcf_version="1.0",
        release_date=date(2020, 1, 1),
    )
    bfs = IndustryAPQCFramework(
        industry_code="BFS",
        industry_name="Banking & Financial Services",
        description="Finance-oriented PCF variant",
        pcf_version="1.0",
        release_date=date(2020, 1, 1),
    )
    hcp = IndustryAPQCFramework(
        industry_code="HCP",
        industry_name="Healthcare Provider",
        description="Healthcare provider PCF variant",
        pcf_version="1.0",
        release_date=date(2020, 1, 1),
    )

    db.session.add_all([mfg, bfs, hcp])
    db.session.flush()

    # Sample processes for each
    mfg_p1 = IndustryAPQCProcess(
        industry_framework_id=mfg.id,
        industry_process_code="MFG-P1",
        industry_process_name="Manufacturing Order Management",
        industry_process_description="Plan, schedule, and execute orders",
        is_active=True,
    )

    bfs_p1 = IndustryAPQCProcess(
        industry_framework_id=bfs.id,
        industry_process_code="BFS-P1",
        industry_process_name="Vendor Evaluation & Selection",
        industry_process_description="Select vendors based on criteria",
        is_active=True,
    )

    hcp_p1 = IndustryAPQCProcess(
        industry_framework_id=hcp.id,
        industry_process_code="HCP-P1",
        industry_process_name="Clinical Pathway Mapping",
        industry_process_description="Map clinical pathways to capabilities",
        is_active=True,
    )

    db.session.add_all([mfg_p1, bfs_p1, hcp_p1])
    db.session.commit()

    print("Seeded Industry APQC Frameworks and Processes")


if __name__ == "__main__":
    seed_industry_apqc()
