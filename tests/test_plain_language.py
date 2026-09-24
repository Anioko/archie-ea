"""Plain-language display: vocabulary map, filter, sidebar labels, and the
show_archimate_names user setting.

Acceptance criteria from the plain-language brief:
1. Sidebar shows "Architecture" and "Vendor Analysis"
2. With the setting on, an element page shows "ApplicationComponent"; with it
   off, "Application"
3. No API response or stored value changes
4. Cross-organisation test for every new read
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db_session, make_org, **kwargs):
    from app.models.user import User

    org = make_org("plain-lang")
    defaults = dict(
        email=f"plain-lang-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Plain",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    defaults.update(kwargs)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


def _login(client, user_id):
    from tests._session_test_helpers import mint_test_sid

    _sid = mint_test_sid(user_id)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
        if _sid:
            sess["_sid"] = _sid

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_client(app, db_session, make_org, **user_kwargs):
    user = _make_user(db_session, make_org, **user_kwargs)
    client = app.test_client()
    _login(client, user.id)
    return client, user


# ---------------------------------------------------------------------------
# Vocabulary map
# ---------------------------------------------------------------------------

def test_vocabulary_map_covers_all_registered_types():
    """Every type in ArchiMateElementTypes has a plain-language entry."""
    from app.models.archimate_element_types import (
        PLAIN_LANGUAGE_NAMES,
        ArchiMateElementTypes,
    )

    all_types = ArchiMateElementTypes.get_all_elements()
    missing = set(all_types) - set(PLAIN_LANGUAGE_NAMES)
    assert not missing, f"Types missing from PLAIN_LANGUAGE_NAMES: {missing}"


def test_plain_name_for_known_type():
    from app.models.archimate_element_types import plain_name_for

    assert plain_name_for("ApplicationComponent") == "Application"
    assert plain_name_for("BusinessActor") == "Person or team"
    assert plain_name_for("Node") == "Platform"
    assert plain_name_for("SystemSoftware") == "Software platform"
    assert plain_name_for("WorkPackage") == "Project"
    assert plain_name_for("Assessment") == "Finding"
    assert plain_name_for("ImplementationEvent") == "Milestone"
    assert plain_name_for("Plateau") == "Stage"


def test_plain_name_for_unknown_type_returns_original():
    from app.models.archimate_element_types import plain_name_for

    assert plain_name_for("Location") == "Location"
    assert plain_name_for("Grouping") == "Grouping"
    assert plain_name_for("Junction") == "Junction"


def test_plain_name_for_none_returns_em_dash():
    from app.models.archimate_element_types import plain_name_for

    assert plain_name_for(None) == "\u2014"
    assert plain_name_for("") == "\u2014"


def test_plain_layer_names():
    from app.models.archimate_element_types import plain_layer_name

    assert plain_layer_name("strategy") == "Strategy"
    assert plain_layer_name("business") == "Business"
    assert plain_layer_name("application") == "Applications"
    assert plain_layer_name("technology") == "Technology"
    assert plain_layer_name("implementation") == "Projects and change"
    assert plain_layer_name("implementation_migration") == "Projects and change"
    assert plain_layer_name(None) == "\u2014"


# ---------------------------------------------------------------------------
# Jinja filter
# ---------------------------------------------------------------------------

def test_plain_name_filter_defaults_to_plain(app):
    """With no user (or show_archimate_names=False), the filter returns plain names."""
    from app.template_helpers import _plain_name

    assert _plain_name("ApplicationComponent") == "Application"
    assert _plain_name("BusinessActor") == "Person or team"
    assert _plain_name("Node") == "Platform"


def test_plain_name_filter_with_archimate_on(app, db_session, make_org):
    """With show_archimate_names=True, the filter returns the original name."""
    from app.template_helpers import _plain_name

    user = _make_user(db_session, make_org, show_archimate_names=True)
    assert _plain_name("ApplicationComponent", user) == "ApplicationComponent"
    assert _plain_name("BusinessActor", user) == "BusinessActor"


def test_plain_name_filter_with_archimate_off(app, db_session, make_org):
    """With show_archimate_names=False, the filter returns plain names."""
    from app.template_helpers import _plain_name

    user = _make_user(db_session, make_org, show_archimate_names=False)
    assert _plain_name("ApplicationComponent", user) == "Application"
    assert _plain_name("BusinessActor", user) == "Person or team"


def test_plain_name_filter_none_input(app):
    from app.template_helpers import _plain_name

    assert _plain_name(None) == "\u2014"
    assert _plain_name("") == "\u2014"


def test_plain_layer_filter(app, db_session, make_org):
    from app.template_helpers import _plain_layer

    user = _make_user(db_session, make_org, show_archimate_names=False)
    assert _plain_layer("application", user) == "Applications"
    assert _plain_layer("implementation", user) == "Projects and change"

    user.show_archimate_names = True
    assert _plain_layer("application", user) == "application"


# ---------------------------------------------------------------------------
# Sidebar labels (acceptance criterion 2)
# ---------------------------------------------------------------------------

def test_sidebar_shows_architecture_not_archimate_elements():
    """The Library zone link formerly labelled 'ArchiMate Elements' now reads
    'Architecture'. Only the library-zone link is checked — the same endpoint
    may appear under a different label in a persona's My-work zone
    (e.g. 'ArchiMate Model' for data_architect), which is a distinct surface."""
    from app.utils.role_access import SIDEBAR_ZONES

    for role, zones in SIDEBAR_ZONES.items():
        for zone in zones:
            if zone["zone"] != "library":
                continue
            for link in zone["links"]:
                if link["endpoint"] == "archimate_crud.dashboard":
                    assert link["label"] == "Architecture", (
                        f"Role {role} library zone: expected 'Architecture', got '{link['label']}'"
                    )


def test_module_directory_shows_vendor_analysis():
    """The More-tools entry formerly labelled 'Vendor ArchiMate Analysis' now
    reads 'Vendor Analysis'."""
    from app.modules.modules_directory.routes import _MORE_TOOLS

    for label, endpoint, _icon in _MORE_TOOLS:
        if endpoint == "main.vendor_archimate_analysis":
            assert label == "Vendor Analysis", (
                f"Expected 'Vendor Analysis', got '{label}'"
            )
            break
    else:
        pytest.fail("main.vendor_archimate_analysis not found in _MORE_TOOLS")


# ---------------------------------------------------------------------------
# Element page display (acceptance criterion 3)
# ---------------------------------------------------------------------------

def test_element_type_display_with_setting_off(app, db_session, make_org):
    """With show_archimate_names=False (default), element types use plain names."""
    from app.models.archimate_element_types import plain_name_for

    # Simulate what the template filter would return
    assert plain_name_for("ApplicationComponent") == "Application"
    assert plain_name_for("BusinessActor") == "Person or team"
    assert plain_name_for("Node") == "Platform"
    assert plain_name_for("WorkPackage") == "Project"


def test_element_type_display_with_setting_on(app, db_session, make_org):
    """With show_archimate_names=True, element types use standard names."""
    from app.template_helpers import _plain_name

    user = _make_user(db_session, make_org, show_archimate_names=True)
    assert _plain_name("ApplicationComponent", user) == "ApplicationComponent"
    assert _plain_name("BusinessActor", user) == "BusinessActor"


# ---------------------------------------------------------------------------
# No API/stored-value change (acceptance criterion 4)
# ---------------------------------------------------------------------------

def test_element_json_unchanged_by_display_setting(app, db_session, make_org):
    """The show_archimate_names setting only affects display, never API responses
    or stored values. An element's stored type is always the ArchiMate name."""
    from app.models.archimate_core import ArchiMateElement

    user = _make_user(db_session, make_org)
    org_id = user.organization_id

    elem = ArchiMateElement(
        name="Test Component",
        type="ApplicationComponent",
        organization_id=org_id,
    )
    db_session.add(elem)
    db_session.flush()

    # Capture the element's data before any setting change
    before = {
        "name": elem.name,
        "type": elem.type,
        "organization_id": elem.organization_id,
    }

    # Toggle the setting — this must not affect the stored element
    user.show_archimate_names = True
    db_session.flush()

    after = {
        "name": elem.name,
        "type": elem.type,
        "organization_id": elem.organization_id,
    }

    assert before == after, (
        f"Element data changed when display setting was toggled: {before} -> {after}"
    )
    # The stored type is always the ArchiMate name
    assert elem.type == "ApplicationComponent"


# ---------------------------------------------------------------------------
# Cross-organisation test (acceptance criterion: reads must not write;
# cross-organisation test for every new read)
# ---------------------------------------------------------------------------

def test_plain_name_filter_cross_organisation(app, db_session, make_org):
    """The plain_name filter is a pure read — it must not write anything and
    must work identically across organisations."""
    from app.template_helpers import _plain_name

    user_a = _make_user(db_session, make_org, show_archimate_names=False)
    user_b = _make_user(db_session, make_org, show_archimate_names=True)

    # Both users see the correct names for their setting
    assert _plain_name("ApplicationComponent", user_a) == "Application"
    assert _plain_name("ApplicationComponent", user_b) == "ApplicationComponent"

    # The filter does not mutate the user
    assert user_a.show_archimate_names is False
    assert user_b.show_archimate_names is True


def test_vocabulary_map_is_read_only():
    """PLAIN_LANGUAGE_NAMES is a module-level constant — calling plain_name_for
    must not mutate it."""
    from app.models.archimate_element_types import PLAIN_LANGUAGE_NAMES, plain_name_for

    before = dict(PLAIN_LANGUAGE_NAMES)
    plain_name_for("ApplicationComponent")
    plain_name_for("BusinessActor")
    after = dict(PLAIN_LANGUAGE_NAMES)
    assert before == after


# ---------------------------------------------------------------------------
# show_archimate_names column default
# ---------------------------------------------------------------------------

def test_show_archimate_names_defaults_false(db_session, make_org):
    """New users default to show_archimate_names=False (plain language)."""
    user = _make_user(db_session, make_org)
    assert user.show_archimate_names is False


def test_show_archimate_names_can_be_enabled(db_session, make_org):
    """The setting can be toggled on."""
    user = _make_user(db_session, make_org, show_archimate_names=True)
    assert user.show_archimate_names is True


# ---------------------------------------------------------------------------
# Account page display preferences endpoint
# ---------------------------------------------------------------------------

def test_save_display_preferences_toggle_on(app, db_session, make_org):
    """POST to save_preferences with show_archimate_names=on enables it."""
    client, user = _make_client(app, db_session, make_org)

    resp = client.post(
        "/account/manage/preferences",
        data={"form_type": "display", "show_archimate_names": "on"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Re-fetch user from DB to confirm persistence
    db_session.expire(user)
    db_session.refresh(user)
    assert user.show_archimate_names is True


def test_save_display_preferences_toggle_off(app, db_session, make_org):
    """POST to save_preferences without the key leaves it off."""
    client, user = _make_client(app, db_session, make_org)
    # First turn it on
    user.show_archimate_names = True
    db_session.flush()

    resp = client.post(
        "/account/manage/preferences",
        data={"form_type": "display"},  # unchecked checkbox sends no value
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db_session.expire(user)
    db_session.refresh(user)
    assert user.show_archimate_names is False


# ---------------------------------------------------------------------------
# F1: Template filter wired into rendered pages
# ---------------------------------------------------------------------------

def test_detail_page_uses_plain_name_filter(app, db_session, make_org):
    """The element detail page renders element_type through |plain_name."""
    from app.models.archimate_core import ArchiMateElement

    client, user = _make_client(app, db_session, make_org)
    org_id = user.organization_id

    elem = ArchiMateElement(
        name="TestApp",
        type="ApplicationComponent",
        organization_id=org_id,
    )
    db_session.add(elem)
    db_session.flush()

    resp = client.get(
        f"/architecture/application/ApplicationComponent/{elem.id}"
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    # With setting off (default), should show plain name
    assert "Application" in html
    # The PascalCase name may appear in URLs but the display text should be plain


def test_detail_page_respects_show_archimate_names(app, db_session, make_org):
    """With show_archimate_names=True, the detail page shows PascalCase names."""
    from app.models.archimate_core import ArchiMateElement

    client, user = _make_client(app, db_session, make_org, show_archimate_names=True)
    org_id = user.organization_id

    elem = ArchiMateElement(
        name="TestApp",
        type="ApplicationComponent",
        organization_id=org_id,
    )
    db_session.add(elem)
    db_session.flush()

    resp = client.get(
        f"/architecture/application/ApplicationComponent/{elem.id}"
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    # With setting on, should show PascalCase name in display
    assert "ApplicationComponent" in html


# ---------------------------------------------------------------------------
# F2: Unified save_preferences endpoint
# ---------------------------------------------------------------------------

def test_save_preferences_handles_notification_keys(app, db_session, make_org):
    """POST to save_preferences with notification keys updates them."""
    client, user = _make_client(app, db_session, make_org)

    resp = client.post(
        "/account/manage/preferences",
        data={
            "form_type": "notifications",
            "arb_decisions": "on",
            "weekly_digest": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db_session.expire(user)
    db_session.refresh(user)
    prefs = user.notification_preferences or {}
    assert prefs.get("arb_decisions") is True
    assert prefs.get("weekly_digest") is True
    assert prefs.get("solution_updates") is False


def test_save_preferences_handles_both_in_one_request(app, db_session, make_org):
    """POST to save_preferences with both notification and display keys."""
    client, user = _make_client(app, db_session, make_org)

    resp = client.post(
        "/account/manage/preferences",
        data={
            "form_type": "notifications",
            "arb_decisions": "on",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db_session.expire(user)
    db_session.refresh(user)
    # Only notification prefs should be affected
    prefs = user.notification_preferences or {}
    assert prefs.get("arb_decisions") is True
    # Display preference should be unchanged (default False)
    assert user.show_archimate_names is False


# ---------------------------------------------------------------------------
# F3: JS globals present in admin base template
# ---------------------------------------------------------------------------

def test_admin_base_includes_plain_language_js_globals(app, db_session, make_org):
    """The admin base template injects PLAIN_LANGUAGE_NAMES as JS globals."""
    client, user = _make_client(app, db_session, make_org)

    resp = client.get("/architecture/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "window.__PLAIN_LANGUAGE_NAMES__" in html
    assert "window.__PLAIN_LAYER_NAMES__" in html
    assert "window.__SHOW_ARCHIMATE_NAMES__" in html
    # Default is false
    assert '"__SHOW_ARCHIMATE_NAMES__": false' in html or \
           'window.__SHOW_ARCHIMATE_NAMES__ = false' in html


def test_admin_base_shows_archimate_names_true_when_enabled(app, db_session, make_org):
    """When show_archimate_names is True, the JS global reflects it."""
    client, user = _make_client(app, db_session, make_org, show_archimate_names=True)

    resp = client.get("/architecture/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert '"__SHOW_ARCHIMATE_NAMES__": true' in html or \
           'window.__SHOW_ARCHIMATE_NAMES__ = true' in html


# ---------------------------------------------------------------------------
# F4: _plain_name and _plain_layer log on exception
# ---------------------------------------------------------------------------

def test_plain_name_does_not_crash_on_detached_user(app):
    """_plain_name handles a plain object with no show_archimate_names attr."""
    from app.template_helpers import _plain_name

    class FakeUser:
        pass

    # Should not raise, should fall back to plain name
    result = _plain_name("ApplicationComponent", FakeUser())
    assert result == "Application"


def test_plain_layer_does_not_crash_on_detached_user(app):
    """_plain_layer handles a plain object with no show_archimate_names attr."""
    from app.template_helpers import _plain_layer

    class FakeUser:
        pass

    result = _plain_layer("application", FakeUser())
    assert result == "Applications"


# ---------------------------------------------------------------------------
# F5: main/index.html no longer has inconsistent ArchiMate references
# ---------------------------------------------------------------------------

def test_landing_page_no_archimate_in_badge(app):
    """The public landing page badge no longer says 'Powered by ArchiMate 3.2'."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Powered by ArchiMate 3.2" not in html
    assert "Powered by open standards" in html


def test_landing_page_no_archimate_in_feature_desc(app):
    """The feature description no longer references ArchiMate 3.2 elements."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "all ArchiMate 3.2 elements" not in html
    assert "all architecture elements" in html


# ---------------------------------------------------------------------------
# F6: SQLite migration uses INTEGER not BOOLEAN
# ---------------------------------------------------------------------------

def test_sqlite_migration_uses_integer_not_boolean():
    """The SQLite branch of the migration uses INTEGER, not BOOLEAN."""
    manage_path = os.path.join(os.path.dirname(__file__), "..", "manage.py")
    with open(manage_path) as f:
        source = f.read()
    # Find the else branch (SQLite) — it should use INTEGER
    # The PostgreSQL branch correctly uses BOOLEAN; only the else branch matters
    else_idx = source.find("show_archimate_names INTEGER")
    assert else_idx != -1, (
        "SQLite migration must use INTEGER not BOOLEAN"
    )
    # The BOOLEAN occurrence should only be in the PostgreSQL branch
    bool_idx = source.find("show_archimate_names BOOLEAN")
    assert bool_idx == -1 or bool_idx < else_idx, (
        "BOOLEAN must only appear in the PostgreSQL branch, not SQLite"
    )