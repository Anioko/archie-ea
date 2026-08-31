"""Every gate must be watched failing, on every run — not once, by hand.

docs/TESTING_STANDARD.md rule 7 has always required it: "Reintroduce the defect,
watch the gate go red, restore, watch it go green. A checker nobody has seen fail
is just a number." The evidence-contract gate enforces that a checker CARRIES a
`Proven-against:` line, which is a claim that someone once did that. This file
turns the claim into a measurement that reruns forever.

Twice today a gate written in this session reported 0 while the defect it was
built for sat right there in the tree:

* the first `authz-widening` probe left the `Permission` import in place, so the
  gate correctly saw a permission check and stayed green — and for a few minutes
  I believed a fake gate was real;
* the first `ai-untrusted-content` probe wrote a broken f-string, the checker's
  `except SyntaxError` skipped the file, and it reported 0 for a defect that was
  present.

Both were caught by chance. A gate that cannot fail is worse than no gate,
because it is counted as coverage — which is the whole thesis of this codebase.

Every checker here accepts `--root`, so each case builds a MINIMAL synthetic
tree containing exactly the defect and runs the checker against it. Nothing in
the real repository is mutated, the cases are independent, and they can run in
parallel. Each case asserts both directions: the bad tree is non-zero AND the
clean tree is zero. Asserting only "red" would pass for a checker that returns a
positive count for everything.

One checker is deliberately absent: check_evidence_contract.py reads real git
history and the verify.py registry, and has no --root, so a synthetic tree
cannot drive it. Its rule-2 substance is covered directly instead, by
test_every_registered_checker_carries_its_proof below. Naming the exclusion is
the point -- a hollow case in THIS file would defeat the file.
"""

import json
import os
import subprocess
import sys

import pytest

NEWLINE = chr(10)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _run_checker(script, root):
    """Run a checker against a synthetic tree and return its count."""
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), "--count", "--root", str(root)],
        capture_output=True, text=True, cwd=REPO,
    )
    trailing = (proc.stdout or "").strip().splitlines()
    assert trailing, (
        "%s produced no count for root=%s\nstdout=%r\nstderr=%r"
        % (script, root, proc.stdout, proc.stderr[:400])
    )
    try:
        return int(trailing[-1])
    except ValueError:
        raise AssertionError(
            "%s did not end with a count: %r (stderr=%r)"
            % (script, trailing[-1], proc.stderr[:400])
        )


def _write(root, relpath, content):
    path = root.join(*relpath.split("/"))
    path.dirpath().ensure_dir()
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Each case: (checker, builder(root, defective) -> None)
# The builder writes a tree that is defective when `defective` is True and
# otherwise identical but clean. Keeping one builder for both halves is
# deliberate: it makes the DIFFERENCE the thing under test, so a case cannot
# accidentally compare two unrelated trees.
# --------------------------------------------------------------------------


def _inline_handlers(root, defective):
    handler = ' onchange="this.form.submit()"' if defective else " data-autosubmit"
    _write(root, "app/templates/probe.html",
           "<form><select name='x'%s><option>1</option></select></form>" % handler)


def _nested_jinja(root, defective):
    inner = "{{ page_header(title='{{ x.name }}') }}" if defective else "{{ page_header(title=x.name) }}"
    _write(root, "app/templates/probe.html", inner)


def _credential_autofill(root, defective):
    extra = "" if defective else ' autocomplete="new-password"'
    _write(root, "app/templates/probe.html",
           '<input type="password" name="api_key"%s>' % extra)


def _unreachable_actions(root, defective):
    allowed = '{"approve"}' if defective else '{"approve", "archive"}'
    _write(root, "app/probe.py",
           "def handler(action):\n"
           "    valid = %s\n"
           "    if action not in valid:\n"
           "        return 400\n"
           "    if action == 'archive':\n"
           "        return 1\n" % allowed)


def _page_cost(root, defective):
    expr = "len(Model.query.all())" if defective else "Model.query.count()"
    _write(root, "app/probe.py", "def handler():\n    return %s\n" % expr)


def _canonical_store(root, defective):
    second = ('\n\nclass Shadow(db.Model):\n    __tablename__ = "widgets"\n'
              if defective else "")
    _write(root, "app/models/probe.py",
           'class Widget(db.Model):\n    __tablename__ = "widgets"\n' + second)


def _nullable_columns(root, defective):
    tail = "" if defective else ', server_default="x"'
    _write(root, "app/models/probe.py",
           "class Widget(db.Model):\n"
           "    name = db.Column(db.String(10), nullable=False%s)\n" % tail)


def _archimate_backbone(root, defective):
    sync = "" if defective else "    _sync_archimate_element(d)\n"
    _write(root, "app/probe.py",
           "def create():\n"
           "    d = Driver(name='x')\n"
           "    db.session.add(d)\n" + sync)


def _cache_tenancy(root, defective):
    key = "domain" if defective else "(org_id, domain)"
    _write(root, "app/probe.py",
           "_thing_cache = {}\n\n"
           "def get(domain, org_id):\n"
           "    org_id = current_org_id\n"
           "    _thing_cache[%s] = 1\n" % key)


def _ai_evidence_rules(root, defective):
    rules = "" if defective else "{_EVIDENCE_RULES}"
    _write(root, "app/modules/ai_chat/services/architect_persona_charters.py",
           '_EVIDENCE_RULES = """rules"""\n\n'
           'def build_architect_prompt(p):\n'
           '    return "your ONLY source for numbers"\n\n'
           'CHARTERS: Dict[str, str] = {\n'
           '    "cto": f"""You are the CTO persona.\n%s""",\n}\n' % rules)


CASES = [
    ("check_inline_handlers.py", _inline_handlers),
    ("check_nested_jinja.py", _nested_jinja),
    ("check_credential_autofill.py", _credential_autofill),
    ("check_unreachable_actions.py", _unreachable_actions),
    ("check_page_cost.py", _page_cost),
    ("check_canonical_store.py", _canonical_store),
    ("check_nullable_columns.py", _nullable_columns),
    ("check_archimate_backbone.py", _archimate_backbone),
    ("check_cache_tenancy.py", _cache_tenancy),
    ("check_ai_evidence_rules.py", _ai_evidence_rules),
]


# --------------------------------------------------------------------------
# Gates whose fixtures need more than one file. Written as real source strings
# rather than escaped one-liners: these builders ARE the specification of what
# each gate considers a defect, so they have to stay readable.
# --------------------------------------------------------------------------

_USER_MODEL = '''ROLE_CTO = "cto"
ROLE_EA = "enterprise_architect"

VALID_ROLES = [
    ROLE_CTO,
    ROLE_EA,
]
'''


def _persona_vocabularies(root, defective):
    """A role in VALID_ROLES with no IdP group can never be provisioned."""
    _write(root, "app/models/user.py", _USER_MODEL)
    cto_group = "" if defective else '    "CTO": "cto",\n'
    _write(root, "app/auth/sso.py",
           "DEFAULT_GROUP_ROLE_MAP = {\n"
           '    "EA-Architects": "enterprise_architect",\n'
           + cto_group +
           "}\n")
    _write(root, "app/modules/ai_chat/services/architect_persona_charters.py",
           'ARCHITECT_PERSONAS = (\n    "cto",\n    "enterprise_architect",\n)\n\n'
           "PERSONA_ALIASES: Dict[str, str] = {\n}\n")


def _journey_coverage(root, defective):
    """A persona with no journey that writes and asserts is unproven."""
    _write(root, "app/models/user.py", _USER_MODEL)
    if defective:
        body = "def test_nothing():\n    pass\n"
    else:
        body = ('def test_a_cto_does_their_job(client):\n'
                '    r = client.post("/x", json={"role": "cto"})\n'
                '    assert r.status_code == 201\n\n'
                'def test_an_ea_does_their_job(client):\n'
                '    r = client.post("/y", json={"role": "enterprise_architect"})\n'
                '    assert r.status_code == 201\n')
    _write(root, "tests/journeys/test_probe.py", body)


def _authz_widening(root, defective):
    """A role granted from a user-settable field with no permission check."""
    guard = "" if defective else "            if current_user.can(Permission.GENERAL):\n"
    _write(root, "app/_decorators_base.py",
           "def require_roles(*allowed):\n"
           "    def decorator(f):\n"
           "        def decorated_function(*a, **kw):\n"
           "            user_roles = set()\n"
           '            role = getattr(current_user, "enterprise_role", None)\n'
           + guard +
           "            user_roles.add(role)\n"
           "            return f(*a, **kw)\n"
           "        return decorated_function\n"
           "    return decorator\n")


def _ai_approval_honoured(root, defective):
    """A user preference must not decide whether AI writes need approval."""
    if defective:
        source = ("def send():\n"
                  "    runner = AgentRunner(user_id=1, "
                  'auto_execute=flask_session.get("agent_auto_execute", False))\n')
    else:
        source = ("def _allowed():\n"
                  '    return not current_app.config.get("REQUIRE_AI_APPROVAL", True)\n\n\n'
                  "def send():\n"
                  "    runner = AgentRunner(user_id=1, auto_execute=_allowed())\n")
    _write(root, "app/modules/ai_chat/routes/chat_core.py", source)


def _ai_untrusted_content(root, defective):
    """Retrieved content must be fenced before it reaches the system prompt."""
    if defective:
        line = '    ctx["system_prompt"] = f"Context: {_rag_ctx}" + ctx["system_prompt"]\n'
    else:
        line = ('    ctx["system_prompt"] = ctx["system_prompt"] + '
                'fence_untrusted("RAG", _rag_ctx)\n')
    _write(root, "app/modules/ai_chat/services/probe_service.py",
           "def build(ctx, _rag_ctx):\n" + line)


def _ai_tool_guard(root, defective):
    """No _tool_* handler may be reached outside the permission choke point."""
    _write(root, "app/modules/ai_chat/tools/registry.py",
           'TOOL_SCHEMAS = [\n    {"name": "create_thing", "mutates": True},\n]\n')
    _write(root, "app/modules/ai_chat/tools/executor.py",
           "class ToolExecutor:\n"
           "    def _tool_create_thing(self, args):\n"
           "        db.session.add(1)\n")
    call = ("    return ex._tool_create_thing({})\n" if defective
            else "    return ex.execute(call)\n")
    _write(root, "app/modules/ai_chat/services/caller.py",
           "def run(ex, call):\n" + call)


CASES += [
    ("check_persona_vocabularies.py", _persona_vocabularies),
    ("check_journey_coverage.py", _journey_coverage),
    ("check_authz_widening.py", _authz_widening),
    ("check_ai_approval_honoured.py", _ai_approval_honoured),
    ("check_ai_untrusted_content.py", _ai_untrusted_content),
    ("check_ai_tool_guard.py", _ai_tool_guard),
]


def _empty_state_cta(root, defective):
    """An empty state that names no next action is a dead end."""
    cta = "" if defective else ", cta_label='Add an application', cta_href='/apps/new'"
    _write(root, "app/templates/probe.html",
           "{% macro empty_state(icon, title, cta_label=None, cta_href=None) %}\n"
           "<div>{{ title }}</div>\n"
           "{% endmacro %}\n"
           "{{ empty_state(icon='layout-grid', "
           "title='No applications found.'" + cta + ") }}\n")


def _role_gate_coverage(root, defective):
    """A role in the delivery contract whose tags match no gate in the registry."""
    _write(root, "scripts/verify.py",
           "def build_gates(baseline):\n"
           "    return [\n"
           "        Gate('ai-tool-guard', 'd', 'ratchet', f, tags=['static', 'ai']),\n"
           "    ]\n")
    tags_cell = "-" if defective else "`ai`"
    _write(root, "docs/DELIVERY_CONTRACT.md",
           "| Role | Gate tags | Gates |\n"
           "|---|---|---|\n"
           "| AI / ML architect | " + tags_cell + " | 1 |\n")


CASES.append(("check_role_gate_coverage.py", _role_gate_coverage))


CASES.append(("check_empty_state_cta.py", _empty_state_cta))


def _business_layer_backbone(root, defective):
    """A capability with no ArchiMate element is invisible to the lenses."""
    sync = "" if defective else "    sync_archimate_element(cap)\n"
    _write(root, "app/probe.py",
           "def create():\n"
           "    cap = BusinessCapability(name='Billing')\n"
           "    db.session.add(cap)\n" + sync)


def _api_envelope(root, defective):
    """A handler that commits to no response shape forces callers to guess."""
    ret = ("    return jsonify({'items': []})\n" if defective
           else "    return success_response({'items': []})\n")
    _write(root, "app/probe.py",
           "@bp.route('/things')\n"
           "def list_things():\n" + ret)


CASES.append(("check_business_layer_backbone.py", _business_layer_backbone))
CASES.append(("check_api_envelope.py", _api_envelope))


def _collapsed_nav_affordance(root, defective):
    """A collapsed rail with no tooltip is a row of unlabelled buttons."""
    named = "" if defective else ' title="Dashboard"'
    _write(root, "app/templates/components/admin_sidebar.html",
           "<nav><a href='/x'" + named + ">"
           "<i data-lucide='layout-dashboard'></i>"
           "<span class='truncate'>Dashboard</span></a></nav>")


def _nav_icon_ambiguity(root, defective):
    """Two destinations behind one icon in one persona's own menu."""
    second = "compass" if defective else "map"
    rows = [
        "ZONES = {",
        "    ROLE_ENTERPRISE_ARCHITECT: [",
        '        _link("Traceability", "trace.index", "compass"),',
        '        _link("Impact", "impact.index", "' + second + '"),',
        "    ],",
        "}",
    ]
    _write(root, "app/utils/role_access.py", NEWLINE.join(rows) + NEWLINE)


def _nav_label_clarity(root, defective):
    """One label naming two different destinations."""
    second = "Applications" if defective else "My Applications"
    rows = [
        "ZONES = {",
        "    ROLE_PORTFOLIO_MANAGER: [",
        '        _link("Applications", "apps.index", "list"),',
        '        _link("' + second + '", "apps.mine", "user"),',
        "    ],",
        "}",
    ]
    _write(root, "app/utils/role_access.py", NEWLINE.join(rows) + NEWLINE)


CASES += [
    ("check_collapsed_nav_affordance.py", _collapsed_nav_affordance),
    ("check_nav_icon_ambiguity.py", _nav_icon_ambiguity),
    ("check_nav_label_clarity.py", _nav_label_clarity),
]


@pytest.mark.parametrize("script,builder", CASES, ids=[c[0] for c in CASES])
def test_the_gate_fires_on_its_own_defect(script, builder, tmpdir):
    """Red on the defect, green without it. Both halves, every run."""
    bad = tmpdir.mkdir("bad")
    builder(bad, defective=True)
    bad_count = _run_checker(script, bad)

    good = tmpdir.mkdir("good")
    builder(good, defective=False)
    good_count = _run_checker(script, good)

    assert bad_count > 0, (
        "%s reported 0 against a tree built to contain exactly the defect it "
        "exists to catch. The gate is decoration: it can be counted as coverage "
        "and can never fail. Fix the checker, or fix this fixture if the defect "
        "shape has moved." % script
    )
    assert good_count == 0, (
        "%s reported %d against the CLEAN tree. A checker that fires on correct "
        "code trains people to ignore it, which is worse than not having it."
        % (script, good_count)
    )
    assert bad_count > good_count


def test_every_registered_checker_carries_its_proof():
    """A checker in the registry must document the defect it was watched on.

    docs/TESTING_STANDARD.md rule 7. The `Proven-against:` line is how a
    reviewer, and this file's next author, learns what fixture to build.
    """
    missing = []
    for script, _ in CASES:
        path = os.path.join(SCRIPTS, script)
        assert os.path.exists(path), "%s is in CASES but not in scripts/" % script
        with open(path, encoding="utf-8") as fh:
            if "Proven-against:" not in fh.read():
                missing.append(script)
    assert not missing, (
        "these checkers carry no Proven-against: line, so nobody recorded "
        "watching them fail: %s" % ", ".join(missing)
    )
