from datetime import datetime
from app.extensions import db

class GDPRRequest(db.Model):
    __tablename__ = "gdpr_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    request_type = db.Column(db.String(16), nullable=False)  # 'export' or 'delete'
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending, completed, failed
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<GDPRRequest {self.request_type} for user {self.user_id} ({self.status})>"