"""
MIGRATION: Copied from app/routes/vendor_management_routes.py
Changes: `from app import db` -> `from app.extensions import db` (already correct in source)
Legacy file preserved at original location.

Vendor Management Routes - Production Ready
"""

from datetime import datetime
from flask import (
    Blueprint,
    jsonify,
    request,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.decorators import audit_log, require_roles  # dead-code-ok
from app.extensions import db
from app.models.vendor_organization import VendorOrganization
from app.utils.pagination import safe_int_arg

# Allowlist for vendor updates (security: prevent mass assignment)
VENDOR_UPDATE_ALLOWLIST = ["name", "vendor_type", "country", "description", "website"]


vendor_management_bp = Blueprint(
    "vendor_management",
    __name__,
    url_prefix="/vendor-management",
    template_folder="templates/vendor_management",
)


# ==================== VIEW ROUTES ====================


@vendor_management_bp.route("/create", methods=["GET", "POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("vendor_create")
def create_vendor():
    """Create new vendor (admin/architect only) with validation."""
    if request.method == "GET":
        return jsonify({"success": True, "message": "Use POST to create vendor"})

    # POST - create vendor
    data = request.get_json() or {}

    # Basic validation
    if not data.get("name"):
        return jsonify({"error": "Vendor name required"}), 400

    # Input length validation
    if len(str(data["name"])) > 200:
        return jsonify(
            {"error": "Vendor name exceeds maximum length of 200 characters"}
        ), 400

    if data.get("description") and len(str(data["description"])) > 5000:
        return jsonify(
            {"error": "Description exceeds maximum length of 5000 characters"}
        ), 400

    # Check for duplicates with row locking
    from sqlalchemy import func

    existing = (
        VendorOrganization.query.with_for_update()
        .filter(func.lower(VendorOrganization.name) == data["name"].lower())
        .first()
    )

    if existing:
        return jsonify(
            {
                "error": f"Vendor '{data['name']}' already exists",
                "existing_id": existing.id,
            }
        ), 409

    vendor = VendorOrganization(
        name=data["name"],
        vendor_type=data.get("vendor_type"),
        headquarters_location=data.get("country"),  # model column is headquarters_location
        description=data.get("description"),
        website=data.get("website"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.session.add(vendor)
    db.session.commit()

    # Audit logging
    current_app.logger.info(
        f"[AUDIT] Vendor created via management API: {vendor.name} (ID: {vendor.id}) by {current_user.email}"
    )

    return jsonify(
        {
            "status": "success",
            "vendor_id": vendor.id,
            "message": f"Vendor '{vendor.name}' created",
        }
    ), 201


# ==================== API ROUTES ====================


@vendor_management_bp.route("/api/vendors", methods=["GET"])
@login_required
def api_list_vendors():
    """API: List all vendors (paginated)."""
    page = safe_int_arg('page', 1, minimum=1)
    per_page = safe_int_arg('per_page', 20, minimum=1, maximum=500)

    paginated = VendorOrganization.query.paginate(page=page, per_page=per_page)

    return jsonify(
        {
            "status": "success",
            "total": paginated.total,
            "pages": paginated.pages,
            "current_page": page,
            "vendors": [v.to_dict() for v in paginated.items],
        }
    )


@vendor_management_bp.route("/api/vendors", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("vendor_api_create")
def api_create_vendor():
    """API: Create vendor with validation and duplicate prevention."""
    data = request.get_json() or {}

    if not data.get("name"):
        return jsonify({"error": "Vendor name required"}), 400

    # Input length validation
    if len(str(data["name"])) > 200:
        return jsonify(
            {"error": "Vendor name exceeds maximum length of 200 characters"}
        ), 400

    if data.get("description") and len(str(data["description"])) > 5000:
        return jsonify(
            {"error": "Description exceeds maximum length of 5000 characters"}
        ), 400

    # Check for duplicates with row locking
    existing = (
        VendorOrganization.query.with_for_update()
        .filter(func.lower(VendorOrganization.name) == data["name"].lower())
        .first()
    )

    if existing:
        return jsonify(
            {
                "error": f"Vendor '{data['name']}' already exists",
                "existing_id": existing.id,
            }
        ), 409

    vendor = VendorOrganization(
        name=data["name"],
        vendor_type=data.get("vendor_type"),
        headquarters_location=data.get("country"),  # model column is headquarters_location
        description=data.get("description"),
        website=data.get("website"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.session.add(vendor)
    db.session.commit()

    # Audit logging
    current_app.logger.info(
        f"[AUDIT] Vendor created via API: {vendor.name} (ID: {vendor.id}) by {current_user.email}"
    )

    return jsonify(
        {
            "status": "success",
            "vendor": vendor.to_dict(),
        }
    ), 201


@vendor_management_bp.route("/api/vendors/<int:vendor_id>", methods=["GET"])
@login_required
def api_get_vendor(vendor_id):
    """API: Get vendor details."""
    vendor = VendorOrganization.query.get_or_404(vendor_id)
    return jsonify(
        {
            "status": "success",
            "vendor": vendor.to_dict(),
        }
    )


@vendor_management_bp.route("/api/vendors/<int:vendor_id>", methods=["PUT"])
@login_required
@require_roles("admin", "architect")
@audit_log("vendor_api_update")
def api_update_vendor(vendor_id):
    """API: Update vendor (with allowlist protection)."""
    vendor = VendorOrganization.query.get_or_404(vendor_id)
    data = request.get_json() or {}

    # Use allowlist to prevent mass assignment
    for key in VENDOR_UPDATE_ALLOWLIST:
        if key in data:
            setattr(vendor, key, data[key])

    vendor.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "vendor": vendor.to_dict(),
        }
    )


@vendor_management_bp.route("/api/vendors/<int:vendor_id>", methods=["DELETE"])
@login_required
@require_roles("admin")
@audit_log("vendor_api_delete")
def api_delete_vendor(vendor_id):
    """
    API: Delete vendor (admin only).

    Cascade deletes:
    - Vendor products (handled by SQLAlchemy cascade)
    - Vendor capability mappings
    - Related embeddings and analysis data
    """
    vendor = VendorOrganization.query.get_or_404(vendor_id)

    # Get counts before deletion for logging
    product_count = len(vendor.products) if hasattr(vendor, "products") else 0
    vendor_name = vendor.name

    try:
        # Log deletion attempt
        current_app.logger.info(
            f"[VENDOR-DELETE] User {current_user.email} deleting vendor "
            f"'{vendor_name}' (ID: {vendor_id}) with {product_count} products"
        )

        # Delete the vendor (cascade will handle products due to
        # cascade="all, delete-orphan" in the model relationship)
        db.session.delete(vendor)
        db.session.commit()

        # Log successful deletion
        current_app.logger.info(
            f"[VENDOR-DELETE] Successfully deleted vendor '{vendor_name}' "
            f"(ID: {vendor_id}) and {product_count} associated products"
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Vendor '{vendor_name}' deleted",
                "deleted_products": product_count,
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"[VENDOR-DELETE] Failed to delete vendor '{vendor_name}' "
            f"(ID: {vendor_id}): {str(e)}",
            exc_info=True,
        )
        return jsonify(
            {"status": "error", "message": f"Failed to delete vendor: {str(e)}"}
        ), 500
