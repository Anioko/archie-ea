"""BA-002: APQC PCF L1-L3 process hierarchy seed data."""
from app import db
from app.models.models import ApqcProcessHierarchy


HIERARCHY_DATA = [
    # (code, name, level, parent_code, ref)
    # L1
    ("1.0", "Develop and Manage Products and Services", 1, None, "1"),
    ("2.0", "Market and Sell Products and Services", 1, None, "2"),
    ("3.0", "Deliver Products and Services", 1, None, "3"),
    ("4.0", "Manage Customer Service", 1, None, "4"),
    ("5.0", "Develop and Manage Human Capital", 1, None, "5"),
    ("6.0", "Manage Information Technology", 1, None, "6"),
    ("7.0", "Manage Financial Resources", 1, None, "7"),
    ("8.0", "Acquire, Construct, and Manage Assets", 1, None, "8"),
    ("9.0", "Manage Environmental Health and Safety", 1, None, "9"),
    ("10.0", "Manage External Relationships", 1, None, "10"),
    ("11.0", "Develop and Manage Business Capabilities", 1, None, "11"),
    ("12.0", "Manage Knowledge, Improvement, and Change", 1, None, "12"),
    # L2 under 1.0
    ("1.1", "Manage product and service portfolio", 2, "1.0", "1.1"),
    ("1.2", "Develop products and services", 2, "1.0", "1.2"),
    ("1.3", "Deliver products and services", 2, "1.0", "1.3"),
    ("1.4", "Manage product and service life cycle", 2, "1.0", "1.4"),
    # L2 under 2.0
    ("2.1", "Understand markets, customers, and capabilities", 2, "2.0", "2.1"),
    ("2.2", "Develop marketing strategy", 2, "2.0", "2.2"),
    ("2.3", "Develop sales strategy", 2, "2.0", "2.3"),
    ("2.4", "Develop and manage marketing plans", 2, "2.0", "2.4"),
    ("2.5", "Develop and manage sales plans", 2, "2.0", "2.5"),
    # L2 under 3.0
    ("3.1", "Plan and manage supply chain", 2, "3.0", "3.1"),
    ("3.2", "Procure materials and services", 2, "3.0", "3.2"),
    ("3.3", "Produce/manufacture/deliver product", 2, "3.0", "3.3"),
    ("3.4", "Deliver service to customer", 2, "3.0", "3.4"),
    ("3.5", "Manage logistics and warehousing", 2, "3.0", "3.5"),
    # L2 under 4.0
    ("4.1", "Develop customer care/customer service strategy", 2, "4.0", "4.1"),
    ("4.2", "Plan and manage customer service operations", 2, "4.0", "4.2"),
    ("4.3", "Measure and evaluate customer service operations", 2, "4.0", "4.3"),
    # L2 under 5.0
    ("5.1", "Develop and manage human resources (HR) planning", 2, "5.0", "5.1"),
    ("5.2", "Recruit, source, and select employees", 2, "5.0", "5.2"),
    ("5.3", "Develop and counsel employees", 2, "5.0", "5.3"),
    ("5.4", "Reward and retain employees", 2, "5.0", "5.4"),
    ("5.5", "Redeploy and retire employees", 2, "5.0", "5.5"),
    ("5.6", "Manage employee information and analytics", 2, "5.0", "5.6"),
    # L2 under 6.0
    ("6.1", "Manage the business of IT", 2, "6.0", "6.1"),
    ("6.2", "Develop and manage IT customer relationships", 2, "6.0", "6.2"),
    ("6.3", "Develop and implement security, privacy, and data protection", 2, "6.0", "6.3"),
    ("6.4", "Manage enterprise information", 2, "6.0", "6.4"),
    ("6.5", "Develop and maintain IT solutions", 2, "6.0", "6.5"),
    ("6.6", "Deploy IT solutions", 2, "6.0", "6.6"),
    ("6.7", "Deliver and support IT services", 2, "6.0", "6.7"),
    # L2 under 7.0
    ("7.1", "Plan and manage enterprise finances", 2, "7.0", "7.1"),
    ("7.2", "Process revenue and receipts", 2, "7.0", "7.2"),
    ("7.3", "Process payables and expense reimbursements", 2, "7.0", "7.3"),
    ("7.4", "Manage payroll", 2, "7.0", "7.4"),
    ("7.5", "Manage treasury and risk", 2, "7.0", "7.5"),
    ("7.6", "Manage internal controls", 2, "7.0", "7.6"),
    ("7.7", "Manage taxes", 2, "7.0", "7.7"),
    # L2 under 8.0
    ("8.1", "Plan and manage assets", 2, "8.0", "8.1"),
    ("8.2", "Design and construct/acquire productive assets", 2, "8.0", "8.2"),
    ("8.3", "Maintain productive assets", 2, "8.0", "8.3"),
    ("8.4", "Retire and dispose of assets", 2, "8.0", "8.4"),
    # L2 under 9.0
    ("9.1", "Formulate EHS strategy and policies", 2, "9.0", "9.1"),
    ("9.2", "Ensure compliance with regulations", 2, "9.0", "9.2"),
    ("9.3", "Manage environmental programs", 2, "9.0", "9.3"),
    ("9.4", "Manage health and safety programs", 2, "9.0", "9.4"),
    # L2 under 10.0
    ("10.1", "Build investor relationships", 2, "10.0", "10.1"),
    ("10.2", "Manage government and industry relationships", 2, "10.0", "10.2"),
    ("10.3", "Manage relations with board of directors", 2, "10.0", "10.3"),
    ("10.4", "Manage legal and ethical issues", 2, "10.0", "10.4"),
    ("10.5", "Manage public relations program", 2, "10.0", "10.5"),
    # L2 under 11.0
    ("11.1", "Manage business architecture", 2, "11.0", "11.1"),
    ("11.2", "Manage portfolio, programmes, and projects", 2, "11.0", "11.2"),
    ("11.3", "Manage enterprise risk", 2, "11.0", "11.3"),
    ("11.4", "Manage business process improvement", 2, "11.0", "11.4"),
    # L2 under 12.0
    ("12.1", "Create and manage organisational knowledge", 2, "12.0", "12.1"),
    ("12.2", "Manage improvement initiatives", 2, "12.0", "12.2"),
    ("12.3", "Implement management of change", 2, "12.0", "12.3"),
    # L3 samples under 1.1, 1.2
    ("1.1.1", "Define product/service portfolio strategy", 3, "1.1", "1.1.1"),
    ("1.1.2", "Conduct competitive analysis for product portfolio", 3, "1.1", "1.1.2"),
    ("1.2.1", "Perform product/service research and development", 3, "1.2", "1.2.1"),
    ("1.2.2", "Design and prototype product/service", 3, "1.2", "1.2.2"),
    ("1.2.3", "Test and evaluate product/service", 3, "1.2", "1.2.3"),
    # L3 samples under 6.5, 6.7
    ("6.5.1", "Develop and maintain application software", 3, "6.5", "6.5.1"),
    ("6.5.2", "Develop and maintain IT infrastructure", 3, "6.5", "6.5.2"),
    ("6.7.1", "Manage IT helpdesk and incident management", 3, "6.7", "6.7.1"),
    ("6.7.2", "Manage IT change and release", 3, "6.7", "6.7.2"),
    # L3 samples under 7.1
    ("7.1.1", "Perform planning and budgeting", 3, "7.1", "7.1.1"),
    ("7.1.2", "Perform financial analysis and reporting", 3, "7.1", "7.1.2"),
    # L3 samples under 5.2, 5.3
    ("5.2.1", "Define employee sourcing strategy", 3, "5.2", "5.2.1"),
    ("5.2.2", "Screen candidates", 3, "5.2", "5.2.2"),
    ("5.3.1", "Manage employee performance", 3, "5.3", "5.3.1"),
    ("5.3.2", "Develop and train employees", 3, "5.3", "5.3.2"),
]


def seed_hierarchy():
    """Seed APQC PCF L1-L3 hierarchy. Idempotent — skips existing codes."""
    existing_codes = {
        row[0] for row in db.session.query(ApqcProcessHierarchy.code).all()
    }

    if len(existing_codes) >= len(HIERARCHY_DATA):
        return {"status": "already_seeded", "rows": len(existing_codes)}

    # First pass: create all nodes without parent FKs
    code_to_id = {}
    for code, name, level, parent_code, ref in HIERARCHY_DATA:
        if code in existing_codes:
            row = db.session.query(ApqcProcessHierarchy).filter_by(code=code).first()
            code_to_id[code] = row.id
            continue
        node = ApqcProcessHierarchy(
            code=code,
            name=name,
            level=level,
            parent_id=None,
            apqc_reference_number=ref,
        )
        db.session.add(node)
    db.session.flush()

    # Refresh code_to_id
    for row in db.session.query(ApqcProcessHierarchy).all():
        code_to_id[row.code] = row.id

    # Second pass: set parent FKs
    for code, name, level, parent_code, ref in HIERARCHY_DATA:
        if parent_code and code in code_to_id and parent_code in code_to_id:
            node = db.session.query(ApqcProcessHierarchy).filter_by(code=code).first()
            if node and node.parent_id is None and parent_code is not None:
                node.parent_id = code_to_id[parent_code]

    db.session.commit()
    return {"status": "seeded", "rows": len(HIERARCHY_DATA)}
