"""ARCH-030(i): bulk importers/connectors get merge-or-skip, not a 409.

Covers app/utils/duplicate_guard.bulk_partition_new_vs_duplicate directly
(the shared helper) and the batch-level in-batch dedup wired into
AIImportService.bulk_import_with_ai.
"""
from __future__ import annotations


def test_bulk_partition_skips_existing_and_within_batch_duplicates(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement
    from app.utils.duplicate_guard import bulk_partition_new_vs_duplicate

    org = make_org("bulk-partition")

    with tenant_ctx(org.id):
        existing = ArchiMateElement(name="Order Service", type="ApplicationComponent", organization_id=org.id)
        db_session.add(existing)
        db_session.flush()

        rows = [
            {"name": "Order Service"},       # collides with existing row (exact, normalized)
            {"name": "New Payments Engine"},  # genuinely new
            {"name": "new  payments engine"},  # duplicate of the previous row, within this batch
            {"name": "   "},                  # blank after normalisation
        ]

        result = bulk_partition_new_vs_duplicate(
            ArchiMateElement, rows, organization_id=org.id
        )

        new_names = [r["name"] for r in result["new"]]
        assert new_names == ["New Payments Engine"]

        reasons = [s["reason"] for s in result["skipped"]]
        assert "duplicate_of_existing_row" in reasons
        assert "duplicate_within_batch" in reasons
        assert "missing_name" in reasons
        assert len(result["skipped"]) == 3


def test_bulk_import_with_ai_skips_duplicate_names_within_batch(app, monkeypatch):
    """bulk_import_with_ai must skip (not create) a second row sharing a
    normalized name within the same batch, and count it."""
    from app.modules.ai_chat.services.ai_import_service import AIImportService

    calls = []

    def fake_import_with_ai_analysis(self, app_data, **kwargs):
        calls.append(app_data["name"])
        return {
            "success": True,
            "created": True,
            "updated": False,
            "mappings_created": {"capabilities": 0, "processes": 0, "archimate_elements": 0},
            "errors": [],
        }

    monkeypatch.setattr(AIImportService, "import_with_ai_analysis", fake_import_with_ai_analysis)

    service = AIImportService()
    results = service.bulk_import_with_ai(
        [
            {"name": "Fleet Tracker"},
            {"name": "fleet  tracker"},  # same normalized name -> must be skipped, not processed
            {"name": "Distinct App"},
        ],
        map_capabilities=False,
        map_processes=False,
        generate_archimate=False,
        match_vendor_products=False,
    )

    assert calls == ["Fleet Tracker", "Distinct App"]
    assert results["skipped_duplicate_in_batch"] == 1
    assert results["total"] == 3
