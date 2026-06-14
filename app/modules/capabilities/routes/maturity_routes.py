#!/usr/bin/env python3
"""
Migration: Copied from app/main/capability_maturity_routes.py -> app/modules/capabilities/routes/maturity_routes.py
Date: 2026-02-14 | Relative imports fixed for new location.

Business Capability Maturity Management Routes

Provides user-friendly routes for managing business capability maturity levels
without requiring admin privileges.
"""

from datetime import datetime

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import audit_log
from sqlalchemy import text

from app import db
from app.utils.framework_classifier import FrameworkClassifier

# Create blueprint
maturity_management = Blueprint("maturity_management", __name__)


# maturity_dashboard removed — empty shell page, frozen sidebar link
# (template capability_maturity/dashboard.html deleted)


@maturity_management.route("/capability-maturity/search")
@login_required
def search_capabilities():
    """Search and filter capabilities"""

    query = request.args.get("q", "")
    domain = request.args.get("domain", "")
    strategic_importance = request.args.get("strategic_importance", "")
    page = int(request.args.get("page", 1))
    per_page = 20

    try:
        # Build base query
        base_query = """
            SELECT id, name, business_domain, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, maturity_assessment_date,
                   business_owner, description, category, capability_type
            FROM business_capability
            WHERE 1=1
        """

        params = {}


        if query:
            base_query += " AND (name ILIKE :query OR description ILIKE :query)"
            params["query"] = f"%{query}%"

        if domain:
            base_query += " AND business_domain = :domain"
            params["domain"] = domain

        if strategic_importance:
            base_query += " AND strategic_importance = :strategic_importance"
            params["strategic_importance"] = strategic# Add ordering and pagination
        base_query += " ORDER BY business_domain, name LIMIT :limit OFFSET :offset"
        params["limit"] = per_page
        params["offset"] = (page - 1) * per_page

        result = db.session.execute(text(base_query), params)  # tenant-filtered
        capabilities = result.fetchall()

        # Get total count for pagination
        count_query = base_query.replace(
            "SELECT id, name, business_domain, current_maturity_level, target_maturity_level, maturity_gap, strategic_importance, maturity_assessment_date, business_owner, description",
            "SELECT COUNT(*)",
        )
        count_query = count_query.replace(
            "ORDER BY business_domain, name LIMIT :limit OFFSET :offset", ""
        )

        count_result = db.session.execute(text(count_query), params)  # tenant-filtered
        total_count = count_result.scalar()

        # Get available domains
        _domain_query = "SELECT DISTINCT business_domain FROM business_capability WHERE business_domain IS NOT NULL"
        _domain_params = {}

        return render_template(
            "capability_maturity/search.html",
            capabilities=capabilities,
            domains=domains,
            total_count=total_count,
            page=page,
            per_page=per_page,
            query=query,
            selected_domain=domain,
            selected_importance=strategic_importance,
        )

    except Exception as e:
        flash("Error searching capabilities. Please try again.", "error")
        return render_template(
            "capability_maturity/search.html", capabilities=[], domains=[], total_count=0
        )


@maturity_management.route("/capability-maturity/edit/<int:capability_id>", methods=["GET", "POST"])
@login_required
@audit_log("edit_capability_maturity")
def edit_capability_maturity(capability_id):
    """Edit maturity levels for a specific capability"""

    try:
        if request.method == "POST":
            # Get form data
            current_level = request.form.get("current_maturity_level")
            target_level = request.form.get("target_maturity_level")
            notes = request.form.get("assessment_notes", "")

            # Validate input
            if current_level:
                try:
                    current_level = int(current_level)
                    if current_level < 1 or current_level > 5:
                        flash("Current maturity level must be between 1 and 5", "error")
                        return redirect(
                            url_for(
                                "maturity_management.edit_capability_maturity",
                                capability_id=capability_id,
                            )
                        )
                except ValueError:
                    flash("Invalid current maturity level", "error")
                    return redirect(
                        url_for(
                            "maturity_management.edit_capability_maturity",
                            capability_id=capability_id,
                        )
                    )

            if target_level:
                try:
                    target_level = int(target_level)
                    if target_level < 1 or target_level > 5:
                        flash("Target maturity level must be between 1 and 5", "error")
                        return redirect(
                            url_for(
                                "maturity_management.edit_capability_maturity",
                                capability_id=capability_id,
                            )
                        )
                except ValueError:
                    flash("Invalid target maturity level", "error")
                    return redirect(
                        url_for(
                            "maturity_management.edit_capability_maturity",
                            capability_id=capability_id,
                        )
                    )

            # Calculate gap
            gap = 0
            if current_level is not None and target_level is not None:
                gap = target_level - current# Update the capability
            update_query = """
                UPDATE business_capability
                SET current_maturity_level = :current_level,
                    target_maturity_level = :target_level,
                    maturity_gap = :gap,
                    maturity_assessment_date = :assessment_date,
                    maturity_assessment_notes = :notes,
                    updated_at = :updated_at
                WHERE id = :capability_id
            """

            params = {
                "current_level": current_level,
                "target_level": target_level,
                "gap": gap,
                "assessment_date": datetime.utcnow(),
                "notes": notes,
                "updated_at": datetime.utcnow(),
                "capability_id": capability_id,
            }


            db.session.execute(text(update_query), params)  # tenant-filtered
            db.session.commit()

            flash("Capability maturity levels updated successfully!", "success")
            return redirect(url_for("maturity_management.search_capabilities"))

        # GET request - show edit form
        _get_query = """
            SELECT id, name, business_domain, description, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, business_owner, maturity_assessment_notes,
                   maturity_assessment_date
            FROM business_capability
            WHERE id = :capability_id
        """
        _get_params = {"capability_id": capability_id}

        capability = result.fetchone()

        if not capability:
            flash("Capability not found", "error")
            return redirect(url_for("maturity_management.search_capabilities"))

        return render_template("capability_maturity/edit.html", capability=capability)

    except Exception as e:
        flash("Error updating capability. Please try again.", "error")
        return redirect(url_for("maturity_management.search_capabilities"))


@maturity_management.route("/capability-maturity/batch-update", methods=["GET", "POST"])
@login_required
@audit_log("batch_update_maturity")
def batch_update_maturity():
    """Batch update maturity levels for multiple capabilities"""

    try:
        if request.method == "POST":
            # Get form data
            domain = request.form.get("domain", "")
            strategic_importance = request.form.get("strategic_importance", "")
            current_level = request.form.get("current_maturity_level")
            target_level = request.form.get("target_maturity_level")
            notes = request.form.get("assessment_notes", "")

            # Validate levels
            if current_level:
                try:
                    current_level = int(current_level)
                    if current_level < 1 or current_level > 5:
                        flash("Current maturity level must be between 1 and 5", "error")
                        return redirect(url_for("maturity_management.batch_update_maturity"))
                except ValueError:
                    flash("Invalid current maturity level", "error")
                    return redirect(url_for("maturity_management.batch_update_maturity"))

            if target_level:
                try:
                    target_level = int(target_level)
                    if target_level < 1 or target_level > 5:
                        flash("Target maturity level must be between 1 and 5", "error")
                        return redirect(url_for("maturity_management.batch_update_maturity"))
                except ValueError:
                    flash("Invalid target maturity level", "error")
                    return redirect(url_for("maturity_management.batch_update_maturity"))

            # Build update query
            update_query = """
                UPDATE business_capability
                SET current_maturity_level = :current_level,
                    target_maturity_level = :target_level,
                    maturity_assessment_date = :assessment_date,
                    maturity_assessment_notes = :notes,
                    updated_at = :updated_at
            """

            params = {
                "current_level": current_level,
                "target_level": target_level,
                "assessment_date": datetime.utcnow(),
                "notes": notes,
                "updated_at": datetime.utcnow(),
            }

            # Add WHERE conditions
            where_conditions = []

            if strategic_importance:
                where_conditions.append("strategic_importance = :strategic_importance")
                params["strategic_importance"] = strategic_importance

            if where_conditions:
                update_query += " WHERE " + " AND ".join(where_conditions)

            # Calculate and update gaps
            if current_level is not None and target_level is not None:
                update_query = update_query.replace(
                    "SET current_maturity_level = :current_level,",
                    "SET current_maturity_level = :current_level, maturity_gap = (:target_level - :current_level),",
                )

            # Execute update
            result = db.session.execute(text(update_query), params)  # tenant-filtered
            db.session.commit()

            flash(f"Successfully updated {result.rowcount} capabilities!", "success")
            return redirect(url_for("maturity_management.frameworks_overview"))

        # GET request - show batch update form
        # Get available domains
        _batch_domain_q = "SELECT DISTINCT business_domain FROM business_capability WHERE business_domain IS NOT NULL"
        _batch_domain_p = {}

        # Preview what would be updated
        domain = request.args.get("domain", "")
        strategic_importance = request.args.get("strategic_importance", "")

        preview_query = """
            SELECT id, name, business_domain, current_maturity_level, target_maturity_level, strategic_importance
            FROM business_capability
            WHERE 1=1
        """

        params = {}

        if strategic_importance:
            preview_query += " AND strategic_importance = :strategic_importance"
            params["strategic_importance"] = strategic_importance

        preview_query += " ORDER BY business_domain, name LIMIT 20"

        result = db.session.execute(text(preview_query), params)  # tenant-filtered
        preview_capabilities = result.fetchall()

        return render_template(
            "capability_maturity/batch_update.html",
            domains=domains,
            preview_capabilities=preview_capabilities,
            selected_domain=domain,
            selected_importance=strategic_importance,
        )

    except Exception as e:
        flash("Error in batch update. Please try again.", "error")
        return redirect(url_for("maturity_management.frameworks_overview"))


@maturity_management.route("/capability-maturity/api/capability/<int:capability_id>")
@login_required
def get_capability_api(capability_id):
    """API endpoint to get capability details"""

    try:
        _api_query = """
            SELECT id, name, business_domain, description, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, business_owner, maturity_assessment_notes,
                   maturity_assessment_date
            FROM business_capability
            WHERE id = :capability_id
        """
        _api_params = {"capability_id": capability_id}

        result = db.session.execute(text(_api_query), _api_params)
        capability = result.fetchone()

        if not capability:
            return jsonify({"error": "Capability not found"}), 404

        return jsonify(
            {
                "id": capability[0],
                "name": capability[1],
                "business_domain": capability[2],
                "description": capability[3],
                "current_maturity_level": capability[4],
                "target_maturity_level": capability[5],
                "maturity_gap": capability[6],
                "strategic_importance": capability[7],
                "business_owner": capability[8],
                "maturity_assessment_notes": capability[9],
                "maturity_assessment_date": capability[10].isoformat() if capability[10] else None,
            }
        )

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


# Framework-Specific Routes


@maturity_management.route("/capability-maturity/framework/<framework_key>")
@login_required
def framework_dashboard(framework_key):
    """Framework-specific dashboard"""

    try:
        # Get framework information
        framework_info = FrameworkClassifier.get_framework_summary(framework_key)

        if not framework_info:
            flash(f'Framework "{framework_key}" not found', "error")
            return redirect(url_for("maturity_management.frameworks_overview"))

        # Get framework categories
        framework_categories = FrameworkClassifier.get_framework_categories(framework_key)

        # Build WHERE clause for framework categories
        category_filter = " OR ".join([f"category = '{cat}'" for cat in framework_categories])

        # Get framework statistics
        _fw_params = {}

        # Get domain distribution within framework
        domain_stats = {}
        for domain_key, domain_data in framework_info["domains"].items():
            domain_categories = FrameworkClassifier.get_domain_categories(framework_key, domain_key)
            if domain_categories:
                domain_filter = " OR ".join([f"category = '{cat}'" for cat in domain_categories])

                _dom_params = {}
        # Get capabilities needing attention in this framework
        result = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT id, name, business_domain, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, maturity_assessment_date, category
            FROM business_capability
            WHERE ({category_filter}) AND
                  ((maturity_gap IS NOT NULL AND maturity_gap > 1) OR current_maturity_level IS NULL){_fw_org_filter}
            ORDER BY CASE WHEN maturity_gap IS NULL THEN 0 ELSE maturity_gap END DESC,
                     strategic_importance DESC
            LIMIT 20
        """
            ),
            _fw_params,
        )
        attention_needed = result.fetchall()

        return render_template(
            f"capability_maturity/frameworks/{framework_key}_dashboard.html",
            framework_info=framework_info,
            stats=stats,
            domain_stats=domain_stats,
            attention_needed=attention_needed,
        )

    except Exception as e:
        flash("Error loading framework dashboard. Please try again.", "error")
        return redirect(url_for("maturity_management.frameworks_overview"))


@maturity_management.route("/capability-maturity/framework/<framework_key>/<domain_key>")
@login_required
def domain_dashboard(framework_key, domain_key):
    """Domain-specific dashboard within a framework"""

    try:
        # Get framework and domain information
        framework_info = FrameworkClassifier.get_framework_summary(framework_key)

        if not framework_info or domain_key not in framework_info["domains"]:
            flash(f'Domain "{domain_key}" in framework "{framework_key}" not found', "error")
            return redirect(
                url_for("maturity_management.framework_dashboard", framework_key=framework_key)
            )

        domain_info = framework_info["domains"][domain_key]
        domain_categories = FrameworkClassifier.get_domain_categories(framework_key, domain_key)

        if not domain_categories:
            flash(f'No categories found for domain "{domain_key}"', "error")
            return redirect(
                url_for("maturity_management.framework_dashboard", framework_key=framework_key)
            )

        # Build WHERE clause for domain categories
        category_filter = " OR ".join([f"category = '{cat}'" for cat in domain_categories])

        # Get domain statistics
        _dd_params = {}

        # Get all capabilities in this domain
        result = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT id, name, business_domain, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, maturity_assessment_date,
                   category, business_owner, description
            FROM business_capability
            WHERE ({category_filter}){_dd_org_filter}
            ORDER BY strategic_importance DESC, name
        """
            ),
            _dd_params,
        )
        capabilities = result.fetchall()

        # Get capabilities needing attention
        result = db.session.execute(  # tenant-filtered
            text(
                f"""
            SELECT id, name, business_domain, current_maturity_level, target_maturity_level,
                   maturity_gap, strategic_importance, maturity_assessment_date, category
            FROM business_capability
            WHERE ({category_filter}) AND
                  ((maturity_gap IS NOT NULL AND maturity_gap > 1) OR current_maturity_level IS NULL){_dd_org_filter}
            ORDER BY CASE WHEN maturity_gap IS NULL THEN 0 ELSE maturity_gap END DESC,
                     strategic_importance DESC
        """
            ),
            _dd_params,
        )
        attention_needed = result.fetchall()

        return render_template(
            f"capability_maturity/frameworks/{framework_key}_{domain_key}_dashboard.html",
            framework_info=framework_info,
            domain_info=domain_info,
            stats=stats,
            capabilities=capabilities,
            attention_needed=attention_needed,
        )

    except Exception as e:
        flash("Error loading domain dashboard. Please try again.", "error")
        return redirect(
            url_for("maturity_management.framework_dashboard", framework_key=framework_key)
        )


@maturity_management.route("/capability-maturity/frameworks-overview")
@login_required
def frameworks_overview_redirect():
    """Redirect /capability-maturity/frameworks-overview to canonical URL."""
    return redirect(url_for("maturity_management.frameworks_overview"))


@maturity_management.route("/capability-maturity/frameworks")
@login_required
def frameworks_overview():
    """Overview of all frameworks"""

    try:
        # Get all frameworks
        all_frameworks = FrameworkClassifier.get_all_frameworks()

        # Get statistics for each framework
        framework_stats = {}

        for framework_key, framework_data in all_frameworks.items():
            framework_categories = FrameworkClassifier.get_framework_categories(framework_key)

            if framework_categories:
                # Use parameterized query to prevent SQL injection
                placeholders = ", ".join(
                    [f":cat_{i}" for i in range(len(framework_categories))]
                )
                params = {
                    f"cat_{i}": cat for i, cat in enumerate(framework_categories)
                }


        return render_template(
            "capability_maturity/frameworks_overview.html",
            all_frameworks=all_frameworks,
            framework_stats=framework_stats,
        )

    except Exception as e:
        flash("Error loading frameworks overview. Please try again.", "error")
        return redirect(url_for("capability_map.index"))


# ── Capability Maturity CSV Import ────────────────────────────────────────────

@maturity_management.route("/capability-maturity/import-csv", methods=["POST"])
@login_required
def import_maturity_csv():
    """Batch-update capability maturity levels from a CSV upload.

    CSV columns (header required):
        capability_name   — matched case-insensitively against business_capability.name
        current_maturity  — integer 1-5
        target_maturity   — integer 1-5 (optional)
        notes             — free text (optional)

    Returns JSON: {success, updated, skipped, errors:[{row, reason}]}
    """
    import csv, io
    from app.models.capability_models import BusinessCapability

    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "No file provided"}), 400

    if not f.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "error": "Only .csv files are accepted"}), 400

    if f.content_length and f.content_length > 2 * 1024 * 1024:
        return jsonify({"success": False, "error": "File exceeds 2 MB limit"}), 413

    try:
        content = f.read().decode("utf-8-sig", errors="replace")
    except Exception:
        return jsonify({"success": False, "error": "Could not read file"}), 400

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return jsonify({"success": False, "error": "CSV has no header row"}), 400

    # Normalise header names
    headers_lower = [h.strip().lower() for h in reader.fieldnames]
    if "capability_name" not in headers_lower:
        return jsonify({"success": False, "error": "CSV must have a 'capability_name' column"}), 400

    # Build name→capability lookup (case-insensitive)
    caps = BusinessCapability.query.all()
    cap_map = {c.name.strip().lower(): c for c in caps if c.name}

    updated = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        row_norm = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        name_key = row_norm.get("capability_name", "").lower()

        if not name_key:
            skipped += 1
            continue

        cap = cap_map.get(name_key)
        if not cap:
            errors.append({"row": row_num, "reason": f"Capability not found: {row_norm.get('capability_name', '')}"})
            skipped += 1
            continue

        current_raw = row_norm.get("current_maturity", "") or row_norm.get("current_level", "")
        target_raw = row_norm.get("target_maturity", "") or row_norm.get("target_level", "")
        notes = row_norm.get("notes", "") or row_norm.get("assessment_notes", "")

        changed = False

        if current_raw:
            try:
                lvl = int(current_raw)
                if not (1 <= lvl <= 5):
                    raise ValueError()
                cap.current_maturity_level = lvl
                changed = True
            except ValueError:
                errors.append({"row": row_num, "reason": f"Invalid current_maturity '{current_raw}' — must be 1-5"})
                skipped += 1
                continue

        if target_raw:
            try:
                lvl = int(target_raw)
                if not (1 <= lvl <= 5):
                    raise ValueError()
                cap.target_maturity_level = lvl
                changed = True
            except ValueError:
                errors.append({"row": row_num, "reason": f"Invalid target_maturity '{target_raw}' — must be 1-5"})
                skipped += 1
                continue

        if notes and hasattr(cap, "maturity_assessment_notes"):
            cap.maturity_assessment_notes = notes
            changed = True

        # Recalculate gap
        if cap.current_maturity_level and cap.target_maturity_level:
            cap.maturity_gap = cap.target_maturity_level - cap.current_maturity_level

        if changed:
            cap.updated_at = datetime.utcnow()
            updated += 1
        else:
            skipped += 1

        if row_num > 501:
            errors.append({"row": row_num, "reason": "Row limit (500) reached — remaining rows skipped"})
            break

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Database error: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "message": f"{updated} capabilities updated, {skipped} skipped" + (f", {len(errors)} errors" if errors else ""),
    })
