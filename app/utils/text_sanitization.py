"""Neutralize untrusted free text before it is stored or echoed back as data.

Used anywhere external, human-authored text (an OAuth client's registered
name, a canvas block, an AI-proposed rationale, an MCP tool result) is about
to be persisted or returned inside a response that a person or an LLM will
read. This module does not interpret the text — it only strips bytes that
could break a surrounding fence or terminal, so the content can never escape
whatever context it is displayed in. The result is still plain data.
"""
from __future__ import annotations

import re

# C0 control characters and DEL, excluding tab/newline/carriage-return which
# are common and harmless in free text.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Three or more consecutive backticks can close/open a markdown code fence
# that untrusted text is later embedded inside.
_FENCE_RUN_RE = re.compile(r"`{3,}")

# Common instruction-injection markers seen in "ignore previous instructions"
# style payloads. Not a security boundary by itself (nothing here is ever
# treated as instructions) — flagged only so callers can log/annotate.
_INSTRUCTION_MARKER_RE = re.compile(
    r"(?i)\[(system|instructions?|inst)\]|<\|?(system|im_start|im_end)\|?>"
)


def strip_control_characters(text: str) -> str:
    """Remove non-printable control bytes, keeping tab/newline/CR."""
    return _CONTROL_CHARS_RE.sub("", text)


def neutralize_fence_lookalikes(text: str) -> str:
    """Break up runs of 3+ backticks so they cannot close a wrapping fence."""
    return _FENCE_RUN_RE.sub(lambda m: "​".join(m.group(0)), text)


def contains_instruction_marker(text: str) -> bool:
    """True if *text* contains a common prompt-injection-style marker."""
    return bool(_INSTRUCTION_MARKER_RE.search(text))


def neutralize_untrusted_text(text, max_len: int | None = None) -> str | None:
    """Return *text* safe to store/echo as inert data.

    - ``None`` passes through unchanged.
    - Non-string input is coerced with ``str()`` first.
    - Control characters are stripped.
    - Fence-lookalike sequences are broken up.
    - Result is truncated to ``max_len`` characters when given.
    """
    if text is None:
        return None
    text = strip_control_characters(str(text))
    text = neutralize_fence_lookalikes(text)
    if max_len is not None:
        text = text[:max_len]
    return text
