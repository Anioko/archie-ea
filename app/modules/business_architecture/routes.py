"""Compatibility redirect for the discontinued Business Architecture directory."""

from flask import Blueprint, redirect, url_for
from flask_login import login_required


business_architecture_bp = Blueprint(
    "business_architecture", __name__, url_prefix="/business-architecture"
)


@business_architecture_bp.route("/")
@login_required
def index():
    """Preserve bookmarked intent while moving work to Architecture Journey."""
    return redirect(
        url_for("architecture_journey.index", intent="business-transformation"),
        code=301,
    )
