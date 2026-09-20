"""The `crosswalk-writer-gated` gate must actually fire on a genuinely
ungated write, and must not false-positive on a genuinely gated one.

A must-be-zero gate that cannot go red is theatre. This pins the real
behaviour with fake files on disk (via ``tmp_path``), not just a narrated
manual proof procedure: a positive control (ungated write -> 1 finding), a
negative control (directly gated write -> 0 findings), and the
"public method gates, private method writes" shape -> 0 findings.
"""
from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECKER = _REPO_ROOT / "scripts" / "check_crosswalk_writer_gated.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_crosswalk_writer_gated", _CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ungated_write_is_flagged(tmp_path):
    """Positive control: a real writer with no gate call anywhere on its
    path must be reported."""
    mod = _load_checker()
    src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk

        def write_crosswalk_row(connector_type, external_id, element_id):
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()
        """
    )
    f = tmp_path / "ungated_writer.py"
    f.write_text(src, encoding="utf-8")

    findings = mod.scan_file(str(f))

    assert len(findings) == 1
    assert findings[0][1] == "write_crosswalk_row"


def test_gate_name_in_docstring_or_comment_does_not_satisfy_the_check(tmp_path):
    """Regression: the gate's name appearing only in a docstring/comment
    (never as a real call) must not suppress the finding."""
    mod = _load_checker()
    src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk

        def write_crosswalk_row(connector_type, external_id, element_id):
            \"\"\"assert_connector_permitted is enforced by the caller.\"\"\"
            # assert_connector_permitted(connector_type)
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()
        """
    )
    f = tmp_path / "fake_gate_mention.py"
    f.write_text(src, encoding="utf-8")

    findings = mod.scan_file(str(f))

    assert len(findings) == 1
    assert findings[0][1] == "write_crosswalk_row"


def test_directly_gated_write_is_not_flagged(tmp_path):
    """Negative control: a real call to the gate in the same function body
    must suppress the finding."""
    mod = _load_checker()
    src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk
        from app.modules.intelligence.services.connector_allowlist import (
            assert_connector_permitted,
        )

        def write_crosswalk_row(connector_type, external_id, element_id):
            assert_connector_permitted(connector_type)
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()
        """
    )
    f = tmp_path / "gated_writer.py"
    f.write_text(src, encoding="utf-8")

    findings = mod.scan_file(str(f))

    assert findings == []


def test_caller_gates_then_delegates_to_private_writer_is_not_flagged(tmp_path):
    """A public method calls the gate, then delegates the actual write
    to a private same-file helper method (`self.foo(...)`, an attribute
    call). The helper itself has no direct gate call, but every same-file
    caller of it gates before calling it, so it must not be flagged."""
    mod = _load_checker()
    src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk
        from app.modules.intelligence.services.connector_allowlist import (
            assert_connector_permitted,
        )

        class CrosswalkService:
            def resolve(self, connector_type, external_id, element_id):
                assert_connector_permitted(connector_type)
                self._write_crosswalk_row(external_id, element_id)

            def _write_crosswalk_row(self, external_id, element_id):
                db.session.add(
                    ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
                )
                db.session.commit()
        """
    )
    f = tmp_path / "delegated_writer.py"
    f.write_text(src, encoding="utf-8")

    findings = mod.scan_file(str(f))

    assert findings == []


def test_private_writer_with_an_ungated_caller_is_still_flagged(tmp_path):
    """The caller check must not become a blanket pass: if ANY same-file
    caller of the writer helper fails to gate first, the helper is still
    reported."""
    mod = _load_checker()
    src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk
        from app.modules.intelligence.services.connector_allowlist import (
            assert_connector_permitted,
        )

        class CrosswalkService:
            def resolve_carefully(self, connector_type, external_id, element_id):
                assert_connector_permitted(connector_type)
                self._write_crosswalk_row(external_id, element_id)

            def resolve_carelessly(self, external_id, element_id):
                self._write_crosswalk_row(external_id, element_id)

            def _write_crosswalk_row(self, external_id, element_id):
                db.session.add(
                    ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
                )
                db.session.commit()
        """
    )
    f = tmp_path / "one_ungated_caller.py"
    f.write_text(src, encoding="utf-8")

    findings = mod.scan_file(str(f))

    assert len(findings) == 1
    assert findings[0][1] == "_write_crosswalk_row"


def test_per_line_escape_hatch_requires_a_reason_and_only_suppresses_its_own_finding(tmp_path):
    """A bare marker with no reason must not suppress anything; a
    marker with a reason on the flagged function's def line (or the line
    above) suppresses only that finding, not the whole file."""
    mod = _load_checker()

    bare_marker_src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk

        def write_crosswalk_row(connector_type, external_id, element_id):  # crosswalk-gate-ok
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()
        """
    )
    f_bare = tmp_path / "bare_marker.py"
    f_bare.write_text(bare_marker_src, encoding="utf-8")
    assert len(mod.scan_file(str(f_bare))) == 1

    reasoned_src = textwrap.dedent(
        """
        from app.extensions import db
        from app.models import ExternalIdentityCrosswalk

        # crosswalk-gate-ok: legacy backfill script, run once under manual review
        def write_crosswalk_row(connector_type, external_id, element_id):
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()

        def another_ungated_writer(connector_type, external_id, element_id):
            db.session.add(
                ExternalIdentityCrosswalk(external_id=external_id, element_id=element_id)
            )
            db.session.commit()
        """
    )
    f_reasoned = tmp_path / "reasoned_marker.py"
    f_reasoned.write_text(reasoned_src, encoding="utf-8")
    findings = mod.scan_file(str(f_reasoned))

    assert len(findings) == 1
    assert findings[0][1] == "another_ungated_writer"


def test_main_hard_fails_when_no_files_are_found(tmp_path, monkeypatch, capsys):
    """A scan finding zero files (e.g. run from the wrong directory) must
    exit non-zero and say so loudly, not report a silent clean pass."""
    mod = _load_checker()
    monkeypatch.chdir(tmp_path)  # no app/ tree here -> default_paths() finds nothing

    exit_code = mod.main([])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "no python files found" in captured.err.lower()
