from datetime import datetime
from app.extensions import db
from app.models.user import User
from app.models.gdpr_request import GDPRRequest
from app.models.audit_log import AuditLog

class GDPRService:
    @staticmethod
    def export_user_data(user_id):
        user = User.query.get(user_id)
        if not user:
            return None
        # Collect user profile
        user_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "organization_id": user.organization_id,
            "created_at": getattr(user, "created_at", None),
            "deleted_at": getattr(user, "deleted_at", None),
        }
        # TODO: Add activities, content, etc. as needed
        return {"profile": user_data}

    @staticmethod
    def delete_user_data(user_id, requester_id):
        user = User.query.get(user_id)
        if not user:
            return False
        # Anonymize PII
        user.email = None
        user.first_name = None
        user.last_name = None
        user.deleted_at = datetime.utcnow()
        # Set status if present
        if hasattr(user, "status"):
            user.status = "deleted"
        db.session.add(user)
        db.session.commit()
        # Log to audit
        AuditLog.log(
            user_id=requester_id,
            table_name="users",
            record_id=user_id,
            action="gdpr_delete",
            new_value={"details": "User data anonymized for GDPR deletion"}
        )
        return True

    @staticmethod
    def get_request_status(user_id):
        req = GDPRRequest.query.filter_by(user_id=user_id).order_by(GDPRRequest.requested_at.desc()).first()
        if not req:
            return {"status": "none"}
        return {"status": req.status, "type": req.request_type, "requested_at": req.requested_at, "completed_at": req.completed_at}
