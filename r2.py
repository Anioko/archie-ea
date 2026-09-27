from manage import app
with app.app_context():
    from app.modules.codegen.models import CodegenGeneration
    fs = CodegenGeneration.query.filter_by(solution_id=11).first().generated_files or {}
    # lengths of all .cls + integration
    print("=== .cls file lengths ===")
    for p in sorted(fs):
        if p.endswith(".cls") or p.endswith(".trigger"):
            print("%6d  %s" % (len(fs[p] or ""), p))
    # any class mentioning callout/SAP/OData
    print("\n=== classes referencing SAP integration ===")
    for p, v in fs.items():
        if v and ("callout:" in v or "OData" in v or "sap/opu" in v):
            print("HIT", p, "len", len(v))
    # AccountService body
    acc = fs.get("force-app/main/default/classes/AccountService.cls") or ""
    print("\n===== AccountService.cls (len=%d) =====" % len(acc))
    print(acc[:1100])
    # count length None occurrences
    objs = [p for p in fs if p.endswith(".object-meta.xml")]
    bad = sum((fs[p] or "").count("<length>None</length>") for p in objs)
    print("\n<length>None</length> occurrences across objects:", bad)
