"""
Export Routes for Application Management

Handles application data export operations (CSV, JSON) and gap analysis export.
"""

import csv
import io
import json
from datetime import datetime

from flask import (
    current_app,
    flash,
    redirect,
    send_file,
    url_for,
)
from flask_login import login_required

from ..models.application_portfolio import ApplicationComponent
from . import application_mgmt

@application_mgmt.route("/applications/export/<format>")
@login_required
def application_export(format):
    """Export Application Components to CSV or JSON"""
    apps = ApplicationComponent.query.limit(
        1000
    ).all()  # Limit to prevent OOM on large datasets

    if format == "csv":
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "ID",
                "Name",
                "Type",
                "Category",
                "Technology Stack",
                "Version",
                "Status",
                "Business Domain",
                "Owner",
                "Team",
                "Users",
                "Criticality",
            ]
        )

        # Data rows
        for app in apps:
            writer.writerow(
                [
                    app.id,
                    app.name,
                    app.component_type,
                    app.application_category,
                    app.technology_stack,
                    app.version,
                    app.deployment_status,
                    app.business_domain,
                    app.business_owner,
                    app.development_team,
                    app.user_count,
                    app.business_criticality,
                ]
            )

        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )

    elif format == "json":
        # Create JSON
        data = []
        for app in apps:
            data.append(
                {
                    "id": app.id,
                    "name": app.name,
                    "component_type": app.component_type,
                    "application_category": app.application_category,
                    "technology_stack": app.technology_stack,
                    "version": app.version,
                    "deployment_status": app.deployment_status,
                    "business_domain": app.business_domain,
                    "business_owner": app.business_owner,
                    "development_team": app.development_team,
                    "user_count": app.user_count,
                    "business_criticality": app.business_criticality,
                    "created_at": app.created_at.isoformat()
                    if app.created_at
                    else None,
                    "updated_at": app.updated_at.isoformat()
                    if app.updated_at
                    else None,
                }
            )

        return send_file(
            io.BytesIO(json.dumps(data, indent=2).encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )

    else:
        flash("Invalid export format", "error")
        return redirect(url_for("unified_applications.application_list"))



@application_mgmt.route("/applications/<int:application_id>/gaps/export")
@login_required
def export_application_gaps(application_id):
    """
    Export gap analysis to CSV for reporting.
    """
    try:
        from ..services.gap_analysis_service import ArchitecturalGapAnalyzer

        app = ApplicationComponent.query.get_or_404(application_id)
        analyzer = ArchitecturalGapAnalyzer()
        gap_results = analyzer.analyze_application_gaps(application_id)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "Category",
                "Type",
                "Severity",
                "Message",
                "Impact",
                "Recommendation",
                "Fix URL",
            ]
        )

        # Write gaps from all categories
        for category in [
            "capability_gaps",
            "integration_gaps",
            "technology_gaps",
            "process_gaps",
            "data_gaps",
            "compliance_gaps",
            "metadata_gaps",
            "relationship_gaps",
        ]:
            gaps = gap_results.get(category, [])
            for gap in gaps:
                writer.writerow(
                    [
                        gap.get("category", ""),
                        gap.get("type", ""),
                        gap.get("severity", ""),
                        gap.get("message", ""),
                        gap.get("impact", ""),
                        gap.get("recommendation", ""),
                        gap.get("fix_url", ""),
                    ]
                )

        # Prepare response
        output.seek(0)
        filename = f"gap_analysis_{app.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.csv"

        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting gaps: {str(e)}")
        flash("Error exporting gaps. Please try again.", "error")
        return redirect(
            url_for(
                "application_mgmt.application_gap_analysis",
                application_id=application_id,
            )
        )
