"""Safe XML parsing for untrusted input.

Every ArchiMate and SAML document this application parses arrives from a user
upload or an external identity provider. Python's stdlib ElementTree does not
resolve external entities, so classic XXE file disclosure is not reachable, but
it remains vulnerable to entity-expansion ("billion laughs") and quadratic
blowup: a few kilobytes can expand to gigabytes during parsing. On a 3.8GB
production box that is a denial of service, and this deployment has already
been OOM-killed once.

Two layers, in order of preference:

1. defusedxml, when installed. It blocks entity expansion, external entities
   and DTD retrieval inside the parser itself.

2. Otherwise, a DTD/ENTITY pre-check on the raw document before the stdlib
   parser ever sees it. Entity expansion requires a document type declaration,
   so refusing any document carrying one closes the same hole. This layer
   exists because the deployed container image predates the defusedxml
   requirement, and shipping an unguarded parser until the next image rebuild
   was not acceptable.

This is deliberately NOT a silent fallback to an unprotected parser. Layer 2 is
a real control. The only difference from layer 1 is that it refuses a
legitimate DTD-bearing document rather than parsing it safely, and no ArchiMate
exchange file needs a DTD.
"""

import re
import xml.etree.ElementTree as _ET

try:  # pragma: no cover - depends on the deployed image
    from defusedxml import ElementTree as _SafeET

    _HAVE_DEFUSEDXML = True
except ImportError:  # pragma: no cover
    _SafeET = None
    _HAVE_DEFUSEDXML = False

ParseError = _ET.ParseError

# A DOCTYPE is the only way to declare entities, so its presence is the signal.
# Checked against the raw document before parsing, because by the time the
# parser has processed it the expansion has already happened.
_DOCTYPE_RE = re.compile(rb"<!\s*DOCTYPE", re.IGNORECASE)
_ENTITY_RE = re.compile(rb"<!\s*ENTITY", re.IGNORECASE)


class UnsafeXmlError(ValueError):
    """Raised when a document declares a DTD or entities."""


def _as_bytes(text):
    if isinstance(text, bytes):
        return text
    return text.encode("utf-8", errors="ignore")


def _reject_dtd(payload):
    raw = _as_bytes(payload)
    if _DOCTYPE_RE.search(raw) or _ENTITY_RE.search(raw):
        raise UnsafeXmlError(
            "XML document declares a DTD or entities, which is refused because "
            "entity expansion can be used to exhaust server memory."
        )


def fromstring(text):
    """Parse untrusted XML text/bytes into an Element."""
    if _HAVE_DEFUSEDXML:
        return _SafeET.fromstring(text)
    _reject_dtd(text)
    return _ET.fromstring(text)


def parse(source):
    """Parse untrusted XML from a file path or file-like object."""
    if _HAVE_DEFUSEDXML:
        return _SafeET.parse(source)
    if hasattr(source, "read"):
        payload = source.read()
        _reject_dtd(payload)
        return _ET.ElementTree(_ET.fromstring(payload))
    with open(source, "rb") as fh:
        payload = fh.read()
    _reject_dtd(payload)
    return _ET.ElementTree(_ET.fromstring(payload))
