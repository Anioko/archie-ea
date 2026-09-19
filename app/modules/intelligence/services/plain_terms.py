"""The one generator of the "in plain terms" sentence on a derived row.

The Provenance drawer, the Ask answers and the Twin map all show this
sentence, and the approved UX addendum binds it to the server: it is a
templating function here, never a client-side string build. This module is
therefore the ONLY place the sentence is assembled -- a static test
(``test_plain_terms.py``) fails if any other module, template or script in
the tree carries the same wording.

The shape (``ux-design-v1.md`` section 4.3, in the corrected form the T-004a
brief fixed):

    We worked this out because {A} depends on {B}, {N} hops away.

followed by ONE confidence clause:

    confidence >= 0.90          Very confident ({pct}%).
    0.70 <= confidence < 0.90   Fairly confident ({pct}%).
    confidence < 0.70           Worth a second look -- we are less confident ({pct}%).

Honesty rules, all deliberate:

* A missing confidence omits the clause entirely. It is never rendered as
  ``0%``: a 0 that means "not recorded" cannot be told apart from a measured
  zero.
* A missing name (another tenant's element, a deleted element) or a missing
  depth makes the WHOLE sentence ``None``. A sentence with a gap in it reads
  as a claim about something the caller cannot see; the consuming surface
  renders its absence state instead.
* The band is chosen from the stored confidence, and the percentage is that
  same value rounded half-up to a whole number, done in ``Decimal`` so the
  result does not depend on binary floating point.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

VERY_CONFIDENT_MIN = Decimal("0.90")
FAIRLY_CONFIDENT_MIN = Decimal("0.70")


def _as_decimal(confidence) -> Decimal:
    """``Decimal`` of a stored confidence (``float``/``Decimal``/``int``).

    Goes through ``str`` so ``0.82`` becomes ``Decimal("0.82")`` rather than
    the long binary expansion of the float. Anything else raises: a
    confidence that is not a number is a bug to surface, not a value to
    paper over.
    """
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float, Decimal)):
        raise TypeError(f"confidence must be a number or None, not {type(confidence).__name__}")
    return Decimal(str(confidence))


def _confidence_clause(confidence) -> Optional[str]:
    """The single confidence clause, or ``None`` when confidence is ``None``."""
    if confidence is None:
        return None
    value = _as_decimal(confidence)
    pct = int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if value >= VERY_CONFIDENT_MIN:
        return f"Very confident ({pct}%)."
    if value >= FAIRLY_CONFIDENT_MIN:
        return f"Fairly confident ({pct}%)."
    return f"Worth a second look — we are less confident ({pct}%)."


def _usable_name(name) -> Optional[str]:
    if not isinstance(name, str):
        return None
    return name if name.strip() else None


def plain_terms_sentence(
    *,
    dependent_name: Optional[str],
    dependency_name: Optional[str],
    depth: Optional[int],
    confidence,
) -> Optional[str]:
    """The plain-terms sentence for one derived row, or ``None``.

    ``dependent_name`` is ``{A}`` and ``dependency_name`` is ``{B}``: both
    come from the identity map ``cross_layer_impact`` builds for the same
    response, so a name is only ever one the caller's tenant can see.
    ``depth`` is ``{N}``, the derived row's own ``relation.depth``.
    """
    a = _usable_name(dependent_name)
    b = _usable_name(dependency_name)
    if a is None or b is None:
        return None
    if isinstance(depth, bool) or not isinstance(depth, int):
        return None

    sentence = f"We worked this out because {a} depends on {b}, {depth} hops away."
    clause = _confidence_clause(confidence)
    if clause is not None:
        sentence = f"{sentence} {clause}"
    return sentence


__all__ = ["plain_terms_sentence"]
