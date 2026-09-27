"""Regression tests for static-asset cache-busting.

Root cause these guard against: un-fingerprinted static files (e.g.
css/tailwind-output.css) were served with `Cache-Control: immutable` under a
stable URL. When such a file was rebuilt in place, browsers stayed pinned to
the stale copy for a year — observed live as a fully unstyled login page.

Fix: asset_url uses the deploy's build identifier in production when there is
no content-hash manifest entry. In debug mode it instead appends an mtime
?v= cache-buster, so editing an asset on a running development server gets a
fresh URL. Only content-hashed / ?v=-versioned URLs get `immutable`.
These tests need no database.
"""

import os

import pytest
from flask import Flask

from app._bootstrap.assets import init_assets
from app._bootstrap.security import _FINGERPRINTED_RE


@pytest.fixture
def app(tmp_path):
    static_dir = tmp_path / "static" / "css"
    static_dir.mkdir(parents=True)
    (static_dir / "tailwind-output.css").write_text("body{color:red}")

    application = Flask(__name__, static_folder=str(tmp_path / "static"))
    init_assets(application)
    return application


@pytest.fixture
def debug_app(app):
    app.debug = True
    return app


def _asset_url(application, filename):
    with application.test_request_context():
        return application.jinja_env.filters["asset_url"](filename)


def test_production_unfingerprinted_asset_uses_the_deploy_build_id(app, monkeypatch):
    monkeypatch.setattr("app._bootstrap.assets.get_build_id", lambda: "test-build-id")

    url = _asset_url(app, "css/tailwind-output.css")
    assert url == "/static/css/tailwind-output.css?v=test-build-id"


def test_production_build_id_does_not_change_when_one_file_is_rebuilt(app):
    """A single deploy has one cache version, not one version per asset."""
    before = _asset_url(app, "css/tailwind-output.css")

    path = os.path.join(app.static_folder, "css", "tailwind-output.css")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("body{color:blue}")
    # Bump mtime deterministically (avoids relying on wall-clock resolution).
    stat = os.stat(path)
    os.utime(path, (stat.st_atime, stat.st_mtime + 5))

    after = _asset_url(app, "css/tailwind-output.css")
    assert before == after, "production asset URLs must use the deploy-wide build id"


def test_debug_version_changes_when_file_is_rebuilt(debug_app):
    before = _asset_url(debug_app, "css/tailwind-output.css")

    path = os.path.join(debug_app.static_folder, "css", "tailwind-output.css")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("body{color:blue}")
    # Bump mtime deterministically (avoids relying on wall-clock resolution).
    stat = os.stat(path)
    os.utime(path, (stat.st_atime, stat.st_mtime + 5))

    after = _asset_url(debug_app, "css/tailwind-output.css")
    assert before != after, "debug asset URLs must change when the file is rebuilt"


def test_debug_missing_asset_falls_back_to_bare_url(debug_app):
    url = _asset_url(debug_app, "css/does-not-exist.css")
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
