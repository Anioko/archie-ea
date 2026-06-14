"""
GovernanceService - Architecture Governance and Compliance
Manages architecture reviews, standards compliance, and governance metrics.
"""
import logging
from datetime import datetime
from typing import Dict, List

from sqlalchemy import text

from app import db
from app.services.decorators import transactional

logger = logging.getLogger(__name__)


class GovernanceService:
    """Service for architecture governance, compliance, and review workflows."""

    @classmethod
    @transactional
    def submit_for_review(
        cls, architecture_id: int, reviewer_id: int, review_type: str = "STANDARD"
    ) -> Dict:
        """
        Submit architecture for governance review.

        Args:
            architecture_id: ID of architecture to review
            reviewer_id: ID of reviewing architect
            review_type: STANDARD, COMPLIANCE, SECURITY, PERFORMANCE

        Returns:
            Review record with ID and status
        """
        query = """
            INSERT INTO architecture_reviews
            (architecture_id, reviewer_id, review_type, status, submitted_at)
            VALUES (:arch_id, :reviewer_id, :review_type, 'PENDING', :now)
            RETURNING id, status
        """
        result = db.session.execute(  # tenant-filtered: scoped via parent FK (architecture_id)
            text(query),
            {
                "arch_id": architecture_id,
                "reviewer_id": reviewer_id,
                "review_type": review_type,
                "now": datetime.utcnow(),
            },
        )
        db.session.commit()
        row = result.fetchone()
        return {"review_id": row[0], "status": row[1]}

    @classmethod
    @transactional
    def check_compliance(cls, architecture_id: int) -> Dict:
        """
        Check architecture against all active standards.

        Returns:
            {
                'compliant': bool,
                'violations': List[dict],
                'compliance_score': float (0 - 100)
            }
        """
        # Get all active standards
        standards_query = "SELECT id, name, category, check_criteria FROM architecture_standards WHERE is_active = true"
        standards_result = db.session.execute(text(standards_query))  # tenant-exempt: system table (architecture standards are org-wide)
        standards = [dict(row._mapping) for row in standards_result]

        violations = []
        total_checks = len(standards)
        passed_checks = 0

        for standard in standards:
            is_compliant = cls._check_standard_compliance(architecture_id, standard)
            if is_compliant:
                passed_checks += 1
            else:
                violations.append(
                    {
                        "standard_id": standard["id"],
                        "standard_name": standard["name"],
                        "category": standard["category"],
                        "severity": "HIGH"
                        if standard["category"] in ["SECURITY", "DATA"]
                        else "MEDIUM",
                    }
                )

        compliance_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "compliance_score": round(compliance_score, 1),
            "total_standards_checked": total_checks,
        }

    @classmethod
    @transactional
    def _check_standard_compliance(cls, architecture_id: int, standard: Dict) -> bool:
        """
        Check if architecture meets a specific standard.
        This is a simplified check - real implementation would be more complex.
        """
        # Example checks based on standard category
        if standard["category"] == "NAMING":
            # Check if all elements have names
            query = "SELECT COUNT(*) FROM archimate_elements WHERE architecture_id = :arch_id AND (name IS NULL OR name = '')"
            result = db.session.execute(text(query), {"arch_id": architecture_id})  # tenant-filtered: scoped via parent FK (architecture_id)
            count = result.scalar()
            return count == 0

        elif standard["category"] == "DOCUMENTATION":
            # Check if elements have descriptions
            query = "SELECT COUNT(*) FROM archimate_elements WHERE architecture_id = :arch_id AND (description IS NULL OR description = '')"
            result = db.session.execute(text(query), {"arch_id": architecture_id})  # tenant-filtered: scoped via parent FK (architecture_id)
            count = result.scalar()
            total_query = "SELECT COUNT(*) FROM archimate_elements WHERE architecture_id = :arch_id"
            total_result = db.session.execute(text(total_query), {"arch_id": architecture_id})  # tenant-filtered: scoped via parent FK (architecture_id)
            total = total_result.scalar()
            return (count / total) < 0.2 if total > 0 else True  # Allow 20% undocumented

        # Default: assume compliant
        return True

    @classmethod
    @transactional
    def get_governance_metrics(cls, architecture_id: int) -> Dict:
        """
        Get governance health metrics for an architecture.

        Returns:
            {
                'compliance_score': float,
                'review_status': str,
                'open_violations': int,
                'last_review_date': datetime,
                'governance_health': str (GOOD/FAIR/POOR)
            }
        """
        compliance = cls.check_compliance(architecture_id)

        # Get latest review
        review_query = """
            SELECT status, completed_at
            FROM architecture_reviews
            WHERE architecture_id = :arch_id
            ORDER BY submitted_at DESC
            LIMIT 1
        """
        review_result = db.session.execute(text(review_query), {"arch_id": architecture_id})  # tenant-filtered: scoped via parent FK (architecture_id)
        review_row = review_result.fetchone()

        review_status = review_row[0] if review_row else "NO_REVIEW"
        last_review = review_row[1] if review_row else None

        # Calculate health
        score = compliance["compliance_score"]
        if score >= 90:
            health = "GOOD"
        elif score >= 70:
            health = "FAIR"
        else:
            health = "POOR"

        return {
            "compliance_score": compliance["compliance_score"],
            "review_status": review_status,
            "open_violations": len(compliance["violations"]),
            "last_review_date": last_review,
            "governance_health": health,
        }

    @classmethod
    @transactional
    def create_standard(
        cls, name: str, category: str, description: str, check_criteria: str
    ) -> int:
        """Create a new architecture standard."""
        query = """
            INSERT INTO architecture_standards (name, category, description, check_criteria, is_active)
            VALUES (:name, :category, :description, :criteria, true)
            RETURNING id
        """
        result = db.session.execute(  # tenant-exempt: system table (architecture standards are org-wide)
            text(query),
            {
                "name": name,
                "category": category,
                "description": description,
                "criteria": check_criteria,
            },
        )
        db.session.commit()
        return result.scalar()

    @classmethod
    @transactional
    def get_portfolio_governance_summary(cls) -> Dict:
        """
        Get portfolio-wide governance summary.

        Returns:
            Summary of governance health across all architectures
        """
        try:
            # Get all architectures
            arch_query = "SELECT id, name FROM architecture_models WHERE status = 'ACTIVE'"
            arch_result = db.session.execute(text(arch_query))  # tenant-exempt: system table (architecture models are org-wide)
            architectures = [dict(row._mapping) for row in arch_result]

            total_architectures = len(architectures)
            compliant_count = 0
            total_violations = 0
            avg_compliance_score = 0

            health_distribution = {"GOOD": 0, "FAIR": 0, "POOR": 0}

            for arch in architectures:
                try:
                    metrics = cls.get_governance_metrics(arch["id"])

                    if metrics["compliance_score"] >= 90:
                        compliant_count += 1

                    total_violations += metrics["open_violations"]
                    avg_compliance_score += metrics["compliance_score"]
                    health_distribution[metrics["governance_health"]] += 1

                except Exception as e:
                    logger.error(f"Error getting metrics for architecture {arch['id']}: {e}")

            avg_compliance_score = (
                avg_compliance_score / total_architectures if total_architectures > 0 else 0
            )

            return {
                "total_architectures": total_architectures,
                "compliant_architectures": compliant_count,
                "compliance_percentage": round(
                    (compliant_count / total_architectures * 100) if total_architectures > 0 else 0,
                    1,
                ),
                "total_violations": total_violations,
                "average_compliance_score": round(avg_compliance_score, 1),
                "health_distribution": health_distribution,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting portfolio governance summary: {e}", exc_info=True)
            return {"error": str(e)}
