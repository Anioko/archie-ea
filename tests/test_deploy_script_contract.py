"""Operator deployment wrapper must preserve immutable artifact identity."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_operator_wrapper_passes_digest_and_full_sha_to_host_deployer():
    script = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    assert "sha256:[0-9a-f]{64}" in script
    assert "[0-9a-f]{40}" in script
    assert "./deploy/deploy.sh '$IMAGE_REF' '$EXPECTED_COMMIT'" in script
    assert "docker compose" not in script
    assert "git push" not in script
    assert "--no-build" in script
