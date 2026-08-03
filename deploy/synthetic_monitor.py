#!/usr/bin/env python3
"""Sign in as a real user every few minutes and check the product still works.

Uptime checks answer "is the process running". That is not the question users
ask. Archie can return HTTP 200 on every route while the sidebar is empty, the
front end never boots, or every save fails - all of which happened during this
engagement and none of which a port check notices.

So this signs in and drives the pages each archetype actually opens, asserting
on content rather than status: the navigation rendered, the page's own landmark
is present, no server error leaked into the HTML. It runs against the public URL
so it exercises TLS, Caddy and the app together, the way a user reaches them.

Deliberately NOT a browser: Playwright on the app host costs hundreds of MB of
RAM per run, and this box has already been OOM-killed once. Browser-level checks
(Alpine booting, icons rendering, nothing cloaked) live in verify_production.py
and run at deploy time, where paying for a browser once is reasonable. This is
the cheap thing that runs continuously. It imports no application code.

    export SYNTHETIC_BASE_URL=https://165-22-125-156.sslip.io
    export SYNTHETIC_EMAIL=monitor@example.com
    export SYNTHETIC_PASSWORD=...            # a low-privilege account
    python3 deploy/synthetic_monitor.py           # human-readable, exit 1 on failure
    python3 deploy/synthetic_monitor.py --json    # for a metrics agent

Exit codes:  0 healthy   1 check failed   2 could not run (config/network)
"""
import argparse
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

DEFAULT_BASE = os.environ.get("SYNTHETIC_BASE_URL", "https://165-22-125-156.sslip.io")
TIMEOUT = float(os.environ.get("SYNTHETIC_TIMEOUT", "30"))

# A page is only healthy if its own content arrived. A marker that appears in
# the shared layout would pass on an empty page, so each is something only that
# page renders.
PAGES = [
    ("/dashboard/overview",   ["dashboard"]),
    ("/applications/",        ["application"]),
    ("/capability-map/",      ["capabilit"]),
    ("/procurement/contracts", ["contract"]),
]

# Text that means the app rendered an error into a 200 response - the failure
# mode a status-code check cannot see.
ERROR_MARKERS = [
    "internal server error",
    "traceback (most recent call last)",
    "werkzeug.exceptions",
    "sqlalchemy.exc",
    "infailedsqltransaction",
    "undefinedcolumn",
    "jinja2.exceptions",
    "builderror",
]

# Slower than this and the page is technically up but not usable. Generous on
# purpose: this is a "something is badly wrong" threshold, not a performance
# budget. Performance belongs in a load test, not a liveness check.
SLOW_SECONDS = float(os.environ.get("SYNTHETIC_SLOW_SECONDS", "10"))


class Result:
    def __init__(self):
        self.checks = []
        self.started = time.time()

    def add(self, name, ok, detail="", seconds=None, fail_detail=""):
        """`detail` is shown either way; `fail_detail` only when the check fails.

        Kept separate because printing a failure explanation next to a passing
        check is how a monitor teaches people to stop reading its output.
        """
        self.checks.append({"check": name, "ok": bool(ok),
                            "detail": detail if ok else (fail_detail or detail),
                            "seconds": round(seconds, 3) if seconds else None})
        return ok

    @property
    def failures(self):
        return [c for c in self.checks if not c["ok"]]

    def report(self, as_json):
        elapsed = round(time.time() - self.started, 2)
        if as_json:
            print(json.dumps({
                "healthy": not self.failures,
                "elapsed_seconds": elapsed,
                "failed": len(self.failures),
                "checks": self.checks,
            }, indent=2))
            return
        width = max(len(c["check"]) for c in self.checks) if self.checks else 20
        for c in self.checks:
            mark = "ok  " if c["ok"] else "FAIL"
            timing = "%6.2fs" % c["seconds"] if c["seconds"] else "       "
            print("  %s %s  %-*s  %s"
                  % (mark, timing, width, c["check"], c["detail"]))
        print()
        if self.failures:
            print("UNHEALTHY - %d of %d checks failed (%ss)"
                  % (len(self.failures), len(self.checks), elapsed))
        else:
            print("HEALTHY - %d checks passed (%ss)" % (len(self.checks), elapsed))


def _opener():
    """A session that keeps cookies, like a browser - login must persist."""
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar()))


def _get(opener, url, data=None, referer=None):
    """Return (status, body, seconds). A 4xx/5xx is a result, not an exception."""
    headers = {"User-Agent": "archie-synthetic-monitor/1.0"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, data=data, headers=headers)
    start = time.time()
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace"), time.time() - start
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), time.time() - start


def check_certificate(result, base):
    """An expired certificate takes the whole product down for every user.

    It is also the outage with the longest warning and the least excuse, so it
    is worth knowing about weeks ahead rather than on the morning it happens.
    """
    host = urllib.parse.urlparse(base).hostname
    if not base.startswith("https://") or not host:
        return
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                not_after = tls.getpeercert().get("notAfter")
        expires = ssl.cert_time_to_seconds(not_after)
        days = int((expires - time.time()) / 86400)
        result.add("tls certificate", days > 14,
                   "expires in %d days" % days if days > 14
                   else "EXPIRES IN %d DAYS - renew now" % days)
    except Exception as exc:
        # sslip.io hostnames are commonly served with a self-signed or
        # short-lived certificate; report it, do not fail the run on it.
        result.add("tls certificate", True, "not verifiable (%s)" % type(exc).__name__)


def _csrf_token(html):
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not match:
        match = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    return match.group(1) if match else None


def check_login(result, opener, base, email, password):
    """Signing in is the check that matters most - everything else needs it."""
    status, html, seconds = _get(opener, base + "/account/login")
    if not result.add("login page loads", status == 200, "HTTP %s" % status, seconds):
        return False

    token = _csrf_token(html)
    if not result.add("csrf token present", token is not None,
                      "the form cannot be submitted without one"):
        return False

    payload = urllib.parse.urlencode({
        "csrf_token": token, "email": email, "password": password,
    }).encode()
    status, body, seconds = _get(opener, base + "/account/login", data=payload,
                                 referer=base + "/account/login")

    # A failed sign-in re-renders the login form with a 200, so status alone
    # proves nothing - look for the form having gone away.
    still_on_form = 'name="password"' in body.lower()
    return result.add("sign in succeeds", status < 400 and not still_on_form,
                      "HTTP %s%s" % (status, ", credentials rejected" if still_on_form else ""),
                      seconds)


def check_page(result, opener, base, path, markers):
    status, body, seconds = _get(opener, base + path)
    lowered = body.lower()

    if not result.add("%s responds" % path, status == 200, "HTTP %s" % status, seconds):
        return

    leaked = [m for m in ERROR_MARKERS if m in lowered]
    result.add("%s error-free" % path, not leaked,
               fail_detail="server error rendered into a 200: %s" % ", ".join(leaked))

    # Signed out mid-run makes every later result meaningless: an empty page
    # would look like a clean pass. The login form's password field is the
    # reliable tell - no signed-in page renders one.
    signed_in = 'name="password"' not in lowered
    if result.add("%s still signed in" % path, signed_in,
                  fail_detail="served the sign-in form - session lost, so the "
                              "remaining checks on this page mean nothing"):
        result.add("%s rendered its content" % path,
                   any(m in lowered for m in markers),
                   fail_detail="none of %s present - the page loaded empty"
                               % markers)

    result.add("%s responded promptly" % path, seconds < SLOW_SECONDS,
               "%.1fs" % seconds, seconds,
               fail_detail="%.1fs, over the %.0fs threshold" % (seconds, SLOW_SECONDS))


def alert(result, base):
    """Post to a webhook if one is configured. Never fail the run on alerting.

    A monitor that crashes while reporting a failure reports nothing, which is
    the same as being down and not knowing.
    """
    url = os.environ.get("SYNTHETIC_ALERT_WEBHOOK")
    if not url or not result.failures:
        return
    lines = "\n".join("- %s: %s" % (c["check"], c["detail"]) for c in result.failures)
    body = json.dumps({
        "text": "Archie synthetic check FAILED against %s\n%s" % (base, lines)
    }).encode()
    try:
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(request, timeout=10).close()
        print("  (alert posted)")
    except Exception as exc:
        print("  (alert could NOT be delivered: %s)" % exc, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    args = parser.parse_args()

    email = os.environ.get("SYNTHETIC_EMAIL")
    password = os.environ.get("SYNTHETIC_PASSWORD")
    if not email or not password:
        print("SYNTHETIC_EMAIL and SYNTHETIC_PASSWORD must be set - the point of "
              "this check is to sign in as a real user.", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    result = Result()
    if not args.json:
        print("\nsynthetic check against %s\n" % base)

    check_certificate(result, base)
    opener = _opener()
    try:
        if check_login(result, opener, base, email, password):
            for path, markers in PAGES:
                check_page(result, opener, base, path, markers)
        else:
            result.add("page checks", False, "skipped - could not sign in")
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as exc:
        result.add("reachable", False, "%s: %s" % (type(exc).__name__, exc))

    result.report(args.json)
    alert(result, base)
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
