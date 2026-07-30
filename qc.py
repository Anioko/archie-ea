from manage import app
with app.app_context():
    import importlib, pkgutil
    found=False
    for modname in ["app.models.solution_composer_models","app.models.composer_models","app.models.solution_composer"]:
        try:
            m=importlib.import_module(modname)
            print("XX module", modname, [n for n in dir(m) if "Canvas" in n or "Node" in n or "Connection" in n])
            found=True
        except Exception as e:
            pass
