"""Shared plumbing for the business-architecture document exports.

Four deliverables — the capability model, a value stream, a business case and
the EA briefing — render to the same four formats. The format table, the
download response and the "which organisation is this" lookup live here once,
so the extension a route promises cannot drift from the MIME type it sends and
a fix to one export is a fix to all of them.

What deliberately does *not* live here is the try/except around the renderers.
Each route spells that out itself, because the interesting case — a format this
deployment cannot produce answering 503 with the reason while the other three
keep working — is the thing a reader of that route needs to see.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from flask import Response, jsonify

# extension -> (mimetype, filename extension). Flask appends the charset for
# text/*, so spelling it here as well produced
# "text/html; charset=utf-8; charset=utf-8".
REPORT_FORMATS = {
    "pdf": ("application/pdf", "pdf"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    "html": ("text/html", "html"),
}

EM_DASH = "—"


def normalise_format(fmt: Optional[str]) -> str:
    """Lower-case the format segment; ``None`` becomes the empty string."""
    return (fmt or "").lower()


def unsupported_format_response(fmt: str) -> Tuple[Response, int]:
    """400 naming the format that was asked for and the ones that exist."""
    return (
        jsonify(
            {
                "success": False,
                "error": f"Unsupported format {fmt!r}. Choose one of: "
                + ", ".join(sorted(REPORT_FORMATS)),
            }
        ),
        400,
    )


def report_response(payload, fmt: str, filename_stem: str) -> Response:
    """Wrap a rendered report in a download (or, for HTML, a plain page)."""
    mimetype, extension = REPORT_FORMATS[fmt]
    response = Response(payload, mimetype=mimetype)
    if fmt != "html":
        stamp = datetime.utcnow().strftime("%Y%m%d")
        response.headers["Content-Disposition"] = (
            f"attachment; filename={filename_stem}_{stamp}.{extension}"
        )
    return response


def current_organisation_name() -> Optional[str]:
    """The signed-in user's organisation name, or None.

    None rather than a placeholder: the cover page omits the line entirely when
    there is no name, which is honest, where "Unknown Organisation" is not.
    """
    try:
        from flask_login import current_user

        org = getattr(current_user, "organization", None)
        return getattr(org, "name", None)
    except Exception:  # noqa: BLE001 - a missing org name must not fail an export
        return None


def safe_filename_stem(text: Optional[str], fallback: str) -> str:
    """A filename fragment from a user-authored title: ASCII, no separators."""
    if not text:
        return fallback
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in text.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned[:60] or fallback).lower()
