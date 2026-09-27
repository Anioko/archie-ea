# Adversarial probe failure diagnostics

Date: 2026-09-05

Scope: diagnostic output only in `tests/smoke/test_adversarial_probes.py`.
The baseline, route selection, status conditions, request timeouts, loop control,
and assertions are unchanged. A 503 still counts as a failure; a request
exception still counts as a failure. No retries were added. The existing 501
exclusion remains intact.

Request failures now include the exception class and a single-line reason,
limited to 300 characters. The two 5xx probes append a similarly bounded reason
from top-level JSON `error` and `message` strings. Other JSON fields, nested
objects, non-JSON bodies, request/session objects, headers, and cookies are not
dumped. URL user information, query strings, common credential assignments, and
header-like authentication/cookie values are redacted from diagnostic text.
This is intended for the existing isolated test-data probes; it is not a general
purpose sanitizer for arbitrary production response content.

Verification:

- Before implementation: focused tests reproduced absent exception reasons and
  absent JSON error details (6 failing, 9 passing after correcting the fake route
  binding).
- `python -m pytest tests/test_probe_error_diagnostics.py -q`: 15 passed, no skips
  (final run: 0.82 seconds).
- `python -m ruff check tests/test_probe_error_diagnostics.py tests/smoke/test_adversarial_probes.py --select F,E4,E7,E9`:
  passed.
- `git diff --check` on the changed test paths: passed.

The focused tests exercise actual probe functions with fake HTTP sessions and
real Requests response objects. They cover request errors across all three
probes, JSON reasons on both 5xx probes, single-request 503 failure detection,
existing accepted persona statuses including 501, malformed/non-object JSON,
HTML omission, bounding, and common credential redaction. No database, server,
browser, production access, installation, full verification run, or deployment
was performed for this bounded task. These results do not establish why the
earlier live ConnectionError or configuration-dependent 503s occurred; the next
CI probe run must provide that evidence.
