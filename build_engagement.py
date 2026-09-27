# -*- coding: utf-8 -*-
"""Big-4 SAP+Salesforce engagement build: target architecture (connected ArchiMate diagram
with data objects + fields), motivation chain, initiative + plateaus — all on solution 11.
Idempotent. Run inside the server container."""
from manage import app
from app import db

SOL_ID = 11  # "SAP to Salesforce Integration Architecture (CPI + MuleSoft)"

# DataObjects with real fields (drives the Salesforce custom objects + Apex)
DATA_OBJECTS = [
    ("Account", "Salesforce Account — golden customer record synced from SAP Business Partner", [
        ("Name", "string", True), ("SAPCustomerId", "string", True), ("AccountNumber", "string", False),
        ("Industry", "string", False), ("AnnualRevenue", "decimal", False),
        ("BillingCountry", "string", False), ("Phone", "string", False), ("Website", "string", False),
    ]),
    ("Contact", "Salesforce Contact — person record synced from SAP Customer contact", [
        ("FirstName", "string", False), ("LastName", "string", True), ("Email", "string", True),
        ("Phone", "string", False), ("AccountId", "reference", True),
        ("SAPContactId", "string", False), ("MailingCountry", "string", False),
    ]),
    ("Customer Master", "Master-data golden record reconciling SAP S/4HANA and Salesforce", [
        ("CustomerId", "string", True), ("LegalName", "string", True), ("TaxId", "string", False),
        ("SystemOfRecord", "string", True), ("GoldenRecordStatus", "string", True),
        ("DunsNumber", "string", False), ("LastSyncedAt", "datetime", False),
    ]),
]

# ApplicationComponents / technology
COMPONENTS = [
    ("SAP S/4HANA", "ApplicationComponent", "Application", "Financial + order system of record (Business Partner master)"),
    ("Salesforce Sales Cloud", "ApplicationComponent", "Application", "Customer engagement + opportunity system of engagement"),
    ("MuleSoft Anypoint Platform", "ApplicationComponent", "Application", "Integration hub brokering SAP <-> Salesforce flows"),
    ("SAP BTP Integration Suite (CPI)", "TechnologyService", "Technology", "Cloud integration runtime for SAP-side iFlows"),
]

# Motivation chain
MOTIVATION = [
    ("Single source of customer truth", "Driver", "Motivation", "Fragmented customer data across SAP and Salesforce drives rework and risk"),
    ("Customer 360 golden record", "Goal", "Motivation", "One reconciled customer record mastered correctly across both stacks"),
    ("Bidirectional Customer Master sync", "Requirement", "Motivation", "Near-real-time, field-mapped, auditable sync of Customer/Account/Contact"),
]

# (source_name, target_name, rel_type)
RELS = [
    ("SAP S/4HANA", "MuleSoft Anypoint Platform", "Flow"),
    ("MuleSoft Anypoint Platform", "Salesforce Sales Cloud", "Flow"),
    ("SAP BTP Integration Suite (CPI)", "MuleSoft Anypoint Platform", "Serving"),
    ("Salesforce Sales Cloud", "Account", "Access"),
    ("Salesforce Sales Cloud", "Contact", "Access"),
    ("SAP S/4HANA", "Customer Master", "Access"),
    ("Bidirectional Customer Master sync", "Customer Master", "Realization"),
    ("Customer 360 golden record", "Bidirectional Customer Master sync", "Realization"),
    ("Single source of customer truth", "Customer 360 golden record", "Influence"),
    ("MuleSoft Anypoint Platform", "Customer Master", "Access"),
]


def main():
    with app.app_context():
        from app.models.solution_models import Solution, SolutionArchiMateElement
        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
        sol = Solution.query.get(SOL_ID)
        assert sol, "solution missing"

        arch = ArchitectureModel.query.filter_by(solution_id=SOL_ID).first()
        if not arch:
            arch = ArchitectureModel(name=f"Target Architecture (Solution {SOL_ID})", version="1.0", solution_id=SOL_ID)
            db.session.add(arch); db.session.flush()

        name_to_id = {}

        def make_elem(name, etype, layer, desc):
            e = ArchiMateElement.query.filter_by(name=name, type=etype).first()
            if not e:
                e = ArchiMateElement(name=name, type=etype, layer=layer, description=desc)
                db.session.add(e); db.session.flush()
            if getattr(e, "architecture_id", None) != arch.id:
                e.architecture_id = arch.id
            name_to_id[name] = e.id
            return e

        def link(e, spec=None, role="primary"):
            j = SolutionArchiMateElement.query.filter_by(solution_id=SOL_ID, element_id=e.id).first()
            if not j:
                j = SolutionArchiMateElement(solution_id=SOL_ID, element_id=e.id,
                    layer_type=e.layer, element_table="archimate_elements",
                    element_name=e.name, element_role=role)
                db.session.add(j)
            if spec is not None:
                j.spec_data = spec
            return j

        # DataObjects with fields
        for name, desc, fields in DATA_OBJECTS:
            e = make_elem(name, "DataObject", "Application", desc)
            spec = {"fields": [{"name": fn, "type": ft, "required": req} for fn, ft, req in fields]}
            link(e, spec=spec)

        # Components / tech
        for name, etype, layer, desc in COMPONENTS:
            e = make_elem(name, etype, layer, desc)
            link(e, role="supporting")

        # Motivation
        for name, etype, layer, desc in MOTIVATION:
            e = make_elem(name, etype, layer, desc)
            link(e, role="supporting")

        db.session.flush()

        # Relationships
        rel_made = 0
        for sname, tname, rtype in RELS:
            sid, tid = name_to_id.get(sname), name_to_id.get(tname)
            if not sid or not tid:
                continue
            ex = ArchiMateRelationship.query.filter_by(source_id=sid, target_id=tid, type=rtype).first()
            if not ex:
                db.session.add(ArchiMateRelationship(source_id=sid, target_id=tid, type=rtype,
                    architecture_id=arch.id, description=f"{sname} -> {tname}"))
                rel_made += 1

        # Advance ADM phase to E (Opportunities & Solutions — ready for build)
        sol.adm_phase = "E"
        db.session.commit()

        n_elems = SolutionArchiMateElement.query.filter_by(solution_id=SOL_ID).count()
        n_rels = ArchiMateRelationship.query.filter_by(architecture_id=arch.id).count()
        print(f"BUILD_OK solution={SOL_ID} arch_model={arch.id} linked_elements={n_elems} relationships={n_rels} new_rels={rel_made}")


if __name__ == "__main__":
    main()
