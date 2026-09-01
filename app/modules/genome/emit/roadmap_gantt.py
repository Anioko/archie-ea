"""Deterministic Jinja/string emitter: roadmap slice -> HTML gantt fragment.

Zero LLM. Given a slice dict from
``app.modules.genome.services.roadmap_slice.build_roadmap_slice``, renders a
transformation roadmap as a gantt-style table:

  - lanes    = plateaus (time-phased architecture states), plus an "Unassigned"
               lane for work packages with no plateau
  - bars     = work packages, positioned left..right across the slice's overall
               date range and shaded by status
  - every row (lane and bar) is provenance-linked via ``data-element-id`` and
    carries its ArchiMate origin (structural vs synthetic) so the reader can
    tell a real anchor from an honestly-absent one.

The emitter is pure: same slice dict -> byte-identical HTML string. It does not
touch Flask, the DB, or the network. Positioning uses inline ``style`` (CSP
allows style-src-attr) rather than Tailwind classes, so no CSS rebuild is
required and the design-tokens gate is unaffected.
"""
from __future__ import annotations

from datetime import date

from markupsafe import escape

# Shade intensity per work-package status. Values are the alpha applied to the
# bar hue in an inline style attribute.
_STATUS_ALPHA = {
    "completed": 0.85,
    "in_progress": 0.65,
    "planned": 0.40,
    "on_hold": 0.25,
    "cancelled": 0.15,
}
_DEFAULT_ALPHA = 0.40

# A single fixed hue for the bars so output is deterministic and theme-neutral.
_BAR_RGB = "37, 99, 235"


def _parse_iso(value):
    """Parse an ISO date string to a date, or None. Deterministic, no exceptions leak."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _status_alpha(status) -> float:
    return _STATUS_ALPHA.get(status, _DEFAULT_ALPHA)


def _date_bounds(work_packages: list) -> tuple:
    """Overall (min_start, max_end) across all dated work packages, or (None, None)."""
    starts, ends = [], []
    for w in work_packages:
        s = _parse_iso(w.get("start_date"))
        e = _parse_iso(w.get("target_date"))
        if s is not None:
            starts.append(s)
        if e is not None:
            ends.append(e)
        # A one-ended bar still contributes its known end to the bounds.
        if s is not None and e is None:
            ends.append(s)
        if e is not None and s is None:
            starts.append(e)
    if not starts or not ends:
        return (None, None)
    return (min(starts), max(ends))


def _bar_geometry(w: dict, lo: date, span_days: int) -> tuple:
    """(left_pct, width_pct) for a work package within [lo, lo+span_days], or None.

    Deterministic and clamped to [0, 100]. Returns None when the row cannot be
    positioned (no usable dates), so the caller renders it as unscheduled rather
    than fabricating a position.
    """
    s = _parse_iso(w.get("start_date"))
    e = _parse_iso(w.get("target_date"))
    if s is None and e is None:
        return None
    if s is None:
        s = e
    if e is None or e < s:
        e = s
    left = max(0.0, min(100.0, (s - lo).days / span_days * 100.0))
    right = max(0.0, min(100.0, (e - lo).days / span_days * 100.0))
    width = max(2.0, right - left)  # a floor so a same-day bar is visible
    if left + width > 100.0:
        left = max(0.0, 100.0 - width)
    return (left, width)


def _prov_attrs(prov: dict) -> str:
    """Provenance data-* attributes shared by lanes and bars."""
    origin = prov.get("origin", "unknown")
    eid = prov.get("archimate_element_id")
    atype = prov.get("archimate_type")
    return (
        f'data-provenance-origin="{escape(str(origin))}" '
        f'data-element-id="{escape("" if eid is None else str(eid))}" '
        f'data-archimate-type="{escape("" if atype is None else str(atype))}"'
    )


def _bar_html(w: dict, geom) -> str:
    prov = w["provenance"]
    status = w.get("status")
    pct = w.get("percent_complete") or 0
    alpha = _status_alpha(status)
    title = (
        f'{w["name"]} | status={status}, {pct}% complete | '
        f'{w.get("start_date") or "?"} -> {w.get("target_date") or "?"} | '
        f'{prov.get("origin")} element '
        f'#{prov.get("archimate_element_id") if prov.get("archimate_element_id") is not None else "—"}'
    )
    if w.get("closed_gap_ids"):
        title += f' | closes gaps {w["closed_gap_ids"]}'
    common = (
        f'data-work-package-id="{w["id"]}" '
        f'data-status="{escape(str(status))}" '
        f'data-percent-complete="{pct}" '
        f'{_prov_attrs(prov)} '
        f'title="{escape(title)}" aria-label="{escape(title)}"'
    )
    if geom is None:
        # Unscheduled: honest label, no fabricated position.
        return (
            '<div class="genome-roadmap-bar-unscheduled text-xs text-muted-foreground '
            f'py-1" {common}>'
            f'{escape(w["name"])} '
            '<span class="italic">(no dates)</span></div>'
        )
    left, width = geom
    return (
        '<div class="genome-roadmap-track" style="position: relative; height: 1.75rem; '
        'margin: 0.25rem 0;">'
        '<div class="genome-roadmap-bar" '
        f'style="position: absolute; left: {left:.2f}%; width: {width:.2f}%; '
        f'top: 0; height: 1.5rem; border-radius: 0.25rem; overflow: hidden; '
        f'background-color: rgba({_BAR_RGB}, {alpha:.2f});" '
        f'{common}>'
        f'<span style="display: block; padding: 0 0.375rem; line-height: 1.5rem; '
        f'white-space: nowrap; font-size: 0.7rem;" class="text-foreground">'
        f'{escape(w["name"])} &middot; {pct}%</span>'
        '</div></div>'
    )


def emit_roadmap_gantt_html(slice_dict: dict) -> str:
    """Render the roadmap slice to a deterministic HTML gantt fragment.

    Args:
        slice_dict: output of build_roadmap_slice (plateaus, work_packages,
            domain, spec_hash).

    Returns:
        An HTML string (plateau lanes with dated, status-shaded work-package
        bars). Deterministic: identical slice -> identical bytes.
    """
    plateaus = slice_dict.get("plateaus", [])
    work_packages = slice_dict.get("work_packages", [])
    domain = slice_dict.get("domain", "unknown")
    spec_hash = slice_dict.get("spec_hash", "")

    lo, hi = _date_bounds(work_packages)
    span_days = max(1, (hi - lo).days) if lo and hi else 1

    # Group work packages by plateau (None -> Unassigned lane). Input is already
    # deterministically ordered by the slice builder, so preserve that order.
    by_plateau = {}
    for w in work_packages:
        by_plateau.setdefault(w.get("plateau_id"), []).append(w)

    parts = []
    parts.append(
        f'<div class="genome-roadmap" '
        f'data-spec-hash="{escape(spec_hash)}" '
        f'data-domain="{escape(domain)}" '
        f'data-plateau-count="{len(plateaus)}" '
        f'data-work-package-count="{len(work_packages)}">'
    )

    window = (
        f'{lo.isoformat()} → {hi.isoformat()}' if lo and hi else 'no scheduled dates'
    )
    parts.append(
        '<div class="mb-4 text-sm text-muted-foreground">'
        f'Domain: <span class="font-medium text-foreground">{escape(domain)}</span> '
        f'&middot; {len(plateaus)} plateaus &middot; {len(work_packages)} work packages '
        f'&middot; window {escape(window)} '
        f'&middot; <span class="font-mono text-xs">{escape(spec_hash)}</span>'
        '</div>'
    )

    if not plateaus and not work_packages:
        parts.append(
            '<div class="p-6 text-center text-muted-foreground border border-border '
            'rounded-lg">No implementation-layer plateaus or work packages for this '
            'organization.</div>'
        )
        parts.append('</div>')
        return "".join(parts)

    parts.append('<div class="overflow-x-auto border border-border rounded-lg divide-y divide-border">')

    # One lane per plateau (in slice order), then the Unassigned lane last.
    lane_order = list(plateaus) + [None]
    for plateau in lane_order:
        if plateau is None:
            lane_wps = by_plateau.get(None, [])
            if not lane_wps:
                continue
            lane_label = "Unassigned"
            lane_meta = "work packages with no plateau"
            lane_attrs = 'data-plateau-id=""'
        else:
            lane_wps = by_plateau.get(plateau["id"], [])
            prov = plateau["provenance"]
            lane_label = plateau["name"]
            seq = plateau.get("sequence_order")
            tgt = plateau.get("target_date")
            lane_meta = (
                f'sequence {seq if seq is not None else "—"} '
                f'&middot; target {escape(tgt) if tgt else "—"} '
                f'&middot; {prov.get("origin")} element '
                f'#{prov.get("archimate_element_id") if prov.get("archimate_element_id") is not None else "—"}'
            )
            lane_attrs = f'data-plateau-id="{plateau["id"]}" {_prov_attrs(prov)}'

        parts.append(f'<div class="genome-roadmap-lane p-3" {lane_attrs}>')
        parts.append(
            '<div class="flex items-baseline justify-between mb-1">'
            f'<div class="font-medium text-foreground text-sm">{escape(lane_label)}</div>'
            f'<div class="text-xs text-muted-foreground">{lane_meta}</div>'
            '</div>'
        )
        if not lane_wps:
            parts.append(
                '<div class="text-xs text-muted-foreground italic py-1">'
                'No work packages assigned to this plateau.</div>'
            )
        else:
            for w in lane_wps:
                geom = _bar_geometry(w, lo, span_days) if lo and hi else None
                parts.append(_bar_html(w, geom))
        parts.append('</div>')

    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)
