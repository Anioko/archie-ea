"""
SolutionCodeBundle — Tracks generated code bundles for solutions.

Wave 1: One row per generation. Stores metadata only (not the files).
Files are regenerated deterministically from the same spec_hash.
"""
from app import db


class SolutionCodeBundle(db.Model):
    __tablename__ = "solution_code_bundles"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bundle_id = db.Column(db.String(64), nullable=False, unique=True)
    language = db.Column(db.String(30), nullable=False, default="python-fastapi")
    spec_hash = db.Column(db.String(64))
    status = db.Column(db.String(20), default="generated")
    file_count = db.Column(db.Integer)
    test_summary = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    solution = db.relationship(
        "Solution",
        backref=db.backref("code_bundles", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<SolutionCodeBundle {self.bundle_id} for solution {self.solution_id}>"
