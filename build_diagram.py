# -*- coding: utf-8 -*-
"""Build a real, positioned ArchiMate canvas of the SAP <-> MuleSoft <-> Salesforce
Customer-Master integration seam, persisted as an ArchiMateView the Composer can load."""
from manage import app
from app import db

NODES = [
    # id, type, name, source_type, x, y, w, h
    ("n_drv",  "driver",               "Single source of customer truth", "motivation", 540, 30,  260, 84),
    ("n_goal", "goal",                 "Customer 360 golden record",       "motivation", 540, 150, 260, 84),
    ("n_sap",  "applicationcomponent", "SAP S/4HANA",                      "application_component", 80,  330, 220, 96),
    ("n_cpi",  "technologyservice",    "SAP BTP Integration Suite (CPI)",  "technology",            80,  470, 220, 84),
    ("n_mule", "applicationcomponent", "MuleSoft Anypoint Platform",       "application_component", 560, 350, 240, 96),
    ("n_sfdc", "applicationcomponent", "Salesforce Sales Cloud",           "application_component", 1080,330, 240, 96),
    ("n_cm",   "dataobject",           "Customer Master",                  "data_object", 300, 600, 200, 80),
    ("n_acc",  "dataobject",           "Account",                          "data_object", 720, 600, 180, 80),
    ("n_con",  "dataobject",           "Contact",                          "data_object", 980, 600, 180, 80),
]

CONNS = [
    # id, source, target, rel, label
    ("c1", "n_sap",  "n_mule", "flow",        "Business Partner OData"),
    ("c2", "n_mule", "n_sfdc", "flow",        "Account / Contact upsert"),
    ("c3", "n_cpi",  "n_mule", "serving",     "iFlow runtime"),
    ("c4", "n_sfdc", "n_acc",  "access",      "writes"),
    ("c5", "n_sfdc", "n_con",  "access",      "writes"),
    ("c6", "n_sap",  "n_cm",   "access",      "masters"),
    ("c7", "n_mule", "n_cm",   "access",      "reconciles"),
    ("c8", "n_goal", "n_sap",  "realization", None),
    ("c9", "n_drv",  "n_goal", "influence",   None),
]


def main():
    with app.app_context():
        from app.models.archimate import ArchiMateView
        from app.modules.solutions_strategic.v2.services.solution_composer_service import SolutionComposerService
        from app.models.user import User

        NAME = "SAP <-> Salesforce Customer Master Integration Seam"
        # remove a prior build of the same canvas so this is idempotent
        for old in ArchiMateView.query.filter_by(name=NAME).all():
            db.session.delete(old)
        db.session.commit()

        svc = SolutionComposerService()
        svc.create_canvas(name=NAME, description="Target integration architecture: SAP S/4HANA (system of record) <-> MuleSoft + SAP CPI (hub) <-> Salesforce (engagement). Customer Master golden record.")
        for nid, etype, name, stype, x, y, w, h in NODES:
            svc.add_node(node_id=nid, element_type=etype, name=name, source_type=stype,
                         position_x=float(x), position_y=float(y))
            # set width/height on the in-memory node
            for n in svc.current_canvas.nodes:
                if n.id == nid:
                    n.width = float(w); n.height = float(h)
        valid = 0
        for cid, s, t, rel, label in CONNS:
            r = svc.add_connection(connection_id=cid, source_node_id=s, target_node_id=t,
                                   relationship_type=rel, label=label)
            if r.get("connection", {}).get("is_valid") or r.get("is_valid"):
                valid += 1
        uid = (User.query.filter_by(email="demo@archiedemo.com").first() or User.query.first()).id
        res = svc.save_canvas(user_id=uid)
        cid = svc.current_canvas.canvas_id
        print(f"DIAGRAM_OK view_id={cid} nodes={len(svc.current_canvas.nodes)} connections={len(svc.current_canvas.connections)} save={res.get('message') or res}")


if __name__ == "__main__":
    main()
