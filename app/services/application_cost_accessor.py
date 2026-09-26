"""
Application Cost Accessor — the single accessor for "annual cost of an application".

Release 1 decision (R1-B08 PR 1): the system of record for annual cost is
ApplicationComponent.total_cost_of_ownership (labelled "Annual TCO" in the model).
This module provides the one read/write path that all Release 1 screens and
imports must use. The full Cost Fact consolidation (MIG-D-0090, Release 2) will
replace this with a cost-fact table; until then this accessor isolates the
choice so callers do not scatter direct column references.

No cost-fact table is created in Release 1.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app import db
from app.models.application_portfolio import ApplicationComponent


# The canonical annual-cost column on ApplicationComponent.
# Model comment: "Annual TCO".
_ANNUAL_COST_COLUMN = "total_cost_of_ownership"

# Recognised cost categories for typed import mapping.
COST_CATEGORIES = frozenset({
    "total_cost_of_ownership",
    "license_cost_annual",
    "maintenance_cost",
    "infrastructure_cost",
    "support_cost",
    "implementation_cost",
    "development_cost_annual",
})

# Recognised period values for normalisation.
PERIOD_VALUES = frozenset({"annual", "monthly"})


def get_annual_cost(app: ApplicationComponent) -> Optional[Decimal]:
    """
    Return the application's annual cost as Decimal, or None if not recorded.

    This is the single read accessor for Release 1. All screens, reports and
    exports that need "the annual cost of this application" must call this.
    """
    value = getattr(app, _ANNUAL_COST_COLUMN, None)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def get_annual_cost_float(app: ApplicationComponent) -> Optional[float]:
    """Convenience wrapper returning float for templates that expect it."""
    d = get_annual_cost(app)
    return float(d) if d is not None else None


def set_annual_cost(app: ApplicationComponent, value: Optional[Decimal]) -> None:
    """
    Write the application's annual cost through the accessor.

    Accepts Decimal, int, float, or numeric string. None clears the field.
    """
    if value is None:
        setattr(app, _ANNUAL_COST_COLUMN, None)
        return
    try:
        setattr(app, _ANNUAL_COST_COLUMN, Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        # Invalid input is treated as "not recorded" — never stored as 0.
        setattr(app, _ANNUAL_COST_COLUMN, None)


def parse_cost_cell(
    raw_value: Any,
    currency: str = "USD",
    period: str = "annual",
    category: str = "total_cost_of_ownership",
) -> Dict[str, Any]:
    """
    Parse a single cost cell from an import spreadsheet.

    Returns a dict with keys:
        - "value": Decimal or None (None means unparseable → import as empty)
        - "currency": normalised currency code (e.g. "USD")
        - "period": normalised period ("annual" or "monthly")
        - "category": normalised category (one of COST_CATEGORIES)
        - "warnings": list of warning strings (empty if clean)
        - "error": error string if unparseable, else None

    An unparseable cell is reported via "error" and "value" = None.
    It is NEVER stored as 0.
    """
    warnings: List[str] = []
    error: Optional[str] = None
    value: Optional[Decimal] = None

    # Normalise currency
    currency = (currency or "USD").strip().upper()
    if len(currency) != 3:
        warnings.append(f"Currency '{currency}' does not look like a 3-letter code; using USD")
        currency = "USD"

    # Normalise period
    period = (period or "annual").strip().lower()
    if period not in PERIOD_VALUES:
        warnings.append(f"Unknown period '{period}'; defaulting to annual")
        period = "annual"

    # Normalise category
    category = (category or "total_cost_of_ownership").strip().lower()
    if category not in COST_CATEGORIES:
        warnings.append(f"Unknown cost category '{category}'; defaulting to total_cost_of_ownership")
        category = "total_cost_of_ownership"

    # Parse the numeric value
    if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
        error = "Empty cost cell"
    else:
        try:
            # Strip common currency symbols and thousands separators
            cleaned = str(raw_value).strip()
            for ch in ["$", "€", "£", "¥", ",", " "]:
                cleaned = cleaned.replace(ch, "")
            # Handle parentheses as negative (accounting format)
            if cleaned.startswith("(") and cleaned.endswith(")"):
                cleaned = "-" + cleaned[1:-1]
            value = Decimal(cleaned)
            if value < 0:
                warnings.append("Negative cost value parsed; stored as-is")
        except (InvalidOperation, ValueError, TypeError):
            error = f"Could not parse cost value: {raw_value!r}"
            value = None

    # Normalise monthly to annual for storage
    annual_value: Optional[Decimal] = None
    if value is not None and period == "monthly":
        annual_value = value * 12
    else:
        annual_value = value

    return {
        "value": annual_value,
        "currency": currency,
        "period": period,
        "category": category,
        "warnings": warnings,
        "error": error,
    }


def map_import_cost_columns(
    row: Dict[str, Any],
    column_mapping: Dict[str, str],
) -> Dict[str, Any]:
    """
    Extract and parse cost columns from an import row using a column mapping.

    Args:
        row: The raw row dict from the parsed file.
        column_mapping: Dict mapping logical cost fields to column names in the file.
            Supported keys: "total_cost_of_ownership", "license_cost_annual",
            "maintenance_cost", "infrastructure_cost", "support_cost",
            "implementation_cost", "development_cost_annual",
            plus optional "currency", "period", "category" for per-row overrides.

    Returns:
        Dict with parsed cost fields ready for the accessor, plus a "cost_warnings"
        list and a "cost_errors" dict mapping field names to error strings.
    """
    result: Dict[str, Any] = {}
    cost_warnings: List[str] = []
    cost_errors: Dict[str, str] = {}

    # Global overrides (apply to all cost fields in this row if present)
    global_currency = row.get(column_mapping.get("currency", ""), "USD") if column_mapping.get("currency") else "USD"
    global_period = row.get(column_mapping.get("period", ""), "annual") if column_mapping.get("period") else "annual"
    global_category = row.get(column_mapping.get("category", ""), "total_cost_of_ownership") if column_mapping.get("category") else "total_cost_of_ownership"

    for field_name in COST_CATEGORIES:
        col_name = column_mapping.get(field_name)
        if not col_name or col_name not in row:
            continue

        raw_value = row[col_name]
        currency = row.get(column_mapping.get("currency", ""), global_currency) if column_mapping.get("currency") else global_currency
        period = row.get(column_mapping.get("period", ""), global_period) if column_mapping.get("period") else global_period
        category = row.get(column_mapping.get("category", ""), global_category) if column_mapping.get("category") else global_category

        parsed = parse_cost_cell(raw_value, currency, period, category)

        if parsed["error"]:
            cost_errors[field_name] = parsed["error"]
            # Value stays None → will be imported as empty
        else:
            result[field_name] = parsed["value"]

        cost_warnings.extend(parsed["warnings"])

    return {
        "cost_fields": result,
        "cost_warnings": cost_warnings,
        "cost_errors": cost_errors,
    }


def apply_cost_to_application(
    app: ApplicationComponent,
    cost_fields: Dict[str, Optional[Decimal]],
) -> None:
    """
    Apply parsed cost fields to an ApplicationComponent via the accessor.

    Only the canonical annual cost column (total_cost_of_ownership) is written
    in Release 1. Other categories are accepted in the preview for future
    compatibility but not persisted yet.
    """
    # Release 1: only total_cost_of_ownership is the system of record
    tco = cost_fields.get("total_cost_of_ownership")
    set_annual_cost(app, tco)


def get_cost_summary_for_org(org_id: int) -> Dict[str, Any]:
    """
    Aggregate cost summary for an organisation (used by portfolio totals).

    Returns dict with total_annual_cost, application_count, applications_with_cost.
    """
    # Use raw SQL to bypass ORM tenant filter since we explicitly filter by org_id
    from app import db
    from sqlalchemy import text

    result = db.session.execute(
        text("""
            SELECT 
                COUNT(*) as application_count,
                COUNT(total_cost_of_ownership) as applications_with_cost,
                COALESCE(SUM(total_cost_of_ownership), 0) as total_annual_cost
            FROM application_components
            WHERE organization_id = :org_id
        """),
        {"org_id": org_id}
    ).fetchone()

    return {
        "total_annual_cost": Decimal(str(result.total_annual_cost)) if result.total_annual_cost else Decimal("0"),
        "application_count": result.application_count or 0,
        "applications_with_cost": result.applications_with_cost or 0,
    }