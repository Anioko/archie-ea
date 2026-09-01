"""Coverage for the deterministic codegen core: `genome_to_bundle`.

This is the emitter every slice reuses (ADR 0010 / 03_integration.md §2). It had
zero tests despite being the reproducibility contract the whole re-architecture
rests on. These lock three invariants:

  1. It runs with **no LLM** — a pure genome → bundle transform, no provider call.
  2. It is **deterministic** — same genome in → byte-identical bundle out.
  3. It **stamps provenance** — `archimate_source_id` flows onto emitted units and
     the bundle's provenance map, in code, never asked of the LLM.

Pure-function tests: no DB, no request context, no fixtures needed.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from app.modules.codegen.services.genome_to_bundle import genome_to_bundle

ARCH_ID = "arch-elem-123"


def _sample_genome() -> dict:
    """A minimal-but-realistic genome: one CRUD module with a provenance source."""
    return {
        "solution_name": "Test App",
        "solution_id": 42,
        "genome_version": "1.0.0",
        "modules": {
            "work_order": {
                "aggregate_root": "WorkOrder",
                "entities": ["WorkOrder"],
                "archimate_element_ids": [ARCH_ID],
                "fields": {
                    "WorkOrder": [
                        {"name": "title", "type": "string", "required": True},
                        {"name": "amount", "type": "decimal", "required": False},
                    ],
                },
            },
        },
        "_archimate_sources": {"modules.work_order.WorkOrder": ARCH_ID},
    }


def _canonical(bundle) -> str:
    """A stable serialization of the whole bundle for byte-identity comparison."""
    return json.dumps(dataclasses.asdict(bundle), sort_keys=True, default=str)


def test_runs_with_no_llm(monkeypatch):
    """The emitter must never touch the LLM boundary.

    We poison `LLMService._call_llm` so that any attempt to invoke it during
    emission fails the test loudly, then assert a full bundle is still produced.
    """
    from app.modules.ai_chat.services.llm_service_impl import LLMService

    def _boom(*args, **kwargs):  # pragma: no cover - only runs on a boundary breach
        raise AssertionError(
            "genome_to_bundle called the LLM — the deterministic emitter boundary "
            "was breached (ADR 0010 / 03_integration.md §2)."
        )

    monkeypatch.setattr(LLMService, "_call_llm", _boom, raising=False)

    bundle = genome_to_bundle(_sample_genome())

    assert bundle is not None
    assert bundle.services, "expected at least one emitted ServiceDef"


def test_deterministic_byte_identical():
    """Same genome in → byte-identical bundle out (the reproducibility contract)."""
    g = _sample_genome()
    first = genome_to_bundle(g)
    second = genome_to_bundle(_sample_genome())

    assert first.spec_hash == second.spec_hash
    assert _canonical(first) == _canonical(second)


def test_deterministic_openapi_stable():
    """The emitted OpenAPI document is stable across runs."""
    a = genome_to_bundle(_sample_genome()).openapi
    b = genome_to_bundle(_sample_genome()).openapi
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_stamps_provenance_on_service_paths():
    """Every emitted PathDef carries the source ArchiMate element id."""
    bundle = genome_to_bundle(_sample_genome())
    svc = next(s for s in bundle.services if s.name == "WorkOrder")
    assert svc.paths, "expected CRUD paths on the service"
    for path in svc.paths:
        assert path.archimate_source_id == ARCH_ID, (
            f"path {path.operation_id} lost its provenance stamp"
        )


def test_provenance_map_carries_sources():
    """The bundle's provenance dict reflects the genome's _archimate_sources."""
    bundle = genome_to_bundle(_sample_genome())
    prov = bundle.provenance
    assert prov["entities"].get("modules.work_order.WorkOrder") == ARCH_ID
    assert prov["genome_version"] == "1.0.0"


def test_missing_provenance_is_none_not_fabricated():
    """A module with no archimate source stamps None — never an invented id."""
    g = _sample_genome()
    del g["modules"]["work_order"]["archimate_element_ids"]
    bundle = genome_to_bundle(g)
    svc = next(s for s in bundle.services if s.name == "WorkOrder")
    for path in svc.paths:
        assert path.archimate_source_id is None
