"""PLT-004: CSV import for solution junction table bulk population.

Provides a single POST endpoint that accepts a CSV file with columns:
  entity_type, entity_name, entity_id (optional)

Supported entity_type values:
  application, capability, vendor, archimate

For each row the route attempts:
  1. Direct ID lookup (if entity_id is provided)
  2. Exact name match (case-insensitive)
  3. Partial name match (ILIKE) — returns first match

Results summary: created (new links), skipped (already linked), errors (no match / bad input).

Routes are attached to ``solution_design_bp`` (url_prefix=/solutions).
"""

import csv
import io
import logging

from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models.solution_models import Solution

from .solution_design_routes import solution_design_bp

logger = logging.getLogger(__name__)

_MAX_CSV_SIZE = 2 * 1024 * 1024  # 2 MB limit
_MAX_ROWS = 500
_VALID_ENTITY_TYPES = {"application", "capability", "vendor", "archimate"}
_REQUIRED_COLUMNS = {"entity_type", "entity_name"}


def _match_application(entity_name, entity_id):
    """Resolve an ApplicationComponent by ID or name."""
    from app.models.application_portfolio import ApplicationComponent

    if entity_id:
        app_obj = db.session.get(ApplicationComponent, entity_id)
        if app_obj:
            return app_obj
    # Exact match first (case-insensitive)
    app_obj = ApplicationComponent.query.filter(
        ApplicationComponent.name.ilike(entity_name)
    ).first()
    if app_obj:
        return app_obj
    # Partial match fallback
    app_obj = ApplicationComponent.query.filter(
        ApplicationComponent.name.ilike(f"%{entity_name}%")
    ).first()
    return app_obj


def _match_capability(entity_name, entity_id):
    """Resolve a BusinessCapability by ID or name."""
    from app.models.business_capabilities import BusinessCapability

    if entity_id:
        cap = db.session.get(BusinessCapability, entity_id)
        if cap:
            return cap
    cap = BusinessCapability.query.filter(
        BusinessCapability.name.ilike(entity_name)
    ).first()
    if cap:
        return cap
    cap = BusinessCapability.query.filter(
        BusinessCapability.name.ilike(f"%{entity_name}%")
    ).first()
    return cap


def _match_vendor(entity_name, entity_id):
    """Resolve a VendorProduct by ID or name (also checks VendorOrganization name)."""
    from app.models.vendor.vendor_organization import VendorProduct

    if entity_id:
        vp = db.session.get(VendorProduct, entity_id)
        if vp:
            return vp
    vp = VendorProduct.query.filter(
        VendorProduct.name.ilike(entity_name)
    ).first()
    if vp:
        return vp
    vp = VendorProduct.query.filter(
        VendorProduct.name.ilike(f"%{entity_name}%")
    ).first()
    return vp


def _match_archimate(entity_name, entity_id):
    """Resolve an ArchitectureElement by ID or name."""
    from app.models.archimate import ArchitectureElement

    if entity_id:
        el = db.session.get(ArchitectureElement, entity_id)
        if el:
            return el
    el = ArchitectureElement.query.filter(
        ArchitectureElement.name.ilike(entity_name)
    ).first()
    if el:
        return el
    el = ArchitectureElement.query.filter(
        ArchitectureElement.name.ilike(f"%{entity_name}%")
    ).first()
    return el


_MATCHERS = {
    "application": _match_application,
    "capability": _match_capability,
    "vendor": _match_vendor,
    "archimate": _match_archimate,
}


def _link_application(solution, matched_entity):
    """Link an ApplicationComponent to a solution. Returns True if created, False if duplicate."""
    from app.models.solution_models import solution_applications

    already = db.session.execute(  # tenant-filtered: scoped via solution FK
        solution_applications.select().where(
            db.and_(
                solution_applications.c.solution_id == solution.id,
                solution_applications.c.application_component_id == matched_entity.id,
            )
        )
    ).first()
    if already:
        return False
    db.session.execute(  # tenant-filtered: scoped via solution FK
        solution_applications.insert().values(
            solution_id=solution.id,
            application_component_id=matched_entity.id,
            role="supporting",
        )
    )
    return True


def _link_capability(solution, matched_entity):
    """Link a BusinessCapability to a solution. Returns True if created, False if duplicate."""
    from app.models.solution_models import SolutionCapabilityMapping

    existing = SolutionCapabilityMapping.query.filter_by(
        solution_id=solution.id, capability_id=matched_entity.id
    ).first()
    if existing:
        return False
    mapping = SolutionCapabilityMapping(
        solution_id=solution.id,
        capability_id=matched_entity.id,
    )
    db.session.add(mapping)
    return True


def _link_vendor(solution, matched_entity):
    """Link a VendorProduct to a solution. Returns True if created, False if duplicate."""
    from app.models.solution_models import solution_vendor_products

    already = db.session.execute(  # tenant-filtered: scoped via solution FK
        solution_vendor_products.select().where(
            db.and_(
                solution_vendor_products.c.solution_id == solution.id,
                solution_vendor_products.c.vendor_product_id == matched_entity.id,
            )
        )
    ).first()
    if already:
        return False
    db.session.execute(  # tenant-filtered: scoped via solution FK
        solution_vendor_products.insert().values(
            solution_id=solution.id,
            vendor_product_id=matched_entity.id,
        )
    )
    return True


def _link_archimate(solution, matched_entity):
    """Link an ArchitectureElement to a solution. Returns True if created, False if duplicate."""
    from app.models.solution_models import SolutionArchiMateElement

    existing = SolutionArchiMateElement.query.filter_by(
        solution_id=solution.id,
        element_id=matched_entity.id,
        element_table="architecture_elements",
    ).first()
    if existing:
        return False
    el = SolutionArchiMateElement(
        solution_id=solution.id,
        element_id=matched_entity.id,
        element_table="architecture_elements",
        element_name=matched_entity.name,
        layer_type=getattr(matched_entity, "layer", None) or "application",
    )
    db.session.add(el)
    return True


_LINKERS = {
    "application": _link_application,
    "capability": _link_capability,
    "vendor": _link_vendor,
    "archimate": _link_archimate,
}


@solution_design_bp.route("/<int:solution_id>/import-junctions", methods=["POST"])
@login_required
def import_junctions_csv(solution_id):
    """Import junction table links from a CSV file upload.

    Accepts multipart/form-data with a ``file`` field containing a CSV.
    Required columns: entity_type, entity_name
    Optional column: entity_id

    Returns JSON summary with created/skipped/error counts and row-level details.
    """
    solution = db.session.get(Solution, solution_id)
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    # Extract CSV file
    if not request.files or "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send a CSV file in the 'file' field."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty filename."}), 400

    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted."}), 400

    raw = uploaded.read()
    if len(raw) > _MAX_CSV_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {_MAX_CSV_SIZE // (1024 * 1024)} MB."}), 413

    # Decode CSV content
    try:
        text = raw.decode("utf-8-sig")  # Handle BOM from Excel exports
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            return jsonify({"error": "Could not decode file. Please use UTF-8 encoding."}), 400

    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return jsonify({"error": "CSV file is empty or has no header row."}), 400

        # Normalize header names (strip whitespace, lowercase)
        normalized_fields = {f.strip().lower() for f in reader.fieldnames if f}
        missing_cols = _REQUIRED_COLUMNS - normalized_fields
        if missing_cols:
            return jsonify({
                "error": f"Missing required CSV columns: {', '.join(sorted(missing_cols))}. "
                         f"Expected columns: entity_type, entity_name, entity_id (optional)."
            }), 400
    except csv.Error as exc:
        return jsonify({"error": f"CSV parsing error: {exc}"}), 400

    # Re-create reader with normalized fieldnames
    reader = csv.DictReader(
        io.StringIO(text),
        fieldnames=[f.strip().lower() for f in reader.fieldnames],
    )
    next(reader)  # Skip header row (we replaced fieldnames)

    created = []
    skipped = []
    errors = []
    row_num = 0

    for row in reader:
        row_num += 1
        if row_num > _MAX_ROWS:
            errors.append({
                "row": row_num,
                "entity_type": "",
                "entity_name": "",
                "reason": f"CSV exceeds maximum of {_MAX_ROWS} rows. Remaining rows skipped.",
            })
            break

        entity_type = (row.get("entity_type") or "").strip().lower()
        entity_name = (row.get("entity_name") or "").strip()
        entity_id_str = (row.get("entity_id") or "").strip()

        # Validate entity_type
        if entity_type not in _VALID_ENTITY_TYPES:
            errors.append({
                "row": row_num,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "reason": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(_VALID_ENTITY_TYPES))}.",
            })
            continue

        # Validate entity_name
        if not entity_name:
            errors.append({
                "row": row_num,
                "entity_type": entity_type,
                "entity_name": "",
                "reason": "entity_name is required and cannot be empty.",
            })
            continue

        # Parse optional entity_id
        entity_id = None
        if entity_id_str:
            try:
                entity_id = int(entity_id_str)
            except ValueError:
                errors.append({
                    "row": row_num,
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                    "reason": f"entity_id '{entity_id_str}' is not a valid integer.",
                })
                continue

        # Match entity
        matcher = _MATCHERS[entity_type]
        matched = matcher(entity_name, entity_id)
        if not matched:
            errors.append({
                "row": row_num,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "reason": f"No matching {entity_type} found for '{entity_name}'"
                          + (f" (id={entity_id})" if entity_id else "") + ".",
            })
            continue

        # Link entity
        linker = _LINKERS[entity_type]
        try:
            was_created = linker(solution, matched)
        except Exception as exc:
            logger.warning(
                "PLT-004: Error linking %s '%s' to solution %s: %s",
                entity_type, entity_name, solution_id, exc,
            )
            errors.append({
                "row": row_num,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "reason": f"Database error: {exc}",
            })
            continue

        entry = {
            "row": row_num,
            "entity_type": entity_type,
            "entity_name": entity_name,
            "matched_name": getattr(matched, "name", str(matched)),
            "matched_id": matched.id,
        }
        if was_created:
            created.append(entry)
        else:
            skipped.append(entry)

    # Commit all successful links
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("PLT-004: Commit failed for solution %s import: %s", solution_id, exc)
        return jsonify({"error": f"Database commit failed: {exc}"}), 500

    logger.info(
        "PLT-004: CSV junction import for solution %s — %d created, %d skipped, %d errors (user: %s)",
        solution_id, len(created), len(skipped), len(errors),
        getattr(current_user, "username", "unknown"),
    )

    return jsonify({
        "solution_id": solution_id,
        "summary": {
            "created": len(created),
            "skipped": len(skipped),
            "errors": len(errors),
            "total_rows": row_num,
        },
        "created": created,
        "skipped": skipped,
        "errors": errors,
    })
