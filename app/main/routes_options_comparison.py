# Registered via app/main/__init__.py — provides @main.route("/roadmap-options")
"""Capability Roadmap Options Comparison Routes"""

from flask import render_template
from flask_login import login_required

from app.main.views import main


@main.route("/roadmap-options")
@login_required
def roadmap_options():
    """Display all 3 capability roadmap options for comparison"""
    return render_template("capability_roadmap/options_comparison.html")
