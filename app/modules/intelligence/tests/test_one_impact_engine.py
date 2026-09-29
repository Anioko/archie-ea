"""One impact engine — the three surfaces (Impact Analysis page API,
AIImpactAnalysisService, and the Ask screen's cross_layer_impact endpoint)
return the same element set and order from the canonical walk."""

from __future__ import annotations


def _element(db_session, org_id, name, etype="ApplicationComponent", layer="application"):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type=etype, layer=layer, organization_id=org_id)
    db_session.add(el)
    db_session.flush()
    return el


def _relationship(db_session, org_id, source, target, type_="Serving"):
    from app.models import ArchiMateRelationship

    rel = ArchiMateRelationship(
        source_id=source.id, target_id=target.id, type=type_, organization_id=org_id
    )
    db_session.add(rel)
    db_session.flush()
    return rel


def _application_component(db_session, org_id, element_id, name="App"):
    from app.models.application_portfolio import ApplicationComponent

    comp = ApplicationComponent(
        name=name, organization_id=org_id, archimate_element_id=element_id
    )
    db_session.add(comp)
    db_session.flush()
    return comp


# ── surface 1: ImpactAnalysisService (Impact Analysis page API) ──────────


def _surface_impact_analysis_service(element_id):
    """Call ImpactAnalysisService.analyze_change_impact — the Impact Analysis page API path."""
    from app.modules.solutions_strategic.v2.services.impact_analysis_service import (
        ImpactAnalysisService,
    )

    result = ImpactAnalysisService.analyze_change_impact(element_id, change_type="MODIFY")
    direct = result.get("direct_dependencies") or []
    indirect = result.get("indirect_dependencies") or []
    # Return sorted (id, name) pairs for comparison.
    all_deps = direct + indirect
    return [(d["id"], d.get("name")) for d in all_deps]


# ── surface 2: AIImpactAnalysisService (assistant) ───────────────────────


def _surface_ai_impact_service(app_id):
    """Call AIImpactAnalysisService.analyze_application_impact — the assistant path."""
    from app.modules.ai_chat.services.ai_impact_analysis_service import (
        AIImpactAnalysisService,
    )

    result = AIImpactAnalysisService.analyze_application_impact(
        app_id, scenario="modification", include_ai_analysis=False
    )
    graph = result.get("dependency_analysis") or {}
    direct = graph.get("direct_impacts") or []
    indirect_list = []
    for depth_items in (graph.get("indirect_impacts") or {}).values():
        indirect_list.extend(depth_items)
    all_impacts = direct + indirect_list
    return [(i["id"], i.get("name")) for i in all_impacts]


# ── surface 3: cross_layer_impact directly (Ask screen) ──────────────────


def _surface_cross_layer_impact(element_id):
    """Call IntelligenceQueryService.cross_layer_impact — the Ask screen path."""
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    result = IntelligenceQueryService.cross_layer_impact(
        element_id,
        include_derived=False,
        max_depth=3,
        direction="downstream",
        with_owner=True,
    )
    rows = result.get("rows") or []
    elements = result.get("elements") or {}
    return [
        (r["element_id"], elements.get(str(r["element_id"]), {}).get("name"))
        for r in rows
    ]


# ── the comparison test ──────────────────────────────────────────────────


def test_three_surfaces_return_same_element_set_and_order(app, db_session, make_org):
    """The three impact surfaces return the same element set
    and order for the same seed element."""
    org = make_org("one-engine")
    a = _element(db_session, org.id, "Platform-A")
    b = _element(db_session, org.id, "Service-B")
    c = _element(db_session, org.id, "Database-C")
    d = _element(db_session, org.id, "Capability-D", etype="Capability", layer="business")
    _relationship(db_session, org.id, a, b)
    _relationship(db_session, org.id, b, c)
    _relationship(db_session, org.id, c, d)
    app_comp = _application_component(db_session, org.id, a.id, name="Platform App")
    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id

        surface1 = _surface_impact_analysis_service(a.id)
        surface2 = _surface_ai_impact_service(app_comp.id)
        surface3 = _surface_cross_layer_impact(a.id)

    # All three surfaces must return the same element ids in the same order.
    ids1 = [eid for eid, _name in surface1]
    ids2 = [eid for eid, _name in surface2]
    ids3 = [eid for eid, _name in surface3]

    assert ids1 == ids2, (
        f"ImpactAnalysisService ({ids1}) and AIImpactAnalysisService ({ids2}) "
        f"return different element sets"
    )
    assert ids1 == ids3, (
        f"ImpactAnalysisService ({ids1}) and cross_layer_impact ({ids3}) "
        f"return different element sets"
    )

    # All three surfaces must return non-empty results.
    assert len(surface1) > 0, "ImpactAnalysisService returned no dependencies"
    assert len(surface2) > 0, "AIImpactAnalysisService returned no dependencies"
    assert len(surface3) > 0, "cross_layer_impact returned no dependencies"


def test_two_organisation_impact_never_crosses_org_boundary(app, db_session, make_org):
    """An impact walk in organisation A never returns
    elements belonging to organisation B."""
    org_a = make_org("one-engine-org-a")
    org_b = make_org("one-engine-org-b")

    a1 = _element(db_session, org_a.id, "A1")
    a2 = _element(db_session, org_a.id, "A2")
    _relationship(db_session, org_a.id, a1, a2)

    b1 = _element(db_session, org_b.id, "B1")
    b2 = _element(db_session, org_b.id, "B2")
    _relationship(db_session, org_b.id, b1, b2)

    db_session.commit()

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org_a.id

        surface1 = _surface_impact_analysis_service(a1.id)
        surface3 = _surface_cross_layer_impact(a1.id)

    # Org A's walk must only contain org A's elements.
    org_a_ids = {a1.id, a2.id}
    org_b_ids = {b1.id, b2.id}

    for eid, _name in surface1:
        assert eid in org_a_ids, f"Org A impact walk leaked org B element {eid}"
        assert eid not in org_b_ids, f"Org A impact walk leaked org B element {eid}"

    for eid, _name in surface3:
        assert eid in org_a_ids, f"Org A cross_layer_impact leaked org B element {eid}"
        assert eid not in org_b_ids, f"Org A cross_layer_impact leaked org B element {eid}"


def test_health_field_present_on_every_row(app, db_session, make_org):
    """Every impact row carries a health field — the maturity block
    for Capability rows, None for others."""
    org = make_org("one-engine-health")
    a = _element(db_session, org.id, "App-X")
    b = _element(db_session, org.id, "Svc-Y")
    c = _element(db_session, org.id, "Cap-Z", etype="Capability", layer="business")
    _relationship(db_session, org.id, a, b)
    _relationship(db_session, org.id, b, c)
    db_session.commit()

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        result = IntelligenceQueryService.cross_layer_impact(
            a.id, include_derived=False, max_depth=3, with_owner=True
        )

    rows = result.get("rows") or []
    elements = result.get("elements") or {}
    assert len(rows) > 0, "Expected at least one dependency row"

    for row in rows:
        # Every row must have a "health" key.
        assert "health" in row, f"Row {row['element_id']} missing health field"
        el_type = elements.get(str(row["element_id"]), {}).get("type")
        if el_type == "Capability":
            # Capability rows carry the maturity block as health.
            assert row["health"] is not None, (
                f"Capability row {row['element_id']} has null health"
            )
        else:
            # Non-capability rows carry None (renders as —).
            assert row["health"] is None, (
                f"Non-capability row {row['element_id']} has unexpected health data"
            )


def test_pagination_stable_cursor_and_total(app, db_session, make_org):
    """Pagination with stable cursor returns correct page and total."""
    org = make_org("one-engine-page")
    root = _element(db_session, org.id, "Root")
    # Create 5 direct dependencies.
    children = []
    for i in range(5):
        child = _element(db_session, org.id, f"Child-{i}")
        _relationship(db_session, org.id, root, child)
        children.append(child)
    db_session.commit()

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id

        # Page 1: first 2 rows.
        page1 = IntelligenceQueryService.cross_layer_impact(
            root.id,
            include_derived=False,
            max_depth=3,
            with_owner=False,
            page_size=2,
        )
        assert page1["total"] == 5
        assert len(page1["rows"]) == 2
        assert page1["next_cursor"] is not None

        # Page 2: next 2 rows after cursor.
        page2 = IntelligenceQueryService.cross_layer_impact(
            root.id,
            include_derived=False,
            max_depth=3,
            with_owner=False,
            page_size=2,
            cursor=page1["next_cursor"],
        )
        assert page2["total"] == 5
        assert len(page2["rows"]) == 2
        assert page2["next_cursor"] is not None

        # Page 3: last row.
        page3 = IntelligenceQueryService.cross_layer_impact(
            root.id,
            include_derived=False,
            max_depth=3,
            with_owner=False,
            page_size=2,
            cursor=page2["next_cursor"],
        )
        assert page3["total"] == 5
        assert len(page3["rows"]) == 1
        assert page3["next_cursor"] is None  # No more pages.

        # All element ids across pages must be unique and cover all 5 children.
        all_ids = set()
        for page in [page1, page2, page3]:
            for row in page["rows"]:
                all_ids.add(row["element_id"])
        assert all_ids == {c.id for c in children}