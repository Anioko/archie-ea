import os

from .. import db

_FAST_INIT = os.getenv("APP_FAST_INIT", "0") == "1"


if not _FAST_INIT:
    # Full model lives in the monolithic module.
    from .models import TechnologyStack  # noqa: F401
else:

    class TechnologyStack(db.Model):
        __tablename__ = "technology_stacks"
        __table_args__ = {"extend_existing": True}

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        description = db.Column(db.Text)
        platform = db.Column(db.String(50))

        def __repr__(self):
            return f"<TechnologyStack {self.name}>"
