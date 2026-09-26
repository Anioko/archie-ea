"""Shared validation for OAuth client redirect URIs.

Used by both ``OAuthClient.register()`` (the only path that creates a
client row) and ``/oauth/authorize`` (which re-validates a registered
client's stored URIs before ever redirecting to one).
"""
from __future__ import annotations

from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def is_loopback_host(host: str) -> bool:
    if not host:
        return False
    hostname = host.split(":", 1)[0]
    return hostname in _LOOPBACK_HOSTS


def validate_redirect_uri(uri: str) -> str:
    """Return *uri* unchanged if it is an acceptable registration target.

    Raises ``ValueError`` otherwise. Rules: https anywhere, or http only on
    a loopback address; no wildcard host or path segment; no fragment.
    """
    if not uri or not isinstance(uri, str):
        raise ValueError("redirect_uris entries must be non-empty strings")

    parts = urlsplit(uri)

    if parts.fragment:
        raise ValueError(f"redirect_uri must not contain a fragment: {uri!r}")

    if "*" in uri:
        raise ValueError(f"redirect_uri must not contain a wildcard: {uri!r}")

    if parts.scheme == "https":
        if not parts.netloc:
            raise ValueError(f"redirect_uri is missing a host: {uri!r}")
        return uri

    if parts.scheme == "http":
        if not is_loopback_host(parts.netloc):
            raise ValueError(
                f"redirect_uri may only use http on a loopback address: {uri!r}"
            )
        return uri

    raise ValueError(f"redirect_uri must use https, or http on loopback: {uri!r}")


def validate_redirect_uris(uris) -> list[str]:
    if not uris or not isinstance(uris, (list, tuple)) or len(uris) == 0:
        raise ValueError("redirect_uris must be a non-empty list")
    return [validate_redirect_uri(u) for u in uris]
