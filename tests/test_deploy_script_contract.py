"""Operator deployment wrapper must preserve immutable artifact identity."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_operator_wrapper_passes_digest_and_full_sha_to_host_deployer():
    script = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    assert "sha256:[0-9a-f]{64}" in script
    assert "[0-9a-f]{40}" in script
    assert "LEGACY_COMMIT=$(git rev-parse HEAD)" in script
    assert './deploy/remote-cutover.sh "$IMAGE_REF" "$EXPECTED_COMMIT" "$LEGACY_COMMIT"' in script
    assert "docker compose" not in script
    assert "git push" not in script
    assert "--no-build" in script


def test_first_immutable_cutover_has_a_verified_legacy_rollback():
    script = (ROOT / "deploy" / "remote-cutover.sh").read_text(encoding="utf-8")

    assert "sha256:[0-9a-f]{64}" in script
    assert "[0-9a-f]{40}" in script
    assert 'git cat-file -e "$LEGACY_COMMIT^{commit}"' in script
    assert 'git checkout --detach "$LEGACY_COMMIT"' in script
    assert "docker compose up -d --no-build --force-recreate server" in script
    assert 'curl -s -o /dev/null -m 10 -w' in script
    assert 'test -f "$RELEASE_FILE"' in script
    assert "verified legacy rollback" in script
