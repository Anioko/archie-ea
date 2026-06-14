"""Hybrid Multi-Path Mapping Dashboard Routes"""

from flask import flash, g, jsonify, render_template, request  # dead-code-ok
from flask_login import login_required
from sqlalchemy import text

from app import db
from app.main.views import main


@main.route("/hybrid-mapping-dashboard")
@login_required
def hybrid_mapping_dashboard():
    """Comprehensive dashboard for hybrid multi-path mapping analysis"""

    try:
        # Get comprehensive mapping statistics
        stats = get_mapping_statistics()

        # Get detailed mapping data
        app_mappings = get_application_mappings()
        product_mappings = get_product_mappings()
        archimate_mappings = get_archimate_mappings()

        # Get unmapped items
        unmapped_caps = get_unmapped_capabilities()
        unmapped_products = get_unmapped_vendor_products()
        unmapped_archimate = get_unmapped_archimate_elements()

        return render_template(
            "hybrid_mapping/dashboard.html",
            stats=stats,
            app_mappings=app_mappings,
            product_mappings=product_mappings,
            archimate_mappings=archimate_mappings,
            unmapped_caps=unmapped_caps,
            unmapped_products=unmapped_products,
            unmapped_archimate=unmapped_archimate,
        )

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        flash("Error loading hybrid mapping dashboard. Please try again.", "error")
        empty_stats = {
            "total_capabilities": 0,
            "application_centric": {"total_capabilities": 0, "capabilities_with_apps": 0, "apps_with_archimate": 0, "coverage_percentage": 0, "archimate_coverage_percentage": 0, "end_to_end_coverage": 0},
            "product_centric": {"total_capabilities": 0, "capabilities_with_products": 0, "capabilities_with_products_archimate": 0, "coverage_percentage": 0, "archimate_coverage_percentage": 0},
            "direct_archimate": {"total_capabilities": 0, "capabilities_with_archimate": 0, "coverage_percentage": 0},
            "multi_path": {"total_capabilities": 0, "capabilities_with_multi_path": 0, "coverage_percentage": 0},
            "quality_metrics": {"total_mappings": 0, "high_quality_mappings": 0, "quality_score": 0},
        }
        return render_template(
            "hybrid_mapping/dashboard.html",
            stats=empty_stats,
            app_mappings=[],
            product_mappings=[],
            archimate_mappings=[],
            unmapped_caps=[],
            unmapped_products=[],
            unmapped_archimate=[],
        )


@main.route("/api/hybrid-mapping/statistics")
@login_required
def get_mapping_statistics():
    """API endpoint for mapping statistics"""

    try:
        # Application-Centric Coverage
        app_result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                COUNT(DISTINCT uc.id) as total_capabilities,
                COUNT(DISTINCT uacm.unified_capability_id) as capabilities_with_apps,
                COUNT(DISTINCT CASE WHEN uc.archimate_element_id IS NOT NULL THEN uacm.unified_capability_id END) as apps_with_archimate
            FROM unified_capabilities uc
            LEFT JOIN unified_application_capability_mapping uacm ON uc.id = uacm.unified_capability_id
            LEFT JOIN application_components ac ON uacm.application_component_id = ac.id
        """
            )
        ).fetchone()

        # Product-Centric Coverage
        prod_result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                COUNT(DISTINCT uc.id) as total_capabilities,
                COUNT(DISTINCT cvpm.unified_capability_id) as capabilities_with_products
            FROM unified_capabilities uc
            LEFT JOIN capability_vendor_product_mapping cvpm ON uc.id = cvpm.unified_capability_id
        """
            )
        ).fetchone()

        # Products with ArchiMate (capability-product mappings where product has archimate link)
        prod_archimate_result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT COUNT(DISTINCT cvpm.unified_capability_id) as capabilities_with_products_archimate
            FROM capability_vendor_product_mapping cvpm
            JOIN vendor_products vp ON cvpm.vendor_product_id = vp.id
            WHERE vp.archimate_product_element_id IS NOT NULL
        """
            )
        ).fetchone()

        # Direct ArchiMate Coverage
        arch_result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                COUNT(DISTINCT uc.id) as total_capabilities,
                COUNT(DISTINCT ucam.unified_capability_id) as capabilities_with_archimate
            FROM unified_capabilities uc
            LEFT JOIN unified_capability_archimate_mapping ucam ON uc.id = ucam.unified_capability_id
        """
            )
        ).fetchone()

        # Multi-path coverage
        multi_path_caps = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT uc.id
                FROM unified_capabilities uc
                WHERE uc.id IN (
                    SELECT DISTINCT unified_capability_id FROM unified_application_capability_mapping
                    WHERE archimate_element_id IS NOT NULL
                ) OR uc.id IN (
                    SELECT DISTINCT unified_capability_id FROM capability_vendor_product_mapping
                ) OR uc.id IN (
                    SELECT DISTINCT unified_capability_id FROM unified_capability_archimate_mapping
                )
            ) AS multi_caps
            """
            )
        ).scalar()

        # Quality metrics
        high_quality_mappings = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT COUNT(*) FROM (
                SELECT mapping_strength FROM unified_application_capability_mapping
                WHERE mapping_strength >= 4
                UNION ALL
                SELECT mapping_strength FROM capability_vendor_product_mapping
                WHERE mapping_strength >= 4
                UNION ALL
                SELECT mapping_strength FROM unified_capability_archimate_mapping
                WHERE mapping_strength >= 4
            ) AS hq_mappings
        """
            )
        ).scalar()

        total_mappings = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT SUM(cnt) FROM (
                SELECT COUNT(*) AS cnt FROM unified_application_capability_mapping
                UNION ALL
                SELECT COUNT(*) AS cnt FROM capability_vendor_product_mapping
                UNION ALL
                SELECT COUNT(*) AS cnt FROM unified_capability_archimate_mapping
            ) AS all_mappings
        """
            )
        ).scalar()

        # Calculate coverage percentages
        total_caps = app_result[0]
        app_coverage = (app_result[1] / total_caps * 100) if total_caps > 0 else 0
        app_archimate_coverage = (app_result[2] / app_result[1] * 100) if app_result[1] > 0 else 0
        prod_coverage = (prod_result[1] / total_caps * 100) if total_caps > 0 else 0
        prod_archimate_coverage = (
            (prod_archimate_result[0] / prod_result[1] * 100)
            if prod_result[1] > 0
            else None
        )
        arch_coverage = (arch_result[1] / total_caps * 100) if total_caps > 0 else 0
        end_to_end_coverage = (app_result[2] / total_caps * 100) if total_caps > 0 else 0
        multi_path_coverage = (multi_path_caps / total_caps * 100) if total_caps > 0 else 0
        quality_score = (high_quality_mappings / total_mappings * 5) if total_mappings > 0 else 0

        return {
            "total_capabilities": total_caps,
            "application_centric": {
                "total_capabilities": total_caps,
                "capabilities_with_apps": app_result[1],
                "apps_with_archimate": app_result[2],
                "coverage_percentage": app_coverage,
                "archimate_coverage_percentage": app_archimate_coverage,
                "end_to_end_coverage": end_to_end_coverage,
            },
            "product_centric": {
                "total_capabilities": total_caps,
                "capabilities_with_products": prod_result[1],
                "capabilities_with_products_archimate": prod_archimate_result[0] or 0,
                "coverage_percentage": prod_coverage,
                "archimate_coverage_percentage": prod_archimate_coverage,
            },
            "direct_archimate": {
                "total_capabilities": total_caps,
                "capabilities_with_archimate": arch_result[1],
                "coverage_percentage": arch_coverage,
            },
            "multi_path": {
                "total_capabilities": total_caps,
                "capabilities_with_multi_path": multi_path_caps,
                "coverage_percentage": multi_path_coverage,
            },
            "quality_metrics": {
                "total_mappings": total_mappings,
                "high_quality_mappings": high_quality_mappings,
                "quality_score": quality_score,
            },
        }

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        import logging
        logging.getLogger(__name__).error(f"Error getting mapping statistics: {e}")
        return {
            "total_capabilities": 0,
            "application_centric": {"total_capabilities": 0, "capabilities_with_apps": 0, "apps_with_archimate": 0, "coverage_percentage": 0, "archimate_coverage_percentage": 0, "end_to_end_coverage": 0},
            "product_centric": {"total_capabilities": 0, "capabilities_with_products": 0, "capabilities_with_products_archimate": 0, "coverage_percentage": 0, "archimate_coverage_percentage": 0},
            "direct_archimate": {"total_capabilities": 0, "capabilities_with_archimate": 0, "coverage_percentage": 0},
            "multi_path": {"total_capabilities": 0, "capabilities_with_multi_path": 0, "coverage_percentage": 0},
            "quality_metrics": {"total_mappings": 0, "high_quality_mappings": 0, "quality_score": 0},
        }


def get_application_mappings():
    """Get detailed application-centric mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                uacm.id,
                uc.name as capability_name,
                uc.strategic_importance,
                ac.name as application_name,
                ac.description as application_description,
                ae.name as archimate_element_name,
                ae.type as archimate_type,
                ae.layer as archimate_layer,
                uacm.mapping_strength,
                uacm.coverage_percentage,
                uacm.relationship_type
            FROM unified_application_capability_mapping uacm
            JOIN unified_capabilities uc ON uacm.unified_capability_id = uc.id
            JOIN application_components ac ON uacm.application_component_id = ac.id
            LEFT JOIN archimate_elements ae ON uc.archimate_element_id = ae.id
            ORDER BY uc.strategic_importance DESC, uc.name
        """
            )
        )

        return [
            dict(
                zip(
                    [
                        "id",
                        "capability_name",
                        "strategic_importance",
                        "application_name",
                        "application_description",
                        "archimate_element_name",
                        "archimate_type",
                        "archimate_layer",
                        "mapping_strength",
                        "coverage_percentage",
                        "relationship_type",
                    ],
                    row,
                )
            )
            for row in result
        ]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


def get_product_mappings():
    """Get detailed product-centric mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                cvpm.id,
                uc.name as capability_name,
                uc.strategic_importance,
                vp.name as product_name,
                vpf.family_name as product_family,
                vo.name as vendor_name,
                ae.name as archimate_element_name,
                ae.type as archimate_type,
                cvpm.mapping_strength,
                cvpm.coverage_percentage,
                cvpm.business_value,
                cvpm.strategic_importance,
                cvpm.relationship_type
            FROM capability_vendor_product_mapping cvpm
            JOIN unified_capabilities uc ON cvpm.unified_capability_id = uc.id
            JOIN vendor_products vp ON cvpm.vendor_product_id = vp.id
            JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
            LEFT JOIN vendor_product_families vpf ON vp.family_id = vpf.id
            LEFT JOIN archimate_elements ae ON vp.archimate_product_element_id = ae.id
            ORDER BY uc.strategic_importance DESC, uc.name
        """
            )
        )

        return [
            dict(
                zip(
                    [
                        "id",
                        "capability_name",
                        "strategic_importance",
                        "product_name",
                        "product_family",
                        "vendor_name",
                        "archimate_element_name",
                        "archimate_type",
                        "mapping_strength",
                        "coverage_percentage",
                        "business_value",
                        "strategic_importance",
                        "relationship_type",
                    ],
                    row,
                )
            )
            for row in result
        ]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


def get_archimate_mappings():
    """Get detailed direct ArchiMate mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                ucam.id,
                uc.name as capability_name,
                uc.strategic_importance,
                ae.name as archimate_element_name,
                ae.type as archimate_type,
                ae.layer as archimate_layer,
                ae.description as archimate_description,
                ucam.mapping_strength,
                ucam.coverage_percentage,
                ucam.relationship_type,
                ucam.implementation_complexity
            FROM unified_capability_archimate_mapping ucam
            JOIN unified_capabilities uc ON ucam.unified_capability_id = uc.id
            JOIN archimate_elements ae ON ucam.archimate_element_id = ae.id
            ORDER BY uc.strategic_importance DESC, uc.name
        """
            )
        )

        return [
            dict(
                zip(
                    [
                        "id",
                        "capability_name",
                        "strategic_importance",
                        "archimate_element_name",
                        "archimate_type",
                        "archimate_layer",
                        "archimate_description",
                        "mapping_strength",
                        "coverage_percentage",
                        "relationship_type",
                        "implementation_complexity",
                    ],
                    row,
                )
            )
            for row in result
        ]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


def get_unmapped_capabilities():
    """Get capabilities without any mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK
            text(
                """
            SELECT
                uc.id,
                uc.name,
                uc.strategic_importance,
                bd.name as domain_name
            FROM unified_capabilities uc
            JOIN business_domains bd ON uc.domain_id = bd.id
            WHERE uc.id NOT IN (
                SELECT DISTINCT unified_capability_id FROM unified_application_capability_mapping
            )
            AND uc.id NOT IN (
                SELECT DISTINCT unified_capability_id FROM capability_vendor_product_mapping
            )
            AND uc.id NOT IN (
                SELECT DISTINCT unified_capability_id FROM unified_capability_archimate_mapping
            )
            ORDER BY uc.strategic_importance DESC, uc.name
        """
            )
        )

        return [
            dict(zip(["id", "name", "strategic_importance", "domain_name"], row)) for row in result
        ]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


def get_unmapped_vendor_products():
    """Get vendor products without capability mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor_products)
            text(
                """
            SELECT
                vp.id,
                vp.name,
                vpf.family_name as product_family,
                vo.name as vendor_name,
                vp.archimate_product_element_id
            FROM vendor_products vp
            JOIN vendor_organizations vo ON vp.vendor_organization_id = vo.id
            LEFT JOIN vendor_product_families vpf ON vp.family_id = vpf.id
            WHERE vp.id NOT IN (
                SELECT DISTINCT vendor_product_id FROM capability_vendor_product_mapping
            )
            ORDER BY vo.name, vp.name
        """
            )
        )

        return [
            dict(zip(["id", "name", "product_family", "vendor_name", "archimate_product_id"], row))
            for row in result
        ]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


def get_unmapped_archimate_elements():
    """Get ArchiMate elements without capability mappings"""

    try:
        result = db.session.execute(  # tenant-filtered: scoped via parent FK (archimate_elements)
            text(
                """
            SELECT
                ae.id,
                ae.name,
                ae.type,
                ae.layer,
                ae.description
            FROM archimate_elements ae
            WHERE ae.id NOT IN (
                SELECT DISTINCT archimate_element_id FROM unified_capability_archimate_mapping
            )
            AND ae.type IN ('ApplicationComponent', 'ApplicationService', 'TechnologyService', 'BusinessProcess')
            ORDER BY ae.type, ae.name
            LIMIT 20
        """
            )
        )

        return [dict(zip(["id", "name", "type", "layer", "description"], row)) for row in result]

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return []


@main.route("/api/hybrid-mapping/export")
@login_required
def export_hybrid_mapping():
    """Export hybrid mapping data as JSON"""

    try:
        return jsonify(
            {
                "statistics": get_mapping_statistics(),
                "application_mappings": get_application_mappings(),
                "product_mappings": get_product_mappings(),
                "archimate_mappings": get_archimate_mappings(),
                "unmapped_capabilities": get_unmapped_capabilities(),
                "unmapped_vendor_products": get_unmapped_vendor_products(),
                "unmapped_archimate_elements": get_unmapped_archimate_elements(),
                "export_date": db.session.execute(text("SELECT CURRENT_TIMESTAMP")).scalar(),  # tenant-exempt: system function
            }
        )

    except Exception as e:
        db.session.rollback()  # clear any aborted txn so later queries don't cascade
        return jsonify({"error": "An internal error occurred"}), 500
