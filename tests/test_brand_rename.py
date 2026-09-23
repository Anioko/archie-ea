"""Acceptance checks for the product name rename to Entelim.

The product is called Entelim everywhere a person reads. Three things pin
that down as regression barriers rather than a one-time sweep:

1. ``APP_NAME`` defaults to "Entelim" in the application config, so every
   page, email and document that reads the name from ``config.APP_NAME``
   renders it correctly on a fresh install.
2. The dotted wordmark ``A.R.C.H.I.E.`` no longer appears anywhere under
   ``app/`` — including comments and generated-code templates.
3. The assistant wordmark ``Archi`` does not appear as a standalone word in
   user-facing templates or static JavaScript; only ``ArchiMate`` (the
   external standard) may appear.

These mirror the repository-wide gates in scripts/verify.py so a regression
fails here first, in a targeted test run.
"""

import re

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

STANDALONE_ARCHI = re.compile(r"(?<![A-Za-z])Archi(?![A-Za-z])")


def test_app_name_defaults_to_entelim():
    import config as config_module

    cls = config_module.Config
    assert cls.APP_NAME == "Entelim"


def test_email_subject_prefix_derives_from_app_name():
    import config as config_module

    cls = config_module.Config
    assert cls.EMAIL_SUBJECT_PREFIX == "[Entelim]"


def test_no_dotted_wordmark_anywhere_in_app():
    offenders = []
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "A.R.C.H.I.E." in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"A.R.C.H.I.E. still present in: {offenders}"


def test_no_standalone_archi_word_in_templates_or_static_js():
    suffixes = {".html", ".js"}
    offenders = []
    for path in APP_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if STANDALONE_ARCHI.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"'Archi' standalone still present in: {offenders}"