"""
Procurement Routes (NS-010, NS-011)

Procurement persona dashboards for contract and license management.
All queries are scoped by current user's organization_id.

ADR Reference: docs/adr/0010-procurement-persona.md
"""

from datetime import date, timedelta

from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.decorators import requires_procurement
from app.extensions import db
from app.models.application_portfolio import VendorContract
from app.models.license_entitlement import LicenseEntitlement
from app.models.vendor.vendor_organization import VendorOrganization

from . import procurement_bp


@procurement_bp.route("/contracts")
@login_required
@requires_procurement
def contracts_list():
    """List all vendor contracts for current organization."""
    org_id = current_user.organization_id

    contracts = VendorContract.query.filter_by(organization_id=org_id).all()

    # Summary stats
    total_value = sum(c.contract_value or 0 for c in contracts)
    active_count = sum(1 for c in contracts if c.status == "active")
    expiring_soon = sum(
        1 for c in contracts
        if c.end_date and c.end_date <= date.today() + timedelta(days=90)
    )

    return render_template(
        "procurement/contracts_list.html",
        contracts=contracts,
        total_value=total_value,
        active_count=active_count,
        expiring_soon=expiring_soon,
    )


@procurement_bp.route("/contracts/<int:contract_id>")
@login_required
@requires_procurement
def contract_detail(contract_id):
    """View contract details (scoped to org)."""
    org_id = current_user.organization_id

    contract = VendorContract.query.filter_by(
        id=contract_id,
        organization_id=org_id
    ).first_or_404()

    # Get licenses under this contract
    licenses = LicenseEntitlement.query.filter_by(
        contract_id=contract_id,
        organization_id=org_id
    ).all()

    return render_template(
        "procurement/contract_detail.html",
        contract=contract,
        licenses=licenses,
    )


@procurement_bp.route("/renewals")
@login_required
@requires_procurement
def renewals_dashboard():
    """Dashboard showing upcoming contract renewals."""
    org_id = current_user.organization_id
    today = date.today()

    # Contracts expiring in different windows
    contracts = VendorContract.query.filter_by(organization_id=org_id).all()

    expiring_30 = [c for c in contracts if c.end_date and today <= c.end_date <= today + timedelta(days=30)]
    expiring_60 = [c for c in contracts if c.end_date and today + timedelta(days=30) < c.end_date <= today + timedelta(days=60)]
    expiring_90 = [c for c in contracts if c.end_date and today + timedelta(days=60) < c.end_date <= today + timedelta(days=90)]
    expired = [c for c in contracts if c.end_date and c.end_date < today]

    return render_template(
        "procurement/renewals_dashboard.html",
        expiring_30=expiring_30,
        expiring_60=expiring_60,
        expiring_90=expiring_90,
        expired=expired,
        today=today,
    )


@procurement_bp.route("/licenses")
@login_required
@requires_procurement
def licenses_list():
    """List all license entitlements for current organization."""
    org_id = current_user.organization_id

    licenses = LicenseEntitlement.query.filter_by(organization_id=org_id).all()

    # Summary stats
    total_entitled = sum(l.quantity_entitled or 0 for l in licenses)
    total_deployed = sum(l.quantity_deployed or 0 for l in licenses)
    total_used = sum(l.quantity_used or 0 for l in licenses)

    # Compliance breakdown
    compliant = sum(1 for l in licenses if l.compliance_status == "compliant")
    over_deployed = sum(1 for l in licenses if l.compliance_status == "over_deployed")
    under_utilized = sum(1 for l in licenses if l.compliance_status == "under_utilized")

    return render_template(
        "procurement/licenses_list.html",
        licenses=licenses,
        total_entitled=total_entitled,
        total_deployed=total_deployed,
        total_used=total_used,
        compliant=compliant,
        over_deployed=over_deployed,
        under_utilized=under_utilized,
    )


@procurement_bp.route("/licenses/<int:license_id>")
@login_required
@requires_procurement
def license_detail(license_id):
    """View license details (scoped to org)."""
    org_id = current_user.organization_id

    license = LicenseEntitlement.query.filter_by(
        id=license_id,
        organization_id=org_id
    ).first_or_404()

    return render_template(
        "procurement/license_detail.html",
        license=license,
    )


@procurement_bp.route("/compliance")
@login_required
@requires_procurement
def compliance_dashboard():
    """License compliance dashboard."""
    org_id = current_user.organization_id

    licenses = LicenseEntitlement.query.filter_by(organization_id=org_id).all()

    # Group by compliance status
    by_status = {}
    for l in licenses:
        status = l.compliance_status or "unknown"
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(l)

    # Calculate risk exposure (over-deployed licenses)
    risk_exposure = sum(
        (l.quantity_deployed - l.quantity_entitled) * float(l.unit_cost or 0)
        for l in licenses
        if l.compliance_status == "over_deployed" and l.quantity_deployed and l.quantity_entitled
    )

    # Shelfware (entitled but not used)
    shelfware_value = sum(
        (l.quantity_entitled - l.quantity_used) * float(l.unit_cost or 0)
        for l in licenses
        if l.quantity_entitled and l.quantity_used and l.quantity_entitled > l.quantity_used
    )

    return render_template(
        "procurement/compliance_dashboard.html",
        licenses=licenses,
        by_status=by_status,
        risk_exposure=risk_exposure,
        shelfware_value=shelfware_value,
    )


@procurement_bp.route("/spend")
@login_required
@requires_procurement
def spend_analytics():
    """Spend analytics dashboard."""
    org_id = current_user.organization_id

    contracts = VendorContract.query.filter_by(organization_id=org_id).all()

    # Total spend
    total_spend = sum(c.contract_value or 0 for c in contracts)
    annual_spend = sum(c.annual_cost or 0 for c in contracts)

    # Spend by vendor
    spend_by_vendor = {}
    for c in contracts:
        vendor_name = c.vendor.name if c.vendor else "Unknown"
        if vendor_name not in spend_by_vendor:
            spend_by_vendor[vendor_name] = 0
        spend_by_vendor[vendor_name] += c.contract_value or 0

    # Sort by spend
    spend_by_vendor = dict(sorted(spend_by_vendor.items(), key=lambda x: -x[1]))

    # Spend by category
    spend_by_category = {}
    for c in contracts:
        cat = c.contract_category or "Uncategorized"
        if cat not in spend_by_category:
            spend_by_category[cat] = 0
        spend_by_category[cat] += c.contract_value or 0

    return render_template(
        "procurement/spend_analytics.html",
        contracts=contracts,
        total_spend=total_spend,
        annual_spend=annual_spend,
        spend_by_vendor=spend_by_vendor,
        spend_by_category=spend_by_category,
    )
