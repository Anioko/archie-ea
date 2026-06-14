"""
Service Layer Update Example: Add Tenant Filtering
Sprint 1.2: Multi-Tenancy Implementation

This shows how to update architecture_assistant_service.py to enforce tenant isolation.

BEFORE: No tenant filtering (INSECURE)
AFTER: All queries filtered by tenant_id (SECURE)
"""

from flask import current_app
from sqlalchemy import and_

from app.extensions import db
from app.models.solution_architect_models import (
    ArchitectureSession,
    CapabilityGapAnalysis,
    SolutionOption,
)


class ArchitectureAssistantService:
    """
    Updated service with tenant isolation

    CRITICAL: All methods MUST accept tenant_id parameter
    """

    def create_session(self, data, tenant_id, user_id):
        """
        Create new architecture session with tenant isolation

        Args:
            data (dict): Session data
            tenant_id (int): Tenant ID (from current_user.tenant_id)
            user_id (int): User ID (from current_user.id)

        Returns:
            ArchitectureSession: Created session
        """
        # Validate tenant_id
        if not tenant_id:
            raise ValueError("tenant_id is required")

        session = ArchitectureSession(
            tenant_id=tenant_id,  # CRITICAL: Always set tenant_id
            session_name=data.get("session_name"),
            capability_id=data.get("capability_id"),
            description=data.get("description"),
            created_by=user_id,
        )

        db.session.add(session)
        db.session.commit()

        return session

    def get_session(self, session_id, tenant_id):
        """
        Get session by ID with tenant isolation

        BEFORE (INSECURE):
            session = db.session.query(ArchitectureSession).get(session_id)

        AFTER (SECURE):
            session = db.session.query(ArchitectureSession)\
                .filter_by(id=session_id, tenant_id=tenant_id).first()

        Args:
            session_id (int): Session ID
            tenant_id (int): Tenant ID

        Returns:
            ArchitectureSession or None

        Raises:
            ValueError: If session not found (prevents info leakage)
        """
        session = (
            db.session.query(ArchitectureSession)
            .filter_by(id=session_id, tenant_id=tenant_id)
            .first()
        )

        if not session:
            # Don't reveal whether session exists for other tenants
            raise ValueError(f"Session {session_id} not found")

        return session

    def list_sessions(self, tenant_id, user_id=None, page=1, per_page=20):
        """
        List sessions for tenant with pagination

        BEFORE (INSECURE):
            sessions = db.session.query(ArchitectureSession).all()

        AFTER (SECURE):
            sessions = db.session.query(ArchitectureSession)\
                .filter_by(tenant_id=tenant_id)\
                .paginate(page=page, per_page=per_page)

        Args:
            tenant_id (int): Tenant ID
            user_id (int, optional): Filter by user
            page (int): Page number
            per_page (int): Items per page

        Returns:
            Pagination object
        """
        query = db.session.query(ArchitectureSession).filter_by(tenant_id=tenant_id)

        # Optional: filter by user
        if user_id:
            query = query.filter_by(created_by=user_id)

        # Always order by most recent first
        query = query.order_by(ArchitectureSession.created_at.desc())

        # Paginate
        return query.paginate(page=page, per_page=per_page, error_out=False)

    def update_session(self, session_id, tenant_id, user_id, data):
        """
        Update session with tenant isolation

        Args:
            session_id (int): Session ID
            tenant_id (int): Tenant ID
            user_id (int): User ID
            data (dict): Update data

        Returns:
            ArchitectureSession: Updated session
        """
        # Get with tenant check
        session = self.get_session(session_id, tenant_id)

        # Optional: Check user permission
        # if session.created_by != user_id:
        #     raise PermissionError("Cannot edit other user's session")

        # Update fields
        if "session_name" in data:
            session.session_name = data["session_name"]
        if "description" in data:
            session.description = data["description"]

        # Track modification
        session.updated_at = db.func.now()
        session.modified_by = user_id

        db.session.commit()

        return session

    def delete_session(self, session_id, tenant_id, user_id):
        """
        Delete session with tenant isolation

        Args:
            session_id (int): Session ID
            tenant_id (int): Tenant ID
            user_id (int): User ID

        Returns:
            bool: True if deleted
        """
        session = self.get_session(session_id, tenant_id)

        # Optional: Check ownership
        # if session.created_by != user_id:
        #     raise PermissionError("Cannot delete other user's session")

        db.session.delete(session)
        db.session.commit()

        return True

    def generate_gap_analysis(self, session_id, tenant_id, user_id, context):
        """
        Generate gap analysis with tenant isolation

        Args:
            session_id (int): Session ID
            tenant_id (int): Tenant ID
            user_id (int): User ID
            context (dict): Analysis context

        Returns:
            CapabilityGapAnalysis: Generated analysis
        """
        # Get session with tenant check
        session = self.get_session(session_id, tenant_id)

        # Generate analysis (using LLM or other logic)
        analysis = CapabilityGapAnalysis(
            tenant_id=tenant_id,  # CRITICAL: Set tenant_id
            session_id=session_id,
            capability_id=session.capability_id,
            gaps_identified=context.get("gaps", []),
            created_by=user_id,
        )

        db.session.add(analysis)
        db.session.commit()

        return analysis

    def generate_solution_options(self, session_id, tenant_id, user_id):
        """
        Generate solution options with tenant isolation

        Args:
            session_id (int): Session ID
            tenant_id (int): Tenant ID
            user_id (int): User ID

        Returns:
            list[SolutionOption]: Generated options
        """
        session = self.get_session(session_id, tenant_id)

        # Generate options (vendor, build, hybrid)
        options = []

        for approach in ["vendor", "build", "hybrid"]:
            option = SolutionOption(
                tenant_id=tenant_id,  # CRITICAL: Set tenant_id
                session_id=session_id,
                approach=approach,
                description=f"{approach.capitalize()} option description",
                created_by=user_id,
            )
            options.append(option)
            db.session.add(option)

        db.session.commit()

        return options


# CRITICAL: Update ALL service methods to follow this pattern:
# 1. Accept tenant_id parameter
# 2. Filter all queries by tenant_id
# 3. Set tenant_id when creating records
# 4. Never expose whether records exist for other tenants
