"""Contracts for build-once, digest-addressed production releases."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SERVICES = {
    "database-bootstrap",
    "schema-deploy",
    "database-acl",
    "server",
    "worker",
}


def test_production_override_uses_one_immutable_image_without_source_mounts():
    source = (ROOT / "deploy" / "docker-compose.production.yml").read_text(
        encoding="utf-8"
    )

    assert source.count("image: ${ARCHIE_IMAGE:?") == len(APP_SERVICES)
    assert source.count("build: !reset null") == len(APP_SERVICES)
    assert source.count("volumes: !reset []") == len(APP_SERVICES)
    assert "./:/app" not in source


def test_release_image_records_the_exact_source_revision():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG VCS_REF" in dockerfile
    assert "org.opencontainers.image.revision=$VCS_REF" in dockerfile
    assert "USER appuser" in dockerfile


def test_ci_builds_once_after_every_release_gate_and_exports_the_digest():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    image_job = workflow.split("\n  release-image:\n", 1)[1]
    for gate in (
        "secret-scan",
        "static-gates",
        "boot-health",
        "tests",
        "db-gates",
        "security-sast",
        "smoke",
        "browser-compatibility",
        "walkthrough",
        "dependency-audit",
    ):
        assert gate in image_job.split("steps:", 1)[0]

    assert image_job.count("docker/build-push-action@") == 1
    assert "push: true" in image_job
    assert "VCS_REF=${{ github.sha }}" in image_job
    assert "steps.build.outputs.digest" in image_job
    assert "release.json" in image_job


def test_static_ci_installs_the_browser_required_by_the_js_syntax_gate():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    static_job = workflow.split("\n  static-gates:\n", 1)[1].split(
        "\n  boot-health:\n", 1
    )[0]

    assert "playwright install --with-deps chromium" in static_job
