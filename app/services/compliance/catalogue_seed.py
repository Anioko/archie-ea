"""
Seed data for the regulatory framework catalogue.

Seeds ISO/IEC 27001, SOC 2, and DORA with clause identifiers and control
summaries — not full copyrighted framework text.  These are reference rows
(organization_id IS NULL, scope='reference') visible to all tenants.
"""

from datetime import datetime, timedelta

from app import db
from app.models.compliance_models import ComplianceControl, RegulatoryFramework


CATALOGUE_FRAMEWORKS = [
    {
        "code": "ISO-27001",
        "name": "ISO/IEC 27001:2022 — Information Security Management",
        "description": (
            "International standard for establishing, implementing, maintaining "
            "and continually improving an information security management system (ISMS)."
        ),
        "category": "security",
        "jurisdiction": "Global",
        "enforcement_level": "recommended",
        "penalty_risk": "medium",
        "applies_to_manufacturing": True,
        "applies_to_region": "Global",
        "industry_specific": "general",
        "official_url": "https://www.iso.org/standard/27001",
        "standard_version": "2022",
        "controls": [
            {"control_code": "A.5.1", "title": "Policies for information security",
             "description": "Management shall define, approve and publish an information security policy.",
             "category": "Organisational controls", "priority": "high"},
            {"control_code": "A.5.2", "title": "Information security roles and responsibilities",
             "description": "Information security responsibilities shall be defined and allocated.",
             "category": "Organisational controls", "priority": "high"},
            {"control_code": "A.5.7", "title": "Threat intelligence",
             "description": "Information relating to information security threats shall be collected and analysed.",
             "category": "Organisational controls", "priority": "medium"},
            {"control_code": "A.6.1", "title": "Screening",
             "description": "Background verification checks on all candidates shall be carried out.",
             "category": "People controls", "priority": "medium"},
            {"control_code": "A.6.3", "title": "Information security awareness, education and training",
             "description": "Personnel shall receive appropriate awareness education and training.",
             "category": "People controls", "priority": "medium"},
            {"control_code": "A.7.2", "title": "Physical entry",
             "description": "Secure areas shall be protected by appropriate entry controls.",
             "category": "Physical controls", "priority": "medium"},
            {"control_code": "A.8.1", "title": "User endpoint devices",
             "description": "Information stored on, processed by or accessible via user endpoint devices shall be protected.",
             "category": "Technological controls", "priority": "high"},
            {"control_code": "A.8.2", "title": "Privileged access rights",
             "description": "The allocation and use of privileged access rights shall be restricted and managed.",
             "category": "Technological controls", "priority": "critical"},
            {"control_code": "A.8.3", "title": "Information access restriction",
             "description": "Access to information shall be restricted in accordance with the access control policy.",
             "category": "Technological controls", "priority": "high"},
            {"control_code": "A.8.8", "title": "Management of technical vulnerabilities",
             "description": "Information about technical vulnerabilities shall be obtained and evaluated.",
             "category": "Technological controls", "priority": "high"},
            {"control_code": "A.8.9", "title": "Configuration management",
             "description": "Configurations of hardware, software, services and networks shall be established and maintained.",
             "category": "Technological controls", "priority": "medium"},
            {"control_code": "A.8.12", "title": "Data leakage prevention",
             "description": "Data leakage prevention measures shall be applied to systems that process sensitive information.",
             "category": "Technological controls", "priority": "high"},
            {"control_code": "A.8.15", "title": "Logging",
             "description": "Logs that record activities, exceptions, faults and other relevant events shall be produced and kept.",
             "category": "Technological controls", "priority": "high"},
            {"control_code": "A.8.16", "title": "Monitoring activities",
             "description": "Networks, systems and applications shall be monitored for anomalous behaviour.",
             "category": "Technological controls", "priority": "medium"},
            {"control_code": "A.8.24", "title": "Use of cryptography",
             "description": "Rules for the effective use of cryptography shall be defined and implemented.",
             "category": "Technological controls", "priority": "high"},
        ],
    },
    {
        "code": "SOC-2",
        "name": "AICPA SOC 2 — Trust Services Criteria",
        "description": (
            "Service Organisation Control 2 framework for managing customer data "
            "based on five trust service criteria: security, availability, "
            "processing integrity, confidentiality and privacy."
        ),
        "category": "security",
        "jurisdiction": "US",
        "enforcement_level": "recommended",
        "penalty_risk": "medium",
        "applies_to_manufacturing": True,
        "applies_to_region": "Global",
        "industry_specific": "general",
        "official_url": "https://www.aicpa.org/soc",
        "standard_version": "2017",
        "controls": [
            {"control_code": "CC1.1", "title": "COSO Principle 1 — Integrity and ethical values",
             "description": "The entity demonstrates a commitment to integrity and ethical values.",
             "category": "Common Criteria", "priority": "high"},
            {"control_code": "CC1.2", "title": "COSO Principle 2 — Board independence and oversight",
             "description": "The board of directors demonstrates independence from management and exercises oversight.",
             "category": "Common Criteria", "priority": "medium"},
            {"control_code": "CC2.1", "title": "COSO Principle 13 — Use of relevant information",
             "description": "The entity obtains or generates and uses relevant, quality information to support internal control.",
             "category": "Common Criteria", "priority": "medium"},
            {"control_code": "CC3.1", "title": "COSO Principle 14 — Internal communication",
             "description": "The entity internally communicates information to support internal control.",
             "category": "Common Criteria", "priority": "medium"},
            {"control_code": "CC4.1", "title": "COSO Principle 16 — Monitoring activities",
             "description": "The entity selects, develops and performs ongoing evaluations of controls.",
             "category": "Common Criteria", "priority": "medium"},
            {"control_code": "CC5.1", "title": "COSO Principle 17 — Evaluation of deficiencies",
             "description": "The entity evaluates and communicates internal control deficiencies in a timely manner.",
             "category": "Common Criteria", "priority": "medium"},
            {"control_code": "CC6.1", "title": "Logical and physical access controls",
             "description": "The entity implements logical and physical access controls to protect assets.",
             "category": "Security", "priority": "critical"},
            {"control_code": "CC6.2", "title": "User access provisioning",
             "description": "Access to system resources is provisioned based on authorised user roles.",
             "category": "Security", "priority": "high"},
            {"control_code": "CC6.3", "title": "Security awareness and training",
             "description": "Personnel responsible for security are provided with appropriate training.",
             "category": "Security", "priority": "medium"},
            {"control_code": "CC6.6", "title": "External communication threats",
             "description": "The entity implements controls to detect and mitigate threats from external communications.",
             "category": "Security", "priority": "high"},
            {"control_code": "CC6.7", "title": "Data encryption and transmission",
             "description": "The entity encrypts sensitive data at rest and in transit.",
             "category": "Security", "priority": "high"},
            {"control_code": "CC7.1", "title": "Change detection and monitoring",
             "description": "The entity detects changes to the system that may affect security.",
             "category": "Availability", "priority": "high"},
            {"control_code": "CC7.2", "title": "Incident response",
             "description": "The entity has procedures to respond to security incidents.",
             "category": "Availability", "priority": "high"},
            {"control_code": "CC8.1", "title": "Change management authorisation",
             "description": "The entity authorises, designs, develops and tests system changes.",
             "category": "Processing Integrity", "priority": "medium"},
            {"control_code": "CC9.1", "title": "Confidential information identification",
             "description": "The entity identifies and maintains confidential information.",
             "category": "Confidentiality", "priority": "high"},
        ],
    },
    {
        "code": "DORA",
        "name": "EU Digital Operational Resilience Act (DORA)",
        "description": (
            "EU regulation on digital operational resilience for the financial sector, "
            "covering ICT risk management, incident reporting, digital operational "
            "resilience testing and third-party risk."
        ),
        "category": "security",
        "jurisdiction": "EU",
        "enforcement_level": "mandatory",
        "penalty_risk": "high",
        "applies_to_manufacturing": False,
        "applies_to_region": "EU",
        "industry_specific": "financial",
        "official_url": "https://eur-lex.europa.eu/eli/reg/2022/2554",
        "standard_version": "2022",
        "controls": [
            {"control_code": "DORA-Art.5", "title": "ICT governance and organisation",
             "description": "The management body shall define and oversee the ICT risk management framework.",
             "category": "ICT Risk Management", "priority": "critical"},
            {"control_code": "DORA-Art.6", "title": "ICT risk management framework",
             "description": "A sound ICT risk management framework shall be established as part of the overall risk management system.",
             "category": "ICT Risk Management", "priority": "critical"},
            {"control_code": "DORA-Art.7", "title": "ICT systems, protocols and tools",
             "description": "ICT systems and tools shall be identified, classified and adequately protected.",
             "category": "ICT Risk Management", "priority": "high"},
            {"control_code": "DORA-Art.8", "title": "Identification of ICT-related incidents",
             "description": "Mechanisms to promptly detect anomalous activities and ICT-related incidents shall be in place.",
             "category": "ICT Risk Management", "priority": "high"},
            {"control_code": "DORA-Art.9", "title": "Protection and prevention",
             "description": "Measures shall be in place to protect ICT systems and prevent incidents.",
             "category": "ICT Risk Management", "priority": "high"},
            {"control_code": "DORA-Art.10", "title": "Detection",
             "description": "Mechanisms to promptly detect anomalous activities shall be in place.",
             "category": "ICT Risk Management", "priority": "high"},
            {"control_code": "DORA-Art.11", "title": "Response and recovery",
             "description": "Comprehensive ICT business continuity policies and disaster recovery plans shall be in place.",
             "category": "ICT Risk Management", "priority": "critical"},
            {"control_code": "DORA-Art.12", "title": "Backup policies and restoration",
             "description": "Backup policies and restoration and recovery procedures shall be established.",
             "category": "ICT Risk Management", "priority": "high"},
            {"control_code": "DORA-Art.13", "title": "Learning and evolving",
             "description": "Capabilities and staff shall be kept up to date with evolving ICT risk.",
             "category": "ICT Risk Management", "priority": "medium"},
            {"control_code": "DORA-Art.15", "title": "ICT incident management process",
             "description": "An ICT incident management process shall be established to detect, manage and notify ICT-related incidents.",
             "category": "Incident Reporting", "priority": "critical"},
            {"control_code": "DORA-Art.17", "title": "Classification of ICT-related incidents",
             "description": "ICT-related incidents shall be classified based on criteria including impact and duration.",
             "category": "Incident Reporting", "priority": "high"},
            {"control_code": "DORA-Art.19", "title": "Reporting of major incidents",
             "description": "Major ICT-related incidents shall be reported to the competent authority.",
             "category": "Incident Reporting", "priority": "critical"},
            {"control_code": "DORA-Art.24", "title": "Digital operational resilience testing",
             "description": "A comprehensive digital operational resilience testing programme shall be established.",
             "category": "Resilience Testing", "priority": "high"},
            {"control_code": "DORA-Art.26", "title": "Threat-led penetration testing",
             "description": "Advanced threat-led penetration testing shall be carried out at least every three years.",
             "category": "Resilience Testing", "priority": "high"},
            {"control_code": "DORA-Art.28", "title": "Third-party ICT risk strategy",
             "description": "A strategy on ICT third-party risk shall be established and regularly reviewed.",
             "category": "Third-Party Risk", "priority": "critical"},
        ],
    },
]


def seed_catalogue_frameworks():
    """Seed the shared catalogue with ISO 27001, SOC 2 and DORA.

    Idempotent: skips frameworks whose code already exists.
    Returns the number of frameworks newly seeded.
    """
    seeded = 0
    for fw_data in CATALOGUE_FRAMEWORKS:
        existing = RegulatoryFramework.query.filter_by(code=fw_data["code"]).first()
        if existing:
            continue
        controls_data = fw_data.pop("controls", [])
        framework = RegulatoryFramework(**fw_data)
        framework.last_updated = datetime.utcnow()
        framework.next_review_date = datetime.utcnow() + timedelta(days=365)
        db.session.add(framework)
        db.session.flush()
        for ctl_data in controls_data:
            control = ComplianceControl(framework_id=framework.id, **ctl_data)
            db.session.add(control)
        seeded += 1
    if seeded:
        db.session.commit()
    return seeded