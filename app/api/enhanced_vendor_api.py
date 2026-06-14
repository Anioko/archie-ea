"""
Enhanced Vendor API Integration

This module adds API endpoints to integrate the improved vendor dataset
with the existing vendor management system.
"""
import json

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app import db
from app.models.vendor import VendorOrganization, VendorProduct

# Create blueprint
enhanced_vendor_bp = Blueprint("enhanced_vendor", __name__, url_prefix="/api/enhanced-vendors")


@enhanced_vendor_bp.route("/dataset", methods=["GET"])
@login_required
def get_vendor_dataset():
    """
    Get the improved vendor dataset as JSON.

    Query Parameters:
        - domain: Filter by domain (optional)
        - vendor: Filter by vendor name (optional)
        - confidence: Filter by classification confidence (high, medium, low)
        - limit: Limit number of results (default: 100)
        - offset: Offset for pagination (default: 0)

    Returns:
        JSON response with vendor products and metadata
    """
    try:
        # Load the improved dataset
        with open("vendor_products_improved_consolidated.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)

        vendor_products = dataset.get("vendor_products", [])

        # Apply filters
        domain_filter = request.args.get("domain")
        vendor_filter = request.args.get("vendor")
        confidence_filter = request.args.get("confidence")

        if domain_filter:
            vendor_products = [
                vp
                for vp in vendor_products
                if vp.get("domain", "").lower() == domain_filter.lower()
            ]

        if vendor_filter:
            vendor_products = [
                vp
                for vp in vendor_products
                if vp.get("vendor_name", "").lower() == vendor_filter.lower()
            ]

        if confidence_filter:
            vendor_products = [
                vp
                for vp in vendor_products
                if vp.get("data_quality", {}).get("classification_confidence") == confidence_filter
            ]

        # Apply pagination
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))

        total_count = len(vendor_products)
        vendor_products = vendor_products[offset : offset + limit]

        return jsonify(
            {
                "success": True,
                "data": {
                    "vendor_products": vendor_products,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "filters_applied": {
                        "domain": domain_filter,
                        "vendor": vendor_filter,
                        "confidence": confidence_filter,
                    },
                },
                "metadata": dataset.get("consolidation_info", {}),
                "domain_analysis": dataset.get("domain_analysis", {}),
            }
        )

    except FileNotFoundError:
        return jsonify({"success": False, "error": "Vendor dataset file not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enhanced_vendor_bp.route("/domains", methods=["GET"])
@login_required
def get_domain_analysis():
    """
    Get domain distribution analysis.

    Returns:
        JSON response with domain statistics and breakdown
    """
    try:
        # Load the improved dataset
        with open("vendor_products_improved_consolidated.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)

        domain_analysis = dataset.get("domain_analysis", {})
        data_quality_summary = dataset.get("data_quality_summary", {})

        # Enhance with database statistics if available
        db_stats = {}
        try:
            db_domain_counts = (
                db.session.query(
                    VendorProduct.domain, db.func.count(VendorProduct.id).label("count")
                )
                .filter(VendorProduct.domain.isnot(None))
                .group_by(VendorProduct.domain)
                .all()
            )

            db_stats = {domain: count for domain, count in db_domain_counts}
        except Exception:
            db_stats = {}

        return jsonify(
            {
                "success": True,
                "data": {
                    "domain_distribution": domain_analysis,
                    "database_counts": db_stats,
                    "data_quality_summary": data_quality_summary,
                    "total_domains": len(domain_analysis),
                    "total_products": sum(domain_analysis.values()),
                },
            }
        )

    except FileNotFoundError:
        return jsonify({"success": False, "error": "Vendor dataset file not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enhanced_vendor_bp.route("/compare", methods=["GET"])
@login_required
def compare_dataset_vs_database():
    """
    Compare the improved dataset with existing database records.

    Returns:
        JSON response with comparison analysis
    """
    try:
        # Load the improved dataset
        with open("vendor_products_improved_consolidated.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)

        dataset_products = dataset.get("vendor_products", [])

        # Get database products
        db_products = VendorProduct.query.options(
            joinedload(VendorProduct.vendor_organization)
        ).all()

        # Create lookup dictionaries
        dataset_lookup = {
            (p["vendor_name"].lower(), p["product_name"].lower()): p for p in dataset_products
        }

        db_lookup = {
            (
                p.vendor_organization.name.lower() if p.vendor_organization else "unknown",
                p.name.lower(),
            ): p
            for p in db_products
        }

        # Find differences
        dataset_only_keys = set(dataset_lookup.keys()) - set(db_lookup.keys())
        db_only_keys = set(db_lookup.keys()) - set(dataset_lookup.keys())
        common_keys = set(dataset_lookup.keys()) & set(db_lookup.keys())

        # Analyze differences
        comparison = {
            "dataset_only_count": len(dataset_only_keys),
            "database_only_count": len(db_only_keys),
            "common_count": len(common_keys),
            "dataset_total": len(dataset_products),
            "database_total": len(db_products),
            "dataset_only": [
                {
                    "vendor_name": key[0],
                    "product_name": key[1],
                    "domain": dataset_lookup[key].get("domain"),
                    "capabilities_count": len(dataset_lookup[key].get("capabilities", [])),
                }
                for key in list(dataset_only_keys)[:20]  # Limit to first 20
            ],
            "database_only": [
                {
                    "vendor_name": key[0],
                    "product_name": key[1],
                    "domain": db_lookup[key].domain,
                    "has_capabilities": bool(db_lookup[key].capabilities),
                }
                for key in list(db_only_keys)[:20]  # Limit to first 20
            ],
            "domain_comparison": {},
            "quality_improvements": {
                "products_with_domain_classification": len([p for p in db_products if p.domain]),
                "products_with_capabilities": len([p for p in db_products if p.capabilities]),
                "products_with_apqc_processes": len([p for p in db_products if p.apqc_processes]),
                "high_confidence_products": len(
                    [p for p in db_products if p.classification_confidence == "high"]
                ),
            },
        }

        # Domain comparison
        dataset_domains = set(p.get("domain") for p in dataset_products if p.get("domain"))
        db_domains = set(p.domain for p in db_products if p.domain)

        comparison["domain_comparison"] = {
            "dataset_only_domains": list(dataset_domains - db_domains),
            "database_only_domains": list(db_domains - dataset_domains),
            "common_domains": list(dataset_domains & db_domains),
        }

        return jsonify({"success": True, "data": comparison})

    except FileNotFoundError:
        return jsonify({"success": False, "error": "Vendor dataset file not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enhanced_vendor_bp.route("/search", methods=["GET"])
@login_required
def search_vendor_products():
    """
    Search vendor products with advanced filtering.

    Query Parameters:
        - q: Search query (searches vendor name, product name, capabilities)
        - domain: Filter by domain
        - capability: Filter by capability (must be in capabilities array)
        - confidence: Filter by classification confidence
        - has_archimate: Filter by ArchiMate template availability

    Returns:
        JSON response with matching vendor products
    """
    try:
        # Get search parameters
        query = request.args.get("q", "").strip().lower()
        domain = request.args.get("domain")
        capability = request.args.get("capability")
        confidence = request.args.get("confidence")
        has_archimate = request.args.get("has_archimate")

        # Build database query
        db_query = VendorProduct.query.options(joinedload(VendorProduct.vendor_organization))

        # Apply filters
        if domain:
            db_query = db_query.filter(VendorProduct.domain == domain)

        if confidence:
            db_query = db_query.filter(VendorProduct.classification_confidence == confidence)

        if has_archimate is not None:
            has_archimate_bool = has_archimate.lower() == "true"
            db_query = db_query.filter(VendorProduct.has_archimate_template == has_archimate_bool)

        # Execute query
        products = db_query.all()

        # Filter by text search and capability
        filtered_products = []
        for product in products:
            product_dict = product.to_dict()

            # Text search
            if query:
                searchable_text = (
                    (product.vendor_organization.name if product.vendor_organization else "")
                    + " "
                    + product.name
                    + " "
                    + " ".join(product_dict.get("capabilities", []))
                ).lower()

                if query not in searchable_text:
                    continue

            # Capability filter
            if capability and capability not in product_dict.get("capabilities", []):
                continue

            filtered_products.append(product_dict)

        return jsonify(
            {
                "success": True,
                "data": {
                    "products": filtered_products,
                    "total_count": len(filtered_products),
                    "search_params": {
                        "query": query,
                        "domain": domain,
                        "capability": capability,
                        "confidence": confidence,
                        "has_archimate": has_archimate,
                    },
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enhanced_vendor_bp.route("/quality-report", methods=["GET"])
@login_required
def get_quality_report():
    """
    Generate a quality report for the vendor dataset.

    Returns:
        JSON response with quality metrics and recommendations
    """
    try:
        # Get all products from database
        products = VendorProduct.query.limit(2000).all()

        if not products:
            return jsonify({"success": False, "error": "No vendor products found in database"}), 404

        # Calculate quality metrics
        total_products = len(products)
        high_confidence = len([p for p in products if p.classification_confidence == "high"])
        medium_confidence = len([p for p in products if p.classification_confidence == "medium"])
        low_confidence = len([p for p in products if p.classification_confidence == "low"])

        with_capabilities = len([p for p in products if p.capabilities])
        with_apqc_processes = len([p for p in products if p.apqc_processes])
        with_archimate = len([p for p in products if p.has_archimate_template])

        # Domain distribution
        domain_counts = {}
        for product in products:
            domain = product.domain or "Unknown"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Calculate average quality scores
        quality_scores = [p.get_quality_score() for p in products]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # Generate recommendations
        recommendations = []

        if low_confidence / total_products > 0.3:
            recommendations.append(
                "Consider reviewing low-confidence classifications for better accuracy"
            )

        if with_capabilities / total_products < 0.8:
            recommendations.append("Add capability descriptions to improve product analysis")

        if with_apqc_processes / total_products < 0.7:
            recommendations.append("Map products to APQC processes for better business alignment")

        if with_archimate / total_products < 0.5:
            recommendations.append("Create ArchiMate templates for better architecture modeling")

        return jsonify(
            {
                "success": True,
                "data": {
                    "summary": {
                        "total_products": total_products,
                        "average_quality_score": round(avg_quality_score, 1),
                        "products_with_capabilities": with_capabilities,
                        "products_with_apqc_processes": with_apqc_processes,
                        "products_with_archimate_templates": with_archimate,
                    },
                    "confidence_distribution": {
                        "high": high_confidence,
                        "medium": medium_confidence,
                        "low": low_confidence,
                    },
                    "domain_distribution": domain_counts,
                    "quality_metrics": {
                        "classification_coverage": (high_confidence + medium_confidence)
                        / total_products,
                        "capability_coverage": with_capabilities / total_products,
                        "process_mapping_coverage": with_apqc_processes / total_products,
                        "archimate_template_coverage": with_archimate / total_products,
                    },
                    "recommendations": recommendations,
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
