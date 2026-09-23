"""The `wiring-rows` gate must actually fire on a real gap, and must not false-positive on a covered column.

Fake files on disk (via tmp_path), not a narrated manual proof: a positive control (an unregistered
fact-bearing column -> flagged), negative controls (a register row, and separately a not_intelligence entry,
suppress it), the escape hatch (on the column's own line and the line above, and its refusal to honour a
marker whose id is not registered), the family boundary, a class nested inside a function, a database-column-
name match, and a missing register exiting 2, not 0.
"""
from __future__ import annotations

import importlib.util
import subprocess
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
    """Exactness control: a row naming class Risk must not cover RiskEntityLink's columns -- exact,
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


def test_a_not_intelligence_where_naming_a_longer_class_does_not_cover_a_shorter_one(tmp_path):
    """A not_intelligence where naming RiskEntityLink.risk_level must not cover Risk.risk_level -- whole-word
    matching on the class name, not a substring test (Risk is a substring of RiskEntityLink)."""
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Risk(db.Model):
            __tablename__ = "risks"
            id = db.Column(db.Integer, primary_key=True)
            risk_level = db.Column(db.String, nullable=True)
        """
    )
    _write_model(root, body, filename="risk.py")
    register_path = _write_register(tmp_path, not_intelligence=[
        {"id": "IW-04", "fact": "n/a",
         "where": ["app/models/links.py:10 RiskEntityLink.risk_level"], "reason": "test entry"},
    ])
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1 and findings[0].cls == "Risk" and findings[0].attr == "risk_level"


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


def test_escape_hatch_on_a_multi_line_declarations_closing_line(tmp_path):
    """A marker on the closing-paren line of a multi-line declaration suppresses that column, and does not
    leak onto the next column -- the declaration's own line range is `lineno..end_lineno`, not `lineno` alone."""
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            health_status = db.Column(
                db.String,
            )  # wiring-ok: IW-01 a real reason
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
            name = db.Column(db.String)
            status = db.Column(db.String)
            controller = db.Column(db.String)
            discount = db.Column(db.Integer)
            scorecard = db.Column(db.String)
            healthy = db.Column(db.Boolean)
            costume = db.Column(db.String)
            riskless = db.Column(db.Boolean)
            eol_date = db.Column(db.Date)
            is_baseline = db.Column(db.Boolean)
            rto_hours = db.Column(db.Integer)
            owner_id = db.Column(db.Integer)
            end_of_life_date = db.Column(db.Date)
            retired_at = db.Column(db.DateTime)
            last_assessed = db.Column(db.Date)
            key_risks = db.Column(db.Text)
            other_costs = db.Column(db.Numeric)
            critical_gaps = db.Column(db.Integer)
            unique_vendors = db.Column(db.Integer)
            ownership_type = db.Column(db.String)
            assessor = db.Column(db.String)
            gaps = db.Column(db.Text)
            licensing_model = db.Column(db.String)
            is_critical = db.Column(db.Boolean)
            gdpr_compliant = db.Column(db.Boolean)
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)
    findings = _scan(mod, root, register_path)
    flagged = {f.attr for f in findings}
    assert flagged == {
        "eol_date", "is_baseline", "rto_hours", "owner_id", "end_of_life_date", "retired_at",
        "last_assessed", "key_risks", "other_costs", "critical_gaps", "unique_vendors",
        "ownership_type", "assessor", "gaps", "licensing_model", "is_critical", "gdpr_compliant",
    }
    for unflagged in ("user_count", "description", "name", "status", "controller", "discount",
                      "scorecard", "healthy", "costume", "riskless"):
        assert unflagged not in flagged


# ---- (iv-b) the SQLAlchemy 2.0 annotated-assignment shape, and mixin columns staying unseen

def test_ann_assign_mapped_column_shape_is_flagged(tmp_path):
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            risk_level: Mapped[str] = mapped_column(sa.String)
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)
    findings = _scan(mod, root, register_path)
    assert len(findings) == 1 and findings[0].cls == "Widget" and findings[0].attr == "risk_level"


def test_mixin_column_is_not_seen(tmp_path):
    """Disclosed limit: a class with no Model base and no __tablename__ (a mixin) is not scanned."""
    mod = _load_checker()
    root = tmp_path / "tree"
    body = textwrap.dedent(
        """\
        class OwnerMixin:
            owner_id = db.Column(db.Integer)
        """
    )
    _write_model(root, body)
    register_path = _write_register(tmp_path)
    assert _scan(mod, root, register_path) == []


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


# ---- (viii) base diff

def _git(root, *args):
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_base_diff_names_a_column_added_alongside_a_deletion(tmp_path, monkeypatch, capsys):
    """A column that arrives with a deletion is invisible to the count ratchet (1 -> 1) but named by --base."""
    mod = _load_checker()
    root = tmp_path / "tree"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    body_v1 = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            is_baseline = db.Column(db.Boolean)
        """
    )
    _write_model(root, body_v1)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    body_v2 = textwrap.dedent(
        """\
        class Widget(db.Model):
            __tablename__ = "widgets"
            id = db.Column(db.Integer, primary_key=True)
            health_score = db.Column(db.Integer)
        """
    )
    _write_model(root, body_v2)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "second")

    register_path = _write_register(tmp_path)

    monkeypatch.setattr("sys.argv",
                         ["check_wiring_rows.py", "--root", str(root), "--register", str(register_path), "--count"])
    assert mod.main() == 0
    assert capsys.readouterr().out.strip() == "1"  # count unchanged: 1 -> 1

    monkeypatch.setattr("sys.argv",
                         ["check_wiring_rows.py", "--root", str(root), "--register", str(register_path),
                          "--base", "HEAD~1", "--count"])
    assert mod.main() == 1
    assert capsys.readouterr().out.strip() == "1"

    monkeypatch.setattr("sys.argv",
                         ["check_wiring_rows.py", "--root", str(root), "--register", str(register_path),
                          "--base", "HEAD~1"])
    assert mod.main() == 1
    assert "Widget.health_score" in capsys.readouterr().out


def test_base_diff_unresolvable_ref_exits_3_with_empty_stdout(tmp_path, monkeypatch, capsys):
    mod = _load_checker()
    root = tmp_path / "tree"
    root.mkdir()
    _git(root, "init", "-q")
    _write_model(root, WIDGET_BODY)
    register_path = _write_register(tmp_path)
    monkeypatch.setattr("sys.argv",
                         ["check_wiring_rows.py", "--root", str(root), "--register", str(register_path),
                          "--base", "does-not-exist"])
    code = mod.main()
    assert code == 3
    assert capsys.readouterr().out.strip() == ""
