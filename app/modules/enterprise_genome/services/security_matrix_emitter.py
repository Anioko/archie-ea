"""
Enterprise Genome — SECURITY slice deterministic Jinja emitter.

Renders a SECURITY genome slice (see ``security_slice.build_security_slice``)
into a control-to-requirement matrix / SOC 2 evidence table as an HTML fragment.

ZERO LLM. Pure Jinja over a fixed template with autoescape on. The output is a
deterministic function of the slice dict, so a byte-identical slice renders a
byte-identical fragment — the property an auditor's evidence pack depends on.

The emitter owns its own Jinja ``Environment`` (a FileSystemLoader on this
module's ``templates/`` dir) so it renders without a Flask request context —
callable from the route, from a test, or from a CLI export identically.
"""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_TEMPLATE_NAME = "control_matrix.html.j2"

# Built once; autoescape ON (values are user/model data). keep_trailing_newline
# and lstrip/trim settings are pinned so rendering is deterministic.
_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def render_control_matrix(slice_dict: dict) -> str:
    """Render a SECURITY slice into the control-to-requirement matrix fragment.

    Args:
        slice_dict: the envelope returned by ``build_security_slice``.

    Returns:
        An HTML fragment (str). Deterministic for a given slice.
    """
    template = _ENV.get_template(_TEMPLATE_NAME)
    return template.render(slice=slice_dict)
