from manage import app
from app import db
with app.app_context():
    from app.modules.codegen.models import CodegenGeneration
    g = CodegenGeneration.query.filter_by(solution_id=11).first()
    fs = g.generated_files or {}
    print("TYPE", type(fs).__name__, "N", len(fs))
    if isinstance(fs, dict):
        for key in ("force-app/main/default/classes/AccountService.cls",
                    "force-app/main/default/objects/Account__c/Account__c.object-meta.xml"):
            v = fs.get(key) or ""
            print("\n===== %s (len=%d) =====" % (key, len(v)))
            print(v[:1500])
