"""Runtime contract for Archie's primary HTML-to-PDF dependency."""

from importlib.metadata import version
import sys

from packaging.version import Version
import pytest


def test_weasyprint_is_on_the_security_fixed_major():
    assert Version(version("weasyprint")) >= Version("69.0")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="production renderer needs Pango/GObject; the release gate runs on Linux",
)
def test_security_fixed_weasyprint_generates_a_pdf():
    """The production runtime must keep the exact API Archie calls."""
    from weasyprint import HTML

    pdf = HTML(
        string=(
            "<!doctype html><html><body>"
            "<h1>Archie export compatibility</h1>"
            "<p>Deterministic local content.</p>"
            "</body></html>"
        )
    ).write_pdf()

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1_000
