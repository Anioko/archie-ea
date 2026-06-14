import logging

import yaml
from flask import jsonify, render_template, request
from flask_login import login_required

from app.main import main
from app.services.agent.agentic_generator import AgenticGenerator

logger = logging.getLogger(__name__)


@main.route("/agentic-generator")
@login_required
def agentic_generator_ui():
    """UI for the Agentic Generator."""
    return render_template("main/agentic_generator.html")


@main.route("/agentic-generate", methods=["POST"])
@login_required
def agentic_generate_api():
    """API endpoint for the Agentic Generator."""
    try:
        data = request.get_json()
        requirement = data.get("requirement")
        generator_type = data.get("type")

        if not requirement:
            return jsonify({"success": False, "error": "Requirement is required"}), 400

        # Run generation
        config_path = AgenticGenerator.generate(requirement, generator_type)

        # Parse the generated config to get the route
        route = None
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                route = config.get("route")
        except Exception as e:
            logger.warning(f"Could not parse generated config to find route: {e}")

        return jsonify({"success": True, "config_path": config_path, "route": route})

    except Exception as e:
        logger.error(f"Agentic generation failed: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
