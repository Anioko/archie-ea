"""The `unrendered-model-fields` gate must actually fire on a real gap, and
must not false-positive on a field that is genuinely rendered.

Fake files on disk (via tmp_path), not a narrated manual proof: a positive
control (a Text column never mentioned in its detail template -> flagged), a
negative control (a Text column the template does render -> not flagged),
and the escape-hatch marker (a flagged column carrying `unrendered-field-ok:
<reason>` -> suppressed).
"""
from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECKER = _REPO_ROOT / "scripts" / "check_unrendered_model_fields.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_unrendered_model_fields", _CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_model(app_dir: Path, body: str) -> None:
    """``body`` is one or more already-4-space-indented column lines -- kept
    separate from the surrounding dedent so mismatched indentation levels
    can't confuse textwrap.dedent's common-prefix calculation (it did once:
    a `class Widget(...)` line left with leftover indentation silently fails
    the checker's `^class\\s+` anchor, and the resulting false '[]' looked
    exactly like a checker bug rather than a fixture one)."""
    (app_dir / "models").mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        """\
        from .. import db

        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
        """
    )
    (app_dir / "models" / "widget.py").write_text(header + body + "\n", encoding="utf-8")


def _write_route(app_dir: Path, template_rel: str) -> Path:
    route_dir = app_dir / "routes_pkg"
    route_dir.mkdir(parents=True, exist_ok=True)
    route_path = route_dir / "routes.py"
    route_path.write_text(
        textwrap.dedent(
            f"""
            from flask import render_template
            from app.models.widget import Widget

            def view_widget(widget_id):
                widget = Widget.query.get_or_404(widget_id)
                return render_template("{template_rel}", widget=widget)
            """
        ),
        encoding="utf-8",
    )
    return route_path


def test_a_field_never_mentioned_in_the_template_is_flagged(tmp_path, monkeypatch):
    """Positive control."""
    app_dir = tmp_path / "app"
    _write_model(app_dir, '    notes = db.Column(db.Text, nullable=True)')
    template_dir = app_dir / "templates" / "widgets"
    template_dir.mkdir(parents=True)
    (template_dir / "detail.html").write_text("<h1>{{ widget.id }}</h1>", encoding="utf-8")
    route_path = _write_route(app_dir, "widgets/detail.html")

    mod = _load_checker()
    monkeypatch.setattr(mod, "APP", str(app_dir))
    findings = mod.scan_route_file(str(route_path))
    assert findings == [(str(route_path), "Widget", "widgets/detail.html", ["notes"])]


def test_a_field_the_template_renders_is_not_flagged(tmp_path, monkeypatch):
    """Negative control: same shape, but the template mentions the field."""
    app_dir = tmp_path / "app"
    _write_model(app_dir, '    notes = db.Column(db.Text, nullable=True)')
    template_dir = app_dir / "templates" / "widgets"
    template_dir.mkdir(parents=True)
    (template_dir / "detail.html").write_text(
        "<h1>{{ widget.id }}</h1><p>{{ widget.notes }}</p>", encoding="utf-8"
    )
    route_path = _write_route(app_dir, "widgets/detail.html")

    mod = _load_checker()
    monkeypatch.setattr(mod, "APP", str(app_dir))
    assert mod.scan_route_file(str(route_path)) == []


def test_a_nested_class_defined_later_in_the_file_is_not_attributed_to_the_scanned_model(
    tmp_path, monkeypatch
):
    """Regression control for a real bug found in production: a class nested
    inside a function (this codebase's fast-init lazy-model pattern) defined
    AFTER the scanned model in the same file must not have its own fields
    attributed to the outer model. ARBGovernanceStandard was reported as
    never rendering rationale/conditions -- those columns genuinely belong to
    Derogation, a class nested inside a factory function later in the same
    file, not to ARBGovernanceStandard at all."""
    app_dir = tmp_path / "app"
    _write_model(app_dir, '    notes = db.Column(db.Text, nullable=True)')
    # Append a nested class, mimicking the fast-init lazy-definition shape.
    widget_file = app_dir / "models" / "widget.py"
    widget_file.write_text(
        widget_file.read_text(encoding="utf-8")
        + textwrap.dedent(
            """

            def _register_lazy_models():
                class Gadget(db.Model):
                    __tablename__ = "gadgets"
                    id = db.Column(db.Integer, primary_key=True)
                    unrelated_field = db.Column(db.Text, nullable=True)
                return Gadget
            """
        ),
        encoding="utf-8",
    )
    template_dir = app_dir / "templates" / "widgets"
    template_dir.mkdir(parents=True)
    (template_dir / "detail.html").write_text(
        "<h1>{{ widget.id }}</h1><p>{{ widget.notes }}</p>", encoding="utf-8"
    )
    route_path = _write_route(app_dir, "widgets/detail.html")

    mod = _load_checker()
    monkeypatch.setattr(mod, "APP", str(app_dir))
    # notes is rendered -> not flagged. unrelated_field belongs to the nested
    # Gadget class, not Widget -> must not appear in Widget's findings at all.
    assert mod.scan_route_file(str(route_path)) == []


def test_escape_marker_suppresses_only_the_marked_field(tmp_path, monkeypatch):
    """A `unrendered-field-ok: <reason>` marker on the column's own line
    suppresses that field; a second, unmarked field in the same model still
    gets flagged."""
    app_dir = tmp_path / "app"
    _write_model(
        app_dir,
        '    notes = db.Column(db.Text, nullable=True)  # unrendered-field-ok: internal audit marker\n'
        '    summary = db.Column(db.Text, nullable=True)',
    )
    template_dir = app_dir / "templates" / "widgets"
    template_dir.mkdir(parents=True)
    (template_dir / "detail.html").write_text("<h1>{{ widget.id }}</h1>", encoding="utf-8")
    route_path = _write_route(app_dir, "widgets/detail.html")

    mod = _load_checker()
    monkeypatch.setattr(mod, "APP", str(app_dir))
    findings = mod.scan_route_file(str(route_path))
    assert findings == [(str(route_path), "Widget", "widgets/detail.html", ["summary"])]
