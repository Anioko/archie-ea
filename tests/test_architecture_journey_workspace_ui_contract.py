"""Static UI contracts for the Architecture Journey people and record edges.

These checks deliberately pin the safe interaction rather than the visual copy: a
person is selected from the tenant user directory, and a record edge can only be
removed when it already exists.  Raw numeric identifiers are not a usable or safe
record picker.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/architecture_assistant/architecture_journey_workspace.html"
SCRIPT = ROOT / "app/static/js/architecture_assistant/architecture_journey_workspace.js"
ARCHIMATE_CORE = ROOT / "app/models/archimate_core.py"


def test_workspace_exposes_people_directory_picker_and_role_selection():
    html = TEMPLATE.read_text(encoding="utf-8")
    javascript = SCRIPT.read_text(encoding="utf-8")

    assert 'role="combobox"' in html
    assert '@input.debounce.300ms="searchMembers"' in html
    assert 'type="hidden"' in html and 'name="journey_member_user_id"' in html
    assert 'id="journey-member-role"' in html
    assert "'/api/users'" in javascript
    assert "/members`" in javascript


def test_workspace_lists_current_people_and_links_with_unlink_action():
    html = TEMPLATE.read_text(encoding="utf-8")
    javascript = SCRIPT.read_text(encoding="utf-8")

    assert 'data-testid="journey-participant-list"' in html
    assert 'data-testid="journey-linked-records"' in html
    assert '@click="unlinkLink(' in html
    assert "Platform.fetch.delete" in javascript
    assert "/links/${linkId}`" in javascript


def test_workspace_never_asks_people_or_record_linkers_for_a_raw_numeric_id():
    html = TEMPLATE.read_text(encoding="utf-8")
    javascript = SCRIPT.read_text(encoding="utf-8")

    assert 'id="link-entity-id"' not in html
    assert 'type="number"' not in html
    assert "Record id" not in html
    assert "numeric id" not in html.lower()
    assert "/applications/api/list?search=" in javascript
    assert "/archimate/api/elements/search?q=" in javascript
    assert "/architecture/decisions/api/element-search" not in javascript


def test_workspace_uses_platform_feedback_and_has_one_page_heading_owner():
    html = TEMPLATE.read_text(encoding="utf-8")
    javascript = SCRIPT.read_text(encoding="utf-8")

    assert "page_shell(" in html
    executable_template = re.sub(r"\{#.*?#\}", "", html, flags=re.DOTALL)
    assert "<h1" not in executable_template  # page_shell owns the only h1 at render time
    assert "Platform.toast.success" in javascript
    assert "Platform.toast.error" in javascript
    assert "window.alert" not in javascript
    assert "window.confirm" not in javascript


def test_fast_init_archimate_targets_keep_tenant_columns_for_safe_resolution():
    source = ARCHIMATE_CORE.read_text(encoding="utf-8")

    assert "class ArchitectureModel(TenantMixin, db.Model):" in source
    assert "class ArchiMateElement(TenantMixin, db.Model):" in source
