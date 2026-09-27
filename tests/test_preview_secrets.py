"""Deployed code previews must not share a published password.

The full-stack preview (`/codegen/docker-preview/deploy`) launches a docker
compose stack per solution and publishes it under /apps/<id>/ via
_register_nginx_proxy(). Until 2026-07-31 the stack was seeded with four
constants written into this repository:

    POSTGRES_PASSWORD  archie-preview
    ADMIN_PASSWORD     Admin2026!
    JWT_SECRET         archie-preview-jwt-not-for-production
    SECRET_KEY         archie-preview-key-not-for-production

This repository is public, so the admin password of every deployed preview was
published alongside it. Calling the keys "not-for-production" documented the
risk without reducing it - the stacks they protected were reachable.

The pair of tests that matter here are the stability ones. _compose_env() is
called twice per deploy - once to write .env, once to build the subprocess
environment - so minting fresh randomness per call would write one password to
.env and hand docker compose another, and the database container would reject
the API container's credentials at startup. Equally, a redeploy over a running
stack must reuse the persisted secret, or it would rotate the password away from
the volume that already has a role created with the old one.
"""

import re

import pytest

# The module imports Flask blueprints at import time; the two functions under
# test are pure, so lift them out of the source rather than booting the app.
SRC_PATH = "app/modules/codegen/routes/preview_routes.py"


@pytest.fixture(scope="module")
def helpers():
    import io
    import secrets as _secrets

    src = io.open(SRC_PATH, encoding="utf-8").read()
    ns = {"secrets": _secrets, "PREVIEW_ADMIN_EMAIL": "admin@archie.demo"}
    for fn in ("_preview_secrets", "_compose_env"):
        match = re.search(r"^def %s\(.*?(?=^\S)" % fn, src, re.S | re.M)
        assert match, "%s not found in %s" % (fn, SRC_PATH)
        exec(compile(match.group(0), fn, "exec"), ns)
    return ns


class _Gen:
    """Stand-in for CodegenGeneration - only .config is read."""

    def __init__(self, config=None):
        self.config = config


def test_each_preview_gets_its_own_credentials(helpers):
    first = helpers["_preview_secrets"](_Gen())
    second = helpers["_preview_secrets"](_Gen())
    for key in ("ADMIN_PASSWORD", "POSTGRES_PASSWORD", "JWT_SECRET", "SECRET_KEY"):
        assert first[key] != second[key], (
            "%s is shared between two previews - one tenant's credentials would "
            "open another tenant's stack" % key
        )


def test_a_redeploy_reuses_the_running_stack_secrets(helpers):
    original = helpers["_preview_secrets"](_Gen())
    persisted = _Gen({"_docker_preview": {"secrets": original}})
    assert helpers["_preview_secrets"](persisted) == original, (
        "redeploy minted new secrets; the postgres volume still holds a role "
        "created with the old password, so the stack would fail to start"
    )


def test_dotenv_and_subprocess_environment_cannot_disagree(helpers):
    secrets_for_stack = helpers["_preview_secrets"](_Gen())
    first = helpers["_compose_env"](7, 8001, 3001, secrets_for_stack)
    second = helpers["_compose_env"](7, 8001, 3001, secrets_for_stack)
    assert first == second
    assert first["POSTGRES_PASSWORD"] == secrets_for_stack["POSTGRES_PASSWORD"]


def test_no_published_credential_survives_in_the_environment(helpers):
    env = helpers["_compose_env"](7, 8001, 3001, helpers["_preview_secrets"](_Gen()))
    published = {
        "archie-preview",
        "Admin2026!",
        "archie-preview-jwt-not-for-production",
        "archie-preview-key-not-for-production",
    }
    assert not published & set(env.values())
    # Long enough that guessing is not the easy path in; short enough to retype.
    assert len(env["ADMIN_PASSWORD"]) >= 12


def test_the_source_file_holds_no_hardcoded_stack_credentials():
    """Guard the file itself, not just the helper.

    The helpers could be correct while someone reintroduces a constant at another
    call site - which is exactly how the originals survived: they sat in a dict
    literal that read like configuration rather than like a secret.

    Checks string literals via the AST rather than grepping the text, because the
    prose above deliberately names the old values in order to explain the fix, and
    a plain substring search cannot tell an explanation from a credential.
    """
    import ast
    import io

    tree = ast.parse(io.open(SRC_PATH, encoding="utf-8").read())

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    live = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]
    # Exact match only: "archie-preview" is also the legitimate prefix of the
    # preview directory (/opt/archie-previews) and of the compose project name, so
    # a substring test would fail on correct code.
    for banned in ("archie-preview",):
        assert banned not in live, (
            "%r is back in %s as a live string literal" % (banned, SRC_PATH)
        )
    # Distinctive enough that any occurrence is the credential itself.
    for banned in ("Admin2026!", "not-for-production"):
        offenders = [s for s in live if banned in s]
        assert not offenders, (
            "%r is back in %s as a live string literal: %r" % (banned, SRC_PATH, offenders[:3])
        )


def test_generated_scaffolds_fail_loudly_without_a_password():
    """Generated compose files must not fall back to a known password.

    ${POSTGRES_PASSWORD:-secret} starts happily with the password "secret" when
    the variable is unset, so a generated stack ships weak in exactly the case
    where nobody noticed. The :? form aborts instead.
    """
    import io

    for path in (
        "app/modules/codegen/routes/boundary_routes.py",
        "app/modules/codegen/services/platform_configs.py",
    ):
        src = io.open(path, encoding="utf-8").read()
        for weak in ("POSTGRES_PASSWORD:-secret", "POSTGRES_PASSWORD:-changeme"):
            assert weak not in src, "%s still emits a silent default in %s" % (weak, path)
