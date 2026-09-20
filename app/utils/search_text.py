"""Spelling-blind text comparison, shared by every search surface (T-302).

The product's own copy is en-GB ("Licences", "Organisation"), but a user typing from habit may type
either spelling. `normalise_search_text` folds both directions of the four variant pairs this product's
labels are known to use, so `normalise_search_text(query) in normalise_search_text(label)` is spelling-blind
for those words without touching anything else. Add a pair here, not a special case at each call site.
"""
import re

# (British, American) pairs. Both spellings fold to the American form purely as a stable choice; nothing
# reads the canonical form itself, only compares it, so which side is "canonical" carries no meaning.
_VARIANT_PAIRS = [
    ("licence", "license"),
    ("organisation", "organization"),
    ("programme", "program"),
    ("rationalisation", "rationalization"),
]

_VARIANT_RE = re.compile(
    "|".join(re.escape(british) for british, _ in _VARIANT_PAIRS), re.IGNORECASE
)
_CANONICAL = {british: american for british, american in _VARIANT_PAIRS}


def _fold(match: "re.Match[str]") -> str:
    return _CANONICAL[match.group(0).lower()]


def normalise_search_text(text: str) -> str:
    """Lowercase `text` and fold every known British spelling variant to its American form."""
    return _VARIANT_RE.sub(_fold, text.lower())
