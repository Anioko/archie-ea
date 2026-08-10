"""Vendor-ArchiMate Mapping Analysis Routes"""

from flask import current_app, flash, jsonify, render_template  # dead-code-ok
from flask_login import login_required
from sqlalchemy import text

from app import db
from app.main.views import main
from app.utils.tenant_sql import org_scope


@main.route("/vendor-archimate-analysis")
@login_required
def vendor_archimate_analysis():
    """Comprehensive vendor-ArchiMate mapping analysis page"""

    try:
        # archimate_elements is tenant-scoped; every count below must carry the
        # predicate or one org's page reports another org's element catalogue.
        _org_where, _org_params = org_scope(keyword="WHERE")
        _org_and, _ = org_scope(keyword="AND")
        _org_and_ae, _ = org_scope(prefix="ae.", keyword="AND")

        # Basic Statistics
        # vendor_organizations / vendor_products carry no organization_id column,
        # so these two are global by schema, not by choice. Recorded here because
        # the comment that used to sit on them claimed they were tenant-filtered.
        vendor_orgs = db.session.execute(text("SELECT COUNT(*) FROM vendor_organizations")).scalar()
        vendor_products = db.session.execute(text("SELECT COUNT(*) FROM vendor_products")).scalar()
        archimate_elements = db.session.execute(
            text(f"SELECT COUNT(*) FROM archimate_elements{_org_where}"), _org_params
        ).scalar()

        # Vendor Products Mapping Status (global: vendor_products has no org column)
        with_archimate = db.session.execute(
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
        with_source_product = db.session.execute(
            text(
                f"""
            SELECT COUNT(*) FROM archimate_elements
            WHERE source_product_id IS NOT NULL{_org_and}
        """
            ),
            _org_params,
        ).scalar()

        without_source_product = archimate_elements - with_source_product
        archimate_coverage = (
            round((with_source_product / archimate_elements * 100), 1)
            if archimate_elements > 0
            else 0
        )

        # Orphaned Elements Analysis
        orphaned_elements = db.session.execute(
            text(
                f"""
            SELECT COUNT(*) FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL{_org_and_ae}
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
        """
            ),
            _org_params,
        ).scalar()

        # Get orphaned elements details
        orphaned_details = db.session.execute(
            text(
                f"""
            SELECT ae.id, ae.name, ae.type, ae.source_product_id
            FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL{_org_and_ae}
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
            ORDER BY ae.name
            LIMIT 20
        """
            ),
            _org_params,
        ).fetchall()

        # Application Vendor Products Analysis
        # (application_vendor_products has no organization_id column — global by schema)
        app_vendor_products = db.session.execute(
            text(
                """
            SELECT COUNT(*) FROM application_vendor_products
        """
            )
        ).scalar()

        # Get vendor products by type (global: vendor_products has no org column)
        product_types = db.session.execute(
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
        element_types = db.session.execute(
            text(
                f"""
            SELECT type, COUNT(*) as count
            FROM archimate_elements
            WHERE source_product_id IS NOT NULL{_org_and}
            GROUP BY type
            ORDER BY count DESC
        """
            ),
            _org_params,
        ).fetchall()

        # Get unmapped vendor products (global: vendor_products has no org column)
        unmapped_products = db.session.execute(
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

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error loading vendor-ArchiMate analysis")
        flash("Error loading vendor-ArchiMate analysis. Please try again.", "error")
        # None throughout: "0% vendor coverage" is a conclusion an architect
        # would act on, and nothing here was actually counted.
        return render_template(
            "vendor_analysis/archimate_mapping.html",
            vendor_orgs=None,
            vendor_products=None,
            archimate_elements=None,
            with_archimate=None,
            without_archimate=None,
            vendor_coverage=None,
            with_source_product=None,
            without_source_product=None,
            archimate_coverage=None,
            orphaned_elements=None,
            orphaned_details=[],
            app_vendor_products=None,
            product_types=[],
            element_types=[],
            unmapped_products=[],
            load_error="Vendor-to-ArchiMate mapping coverage could not be calculated.",
        )


@main.route("/api/vendor-archimate-analysis/export")
@login_required
def export_vendor_archimate_analysis():
    """Export vendor-ArchiMate mapping analysis as JSON"""

    try:
        _org_and_ae, _org_params = org_scope(prefix="ae.", keyword="AND")

        # Get all unmapped vendor products
        # (global: neither vendor_products nor vendor_organizations has an
        # organization_id column, so there is nothing here to scope against)
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
        orphaned_elements = db.session.execute(
            text(
                f"""
            SELECT ae.id, ae.name, ae.type, ae.source_product_id
            FROM archimate_elements ae
            WHERE ae.source_product_id IS NOT NULL{_org_and_ae}
            AND NOT EXISTS (
                SELECT 1 FROM vendor_products vp
                WHERE vp.id = ae.source_product_id
            )
            ORDER BY ae.name
        """
            ),
            _org_params,
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

    except Exception:
        return jsonify({"error": "An internal error occurred"}), 500
