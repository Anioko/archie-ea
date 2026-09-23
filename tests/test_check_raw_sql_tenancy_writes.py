"""Rule 2 of scripts/check_raw_sql_tenancy.py: one backfill home.

A raw ``UPDATE <tenant table> ... SET organization_id`` anywhere in app/ or
scripts/ outside app/commands/backfill_layer_tenancy.py is a finding. The
dedicated commands that predate that one policy are the counted, falling
ratchet baseline, not an exemption from it.
"""

from __future__ import annotations

import os
import sys

from scripts.check_raw_sql_tenancy import (
    REPO_ROOT,
    _CANONICAL_BACKFILL,
    main,
    scan_file_writes,
    tenant_tables,
)


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _reset_tenant_tables_cache():
    """scripts/tenant_tables.txt is regenerated on disk as a side effect
    whenever tenant_tables() resolves the mapper registry live -- which
    running this process (or any earlier test in the same pytest session)
    already may have done, since the repo root is on sys.path here. Reset
    to the git-committed file before a subprocess measurement, so it
    depends on the committed cache the way a fresh checkout -- and the real
    gate, run as a subprocess with no prior in-process call to have
    regenerated it -- does, not on what happened to run immediately before
    it in this session.
    """
    import subprocess

    subprocess.run(
        ["git", "checkout", "--", "scripts/tenant_tables.txt"],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )


def test_catches_a_plain_update_on_a_tenant_table(tmp_path):
    tables = {"roadmap_tasks"}
    path = _write(
        tmp_path,
        "synthetic_plain.py",
        'from app import db\n'
        'from sqlalchemy import text\n\n'
        'db.session.execute(\n'
        '    text(\n'
        '        "UPDATE roadmap_tasks SET organization_id = 1 "\n'
        '        "WHERE organization_id IS NULL"\n'
        "    )\n"
        ")\n",
    )
    findings = scan_file_writes(path, tables)
    assert len(findings) == 1
    lineno, table, blob = findings[0]
    assert table == "roadmap_tasks"
    assert "SET organization_id" in blob


def test_catches_a_multiline_f_string_update(tmp_path):
    tables = {"roadmap_tasks"}
    path = _write(
        tmp_path,
        "synthetic_fstring.py",
        'from app import db\n'
        'from sqlalchemy import text\n\n'
        'org_id = 1\n'
        'db.session.execute(\n'
        '    text(\n'
        '        f"""\n'
        '        UPDATE roadmap_tasks t\n'
        '           SET organization_id = {org_id}\n'
        "         WHERE t.organization_id IS NULL\n"
        '        """\n'
        "    )\n"
        ")\n",
    )
    findings = scan_file_writes(path, tables)
    assert len(findings) == 1
    assert findings[0][1] == "roadmap_tasks"


def test_ignores_a_table_that_is_not_tenant_scoped(tmp_path):
    tables = {"roadmap_tasks"}  # deliberately excludes "widgets"
    path = _write(
        tmp_path,
        "synthetic_non_tenant.py",
        'from sqlalchemy import text\n\n'
        'stmt = text("UPDATE widgets SET organization_id = 1 WHERE organization_id IS NULL")\n',
    )
    assert scan_file_writes(path, tables) == []


def test_honours_a_marker_only_with_a_checkable_reason(tmp_path):
    tables = {"roadmap_tasks"}
    unqualified = _write(
        tmp_path,
        "synthetic_bare_marker.py",
        'from sqlalchemy import text\n\n'
        '# tenancy-ok: legacy, fine for now\n'
        'stmt = text("UPDATE roadmap_tasks SET organization_id = 1 WHERE organization_id IS NULL")\n',
    )
    assert len(scan_file_writes(unqualified, tables)) == 1

    qualified = _write(
        tmp_path,
        "synthetic_dated_marker.py",
        'from sqlalchemy import text\n\n'
        '# tenancy-ok: retired 2027-01-01, deletion ticket ARCH-999\n'
        'stmt = text("UPDATE roadmap_tasks SET organization_id = 1 WHERE organization_id IS NULL")\n',
    )
    assert scan_file_writes(qualified, tables) == []


def test_ignores_the_canonical_backfill_file_on_the_real_tree():
    """app/commands/backfill_layer_tenancy.py writes organization_id on several
    tenant tables by design -- it is the one file rule 2 does not report on.
    Proven against the real file content, not a synthetic copy: it already
    contains several matching UPDATE ... SET organization_id statements.
    """
    canonical_path = os.path.join(REPO_ROOT, *_CANONICAL_BACKFILL.split("/"))
    tables = tenant_tables()
    assert tables, "tenant_tables() must resolve at least one table to test anything"
    direct_findings = scan_file_writes(canonical_path, tables)
    assert len(direct_findings) > 0, (
        "the canonical file is expected to contain real UPDATE ... SET "
        "organization_id statements for this test to mean anything"
    )

    # main()'s --json path, exercised end to end (directory walk, canonical-file
    # exclusion, tenant_tables() included) rather than re-derived here. Parsed
    # by locating the printed object rather than assuming stdout is only that
    # object: create_app(), which tenant_tables() calls, prints its own boot
    # banner ("Loaded environment...", "API keys loaded...", and the rest) on
    # stdout ahead of it, in this process and in a subprocess alike.
    import json
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["--json", "--rule", "writes"])
    output = buf.getvalue()
    payload = json.loads(output[output.index("{"):])
    reported_files = {f["file"] for f in payload.get("write_findings", [])}
    assert _CANONICAL_BACKFILL not in reported_files


def test_writes_count_matches_the_measured_baseline_and_a_synthetic_copy_raises_it():
    """The one live measurement this ratchet depends on: run twice, once clean
    and once with a second synthetic writer added to the real tree, so the
    baseline this module's Proven-against line refers to is demonstrated, not
    asserted.

    Goes through scripts.verify._run -- a real subprocess, exactly the way
    gate_raw_sql_tenancy_writes measures this -- rather than calling main()
    in this process. In this process, tenant_tables() resolves the mapper
    registry live (pytest.ini puts the repo root on sys.path for that);
    invoked as a subprocess the way the gate does, it does not, and falls
    back to the committed scripts/tenant_tables.txt cache instead. Calling
    main() directly here would measure a different, larger table set than
    the gate ever does, and could disagree with its own baseline for a
    reason that has nothing to do with this rule.

    The synthetic statement below names business_capability, not
    roadmap_tasks: the committed cache predates roadmap_tasks (and over a
    hundred other now-mapped tables) gaining TenantMixin, so a subprocess
    falling back to it cannot resolve that table at all -- proven by
    running this same probe with roadmap_tasks first and watching the count
    stay at baseline. business_capability is in the committed cache.
    """
    from scripts import verify

    baseline = verify.load_baseline()["raw_sql_tenancy_writes"]

    def _count():
        _reset_tenant_tables_cache()
        proc = verify._run(
            [sys.executable, "scripts/check_raw_sql_tenancy.py", "--count", "--rule", "writes"]
        )
        return int(proc.stdout.strip().splitlines()[-1])

    assert _count() == baseline

    synthetic = os.path.join(REPO_ROOT, "app", "_synthetic_tenancy_writes_probe.py")
    assert not os.path.exists(synthetic)
    try:
        with open(synthetic, "w", encoding="utf-8") as fh:
            fh.write(
                'from sqlalchemy import text\n\n'
                'stmt = text("UPDATE business_capability SET organization_id = 1 '
                'WHERE organization_id IS NULL")\n'
            )
        assert _count() == baseline + 1
    finally:
        os.remove(synthetic)

    assert _count() == baseline


def test_rule_one_count_is_unaffected_by_rule_two():
    """--count with no --rule stays the original, zero-tolerance rule 1 --
    the existing raw-sql-tenancy gate's own contract, unchanged by adding a
    second rule to this file."""
    import io
    import contextlib

    def _count(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(argv)
        # The last printed line, not the whole capture: create_app(), which
        # tenant_tables() calls, prints its own boot banner on stdout ahead
        # of the count, in this process and in a subprocess alike -- the
        # same reason scripts/verify.py's own gates parse a subprocess's
        # stdout the same way rather than assuming it is only the count.
        return int(buf.getvalue().strip().splitlines()[-1])

    # Not asserting a literal 0 here: that is raw-sql-tenancy's own gate,
    # covered by scripts/verify.py --gate raw-sql-tenancy, not this file's
    # job to re-prove. This only proves --rule writes' addition changed
    # nothing about the bare --count path.
    assert _count(["--count"]) == _count(["--count", "--rule", "reads"])
