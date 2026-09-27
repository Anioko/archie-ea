"""
Enterprise Genome — SECURITY slice tests.

Uses the SHARED fixtures (tests/conftest.py): db_session runs inside a
transaction that is always rolled back, so the demo seed leaves no residue.

Asserts the four things that make the slice sellable rather than decorative:
  1. real control / requirement names render (no fabricated placeholders);
  2. every emitted row resolves to a REAL requirement ArchiMate element id in
     the org — structural provenance is present and non-optional;
  3. the build is deterministic — a rebuild is byte-identical (same dict, same
     spec_hash, same rendered HTML);
  4. the seed is reversible — unseed removes exactly what it created.
"""
from __future__ import annotations

import pytest

from app.models.archimate_core import ArchiMateElement
from app.modules.enterprise_genome.seeds.seed_security_demo import (
    seed_security_demo,
    unseed_security_demo,
)
from app.modules.enterprise_genome.services.security_matrix_emitter import (
    render_control_matrix,
)
from app.modules.enterprise_genome.services.security_slice import build_security_slice

pytestmark = pytest.mark.usefixtures("db_session")

_EXPECTED_CONTROL_COUNT = 8
_KNOWN_CODES = {"CC6.1", "CC6.7", "CC7.2", "CC8.1", "A.9.2.1", "A.10.1.1", "A.12.4.1", "A.12.1.2"}


def _seed(db_session, make_org):
    org = make_org("security-genome")
    summary = seed_security_demo(org.id, session=db_session)
    assert summary["created"] is True
    assert summary["controls"] == _EXPECTED_CONTROL_COUNT
    return org


def test_slice_projects_seeded_controls(db_session, make_org):
    org = _seed(db_session, make_org)
    slice_dict = build_security_slice(org.id, session=db_session)

    assert slice_dict["slice"] == "security"
    assert slice_dict["organization_id"] == org.id
    assert slice_dict["store"] == "compliance_requirements"  # ONE labelled store
    assert len(slice_dict["controls"]) == _EXPECTED_CONTROL_COUNT

    codes = {n["control"]["code"] for n in slice_dict["controls"]}
    assert codes == _KNOWN_CODES
    # Real names, not placeholders.
    for node in slice_dict["controls"]:
        assert node["control"]["title"].strip()
        assert node["requirement"]["title"].strip()
        assert node["framework"]["code"] in {"SOC2", "ISO27001"}


def test_every_row_resolves_to_a_real_requirement_element(db_session, make_org):
    org = _seed(db_session, make_org)
    slice_dict = build_security_slice(org.id, session=db_session)

    for node in slice_dict["controls"]:
        prov = node["provenance"]
        # Provenance is structural and NON-OPTIONAL.
        assert prov["origin"] == "element"
        element_id = prov["archimate_element_id"]
        assert element_id, "node emitted without a provenance element id"
        # It must resolve to a real element in THIS org.
        element = (
            db_session.query(ArchiMateElement)
            .filter(ArchiMateElement.id == element_id)
            .filter(ArchiMateElement.organization_id == org.id)
            .first()
        )
        assert element is not None, f"provenance id {element_id} does not resolve in org {org.id}"
        assert element.name == prov["element_name"]
        assert prov["layer"] == "motivation"


def test_build_is_deterministic(db_session, make_org):
    org = _seed(db_session, make_org)
    first = build_security_slice(org.id, session=db_session)
    second = build_security_slice(org.id, session=db_session)

    assert first == second
    assert first["spec_hash"] == second["spec_hash"]
    assert first["spec_hash"].startswith("sha256:")


def test_emitter_is_deterministic_and_renders_real_data(db_session, make_org):
    org = _seed(db_session, make_org)
    slice_dict = build_security_slice(org.id, session=db_session)

    html_a = render_control_matrix(slice_dict)
    html_b = render_control_matrix(slice_dict)
    assert html_a == html_b  # byte-identical rebuild

    # Real control code and a real provenance element id are in the output.
    assert "CC6.1" in html_a
    sample_element_id = slice_dict["controls"][0]["provenance"]["archimate_element_id"]
    assert f'data-archimate-element-id="{sample_element_id}"' in html_a
    assert slice_dict["spec_hash"] in html_a


def test_seed_is_idempotent_and_reversible(db_session, make_org):
    org = make_org("security-genome")

    first = seed_security_demo(org.id, session=db_session)
    assert first["created"] is True

    # Re-run: no duplication.
    again = seed_security_demo(org.id, session=db_session)
    assert again["created"] is False
    assert build_security_slice(org.id, session=db_session)["controls"]

    # Reverse it.
    removed = unseed_security_demo(org.id, session=db_session)
    assert removed["requirements"] == _EXPECTED_CONTROL_COUNT
    assert removed["controls"] == _EXPECTED_CONTROL_COUNT
    assert removed["elements"] == _EXPECTED_CONTROL_COUNT

    after = build_security_slice(org.id, session=db_session)
    assert after["controls"] == []
