"""Apply unified diff patches to in-memory file content.

Supports Python, TypeScript, Go, Java (any text file via line-based patch).
No AST required — standard unified diff line patching with context validation.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PatchApplyError(Exception):
    """Raised when a patch cannot be cleanly applied."""


def apply_patch(original_content: str, unified_diff: str) -> str:
    """Apply a unified diff to file content. Returns new content.

    Raises PatchApplyError if the patch context doesn't match.
    """
    hunks = _parse_hunks(unified_diff)
    if not hunks:
        raise PatchApplyError("No hunks found in diff.")

    lines = original_content.splitlines(keepends=True)
    offset = 0  # accumulated line offset from previous hunks

    for hunk in hunks:
        orig_start = hunk["orig_start"] - 1 + offset  # 0-indexed
        orig_count = hunk["orig_count"]

        # Validate context
        hunk_orig_lines = [l for l in hunk["lines"] if l.startswith(" ") or l.startswith("-")]
        segment = lines[orig_start: orig_start + orig_count]

        if not _context_matches(segment, hunk_orig_lines):
            # Try fuzzy match ±3 lines
            found_at = _fuzzy_find(lines, hunk_orig_lines, orig_start)
            if found_at is None:
                raise PatchApplyError(
                    f"Patch context mismatch at line {orig_start + 1}. "
                    "The file may have changed since the diff was generated."
                )
            offset_correction = found_at - orig_start
            orig_start = found_at
            offset += offset_correction

        # Build replacement lines from hunk
        new_lines = []
        for line in hunk["lines"]:
            if line.startswith("+"):
                new_lines.append(line[1:] if len(line) > 1 else "\n")
            elif line.startswith(" "):
                new_lines.append(line[1:] if len(line) > 1 else "\n")
            # lines starting with "-" are removed

        lines[orig_start: orig_start + orig_count] = new_lines
        added = len(new_lines)
        removed = orig_count
        offset += added - removed

    return "".join(lines)


def _parse_hunks(unified_diff: str) -> list[dict]:
    """Parse unified diff into list of hunks."""
    hunks = []
    current_hunk = None
    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    for line in unified_diff.splitlines(keepends=True):
        if line.startswith("---") or line.startswith("+++"):
            continue
        m = hunk_header_re.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "orig_start": int(m.group(1)),
                "orig_count": int(m.group(2)) if m.group(2) is not None else 1,
                "new_start": int(m.group(3)),
                "new_count": int(m.group(4)) if m.group(4) is not None else 1,
                "lines": [],
            }
        elif current_hunk is not None:
            current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)
    return hunks


def _context_matches(segment: list[str], hunk_orig_lines: list[str]) -> bool:
    """Check if file segment matches the hunk's context/removed lines."""
    if len(segment) != len(hunk_orig_lines):
        return False
    for file_line, hunk_line in zip(segment, hunk_orig_lines):
        expected = hunk_line[1:] if hunk_line.startswith((" ", "-")) else hunk_line
        if file_line.rstrip("\n\r") != expected.rstrip("\n\r"):
            return False
    return True


def _fuzzy_find(lines: list[str], hunk_orig_lines: list[str], hint: int) -> Optional[int]:
    """Try to find the hunk context within ±10 lines of the hint."""
    for delta in range(1, 11):
        for sign in (1, -1):
            candidate = hint + sign * delta
            if candidate < 0 or candidate + len(hunk_orig_lines) > len(lines):
                continue
            if _context_matches(lines[candidate: candidate + len(hunk_orig_lines)], hunk_orig_lines):
                return candidate
    return None


def validate_diff_safety(unified_diff: str) -> list[str]:
    """Return list of safety warnings for a diff before applying it."""
    from app.modules.codegen.services.nl_code_editor import _check_destructive
    return _check_destructive(unified_diff)
