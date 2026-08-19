"""Gate the CSP-safe Alpine evaluator (ARCH-070).

Two headless-browser checks, each skipping cleanly when Playwright or a browser
is unavailable (same policy as tests/smoke), so `pytest -q` stays green on a
box without chromium while CI (which has it) enforces them:

  1. verify_evaluator: the evaluator parses ~100% of the real Alpine expression
     corpus and matches native eval on every pure expression.
  2. verify_alpine_integration: real Alpine 3.14.3 + the evaluator works under a
     CSP whose header omits 'unsafe-eval' (with stock-Alpine broken as control).
"""
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

playwright = pytest.importorskip("playwright.sync_api")


def _has_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True); b.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _has_browser(), reason="no chromium for Playwright")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_evaluator_covers_corpus_and_matches_native_eval():
    m = _load("verify_evaluator", HERE / "verify_evaluator.py")
    assert m.main() == 0, "CSP evaluator failed coverage/correctness/differential checks"


def test_alpine_works_under_csp_without_unsafe_eval():
    m = _load("verify_alpine_integration", HERE / "verify_alpine_integration.py")
    assert m.main() == 0, "Alpine+CSPExpr failed under a CSP without unsafe-eval"


@pytest.mark.skipif(
    "TEST_DATABASE_URL" not in __import__("os").environ,
    reason="real-app smoke needs a database (TEST_DATABASE_URL)")
def test_real_app_pages_parse_and_evaluate():
    """Boot the real app, load real rendered pages, and check every Alpine
    expression in the live DOM parses and matches native eval (0 divergences)."""
    import os
    os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    m = _load("verify_real_pages", HERE / "verify_real_pages.py")
    assert m.main() == 0, "CSP evaluator failed against real rendered app pages"
