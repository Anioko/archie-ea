"""Script to generate test_gateway_bypass_check.py with clean strings."""
from pathlib import Path

ROOT = Path("/home/ubuntu/verify/wt-rb23")
OUPUT = ROOT / "tests" / "test_gateway_bypass_check.py"

def w(line):
    f.write(line + "\n")

GATEWAY = "app/modules/ai_chat/services/llm_service_impl.py"
R1_AGENT = "app/modules/ai_chat/services/agent_runer.py"
R1_MULTI = "app/modules/ai_chat/services/multi_domain_chat_service.py"
R1_AIMULTI = "app/modules/ai_chat/services/ai_chat_multi_model.py"

BYPASSES = [
    # Provider SDK constructors - R1 files
    (R1_AGENT, 759, "R1-B11", "anthropic.Anthropic("),
    (R1_AGENT, 794, "R1-B11", "anthropic.Anthropic("),     
    (R1_AGENT, 832, "R1-B11", "OpenAI("),
    (R1_AGENT, 862, "R1-B11", "OpenAI("),
    (R1_AIMULTI, 103, "R1-B22", "openai.OpenAI("),
    (R1_AIMULTI, 111, "R1-B22", "anthropic.Anthropic("),
    (R1_MULTI, 6440, "R1-B22", "OpenAI("),
    (R1_MULTI, 6466, "R1-B22", "anthropic.Anthropic("),
    (R1_MULTI, 6493, "R1-B22", "genai.GenerativeModel"),
]

with open(OUTPUT, "w") as f:
    w('"""Gateway bypass enumeration -- AST-based scanning."""")
    w('')
    w('from __future__ import annotations')
    w('import ast, importlib.util, textwrap')
    w('from pathlib import Path')
    w('import pytest')
    w('')
    w(f'REPO_ROOT = Path(__file__).resolve().parent.parent') 
    w(f'GATEWAY_FILES = {{"{GATEWAY}",}}')
    w(f'R1_BYPASS_FILES = {{"{R1_AGENT}", "{R1_MULTI}", "{R1_AIMULTI}"}}')
    w(f'SKIP_DIR_PREFIXES = ("code_templates/", "migrations/")')
    w(f'EXPECTED_BYPASSES = {BYPASSES!r}')
print(f"Wrote {len(BYPASSES)} bypass entries to {OUTPUT}")
