"""The `wiring-rows` gate must actually fire on a real gap, and must not false-positive on a covered column.

Fake files on disk (via tmp_path), not a narrated manual proof: a positive control (an unregistered
fact-bearing column -> flagged), negative controls (a register row, and separately a not_intelligence entry,
suppress it), the escape hatch (on the column's own line and the line above, and its refusal to honour a
marker whose id is not registered), the family boundary, a class nested inside a function, a database-column-
name match, and a missing register exiting 2, not 0.
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECKER = _REPO_ROOT / "scripts" / "check_wiring_rows.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_wiring_rows", _CHECKER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass field resolution needs the module registered before exec
    spec.loader.exec_module(mod)
    return mod


def _write_register(tmp_path: Path, rows=None, not_intelligence=None, name: str = "register.yml") -> Path:
    data = {
        "schema_version": 1,
        "updated": "2026-09-23",
        "rows": rows or [],
        "not_intelligence": not_intelligence or [],
        "pipeline_rule": {"statement": "a fact-bearing column needs a row here"},
    }
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _write_model(root: Path, body: str, filename: str = "widget.py") -> Path:
    models = root / "app" / "models"
    models.mkdir(parents=True, exist_ok=True)
    p = models / filename
    p.write_text("from .. import db\n\n" + body, encoding="utf-8")
    return p


def _scan(mod, root: Path, register_path: Path):
    register, err = mod._load_register(register_path)
    assert register is not None, err
    return mod.scan(root, register)


WIDGET_BODY = textwrap.dedent(
    """\
    class Widget(db.Model):
        __tablename__ = "widgets"
        id = db.Column(db.Integer, primary_key=True)
        health_status = db.Column(db.String, nullable=True)
    """
)


# ---- (i) positive control

def test_unregistered_fact_bearing_column_is_flagged(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    register_path = _write_register(tmp_path)
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1
    assert findings[0].cls == "Widget" and findings[0].attr == "health_status"
    assert "Widget.health_status" in findings[0].render()


# ---- (ii) negative controls

def test_a_register_row_naming_the_class_and_field_suppresses_it(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    register_path = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "Widget", "fields": ["health_status"]}])
    assert _scan(mod, root, register_path) == []


def test_a_not_intelligence_entry_suppresses_it(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    register_path = _write_register(tmp_path, not_intelligence=[
        {"id": "IW-02", "fact": "n/a", "where": ["widget.py:3 Widget.health_status"], "reason": "test entry"},
    ])
    assert _scan(mod, root, register_path) == []


def test_a_row_naming_a_different_class_does_not_cover_this_one(tmp_path):
    """Refuter control: a row naming class Risk must not cover RiskEntityLink's columns -- exact,
    comma-split equality on `model`, never a substring match."""
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class RiskEntityLink(db.Model):
            __tablename__ = "risk_entity_links"
            id = db.Column(db.Integer, primary_key=True)
            risk_level = db.Column(db.String, nullable=True)
        """
    )
    _write_model(root, body, filename="risk_entity_link.py")
    register_path = _write_register(tmp_path, rows=[{"id": "IW-03", "model": "Risk", "fields": ["risk_level"]}])
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1 and findings[0].cls == "RiskEntityLink" and findings[0].attr == "risk_level"


# ---- (iii) escape hatch

def test_escape_hatch_on_the_columns_own_line(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = WIDGET_BODY.replace(
        "health_status = db.Column(db.String, nullable=True)",
        "health_status = db.Column(db.String, nullable=True)  # wiring-ok: IW-01 a real reason",
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "none", "fields": []}])
    assert _scan(mod, root, register_path) == []


def test_escape_hatch_on_the_line_above(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = WIDGET_BODY.replace(
        "health_status = db.Column(db.String, nullable=True)",
        "# wiring-ok: IW-01 a real reason\n    health_status = db.Column(db.String, nullable=True)",
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "none", "fields": []}])
    assert _scan(mod, root, register_path) == []


def test_escape_hatch_line_above_does_not_leak_to_the_next_column(tmp_path):
    """The line above counts only when it is not itself another column's own declaration -- the same rule
    check_unrendered_model_fields.py fixed a real bug on. A marker trailing one column's line must not also
    suppress the very next column."""
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            health_status = db.Column(db.String)  # wiring-ok: IW-01 a real reason
            risk_level = db.Column(db.String)
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "none", "fields": []}])
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1 and findings[0].attr == "risk_level"


def test_escape_marker_with_an_id_not_in_the_register_is_reported_not_honoured(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = WIDGET_BODY.replace(
        "health_status = db.Column(db.String, nullable=True)",
        "health_status = db.Column(db.String, nullable=True)  # wiring-ok: IW-99 a real reason",
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)  # IW-99 not registered
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1
    rendered = findings[0].render()
    assert "IW-99" in rendered and "no effect" in rendered


def test_escape_marker_with_no_reason_does_not_suppress(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = WIDGET_BODY.replace(
        "health_status = db.Column(db.String, nullable=True)",
        "health_status = db.Column(db.String, nullable=True)  # wiring-ok: IW-01",
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "none", "fields": []}])
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1


# ---- (iv) family boundary

def test_family_boundary(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            user_count = db.Column(db.Integer)
            description = db.Column(db.Text)
            eol_date = db.Column(db.Date)
            is_baseline = db.Column(db.Boolean)
            rto_hours = db.Column(db.Integer)
            owner_id = db.Column(db.Integer)
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)
    findings = _scan(mod, root, register_path)
    flagged = {f.attr for f in findings}
    assert flagged == {"eol_date", "is_baseline", "rto_hours", "owner_id"}
    assert "user_count" not in flagged and "description" not in flagged


# ---- (v) nested class inside a function

def test_nested_class_inside_a_function_is_scanned(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        def register_lazy_models():
            class Gadget(db.Model):
                __tablename__ = "gadgets"
                id = db.Column(db.Integer, primary_key=True)
                risk_level = db.Column(db.String)
            return Gadget
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1 and findings[0].cls == "Gadget" and findings[0].attr == "risk_level"


# ---- (vi) database column name

def test_database_column_name_covers_alongside_the_attribute_name(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            togaf_plateau = db.Column("plateau", db.String)
        """
    )
    _write_model(root, body)
    by_attr = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "Widget", "fields": ["togaf_plateau"]}],
                               name="by_attr.yml")
    assert _scan(mod, root, by_attr) == []
    by_dbcol = _write_register(tmp_path, rows=[{"id": "IW-01", "model": "Widget", "fields": ["plateau"]}],
                                name="by_dbcol.yml")
    assert _scan(mod, root, by_dbcol) == []


# ---- (vii) missing register

def test_missing_register_exits_2_not_0(tmp_path, monkeypatch, capsys):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    missing = tmp_path / "does-not-exist.yml"
    monkeypatch.setattr("sys.argv", ["check_wiring_rows.py", "--root", str(root), "--register", str(missing), "--count"])
    code = mod.main()
    assert code == 2
    out = capsys.readouterr()
    assert out.out.strip() == ""  # never a count of 0 -- nothing on stdout that could be read as one


def test_unparseable_register_exits_2(tmp_path, monkeypatch, capsys):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    bad = tmp_path / "bad.yml"
    bad.write_text("rows: [this is not: valid: yaml: at all\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_wiring_rows.py", "--root", str(root), "--register", str(bad), "--count"])
    code = mod.main()
    assert code == 2
    assert capsys.readouterr().out.strip() == ""


# ---- CLI-level sanity: --count matches len(scan())

def test_count_matches_the_number_of_findings(tmp_path, monkeypatch, capsys):
    mod = _load_checker()
    root = tmp_path / "tree"
    _write_model(root, WIDGET_BODY)
    register_path = _write_register(tmp_path)
    monkeypatch.setattr("sys.argv", ["check_wiring_rows.py", "--root", str(root), "--register", str(register_path), "--count"])
    code = mod.main()
    assert code == 0
    assert capsys.readouterr().out.strip() == "1"
