"""Static regression guards for composer front-end fixes (CMP-04, ...).

There is no JS test runtime in this environment (the JS suite is Playwright,
which needs a browser), so these guards assert the shape of the fix in source —
enough to catch a regression that silently reverts the change. Behavioural
confirmation of these UI fixes is done with a browser pass (fix-then-verify).
"""

from __future__ import annotations

import pathlib

JS = pathlib.Path(__file__).resolve().parents[1] / "app" / "static" / "js"


def _read(rel: str) -> str:
    return (JS / rel).read_text(encoding="utf-8")


def test_cmp04_confirm_accepts_object_first_argument():
    """Platform.modal.confirm must not render an options object as [object Object].

    ui/modal.js confirmDialog(message, options) String()'d message into the body;
    the composer calls it with a single {title, message, ...} object, so the body
    read literally "[object Object]". The fix normalises an object-first call.
    """
    src = _read("ui/modal.js")
    # The normalisation branch: when message is an object, treat it as options
    # and pull the body text out of it.
    assert "typeof message === 'object'" in src, \
        "confirmDialog must detect an object-first call"
    assert "options.message || options.text" in src, \
        "confirmDialog must extract the body text from the options object"
    # Both label naming conventions supported (confirmText/cancelText and
    # confirmLabel/cancelLabel) so the composer's confirmText/cancelText work.
    assert "options.confirmLabel || options.confirmText" in src
    assert "options.cancelLabel || options.cancelText" in src


def test_cmp02_delete_affordance_and_method_present():
    """The saved-viewpoint picker must expose delete, wired to deleteSavedViewpoint."""
    overlays = (JS.parents[1] / "templates" / "archimate" / "partials"
                / "_composer_overlays.html").read_text(encoding="utf-8")
    assert "deleteSavedViewpoint(svp.id" in overlays, \
        "picker rows must call deleteSavedViewpoint"
    persistence = _read("archimate/composer_persistence.js")
    assert "deleteSavedViewpoint:" in persistence, "method must exist"
    assert "Platform.fetch.delete('/archimate/api/saved-viewpoints/'" in persistence, \
        "must call the DELETE endpoint"


def test_cmp08_quick_add_avoids_overlap():
    """New elements must cascade off an occupied spot instead of stacking."""
    src = _read("archimate/composer.js")
    assert "_placementFor:" in src, "placement helper must exist"
    assert "this._placementFor(this.dropX, this.dropY)" in src, \
        "pickElement must route placement through the overlap-avoider"


def test_cmp11_quick_add_searches_catalog_by_name():
    """Quick-add must query the catalog by name, not only palette type labels."""
    src = _read("archimate/composer.js")
    assert "/archimate/api/elements/search?limit=10&q=" in src, \
        "doQuickAddSearch must query the catalog search API"
    assert "_existing" in src, "results must distinguish existing elements from new types"
    overlays = (JS.parents[1] / "templates" / "archimate" / "partials"
                / "_composer_overlays.html").read_text(encoding="utf-8")
    assert "No matching element types found" not in overlays, \
        "misleading 'element types' copy must be gone"
    assert "No matching elements in catalog" in overlays


def test_cmp03_audit_failure_not_toasted():
    """The composer must not toast on a fire-and-forget audit-log failure."""
    src = _read("archimate/composer.js")
    # The old code toasted 'Failed to log audit event' inside the catch.
    assert "Failed to log audit event" not in src, \
        "audit-log failures must be silent (fire-and-forget), not toasted"
