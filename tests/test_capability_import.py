"""Bulk import of a capability model.

The gap: Archie could import an application inventory and could not import a
capability model. A business architect arrives with an existing Level 1–3 model
— all of them do, because the model predates the tool — and had no path but
re-keying it.

What these tests hold the importer to, in rough order of how badly each one
hurts when it is missing:

* **A rejected row costs you that row, not the file.** One bad maturity value
  must not roll back 400 good capabilities; errors carry the 1-based line
  number the spreadsheet shows.
* **Running it twice is safe.** An import nobody dares repeat is an import
  nobody runs on production data.
* **The hierarchy survives.** Parents may appear below their children, and a
  cycle is rejected in the plan rather than committed into a tree that no
  longer terminates.
* **Nothing is written until the operator has seen what would be.**
* **The ArchiMate model is populated too** — a capability that exists only in
  ``business_capability`` is invisible to the composer and the traceability
  matrix.
"""

from __future__ import annotations

import io
import uuid

import pytest

from app.modules.capabilities.services.capability_import_service import (
    CapabilityImportError,
    CapabilityImportService,
)


def _read(text: str, filename="model.csv"):
    return CapabilityImportService.read(io.BytesIO(text.encode("utf-8")), filename)


def _plan(text: str):
    rows, headers = _read(text)
    return CapabilityImportService.plan(rows, headers)


def _errors_on(plan, line):
    return [e for e in plan.errors if e.line == line]


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------


def test_the_template_carries_the_documented_columns():
    csv_text = CapabilityImportService.template_csv()
    header = csv_text.splitlines()[0]
    for column in ("code", "name", "level", "parent", "current_maturity"):
        assert column in header
    # A template with no example rows teaches nothing about the parent column.
    assert len(csv_text.strip().splitlines()) > 2


def test_headers_are_matched_loosely(app):
    """Excel, Sparx, LeanIX and APQC do not agree on a spelling."""
    with app.app_context():
        rows, headers = _read(
            "Capability Name,Capability Code,Tier,Parent Capability\n"
            "Demand Planning,CAP-1,2,CAP-0\n"
        )
    assert rows[0]["name"] == "Demand Planning"
    assert rows[0]["code"] == "CAP-1"
    assert rows[0]["level"] == "2"
    assert rows[0]["parent"] == "CAP-0"


def test_a_file_that_is_not_csv_or_excel_is_refused():
    with pytest.raises(CapabilityImportError) as exc:
        CapabilityImportService.read(io.BytesIO(b"anything"), "model.pdf")
    assert ".csv" in str(exc.value)


def test_blank_spacer_rows_are_not_errors(app):
    with app.app_context():
        rows, _headers = _read("name,level\nAlpha,1\n\n,\nBeta,1\n")
    assert [r["name"] for r in rows] == ["Alpha", "Beta"]


# ---------------------------------------------------------------------------
# Planning — validation
# ---------------------------------------------------------------------------


def test_a_file_with_no_name_column_is_rejected_whole(db_session, make_org, tenant_ctx):
    org = make_org(f"import-noname-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan("code,level\nCAP-1,1\n")
    assert plan.rows == []
    assert "name" in plan.errors[0].message.lower()


def test_bad_values_reject_their_own_row_only(db_session, make_org, tenant_ctx):
    org = make_org(f"import-bad-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan(
            "name,level,current maturity,importance\n"
            "Good One,1,3,high\n"        # line 2 — fine
            "Bad Level,9,3,high\n"       # line 3
            "Bad Maturity,1,77,high\n"   # line 4
            "Bad Importance,1,3,vital\n" # line 5
            ",1,3,high\n"                # line 6 — no name
            "Good Two,2,4,low\n"         # line 7 — fine
        )

    assert [r.values["name"] for r in plan.rows] == ["Good One", "Good Two"], (
        "a bad row must not take its neighbours with it"
    )
    assert _errors_on(plan, 3)[0].column == "level"
    assert _errors_on(plan, 4)[0].column == "current_maturity"
    assert _errors_on(plan, 5)[0].column == "strategic_importance"
    assert _errors_on(plan, 6)[0].column == "name"


def test_a_duplicated_code_names_the_line_it_collides_with(db_session, make_org, tenant_ctx):
    org = make_org(f"import-dupe-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan("code,name\nCAP-1,First\nCAP-1,Second\n")
    assert len(plan.rows) == 1
    assert "line 2" in _errors_on(plan, 3)[0].message


def test_ignored_columns_are_reported_rather_than_dropped_silently(
    db_session, make_org, tenant_ctx
):
    org = make_org(f"import-ignored-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan("name,Cost Centre\nAlpha,CC-100\n")
    assert plan.columns_ignored == ["Cost Centre"]
    assert any("Cost Centre" in w for w in plan.warnings)


# ---------------------------------------------------------------------------
# Planning — hierarchy
# ---------------------------------------------------------------------------


def test_a_parent_may_appear_below_its_child(db_session, make_org, tenant_ctx):
    """Spreadsheets are sorted by name as often as by hierarchy."""
    org = make_org(f"import-fwd-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan(
            "code,name,level,parent\n"
            "CAP-1-1,Demand Planning,2,CAP-1\n"
            "CAP-1,Supply Chain,1,\n"
        )
    assert plan.errors == []
    assert plan.creates == 2


def test_an_unresolvable_parent_is_rejected_with_advice(db_session, make_org, tenant_ctx):
    org = make_org(f"import-noparent-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan("code,name,level,parent\nCAP-9,Orphan,2,NOT-HERE\n")
    assert plan.creates == 0
    message = _errors_on(plan, 2)[0].message
    assert "NOT-HERE" in message
    assert "import the parent level first" in message.lower()


def test_a_cycle_is_rejected_in_the_plan(db_session, make_org, tenant_ctx):
    """A cycle committed to the database is a tree that does not terminate."""
    org = make_org(f"import-cycle-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        plan = _plan(
            "code,name,level,parent\n"
            "A,Alpha,1,B\n"
            "B,Beta,2,A\n"
        )
    assert plan.creates == 0
    assert any("own ancestor" in e.message for e in plan.errors)


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


def test_apply_creates_the_tree_and_its_archimate_elements(
    db_session, make_org, tenant_ctx
):
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability

    tag = uuid.uuid4().hex[:8]
    org = make_org(f"import-apply-{tag}")
    with tenant_ctx(org.id):
        plan = _plan(
            "code,name,level,parent,domain,current maturity,target maturity\n"
            f"{tag}-1,Supply Chain {tag},1,,Operations,,\n"
            f"{tag}-1-1,Demand Planning {tag},2,{tag}-1,Operations,2,4\n"
        )
        result = CapabilityImportService.apply(plan)

        assert result["created"] == 2
        assert result["archimate_elements"] == 1, (
            "one parent link — the elements themselves come from the "
            "before_insert listener; what the import adds is the hierarchy"
        )

        parent = BusinessCapability.query.filter_by(code=f"{tag}-1").one()
        child = BusinessCapability.query.filter_by(code=f"{tag}-1-1").one()

        assert child.parent_capability_id == parent.id
        assert child.current_maturity_level == 2
        assert child.target_maturity_level == 4
        assert child.maturity_gap == 2
        assert child.maturity_assessment_date is not None, (
            "current_maturity_level defaults to 1, so a level written without "
            "an assessment date cannot be told from an unassessed capability"
        )
        assert parent.maturity_assessment_date is None, (
            "the parent row supplied no maturity and must not be marked assessed"
        )

        element = db_session.get(ArchiMateElement, child.archimate_element_id)
        assert element.type == "Capability"
        assert element.layer == "strategy", (
            "layer is canonically lower case — the element browser, the "
            "/architecture/api/layer/<layer>/* endpoints and LAYER_CONFIG all "
            "key on it, so a capitalised 'Strategy' is invisible to every one"
        )
        assert element.parent_id == parent.archimate_element_id, (
            "the element hierarchy must mirror the capability hierarchy, or a "
            "decomposition drawn in the composer contradicts the map"
        )


def test_importing_the_same_file_twice_changes_nothing_the_second_time(
    db_session, make_org, tenant_ctx
):
    tag = uuid.uuid4().hex[:8]
    org = make_org(f"import-idem-{tag}")
    csv_text = (
        "code,name,level,parent\n"
        f"{tag}-1,Supply Chain {tag},1,\n"
        f"{tag}-1-1,Demand Planning {tag},2,{tag}-1\n"
    )
    with tenant_ctx(org.id):
        first = CapabilityImportService.apply(_plan(csv_text))
        assert first["created"] == 2

        second_plan = _plan(csv_text)
        assert second_plan.creates == 0
        assert second_plan.updates == 0
        assert second_plan.unchanged == 2

        second = CapabilityImportService.apply(second_plan)
        assert (second["created"], second["updated"]) == (0, 0)


def test_a_changed_cell_updates_and_a_blank_cell_leaves_the_value_alone(
    db_session, make_org, tenant_ctx
):
    from app.models.business_capabilities import BusinessCapability

    tag = uuid.uuid4().hex[:8]
    org = make_org(f"import-update-{tag}")
    with tenant_ctx(org.id):
        CapabilityImportService.apply(
            _plan(f"code,name,level,domain,owner\n{tag}-1,Original {tag},1,Operations,Alice\n")
        )

        plan = _plan(f"code,name,level,domain,owner\n{tag}-1,Renamed {tag},1,,\n")
        assert plan.updates == 1
        assert set(plan.rows[0].changes) == {"name"}, (
            "a blank cell means 'leave it alone', not 'erase it' — an import "
            "that blanks a column nobody filled in destroys data"
        )

        CapabilityImportService.apply(plan)
        cap = BusinessCapability.query.filter_by(code=f"{tag}-1").one()
        assert cap.name == f"Renamed {tag}"
        assert cap.business_domain == "Operations"
        assert cap.business_owner == "Alice"


def test_a_failure_part_way_through_leaves_nothing_behind(
    db_session, make_org, tenant_ctx, monkeypatch
):
    """A half-imported capability model is worse than none.

    The operator cannot tell which half is real, and re-running is the only
    recovery — which is exactly what half-written parent links make unsafe.
    """
    from app.models.business_capabilities import BusinessCapability

    tag = uuid.uuid4().hex[:8]
    org = make_org(f"import-atomic-{tag}")
    with tenant_ctx(org.id):
        plan = _plan(
            "code,name,level\n"
            f"{tag}-1,First {tag},1\n"
            f"{tag}-2,Second {tag},1\n"
        )

        def _boom(_capabilities):
            raise RuntimeError("archimate sync exploded")

        monkeypatch.setattr(CapabilityImportService, "_sync_archimate", staticmethod(_boom))

        with pytest.raises(RuntimeError):
            CapabilityImportService.apply(plan)

        assert BusinessCapability.query.filter(
            BusinessCapability.code.in_([f"{tag}-1", f"{tag}-2"])
        ).count() == 0


def test_two_organisations_may_use_the_same_capability_codes(
    db_session, make_org, tenant_ctx
):
    """Every capability model uses codes; they cannot be first-come-first-served.

    ``business_capability.code`` shipped globally unique, so the second
    organisation to import its own model collided on row one. It is unique per
    organisation now — existing databases need
    ``flask scope-capability-code-to-tenant``.
    """
    from app.models.business_capabilities import BusinessCapability

    tag = uuid.uuid4().hex[:8]
    org_a = make_org(f"import-iso-a-{tag}")
    org_b = make_org(f"import-iso-b-{tag}")
    csv_text = f"code,name,level\nCAP-{tag},Supply Chain,1\n"

    with tenant_ctx(org_a.id):
        CapabilityImportService.apply(_plan(csv_text))

    with tenant_ctx(org_b.id):
        plan = _plan(csv_text)
        assert plan.creates == 1, (
            "org B saw org A's code as an existing row — the plan is not "
            "tenant-scoped"
        )
        CapabilityImportService.apply(plan)
        assert BusinessCapability.query.filter_by(code=f"CAP-{tag}").count() == 1
