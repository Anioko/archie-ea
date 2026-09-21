"""The Ask and Twin map pages: who can open them, what they render, and the
rules their markup and scripts keep.

Two kinds of test live here. The first drives the real pages through the test
client (signed in, signed out, workspace empty, populated, counts unreadable).
The second reads the page templates and scripts as text, for the properties that
must hold for every render rather than for one: one disclosure control, a single
element search endpoint, no layer or type asked for, no sentence written in the
browser, colour only from the layer tokens.
"""

from __future__ import annotations

import inspect
import re
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path

import pytest

# Fixtures (app, db_session, make_org, client, login_as) come from this
# directory's conftest, which re-exports the shared ones.

PAGES = ["/intelligence/ask", "/intelligence/twin-map"]

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_DIR = REPO_ROOT / "app" / "modules" / "intelligence" / "templates" / "intelligence"
SCRIPT_DIR = REPO_ROOT / "app" / "static" / "js" / "intelligence"


def _text_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _templates() -> dict[str, str]:
    return {p.name: _text_of(p) for p in sorted(TEMPLATE_DIR.glob("*.html"))}


def _scripts() -> dict[str, str]:
    return {p.name: _text_of(p) for p in sorted(SCRIPT_DIR.glob("*.js"))}


def _code(source: str) -> str:
    """A script with its comments removed, for checks about what it does."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(?m)//[^\n]*$", "", source)


def _everything() -> dict[str, str]:
    files = {f"templates/{n}": t for n, t in _templates().items()}
    files.update({f"js/{n}": t for n, t in _scripts().items()})
    return files


def _user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"ui-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Ui",
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


class _Visible(HTMLParser):
    """The text a person reads: text nodes only, skipping scripts and styles."""

    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.chunks.append(data.strip())


def _main_html(html: str) -> str:
    match = re.search(r'<main id="main-content".*?</main>', html, re.S)
    assert match, "the page has no main region"
    return match.group(0)


def _visible_text(html: str) -> str:
    parser = _Visible()
    parser.feed(html)
    return " ".join(parser.chunks)


def _rendered_templates(app):
    from flask import template_rendered

    seen: list[str] = []

    def record(sender, template, context, **extra):
        seen.append(template.name)

    template_rendered.connect(record, app)
    return seen, lambda: template_rendered.disconnect(record, app)


# --- the routes -------------------------------------------------------------


@pytest.mark.parametrize("path,template", [
    ("/intelligence/ask", "intelligence/ask.html"),
    ("/intelligence/twin-map", "intelligence/twin_map.html"),
])
def test_page_renders_for_a_signed_in_user_with_its_own_template(
    app, db_session, make_org, client, login_as, path, template
):
    org = make_org("ui-render")
    user = _user(db_session, org.id)
    seen, stop = _rendered_templates(app)
    try:
        login_as(client, user)
        response = client.get(path)
    finally:
        stop()
    assert response.status_code == 200
    assert template in seen


@pytest.mark.parametrize("path", PAGES)
def test_page_is_not_served_to_an_anonymous_visitor(app, client, path):
    response = client.get(path)
    assert response.status_code in (301, 302, 401)
    if response.status_code in (301, 302):
        assert "/account/login" in response.headers["Location"]


def test_the_two_pages_are_the_only_routes_this_blueprint_serves(app):
    """Ask and Twin map, and the Worked-out connections page they each link to."""
    rules = {
        rule.rule: sorted(rule.methods - {"HEAD", "OPTIONS"})
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("intelligence_ui.")
    }
    assert rules == {
        "/intelligence/ask": ["GET"],
        "/intelligence/twin-map": ["GET"],
        "/intelligence/worked-out-connections": ["GET"],
    }
    assert not [r for r in rules if r.startswith("/api/")]


def test_pages_have_a_breadcrumb_and_the_page_shell_wrapper(
    app, db_session, make_org, client, login_as
):
    org = make_org("ui-shell")
    user = _user(db_session, org.id)
    for path, title in (("/intelligence/ask", "Ask"), ("/intelligence/twin-map", "Twin map")):
        login_as(client, user)
        html = client.get(path).get_data(as_text=True)
        assert 'aria-label="Breadcrumb"' in html
        assert f'<h1 class="text-2xl font-bold text-foreground">{title}</h1>' in html
        assert "p-6 space-y-6" in html
        assert "container mx-auto" not in _main_html(html)


def test_twin_map_hands_a_whole_number_element_to_the_page(
    app, db_session, make_org, client, login_as
):
    org = make_org("ui-handoff")
    user = _user(db_session, org.id)
    login_as(client, user)
    html = client.get("/intelligence/twin-map?element=42").get_data(as_text=True)
    assert 'data-initial-element="42"' in html


@pytest.mark.parametrize("value", ["abc", "", "4 2", "1e3", "-"])
def test_twin_map_ignores_an_element_that_is_not_a_whole_number(
    app, db_session, make_org, client, login_as, value
):
    org = make_org("ui-bad-element")
    user = _user(db_session, org.id)
    login_as(client, user)
    response = client.get("/intelligence/twin-map", query_string={"element": value})
    assert response.status_code == 200
    assert 'data-initial-element=""' in response.get_data(as_text=True)


def test_ui_blueprint_registration_is_non_fatal_and_leaves_the_api_registered(monkeypatch):
    """A failure to load the UI blueprint costs the two pages and nothing else."""
    monkeypatch.setitem(sys.modules, "app.modules.intelligence.routes.ui", None)
    from app.modules.intelligence import register

    class _Logger:
        def __init__(self):
            self.errors = []

        def exception(self, msg, *args):
            self.errors.append(msg)

        def __getattr__(self, name):
            return lambda *a, **k: None

    class _App:
        def __init__(self):
            self.blueprints = {}
            self.logger = _Logger()

        def register_blueprint(self, bp, **kwargs):
            self.blueprints[bp.name] = bp

    stub = _App()
    register(stub)  # must not raise
    assert set(stub.blueprints) == {"intelligence_api"}
    assert any("UI blueprint" in message for message in stub.logger.errors)


# --- the empty workspace ----------------------------------------------------


def _patch_counts(monkeypatch, counts):
    from app._bootstrap import context_processors

    if isinstance(counts, Exception):
        def fail(org_id, ttl=None):
            raise counts

        monkeypatch.setattr(context_processors, "compute_nav_counts", fail)
    else:
        monkeypatch.setattr(
            context_processors, "compute_nav_counts", lambda org_id, ttl=None: dict(counts)
        )


@pytest.mark.parametrize("path", PAGES)
def test_an_empty_workspace_shows_the_setup_state_instead_of_the_picker(
    app, db_session, make_org, client, login_as, monkeypatch, path
):
    _patch_counts(monkeypatch, {"applications": 0, "elements": 0, "capabilities": 0, "vendors": 0})
    org = make_org("ui-empty")
    user = _user(db_session, org.id)
    login_as(client, user)
    html = _main_html(client.get(path).get_data(as_text=True))
    text = _visible_text(html)
    assert "Nothing is modelled yet" in text
    assert "Add your systems and teams, and this is where you will ask questions about them." in text
    assert "Set up your workspace" in text
    assert 'href="/dashboard/overview"' in html
    assert 'role="combobox"' not in html
    assert 'role="status"' in html
    assert not re.search(r"connector", text, re.I)
    assert "onboarding" not in html.lower()


@pytest.mark.parametrize("path", PAGES)
@pytest.mark.parametrize("counts", [
    {"applications": 1, "elements": 0, "capabilities": 0, "vendors": 0},
    {"applications": 0, "elements": 5, "capabilities": 0, "vendors": 0},
    {"applications": 0, "elements": 0, "capabilities": 2, "vendors": 0},
    {"applications": 0, "elements": 0, "capabilities": 0, "vendors": 3},
])
def test_a_populated_workspace_shows_the_picker_and_no_setup_state(
    app, db_session, make_org, client, login_as, monkeypatch, path, counts
):
    _patch_counts(monkeypatch, counts)
    org = make_org("ui-populated")
    user = _user(db_session, org.id)
    login_as(client, user)
    html = _main_html(client.get(path).get_data(as_text=True))
    assert 'role="combobox"' in html
    assert "Nothing is modelled yet" not in html


@pytest.mark.parametrize("path", PAGES)
def test_unreadable_counts_never_read_as_an_empty_workspace(
    app, db_session, make_org, client, login_as, monkeypatch, path
):
    """The shell answers a failed count with zeros; the pages must not take that
    for an empty workspace."""
    _patch_counts(monkeypatch, RuntimeError("counts unavailable"))
    org = make_org("ui-counts-down")
    user = _user(db_session, org.id)
    login_as(client, user)
    response = client.get(path)
    assert response.status_code == 200
    html = _main_html(response.get_data(as_text=True))
    assert 'role="combobox"' in html
    assert "Nothing is modelled yet" not in html


# --- what a person reads ----------------------------------------------------

# Page copy is written for the people who use the page. It carries no status
# label (an upper-case tag such as a status stamp) and no placeholder wording.
STATUS_LABELS = re.compile(r"\b(?:VERIFIED|UNVERIFIED|TBC|TODO)\b|(?i:to be confirmed)")
# ...and nothing that reads as a file, a path, a hash or a tracker id.
FORBIDDEN_SHAPES = re.compile(
    r"(\bapp/|\bdocs/|\bscripts/|\btests?/|\.py\b|\.html\b|\.md\b|\.json\b|"
    r"\b[0-9a-f]{7,40}\b|\b[A-Z]{1,3}-\d+\b)"
)


@pytest.mark.parametrize("path", PAGES)
def test_page_text_carries_no_status_labels_paths_or_ids_outside_full_detail(
    app, db_session, make_org, client, login_as, path
):
    org = make_org("ui-copy")
    user = _user(db_session, org.id)
    login_as(client, user)
    html = _main_html(client.get(path).get_data(as_text=True))
    html = re.sub(r"<[^>]*data-full-detail-region[^>]*>.*?</dl>\s*</div>", "", html, flags=re.S)
    text = _visible_text(html)
    assert text, "the page rendered no text at all"
    assert STATUS_LABELS.findall(text) == []
    assert FORBIDDEN_SHAPES.findall(text) == []


def test_script_strings_carry_no_status_labels():
    strings = []
    for name, source in _scripts().items():
        strings.extend(re.findall(r"'([^'\n]{4,})'", source))
        strings.extend(re.findall(r'"([^"\n]{4,})"', source))
    readable = [s for s in strings if " " in s]
    assert readable, "no readable strings found: the scan is not looking at the scripts"
    offenders = [s for s in readable if STATUS_LABELS.search(s)]
    assert offenders == []


# --- one entry point, no layer, one endpoint --------------------------------


def test_only_the_archimate_element_search_endpoint_is_used_and_nothing_layer_scoped():
    for name, source in _everything().items():
        assert "/architecture/api/layer/" not in source, name
        assert "/architecture/decisions/api/element-search" not in source, name
        for found in re.findall(r"/archimate/api/elements/[A-Za-z0-9_<>{}/-]*", source):
            assert found == "/archimate/api/elements/search", (name, found)
    assert "/archimate/api/elements/search" in _scripts()["core.js"]


def test_the_picker_asks_for_no_layer_type_or_vocabulary_term():
    for name, source in _templates().items():
        assert "<select" not in source, name
    # The picker and the search request carry only what was typed. (The pages
    # read an element's layer from the answer to place it on the map; that is
    # a value shown, never one collected.)
    assert not re.search(r"layer|archimate_type|vocabulary", _code(_scripts()["picker.js"]), re.I)
    picker_markup = re.sub(r"\{#.*?#\}", "", _templates()["_entity_picker.html"], flags=re.S)
    assert not re.search(r"layer|<select", picker_markup, re.I)
    core = _scripts()["core.js"]
    call = re.search(r"Platform\.fetch\.get\(SEARCH_URL, (\{[^}]*\})", core)
    assert call and set(re.findall(r"(\w+):", call.group(1))) == {"q", "limit"}


def test_names_come_only_from_the_impact_answers_element_map():
    for name, source in _everything().items():
        assert "/detail" not in source, name
        assert "localStorage" not in source and "sessionStorage" not in source, name
    urls = set(re.findall(r"'(/[a-z0-9_/.-]*)'", _scripts()["core.js"]))
    assert urls == {
        "/archimate/api/elements/search",
        "/api/v1/intelligence/impact/",
        "/api/v1/intelligence/derivation/recompute",
    }


def test_every_network_call_goes_through_platform_fetch():
    for name, source in _scripts().items():
        assert not re.search(r"(?<![.\w])fetch\(", source), name
        assert "XMLHttpRequest" not in source, name
        assert "console." not in source, name
    for name, source in _templates().items():
        assert "console." not in source, name


# --- one disclosure control -------------------------------------------------


def test_full_detail_is_defined_once_and_called_from_exactly_four_places():
    """The three surfaces that show a connection call the macro inline; the Worked-out
    connections page calls it with a call block. Both forms are counted, so the guard
    sees every call site."""
    templates = _templates()
    definitions = [n for n, t in templates.items() for _ in re.findall(r"\{%\s*macro\s+full_detail\(", t)]
    assert definitions == ["_full_detail.html"]
    calls = [
        n for n, t in templates.items()
        for _ in re.findall(
            r"\{\{\s*full_detail\(|\{%\s*call\s+full_detail\(", re.sub(r"\{#.*?#\}", "", t, flags=re.S)
        )
    ]
    assert sorted(calls) == [
        "_provenance_drawer.html", "ask.html", "twin_map.html", "worked_out_connections.html",
    ]


def test_the_disclosure_label_is_full_detail_and_it_starts_collapsed():
    source = _templates()["_full_detail.html"]
    assert re.search(r"data-full-detail-toggle.*?aria-expanded=\"false\"", source, re.S)
    assert "x-data=\"{ open: false }\"" in source
    assert re.search(r"\bFull detail\b", source)
    # A native button that changes nothing in the address bar.
    assert re.search(r"<button type=\"button\" data-full-detail-toggle", source)
    assert "href=" not in source and "window.open" not in source


def test_no_second_show_more_affordance_exists():
    banned = re.compile(
        r"<details|<summary|role=\"tab\"|role=\"tablist\"|x-collapse|Show more|Show less|"
        r"See more|Read more|More questions|Expand all|Collapse all",
        re.I,
    )
    for name, source in _templates().items():
        assert not banned.search(source), name
    for name, source in _scripts().items():
        assert not re.search(r"Show more|More questions", source, re.I), name
    # The only controls that carry aria-expanded: the one disclosure control,
    # the combobox, the question card that opens the picker, and the button
    # that collapses the Twin map's side panel.
    owners = {}
    for name, source in _templates().items():
        for tag in re.findall(r"<(?:button|input)[^>]*aria-expanded[^>]*>", source, re.S):
            key = ("full-detail" if "data-full-detail-toggle" in tag else
                   "combobox" if 'role="combobox"' in tag else
                   "question" if "ask-question-" in tag else
                   "rail" if "twin-rail-toggle" in tag else "OTHER")
            owners.setdefault(key, []).append(name)
    assert set(owners) == {"full-detail", "combobox", "question", "rail"}, owners


def test_the_map_table_is_present_without_a_toggle():
    source = _templates()["twin_map.html"]
    region = re.search(r"<div ([^>]*)data-map-table-region([^>]*)>", source)
    assert region, "the table region is missing from the Twin map page"
    attributes = region.group(1) + region.group(2)
    assert not re.search(r"x-show|x-if|x-cloak|hidden|:class|@click", attributes)
    table = _templates()["_map_table.html"]
    assert "<caption" in table and "<thead" in table
    assert re.search(r"tabindex", table) is None


def test_level_three_terms_appear_only_inside_full_detail():
    """The ArchiMate type, layer, rule, confidence, chain, depth, time worked out
    and engine version are named in the disclosure macro and nowhere else."""
    terms = ["ArchiMate type", "Engine version", "Derived record", "Worked out at", "Rule"]
    for name, source in _templates().items():
        if name == "_full_detail.html":
            continue
        visible = re.sub(r"\{#.*?#\}", "", source, flags=re.S)
        for term in terms:
            assert not re.search(r">\s*" + re.escape(term) + r"\s*<", visible), (name, term)
        for key in ("detail.type", "detail.layer", "detail.ruleId", "detail.confidence",
                    "detail.engineVersion", "detail.computedAt", "detail.derivedId", "detail.chain"):
            assert key not in visible or name in {"_full_detail.html"}, (name, key)


# --- the sentence is the server's --------------------------------------------


def test_no_script_or_template_writes_the_plain_terms_sentence_or_formats_confidence():
    signatures = [
        r"worked\s+this\s+out\s+because", r"hops\s+away", r"(very|fairly)\s+confident",
        r"less\s+confident", r"second\s+look",
    ]
    for name, source in _everything().items():
        for pattern in signatures:
            assert not re.search(pattern, source, re.I), (name, pattern)
        assert not re.search(r"confidence\s*(>=|<=|>|<)", source), name
        assert not re.search(r"toFixed|Math\.round|\*\s*100\b", source), name


def test_the_drawer_renders_the_supplied_sentence_in_one_paragraph_and_nothing_else():
    source = _templates()["_provenance_drawer.html"]
    assert len(re.findall(r"data-plain-terms", source)) == 1
    assert re.search(r'<p [^>]*data-plain-terms x-text="drawer\.plainTerms"></p>', source)
    assert 'x-show="drawer.plainTerms"' in source


# --- colour and copy of the map ---------------------------------------------


def test_no_hard_coded_colour_values_and_no_per_domain_palette():
    for name, source in _everything().items():
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", re.sub(r"&#\d+;", "", source)), name
        assert not re.search(r"\.domain-[a-z]+", source), name
        assert not re.search(r"\brgba?\(|\bhsla?\(\s*\d", source), name
    graph = _scripts()["graph.js"]
    for layer in ("motivation", "strategy", "business", "application", "technology", "implementation"):
        assert f"layer-{layer}" in graph
    assert "layer-risk" not in graph


def test_derived_edges_are_dashed_and_badged_and_explicit_edges_are_solid():
    graph = _scripts()["graph.js"]
    assert "var DASH = '5,5'" in graph
    assert re.search(r"stroke-dasharray.*d\.edge\.kind === 'derived' \? DASH : null", graph)
    assert "Intelligence.WORKED_OUT" in graph
    assert "var WORKED_OUT = 'Worked out';" in _code(_scripts()["core.js"])


def test_the_map_text_is_written_with_text_never_html():
    graph = _scripts()["graph.js"]
    assert ".html(" not in graph
    assert "innerHTML" not in graph
    for name, source in _scripts().items():
        assert "innerHTML" not in source and "insertAdjacentHTML" not in source, name


def test_the_hop_depth_control_is_a_native_range_input_from_one_to_five():
    source = _templates()["twin_map.html"]
    control = re.search(r"<input type=\"range\"[^>]*>", source, re.S)
    assert control
    tag = control.group(0)
    for attribute in ('id="twin-hop-depth"', 'min="1"', 'max="5"', 'step="1"'):
        assert attribute in tag
    assert re.search(r'<label for="twin-hop-depth"[^>]*>Hop depth</label>', source)


def test_the_page_scripts_are_top_level_factories_not_alpine_data_registrations():
    for name in ("ask.js", "twin_map.js"):
        source = _code(_scripts()[name])
        assert "Alpine.data(" not in source, name
    assert "window.askSurface = askSurface;" in _scripts()["ask.js"]
    assert "window.twinMapSurface = twinMapSurface;" in _scripts()["twin_map.js"]
    assert 'x-data="askSurface()"' in _templates()["ask.html"]
    assert 'x-data="twinMapSurface()"' in _templates()["twin_map.html"]


def test_the_shipped_macros_are_the_named_ones_with_the_right_keywords():
    joined = "\n".join(_templates().values())
    assert "from 'components/empty_state.html' import empty_state" in joined
    assert "from 'macros/page_shell.html' import empty_state" not in joined
    assert "from 'components/drawer.html' import drawer with context" in joined
    assert "from 'components/skeleton.html' import" in joined
    for call in re.findall(r"empty_state\((.*?)\) \}\}", joined, re.S):
        assert "headline=" not in call and "body=" not in call
    assert "animate-spin" not in joined and "loader" not in joined


# --- what the pages are built on ----------------------------------------------


def _element(db_session, org_id, name, layer="application", kind="ApplicationComponent"):
    from app.models import ArchiMateElement

    row = ArchiMateElement(name=name, type=kind, layer=layer, organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


def _relationship(db_session, org_id, source, target):
    from app.models import ArchiMateRelationship

    row = ArchiMateRelationship(
        source_id=source.id, target_id=target.id, type="Serving", organization_id=org_id
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_the_impact_answer_carries_the_names_and_derived_fields_the_pages_read(
    app, db_session, make_org, client, login_as
):
    """The pages read four things from the impact answer and invent none of them:
    an element map whose entries hold exactly id, name, type and layer, and on a
    worked-out row its record id, engine version and sentence."""
    import datetime

    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    org = make_org("ui-contract")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Beta", layer="business", kind="BusinessActor")
    c = _element(db_session, org.id, "Gamma", layer="technology", kind="Node")
    first = _relationship(db_session, org.id, a, b)
    second = _relationship(db_session, org.id, b, c)
    db_session.add(DerivedRelationship(
        organization_id=org.id, source_element_id=a.id, target_element_id=c.id,
        derived_type="Serving", rule_id="serving-through-serving",
        chain=[first.id, second.id], chain_element_ids=[a.id, b.id, c.id], depth=2,
        confidence=0.82, provenance="derivation", engine_version="1.0",
        computed_at=datetime.datetime.utcnow(), stale=False,
    ))
    db_session.flush()

    login_as(client, user)
    response = client.get(
        f"/api/v1/intelligence/impact/{a.id}?include_derived=true&max_depth=3&with_owner=true"
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert set(data) >= {"rows", "summary", "reasons", "elements"}
    assert set(data["elements"]) == {str(a.id), str(b.id), str(c.id)}
    for entry in data["elements"].values():
        assert set(entry) == {"id", "name", "type", "layer"}
    assert data["elements"][str(b.id)] == {
        "id": b.id, "name": "Beta", "type": "BusinessActor", "layer": "business",
    }

    derived = [r for r in data["rows"] if r["relation"]["kind"] == "derived"]
    explicit = [r for r in data["rows"] if r["relation"]["kind"] == "explicit"]
    assert len(derived) == 1 and len(explicit) == 2
    relation = derived[0]["relation"]
    assert isinstance(relation["derived_id"], int)
    assert relation["engine_version"] == "1.0"
    assert relation["plain_terms"].startswith("We worked this out because")
    for row in explicit:
        assert row["relation"]["derived_id"] is None
        assert row["relation"]["engine_version"] is None
        assert row["relation"]["plain_terms"] is None


def test_the_accessibility_audit_this_work_extends_checks_wcag_22_and_fails_rather_than_skips():
    """The pages are added to an audit that reads the 2.2 tag set and refuses to skip:
    without both, a clean result there would say nothing."""
    source = (REPO_ROOT / "tests" / "smoke" / "test_accessibility_audit.py").read_text(encoding="utf-8")
    tags = re.search(r"^TAGS = \[(.*?)\]", source, re.M | re.S)
    assert tags and '"wcag22aa"' in tags.group(1)
    assert not re.search(r"^(?!\s*#).*importorskip\(", source, re.M)
    assert re.search(r"def axe_module\(browser\):.*?pytest\.fail\(", source, re.S)
    assert '"target-size": "wcag22aa"' in source
    assert '("solution_architect", "/intelligence/ask")' in source
    assert '("enterprise_architect", "/intelligence/twin-map")' in source
    baseline = (REPO_ROOT / "tests" / "smoke" / "a11y_baseline.json").read_text(encoding="utf-8")
    assert "/intelligence/" not in baseline


# --- a model that has gone out of date; what a worked-out row is called ------------


def test_worked_out_connections_are_asked_for_together_with_out_of_date_ones():
    """Wherever the pages ask for worked-out connections they ask for the ones that
    have gone out of date too; without that the answer leaves them out and only its
    summary says so."""
    core = _code(_scripts()["core.js"])
    request = re.search(r"Platform\.fetch\.get\(IMPACT_URL \+ elementId, (\{.*?\})", core, re.S)
    assert request, "the impact request was not found"
    assert re.search(r"include_derived:\s*options\.includeDerived", request.group(1))
    assert re.search(r"include_stale:\s*options\.includeDerived", request.group(1))
    # Both pages go through that one request.
    for name in ("ask.js", "twin_map.js"):
        assert "Intelligence.fetchImpact(" in _code(_scripts()[name]), name


def test_an_out_of_date_answer_gets_a_notice_that_is_text_and_a_clock_with_the_action():
    states = _templates()["_impact_states.html"]
    notice = re.search(r"<div x-show=\"stale\"[^>]*data-stale-notice.*?</div>\s*(?=\{% endmacro|<div|$)", states, re.S)
    assert notice, "the out-of-date notice is missing"
    assert 'role="status"' in notice.group(0)
    assert 'data-lucide="clock"' in notice.group(0)
    assert 'x-text="staleNotice"' in notice.group(0)
    # The same action as the not-worked-out state, from one definition.
    assert len(re.findall(r"\{\{ recompute_action\(\) \}\}", states)) == 2
    assert len(re.findall(r"Work them out now", states)) == 1
    for name in ("ask.js", "twin_map.js"):
        source = _code(_scripts()[name])
        assert "answerState(" in source and "this.stale = answer.stale" in source, name


def test_the_row_kind_in_the_drawer_title_is_true_of_the_row_and_adds_no_badge_kind():
    drawer = _code(_scripts()["drawer.js"])
    assert re.search(r"drawer\.kind = row\.name === null \? 'missing' : \(row\.derived \? 'derived' : 'measured'\)", drawer)
    title = _templates()["_provenance_drawer.html"]
    assert re.search(r"drawer\.kind === 'derived'.*?data-lucide=\"waypoints\".*?>Worked out</span>", title, re.S)
    # The title words for a worked-out row are plain markup; the provenance badge
    # macro is only ever called with the four kinds it already has.
    kinds = set()
    for name, source in _templates().items():
        kinds.update(re.findall(r"provenance_badge\('([a-z]+)'\)", source))
    assert kinds <= {"measured", "missing", "unavailable"}, kinds
    assert "provenance_badge('derived')" not in title


def test_the_map_badge_and_table_say_when_a_worked_out_connection_may_be_out_of_date():
    graph = _code(_scripts()["graph.js"])
    assert "WORKED_OUT_STALE" in graph and "GLYPH_CLOCK" in graph
    core = _code(_scripts()["core.js"])
    assert "var WORKED_OUT_STALE = 'Worked out, may be out of date';" in core
    table = _templates()["_map_table.html"]
    assert "stale_clock('row.stale')" in table and 'x-text="row.kindLabel"' in table


def test_the_status_region_reads_results_for_a_search_and_connections_for_a_choice():
    core = _code(_scripts()["core.js"])
    assert "' result' : ' results'" in core
    assert "' connection' : ' connections'" in core
    assert "resultsText(this.options.length, typed)" in _code(_scripts()["picker.js"])
    for name in ("ask.js", "twin_map.js"):
        source = _code(_scripts()[name])
        assert "connectionsText(" in source, name
        assert "results for" not in source, name


def test_the_side_panel_control_is_named_for_the_panel():
    twin = _templates()["twin_map.html"]
    assert re.search(r'id="twin-rail-toggle".*?Selected element\s*</button>', twin, re.S)
    assert 'aria-label="Selected element"' in twin
    assert ">Details<" not in twin and "Details</button>" not in twin


# =============================================================================
# Worked-out connections: the third page of this blueprint.
#
# The page is a shell that asks the yield endpoint for its figures, so what these
# tests read is the shell as served, the script as shipped, and the rules the
# page keeps for every render: one label, no banned word, one disclosure control,
# one guarded link to the drift page and nothing of that page's own, no sidebar
# entry, nothing under the drift page's address.
# =============================================================================

WORKED_OUT_PATH = "/intelligence/worked-out-connections"
LABEL = "Worked-out connections"

BANNED_WORDS = re.compile(r"\b(?:yield|health)\b", re.I)
INTERNAL_SHAPES = re.compile(
    r"\b(?:archie_[a-z_]+|[a-z_]+_seconds|intelligence_derivation_runs|archimate_derived_relationships)\b"
)


def _strip_full_detail_region(html: str) -> str:
    """The page with the content of its one disclosure region taken out."""
    start = re.search(r"<div [^>]*data-full-detail-region[^>]*>", html)
    if not start:
        return html
    depth, position = 1, start.end()
    for token in re.finditer(r"<div\b|</div>", html[position:]):
        depth += 1 if token.group(0) == "<div" else -1
        if depth == 0:
            return html[: start.end()] + html[position + token.start():]
    raise AssertionError("the disclosure region never closes")


def _readable_strings(source: str) -> list[str]:
    strings = re.findall(r"'([^'\n]{3,})'", source) + re.findall(r'"([^"\n]{3,})"', source)
    return [s for s in strings if " " in s or s[:1].isupper()]


def _worked_out_page(client, login_as, user):
    login_as(client, user)
    response = client.get(WORKED_OUT_PATH)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_the_third_page_renders_for_a_signed_in_user_with_its_own_template(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-render")
    user = _user(db_session, org.id)
    seen, stop = _rendered_templates(app)
    try:
        login_as(client, user)
        response = client.get(WORKED_OUT_PATH)
    finally:
        stop()
    assert response.status_code == 200
    assert "intelligence/worked_out_connections.html" in seen


def test_the_third_page_is_not_served_to_an_anonymous_visitor(app, client):
    response = client.get(WORKED_OUT_PATH)
    assert response.status_code in (301, 302, 401)
    if response.status_code in (301, 302):
        assert "/account/login" in response.headers["Location"]


def test_the_third_page_is_one_get_route_of_the_existing_blueprint(app):
    rules = [r for r in app.url_map.iter_rules() if r.rule == WORKED_OUT_PATH]
    assert [(r.endpoint, sorted(r.methods - {"HEAD", "OPTIONS"})) for r in rules] == [
        ("intelligence_ui.worked_out_connections", ["GET"])
    ]
    assert WORKED_OUT_PATH.count("/") == 2, "two path segments: not a module root"
    blueprints = {r.endpoint.split(".")[0] for r in app.url_map.iter_rules() if r.rule.startswith("/intelligence")}
    assert blueprints == {"intelligence_ui"}


def test_the_title_and_the_breadcrumb_leaf_are_the_label_and_nothing_else(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-label")
    user = _user(db_session, org.id)
    html = _worked_out_page(client, login_as, user)
    assert f'<h1 class="text-2xl font-bold text-foreground">{LABEL}</h1>' in html
    assert re.search(r'<title>\s*' + re.escape(LABEL) + r'\b', html)
    crumbs = re.search(r'<nav aria-label="Breadcrumb".*?</nav>', html, re.S).group(0)
    assert re.findall(r'<li[^>]*aria-current="page"[^>]*>\s*<span[^>]*>([^<]+)</span>', crumbs) == [LABEL]
    assert "p-6 space-y-6" in html
    assert "container mx-auto" not in _main_html(html)


def test_the_subtitle_and_the_fixed_strings_are_the_specified_ones(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-strings")
    user = _user(db_session, org.id)
    text = _visible_text(_main_html(_worked_out_page(client, login_as, user)))
    for wanted in (
        "How much of your business we have worked out for you, and how fresh it is.",
        "Explicit facts", "Worked-out facts", "Ratio", "Stale count", "Last worked out", "Response time",
        "We don't set a target for this yet — this is the first real measurement, not a borrowed benchmark.",
        "Work them out now", "See drift findings and fixes", "We could not answer that just now.",
        "Full detail",
    ):
        assert wanted in text, wanted


def test_neither_banned_word_is_on_the_page_or_in_the_words_the_script_writes(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-banned")
    user = _user(db_session, org.id)
    html = _strip_full_detail_region(_main_html(_worked_out_page(client, login_as, user)))
    text = _visible_text(html)
    assert text
    assert BANNED_WORDS.findall(text) == []
    script = _scripts()["worked_out_connections.js"]
    written = [s for s in _readable_strings(_code(script)) if not s.startswith("/api/")]
    assert written
    assert [s for s in written if BANNED_WORDS.search(s)] == []
    template = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    assert BANNED_WORDS.findall(_visible_text(re.sub(r"\{[{%].*?[%}]\}", "", template, flags=re.S))) == []


def test_the_copy_carries_no_status_label_path_id_or_metric_name(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-copy")
    user = _user(db_session, org.id)
    html = _strip_full_detail_region(_main_html(_worked_out_page(client, login_as, user)))
    text = _visible_text(html)
    assert text
    assert STATUS_LABELS.findall(text) == []
    assert FORBIDDEN_SHAPES.findall(text) == []
    assert INTERNAL_SHAPES.findall(text) == []
    for name in ("worked_out_connections.js",):
        written = [s for s in _readable_strings(_code(_scripts()[name])) if not s.startswith("/api/")]
        for line in written:
            assert not STATUS_LABELS.search(line), line
            assert not FORBIDDEN_SHAPES.search(line), line
    # The technical terms live in the disclosure's rows and nowhere else on the page.
    for internal in ("cross_layer_impact", "include_derived", "Engine version", "1.0.0"):
        assert internal not in text


def test_no_card_is_bound_through_the_value_slot_that_falls_back_to_a_zero(
    app, db_session, make_org, client, login_as
):
    source = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    assert "value_alpine" not in source
    html = _main_html(_worked_out_page(client, login_as, _user(db_session, make_org("wc-zero").id)))
    assert not re.search(r">\s*0\s*<", html), "the served page holds a bare zero"
    assert "0" not in _visible_text(html).split(), "no visible zero in the served page"


def test_six_figures_each_a_figure_with_a_caption_and_one_named_value(
    app, db_session, make_org, client, login_as
):
    org = make_org("wc-figures")
    html = _main_html(_worked_out_page(client, login_as, _user(db_session, org.id)))
    figures = re.findall(r"<figure [^>]*data-metric=\"(\w+)\"[^>]*>\s*<figcaption[^>]*>([^<]+)</figcaption>", html)
    assert figures == [
        ("explicit", "Explicit facts"), ("derived", "Worked-out facts"), ("ratio", "Ratio"),
        ("stale", "Stale count"), ("workedOutAt", "Last worked out"), ("response", "Response time"),
    ]
    values = re.findall(r'<div role="img" :aria-label="cards\.(\w+)\.name" data-testid="value-(\w+)"', html)
    assert [k for k, _ in values] == [k for k, _ in figures] and all(a == b for a, b in values)


def test_the_page_is_built_from_the_named_macros(app):
    source = _templates()["worked_out_connections.html"]
    for line in (
        "{% from 'macros/page_shell.html' import page_shell %}",
        "{% from 'components/metrics_card.html' import metrics_card %}",
        "{% from 'components/skeleton.html' import skeleton_card, skeleton_text %}",
        "{% from 'components/provenance.html' import provenance_badge %}",
        "{% from 'intelligence/_full_detail.html' import full_detail with context %}",
    ):
        assert line in source
    assert "{% extends 'layouts/admin_base.html' %}" in source
    assert "from 'macros/page_shell.html' import empty_state" not in source
    assert "animate-spin" not in source and "<svg" not in source
    assert "onclick=" not in source and "container mx-auto" not in source
    for state in (
        "provenance_badge('unavailable')", "provenance_badge('missing')", "skeleton_card()",
        "skeleton_text(lines=2)",
    ):
        assert state in source


def test_the_one_disclosure_control_is_the_shared_macro_and_no_other_affordance_exists(app):
    source = _templates()["worked_out_connections.html"]
    assert len(re.findall(r"\{%\s*call\s+full_detail\(", source)) == 1
    assert not re.findall(r"\{\{\s*full_detail\(", source), "the macro is called once, as a call block"
    for banned in (
        r"<details", r"<summary", r'role="tab', r'role="dialog"', r"aria-haspopup", r"aria-expanded",
        r"x-collapse", r"Show more", r"Show less", r"See more", r"Read more", r"Advanced", r"Expand all",
    ):
        assert not re.search(banned, source, re.I), banned
    macro = _templates()["_full_detail.html"]
    assert len(re.findall(r"data-full-detail-toggle", macro)) == 1


def test_the_full_detail_macro_still_renders_a_connections_detail_when_called_the_old_way(app):
    """The content slot changed nothing for the three surfaces that read a connection."""
    macro = _templates()["_full_detail.html"]
    assert re.search(r"\{%\s*if caller\s*%\}\s*\{\{\s*caller\(\)\s*\}\}\s*\{%\s*else\s*%\}\s*<dl", macro)
    for label in ("ArchiMate type", "Layer", "Depth", "Chain", "Rule", "Confidence", "Worked out at",
                  "Engine version", "Derived record"):
        assert f">{label}</dt>" in macro, label


def test_the_detail_lives_in_the_disclosure_and_the_script_only(app):
    source = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    inside = re.search(r"\{%\s*call full_detail.*?\{%\s*endcall\s*%\}", source, re.S).group(0)
    outside = source.replace(inside, "")
    for term in ("Engine version", "Worked out at", "Response time, 95th percentile", "Response time, measured from",
                 "cross_layer_impact", "include_derived", "1.0.0", "computed_at", "engine_version",
                 "p95_latency_seconds"):
        assert term not in outside, term
    script = _scripts()["worked_out_connections.js"]
    for term in ("Engine version", "Worked out at", "Response time, 95th percentile", "Response time, measured from"):
        assert term in script
    assert "Response time, exact" not in script, "the exact-figure row is gone: its number is in the first row"


def test_the_drift_row_is_a_count_and_one_guarded_link_and_no_second_list(
    app, db_session, make_org, client, login_as
):
    source = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    assert len(re.findall(r"url_for\('genome_drift\.index'\)", source)) == 1
    assert "{% if 'genome_drift.index' in flask.current_app.view_functions %}" in source
    guarded = re.search(
        r"\{% if 'genome_drift\.index' in flask\.current_app\.view_functions %\}(.*?)\{% endif %\}", source, re.S
    ).group(1)
    assert "url_for('genome_drift.index')" in guarded and "drift.text" in guarded
    for finding_shape in ("<table", "<ul", "<ol", "<li", "severity", "by_type", "findings", "fix", "Fix", "<form",
                          "genome_drift.", "/genome/"):
        pool = (
            source.replace("url_for('genome_drift.index')", "")
            .replace("'genome_drift.index'", "")
            .replace("See drift findings and fixes", "")
        )
        assert finding_shape not in pool, finding_shape
    script = _scripts()["worked_out_connections.js"]
    for shape in ("severity", "by_type", "spec_hash", "signals"):
        assert shape not in script, shape
    assert not re.search(r"\.findings\b|['\"]findings['\"]", script), "the script never reads a list of findings"
    assert "drift_finding_count" in script
    html = _main_html(_worked_out_page(client, login_as, _user(db_session, make_org("wc-drift").id)))
    assert html.count('href="/genome/model-health/"') == 1
    assert len(re.findall(r"<a [^>]*href=\"/genome/", html)) == 1


def test_without_the_drift_page_the_row_and_its_link_are_both_omitted(
    app, db_session, make_org, client, login_as, monkeypatch
):
    monkeypatch.delitem(app.view_functions, "genome_drift.index")
    org = make_org("wc-no-drift")
    html = _main_html(_worked_out_page(client, login_as, _user(db_session, org.id)))
    assert "See drift findings and fixes" not in html
    assert "/genome/" not in html
    assert "drift-row" not in html
    assert LABEL in html


def test_the_header_action_is_on_ask_and_on_twin_map_and_guarded(
    app, db_session, make_org, client, login_as, monkeypatch
):
    org = make_org("wc-actions")
    user = _user(db_session, org.id)
    for path in PAGES:
        login_as(client, user)
        html = _main_html(client.get(path).get_data(as_text=True))
        links = re.findall(r'<a href="' + re.escape(WORKED_OUT_PATH) + r'"[^>]*>(.*?)</a>', html, re.S)
        assert len(links) == 1, path
        assert _visible_text(links[0]) == LABEL
    monkeypatch.delitem(app.view_functions, "intelligence_ui.worked_out_connections")
    for path in PAGES:
        login_as(client, user)
        response = client.get(path)
        assert response.status_code == 200
        assert WORKED_OUT_PATH not in response.get_data(as_text=True)


def test_ask_and_twin_map_gained_one_header_action_each_and_nothing_else(app):
    for name in ("ask.html", "twin_map.html"):
        source = _templates()[name]
        assert source.count("intelligence_ui.worked_out_connections") == 2, name  # the guard and the link
        assert source.count("Worked-out connections") == 1, name


def test_the_screen_has_no_sidebar_link_and_no_directory_row(app):
    """The label, the route, the endpoint and the script appear in the intelligence
    module and nowhere else in the product. The label is searched as a title or a
    quoted string (prose that mentions worked-out connections is not a label)."""
    allowed = {
        "app/modules/intelligence/routes/ui.py",
        "app/modules/intelligence/templates/intelligence/ask.html",
        "app/modules/intelligence/templates/intelligence/twin_map.html",
        "app/modules/intelligence/templates/intelligence/worked_out_connections.html",
        "app/static/js/intelligence/worked_out_connections.js",
    }
    needles = re.compile(
        r"worked-out-connections|worked_out_connections|workedOutConnections"
        r"|(?:>|['\"])\s*Worked-out connections\s*(?:<|['\"])"
    )
    found = set()
    for path in (REPO_ROOT / "app").rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".html", ".js", ".json", ".yml", ".yaml", ".md", ".txt"}:
            continue
        if "tests" in path.parts or "node_modules" in path.parts or "vendor" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needles.search(text):
            found.add(path.relative_to(REPO_ROOT).as_posix())
    assert found <= allowed, sorted(found - allowed)
    assert not [p for p in found if "sidebar" in p or "modules_directory" in p or "role_access" in p]


def test_nothing_this_screen_added_sits_under_the_drift_pages_address_or_name(app):
    module = REPO_ROOT / "app" / "modules" / "intelligence"
    for path in module.rglob("*"):
        assert "model_health" not in path.name and "drift" not in path.name.lower(), path
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("intelligence_"):
            assert not rule.rule.startswith("/genome"), rule
            assert "model-health" not in rule.rule and "drift" not in rule.rule, rule
    assert not [b for b in app.blueprints if b.startswith("intelligence") and ("drift" in b or "model_health" in b)]
    assert (
        app.view_functions["intelligence_ui.worked_out_connections"].__module__
        == "app.modules.intelligence.routes.ui"
    )
    assert "genome" not in inspect.getsource(sys.modules["app.modules.intelligence.routes.ui"])


def test_the_script_is_a_top_level_factory_that_reads_through_platform_fetch(app):
    script = _scripts()["worked_out_connections.js"]
    code = _code(script)
    assert "window.workedOutConnections = workedOutConnections;" in script
    assert "Alpine.data(" not in code
    assert 'x-data="workedOutConnections()"' in _templates()["worked_out_connections.html"]
    assert "Platform.fetch.get(YIELD_URL" in code
    assert "'/api/v1/intelligence/yield'" in code
    assert "Intelligence.recompute()" in code
    assert not re.search(r"(?<![.\w])fetch\(", code) and "console." not in code
    assert "toFixed" not in code and "Math.round" not in code


def test_the_recalculation_asks_for_the_callers_own_tenant_and_only_that():
    core = _code(_scripts()["core.js"])
    assert "Platform.fetch.post(RECOMPUTE_URL, { scope: 'tenant' }" in core
    assert "RECOMPUTE_URL = '/api/v1/intelligence/derivation/recompute'" in core


def test_the_status_region_is_polite_and_holds_the_notice_and_its_button(app):
    source = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    region = re.search(r'<div role="status" aria-live="polite"[^>]*data-testid="derivation-status"[^>]*>(.*?)\n    </div>\n\n', source, re.S)
    assert region, "the polite status region is missing"
    assert "data-recompute-button" in region.group(1) and "Work them out now" in region.group(1)
    assert 'x-text="statusLine"' in region.group(1)
    assert "aria-disabled" in region.group(1), "the button keeps keyboard focus while it works"
    assert ":disabled" not in region.group(1)


def test_a_percent_sign_or_progress_element_or_verdict_word_is_never_on_the_page(
    app, db_session, make_org, client, login_as
):
    source = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    for shape in ("<progress", "<meter", 'role="progressbar"', "aria-valuenow", "bg-success", "bg-destructive",
                  "text-success", "text-destructive", "text-warning"):
        assert shape not in source, shape
    script = _code(_scripts()["worked_out_connections.js"])
    for word in ("good", "bad", "healthy", "excellent", "poor", "on track", "behind", "target"):
        assert not re.search(r"\b" + word + r"\b", script, re.I), word
    assert "%" not in "".join(_readable_strings(script))


# --- the second question, the row's states, and the action in the out-of-date state ---


def _method(code: str, name: str) -> str:
    """The body of one method of the page's component object (they sit at one indent)."""
    match = re.search(r"\n        (?:async )?" + re.escape(name) + r"\([^)]*\) \{\n(.*?)\n        \}(?:,|\n)", code, re.S)
    assert match, f"method {name} not found"
    return match.group(1)


def _function_body(code: str, name: str) -> str:
    match = re.search(r"\n    function " + re.escape(name) + r"\([^)]*\) \{\n(.*?)\n    \}\n", code, re.S)
    assert match, f"function {name} not found"
    return match.group(1)


def test_the_figures_and_the_model_check_are_two_named_questions_asked_in_that_order():
    code = _code(_scripts()["worked_out_connections.js"])
    assert len(re.findall(r"Platform\.fetch\.get\(YIELD_URL", code)) == 2
    assert code.count("{ part: 'figures' }") == 1 and code.count("{ part: 'model-check' }") == 1
    assert "{ part: 'model-check' }" in _method(code, "checkModel")
    assert "{ part: 'figures' }" in _method(code, "load")
    load = _method(code, "load")
    assert re.search(r"if \(!refresh && self\.loaded\)", load), "asked after the first read only, and only if it drew"
    assert "self.checkModel()" in load and "window.setTimeout(" in load
    assert "checkModel" not in _method(code, "recomputeNow") and "checkModel" not in _method(code, "apply")


def test_the_figures_answer_never_writes_the_drift_row_and_a_recalculation_leaves_it_alone():
    code = _code(_scripts()["worked_out_connections.js"])
    assert "drift" not in _method(code, "apply"), "the figures answer carries no drift count to show"
    assert "drift" not in _method(code, "recomputeNow"), "the row keeps the value it has"
    assert _method(code, "checkModel").count("this.drift =") == 3, "loading, the answer, or could not check"
    assert len(re.findall(r"this\.drift =", code)) == 3, "the row is written by the model check alone"


def test_the_model_check_is_asked_once_and_only_when_its_row_is_on_the_page():
    code = _code(_scripts()["worked_out_connections.js"])
    body = _method(code, "checkModel")
    assert "this.modelChecked" in body and "!this.$refs.driftRow" in body
    template = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    guarded = re.search(
        r"\{% if 'genome_drift\.index' in flask\.current_app\.view_functions %\}(.*?)\{% endif %\}", template, re.S
    ).group(1)
    assert 'x-ref="driftRow"' in guarded and template.count('x-ref="driftRow"') == 1


def test_only_a_whole_number_is_a_count_and_the_row_has_exactly_four_states():
    code = _code(_scripts()["worked_out_connections.js"])
    assert re.search(r"function isWholeCount\(value\) \{\s*return isCount\(value\) && Math\.floor\(value\) === value && value >= 0;", code)
    body = _function_body(code, "driftFrom")
    assert body.index("isWholeCount(data.drift_finding_count)") < body.index("too_large") < body.index("unavailableDrift()")
    assert "'counted'" in body and "data.drift_finding_count === null" in body
    states = set(re.findall(r"state: '(\w+)'", code))
    assert states == {"loading", "counted", "too_large", "unavailable"}, states
    template = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    assert "drift.state === 'loading'" in template and "drift.state === 'unavailable'" in template
    assert 'x-show="drift.linked"' in template
    assert "skeleton_text(lines=2)" in template.split("data-testid=\"drift-row\"")[1]


def test_the_out_of_date_state_offers_the_same_recalculation_action_as_the_not_worked_out_state():
    code = _code(_scripts()["worked_out_connections.js"])
    assert "this.showRecompute = notWorkedOut || outOfDate;" in _method(code, "apply")
    template = re.sub(r"\{#.*?#\}", "", _templates()["worked_out_connections.html"], flags=re.S)
    region = re.search(r'<div role="status" aria-live="polite"[^>]*data-testid="derivation-status"[^>]*>(.*?)\n    </div>\n\n', template, re.S).group(1)
    assert "stale_line('staleLine')" in region, "the out-of-date line and its action share the polite region"
    assert region.index("stale_line('staleLine')") < region.index("data-recompute-button")
    assert region.count("data-recompute-button") == 1, "one button for both states"
    ask = _templates()["_impact_states.html"]
    assert "data-stale-notice" in ask and "recompute_action()" in ask.split("data-stale-notice")[1]


def test_the_response_time_card_is_chosen_by_the_answers_reason_never_by_a_null_figure():
    code = _code(_scripts()["worked_out_connections.js"])
    body = _function_body(code, "responseReading")
    assert body.count("'notEnough'") == 1
    assert re.search(
        r"if \(hasReason\(data, 'insufficient_samples_for_p95'\)\) return \{ kind: 'notEnough'", body
    ), "the not-enough card is chosen by its reason code alone"
    assert body.index("'measured'") < body.index("'above'") < body.index("'notEnough'") < body.rindex("'absent'")
    assert not re.search(r"p95_latency_seconds\s*(===|==)\s*null|!\s*isCount\(data\.p95_latency_seconds\)", body)


def test_the_time_the_last_run_finished_never_stands_in_for_the_time_it_was_worked_out():
    code = _code(_scripts()["worked_out_connections.js"])
    assert "last_run_at" not in code
    assert not re.search(r"computed_at\s*\|\|", code)
    assert "'Worked out at'" in code


def test_the_copy_guards_check_status_labels_shapes_and_the_two_banned_words_and_nothing_else():
    """The guards in this file and in the browser journey are pinned to what they are for: status-label
    words, file, path, hash and identifier shapes, and the two words this screen never uses. A guard
    that grows a list of other vocabulary would carry that vocabulary in the repository."""
    import ast

    def _patterns(path):
        found = {}
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "re.compile"
            ):
                found[node.targets[0].id] = "".join(
                    part.value for part in ast.walk(node.value.args[0]) if isinstance(part, ast.Constant)
                )
        return found

    here = _patterns(Path(__file__))
    journey = _patterns(REPO_ROOT / "tests" / "smoke" / "test_intelligence_us5_journey.py")
    status_labels = r"\b(?:VERIFIED|UNVERIFIED|TBC|TODO)\b|(?i:to be confirmed)"
    banned = r"\b(?:yield|health)\b"

    assert here["STATUS_LABELS"] == status_labels and journey["STATUS_LABELS"] == status_labels
    assert here["BANNED_WORDS"] == banned and journey["BANNED"] == banned
    assert set(here) >= {"FORBIDDEN_SHAPES", "INTERNAL_SHAPES"} and "SHAPES" in journey
    assert not set(here) & {"INTERNAL_WORDS", "INTERNAL"} and not set(journey) & {"INTERNAL_WORDS", "INTERNAL"}

    # ...and each guard is live: it finds what it is for.
    assert STATUS_LABELS.search("Status: TBC") and STATUS_LABELS.search("to be confirmed")
    assert BANNED_WORDS.search("Yield") and BANNED_WORDS.search("Model health")
    assert FORBIDDEN_SHAPES.search("see app/x.py") and FORBIDDEN_SHAPES.search("a1b2c3d4e5f6")
    assert INTERNAL_SHAPES.search("archie_intelligence_query_seconds")
