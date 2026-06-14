"""
ARB Exception Service

Manages exception/waiver requests against governance standards.
Handles the full lifecycle: request, review, approve/deny, renewal, expiration.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app import db
from app.models.architecture_review_board import (
    ARBException,
    ARBExceptionStatus,
    ARBGovernanceStandard,
    ARBReviewItem,
)
from app.services.arb_audit_service import arb_audit_service

logger = logging.getLogger(__name__)


class ARBExceptionService:
    """
    Service for managing ARB exception/waiver requests.

    Handles:
    - Exception request creation
    - Review and approval workflow
    - Expiration tracking
    - Renewal processing
    - Exception reporting
    """

    # Default exception duration in days by type
    DEFAULT_DURATIONS = {
        "waiver": 365,
        "deviation": 180,
        "temporary_exemption": 90,
    }

    def __init__(self):
        pass

    def create_exception_request(
        self,
        standard_id: int,
        exception_reason: str,
        requested_by_id: int,
        review_item_id: int = None,
        exception_type: str = "waiver",
        business_justification: str = None,
        risk_mitigation: str = None,
        scope: str = None,
        requested_duration_days: int = None,
    ) -> Dict[str, Any]:
        """
        Create a new exception request.

        Args:
            standard_id: ID of the governance standard
            exception_reason: Reason for requesting exception
            requested_by_id: ID of user making request
            review_item_id: Optional linked review item
            exception_type: Type of exception (waiver, deviation, temporary_exemption)
            business_justification: Business case for exception
            risk_mitigation: How risks will be mitigated
            scope: Scope of the exception
            requested_duration_days: Requested duration

        Returns:
            Dictionary with exception details or error
        """
        # Validate standard exists
        standard = db.session.get(ARBGovernanceStandard, standard_id)
        if not standard:
            return {"success": False, "error": f"Governance standard {standard_id} not found"}

        # Validate review item if provided
        if review_item_id:
            review_item = db.session.get(ARBReviewItem, review_item_id)
            if not review_item:
                return {"success": False, "error": f"Review item {review_item_id} not found"}

        # Generate exception number
        exception_number = ARBException.generate_exception_number()

        # Calculate expiration date
        duration = requested_duration_days or self.DEFAULT_DURATIONS.get(exception_type, 180)
        expires_at = datetime.utcnow() + timedelta(days=duration)

        # Create exception
        exception = ARBException(
            exception_number=exception_number,
            review_item_id=review_item_id,
            standard_id=standard_id,
            exception_type=exception_type,
            exception_reason=exception_reason,
            business_justification=business_justification,
            risk_mitigation=risk_mitigation,
            scope=scope,
            status=ARBExceptionStatus.REQUESTED.value,
            requested_by_id=requested_by_id,
            requested_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        db.session.add(exception)
        db.session.commit()

        # Log audit event
        arb_audit_service.log_exception_request(
            exception=exception,
            user_id=requested_by_id,
        )

        logger.info(f"Created exception request {exception_number} for standard {standard.code}")

        return {
            "success": True,
            "exception_id": exception.id,
            "exception_number": exception_number,
            "status": exception.status,
            "expires_at": expires_at.isoformat(),
        }

    def submit_for_review(
        self,
        exception_id: int,
        reviewer_id: int,
    ) -> Dict[str, Any]:
        """
        Submit exception for review.

        Args:
            exception_id: ID of the exception
            reviewer_id: ID of reviewer to assign

        Returns:
            Updated exception status
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return {"success": False, "error": "Exception not found"}

        if exception.status != ARBExceptionStatus.REQUESTED.value:
            return {
                "success": False,
                "error": f"Cannot submit exception in {exception.status} status",
            }

        old_status = exception.status
        exception.status = ARBExceptionStatus.UNDER_REVIEW.value
        exception.reviewed_by_id = reviewer_id
        exception.updated_at = datetime.utcnow()

        db.session.commit()

        # Log status change
        arb_audit_service.log_action(
            entity_type="exception",
            entity_id=exception.id,
            action="status_change",
            user_id=reviewer_id,
            old_value={"status": old_status},
            new_value={"status": exception.status},
            description=f"Exception {exception.exception_number} submitted for review",
        )

        return {
            "success": True,
            "exception_id": exception.id,
            "exception_number": exception.exception_number,
            "status": exception.status,
        }

    def approve_exception(
        self,
        exception_id: int,
        approved_by_id: int,
        approval_notes: str = None,
        new_expires_at: datetime = None,
    ) -> Dict[str, Any]:
        """
        Approve an exception request.

        Args:
            exception_id: ID of the exception
            approved_by_id: ID of approver
            approval_notes: Optional approval notes
            new_expires_at: Optional override for expiration date

        Returns:
            Updated exception status
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return {"success": False, "error": "Exception not found"}

        if exception.status not in [
            ARBExceptionStatus.REQUESTED.value,
            ARBExceptionStatus.UNDER_REVIEW.value,
        ]:
            return {
                "success": False,
                "error": f"Cannot approve exception in {exception.status} status",
            }

        old_status = exception.status
        exception.status = ARBExceptionStatus.APPROVED.value
        exception.approved_by_id = approved_by_id
        exception.approved_at = datetime.utcnow()
        exception.approval_notes = approval_notes
        exception.updated_at = datetime.utcnow()

        if new_expires_at:
            exception.expires_at = new_expires_at

        db.session.commit()

        # Log decision
        arb_audit_service.log_exception_decision(
            exception=exception,
            decision="approved",
            user_id=approved_by_id,
            notes=approval_notes,
        )

        logger.info(f"Exception {exception.exception_number} approved by user {approved_by_id}")

        return {
            "success": True,
            "exception_id": exception.id,
            "exception_number": exception.exception_number,
            "status": exception.status,
            "expires_at": exception.expires_at.isoformat() if exception.expires_at else None,
        }

    def deny_exception(
        self,
        exception_id: int,
        denied_by_id: int,
        denial_reason: str,
    ) -> Dict[str, Any]:
        """
        Deny an exception request.

        Args:
            exception_id: ID of the exception
            denied_by_id: ID of denier
            denial_reason: Reason for denial

        Returns:
            Updated exception status
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return {"success": False, "error": "Exception not found"}

        if exception.status not in [
            ARBExceptionStatus.REQUESTED.value,
            ARBExceptionStatus.UNDER_REVIEW.value,
        ]:
            return {
                "success": False,
                "error": f"Cannot deny exception in {exception.status} status",
            }

        old_status = exception.status
        exception.status = ARBExceptionStatus.DENIED.value
        exception.denied_by_id = denied_by_id
        exception.denied_at = datetime.utcnow()
        exception.denial_reason = denial_reason
        exception.updated_at = datetime.utcnow()

        db.session.commit()

        # Log decision
        arb_audit_service.log_exception_decision(
            exception=exception,
            decision="denied",
            user_id=denied_by_id,
            notes=denial_reason,
        )

        logger.info(f"Exception {exception.exception_number} denied by user {denied_by_id}")

        return {
            "success": True,
            "exception_id": exception.id,
            "exception_number": exception.exception_number,
            "status": exception.status,
        }

    def revoke_exception(
        self,
        exception_id: int,
        revoked_by_id: int,
        revocation_reason: str,
    ) -> Dict[str, Any]:
        """
        Revoke an approved exception.

        Args:
            exception_id: ID of the exception
            revoked_by_id: ID of user revoking
            revocation_reason: Reason for revocation

        Returns:
            Updated exception status
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return {"success": False, "error": "Exception not found"}

        if exception.status != ARBExceptionStatus.APPROVED.value:
            return {"success": False, "error": "Can only revoke approved exceptions"}

        old_status = exception.status
        exception.status = ARBExceptionStatus.REVOKED.value
        exception.revoked_by_id = revoked_by_id
        exception.revoked_at = datetime.utcnow()
        exception.revocation_reason = revocation_reason
        exception.updated_at = datetime.utcnow()

        db.session.commit()

        # Log revocation
        arb_audit_service.log_action(
            entity_type="exception",
            entity_id=exception.id,
            action="status_change",
            user_id=revoked_by_id,
            old_value={"status": old_status},
            new_value={"status": exception.status},
            description=f"Exception {exception.exception_number} revoked: {revocation_reason}",
        )

        logger.info(f"Exception {exception.exception_number} revoked by user {revoked_by_id}")

        return {
            "success": True,
            "exception_id": exception.id,
            "exception_number": exception.exception_number,
            "status": exception.status,
        }

    def check_expiring_exceptions(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Find exceptions expiring within specified days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of expiring exceptions
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days)

        exceptions = (
            ARBException.query.filter(
                ARBException.status == ARBExceptionStatus.APPROVED.value,
                ARBException.expires_at <= cutoff_date,
                ARBException.expires_at > datetime.utcnow(),
            )
            .order_by(ARBException.expires_at)
            .all()
        )

        return [
            {
                "id": e.id,
                "exception_number": e.exception_number,
                "exception_type": e.exception_type,
                "standard_id": e.standard_id,
                "standard_code": e.standard.code if e.standard else None,
                "standard_name": e.standard.name if e.standard else None,
                "expires_at": e.expires_at.isoformat(),
                "days_until_expiry": (e.expires_at - datetime.utcnow()).days,
                "requested_by": e.requester.email if e.requester else None,
                "reminder_sent": e.reminder_sent_at is not None,
            }
            for e in exceptions
        ]

    def mark_expired(self) -> Dict[str, Any]:
        """
        Mark all expired exceptions as expired.

        Returns:
            Summary of expired exceptions
        """
        now = datetime.utcnow()

        expired_exceptions = ARBException.query.filter(
            ARBException.status == ARBExceptionStatus.APPROVED.value,
            ARBException.expires_at <= now,
        ).all()

        count = 0
        for exception in expired_exceptions:
            exception.status = ARBExceptionStatus.EXPIRED.value
            exception.updated_at = now
            count += 1

            arb_audit_service.log_action(
                entity_type="exception",
                entity_id=exception.id,
                action="status_change",
                user_id=0,  # System action
                old_value={"status": ARBExceptionStatus.APPROVED.value},
                new_value={"status": ARBExceptionStatus.EXPIRED.value},
                description=f"Exception {exception.exception_number} expired",
            )

        if count > 0:
            db.session.commit()
            logger.info(f"Marked {count} exceptions as expired")

        return {
            "success": True,
            "expired_count": count,
        }

    def renew_exception(
        self,
        exception_id: int,
        renewed_by_id: int,
        new_expiry_days: int = None,
        renewal_reason: str = None,
    ) -> Dict[str, Any]:
        """
        Renew an existing exception.

        Creates a new exception linked to the original.

        Args:
            exception_id: ID of the exception to renew
            renewed_by_id: ID of user renewing
            new_expiry_days: Duration for renewal
            renewal_reason: Reason for renewal

        Returns:
            New exception details
        """
        original = db.session.get(ARBException, exception_id)
        if not original:
            return {"success": False, "error": "Exception not found"}

        if original.status not in [
            ARBExceptionStatus.APPROVED.value,
            ARBExceptionStatus.EXPIRED.value,
        ]:
            return {
                "success": False,
                "error": f"Cannot renew exception in {original.status} status",
            }

        # Generate new exception number
        exception_number = ARBException.generate_exception_number()

        # Calculate new expiration
        duration = new_expiry_days or self.DEFAULT_DURATIONS.get(original.exception_type, 180)
        expires_at = datetime.utcnow() + timedelta(days=duration)

        # Create renewal exception
        renewal = ARBException(
            exception_number=exception_number,
            review_item_id=original.review_item_id,
            standard_id=original.standard_id,
            exception_type=original.exception_type,
            exception_reason=renewal_reason or original.exception_reason,
            business_justification=original.business_justification,
            risk_mitigation=original.risk_mitigation,
            scope=original.scope,
            status=ARBExceptionStatus.REQUESTED.value,
            requested_by_id=renewed_by_id,
            requested_at=datetime.utcnow(),
            expires_at=expires_at,
            parent_exception_id=original.id,
            renewal_count=original.renewal_count + 1,
        )

        db.session.add(renewal)
        db.session.commit()

        # Log renewal
        arb_audit_service.log_action(
            entity_type="exception",
            entity_id=renewal.id,
            action="create",
            user_id=renewed_by_id,
            new_value={
                "exception_number": exception_number,
                "parent_exception_id": original.id,
                "renewal_count": renewal.renewal_count,
            },
            description=f"Renewal of exception {original.exception_number}",
        )

        logger.info(f"Created renewal {exception_number} for exception {original.exception_number}")

        return {
            "success": True,
            "exception_id": renewal.id,
            "exception_number": exception_number,
            "parent_exception_number": original.exception_number,
            "renewal_count": renewal.renewal_count,
            "status": renewal.status,
            "expires_at": expires_at.isoformat(),
        }

    def get_exception_details(
        self,
        exception_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get full exception details.

        Args:
            exception_id: ID of the exception

        Returns:
            Exception details or None
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return None

        return {
            "id": exception.id,
            "exception_number": exception.exception_number,
            "exception_type": exception.exception_type,
            "exception_reason": exception.exception_reason,
            "business_justification": exception.business_justification,
            "risk_mitigation": exception.risk_mitigation,
            "scope": exception.scope,
            "status": exception.status,
            "review_item_id": exception.review_item_id,
            "review_number": exception.review_item.review_number if exception.review_item else None,
            "standard_id": exception.standard_id,
            "standard_code": exception.standard.code if exception.standard else None,
            "standard_name": exception.standard.name if exception.standard else None,
            "requested_by": {
                "id": exception.requester.id,
                "email": exception.requester.email,
                "name": exception.requester.display_name,
            }
            if exception.requester
            else None,
            "requested_at": exception.requested_at.isoformat() if exception.requested_at else None,
            "reviewed_by": {
                "id": exception.reviewer.id,
                "email": exception.reviewer.email,
            }
            if exception.reviewer
            else None,
            "reviewed_at": exception.reviewed_at.isoformat() if exception.reviewed_at else None,
            "review_notes": exception.review_notes,
            "approved_by": {
                "id": exception.approver.id,
                "email": exception.approver.email,
            }
            if exception.approver
            else None,
            "approved_at": exception.approved_at.isoformat() if exception.approved_at else None,
            "approval_notes": exception.approval_notes,
            "denied_by": {
                "id": exception.denier.id,
                "email": exception.denier.email,
            }
            if exception.denier
            else None,
            "denied_at": exception.denied_at.isoformat() if exception.denied_at else None,
            "denial_reason": exception.denial_reason,
            "expires_at": exception.expires_at.isoformat() if exception.expires_at else None,
            "is_expired": exception.expires_at and exception.expires_at < datetime.utcnow(),
            "days_until_expiry": (
                (exception.expires_at - datetime.utcnow()).days
                if exception.expires_at and exception.expires_at > datetime.utcnow()
                else None
            ),
            "parent_exception_id": exception.parent_exception_id,
            "parent_exception_number": (
                exception.parent.exception_number if exception.parent else None
            ),
            "renewal_count": exception.renewal_count,
            "renewals": [
                {
                    "id": r.id,
                    "exception_number": r.exception_number,
                    "status": r.status,
                    "requested_at": r.requested_at.isoformat() if r.requested_at else None,
                }
                for r in exception.renewals
            ],
            "created_at": exception.created_at.isoformat() if exception.created_at else None,
            "updated_at": exception.updated_at.isoformat() if exception.updated_at else None,
        }

    def list_exceptions(
        self,
        status: str = None,
        standard_id: int = None,
        exception_type: str = None,
        requested_by_id: int = None,
        include_expired: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List exceptions with filters.

        Args:
            status: Filter by status
            standard_id: Filter by standard
            exception_type: Filter by type
            requested_by_id: Filter by requester
            include_expired: Include expired exceptions
            limit: Max results
            offset: Skip results

        Returns:
            Paginated exception list
        """
        query = ARBException.query

        if status:
            query = query.filter(ARBException.status == status)
        elif not include_expired:
            query = query.filter(ARBException.status != ARBExceptionStatus.EXPIRED.value)

        if standard_id:
            query = query.filter(ARBException.standard_id == standard_id)

        if exception_type:
            query = query.filter(ARBException.exception_type == exception_type)

        if requested_by_id:
            query = query.filter(ARBException.requested_by_id == requested_by_id)

        total = query.count()
        exceptions = (
            query.order_by(ARBException.created_at.desc()).offset(offset).limit(limit).all()
        )

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "exceptions": [
                {
                    "id": e.id,
                    "exception_number": e.exception_number,
                    "exception_type": e.exception_type,
                    "status": e.status,
                    "standard_code": e.standard.code if e.standard else None,
                    "standard_name": e.standard.name if e.standard else None,
                    "requested_by": e.requester.email if e.requester else None,
                    "requested_at": e.requested_at.isoformat() if e.requested_at else None,
                    "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                    "renewal_count": e.renewal_count,
                }
                for e in exceptions
            ],
        }

    def generate_exception_report(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Generate exception summary report.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Exception statistics and trends
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=365)
        if not end_date:
            end_date = datetime.utcnow()

        # Base query for date range
        query = ARBException.query.filter(
            ARBException.created_at >= start_date,
            ARBException.created_at <= end_date,
        )

        all_exceptions = query.all()

        # Calculate statistics
        total = len(all_exceptions)
        by_status = {}
        by_type = {}
        by_standard = {}

        for e in all_exceptions:
            # By status
            by_status[e.status] = by_status.get(e.status, 0) + 1

            # By type
            by_type[e.exception_type] = by_type.get(e.exception_type, 0) + 1

            # By standard
            std_key = e.standard.code if e.standard else "unknown"
            by_standard[std_key] = by_standard.get(std_key, 0) + 1

        # Approval rate
        approved = by_status.get(ARBExceptionStatus.APPROVED.value, 0)
        denied = by_status.get(ARBExceptionStatus.DENIED.value, 0)
        decided = approved + denied
        approval_rate = (approved / decided * 100) if decided > 0 else 0

        # Average time to decision
        decided_exceptions = [
            e
            for e in all_exceptions
            if e.status in [ARBExceptionStatus.APPROVED.value, ARBExceptionStatus.DENIED.value]
            and e.requested_at
            and (e.approved_at or e.denied_at)
        ]

        if decided_exceptions:
            total_days = sum(
                ((e.approved_at or e.denied_at) - e.requested_at).days for e in decided_exceptions
            )
            avg_days_to_decision = total_days / len(decided_exceptions)
        else:
            avg_days_to_decision = 0

        # Currently active
        active_count = ARBException.query.filter(
            ARBException.status == ARBExceptionStatus.APPROVED.value,
            ARBException.expires_at > datetime.utcnow(),
        ).count()

        # Expiring soon (30 days)
        expiring_soon = len(self.check_expiring_exceptions(days=30))

        return {
            "success": True,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_requests": total,
                "active_exceptions": active_count,
                "expiring_soon": expiring_soon,
                "approval_rate": round(approval_rate, 1),
                "avg_days_to_decision": round(avg_days_to_decision, 1),
            },
            "by_status": by_status,
            "by_type": by_type,
            "by_standard": by_standard,
        }

    def mark_reminder_sent(
        self,
        exception_id: int,
    ) -> Dict[str, Any]:
        """
        Mark that an expiration reminder was sent.

        Args:
            exception_id: ID of the exception

        Returns:
            Status update
        """
        exception = db.session.get(ARBException, exception_id)
        if not exception:
            return {"success": False, "error": "Exception not found"}

        exception.reminder_sent_at = datetime.utcnow()
        db.session.commit()

        return {
            "success": True,
            "exception_id": exception.id,
            "reminder_sent_at": exception.reminder_sent_at.isoformat(),
        }


# Create singleton instance
arb_exception_service = ARBExceptionService()
