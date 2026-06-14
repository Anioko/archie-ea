"""Gantt Chart Demo Route."""  # mass-deletion-ok
from flask import render_template

from app.main.views import main
from flask_login import login_required


@main.route("/gantt-demo")
@login_required
def gantt_demo():
    """Render the interactive Gantt chart demo page."""
    return render_template("tools/gantt_demo.html")
