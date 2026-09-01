"""Regression: the composer's "Enterprise Context" preview must report the same
entity counts the AI actually reasons over.

Defect (QA 01 Sep 2026): the generation modal reported a handful of apps/elements
while the tenant held many more. Root cause was that ``get_context_preview`` ran a
separate, tighter semantic search (limit=5) than ``assemble_context`` (limit=15/30),
so the preview under-reported what generation used. The fix routes the preview
through ``assemble_context`` so the two can never disagree.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.enterprise_context_assembler import (
    EnterpriseContext,
    EnterpriseContextAssembler,
)

pytestmark = pytest.mark.usefixtures("db_session")


def test_preview_counts_match_assembled_context():
    """Preview counts must equal the sizes of the assembled context lists."""
    assembler = EnterpriseContextAssembler()

    fake_ctx = EnterpriseContext(
        description="customer management platform",
        phase="C",
        applications=[{"id": 1}, {"id": 2}, {"id": 3}],
        archimate_elements=[{"id": 10}, {"id": 11}],
        vendors=[{"id": 20}],
        capabilities=[{"id": 30}, {"id": 31}, {"id": 32}, {"id": 33}],
    )

    with patch.object(assembler, "assemble_context", return_value=fake_ctx) as mock:
        preview = assembler.get_context_preview(
            description="customer management platform", phase="C"
        )

    # Preview must have run the same assembly path generation uses.
    assert mock.called
    assert preview["counts"] == {
        "application": 3,
        "archimate_element": 2,
        "vendor": 1,
        "capability": 4,
    }


def test_preview_degrades_to_zero_counts_on_assembly_error():
    """A failed assembly must yield honest zeros, never a fabricated number."""
    assembler = EnterpriseContextAssembler()

    with patch.object(
        assembler, "assemble_context", side_effect=RuntimeError("boom")
    ):
        preview = assembler.get_context_preview(description="anything", phase="C")

    assert preview["counts"] == {
        "application": 0,
        "archimate_element": 0,
        "vendor": 0,
        "capability": 0,
    }
