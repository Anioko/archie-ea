import os

from sqlalchemy.orm import relationship

from .. import db

_FAST_INIT = os.getenv("APP_FAST_INIT", "0") == "1"


if not _FAST_INIT:
    # Full models live in the monolithic module.
    from .models import Outcome, Principle  # noqa: F401
else:

    class Outcome(db.Model):
        __tablename__ = "outcomes"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(255), nullable=False)
        description = db.Column(db.Text)

        # Note: relationship() connections to ArchiMate elements can be added as needed

        def __repr__(self):
            return f"<Outcome {self.name}>"

    class Principle(db.Model):
        __tablename__ = "principles"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(255), nullable=False)
        statement = db.Column(db.Text, nullable=True)
        rationale = db.Column(db.Text, nullable=True)
        implications = db.Column(db.Text, nullable=True)
        category = db.Column(db.String(50), nullable=True)
        enforcement_level = db.Column(db.String(20), nullable=True)
        enforcement_status = db.Column(db.String(20), nullable=False, default='advisory')  # mandatory/advisory/retired
        adm_phase = db.Column(db.String(5), nullable=True)  # e.g. 'A', 'B', 'D'

        def __repr__(self):
            return f"<Principle {self.name}>"
