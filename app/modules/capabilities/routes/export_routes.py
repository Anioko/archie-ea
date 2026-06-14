"""
Capability Map — CSV/JSON/image export.

Extracted from app/routes/capability_map_routes.py (lines 1415-1973).

Routes:
    - api_export_mappings()   GET "/api/export-mappings"

Helpers:
    - _export_csv(capabilities, mappings, mapped_capability_ids, applications)
    - _export_json(capabilities, mappings, mapped_capability_ids, applications)
    - _export_image(capabilities, mappings, mapped_capability_ids, format_type, applications=None)
"""

import csv
import json
from datetime import datetime
from io import BytesIO, StringIO

from flask import Response, current_app, jsonify, request
from flask_login import login_required
from sqlalchemy.exc import IntegrityError as SQLIntegrityError  # dead-code-ok
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload  # dead-code-ok

from app import db  # dead-code-ok
from app.exceptions import (  # dead-code-ok
    BusinessRuleError,
    DatabaseError,
    ExternalServiceError,
    IntegrityError,
    NotFoundError,
    ValidationError,
)

from . import capability_map


@capability_map.route("/api/export-mappings")
@login_required
def api_export_mappings():
    """Export capability mappings and gap analysis to multiple formats"""
    try:
        import csv
        import json
        from datetime import datetime
        from io import StringIO

        from flask import Response

        # Get format parameter
        export_format = request.args.get("format", "csv").lower()

        # Get filter parameters
        domain_filter = request.args.get("domain", "")
        level_filter = request.args.get("level", "")

        # Get mapping data with gap analysis
        from app.models.application_layer import ApplicationComponent
        from app.models.business_capabilities import (
            ApplicationCapabilityCoverage,
            BusinessCapability,
        )

        mappings = ApplicationCapabilityCoverage.query.all()
        all_capabilities = BusinessCapability.query.all()
        all_applications = ApplicationComponent.query.all()

        mapped_capability_ids = {mapping.capability_id for mapping in mappings}

        # Batch-prefetch capabilities
        export_caps_by_id = {c.id: c for c in all_capabilities}

        # Apply filters to capabilities
        filtered_capabilities = []
        for capability in all_capabilities:
            if domain_filter and capability.business_domain and capability.business_domain != domain_filter:
                continue
            if level_filter and str(capability.level) != level_filter:
                continue
            filtered_capabilities.append(capability)

        # Apply filters to mappings
        filtered_mappings = []
        for mapping in mappings:
            capability = export_caps_by_id.get(mapping.capability_id)
            if domain_filter and capability and capability.business_domain and capability.business_domain != domain_filter:
                continue
            if level_filter and capability and str(capability.level) != level_filter:
                continue
            filtered_mappings.append(mapping)

        if export_format == "csv":
            return _export_csv(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, all_applications
            )
        elif export_format == "json":
            return _export_json(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, all_applications
            )
        elif export_format == "jpg":
            return _export_image(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, "jpg", all_applications
            )
        elif export_format == "png":
            return _export_image(
                filtered_capabilities, filtered_mappings, mapped_capability_ids, "png", all_applications
            )
        else:
            return jsonify({"error": "Unsupported format. Use csv, json, jpg, or png"}), 400

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error exporting mappings: {e}")
        raise DatabaseError(
            message=f"Failed to export mapping data: {str(e)}",
            user_message="Unable to export capability mappings.",
            recovery_action="Please try again. If the problem persists, contact support.",
        )
    except Exception as e:
        current_app.logger.error(f"Error exporting mappings: {e}")
        raise BusinessRuleError(
            message=f"Export failed: {str(e)}",
            user_message="Unable to export data in the requested format.",
            recovery_action="Try a different export format or refresh the page.",
        )


def _export_csv(capabilities, mappings, mapped_capability_ids, applications):
    """Export to CSV format"""
    import csv
    from datetime import datetime
    from io import StringIO

    from flask import Response

    from app.models.application_layer import ApplicationComponent
    from app.models.business_capabilities import BusinessCapability

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "Report Type",
            "Capability ID",
            "Capability Name",
            "Capability Level",
            "Domain",
            "Application ID",
            "Application Name",
            "Support Level",
            "Coverage %",
            "Gap Status",
            "Assessment Notes",
            "Strategic Priority",
        ]
    )

    # Batch-prefetch apps and capabilities
    csv_app_ids = {m.application_component_id for m in mappings}
    csv_cap_ids = {m.capability_id for m in mappings}
    csv_apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(csv_app_ids)).all() if csv_app_ids else []
    csv_caps = BusinessCapability.query.filter(BusinessCapability.id.in_(csv_cap_ids)).all() if csv_cap_ids else []
    csv_apps_by_id = {a.id: a for a in csv_apps}
    csv_caps_by_id = {c.id: c for c in csv_caps}

    # Write existing mappings
    for mapping in mappings:
        app = csv_apps_by_id.get(mapping.application_component_id)
        capability = csv_caps_by_id.get(mapping.capability_id)

        if app and capability:
            writer.writerow(
                [
                    "MAPPING",
                    capability.id,
                    capability.name,
                    capability.level or 1,
                    getattr(capability, "business_domain", "Unknown"),  # model-safety-ok: UnifiedCapability uses domain_id relationship, no direct business_domain field
                    app.id,
                    app.name,
                    mapping.support_level,
                    mapping.coverage_percentage,
                    mapping.gap_status,
                    mapping.assessment_notes,
                    "High" if (capability.level or 1) == 1 else "Medium",
                ]
            )

    # Write unmapped capabilities (gaps)
    for capability in capabilities:
        if capability.id not in mapped_capability_ids:
            writer.writerow(
                [
                    "GAP",
                    capability.id,
                    capability.name,
                    capability.level or 1,
                    getattr(capability, "business_domain", "Unknown"),  # model-safety-ok: UnifiedCapability uses domain_id relationship, no direct business_domain field
                    "",
                    "",
                    "",
                    "0%",
                    "Gap Identified",
                    "Capability needs application support",
                    "High" if (capability.level or 1) == 1 else "Medium",
                ]
            )

    # Write summary
    writer.writerow([])
    writer.writerow(["SUMMARY METRICS"])
    writer.writerow(["Total Capabilities", len(capabilities)])
    writer.writerow(["Mapped Capabilities", len(mapped_capability_ids)])
    writer.writerow(["Gap Count", len(capabilities) - len(mapped_capability_ids)])
    writer.writerow(["Total Applications", len(applications)])
    writer.writerow(["Total Mappings", len(mappings)])
    writer.writerow([])

    # Create response
    output.seek(0)
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    return response


def _export_json(capabilities, mappings, mapped_capability_ids, applications):
    """Export to JSON format"""
    import json
    from datetime import datetime

    from flask import Response

    from app.models.application_layer import ApplicationComponent
    from app.models.business_capabilities import BusinessCapability

    # Build JSON structure
    export_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "total_capabilities": len(capabilities),
            "mapped_capabilities": len(mapped_capability_ids),
            "gap_count": len(capabilities) - len(mapped_capability_ids),
            "total_applications": len(applications),
            "total_mappings": len(mappings),
        },
        "mappings": [],
        "gaps": [],
    }

    # OPTIMIZATION: Batch-prefetch apps and capabilities to avoid N+1 queries
    json_app_ids = {m.application_component_id for m in mappings}
    json_cap_ids = {m.capability_id for m in mappings}
    json_apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(json_app_ids)).all() if json_app_ids else []
    json_caps = BusinessCapability.query.filter(BusinessCapability.id.in_(json_cap_ids)).all() if json_cap_ids else []
    json_apps_by_id = {a.id: a for a in json_apps}
    json_caps_by_id = {c.id: c for c in json_caps}

    # Add mappings
    for mapping in mappings:
        app = json_apps_by_id.get(mapping.application_component_id)
        capability = json_caps_by_id.get(mapping.unified_capability_id)

        if app and capability:
            export_data["mappings"].append(
                {
                    "capability_id": capability.id,
                    "capability_name": capability.name,
                    "capability_level": capability.level or 1,
                    "application_id": app.id,
                    "application_name": app.name,
                    "support_level": mapping.support_level,
                    "coverage_percentage": mapping.coverage_percentage,
                    "strategic_priority": "High"
                    if (capability.level or 1) == 1
                    else "Medium",
                }
            )

    # Add gaps
    for capability in capabilities:
        if capability.id not in mapped_capability_ids:
            export_data["gaps"].append(
                {
                    "capability_id": capability.id,
                    "capability_name": capability.name,
                    "capability_level": capability.level or 1,
                    "gap_status": "Gap Identified",
                    "strategic_priority": "High"
                    if (capability.level or 1) == 1
                    else "Medium",
                }
            )

    # Create response
    response = Response(json.dumps(export_data, indent=2), mimetype="application/json")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

    return response


def _export_image(capabilities, mappings, mapped_capability_ids, format_type, applications=None):
    """Export to image format (JPG/PNG)"""
    try:
        from datetime import datetime
        from io import BytesIO

        from flask import Response
        from PIL import Image, ImageDraw, ImageFont

        from app.models.application_layer import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability

        # Create image
        img_width, img_height = 1200, 800
        img = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a simple font
        try:
            font_title = ImageFont.truetype("arial.ttf", 24)
            font_header = ImageFont.truetype("arial.ttf", 18)
            font_normal = ImageFont.truetype("arial.ttf", 12)
        except (OSError, IOError):
            font_title = ImageFont.load_default()
            font_header = ImageFont.load_default()
            font_normal = ImageFont.load_default()

        # Title
        title = f"Capability Mapping Report - {datetime.now().strftime('%Y-%m-%d')}"
        draw.text((50, 30), title, fill="black", font=font_title)

        # Summary section
        y_position = 80
        draw.text((50, y_position), "SUMMARY METRICS", fill="black", font=font_header)
        y_position += 30

        summary_data = [
            f"Total Capabilities: {len(capabilities)}",
            f"Mapped Capabilities: {len(mapped_capability_ids)}",
            f"Gap Count: {len(capabilities) - len(mapped_capability_ids)}",
            f"Total Applications: {len(applications) if applications else 0}",
            f"Total Mappings: {len(mappings)}",
            f"Coverage: {round((len(mapped_capability_ids) / len(capabilities)) * 100, 2) if capabilities else 0}%",
        ]

        for metric in summary_data:
            draw.text((70, y_position), metric, fill="black", font=font_normal)
            y_position += 20

        # Mappings section
        y_position += 20
        draw.text(
            (50, y_position), "APPLICATION CAPABILITY MAPPINGS", fill="black", font=font_header
        )
        y_position += 30

        draw.text((70, y_position), "Capability Name", fill="black", font=font_normal)
        draw.text((400, y_position), "Application Name", fill="black", font=font_normal)
        draw.text((700, y_position), "Support Level", fill="black", font=font_normal)
        draw.text((900, y_position), "Coverage", fill="black", font=font_normal)
        y_position += 20

        # OPTIMIZATION: Batch-prefetch apps and capabilities for image export to avoid N+1 queries
        img_app_ids = {m.application_component_id for m in mappings[:10]}
        img_cap_ids = {m.capability_id for m in mappings[:10]}
        img_apps = ApplicationComponent.query.filter(ApplicationComponent.id.in_(img_app_ids)).all() if img_app_ids else []
        img_caps = BusinessCapability.query.filter(BusinessCapability.id.in_(img_cap_ids)).all() if img_cap_ids else []
        img_apps_by_id = {a.id: a for a in img_apps}
        img_caps_by_id = {c.id: c for c in img_caps}

        # Add top 10 mappings
        for i, mapping in enumerate(mappings[:10]):
            if y_position > img_height - 100:
                break

            app = img_apps_by_id.get(mapping.application_component_id)
            capability = img_caps_by_id.get(mapping.unified_capability_id)

            if app and capability:
                draw.text(
                    (70, y_position),
                    capability.name[:35] + "..." if len(capability.name) > 35 else capability.name,
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (400, y_position),
                    app.name[:35] + "..." if len(app.name) > 35 else app.name,
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (700, y_position),
                    mapping.support_level or "Primary",
                    fill="black",
                    font=font_normal,
                )
                draw.text(
                    (900, y_position),
                    f"{mapping.coverage_percentage or 80}%",
                    fill="black",
                    font=font_normal,
                )
                y_position += 18

        # Gaps section
        if len(capabilities) - len(mapped_capability_ids) > 0 and y_position < img_height - 150:
            y_position += 20
            draw.text((50, y_position), "CAPABILITY GAPS", fill="black", font=font_header)
            y_position += 30

            draw.text((70, y_position), "Capability Name", fill="black", font=font_normal)
            draw.text((400, y_position), "Level", fill="black", font=font_normal)
            draw.text((500, y_position), "Priority", fill="black", font=font_normal)
            y_position += 20

            # Add top 10 gaps
            gap_count = 0
            for capability in capabilities:
                if capability.id not in mapped_capability_ids and gap_count < 10:
                    if y_position > img_height - 50:
                        break

                    priority = "High" if (capability.level or 1) == 1 else "Medium"
                    draw.text(
                        (70, y_position),
                        capability.name[:35] + "..."
                        if len(capability.name) > 35
                        else capability.name,
                        fill="black",
                        font=font_normal,
                    )
                    draw.text(
                        (400, y_position),
                        str(capability.level or 1),
                        fill="black",
                        font=font_normal,
                    )
                    draw.text((500, y_position), priority, fill="black", font=font_normal)
                    y_position += 18
                    gap_count += 1

        # Save image to BytesIO
        img_buffer = BytesIO()
        img.save(img_buffer, format=format_type.upper())
        img_buffer.seek(0)

        # Create response
        response = Response(img_buffer.getvalue(), mimetype=f"image/{format_type}")
        response.headers[
            "Content-Disposition"
        ] = f'attachment; filename=capability_mappings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{format_type}'

        return response

    except Exception as e:
        # Fallback to error response if PIL is not available
        return (
            jsonify(
                {
                    "error": "Image export requires PIL/Pillow library. Please install it with: pip install Pillow",
                    "details": "See server logs for details",
                }
            ),
            500,
        )
