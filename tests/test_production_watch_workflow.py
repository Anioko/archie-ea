"""GitHub must be able to parse and dispatch the production monitor."""

from pathlib import Path
import re


WORKFLOW = Path(".github/workflows/production-watch.yml")


def test_production_watch_never_references_secrets_directly_in_if_conditions():
    source = WORKFLOW.read_text(encoding="utf-8")

    offenders = re.findall(r"^\s*if:\s*.*secrets\.[A-Za-z0-9_]+", source, re.MULTILINE)
    assert offenders == [], (
        "GitHub rejects secrets.* in if conditionals before creating any jobs: "
        f"{offenders}"
    )
    assert "DROPLET_SSH_KEY: ${{ secrets.DROPLET_SSH_KEY }}" in source
    assert "if: ${{ env.DROPLET_SSH_KEY != '' }}" in source
