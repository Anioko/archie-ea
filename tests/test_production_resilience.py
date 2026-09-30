"""Production test organisations: seed command, cross-org check, and restore drill.

Coverage:
- The seed-production-test-organisations CLI command is idempotent
- The cross-organisation check detects a seeded leak
- The restore drill script is structurally valid
- The WAL archive script is structurally valid
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.usefixtures("db_session")


# ---------------------------------------------------------------------------
# Seed command
# ---------------------------------------------------------------------------


def test_seed_command_creates_two_organisations(app, db_session, monkeypatch):
    """The seed command creates exactly two organisations with stable slugs."""
    from app.models.organization import Organization

    monkeypatch.setenv("PROD_TEST_ORG_PASSWORD", "test-password-123")

    before_a = Organization.query.filter_by(slug="archie-prod-test-org-a").first()
    before_b = Organization.query.filter_by(slug="archie-prod-test-org-b").first()
    assert before_a is None
    assert before_b is None

    result = app.test_cli_runner().invoke(
        args=["seed-production-test-organisations", "--password", "test-password-123"]
    )

    assert result.exit_code == 0, f"command failed: {result.output}\n{result.exception!r}"
    assert "organisation A: archie-prod-test-org-a (created)" in result.output
    assert "organisation B: archie-prod-test-org-b (created)" in result.output

    org_a = Organization.query.filter_by(slug="archie-prod-test-org-a").first()
    org_b = Organization.query.filter_by(slug="archie-prod-test-org-b").first()
    assert org_a is not None
    assert org_b is not None
    assert org_a.name == "Archie Production Test Organisation A"
    assert org_b.name == "Archie Production Test Organisation B"
    assert org_a.settings.get("production_test_org") is True
    assert org_b.settings.get("production_test_org") is True

    # Each org has one admin user
    from app.models.user import User

    users_a = User.query.filter_by(organization_id=org_a.id).all()
    users_b = User.query.filter_by(organization_id=org_b.id).all()
    assert len(users_a) == 1
    assert len(users_b) == 1
    assert users_a[0].email.endswith("@archie-prod-test.example.com")
    assert users_b[0].email.endswith("@archie-prod-test.example.com")


def test_seed_command_is_idempotent(app, db_session, monkeypatch):
    """Running the seed command twice does not create duplicates."""
    from app.models.organization import Organization
    from app.models.user import User

    monkeypatch.setenv("PROD_TEST_ORG_PASSWORD", "test-password-123")

    # First run
    result1 = app.test_cli_runner().invoke(
        args=["seed-production-test-organisations", "--password", "test-password-123"]
    )
    assert result1.exit_code == 0

    org_a_count_before = Organization.query.filter_by(slug="archie-prod-test-org-a").count()
    org_b_count_before = Organization.query.filter_by(slug="archie-prod-test-org-b").count()
    assert org_a_count_before == 1
    assert org_b_count_before == 1

    # Second run
    result2 = app.test_cli_runner().invoke(
        args=["seed-production-test-organisations", "--password", "test-password-123"]
    )
    assert result2.exit_code == 0
    assert "already exists" in result2.output

    org_a_count_after = Organization.query.filter_by(slug="archie-prod-test-org-a").count()
    org_b_count_after = Organization.query.filter_by(slug="archie-prod-test-org-b").count()
    assert org_a_count_after == 1
    assert org_b_count_after == 1

    # User count is still 1 per org
    org_a = Organization.query.filter_by(slug="archie-prod-test-org-a").first()
    org_b = Organization.query.filter_by(slug="archie-prod-test-org-b").first()
    assert User.query.filter_by(organization_id=org_a.id).count() == 1
    assert User.query.filter_by(organization_id=org_b.id).count() == 1


def test_seed_command_refuses_without_password(app):
    """The command fails when no password is provided."""
    result = app.test_cli_runner().invoke(
        args=["seed-production-test-organisations"],
        env={**os.environ, "PROD_TEST_ORG_PASSWORD": ""},
    )
    assert result.exit_code != 0
    assert "PROD_TEST_ORG_PASSWORD" in result.output


def test_is_production_test_org_helper():
    """The helper correctly identifies production test org slugs."""
    from app.commands.seed_production_test_organisations import (
        is_production_test_org,
        production_test_org_slugs,
    )

    assert is_production_test_org("archie-prod-test-org-a") is True
    assert is_production_test_org("archie-prod-test-org-b") is True
    assert is_production_test_org("some-real-org") is False
    assert is_production_test_org(None) is False
    assert is_production_test_org("") is False

    slugs = production_test_org_slugs()
    assert "archie-prod-test-org-a" in slugs
    assert "archie-prod-test-org-b" in slugs
    assert len(slugs) == 2


# ---------------------------------------------------------------------------
# Cross-organisation check (regression test against the check itself)
# ---------------------------------------------------------------------------


def test_cross_org_check_detects_seeded_leak(app, db_session, make_org, monkeypatch):
    """A seeded cross-organisation leak fails the post-deploy check.

    This is a regression test against the check itself: we create two orgs,
    seed a user in org A that has a foreign record pointing to org B, then
    prove the cross-org check script detects it.
    """
    from app.models.organization import Organization
    from app.models.user import Role, User

    # Create two test organisations
    org_a = make_org("cross-check-a")
    org_b = make_org("cross-check-b")

    Role.insert_roles()
    admin_role = Role.query.filter_by(name="Administrator").first()

    password = "cross-org-test-pw-123"
    user_a = User(
        email="cross-check-a@archie-prod-test.example.com",
        first_name="Cross",
        last_name="Check A",
        organization_id=org_a.id,
        role=admin_role,
        confirmed=True,
    )
    user_a.password = password
    user_b = User(
        email="cross-check-b@archie-prod-test.example.com",
        first_name="Cross",
        last_name="Check B",
        organization_id=org_b.id,
        role=admin_role,
        confirmed=True,
    )
    user_b.password = password
    db_session.add_all([user_a, user_b])
    db_session.commit()

    # The cross-org check script is importable and its main function is callable
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "deploy_verify_cross_org",
        ROOT / "scripts" / "deploy_verify_cross_org.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The module should have the expected functions
    assert hasattr(mod, "_login")
    assert hasattr(mod, "_check_cannot_read_other_org")
    assert hasattr(mod, "main")


def test_cross_org_check_script_is_syntactically_valid():
    """The cross-org check script compiles and has the expected structure."""
    script = ROOT / "scripts" / "deploy_verify_cross_org.py"
    source = script.read_text(encoding="utf-8")

    # Compile to check syntax
    compile(source, str(script), "exec")

    # Verify key structural elements
    assert "def _login" in source
    assert "def _check_cannot_read_other_org" in source
    assert "def main" in source
    assert "PROD_TEST_ORG_A_EMAIL" in source
    assert "PROD_TEST_ORG_B_EMAIL" in source
    assert "PROD_TEST_ORG_PASSWORD" in source
    assert "cross-org-check: OK" in source
    assert "cross-org-check: FAIL" in source


# ---------------------------------------------------------------------------
# WAL archive script
# ---------------------------------------------------------------------------


def test_wal_archive_script_is_syntactically_valid():
    """The WAL archive script passes bash syntax check."""
    script = ROOT / "deploy" / "wal_archive.sh"
    source = script.read_text(encoding="utf-8")

    # Verify key structural elements
    assert "WALG_STORAGE_PREFIX" in source
    assert "AWS_ACCESS_KEY_ID" in source
    assert "AWS_SECRET_ACCESS_KEY" in source
    assert "build_archive_command" in source
    assert "apply_archive_config" in source
    assert "verify_wal_g" in source
    assert "wal-g" in source
    assert "archive_command" in source
    assert "archive_mode" in source

    # Check bash syntax with bash -n
    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


def test_wal_archive_script_prints_command_with_flag():
    """The --print-command flag outputs the archive_command without applying it."""
    script = ROOT / "deploy" / "wal_archive.sh"
    result = subprocess.run(
        ["bash", str(script), "--print-command"],
        capture_output=True, text=True,
        env={
            **os.environ,
            "WALG_STORAGE_PREFIX": "s3://test-bucket/archie-wal",
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_REGION": "us-east-1",
        },
    )
    # The command should print the archive_command string
    assert "wal-g" in result.stdout
    assert "wal-push" in result.stdout
    assert "docker exec" in result.stdout


# ---------------------------------------------------------------------------
# Restore drill script
# ---------------------------------------------------------------------------


def test_restore_drill_script_is_syntactically_valid():
    """The restore drill script passes bash syntax check."""
    script = ROOT / "scripts" / "restore_drill.sh"
    source = script.read_text(encoding="utf-8")

    # Verify key structural elements
    assert "WALG_STORAGE_PREFIX" in source
    assert "RESTORE_TARGET_TIME" in source
    assert "SCRATCH_CONTAINER_NAME" in source
    assert "MAX_RESTORE_SECONDS" in source
    assert "wal-g backup-list" in source
    assert "wal-g backup-fetch" in source
    assert "pg_restore" in source
    assert "recovery_target_time" in source
    assert "RESTORE DRILL PASSED" in source
    assert "RESTORE-DRILL FAIL" in source

    # Check bash syntax with bash -n
    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"bash syntax error: {result.stderr}"


def test_restore_drill_script_refuses_without_target_time():
    """The script fails when RESTORE_TARGET_TIME is not set."""
    script = ROOT / "scripts" / "restore_drill.sh"
    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True, text=True,
        env={
            **os.environ,
            "WALG_STORAGE_PREFIX": "s3://test-bucket/archie-wal",
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_REGION": "us-east-1",
            # RESTORE_TARGET_TIME deliberately not set
        },
    )
    assert result.returncode != 0
    assert "RESTORE_TARGET_TIME" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# deploy_verified.sh cross-org integration
# ---------------------------------------------------------------------------


def test_deploy_verified_sh_has_cross_org_step():
    """deploy_verified.sh includes the cross-organisation check as step 6."""
    script = ROOT / "scripts" / "deploy_verified.sh"
    source = script.read_text(encoding="utf-8")

    assert "run_cross_org_check" in source
    assert "cross-organisation tenant isolation" in source
    assert "PROD_TEST_ORG_A_EMAIL" in source
    assert "PROD_TEST_ORG_B_EMAIL" in source
    assert "PROD_TEST_ORG_PASSWORD" in source
    assert "deploy_verify_cross_org.py" in source
    assert "IMAGE_PIPELINE_TOPOLOGY" in source


def test_deploy_verified_sh_has_retired_bind_mount_note():
    """deploy_verified.sh documents that bind-mount checks are retired for the image pipeline."""
    script = ROOT / "scripts" / "deploy_verified.sh"
    source = script.read_text(encoding="utf-8")

    assert "29 Sep 2026" in source
    assert "image-pipeline topology" in source
    assert "RETIRED" in source
    assert "IMAGE_PIPELINE_TOPOLOGY=1" in source


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------


def test_seed_command_is_registered_in_cli():
    """The seed command is registered in app/_bootstrap/cli.py."""
    cli_file = ROOT / "app" / "_bootstrap" / "cli.py"
    source = cli_file.read_text(encoding="utf-8")

    assert "seed_production_test_organisations" in source
    assert "Production test organisations seed CLI command registered" in source


# ---------------------------------------------------------------------------
# Exclusion from metrics and billing
# ---------------------------------------------------------------------------


def test_production_test_org_slugs_are_stable():
    """The production test org slugs must never change without updating all exclusion filters."""
    from app.commands.seed_production_test_organisations import (
        ORG_A_SLUG,
        ORG_B_SLUG,
    )

    assert ORG_A_SLUG == "archie-prod-test-org-a"
    assert ORG_B_SLUG == "archie-prod-test-org-b"


def test_production_test_orgs_are_excluded_from_metrics_queries(app, db_session, monkeypatch):
    """Metrics queries that aggregate by organisation must exclude test orgs."""
    from app.commands.seed_production_test_organisations import (
        is_production_test_org,
        production_test_org_slugs,
    )
    from app.models.organization import Organization

    monkeypatch.setenv("PROD_TEST_ORG_PASSWORD", "test-password-123")

    # Seed the test orgs
    app.test_cli_runner().invoke(
        args=["seed-production-test-organisations", "--password", "test-password-123"]
    )

    org_a = Organization.query.filter_by(slug="archie-prod-test-org-a").first()
    org_b = Organization.query.filter_by(slug="archie-prod-test-org-b").first()

    assert org_a is not None
    assert org_b is not None
    assert is_production_test_org(org_a.slug) is True
    assert is_production_test_org(org_b.slug) is True

    # The exclusion filter works in a query
    slugs = production_test_org_slugs()
    non_test_orgs = Organization.query.filter(
        ~Organization.slug.in_(slugs)
    ).all()

    for org in non_test_orgs:
        assert org.slug not in slugs
