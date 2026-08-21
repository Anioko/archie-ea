"""Regression coverage for pytest's LLM credential isolation."""

import os

from dotenv import load_dotenv


def test_empty_provider_env_blocks_default_dotenv_reload(monkeypatch, tmp_path):
    """`override=False` must not restore a provider key from a parent dotenv."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=real-credential-must-not-load\n")

    # Simulate python-dotenv releases that do not implement
    # PYTHON_DOTENV_DISABLED. The pre-existing empty value is the protection.
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    assert os.environ["OPENAI_API_KEY"] == ""

    load_dotenv(dotenv_path=dotenv_path, override=False)

    assert os.environ["OPENAI_API_KEY"] == ""
