"""All-modules directory (shell-overhaul Wave 1, Task 3 fix round).

The sidebar diet (persona zones, <=~26 links) moved dozens of real, working
routes out of the DOM for most roles. The design's own long-tail answer for
"but I need the thing that isn't in my persona's zones" was Ctrl-K search
(not yet wired to an event — see admin_sidebar.html) plus a flat, searchable
directory page reachable from every role. This blueprint is that page: every
link from every role's SIDEBAR_ZONES, deduplicated, plus a curated "More
tools" section for routes that were never in any zone at all.

See docs/superpowers/specs/2026-08-12-shell-overhaul-design.md section 1
("Library ... the long tail: Ctrl-K global search + one new 'All modules'
directory page").
"""

from flask import Blueprint

modules_directory_bp = Blueprint(
    "modules_directory",
    __name__,
    url_prefix="/modules",
    template_folder="templates",
)

from . import routes  # noqa: F401, E402
