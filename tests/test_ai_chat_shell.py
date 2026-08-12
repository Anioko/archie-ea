"""AI Chat shell redesign (shell-overhaul Wave 1, Task 6).

Product owner screenshotted `/ai-chat` at ~1024px as cluttered: suggestion
cards clip mid-word, the conversation rail eats a third of the width, and
three control rows stack above any content. This file pins the calm
version's structural contract:

- The "Multi-Domain AI Assistant" title block is gone — the assistant/scope
  selectors already say what's selected.
- Exactly one header control row (`data-testid="chat-header-row"`).
- Docs / Match / Export / Approvals move behind a single overflow menu
  (`data-testid="chat-overflow-menu"`).
- The conversation rail (Context/Query/Alerts/Chats) is a collapsible drawer
  (`data-testid="chat-rail"`) whose collapse state is Alpine-driven so it can
  auto-collapse below 1280px and remember the user's choice.

Does not touch transport/streaming behaviour — see test_ai_chat_stream_error.py
for that contract, and test_header_and_login_feedback.py for the pinned
`#model-selector` Settings-panel assertion this file must not break.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_user(db_session, make_org, label):
    from app.models.user import User

    org = make_org(f"aichat-shell-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"aichat-shell-{label}-{suffix}@example.com",
        first_name="Chat",
        last_name="Shell",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    return user.id, org


def _get_chat_html(app, db_session, make_org):
    user, _ = _make_user(db_session, make_org, "get")
    client = app.test_client()
    _login(client, user)
    resp = client.get("/ai-chat")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    return resp.get_data(as_text=True)


def test_no_multi_domain_title_block(app, db_session, make_org):
    html = _get_chat_html(app, db_session, make_org)
    assert "Multi-Domain AI Assistant" not in html, (
        "the old title block should be gone — the assistant/scope selectors "
        "already say what's selected"
    )


def test_exactly_one_header_row(app, db_session, make_org):
    html = _get_chat_html(app, db_session, make_org)
    assert html.count('data-testid="chat-header-row"') == 1


def test_overflow_menu_wraps_docs_match_export_approvals(app, db_session, make_org):
    html = _get_chat_html(app, db_session, make_org)
    assert 'data-testid="chat-overflow-menu"' in html

    start = html.index('data-testid="chat-overflow-menu"')
    # The overflow menu is a bounded dropdown container — grab a generous
    # slice after its opening tag rather than trying to balance divs.
    end = start + 6000
    menu_slice = html[start:end]

    assert "Docs" in menu_slice
    assert "Match" in menu_slice
    assert "Export" in menu_slice
    assert "Approvals" in menu_slice


def test_rail_has_alpine_collapse_state(app, db_session, make_org):
    html = _get_chat_html(app, db_session, make_org)
    assert 'data-testid="chat-rail"' in html

    start = html.index('data-testid="chat-rail"')
    # The Alpine binding referencing the collapse var may appear before or
    # after the testid attribute on the same tag — look at the whole opening
    # tag plus a little slack either side.
    tag_slice = html[max(0, start - 400) : start + 400]
    assert "railOpen" in tag_slice, (
        "expected an Alpine binding referencing a rail collapse state var "
        "(e.g. :class=\"railOpen ? ... : ...\") near data-testid=\"chat-rail\""
    )


def test_model_selector_still_present(app, db_session, make_org):
    """Guards against Task 6 breaking the Task 4 Settings-panel contract."""
    html = _get_chat_html(app, db_session, make_org)
    assert 'id="model-selector"' in html


def test_show_more_suggestions_declared_on_shared_ancestor(app, db_session, make_org):
    """Evidence review: Task 6's "More suggestions" disclosure declared
    `showMoreSuggestions` on an inner `x-data` that only wrapped the
    AI-architects card grid, while the disclosure button, the remaining
    domain cards, and the toggle's own `x-show="!showMoreSuggestions"` live
    as siblings outside that div. Alpine's `with()`-based expression
    evaluation throws `ReferenceError: showMoreSuggestions is not defined`
    for every one of those siblings — reproduced 8x in the console capture
    behind the screenshot evidence. Pin the fix structurally: exactly one
    `x-data` block declares the variable (on #domain-welcome-grid, the
    common ancestor of every element that reads it), not the narrower inner
    div."""
    html = _get_chat_html(app, db_session, make_org)

    assert html.count("showMoreSuggestions: false") == 1, (
        "showMoreSuggestions must be declared exactly once, on the common "
        "ancestor of every element that reads it — a second declaration "
        "means it is scoped too narrowly again and siblings outside it will "
        "throw ReferenceError at render"
    )

    grid_start = html.index('id="domain-welcome-grid"')
    grid_tag_end = html.index(">", grid_start)
    grid_open_tag = html[grid_start:grid_tag_end]
    assert "showMoreSuggestions" in grid_open_tag, (
        "showMoreSuggestions must be declared on #domain-welcome-grid itself "
        "so every x-show reading it (the disclosure button, the remaining "
        "domain cards) shares its scope"
    )

    more_button_idx = html.index("More suggestions")
    disclosure_idx = html.rindex('x-show="!showMoreSuggestions"', 0, more_button_idx)
    remaining_cards_idx = html.rindex('x-show="showMoreSuggestions"', 0, more_button_idx)
    assert grid_start < disclosure_idx, "disclosure toggle must be inside #domain-welcome-grid"
    assert grid_start < remaining_cards_idx, "remaining domain cards must be inside #domain-welcome-grid"


def _find_ancestor_ids_and_testids(html, target_id):
    """Walk the DOM (via html.parser, not regex) and return the set of
    (attr, value) markers — id or data-testid — carried by every open
    ancestor element of the node with id=target_id, at the point the parser
    reaches it. Void/self-closing elements are not tracked as containers."""
    from html.parser import HTMLParser

    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    class _Walker(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []  # list of (tag, attrs_dict)
            self.ancestors_at_target = None

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == target_id and self.ancestors_at_target is None:
                # Record ancestors BEFORE pushing the target itself.
                self.ancestors_at_target = list(self.stack)
            if tag not in VOID_ELEMENTS:
                self.stack.append((tag, attrs_dict))

        def handle_startendtag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == target_id and self.ancestors_at_target is None:
                self.ancestors_at_target = list(self.stack)
            # self-closing — never pushed, nothing to pop.

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    walker = _Walker()
    walker.feed(html)
    return walker.ancestors_at_target


def test_approvals_modal_is_not_descendant_of_overflow_menu(app, db_session, make_org):
    """CRITICAL fix (Wave 1 final review): the approvals modal
    (#ai-chat-approvals-modal) used to be nested inside the overflow
    dropdown's x-show="menuOpen" panel. Platform.modal.open() toggles
    classes on the modal element in place — it does not teleport the modal
    elsewhere in the DOM — so the instant the overflow menu closes
    (@click="menuOpen = false" fires on every trigger inside it, including
    the Approvals menu item itself), the whole subtree containing the modal
    goes display:none while Platform.modal still believes it is open: body
    scroll stays locked, Escape stays bound, background stays inert, and the
    user sees nothing. Parsed with html.parser (not regex) because nesting
    depth is exactly what's under test."""
    html = _get_chat_html(app, db_session, make_org)

    assert 'id="ai-chat-approvals-modal"' in html
    assert 'data-testid="chat-overflow-menu"' in html

    ancestors = _find_ancestor_ids_and_testids(html, "ai-chat-approvals-modal")
    assert ancestors is not None, "could not locate #ai-chat-approvals-modal while parsing"

    ancestor_testids = {a.get("data-testid") for _, a in ancestors}

    assert "chat-overflow-menu" not in ancestor_testids, (
        "#ai-chat-approvals-modal must not be a descendant of "
        '[data-testid="chat-overflow-menu"] — that panel is x-show="menuOpen" '
        "and toggling menuOpen would hide the modal out from under "
        "Platform.modal"
    )
