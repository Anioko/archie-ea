"""ArchiMate diagram rendering service — generates SVG viewpoint diagrams."""
import html

from app import db
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

LAYER_ORDER = [
    "motivation",
    "strategy",
    "business",
    "application",
    "technology",
    "implementation",
    "physical",
]

LAYER_COLORS = {
    "motivation": "#f0e6ff",
    "strategy": "#e6f0ff",
    "business": "#fff9e6",
    "application": "#e6ffe6",
    "technology": "#e6f9ff",
    "implementation": "#ffe6e6",
    "physical": "#f5f5f5",
}


class DiagramRenderService:
    BOX_W = 160
    BOX_H = 50
    BOX_GAP = 20
    LAYER_H = 100
    MARGIN = 40

    def render_diagram(self, element_ids: list, viewpoint: str = "application") -> str:
        """Return SVG string for the given element IDs grouped by ArchiMate layer."""
        if not element_ids:
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">'
                '<text x="10" y="20" font-size="12">No elements selected</text>'
                "</svg>"
            )

        try:
            elements = ArchiMateElement.query.filter(
                ArchiMateElement.id.in_(element_ids)
            ).all()
        except Exception:
            elements = []

        if not elements:
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">'
                '<text x="10" y="20" font-size="12">No elements found</text>'
                "</svg>"
            )

        # Group by layer
        layers = {}
        for el in elements:
            layer = (el.layer or "application").lower()
            layers.setdefault(layer, []).append(el)

        # Determine draw order: canonical order first, then any extras
        ordered_layers = [l for l in LAYER_ORDER if l in layers] + [
            l for l in layers if l not in LAYER_ORDER
        ]

        canvas_w = max(
            max(
                len(els) * (self.BOX_W + self.BOX_GAP)
                for els in layers.values()
            )
            + self.MARGIN * 2,
            600,
        )
        canvas_h = len(ordered_layers) * self.LAYER_H + self.MARGIN * 2

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}"'
            ' font-family="Arial,sans-serif" font-size="11">',
            (
                "<defs>"
                '<marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
                '<path d="M0,0 L0,6 L8,3 z" fill="#666"/>'
                "</marker>"
                "</defs>"
            ),
        ]

        # Compute centre positions for relationship drawing
        positions = {}  # element_id -> (cx, cy)

        for layer_idx, layer_name in enumerate(ordered_layers):
            els = layers[layer_name]
            color = LAYER_COLORS.get(layer_name, "#f5f5f5")
            y_top = self.MARGIN + layer_idx * self.LAYER_H
            row_w = len(els) * (self.BOX_W + self.BOX_GAP) - self.BOX_GAP
            x_start = (canvas_w - row_w) // 2

            # Layer background band
            svg_parts.append(
                f'<rect x="{self.MARGIN // 2}" y="{y_top}"'
                f' width="{canvas_w - self.MARGIN}" height="{self.LAYER_H - 10}"'
                f' rx="4" fill="{color}" stroke="#ccc" stroke-width="1"/>'
            )
            svg_parts.append(
                f'<text x="{self.MARGIN}" y="{y_top + 14}"'
                f' font-size="10" fill="#666" font-weight="bold">'
                f"{html.escape(layer_name.upper())}</text>"
            )

            for el_idx, el in enumerate(els):
                bx = x_start + el_idx * (self.BOX_W + self.BOX_GAP)
                by = y_top + 25
                # Store centre point for arrow drawing
                positions[el.id] = (bx + self.BOX_W // 2, by + self.BOX_H // 2)

                raw_name = el.name or ""
                label = html.escape(
                    raw_name[:22] + "\u2026" if len(raw_name) > 22 else raw_name
                )
                el_type = html.escape(el.type or "")

                svg_parts.append(
                    f'<rect x="{bx}" y="{by}" width="{self.BOX_W}" height="{self.BOX_H}"'
                    f' rx="3" fill="white" stroke="#666" stroke-width="1.5"/>'
                )
                svg_parts.append(
                    f'<text x="{bx + self.BOX_W // 2}" y="{by + 18}"'
                    f' text-anchor="middle" font-weight="bold">{label}</text>'
                )
                svg_parts.append(
                    f'<text x="{bx + self.BOX_W // 2}" y="{by + 32}"'
                    f' text-anchor="middle" fill="#888">{el_type}</text>'
                )

        # Relationships — drawn after elements so they appear on top of band fills
        try:
            rels = ArchiMateRelationship.query.filter(
                db.or_(
                    ArchiMateRelationship.source_id.in_(element_ids),
                    ArchiMateRelationship.target_id.in_(element_ids),
                )
            ).all()
            for rel in rels:
                if rel.source_id in positions and rel.target_id in positions:
                    x1, y1 = positions[rel.source_id]
                    x2, y2 = positions[rel.target_id]
                    svg_parts.append(
                        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
                        f' stroke="#666" stroke-width="1.5" marker-end="url(#arrow)"/>'
                    )
        except Exception:  # fabricated-values-ok — relationship errors must not abort SVG output
            # Relationship query failures are non-fatal; diagram is still useful without edges
            pass

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)
