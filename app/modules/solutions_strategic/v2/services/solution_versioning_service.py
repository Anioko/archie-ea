"""
SolutionVersioningService: Multi-round approval workflows with version tracking.
Handles v1 → v2 → v3 with change diffs and approval matrix.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from app import db
from app.models.solution_governance import SolutionVersion


class SolutionVersioningService:
    """Manages multi-round solution versioning with approval tracking."""
    
    def create_new_version(
        self,
        solution_id: int,
        created_by_id: int,
        change_summary: str,
        change_delta: Optional[Dict] = None,
        solution_snapshot: Optional[Dict] = None
    ) -> SolutionVersion:
        """
        Create a new version of the solution.
        
        Args:
            solution_id: Solution being versioned
            created_by_id: Who created this version
            change_summary: Human-readable summary of changes
            change_delta: Structured diff from previous version
            solution_snapshot: Full solution state at this version
        
        Returns:
            SolutionVersion: Newly created version
        """
        # Get latest version number
        latest = db.session.query(SolutionVersion).filter(
            SolutionVersion.solution_id == solution_id
        ).order_by(SolutionVersion.version_number.desc()).first()
        
        next_version_number = (latest.version_number + 1) if latest else 1
        
        version = SolutionVersion(
            solution_id=solution_id,
            version_number=next_version_number,
            created_by_id=created_by_id,
            change_summary=change_summary,
            change_delta=change_delta or {},
            solution_snapshot=solution_snapshot or {},
            approval_status='pending'
        )
        
        db.session.add(version)
        db.session.commit()
        
        return version
    
    def auto_generate_next_version(
        self,
        solution_id: int,
        created_by_id: int,
        feedback_items: List[Dict]
    ) -> SolutionVersion:
        """
        Auto-generate next version from feedback (would call AI orchestrator in production).
        
        Args:
            solution_id: Solution to update
            created_by_id: Who triggered auto-generation
            feedback_items: Feedback from stakeholders to address
        
        Returns:
            SolutionVersion: Auto-generated next version
        """
        # Get current version
        current = db.session.query(SolutionVersion).filter(
            SolutionVersion.solution_id == solution_id
        ).order_by(SolutionVersion.version_number.desc()).first()
        
        if not current:
            raise ValueError(f"No current version for solution {solution_id}")
        
        current_snapshot = current.solution_snapshot or {}
        
        # In production: Call AI orchestrator to generate next version
        # For now: Create placeholder updated snapshot
        new_snapshot = dict(current_snapshot)
        new_snapshot['updated_from_feedback'] = True
        new_snapshot['feedback_addressed'] = len(feedback_items)
        
        # Create change summary
        change_summary = f"Auto-generated v{current.version_number + 1} addressing {len(feedback_items)} feedback items: " + \
                        ", ".join([f["summary"] for f in feedback_items[:3]])
        
        # Calculate diff
        try:
            from deepdiff import DeepDiff
            change_delta = DeepDiff(current_snapshot, new_snapshot, ignore_order=True).to_dict()
        except ImportError:
            change_delta = {}
        
        return self.create_new_version(
            solution_id=solution_id,
            created_by_id=created_by_id,
            change_summary=change_summary,
            change_delta=change_delta,
            solution_snapshot=new_snapshot
        )
    
    def get_version_diff(
        self,
        version_id: int,
        compare_to_version_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get diff between two versions.
        
        Args:
            version_id: Version to show
            compare_to_version_id: Compare to this version (defaults to previous version)
        
        Returns:
            Dict with diff details
        """
        version = db.session.query(SolutionVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        if compare_to_version_id:
            prev_version = db.session.query(SolutionVersion).get(compare_to_version_id)
        else:
            # Get previous version
            prev_version = db.session.query(SolutionVersion).filter(
                SolutionVersion.solution_id == version.solution_id,
                SolutionVersion.version_number == version.version_number - 1
            ).first()
        
        if not prev_version:
            return {
                'version_number': version.version_number,
                'change_summary': version.change_summary,
                'is_first_version': True,
                'change_delta': version.change_delta or {}
            }
        
        return {
            'current_version': version.version_number,
            'previous_version': prev_version.version_number,
            'change_summary': version.change_summary,
            'change_delta': version.change_delta or {},
            'created_at': version.created_at.isoformat(),
            'created_by_id': version.created_by_id
        }
    
    def approve_version(
        self,
        version_id: int,
        approved_by_id: int,
        approval_notes: str = "",
        conditions: Optional[List[Dict]] = None
    ) -> SolutionVersion:
        """
        Approve a version (with optional conditions).
        
        Args:
            version_id: Version to approve
            approved_by_id: Who is approving
            approval_notes: Approval notes
            conditions: List of approval conditions to satisfy
        
        Returns:
            SolutionVersion: Updated version
        """
        version = db.session.query(SolutionVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        if conditions:
            version.approval_status = 'conditional'
            version.approval_conditions = conditions
        else:
            version.approval_status = 'approved'
        
        version.approved_by_id = approved_by_id
        version.approved_at = datetime.utcnow()
        version.approval_notes = approval_notes
        
        db.session.commit()
        return version
    
    def reject_version(
        self,
        version_id: int,
        rejection_reason: str
    ) -> SolutionVersion:
        """
        Reject a version.
        
        Args:
            version_id: Version to reject
            rejection_reason: Why this version is rejected
        
        Returns:
            SolutionVersion: Updated version
        """
        version = db.session.query(SolutionVersion).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        version.approval_status = 'rejected'
        version.rejection_reason = rejection_reason
        
        db.session.commit()
        return version
    
    def get_version_history(self, solution_id: int) -> List[Dict]:
        """
        Get full version history for a solution.
        
        Args:
            solution_id: Solution to get history for
        
        Returns:
            List of versions in order
        """
        versions = db.session.query(SolutionVersion).filter(
            SolutionVersion.solution_id == solution_id
        ).order_by(SolutionVersion.version_number).all()
        
        return [v.to_dict() for v in versions]
    
    def get_approval_matrix(self, solution_id: int) -> Dict[str, Any]:
        """
        Get approval matrix (status of each version).
        
        Args:
            solution_id: Solution to analyze
        
        Returns:
            Dict with approval status for each version
        """
        versions = db.session.query(SolutionVersion).filter(
            SolutionVersion.solution_id == solution_id
        ).order_by(SolutionVersion.version_number).all()
        
        matrix = {}
        for v in versions:
            matrix[f'v{v.version_number}'] = {
                'status': v.approval_status,
                'created_at': v.created_at.isoformat(),
                'approved_at': v.approved_at.isoformat() if v.approved_at else None,
                'approved_by_id': v.approved_by_id,
                'conditions': v.approval_conditions,
                'rejection_reason': v.rejection_reason
            }
        
        return {
            'solution_id': solution_id,
            'total_versions': len(versions),
            'latest_version': versions[-1].version_number if versions else 0,
            'approval_matrix': matrix
        }
