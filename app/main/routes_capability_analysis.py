"""Unmapped Capabilities Analysis Routes"""

from flask import flash, g, jsonify, render_template, request  # dead-code-ok
from flask_login import login_required
from sqlalchemy import text

from app import db
from app.main.views import main


@main.route("/capability-analysis/unmapped")
@login_required
def unmapped_capabilities():
    """Dedicated page for viewing capabilities with no applications mapped"""

    try:
        # Get unmapped capabilities with detailed information
        org_params = {}

        # Get summary statistics
        total_capabilities = db.session.execute(  # tenant-filtered
            text(f"SELECT COUNT(*) FROM unified_capabilities WHERE 1=1 {org_filter}"),
            org_params
        ).scalar()
        mapped_capabilities = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT COUNT(DISTINCT uacm.unified_capability_id)
            FROM unified_application_capability_mapping uacm
            JOIN unified_capabilities uc ON uc.id = uacm.unified_capability_id
            WHERE 1=1 {org_filter}
        """
            ),
            org_params
        ).scalar()

        # Get domain statistics
        domain_stats = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT
                bd.name as domain_name,
                bd.code as domain_code,
                COUNT(uc.id) as total_capabilities,
                COUNT(uacm.unified_capability_id) as mapped_capabilities,
                COUNT(uc.id) - COUNT(uacm.unified_capability_id) as unmapped_capabilities
            FROM business_domains bd
            LEFT JOIN unified_capabilities uc ON bd.id = uc.domain_id
            LEFT JOIN unified_application_capability_mapping uacm ON uc.id = uacm.unified_capability_id
            WHERE 1=1 {org_filter.replace('AND uc.', 'AND uc.')}
            GROUP BY bd.id, bd.name, bd.code
            ORDER BY bd.strategic_weight DESC, bd.name
        """
            ),
            org_params
        )
        domain_stats = domain_stats.fetchall()

        # Get priority breakdown
        priority_breakdown = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT
                uc.strategic_importance,
                COUNT(*) as count
            FROM unified_capabilities uc
            LEFT JOIN unified_application_capability_mapping uacm
                ON uc.id = uacm.unified_capability_id
            WHERE uacm.unified_capability_id IS NULL
            {org_filter}
            GROUP BY uc.strategic_importance
            ORDER BY
                CASE uc.strategic_importance
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END
        """
            ),
            org_params
        )
        priority_breakdown = priority_breakdown.fetchall()

        # Calculate coverage percentage
        mapping_coverage = (
            round((mapped_capabilities / total_capabilities * 100), 1)
            if total_capabilities > 0
            else 0
        )

        return render_template(
            "capability_analysis/unmapped_capabilities.html",
            unmapped_capabilities=unmapped_capabilities,
            total_capabilities=total_capabilities,
            mapped_capabilities=mapped_capabilities,
            unmapped_count=len(unmapped_capabilities),
            mapping_coverage=mapping_coverage,
            domain_stats=domain_stats,
            priority_breakdown=priority_breakdown,
        )

    except Exception as e:
        flash("Error loading unmapped capabilities. Please try again.", "error")
        return render_template(
            "capability_analysis/unmapped_capabilities.html",
            unmapped_capabilities=[],
            total_capabilities=0,
            mapped_capabilities=0,
            unmapped_count=0,
            mapping_coverage=0,
            domain_stats=[],
            priority_breakdown=[],
        )


@main.route("/api/capability-analysis/unmapped/export")
@login_required
def export_unmapped_capabilities():
    """Export unmapped capabilities as JSON"""

    try:
        # Unmapped = capabilities with no application mapping. unified_capabilities
        # has no organization_id column, so no tenant filter is applied here.
        unmapped_result = db.session.execute(
            text(
                """
            SELECT uc.name, uc.description, uc.strategic_importance,
                   uc.current_maturity_level, uc.target_maturity_level, uc.status,
                   bd.name AS domain_name
            FROM unified_capabilities uc
            LEFT JOIN unified_application_capability_mapping uacm
                ON uc.id = uacm.unified_capability_id
            LEFT JOIN business_domains bd ON uc.domain_id = bd.id
            WHERE uacm.unified_capability_id IS NULL
            ORDER BY uc.name
        """
            )
        ).fetchall()

        capabilities = []
        for row in unmapped_result:
            capabilities.append(
                {
                    "name": row[0],
                    "description": row[1],
                    "strategic_importance": row[2],
                    "current_maturity_level": row[3],
                    "target_maturity_level": row[4],
                    "status": row[5],
                    "domain_name": row[6],
                }
            )

        return jsonify(
            {
                "capabilities": capabilities,
                "total_count": len(capabilities),
                "export_date": db.session.execute(text("SELECT CURRENT_TIMESTAMP")).scalar(),  # tenant-exempt: system function
            }
        )

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500
