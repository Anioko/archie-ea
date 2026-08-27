"""Regression coverage for dashboard fetch contracts that previously broke live surfaces."""

from pathlib import Path
import uuid

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]


def _architect(db_session, make_org, slug):
    from app.models.user import User

    org = make_org(slug)
    user = User(
        email=f"duplicate-surface-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Duplicate",
        last_name="Reviewer",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="architect",
    )
    db_session.add(user)
    db_session.flush()
    return org, user


def test_guardrail_dedupe_blueprint_exposes_dashboard_element_groups_url():
    """The guardrail-enabled app must serve the URL dashboard.js requests.

    Removing this route from the v2 blueprint makes the dashboard's live
    ArchiMate duplicate panel receive a 404 even though the legacy blueprint
    still has an implementation.
    """
    from app.modules.duplicate_detection.v2.routes.unified_duplicate_routes import (
        unified_duplicate_bp_v2,
    )

    app = Flask(__name__)
    app.register_blueprint(unified_duplicate_bp_v2)

    assert app.url_map.bind("localhost").test(
        "/duplicate-detection/simple/api/element-groups", "GET"
    )


def test_governance_bulk_delete_rejects_non_2xx_before_reading_json():
    """A 500 body must count as a deletion failure even if it contains JSON.

    Without the HTTP-status guard a gateway error payload could claim success
    and the dashboard would show a successful delete although nothing changed.
    """
    source = (
        ROOT / "app" / "static" / "js" / "governance" / "governance_dashboard.js"
    ).read_text(encoding="utf-8")
    bulk_delete = source.split("executeBulkDelete: function", 1)[1]
    normalized = " ".join(bulk_delete.split())

    # The delete now goes through Platform.fetch, which RAISES on any non-2xx, so
    # the explicit `if (!r.ok) throw` is gone. The contract is unchanged and is
    # what this asserts: a non-2xx must reach the failure counter, never the
    # success path, even when the error body happens to be valid JSON.
    assert "Platform.fetch.delete(" in normalized, (
        "the delete must use the wrapper that throws on non-2xx"
    )
    assert ".catch(function () { failures++; })" in normalized, (
        "a thrown non-2xx must be counted as a failed deletion"
    )
    assert "failures === 0" in normalized and "Capabilities deleted." in normalized, (
        "success may only be reported when nothing failed"
    )


def test_element_groups_api_requires_authentication(app):
    response = app.test_client().get(
        "/duplicate-detection/simple/api/element-groups"
    )

    assert response.status_code in {302, 401}


def test_element_groups_api_is_tenant_scoped(
    app, db_session, login_as, make_org
):
    from app.models.archimate_core import ArchiMateElement

    org_a, user_a = _architect(db_session, make_org, "element-groups-a")
    org_b = make_org("element-groups-b")
    db_session.add_all(
        [
            ArchiMateElement(
                name="Shared A", type="ApplicationComponent", layer="Application",
                organization_id=org_a.id,
            ),
            ArchiMateElement(
                name="shared a", type="ApplicationComponent", layer="Application",
                organization_id=org_a.id,
            ),
            ArchiMateElement(
                name="Shared B", type="ApplicationComponent", layer="Application",
                organization_id=org_b.id,
            ),
            ArchiMateElement(
                name="shared b", type="ApplicationComponent", layer="Application",
                organization_id=org_b.id,
            ),
        ]
    )
    db_session.flush()
    client = app.test_client()
    login_as(client, user_a)

    response = client.get("/duplicate-detection/simple/api/element-groups")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["total_groups"] == 1
    assert body["total_duplicated_elements"] == 2
    assert {group["name"].casefold() for group in body["groups"]} == {"shared a"}


def test_element_groups_api_reports_query_failure(
    app, db_session, login_as, make_org, monkeypatch
):
    from app.models.archimate_core import ArchiMateElement

    _org, user = _architect(db_session, make_org, "element-groups-error")
    query_type = type(ArchiMateElement.query)

    def fail_query(_query, *_entities):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(query_type, "with_entities", fail_query)
    client = app.test_client()
    login_as(client, user)

    response = client.get("/duplicate-detection/simple/api/element-groups")

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "An internal error occurred",
    }


def test_element_groups_ui_keeps_failure_distinct_from_empty_result():
    script = (
        ROOT / "app" / "static" / "js" / "duplicate_detection" / "dashboard.js"
    ).read_text(encoding="utf-8")
    template = (
        ROOT / "app" / "templates" / "duplicate_detection" / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert "elementGroupsError: ''" in script
    assert "this.elementGroupsError = '';" in script
    assert (
        "this.elementGroupsError = 'Could not load ArchiMate element duplicate groups.';"
        in script
    )
    load_method = script.split("async loadElementGroups()", 1)[1].split(
        "clearRunFeedback()", 1
    )[0]
    failure_branch = load_method.split("catch (error)", 1)[1].split("finally", 1)[0]
    assert "this.elementGroups = []" not in failure_branch
    assert "this.elementGroupsTotalDuplicated = 0" not in failure_branch
    assert 'x-if="!elementGroupsLoading && elementGroupsError"' in template
    assert (
        'x-if="!elementGroupsLoading && !elementGroupsError && elementGroups.length === 0"'
        in template
    )
    assert '@click="loadElementGroups()"' in template


def test_value_stream_ai_capability_lookup_distinguishes_http_failure_from_no_match():
    """A failed lookup must reach applySuggestion's failure toast, not say missing.

    A null result is meaningful here: it tells the user that the named capability
    was not found. HTTP and network failures are different states and must be
    re-raised so the caller surfaces the actual failed apply operation.
    """
    source = (ROOT / "app" / "static" / "js" / "value_stream" / "grid.js").read_text(
        encoding="utf-8"
    )
    resolver = source.split("async resolveCapabilityByName(name)", 1)[1].split(
        "async applySuggestion(index)", 1
    )[0]

    # The lookup now goes through Platform.fetch, which raises on any non-ok
    # response, so the explicit `if (!resp.ok) throw` is gone. What the contract
    # actually needs is unchanged and is what is asserted here: the failure must
    # LEAVE this function, because a null return from it means "no capability of
    # that name exists" and a swallowed failure would be indistinguishable.
    assert "Platform.fetch" in resolver, "the lookup must use the wrapper that throws on non-ok"
    assert "throw err;" in resolver, "network and HTTP failures must propagate to applySuggestion"
    assert "return results.find" in resolver, "a genuine no-match must still return null"
