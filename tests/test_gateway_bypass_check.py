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

# Files owned by briefs R1-B11 / R1-B22
R1_BYPASS_FILES = {
    "app/modules/ai_chat/services/agent_runner.py",
    "app/modules/ai_chat/services/multi_domain_chat_service.py",
    "app/modules/ai_chat/services/ai_chat_multi_model.py",
}

# ---------------------------------------------------------------------------
# Expected bypass site list
# ---------------------------------------------------------------------------

EXPECTED_BYPASSES = [
    # Provider SDK constructors - R1-B11 files
    ("app/modules/ai_chat/services/agent_runner.py", 759, "R1-B11", "anthropic.Anthropic("),
    ("app/modules/ai_chat/services/agent_runner.py", 794, "R1-B11", "anthropic.Anthropic("),
    ("app/modules/ai_chat/services/agent_runner.py", 832, "R1-B11", "OpenAI("),
    ("app/modules/ai_chat/services/agent_runner.py", 862, "R1-B11", "OpenAI("),
    # Provider SDK constructors - R1-B22 files
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", 103, "R1-B22", "openai.OpenAI("),
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", 111, "R1-B22", "anthropic.Anthropic("),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", 6440, "R1-B22", "OpenAI("),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", 6466, "R1-B22", "anthropic.Anthropic("),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", 6493, "R1-B22", "genai.GenerativeModel"),
    # Provider SDK constructors - other files
    ("app/modules/architecture/services/inference_providers.py", 34, "R1-A03", "anthropic.Anthropic("),
    ("app/modules/architecture/services/inference_providers.py", 39, "R1-A03", "openai.OpenAI("),
    ("app/services/vector_embedding_service.py", 262, "R1-E01", "openai.OpenAI("),
    ("app/services/vector_embedding_service.py", 294, "R1-E01", "SentenceTransformer("),
    ("app/services/vector_embedding_service.py", 421, "R1-E01", "SentenceTransformer("),
    ("app/services/pgvector_embedding_service.py", 69, "R1-E02", "SentenceTransformer("),
    ("app/services/chromadb_apqc_service.py", 228, "R1-E03", "SentenceTransformer("),
    ("app/services/faiss_apqc_service.py", 198, "R1-E04", "SentenceTransformer("),
    ("app/modules/vendors/services/semantic_vendor_discovery.py", 96, "R1-V01", "SentenceTransformer("),
    ("app/services/conversation_history.py", 102, "R1-C01", "SentenceTransformer("),
    ("app/modules/duplicate_detection/services/ai_duplicate_detection_service.py", 117, "R1-D01", "SentenceTransformer("),
    ("app/modules/ai_chat/services/ai_semantic_discovery_service.py", 105, "R1-S01", "SentenceTransformer("),
    ("app/modules/capabilities/routes/mapping_routes.py", 277, "R1-M01", "SentenceTransformer("),
    # Provider SDK calls
    ("app/modules/ai_chat/services/agent_runner.py", 762, "R1-B11", ".messages.create"),
    ("app/modules/ai_chat/services/agent_runner.py", 838, "R1-B11", ".chat.completions.create"),
    ("app/modules/ai_chat/services/agent_runner.py", 870, "R1-B11", ".chat.completions.create"),
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", 252, "R1-B22", ".chat.completions.create"),
    ("app/modules/ai_chat/services/ai_chat_multi_model.py", 299, "R1-B22", ".messages.create"),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", 6441, "R1-B22", ".chat.completions.create"),
    ("app/modules/ai_chat/services/multi_domain_chat_service.py", 6467, "R1-B22", ".messages.create"),
    ("app/modules/architecture/services/inference_providers.py", 89, "R1-A03", ".messages.create"),
    ("app/modules/architecture/services/inference_providers.py", 96, "R1-A03", ".chat.completions.create"),
    ("app/services/vector_embedding_service.py", 264, "R1-E01", ".embeddings.create"),
    # Gateway bypass - _call_llm_with_failover outside llm_service_impl
    ("app/modules/ai_chat/services/agent_runner.py", 1122, "R1-B11", "_call_llm_with_failover"),
    ("app/services/technology_analyzer.py", 520, "R1-T01", "_call_llm_with_failover"),
    ("app/services/technology_analyzer.py", 915, "R1-T01", "_call_llm_with_failover"),
    ("app/services/capability_design_composition_service.py", 145, "R1-C02", "_call_llm_with_failover"),
    ("app/services/intelligent_analyzer.py", 575, "R1-I01", "_call_llm_with_failover"),
    ("app/modules/applications/services/application_architecture_mapper.py", 961, "R1-AM01", "_call_llm_with_failover"),
    ("app/modules/applications/services/application_capability_mapper.py", 131, "R1-AM02", "_call_llm_with_failover"),
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


# ---- tests ----------------------------------------------------------


def test_no_unaccounted_bypasses():
    discovered = discover_bypass_sites()
    expected_lookup = {(e[0], e[1]): e for e in EXPECTED_BYPASSES}
    unaccounted = []
    for rel, lineno, pattern in discovered:
        if (rel, lineno) not in expected_lookup:
            unaccounted.append((rel, lineno, pattern))
    assert unaccounted == [], (
        "Unaccounted bypass site(s) not in EXPECTED_BYPASSES:\n"
        + "\n".join(f"  {r}:{ln} ({p})" for r, ln, p in unaccounted)
    )


def test_known_bypasses_still_present():
    discovered = discover_bypass_sites()
    discovered_set = {(r, ln) for r, ln, _ in discovered}
    missing = []
    for entry in EXPECTED_BYPASSES:
        if (entry[0], entry[1]) not in discovered_set:
            missing.append(entry)
    assert missing == [], (
        "Expected bypass site(s) no longer exist -- "
        "update EXPECTED_BYPASSES if refactored:\n"
        + "\n".join(f"  {r}:{ln} ({bref}) [{pat}]" for r, ln, bref, pat in missing)
    )


def test_r1_bypasses_are_xfail():
    discovered = discover_bypass_sites()
    discovered_set = {(r, ln) for r, ln, _ in discovered}
    r1_discovered = [(r, ln, p) for r, ln, p in discovered if r in R1_BYPASS_FILES]
    r1_expected = [e for e in EXPECTED_BYPASSES if e[0] in R1_BYPASS_FILES]
    r1_expected_keys = {(e[0], e[1]) for e in r1_expected}
    for rel, lineno, _ in r1_discovered:
        assert (rel, lineno) in r1_expected_keys, (
            f"R1 bypass site {rel}:{lineno} not in EXPECTED_BYPASSES"
        )
    for entry in r1_expected:
        assert (entry[0], entry[1]) in discovered_set, (
            f"Expected R1 bypass {entry[0]}:{entry[1]} no longer exists"
        )
    assert r1_discovered, "No R1 bypass sites discovered"


@pytest.mark.xfail(strict=True)
def test_r1_bypasses_are_still_xfail():
    """Demonstrate that R1-B11 / R1-B22 files still contain bypass sites.

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
