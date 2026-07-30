"""Regression tests for static-asset cache-busting.

Root cause these guard against: un-fingerprinted static files (e.g.
css/tailwind-output.css) were served with `Cache-Control: immutable` under a
stable URL. When such a file was rebuilt in place, browsers stayed pinned to
the stale copy for a year — observed live as a fully unstyled login page.

Fix: asset_url appends an mtime ?v= cache-buster when there is no content-hash
manifest entry, and only content-hashed / ?v=-versioned URLs get `immutable`.
These tests need no database.
"""

import os

import pytest
from flask import Flask

from app._bootstrap.assets import _asset_version, init_assets
from app._bootstrap.security import _FINGERPRINTED_RE


@pytest.fixture
def app(tmp_path):
    static_dir = tmp_path / "static" / "css"
    static_dir.mkdir(parents=True)
    (static_dir / "tailwind-output.css").write_text("body{color:red}")

    application = Flask(__name__, static_folder=str(tmp_path / "static"))
    init_assets(application)
    return application


def _asset_url(application, filename):
    with application.test_request_context():
        return application.jinja_env.filters["asset_url"](filename)


def test_unfingerprinted_asset_gets_version_query(app):
    url = _asset_url(app, "css/tailwind-output.css")
    assert url.startswith("/static/css/tailwind-output.css?v=")

    expected = _asset_version(app.static_folder, "css/tailwind-output.css")
    assert expected is not None
    assert url.endswith(f"v={expected}")


def test_version_changes_when_file_is_rebuilt(app):
    before = _asset_url(app, "css/tailwind-output.css")

    path = os.path.join(app.static_folder, "css", "tailwind-output.css")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("body{color:blue}")
    # Bump mtime deterministically (avoids relying on wall-clock resolution).
    stat = os.stat(path)
    os.utime(path, (stat.st_atime, stat.st_mtime + 5))

    after = _asset_url(app, "css/tailwind-output.css")
    assert before != after, "rebuilt asset must get a fresh URL so clients refetch"


def test_missing_asset_falls_back_to_bare_url(app):
    url = _asset_url(app, "css/does-not-exist.css")
    assert url == "/static/css/does-not-exist.css"
    assert "?v=" not in url


def test_manifest_hashed_asset_needs_no_version_query(app, monkeypatch):
    # A manifest entry means the filename is already content-hashed.
    monkeypatch.setattr(
        "app._bootstrap.assets._manifest_cache",
        {"css/tailwind-output.css": "css/tailwind-output.b257857d.css"},
    )
    url = _asset_url(app, "css/tailwind-output.css")
    assert url == "/static/css/tailwind-output.b257857d.css"
    assert "?v=" not in url


@pytest.mark.parametrize(
    "path,fingerprinted",
    [
        ("/static/css/tailwind-output.b257857d.css", True),
        ("/static/js/app.9f8e7d6c5b4a.js", True),
        ("/static/css/tailwind-output.css", False),
        ("/static/css/app.css", False),
        ("/static/js/core/00-namespace.js", False),
    ],
)
def test_fingerprint_regex(path, fingerprinted):
    assert bool(_FINGERPRINTED_RE.search(path)) is fingerprinted
