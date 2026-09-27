"""Runtime contract for Archie's primary HTML-to-PDF dependency."""

from importlib.metadata import version
import sys

from packaging.version import Version


def test_weasyprint_is_on_the_security_fixed_major():
    assert Version(version("weasyprint")) >= Version("69.0")


def _security_fixed_weasyprint_generates_a_pdf():
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


# PDF rendering is a production-runtime assertion.  Windows cannot load the
# required native Pango/GObject stack; Linux CI always collects and executes
# it, while Windows still executes the version/security-floor assertion above.
if sys.platform != "win32":
    test_security_fixed_weasyprint_generates_a_pdf = (
        _security_fixed_weasyprint_generates_a_pdf
    )
