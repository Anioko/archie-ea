from manage import app
with app.app_context():
    from app.models.archimate import ArchiMateView
    vs = ArchiMateView.query.order_by(ArchiMateView.id.desc()).limit(12).all()
    print("XX N_VIEWS", len(vs))
    for v in vs:
        # find the json blob holding nodes
        cols = {c.name for c in v.__table__.columns}
        nodect = "?"
        for attr in ("canvas_data","state","diagram_json","content","view_data","data","nodes_json"):
            if attr in cols:
                val = getattr(v, attr)
                if val:
                    import json
                    try:
                        d = val if isinstance(val, dict) else json.loads(val)
                        nodect = len(d.get("nodes", []) if isinstance(d, dict) else [])
                    except Exception:
                        nodect = "raw%d" % len(str(val))
        print("XX VIEW", v.id, repr((getattr(v,'name','')or'')[:40]), "sol=", getattr(v,'solution_id',None), "nodes=", nodect, "cols=", sorted(cols))
