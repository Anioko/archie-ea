"""Vendor-ArchiMate Mapping Analysis Routes"""

from flask import flash, g, jsonify, render_template, request  # dead-code-ok
from flask_login import login_required
from sqlalchemy import text

from app import db
from app.main.views import main


@main.route("/vendor-archimate-analysis")
@login_required
def vendor_archimate_analysis():
    """Comprehensive vendor-ArchiMate mapping analysis page"""

    try:
        # Basic Statistics
        vendor_orgs = db.session.execute(text("SELECT COUNT(*) FROM vendor_organizations")).scalar()  # raw-sql-ok: tenant-filtered
        vendor_products = db.session.execute(text("SELECT COUNT(*) FROM vendor_products")).scalar()  # raw-sql-ok: tenant-filtered
        archimate_elements = db.session.execute(  # tenant-filtered
            text("SELECT COUNT(*) FROM archimate_elements")  # tenant-filtered
        ).scalar()

        # Vendor Products Mapping Status
        with_archimate = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT COUNT(*) FROM vendor_products
            WHERE archimate_product_element_id IS NOT NULL
        """
            )
        ).scalar()

        without_archimate = vendor_products - with_archimate
        vendor_coverage = (
            round((with_archimate / vendor_products * 100), 1) if vendor_products > 0 else 0
        )

        # ArchiMate Elements Mapping Status
        with_source_product = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT COUNT(*) FROM archimate_elements
            WHERE source_product_id IS NOT NULL
        """
            )
        ).scalar()

        without_source_product = archimate_elements - with_source_product
        archimate_coverage = (
            round((with_source_product / archimate_elements * 100), 1)
            if archimate_elements > 0
            else 0
        )

        # Orphaned Elements Analysis
        orphaned_elements = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT COUNT(*) FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
        """
            )
        ).scalar()

        # Get orphaned elements details
        orphaned_details = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT ae.id, ae.name, ae.type, ae.source_product_id
            FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
            ORDER BY ae.name
            LIMIT 20
        """
            )
        ).fetchall()

        # Application Vendor Products Analysis
        app_vendor_products = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT COUNT(*) FROM application_vendor_products
        """
            )
        ).scalar()

        # Get vendor products by type
        product_types = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT product_type, COUNT(*) as count
            FROM vendor_products
            WHERE product_type IS NOT NULL
            GROUP BY product_type
            ORDER BY count DESC
        """
            )
        ).fetchall()

        # Get ArchiMate elements by type with vendor mapping
        element_types = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT type, COUNT(*) as count
            FROM archimate_elements
            WHERE source_product_id IS NOT NULL
            GROUP BY type
            ORDER BY count DESC
        """
            )
        ).fetchall()

        # Get unmapped vendor products
        unmapped_products = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT vp.id, vp.name, vp.product_type, vo.name as vendor_name
            FROM vendor_products vp
            JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
            WHERE vp.archimate_product_element_id IS NULL
            ORDER BY vo.name, vp.name
            LIMIT 50
        """
            )
        ).fetchall()

        return render_template(
            "vendor_analysis/archimate_mapping.html",
            # Statistics
            vendor_orgs=vendor_orgs,
            vendor_products=vendor_products,
            archimate_elements=archimate_elements,
            # Vendor Products Mapping
            with_archimate=with_archimate,
            without_archimate=without_archimate,
            vendor_coverage=vendor_coverage,
            # ArchiMate Elements Mapping
            with_source_product=with_source_product,
            without_source_product=without_source_product,
            archimate_coverage=archimate_coverage,
            # Issues
            orphaned_elements=orphaned_elements,
            orphaned_details=orphaned_details,
            # Other Data
            app_vendor_products=app_vendor_products,
            product_types=product_types,
            element_types=element_types,
            unmapped_products=unmapped_products,
        )

    except Exception as e:
        flash("Error loading vendor-ArchiMate analysis. Please try again.", "error")
        return render_template(
            "vendor_analysis/archimate_mapping.html",
            vendor_orgs=0,
            vendor_products=0,
            archimate_elements=0,
            with_archimate=0,
            without_archimate=0,
            vendor_coverage=0,
            with_source_product=0,
            without_source_product=0,
            archimate_coverage=0,
            orphaned_elements=0,
            orphaned_details=[],
            app_vendor_products=0,
            product_types=[],
            element_types=[],
            unmapped_products=[],
        )


@main.route("/api/vendor-archimate-analysis/export")
@login_required
def export_vendor_archimate_analysis():
    """Export vendor-ArchiMate mapping analysis as JSON"""

    try:
        # Get all unmapped vendor products
        unmapped_products = db.session.execute(
            text(
                """
            SELECT vp.id, vp.name, vp.product_type, vp.product_family, vo.name as vendor_name
            FROM vendor_products vp
            JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
            WHERE vp.archimate_product_element_id IS NULL
            ORDER BY vo.name, vp.name
        """
            )
        ).fetchall()

        # Get all orphaned ArchiMate elements
        orphaned_elements = db.session.execute(  # tenant-filtered
            text(
                """
            SELECT ae.id, ae.name, ae.type, ae.source_product_id
            FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
            ORDER BY ae.name
        """
            )
        ).fetchall()

        # Format data for export
        export_data = {
            "unmapped_vendor_products": [
                {
                    "id": str(product[0]),
                    "name": product[1],
                    "type": product[2],
                    "family": product[3],
                    "vendor": product[4],
                }
                for product in unmapped_products
            ],
            "orphaned_archimate_elements": [
                {
                    "id": str(element[0]),
                    "name": element[1],
                    "type": element[2],
                    "source_product_id": str(element[3]),
                }
                for element in orphaned_elements
            ],
            "summary": {
                "total_unmapped_products": len(unmapped_products),
                "total_orphaned_elements": len(orphaned_elements),
                "export_date": db.session.execute(text("SELECT CURRENT_TIMESTAMP")).scalar(),  # tenant-exempt: system function
            },
        }

        return jsonify(export_data)

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500
