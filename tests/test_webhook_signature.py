"""Webhook receipt must not accept unauthenticated payloads.

/api/webhooks/receive/<subscription_id> is @csrf.exempt, which is correct - the
caller is an external service that cannot hold a CSRF token. That makes the HMAC
signature the only thing authenticating the request, so two defects mattered:

  1. verify_webhook_signature() returned True when no secret was configured,
     collapsing "I cannot check this" into "this checked out".
  2. The secret was optional at subscription creation, and the receiver only
     enforces signatures when one exists - so a subscription created without one
     was an unauthenticated write endpoint that anyone knowing its id could post
     to, rate-limited by IP and nothing else.

The helper is extracted from source rather than imported because the module
imports `from app import csrf` at import time, which needs the app package.
"""

import hashlib
import hmac
import io
import re

import pytest

SRC_PATH = "app/routes/webhook.py"


@pytest.fixture(scope="module")
def verify():
    src = io.open(SRC_PATH, encoding="utf-8").read()
    match = re.search(r"^def verify_webhook_signature\(.*?(?=^\S)", src, re.S | re.M)
    assert match, "verify_webhook_signature not found in %s" % SRC_PATH
    ns = {"hmac": hmac, "hashlib": hashlib}
    exec(compile(match.group(0), "verify_webhook_signature", "exec"), ns)
    return ns["verify_webhook_signature"]


BODY = b'{"event":"application.deleted","id":42}'
SECRET = "s3cret"


def _sign(body, secret):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_a_correct_signature_is_accepted(verify):
    assert verify(BODY, _sign(BODY, SECRET), SECRET) is True


def test_a_forged_signature_is_rejected(verify):
    assert verify(BODY, "deadbeef", SECRET) is False


def test_a_tampered_body_is_rejected(verify):
    assert verify(BODY + b" ", _sign(BODY, SECRET), SECRET) is False


@pytest.mark.parametrize(
    "signature,secret",
    [
        (None, None),          # nothing to check, nothing supplied
        ("deadbeef", None),    # attacker supplies a signature, no secret to check it
        (None, SECRET),        # secret configured, caller sent no signature
        ("", SECRET),
    ],
)
def test_it_fails_closed_when_it_cannot_verify(verify, signature, secret):
    """The regression that matters.

    Returning True here meant an unsigned request was indistinguishable from a
    verified one. Absence of a credential is not proof of a credential.
    """
    assert verify(BODY, signature, secret) is False


def test_new_subscriptions_always_get_a_secret():
    """Guards the creation path that made the receiver's check reachable.

    Asserted against the source because exercising the route needs the full app
    plus a database; the property is that no code path passes a caller-optional
    secret straight through to create_subscription().
    """
    src = io.open(SRC_PATH, encoding="utf-8").read()
    assert "secret=data.get(\"secret\")" not in src, (
        "subscription creation passes the caller's secret through unchecked, so "
        "omitting it recreates the unauthenticated endpoint"
    )
    assert "secrets.token_hex" in src, "no secret is generated when the caller omits one"


def test_a_generated_secret_is_returned_once():
    """It has to be, or it would be unusable.

    to_dict() deliberately withholds the secret and there is no endpoint that
    reveals it later, so a generated secret that is never returned would leave the
    caller unable to sign anything - and the natural "fix" would be to drop the
    signature requirement again.
    """
    src = io.open(SRC_PATH, encoding="utf-8").read()
    assert 'payload["secret"] = secret' in src
    # The key, not the prose: the notice is split across adjacent string literals,
    # so no contiguous substring of it survives in the source text.
    assert 'payload["secret_notice"]' in src
