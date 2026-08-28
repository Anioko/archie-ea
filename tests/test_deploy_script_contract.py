"""Release script contracts that must not depend on Compose heuristics."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recreate_flag_forces_a_new_server_container():
    script = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    assert 'echo "up -d --force-recreate server"' in script
    assert script.count("docker compose up -d --force-recreate server") >= 2
