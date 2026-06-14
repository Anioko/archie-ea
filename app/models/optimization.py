from datetime import datetime

from .. import db


class OptimizationRun(db.Model):
    """Tracks portfolio optimization/rationalization runs."""

    __tablename__ = "optimization_runs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(
        db.String(32), default="pending", index=True
    )  # pending, running, completed, failed
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    # JSON context: objectives, constraints, input file refs
    context = db.Column(db.Text)
    # Results summary (JSON): recommendation count, estimated_savings, errors
    results = db.Column(db.Text)
    # LLM metadata / cost tracking
    llm_model = db.Column(db.String(128))
    llm_tokens_used = db.Column(db.Integer, default=0)
    llm_cost_estimate = db.Column(db.Numeric(12, 6), default=0)

    created_by = db.relationship("User", backref="optimization_runs")

    def mark_running(self):
        self.status = "running"
        self.started_at = datetime.utcnow()

    def mark_completed(self, results_json: str = None):
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        if results_json is not None:
            self.results = results_json

    def mark_failed(self, error_message: str = None):
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        if error_message:
            self.results = error_message

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "llm_model": self.llm_model,
            "llm_tokens_used": int(self.llm_tokens_used or 0),
            "llm_cost_estimate": float(self.llm_cost_estimate or 0),
        }
