#!/usr/bin/env python
"""A second implementation of something the tree already has, caught early.

The 20 Sep 2026 Fortune 500 readiness review found two drawing engines for one
model, four implementations of "combine a chain of relationships into one
type", and two macros named ``empty_state`` with incompatible signatures --
each built beside what already existed because nobody searching for the job
found the earlier answer first. ``docs/reuse-register.yml`` is the list of
canonical answers; this script is the ratchet that keeps a second answer from
being added beside one that is already registered.

This first pass implements two rules only:

RG-1 macro-names
    A Jinja macro name defined in more than one template file. One finding
    per NAME that has two or more distinct defining files (not one per file):
    a name in three files is still a single finding, because the fix is one
    decision -- pick the canonical file -- not three.

RG-2 diagram-libraries
    A template or script that loads a diagram-drawing vendor library
    (joint/d3/dagre/mermaid/cytoscape/drawflow) outside the pages of the
    canonical ArchiMate renderer. One finding per (file, library) pair; a
    page that also names ``archimate/composer_renderer.js`` may load
    ``joint`` and ``dagre`` (the canonical renderer is built on them) without
    being flagged.

Both patterns, scopes and exclusions below are the same ones recorded in
``docs/reuse-register.yml``'s ``rules:`` block -- kept in step by hand, since
the register's ``scope``/``excluded`` fields mix glob-like paths with plain
English ("not app/static/") that is written for a person to read, not a
parser to execute. The register's structured ``concepts:`` list (canonical
path and one-line use) IS read at run time, to fill in the "Already exists"
half of a finding's message when a duplicated name or a loaded library
resolves to a registered concept.

Escape hatch: a line carrying ``reuse-ok: <concept-id> <reason>`` is excluded
from both rules, matching the marker the register itself defines.

Further rules (RG-3 through RG-9, and the register-integrity check RG-0) are
out of scope for this script's first version; see the register's own
``rules:`` block for their definitions when they are added.

Usage:
    python scripts/check_reuse.py --rule RG-1
    python scripts/check_reuse.py --rule RG-1 --count [--root <tree>]
    python scripts/check_reuse.py --rule RG-2 --count [--root <tree>]
    python scripts/check_reuse.py --summary [--root <tree>]

Proven-against: a synthetic tree with a second ``{% macro empty_state( %}``
in a second template -- red at 1 naming both files, green at 0 with the
second file removed; and a synthetic template loading
``vendor/d3.min.js`` with no ``archimate/composer_renderer.js`` reference
anywhere in the tree -- red at 1, green at 0 once the reference is added.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is pinned in requirements.txt
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The one marker name the register defines for every rule (docs/reuse-register.yml's
# top-level `marker:` field), not a per-rule name -- a builder only has to
# remember one escape-hatch spelling.
MARKER = re.compile(r"reuse-ok:[ \t]*\S")

RULE_NAMES = {"RG-1": "macro-names", "RG-2": "diagram-libraries"}
BASELINE_KEYS = {"RG-1": "reuse_macro_names", "RG-2": "reuse_diagram_libraries"}

# ---------------------------------------------------------------- RG-1: macro-names

MACRO_PATTERN = re.compile(r"\{%-?\s*macro\s+([A-Za-z]\w*)\s*\(")
MACRO_SCOPE_EXTS = (".html", ".j2", ".jinja")
# "node_modules, vendor, bundles" and the generated-code templates, per the
# register's RG-1 `excluded` list. Names beginning with `_` are already
# excluded by MACRO_PATTERN itself (it requires a letter first).
MACRO_EXCLUDED = ("node_modules/", "vendor/", "bundles/", "app/modules/solutions_product/templates/")

# ---------------------------------------------------------------- RG-2: diagram-libraries

DIAGRAM_LIB_PATTERN = re.compile(
    r"vendor/(joint|d3|dagre|mermaid|cytoscape[\w.\-]*|drawflow[\w.\-]*?)(?:\.min)?\.js"
)
DIAGRAM_EXCLUDED = ("vendor/", "bundles/", "solutions_product")
COMPOSER_RENDERER_REF = "archimate/composer_renderer.js"
COMPOSER_ALLOWED_LIBS = {"joint", "dagre"}


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _walk_files(root: str, under: str, exts: tuple[str, ...]):
    base = os.path.join(root, *under.split("/"))
    if not os.path.isdir(base):
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", ".git"))
        for filename in sorted(filenames):
            if filename.endswith(exts):
                path = os.path.join(dirpath, filename)
                yield path, _rel(root, path)


def _excluded(rel: str, substrings: tuple[str, ...]) -> bool:
    return any(s in rel for s in substrings)


# ---------------------------------------------------------------- register lookups


def _load_register(root: str) -> dict:
    path = os.path.join(root, "docs", "reuse-register.yml")
    if yaml is None or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return {}
    return data or {}


def _concepts_for_rule(register: dict, rule_id: str) -> list[dict]:
    return [c for c in (register.get("concepts") or []) if rule_id in (c.get("rules") or [])]


def _concept_for_macro(register: dict, name: str) -> dict | None:
    """A concept whose canonical.use names this macro as a call, e.g. 'empty_state('."""
    for concept in _concepts_for_rule(register, "RG-1"):
        use = ((concept.get("canonical") or {}).get("use")) or ""
        if re.search(r"\b%s\s*\(" % re.escape(name), use):
            return concept
    return None


def _concept_for_diagram(register: dict) -> dict | None:
    concepts = _concepts_for_rule(register, "RG-2")
    return concepts[0] if concepts else None


def _load_baseline(root: str) -> dict:
    path = os.path.join(root, "verification_baseline.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data.get("ratchets", {})


# ---------------------------------------------------------------- message format


def _format_finding(rule: str, path: str, line: int, concept_id: str, what: str,
                     canonical_path: str, canonical_use: str) -> str:
    rule_name = RULE_NAMES[rule]
    return (
        "%s:%d [reuse:%s/%s] %s.\n"
        "  Already exists: %s -- %s\n"
        "  Do one of: (1) use the existing one; (2) if this is a genuinely different job, "
        "add it under allowed_specialisations for\n"
        "  '%s' in docs/reuse-register.yml with a reason and the role that accepted it; "
        "(3) append 'reuse-ok: %s <reason>' to this line."
        % (path, line, rule_name, concept_id, what, canonical_path, canonical_use,
           concept_id, concept_id)
    )


# ---------------------------------------------------------------- RG-1 scan


def scan_rg1(root: str) -> list[str]:
    register = _load_register(root)
    by_name: dict[str, dict[str, int]] = {}
    for path, rel in _walk_files(root, "app", MACRO_SCOPE_EXTS):
        if _excluded(rel, MACRO_EXCLUDED):
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            match = MACRO_PATTERN.search(line)
            if not match:
                continue
            if MARKER.search(line):
                continue
            name = match.group(1)
            # A file defining the same macro name twice is a redefinition
            # (ruff F811's job); only the first definition per file counts
            # toward how many DISTINCT files carry this name.
            by_name.setdefault(name, {}).setdefault(rel, lineno)

    findings = []
    for name in sorted(by_name):
        locations = by_name[name]
        if len(locations) < 2:
            continue
        findings.append(_rg1_finding(name, locations, _concept_for_macro(register, name)))
    return findings


def _rg1_finding(name: str, locations: dict[str, int], concept: dict | None) -> str:
    files = sorted(locations)
    canonical_path = None
    if concept:
        for candidate in (concept.get("canonical") or {}).get("paths") or []:
            if candidate in locations:
                canonical_path = candidate
                break
    if canonical_path is None:
        canonical_path = files[0]

    non_canonical = [f for f in files if f != canonical_path]
    flagged = non_canonical[0]
    flagged_line = locations[flagged]
    other_files = [f for f in files if f != flagged]
    also_defined_in = ", ".join("%s:%d" % (f, locations[f]) for f in other_files)

    if concept:
        concept_id = concept["id"]
        canonical_use = (concept.get("canonical") or {}).get("use", canonical_path)
    else:
        concept_id = "unregistered"
        canonical_use = "first defined at %s:%d" % (canonical_path, locations[canonical_path])

    what = "macro '%s' is also defined in %s" % (name, also_defined_in)
    return _format_finding("RG-1", flagged, flagged_line, concept_id, what,
                            canonical_path, canonical_use)


# ---------------------------------------------------------------- RG-2 scan


def scan_rg2(root: str) -> list[str]:
    register = _load_register(root)
    concept = _concept_for_diagram(register)

    candidates = []
    for path, rel in _walk_files(root, "app", (".html",)):
        if rel.startswith("app/static/"):
            continue
        if _excluded(rel, DIAGRAM_EXCLUDED):
            continue
        candidates.append((path, rel))
    for path, rel in _walk_files(root, "app/static/js", (".js",)):
        if _excluded(rel, DIAGRAM_EXCLUDED):
            continue
        candidates.append((path, rel))

    seen: set[tuple[str, str]] = set()
    findings = []
    for path, rel in candidates:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        composer_page = COMPOSER_RENDERER_REF in text
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = DIAGRAM_LIB_PATTERN.search(line)
            if not match:
                continue
            if MARKER.search(line):
                continue
            lib = re.split(r"[.\-]", match.group(1))[0]
            if lib in COMPOSER_ALLOWED_LIBS and composer_page:
                continue
            key = (rel, lib)
            if key in seen:
                continue
            seen.add(key)
            findings.append(_rg2_finding(rel, lineno, lib, concept))
    findings.sort()
    return findings


def _rg2_finding(rel: str, lineno: int, lib: str, concept: dict | None) -> str:
    if concept:
        concept_id = concept["id"]
        canonical = concept.get("canonical") or {}
        canonical_path = (canonical.get("paths") or [None])[0] or \
            "app/static/js/archimate/composer_renderer.js"
        canonical_use = canonical.get("use", "ComposerRenderer.create(...)")
    else:
        concept_id = "unregistered"
        canonical_path = "app/static/js/archimate/composer_renderer.js"
        canonical_use = "ComposerRenderer.create(containerEl, { mode: 'view' }) draws elements and relationships"

    what = "loads vendor/%s.min.js; model diagrams are drawn by the ArchiMate renderer" % lib
    return _format_finding("RG-2", rel, lineno, concept_id, what, canonical_path, canonical_use)


SCANNERS = {"RG-1": scan_rg1, "RG-2": scan_rg2}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rule", choices=sorted(SCANNERS), help="which rule to run (RG-1 or RG-2)")
    parser.add_argument("--count", action="store_true", help="print only the finding count")
    parser.add_argument("--root", default=ROOT, help="scan this tree instead of the real repository")
    parser.add_argument("--summary", action="store_true",
                         help="print every rule's count against its baseline")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)

    if args.summary:
        baseline = _load_baseline(root)
        for rule in sorted(SCANNERS):
            count = len(SCANNERS[rule](root))
            base = baseline.get(BASELINE_KEYS[rule])
            state = "no baseline recorded" if base is None else ("ok" if count <= base else "OVER baseline")
            print("%s (%s): %d finding(s), baseline %s -- %s"
                  % (rule, RULE_NAMES[rule], count, base if base is not None else "?", state))
        return 0

    if not args.rule:
        parser.error("--rule RG-1|RG-2 is required unless --summary is given")

    findings = SCANNERS[args.rule](root)

    if not args.count:
        for finding in findings:
            print(finding)
            print()
        baseline = _load_baseline(root).get(BASELINE_KEYS[args.rule])
        baseline_text = str(baseline) if baseline is not None else "not set"
        print("%d finding(s); baseline %s. The count may fall, not rise."
              % (len(findings), baseline_text))
    print(len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
