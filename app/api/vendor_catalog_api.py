from flask import Blueprint, jsonify
from flask_login import login_required
import logging

from app.models.vendor.vendor_organization import VendorOrganization

vendor_catalog_api_bp = Blueprint("vendor_catalog_api", __name__)
logger = logging.getLogger(__name__)


def _vendor_to_dict(v):
    try:
        products = getattr(v, "products", []) or []
        product_list = [p.to_dict() for p in products if hasattr(p, "to_dict")]
    except Exception as e:
        logger.error(
            "Failed to serialize vendor products vendor_id=%s: %s",
            getattr(v, "id", None),
            e,
            exc_info=True,
        )
        product_list = []
    return {
        "id": v.id,
        "name": v.name,
        "display_name": v.display_name,
        "vendor_type": v.vendor_type,
        "headquarters_location": v.headquarters_location,
        "website": v.website,
        "description": v.description,
        "year_founded": getattr(v, "year_founded", None),
        "public_company": getattr(v, "public_company", None),
        "products": product_list,
        "created_at": v.created_at.isoformat() if getattr(v, "created_at", None) else None,
        "updated_at": v.updated_at.isoformat() if getattr(v, "updated_at", None) else None,
    }


@vendor_catalog_api_bp.route("/vendors", methods=["GET"])
@login_required
def list_vendors():
    vendors = VendorOrganization.query.filter_by(status="active").all()
    return jsonify({"vendors": [_vendor_to_dict(v) for v in vendors], "count": len(vendors)})
