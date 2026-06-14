from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.services.org_service import OrgService
from app import db

signup_bp = Blueprint("signup", __name__)

@signup_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        org_name = request.form.get("org_name")
        admin_name = request.form.get("admin_name")
        admin_email = request.form.get("admin_email")
        admin_password = request.form.get("admin_password")
        first_name, *last_name = admin_name.split(" ", 1)
        last_name = last_name[0] if last_name else None
        try:
            org, user = OrgService.create_org(
                name=org_name,
                admin_email=admin_email,
                plan="starter",
                admin_password=admin_password,
                admin_first_name=first_name,
                admin_last_name=last_name
            )
            flash("Organization and admin user created!", "success")
            return redirect("/billing/setup")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template("auth/register.html")

@signup_bp.route("/api/orgs/<int:org_id>/invite", methods=["POST"])
def invite_member(org_id):
    data = request.get_json() or request.form
    email = data.get("email")
    inviter_id = data.get("inviter_id")
    try:
        user = OrgService.invite_member(org_id, email, inviter_id)
        return jsonify({"status": "ok", "user_id": user.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "error": str(e)}), 400
