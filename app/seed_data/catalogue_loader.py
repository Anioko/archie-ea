"""Utility helpers to load the vendor catalogue definitions.

This module now loads from the native Python vendor_catalogue module
instead of parsing TypeScript files with regex.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Import from the Python module
from . import vendor_catalogue

DEFAULT_CUSTOM_MODEL_PATH = Path(__file__).with_name("custom_capability_model.ts")

# Legacy path for backwards compatibility
DEFAULT_CATALOGUE_PATH = Path(__file__).with_name("vendor_catalogue.ts")

# Regex to capture `export const NAME = ...;` blocks (arrays or objects)
EXPORT_BLOCK_PATTERN = re.compile(
    r"export\s+const\s+(?P<name>[A-Z0-9_]+)(?:\s*:[^=]+)?\s*=\s*(?P<body>\[[\s\S]*?\]|\{[\s\S]*?\});",
    re.MULTILINE,
)


class CatalogueParseError(RuntimeError):
    """Raised when the TypeScript catalogue file cannot be parsed."""


def _strip_comments(source: str) -> str:
    """Remove line and block comments without touching URL protocols."""

    # Remove block comments first
    cleaned = re.sub(r"/\*[\s\S]*?\*/", "", source)

    # Remove // comments that are not part of a URL literal (http:// or https://)
    cleaned = re.sub(r"(?<!:)//.*", "", cleaned)
    return cleaned


def _quote_object_keys(source: str) -> str:
    """Ensure JavaScript object keys are quoted so the block becomes valid JSON."""

    def replacer(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        key = match.group("key")
        return f'{prefix}"{key}":'

    # Match keys that follow either `{` or `,` and consist of JS identifier characters.
    return re.sub(
        r"(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:",
        replacer,
        source,
    )


def _remove_trailing_commas(source: str) -> str:
    """JSON does not allow trailing commas on arrays/objects."""
    return re.sub(r",(\s*[}\]])", r"\1", source)


def _normalise_block(raw_block: str) -> str:
    """Convert a TypeScript literal block into JSON text."""
    without_comments = _strip_comments(raw_block)
    quoted = _quote_object_keys(without_comments)
    no_trailing_commas = _remove_trailing_commas(quoted)
    return no_trailing_commas.strip()


def _extract_export_block(source: str, name: str) -> str:
    match = None
    for candidate in EXPORT_BLOCK_PATTERN.finditer(source):
        if candidate.group("name") == name:
            match = candidate
            break
    if not match:
        raise CatalogueParseError(f"Unable to locate export block for '{name}'.")
    return match.group("body")


def _load_export_as_json(source: str, name: str) -> Any:
    block = _extract_export_block(source, name)
    normalised = _normalise_block(block)
    try:
        return json.loads(normalised)
    except json.JSONDecodeError as exc:
        raise CatalogueParseError(f"Failed to parse '{name}' block: {exc}") from exc


def load_catalogue(path: Path | None = None) -> Dict[str, Any]:
    """
    Load the vendor catalogue and return the exported data.

    Now loads from the native Python module vendor_catalogue.py
    instead of parsing TypeScript with regex.
    """
    # Ignore path parameter - always use Python module now
    return {
        "capability_taxonomy": dict(vendor_catalogue.CAPABILITY_TAXONOMY),
        "cobit_processes": dict(vendor_catalogue.COBIT_PROCESSES),
        "itil_processes": dict(vendor_catalogue.ITIL_PROCESSES),
        "vendors": list(vendor_catalogue.VENDOR_CATALOGUE),
    }


def load_custom_capability_model(path: Path | None = None) -> List[Dict[str, Any]]:
    """Load the custom capability model definition from its TypeScript source."""
    ts_path = path or DEFAULT_CUSTOM_MODEL_PATH
    if not ts_path.exists():
        raise FileNotFoundError(f"Custom capability model not found at {ts_path!s}")

    source = ts_path.read_text(encoding="utf-8")
    model = _load_export_as_json(source, "CUSTOM_CAPABILITY_MODEL")
    if not isinstance(model, list):
        raise CatalogueParseError("Custom capability model export must be an array.")
    return model


__all__ = [
    "load_catalogue",
    "load_custom_capability_model",
    "CatalogueParseError",
    "DEFAULT_CATALOGUE_PATH",
    "DEFAULT_CUSTOM_MODEL_PATH",
]
