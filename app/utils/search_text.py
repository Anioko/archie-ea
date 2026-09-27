"""Spelling-blind text comparison, shared by every search surface.

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

# A query is typed one character at a time, so it is very often a PREFIX of a full word, not the word
# itself -- "licenc" while typing "licence". The two spellings diverge partway through ("licen" then
# "c" vs "s"), so folding only the complete British word left every prefix from the divergence point up
# to (but not including) the final character unfoldable: "licenc" stayed "licenc", which is not a
# substring of the folded label "licenses", and the box reported "No pages match" mid-word on exactly
# the words this feature exists to fix. Folding every prefix of the British spelling to the
# same-length prefix of the American spelling covers it: prefixes before the divergence point are
# identical in both spellings anyway (folding is a no-op there), and prefixes at or past it map to the
# American prefix, which the folded label's American form always starts with.
_PREFIX_PAIRS = [
    (british[:n], american[:n])
    for british, american in _VARIANT_PAIRS
    for n in range(len(british), 0, -1)
]
# Longest alternative first: re's alternation takes the first match at each position, not the longest,
# so a shorter prefix listed before a longer one would shadow it (e.g. "licen" matching before "licence").
_VARIANT_RE = re.compile(
    "|".join(re.escape(british) for british, _ in sorted(_PREFIX_PAIRS, key=lambda p: -len(p[0]))),
    re.IGNORECASE,
)
_CANONICAL = dict(_PREFIX_PAIRS)


def _fold(match: "re.Match[str]") -> str:
    return _CANONICAL[match.group(0).lower()]


def normalise_search_text(text: str) -> str:
    """Lowercase `text` and fold every known British spelling variant to its American form."""
    return _VARIANT_RE.sub(_fold, text.lower())
