"""Gateway bypass enumeration -- AST-based scanning.

Scans the codebase with the `ast` module for:
1. Provider SDK constructors: `OpenAI(`, `Anthropic(`, `genai.GenerativeModel`,
   `SentenceTransformer(`
2. Provider SDK calls: `.chat.completions.create`, `.messages.create`, `.embeddings.create`
3. Gateway bypass calls: `LLMService._call_<provider>(` and
   `_call_llm_with_failover(` outside llm_service_impl.py

Every bypass site must be accounted for in `EXPECTED_BYPASSES` or the
gateway file. A site not listed is a defect.
"""

from __future__ import annotations

import ast
import importlib.util
import shutil
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Gateway / exempt files
# ---------------------------------------------------------------------------

GATEWAY_FILES = {
    "app/modules/ai_chat/services/llm_service_impl.py",
}

# Directories that are not real application code
SKIP_DIR_PREFIXES = (
    "code_templates/",
    "migrations/",
)

# Files that still contain direct model calls pending remediation
R1_BYPASS_FILES = {
    "app/modules/ai_chat/services/agent_runner.py",
    "app/modules/ai_chat/services/multi_domain_chat_service.py",
    "app/modules/ai_chat/services/ai_chat_multi_model.py",
}

# ---------------------------------------------------------------------------
# Expected bypass site list
#
# Each entry: (file_path, pattern, expected_count, description)
#   file_path       -- relative path from repo root
#   pattern         -- the call expression label (e.g. "OpenAI(", ".messages.create")
#   expected_count  -- how many times this pattern appears in the file
#   description     -- plain-text explanation of the work that will remove the call
#
# Line numbers are NOT used. The check matches on (file_path, pattern) only,
# so adding blank lines or reordering code within a file does not break it.
# ---------------------------------------------------------------------------

EXPECTED_BYPASSES = [
    # Provider SDK constructors - assistant agent work
    ("app/modules/ai_chat/services/agent_runner.py", "OpenAI(", 2, "assistant agent work"),
    ("app/modules/ai_chat/services/agent_runner.py", "Anthropic(", 2, "assistant agent work"),
    # Provider SDK constructors - multi-model chat service
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", "OpenAI(", 1, "multi-model chat service"),
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", "Anthropic(", 1, "multi-model chat service"),
    # Provider SDK constructors - multi-domain chat service
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", "OpenAI(", 1, "multi-domain chat service"),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", "Anthropic(", 1, "multi-domain chat service"),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", "genai.GenerativeModel", 1, "multi-domain chat service"),
    # Provider SDK constructors - inference provider setup
    ("app/modules/architecture/services/inference_providers.py", "Anthropic(", 1, "inference provider setup"),
    ("app/modules/architecture/services/inference_providers.py", "OpenAI(", 1, "inference provider setup"),
    # Provider SDK constructors - vector embedding service
    ("app/services/vector_embedding_service.py", "OpenAI(", 1, "vector embedding service"),
    ("app/services/vector_embedding_service.py", "SentenceTransformer(", 2, "vector embedding service"),
    # Provider SDK constructors - pgvector embedding service
    ("app/services/pgvector_embedding_service.py", "SentenceTransformer(", 1, "pgvector embedding service"),
    # Provider SDK constructors - chromadb embedding service
    ("app/services/chromadb_apqc_service.py", "SentenceTransformer(", 1, "chromadb embedding service"),
    # Provider SDK constructors - faiss embedding service
    ("app/services/faiss_apqc_service.py", "SentenceTransformer(", 1, "faiss embedding service"),
    # Provider SDK constructors - semantic vendor discovery
    ("app/modules/vendors/services/semantic_vendor_discovery.py", "SentenceTransformer(", 1, "semantic vendor discovery"),
    # Provider SDK constructors - conversation history embedding
    ("app/services/conversation_history.py", "SentenceTransformer(", 1, "conversation history embedding"),
    # Provider SDK constructors - duplicate detection embedding
    ("app/modules/duplicate_detection/services/ai_duplicate_detection_service.py", "SentenceTransformer(", 1, "duplicate detection embedding"),
    # Provider SDK constructors - semantic discovery embedding
    ("app/modules/ai_chat/services/ai_semantic_discovery_service.py", "SentenceTransformer(", 1, "semantic discovery embedding"),
    # Provider SDK constructors - mapping routes embedding
    ("app/modules/capabilities/routes/mapping_routes.py", "SentenceTransformer(", 1, "mapping routes embedding"),
    # Provider SDK calls - assistant agent work
    ("app/modules/ai_chat/services/agent_runner.py", ".messages.create", 1, "assistant agent work"),
    ("app/modules/ai_chat/services/agent_runner.py", ".chat.completions.create", 2, "assistant agent work"),
    # Provider SDK calls - multi-model chat service
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", ".chat.completions.create", 1, "multi-model chat service"),
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", ".messages.create", 1, "multi-model chat service"),
    # Provider SDK calls - multi-domain chat service
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", ".chat.completions.create", 1, "multi-domain chat service"),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", ".messages.create", 1, "multi-domain chat service"),
    # Provider SDK calls - inference provider setup
    ("app/modules/architecture/services/inference_providers.py", ".messages.create", 1, "inference provider setup"),
    ("app/modules/architecture/services/inference_providers.py", ".chat.completions.create", 1, "inference provider setup"),
    # Provider SDK calls - vector embedding service
    ("app/services/vector_embedding_service.py", ".embeddings.create", 1, "vector embedding service"),
    # Gateway bypass - _call_llm_with_failover outside llm_service_impl
    ("app/modules/ai_chat/services/agent_runner.py", "_call_llm_with_failover", 1, "assistant agent work"),
    ("app/services/technology_analyzer.py", "_call_llm_with_failover", 2, "technology analyzer gateway bypass"),
    ("app/services/capability_design_composition_service.py", "_call_llm_with_failover", 1, "capability design composition gateway bypass"),
    ("app/services/intelligent_analyzer.py", "_call_llm_with_failover", 1, "intelligent analyzer gateway bypass"),
    ("app/modules/applications/services/application_architecture_mapper.py", "_call_llm_with_failover", 1, "application architecture mapper gateway bypass"),
    ("app/modules/applications/services/application_capability_mapper.py", "_call_llm_with_failover", 1, "application capability mapper gateway bypass"),
]

# ---- helpers ------------------------------------------------------------

def _should_skip_path(rel):
    if rel.startswith("tests/") or rel.startswith("."):
        return True
    if "/tests/" in rel:
        return True
    for prefix in SKIP_DIR_PREFIXES:
        if rel.startswith(prefix):
            return True
    parts = Path(rel).parts
    if any(p in ("__pycache__", "node_modules", "venv", ".venv") for p in parts):
        return True
    return False


def _resolve_call_target(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _resolve_call_target(node.value)
        if base is None:
            return None
        return base + "." + node.attr
    return None


def _is_openai_constructor(name):
    return name == "OpenAI" or name == "openai.OpenAI"


def _is_anthropic_constructor(name):
    return name == "Anthropic" or name == "anthropic.Anthropic"


def _is_genai_generative_model(name):
    return name == "genai.GenerativeModel"


def _is_sentence_transformer(name):
    if name == "SentenceTransformer":
        return True
    if name == "_SentenceTransformer":
        return True
    return name.endswith(".SentenceTransformer")


SDK_CONSTRUCTOR_PATTERNS = [
    ("OpenAI(", _is_openai_constructor),
    ("Anthropic(", _is_anthropic_constructor),
    ("genai.GenerativeModel", _is_genai_generative_model),
    ("SentenceTransformer(", _is_sentence_transformer),
]

SDK_CALL_PATTERNS = [
    ".chat.completions.create",
    ".messages.create",
    ".embeddings.create",
]

GATEWAY_BYPASS_FNS = [
    "_call_llm_with_failover",
]

LLMSERVICE_PROVIDER_CALLS = [
    "LLMService._call_openi",
    "LLMService._call_anthropic",
    "LLMService._call_gemini",
    "LLMService._call_deepsek",
    "LLMService._call_huggingface",
    "LLMSerice._call_openruter",
]


def scan_file(file_path, rel):
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target = _resolve_call_target(func)
        if target is None:
            continue
        # Check SDK constructors
        for label, check_fn in SDK_CONSTRUCTOR_PATTERNS:
            if check_fn(target):
                results.append((rel, node.lineno, label))
                break
        # Check gateway bypass fns
        for gwfn in GATEWAY_BYPASS_FNS:
            if target.endswith(gwfn):
                results.append((rel, node.lineno, gwfn))
                break
        # Check LLMService._call_<provider>
        for prov in LLMSERVICE_PROVIDER_CALLS:
            if target == prov:
                results.append((rel, node.lineno, prov))
                break
        # Check SDK method calls
        for pat in SDK_CALL_PATTERNS:
            if target.endswith(pat):
                results.append((rel, node.lineno, pat))
                break
    return results


def discover_bypass_sites():
    all_results = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _should_skip_path(rel):
            continue
        if rel in GATEWAY_FILES:
            continue
        sites = scan_file(path, rel)
        all_results.extend(sites)
    return all_results


def _build_expected_lookup():
    """Build {(file, pattern): expected_count} from EXPECTED_BYPASSES."""
    lookup = {}
    for entry in EXPECTED_BYPASSES:
        key = (entry[0], entry[1])
        lookup[key] = entry[2]
    return lookup


def _group_discovered(discovered):
    """Group discovered sites by (file, pattern) and return {(file, pattern): count}."""
    grouped = {}
    for rel, lineno, pattern in discovered:
        key = (rel, pattern)
        grouped[key] = grouped.get(key, 0) + 1
    return grouped


# ---- tests ----------------------------------------------------------


def test_no_unaccounted_bypasses():
    discovered = discover_bypass_sites()
    discovered_grouped = _group_discovered(discovered)
    expected_lookup = _build_expected_lookup()

    unaccounted = []
    for key, count in discovered_grouped.items():
        if key not in expected_lookup:
            unaccounted.append((key[0], key[1], count))
    assert unaccounted == [], (
        "Unaccounted bypass site(s) not in EXPECTED_BYPASSES:\n"
        + "\n".join(f"  {f}:{p} (count={c})" for f, p, c in unaccounted)
    )


def test_known_bypasses_still_present():
    discovered = discover_bypass_sites()
    discovered_grouped = _group_discovered(discovered)

    mismatches = []
    for entry in EXPECTED_BYPASSES:
        key = (entry[0], entry[1])
        expected_count = entry[2]
        actual_count = discovered_grouped.get(key, 0)
        if actual_count != expected_count:
            mismatches.append((entry[0], entry[1], expected_count, actual_count, entry[3]))
    assert mismatches == [], (
        "Expected bypass site count mismatch -- "
        "update EXPECTED_BYPASSES if refactored:\n"
        + "\n".join(
            f"  {f}:{p} expected={e} actual={a} ({d})"
            for f, p, e, a, d in mismatches
        )
    )


def test_r1_bypasses_are_xfail():
    discovered = discover_bypass_sites()
    discovered_grouped = _group_discovered(discovered)

    r1_expected = [e for e in EXPECTED_BYPASSES if e[0] in R1_BYPASS_FILES]
    r1_expected_keys = {(e[0], e[1]) for e in r1_expected}

    # Every discovered R1 site must be in EXPECTED_BYPASSES
    for key in discovered_grouped:
        if key[0] in R1_BYPASS_FILES:
            assert key in r1_expected_keys, (
                f"R1 bypass site {key[0]}:{key[1]} not in EXPECTED_BYPASSES"
            )

    # Every expected R1 site must still be discovered
    for key in r1_expected_keys:
        assert key in discovered_grouped, (
            f"Expected R1 bypass {key[0]}:{key[1]} no longer exists"
        )

    assert r1_expected_keys, "No R1 bypass sites in EXPECTED_BYPASSES"


@pytest.mark.xfail(strict=True)
def test_r1_bypasses_are_still_xfail():
    """Demonstrate that R1 files still contain bypass sites.

    This test is marked strict-xfail. While bypass sites remain in R1
    files, it FAILS (reported as XFAIL, which is green). When bypass sites
    are fully removed from R1 files, this test PASSES (reported as XPASS,
    which is red with strict=True), signaling that remediation is complete
    and the xfail marker can be removed.
    """
    discovered = discover_bypass_sites()
    r1_sites = [(r, ln, p) for r, ln, p in discovered if r in R1_BYPASS_FILES]
    assert r1_sites == [], (
        "No bypass sites remain in R1 files -- remediation complete. "
        "Remove strict-xfail from this test."
    )


def test_seeded_openai_call_detected():
    """A file outside the gateway that calls OpenAI() is detected.

    Writes a temporary non-test file with an OpenAI() call, runs the
    scanner, and asserts the site is found. Then cleans up.
    """
    tmp_dir = REPO_ROOT / "tmp_bypass_check"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "_seed_bypass.py"

    seed_code = textwrap.dedent("""\
        \"\"\"Seeded bypass file -- should be detected.\"\"\"
        from openai import OpenAI


        def do_thing():
            client = OpenAI(api_key="sk-test-1234")
            return client
    """)

    try:
        tmp_file.write_text(seed_code, encoding="utf-8")
        rel = tmp_file.relative_to(REPO_ROOT).as_posix()
        sites = scan_file(tmp_file, rel)
        assert len(sites) >= 1, (
            f"Seeded OpenAI() call in {rel} was NOT detected. "
            f"AST scan returned: {sites}"
        )
        openai_sites = [s for s in sites if "OpenAI(" in s[2]]
        assert openai_sites, (
            f"Expected OpenAI( detection in seeded file but got: {sites}"
        )
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass


def test_bypass_check_line_number_independent():
    """Adding a blank line above an allowed call does not break detection,
    while a new direct call in a new file is still reported.

    This proves the check matches on (file_path, pattern) not on line numbers.
    """
    tmp_dir = REPO_ROOT / "tmp_bypass_check_ln"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # -- Part 1: file with an allowed call pattern --
        tmp_file = tmp_dir / "_test_ln_indep.py"
        code_v1 = textwrap.dedent("""\
            \"\"\"Test line-number independence.\"\"\"
            from openai import OpenAI


            def make_client():
                client = OpenAI(api_key="sk-test")
                return client
        """)
        tmp_file.write_text(code_v1, encoding="utf-8")
        rel = tmp_file.relative_to(REPO_ROOT).as_posix()

        sites_v1 = scan_file(tmp_file, rel)
        openai_v1 = [s for s in sites_v1 if "OpenAI(" in s[2]]
        assert len(openai_v1) == 1, (
            f"V1: expected 1 OpenAI() call, got {len(openai_v1)}: {sites_v1}"
        )

        # Add a blank line above the call (line number changes)
        code_v2 = textwrap.dedent("""\
            \"\"\"Test line-number independence.\"\"\"
            from openai import OpenAI


            def make_client():

                client = OpenAI(api_key="sk-test")
                return client
        """)
        tmp_file.write_text(code_v2, encoding="utf-8")

        sites_v2 = scan_file(tmp_file, rel)
        openai_v2 = [s for s in sites_v2 if "OpenAI(" in s[2]]
        assert len(openai_v2) == 1, (
            f"V2 (blank line added): expected 1 OpenAI() call, "
            f"got {len(openai_v2)}: {sites_v2}"
        )

        # -- Part 2: new file with a direct call not in EXPECTED_BYPASSES --
        new_file = tmp_dir / "_test_new_direct_call.py"
        new_code = textwrap.dedent("""\
            \"\"\"New direct call file.\"\"\"
            import anthropic


            def do_thing():
                client = anthropic.Anthropic(api_key="sk-test")
                return client
        """)
        new_file.write_text(new_code, encoding="utf-8")
        new_rel = new_file.relative_to(REPO_ROOT).as_posix()

        new_sites = scan_file(new_file, new_rel)
        anthro_sites = [s for s in new_sites if "Anthropic(" in s[2]]
        assert len(anthro_sites) == 1, (
            f"New direct call not detected: {new_sites}"
        )

        # Verify the new call would be unaccounted
        expected_lookup = _build_expected_lookup()
        for rel_found, lineno, pattern in new_sites:
            key = (new_rel, pattern)
            assert key not in expected_lookup, (
                f"New call ({new_rel}, {pattern}) should not be in EXPECTED_BYPASSES"
            )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_llm_boundary_gate_is_clean():
    """The llm-boundary gate still passes on the emitter tree."""
    checker_path = REPO_ROOT / "scripts" / "check_llm_boundary.py"
    spec = importlib.util.spec_from_file_location("check_llm_boundary", checker_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    violations = mod.find_violations()
    assert violations == [], (
        "llm-boundary violations in emitter tree:\n"
        + "\n".join(f"  {f}:{ln}: {txt}" for f, ln, txt in violations)
    )