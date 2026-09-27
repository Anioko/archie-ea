"""DEF-068, Capgemini dry-run pass 3: the RAID Resolve/Close button's
@click="setStatus(id, {{ 'resolved' if ... else 'closed' }})" rendered the
ternary's output as a bare (unquoted) JS identifier, not a string literal.
Alpine evaluated the undefined identifier as `undefined`, so the PATCH body
JSON.stringify'd to {} (no status key), and the route replied 200 having
updated nothing -- "Resolve" silently did nothing.

First fix attempt (wrapping in |tojson inside the double-quoted @click
attribute) passed a naive substring check but was itself broken: |tojson's
double-quoted output closed the double-quoted HTML attribute early,
producing malformed HTML (browser-verified: the button's own outerHTML came
back as `@click="setStatus(1, " resolved")"=""`, with "resolved")" split
into a garbage bare attribute). This test parses the actual button element
with an HTML parser and reads its @click attribute as a single value, which
the substring-only version of this test could not have caught.
"""

import re

import pytest
from html.parser import HTMLParser


class _ButtonAttrFinder(HTMLParser):
    """Collect every <button ...> tag's attributes, in document order."""

    def __init__(self):
        super().__init__()
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            self.buttons.append(dict(attrs))


@pytest.mark.usefixtures("db_session")
def test_raid_resolve_button_renders_quoted_status(app, db_session, make_org, tenant_ctx):
    from app.models.raid_item import RaidItem, RaidKind, RaidStatus
    from app.models.user import User

    org = make_org("def068-raid-button-quoting")
    with tenant_ctx(org.id):
        item = RaidItem(title="ZZ-VERIFY RAID button quoting", kind=RaidKind.ISSUE,
                         status=RaidStatus.OPEN, organization_id=org.id)
        db_session.add(item)
        user = User(email=f"def068btn-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()
        item_id = item.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/risks/")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)

            parser = _ButtonAttrFinder()
            parser.feed(html)
            resolve_buttons = [
                b for b in parser.buttons
                if b.get("@click", "").startswith(f"setStatus({item_id},")
            ]
            assert len(resolve_buttons) == 1, (
                f"expected exactly one Resolve button for item {item_id}, "
                f"found matching @click attrs: {[b.get('@click') for b in parser.buttons]}"
            )
            click_attr = resolve_buttons[0]["@click"]
            # A well-formed attribute value, parsed as ONE attribute by a real
            # HTML parser, proves the quoting did not break out early.
            assert re.fullmatch(
                rf"setStatus\({item_id}, ['\"]resolved['\"]\)", click_attr
            ), f"@click attribute was malformed: {click_attr!r}"
