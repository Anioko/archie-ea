"""Portfolio module — the delivery view of the architecture.

EnterpriseInitiative carried approved_budget, spent_to_date, forecast_cost, RAG
health, sponsor and phase, and had zero templates: the richest delivery object in
the repository was unreachable. This module surfaces it, and with it the Benefit,
Demand and Assumption records that hang off an initiative.
"""
import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    from app.modules.portfolio.routes.portfolio_routes import portfolio_bp

    # Importing for the side effect of registering its @portfolio_bp.route
    # decorators; the write paths live in their own module to keep each file
    # readable, but they belong to this blueprint.
    from app.modules.portfolio.routes import portfolio_write_routes  # noqa: F401

    app.register_blueprint(portfolio_bp)
    app.logger.info("[MODULE] portfolio registered")
