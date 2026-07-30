from manage import app
with app.app_context():
    from app.modules.codegen.models import CodegenGeneration
    fs = CodegenGeneration.query.filter_by(solution_id=11).first().generated_files or {}
    print("TOTAL", len(fs))
    sapint = [p for p in fs if "SapIntegration" in p]
    print("SAP_INTEGRATION_CLASS:", sapint)
    badlen = sum((fs[p] or "").count("<length>None</length>") for p in fs if p.endswith(".object-meta.xml"))
    print("length_None_count:", badlen)
    callouts = [p for p in fs if (fs[p] and ("callout:" in fs[p] or "/sap/opu/odata/" in fs[p]))]
    print("FILES_WITH_SAP_CALLOUT:", callouts)
    if sapint:
        c = fs[sapint[0]]
        print("\n===== %s (len=%d) =====" % (sapint[0], len(c)))
        print(c[:1600])
