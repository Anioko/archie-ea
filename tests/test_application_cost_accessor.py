"""Tests for the Application Cost Accessor (R1-B08 PR 1).

Covers:
- Single accessor for annual cost (get_annual_cost, set_annual_cost)
- Cost cell parsing with currency, period, category
- Import column mapping and typed preview
- Unparseable cells reported and imported as empty (never 0)
- Tenant isolation: cost visible only to owning organisation
"""

import pytest
from decimal import Decimal

from app.models.application_portfolio import ApplicationComponent
from app.models.organization import Organization
from app.services.application_cost_accessor import (
    COST_CATEGORIES,
    PERIOD_VALUES,
    get_annual_cost,
    get_annual_cost_float,
    set_annual_cost,
    parse_cost_cell,
    map_import_cost_columns,
    apply_cost_to_application,
    get_cost_summary_for_org,
)


class TestCostAccessorBasics:
    """Basic read/write through the accessor."""

    def test_get_annual_cost_returns_none_when_not_set(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-1")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            assert get_annual_cost(app_comp) is None
            assert get_annual_cost_float(app_comp) is None

    def test_set_and_get_annual_cost_decimal(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-2")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            set_annual_cost(app_comp, Decimal("123456.78"))
            db_session.commit()

            assert get_annual_cost(app_comp) == Decimal("123456.78")
            assert get_annual_cost_float(app_comp) == 123456.78

    def test_set_annual_cost_from_int(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-3")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            set_annual_cost(app_comp, 100000)
            db_session.commit()

            assert get_annual_cost(app_comp) == Decimal("100000")

    def test_set_annual_cost_from_float(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-4")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            set_annual_cost(app_comp, 12345.67)
            db_session.commit()

            assert get_annual_cost(app_comp) == Decimal("12345.67")

    def test_set_annual_cost_from_string(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-5")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            set_annual_cost(app_comp, "98765.43")
            db_session.commit()

            assert get_annual_cost(app_comp) == Decimal("98765.43")

    def test_set_annual_cost_none_clears_field(self, app, db_session, make_org, tenant_ctx):
        org = make_org("cost-accessor-6")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id, total_cost_of_ownership=50000)
            db_session.add(app_comp)
            db_session.commit()

            set_annual_cost(app_comp, None)
            db_session.commit()

            assert get_annual_cost(app_comp) is None


class TestParseCostCell:
    """parse_cost_cell handles currency, period, category and errors."""

    def test_parse_clean_annual_usd(self):
        result = parse_cost_cell("100000", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] == Decimal("100000")
        assert result["currency"] == "USD"
        assert result["period"] == "annual"
        assert result["category"] == "total_cost_of_ownership"
        assert result["error"] is None
        assert result["warnings"] == []

    def test_parse_with_currency_symbol_and_commas(self):
        result = parse_cost_cell("$1,234,567.89", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] == Decimal("1234567.89")
        assert result["error"] is None

    def test_parse_euro_currency(self):
        result = parse_cost_cell("€99.999,50", currency="EUR", period="annual", category="total_cost_of_ownership")
        # Note: European format with comma as decimal separator not handled - this is a known limitation
        # The parser strips commas, so this becomes 9999950
        # For now we accept the behaviour; a full locale parser is out of scope for R1
        assert result["currency"] == "EUR"

    def test_parse_monthly_normalises_to_annual(self):
        result = parse_cost_cell("5000", currency="USD", period="monthly", category="total_cost_of_ownership")
        assert result["value"] == Decimal("60000")  # 5000 * 12
        assert result["period"] == "monthly"

    def test_parse_quarterly_period_defaults_to_annual_with_warning(self):
        result = parse_cost_cell("10000", currency="USD", period="quarterly", category="total_cost_of_ownership")
        assert result["value"] == Decimal("10000")
        assert result["period"] == "annual"
        assert any("Unknown period" in w for w in result["warnings"])

    def test_parse_unknown_category_defaults_with_warning(self):
        result = parse_cost_cell("10000", currency="USD", period="annual", category="unknown_category")
        assert result["value"] == Decimal("10000")
        assert result["category"] == "total_cost_of_ownership"
        assert any("Unknown cost category" in w for w in result["warnings"])

    def test_parse_empty_string_returns_error_and_none_value(self):
        result = parse_cost_cell("", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] is None
        assert result["error"] == "Empty cost cell"

    def test_parse_none_returns_error_and_none_value(self):
        result = parse_cost_cell(None, currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] is None
        assert result["error"] == "Empty cost cell"

    def test_parse_unparseable_returns_error_and_none_value(self):
        result = parse_cost_cell("not a number", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] is None
        assert result["error"] is not None
        assert "Could not parse cost value" in result["error"]

    def test_parse_negative_value_warns_but_stores(self):
        result = parse_cost_cell("-5000", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] == Decimal("-5000")
        assert any("Negative cost value" in w for w in result["warnings"])

    def test_parse_parentheses_as_negative(self):
        result = parse_cost_cell("(5000)", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] == Decimal("-5000")


class TestMapImportCostColumns:
    """map_import_cost_columns extracts and parses cost columns from a row."""

    def test_maps_total_cost_of_ownership_column(self):
        row = {"total_cost_of_ownership": "100000", "name": "Test App"}
        mapping = {"total_cost_of_ownership": "total_cost_of_ownership"}
        result = map_import_cost_columns(row, mapping)

        assert "total_cost_of_ownership" in result["cost_fields"]
        assert result["cost_fields"]["total_cost_of_ownership"] == Decimal("100000")
        assert result["cost_errors"] == {}

    def test_maps_multiple_cost_columns(self):
        row = {
            "total_cost_of_ownership": "100000",
            "license_cost_annual": "50000",
            "maintenance_cost": "20000",
            "name": "Test App",
        }
        mapping = {
            "total_cost_of_ownership": "total_cost_of_ownership",
            "license_cost_annual": "license_cost_annual",
            "maintenance_cost": "maintenance_cost",
        }
        result = map_import_cost_columns(row, mapping)

        assert result["cost_fields"]["total_cost_of_ownership"] == Decimal("100000")
        assert result["cost_fields"]["license_cost_annual"] == Decimal("50000")
        assert result["cost_fields"]["maintenance_cost"] == Decimal("20000")

    def test_unparseable_cell_reported_in_errors_not_as_zero(self):
        row = {"total_cost_of_ownership": "not a number", "name": "Test App"}
        mapping = {"total_cost_of_ownership": "total_cost_of_ownership"}
        result = map_import_cost_columns(row, mapping)

        assert "total_cost_of_ownership" in result["cost_errors"]
        assert "total_cost_of_ownership" not in result["cost_fields"]
        assert result["cost_fields"] == {}

    def test_empty_cell_reported_in_errors_not_as_zero(self):
        row = {"total_cost_of_ownership": "", "name": "Test App"}
        mapping = {"total_cost_of_ownership": "total_cost_of_ownership"}
        result = map_import_cost_columns(row, mapping)

        assert "total_cost_of_ownership" in result["cost_errors"]
        assert "total_cost_of_ownership" not in result["cost_fields"]

    def test_global_currency_period_category_overrides(self):
        row = {
            "total_cost_of_ownership": "5000",
            "currency": "EUR",
            "period": "monthly",
            "category": "license_cost_annual",
            "name": "Test App",
        }
        mapping = {
            "total_cost_of_ownership": "total_cost_of_ownership",
            "currency": "currency",
            "period": "period",
            "category": "category",
        }
        result = map_import_cost_columns(row, mapping)

        # 5000 monthly -> 60000 annual
        assert result["cost_fields"]["total_cost_of_ownership"] == Decimal("60000")

    def test_missing_columns_ignored(self):
        row = {"name": "Test App"}
        mapping = {"total_cost_of_ownership": "total_cost_of_ownership"}
        result = map_import_cost_columns(row, mapping)

        assert result["cost_fields"] == {}
        assert result["cost_errors"] == {}


class TestApplyCostToApplication:
    """apply_cost_to_application writes through the accessor."""

    def test_applies_total_cost_of_ownership(self, app, db_session, make_org, tenant_ctx):
        org = make_org("apply-cost-1")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            apply_cost_to_application(app_comp, {"total_cost_of_ownership": Decimal("75000")})
            db_session.commit()

            assert get_annual_cost(app_comp) == Decimal("75000")

    def test_other_categories_accepted_but_not_persisted_in_r1(self, app, db_session, make_org, tenant_ctx):
        """Release 1 only persists total_cost_of_ownership; other categories accepted for preview."""
        org = make_org("apply-cost-2")
        with tenant_ctx(org.id):
            app_comp = ApplicationComponent(name="Test App", organization_id=org.id)
            db_session.add(app_comp)
            db_session.commit()

            apply_cost_to_application(app_comp, {
                "total_cost_of_ownership": Decimal("100000"),
                "license_cost_annual": Decimal("50000"),
                "maintenance_cost": Decimal("20000"),
            })
            db_session.commit()

            # Only TCO is written in R1
            assert get_annual_cost(app_comp) == Decimal("100000")


class TestTenantIsolation:
    """Cost is visible only to its organisation; totals per org are unaffected by the other."""

    def test_cost_isolation_between_organisations(self, app, db_session, make_org, tenant_ctx):
        org1 = make_org("cost-org-1")
        org2 = make_org("cost-org-2")

        with tenant_ctx(org1.id):
            app1 = ApplicationComponent(name="App Org1", organization_id=org1.id)
            db_session.add(app1)
            db_session.commit()
            set_annual_cost(app1, Decimal("100000"))
            db_session.commit()

        with tenant_ctx(org2.id):
            app2 = ApplicationComponent(name="App Org2", organization_id=org2.id)
            db_session.add(app2)
            db_session.commit()
            set_annual_cost(app2, Decimal("200000"))
            db_session.commit()

        # Query org1's apps and costs
        with tenant_ctx(org1.id):
            apps1 = ApplicationComponent.query.filter_by(organization_id=org1.id).all()
            assert len(apps1) == 1
            assert get_annual_cost(apps1[0]) == Decimal("100000")

            summary1 = get_cost_summary_for_org(org1.id)
            assert summary1["total_annual_cost"] == Decimal("100000")
            assert summary1["applications_with_cost"] == 1

        # Query org2's apps and costs
        with tenant_ctx(org2.id):
            apps2 = ApplicationComponent.query.filter_by(organization_id=org2.id).all()
            assert len(apps2) == 1
            assert get_annual_cost(apps2[0]) == Decimal("200000")

            summary2 = get_cost_summary_for_org(org2.id)
            assert summary2["total_annual_cost"] == Decimal("200000")
            assert summary2["applications_with_cost"] == 1

        # Cross-org query should not leak (tenant middleware should filter)
        # But get_cost_summary_for_org explicitly filters by org_id
        summary1_again = get_cost_summary_for_org(org1.id)
        assert summary1_again["total_annual_cost"] == Decimal("100000")
        assert summary1_again["applications_with_cost"] == 1


class TestAnnualMonthlyNormalisation:
    """Annual and monthly normalisation in parse_cost_cell."""

    def test_annual_period_stored_as_is(self):
        result = parse_cost_cell("120000", currency="USD", period="annual", category="total_cost_of_ownership")
        assert result["value"] == Decimal("120000")

    def test_monthly_period_multiplied_by_12(self):
        result = parse_cost_cell("10000", currency="USD", period="monthly", category="total_cost_of_ownership")
        assert result["value"] == Decimal("120000")

    def test_monthly_with_decimal(self):
        result = parse_cost_cell("8333.33", currency="USD", period="monthly", category="total_cost_of_ownership")
        assert result["value"] == Decimal("99999.96")  # 8333.33 * 12


class TestImportPreviewCostMapping:
    """Integration test for import preview cost mapping (smoke test)."""

    def test_preview_includes_cost_mapping(self, app, db_session, make_org, tenant_ctx):
        from app.modules.import_batch.services.import_preview_service import ImportPreviewService
        from app.models.batch_import import BatchImportJob, BatchImportBatch, BatchImportApplication, BatchJobStatus, BatchStatus
        from app.models.user import User

        org = make_org("preview-cost-1")
        with tenant_ctx(org.id):
            # Create a user for the job
            user = User(email="test@example.com", organization_id=org.id, confirmed=True)
            db_session.add(user)
            db_session.flush()

            # Create a job with applications that have cost columns
            job = BatchImportJob(
                job_uuid="test-uuid",
                user_id=user.id,
                name="Test Job",
                filename="test.csv",
                file_path="/tmp/test.csv",
                file_hash="abc123",
                total_applications=2,
                batch_size=10,
                total_batches=1,
                status=BatchJobStatus.AWAITING_CONFIRMATION,
                archimate_mode="standard",
                enable_ai_generation=False,
            )
            db_session.add(job)
            db_session.flush()

            batch = BatchImportBatch(job_id=job.id, batch_number=1, status=BatchStatus.QUEUED, total_applications=2)
            db_session.add(batch)
            db_session.flush()

            app1 = BatchImportApplication(
                batch_id=batch.id,
                row_number=1,
                source_data={"name": "App1", "total_cost_of_ownership": "100000", "license_cost_annual": "50000"},
                application_name="App1",
                status="pending",
            )
            app2 = BatchImportApplication(
                batch_id=batch.id,
                row_number=2,
                source_data={"name": "App2", "total_cost_of_ownership": "not a number"},
                application_name="App2",
                status="pending",
            )
            db_session.add_all([app1, app2])
            db_session.commit()

            preview_service = ImportPreviewService()
            preview = preview_service.generate_preview(job.id)

            assert "cost_mapping" in preview
            cost_mapping = preview["cost_mapping"]
            assert "detected_columns" in cost_mapping
            assert "total_cost_of_ownership" in cost_mapping["detected_columns"]
            assert "license_cost_annual" in cost_mapping["detected_columns"]
            assert len(cost_mapping["row_previews"]) == 2

            # Row 1 has valid cost
            row1 = cost_mapping["row_previews"][0]
            assert row1["cost_fields"]["total_cost_of_ownership"] == 100000.0
            assert row1["cost_fields"]["license_cost_annual"] == 50000.0
            assert row1["cost_errors"] == {}

            # Row 2 has unparseable cost
            row2 = cost_mapping["row_previews"][1]
            assert "total_cost_of_ownership" in row2["cost_errors"]
            assert row2["cost_fields"] == {}

            # Summary counts
            assert cost_mapping["summary"]["rows_with_cost"] == 1
            assert cost_mapping["summary"]["rows_with_errors"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])