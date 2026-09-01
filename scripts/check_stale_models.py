"""Gate: no RETIRED LLM model id may appear in shipped code.

app/modules/ai_chat/services/model_defaults.py documents the exact defect this
gate prevents from regressing: retired Anthropic/Google model ids that had
drifted into six places and now return 404, and priced-but-retired ids that made
cost reporting fiction. DEFAULT_MODELS is now the single source of truth; this
gate keeps a retired id from creeping back into the tree.

A retired id is allowed to appear ONLY in the documentation that names it as
retired (model_defaults.py's docstring, and this file), each carrying the
`stale-model-ok` marker's spirit — those two files are excluded by path.

Exit non-zero (with the offending file:line) if a retired id appears anywhere
else. Ratchet @ 0 in verify.py.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

# Ids documented as retired/deprecated (returning 404 or deprecated) as of the
# model_defaults.py cleanup. Keep in step with that file when a model retires.
RETIRED = [
    "claude-3-5-sonnet-20241022",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku-20240307",
    "claude-2.1",
    "claude-2.0",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gpt-4-32k",
    "gpt-3.5-turbo-0301",
]
PATTERN = re.compile("|".join(re.escape(m) for m in RETIRED))

# Files that legitimately NAME retired ids (as documentation of the retirement).
EXCLUDE_PATHS = {
    "app/modules/ai_chat/services/model_defaults.py",
    "scripts/check_stale_models.py",
    # This test IS the retired-model enforcement — it carries its own RETIRED
    # denylist and asserts those ids never reappear as a default or as guidance,
    # so it names them deliberately (a live stale USE here would fail the test).
    "tests/test_ai_chat_models.py",
}
SCAN_EXT = {".py", ".html", ".js", ".j2", ".jinja", ".json", ".yaml", ".yml", ".md"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".worktrees", ".claude", "migrations"}

def main() -> int:
    count_only = "--count" in sys.argv
    root = Path(".").resolve()
    hits = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in SCAN_EXT:
            continue
        rel_parts = path.relative_to(root).parts
        # Check skip-dirs against the path RELATIVE to root — the absolute root
        # itself may sit under a dir named in SKIP_DIRS (e.g. a .worktrees
        # checkout), which would otherwise skip every file in the tree.
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in EXCLUDE_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "stale-model-ok" in line:
                continue
            m = PATTERN.search(line)
            if m:
                hits.append(f"{rel}:{i}: retired model id '{m.group(0)}' — {line.strip()[:90]}")
    if count_only:
        print(len(hits))
        return 1 if hits else 0
    for h in hits:
        print(h)
    print(f"\n{len(hits)} retired-model reference(s).")
    if hits:
        print("A retired id 404s in production. Use a current id from DEFAULT_MODELS, "
              "or append 'stale-model-ok' if the line legitimately documents a retirement.")
    return 1 if hits else 0

if __name__ == "__main__":
    sys.exit(main())
