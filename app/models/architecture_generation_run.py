"""ArchitectureGenerationRun — one record per LLM generation attempt.

Created via db.create_all() (migration freeze respected).
Stores the engine_run_id UUID that stamps ArchiMateElement.acm_properties,
ArchiMateRelationship.connection_spec, and SolutionArchiMateElement.spec_data
so a pre-run cleanup can identify and remove unreviewed AI-derived artefacts
from a previous run before writing the new one.
"""

from datetime import datetime

from app import db


class ArchitectureGenerationRun(db.Model):
    __tablename__ = "architecture_generation_runs"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="running", nullable=False)
    # running | completed | failed | partial
    element_count = db.Column(db.Integer, default=0)
    relationship_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)

    solution = db.relationship("Solution", backref=db.backref("generation_runs", lazy="dynamic"))
