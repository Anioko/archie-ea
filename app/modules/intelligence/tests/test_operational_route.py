"""``IntelligenceQueryService.operational_for_element`` and
``GET /api/v1/intelligence/operational/<element_id>`` (the Operational
lens): "what has changed around this element since we last checked, and is
anything out of date?"

Twelve groups, matching the task brief's own numbering. Grouped by what each
needs, so the file grows in step with the three commits that add it:

  (7)                     the adapter contract alone -- no service, no route
  (2)-(6), (8)-(10)       the service method, called directly (no route yet)
  (1), (11), (12)         the route

Fixtures (``app``, ``db_session``, ``make_org``, ``client``, ``login_as``,
``tenant_ctx``) come from this module's own ``conftest.py``, which re-imports
them from ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_monitoring_state():
    """Clear ``ArchitectureMonitoringService``'s module-level per-tenant
    cache before and after every test -- it lives for the life of the
    process, not the life of a request."""
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    ArchitectureMonitoringService.reset_state()
    yield
    ArchitectureMonitoringService.reset_state()


# --- (7) the adapter contract, alone -----------------------------------------


def test_group7_no_adapter_registered_means_feed_not_connected():
    import re

    from app.modules.intelligence.services.operational_sources import (
        ChangeRecord,
        ExternalRef,
        IncidentRecord,
        OperationalSourceAdapter,
        TelemetrySample,
        registered_adapter,
    )

    assert registered_adapter(1) is None
    assert OperationalSourceAdapter is not None
    assert ExternalRef and IncidentRecord and ChangeRecord and TelemetrySample

    # No class implementing the adapter contract exists anywhere in this
    # module -- only the Protocol itself.
    source_path = "app/modules/intelligence/services/operational_sources.py"
    with open(source_path, encoding="utf-8") as fh:
        source_text = fh.read()
    class_defs = re.findall(
        r"^class\s+([A-Za-z0-9_]*Adapter[A-Za-z0-9_]*)\b", source_text, re.MULTILINE
    )
    assert class_defs == ["OperationalSourceAdapter"]
