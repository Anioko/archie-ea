from manage import app
with app.app_context():
    from app.models.strategic import StrategicInitiative, StrategicMilestone
    for M in (StrategicInitiative, StrategicMilestone):
        req=[c.name for c in M.__table__.columns if not c.nullable and c.default is None and not c.primary_key]
        print("XX", M.__name__, "REQ", req)
    try:
        from app.models.implementation_migration import Plateau
        print("XX Plateau ALL", [c.name for c in Plateau.__table__.columns])
    except Exception as e:
        print("XX Plateau err", repr(e))
    # how solutions link to an initiative
    from app.models.solution_models import Solution
    print("XX Solution has initiative_id:", "initiative_id" in [c.name for c in Solution.__table__.columns])
