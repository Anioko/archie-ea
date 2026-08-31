#!/usr/bin/env python
"""Two surfaces answer one question and give different numbers.

Every other gate in this repository reads SOURCE. This one reads ANSWERS.

The owner found all three of these by clicking around the deployed product,
while all 70+ gates were green:

  * /capability-map/ printing "Total Capabilities 191" directly above a table
    reading "Showing 1-10 of 0 results";
  * the Capability Roadmap counting 173 gaps beside a Gap Analysis screen
    reading 0;
  * GET /api/v1/capabilities returning an empty list while `business_capability`
    held 461 rows.

They are one defect wearing three faces: a concept lives in more than one store,
each screen reads a different one, and the product contradicts itself in front
of the user. No source-reading gate can see it, because every individual line is
correct -- `/dashboard/api/capabilities` counting BusinessCapability and
`/api/v1/capabilities/` paginating UnifiedCapability are both perfectly good
code. The defect exists only in the DIFFERENCE between their outputs.
check_canonical_store.py holds the nearest structural approximation (no NEW
table gains a second mapped class); this holds the behavioural fact.

So this gate boots the app, establishes a real tenant, asks every surface that
answers a given question, and fails when they disagree.

Adding a concept
----------------
CONCEPTS at the top of this file is the whole extension surface. A new concept
is a dict entry and two or more Surface(...) lines. A gate nobody can extend
gets bypassed, so keep it that way -- put the model path and the URL in the
registry, never a special case in the engine.

Not reporting differences that are legitimate
---------------------------------------------
Two counts may honestly differ, and a gate that cries wolf gets ignored --
this repository has already had two gates ratcheting phantom findings. Three
legitimate reasons, all handled by the `scope` field rather than by heuristics:

  pagination   a page of items is not the population. A surface returning
               `pagination.total` is scope="all"; one returning the length of
               the items ON the page is scope="page".
  a filter     "active applications" is a different question from "all
               applications". Declare it: scope="status=active".
  permissions  a role-scoped listing answers a narrower question. Declare it.

Surfaces are compared ONLY within their own scope group. Equality inside a group
is required; across groups the only rule asserted is that a declared subset may
not EXCEED the scope="all" population, which is true of every filter, page and
permission narrowing there is. A difference the declared scope explains is
therefore never reported. Anything undeclared is a finding naming both surfaces
and both numbers.

Blindness is reported, not hidden
---------------------------------
Against an empty database every surface answers 0 and agrees perfectly. That is
not evidence of health, so a concept whose surfaces are ALL zero is printed as
`no-evidence` and excluded from the count instead of being silently counted as
a pass. Read those lines: they say the gate could not see anything, and a run
that is all no-evidence has proven nothing.

Escape hatch: `store-agreement-ok: <reason>` in a Surface's `waived=` field, for
a surface that is knowingly and permanently a different number (a cached
projection with a documented staleness window, say). Name what makes the
divergence correct and who keeps it bounded.

    python scripts/check_store_agreement.py
    python scripts/check_store_agreement.py --count
    python scripts/check_store_agreement.py --root <tree>   # synthetic

`--root` reads `<root>/store_agreement_probe.json` -- the observations an app
boot would have produced -- and runs the identical comparison engine over them.
That is what makes the JUDGEMENT (which differences are reported and which are
explained away) testable without a seeded database, which is the part of this
gate that can be wrong.

Proven-against: run against the shared test database it reports 1 --
`capabilities: orm:BusinessCapability=12, GET /dashboard/api/capabilities=12,
orm:UnifiedCapability=0, GET /api/v1/capabilities/=0` for organisation 52336 --
which is the owner's third finding reproduced mechanically: the list endpoint
answers 0 while the store holds rows. Confirmed against the database by hand
(`select count(*) from business_capability where organization_id=52336` = 12,
`unified_capabilities` = 0). Red-and-green on a synthetic tree by
tests/test_gates_actually_fail.py, which also plants a difference that IS
legitimate (a scope="page" surface reading 10 beneath a scope="all" surface
reading 191) and asserts it is NOT reported.

"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW_MARKER = "store-agreement-ok:"


class Surface:
    """One way the product answers "how many X are there?".

    kind    "orm"  -- count rows of a mapped model
            "http" -- GET a URL as a logged-in user of the tenant and read a
                      number out of the JSON
    target  dotted model path ("app.models.business_capabilities.BusinessCapability")
            or a URL path ("/api/v1/capabilities/?per_page=1")
    extract http only. A dotted path into the JSON ("data.pagination.total"),
            or "len:<path>" for the length of a list ("len:" for the top level).
    scope   the question this surface actually answers. "all" is the whole
            population; anything else declares a filter, and is compared only
            with surfaces carrying the SAME string.
    waived  a `store-agreement-ok: <reason>` string; excludes this surface.
    """

    def __init__(self, name, kind, target, extract=None, scope="all", waived=None):
        self.name = name
        self.kind = kind
        self.target = target
        self.extract = extract
        self.scope = scope
        self.waived = waived


# --------------------------------------------------------------------------
# THE REGISTRY. Adding a concept is an entry here and nothing else.
# --------------------------------------------------------------------------
CONCEPTS = {
    # The owner's finding, exactly. Both surfaces answer "how many capabilities
    # does this organisation have"; they read two different tables.
    "capabilities": [
        Surface("orm:BusinessCapability", "orm",
                "app.models.business_capabilities.BusinessCapability"),
        Surface("orm:UnifiedCapability", "orm",
                "app.models.unified_capability.UnifiedCapability"),
        Surface("GET /dashboard/api/capabilities", "http",
                "/dashboard/api/capabilities", extract="len:"),
        Surface("GET /api/v1/capabilities/", "http",
                "/api/v1/capabilities/?per_page=1",
                extract="data.pagination.total"),
    ],
    "applications": [
        Surface("orm:ApplicationComponent", "orm",
                "app.models.application_portfolio.ApplicationComponent"),
        Surface("GET /api/v1/applications/", "http",
                "/api/v1/applications/?per_page=1",
                extract="data.pagination.total"),
        # Deliberately a DIFFERENT scope: this reads one page of rows, not the
        # population. Declared, so a smaller number here is never a finding.
        Surface("GET /api/v1/applications/ (one page)", "http",
                "/api/v1/applications/?per_page=1",
                extract="len:data.applications", scope="page"),
    ],
    "gaps": [
        Surface("orm:ImplementationGap", "orm",
                "app.models.implementation_planning.ImplementationGap"),
        Surface("GET /implementation/api/gaps", "http",
                "/implementation/api/gaps", extract="len:gaps"),
    ],
}

# Concepts deliberately NOT registered, and why -- naming the exclusion is the
# point, because a hollow entry here would defeat the file:
#
#   capability gaps   CapabilityGapDetail, CapabilityGapAnalysis and
#                     ImplementationGap are three stores, but they are not three
#                     answers to ONE question: detail rows hang off analysis
#                     rows (a parent/child cardinality, so unequal counts are
#                     correct), and the portfolio gap-analysis API computes gaps
#                     from a live analyzer rather than reading a store. Comparing
#                     them would manufacture findings. What the owner saw (173
#                     vs 0) is real, but proving WHICH pair disagrees needs the
#                     two definitions reconciled first -- that is a product
#                     decision about what "a gap" is, not a gate.
#   capability        the coverage percentages (48% vs 0%) are ratios of two
#   coverage          populations each of which is itself contested. Fix the
#                     populations first; the ratio follows.


def _extract(payload, spec):
    """Pull a number out of a JSON response per the surface's `extract` spec."""
    want_len = spec.startswith("len:")
    path = spec[4:] if want_len else spec
    node = payload
    for part in [p for p in path.split(".") if p]:
        if not isinstance(node, dict) or part not in node:
            raise KeyError("%r not present in the response" % path)
        node = node[part]
    if want_len:
        if not isinstance(node, list):
            raise KeyError("%r is not a list" % (path or "<top level>"))
        return len(node)
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        raise KeyError("%r is not a number: %r" % (path, node))
    return int(node)


# --------------------------------------------------------------------------
# The comparison engine. Pure: observations in, findings out. Shared by the
# live run and by --root, so the synthetic test exercises the real judgement.
# --------------------------------------------------------------------------
def compare(observations):
    """observations: {concept: [(surface_name, count, scope), ...]}

    Returns (findings, notes).
    """
    findings, notes = [], []
    for concept in sorted(observations):
        rows = [r for r in observations[concept] if r[1] is not None]
        if len(rows) < 2:
            notes.append(
                "  %s [no-evidence] fewer than two surfaces answered; nothing "
                "was compared" % concept)
            continue
        if all(count == 0 for _, count, _ in rows):
            notes.append(
                "  %s [no-evidence] every surface answered 0. An empty store "
                "agrees with an empty store: this proves nothing. Seed the "
                "tenant, or point DATABASE_URL at data." % concept)
            continue

        groups = {}
        for name, count, scope in rows:
            groups.setdefault(scope, []).append((name, count))

        # Within one declared scope, the surfaces must agree exactly.
        for scope in sorted(groups):
            members = groups[scope]
            distinct = {c for _, c in members}
            if len(distinct) < 2:
                continue
            # Name EVERY surface and its number, not just the extreme pair.
            # "191 vs 0" tells you there is a disagreement; "dashboard=12,
            # api/v1=0, BusinessCapability=12, UnifiedCapability=0" tells you
            # which store each surface is reading, which is the fix.
            detail = ", ".join(
                "%s=%d" % (name, count)
                for name, count in sorted(members, key=lambda m: -m[1]))
            findings.append(
                "  %s [store-disagreement] one question, %d different answers, "
                "all shown to the user: %s%s"
                % (concept, len(distinct), detail,
                   "" if scope == "all" else " (scope %r)" % scope))

        # Across scopes the ONLY assertion is that a declared subset cannot
        # exceed the whole. Pagination, filters and permission scoping all
        # narrow; none of them can add rows. A smaller number is therefore
        # explained by the declaration and is never reported.
        if "all" in groups:
            total = max(c for _, c in groups["all"])
            for scope in sorted(groups):
                if scope == "all":
                    continue
                for name, count in groups[scope]:
                    if count > total:
                        findings.append(
                            "  %s [store-disagreement] %s reports %d under the "
                            "declared narrowing %r, which is MORE than the "
                            "unfiltered population (%d). A filter cannot add "
                            "rows, so the two surfaces are reading different "
                            "stores." % (concept, name, count, scope, total))
    return findings, notes


# --------------------------------------------------------------------------
# Live observation: boot the app, establish a tenant, ask every surface.
# --------------------------------------------------------------------------
def _orm_models():
    """Every model named by an "orm" surface, deduplicated."""
    seen, out = set(), []
    for surfaces in CONCEPTS.values():
        for surface in surfaces:
            if surface.kind != "orm" or surface.target in seen:
                continue
            seen.add(surface.target)
            module, _, cls = surface.target.rpartition(".")
            try:
                out.append(getattr(__import__(module, fromlist=[cls]), cls))
            except Exception:
                continue
    return out


def _pick_tenant(db):
    """The tenant that actually HOLDS data, preferring one with a user.

    Taking "the first organisation" is the obvious choice and it is wrong here:
    it selects whichever empty shell sorts lowest, every surface answers 0, and
    the run reports no-evidence across the board while a populated tenant sits
    two rows away. Measured on the shared test database, the first organisation
    held 0 capabilities and 0 applications; the richest held 12.

    A user is preferred because the HTTP surfaces need a session to get past
    login_required. Without one only the ORM surfaces answer, which is still a
    valid comparison but a much thinner one, so a populated tenant WITH a user
    always wins over a slightly richer tenant without.
    """
    from sqlalchemy import func

    from app.models.organization import Organization
    from app.models.user import User

    totals = {}
    for model in _orm_models():
        column = getattr(model, "organization_id", None)
        if column is None:
            continue
        try:
            rows = (db.session.query(column, func.count())
                    .group_by(column).all())
        except Exception:
            db.session.rollback()
            continue
        for org_id, count in rows:
            if org_id is not None:
                totals[org_id] = totals.get(org_id, 0) + int(count)

    with_user = {row[0] for row in db.session.query(User.organization_id)
                 .filter(User.organization_id.isnot(None)).distinct().all()}

    ranked = sorted(totals.items(), key=lambda kv: (kv[0] in with_user, kv[1]),
                    reverse=True)
    org_id = ranked[0][0] if ranked else None
    if org_id is None:
        org = db.session.query(Organization).order_by(Organization.id).first()
    else:
        org = db.session.get(Organization, org_id)
        if org is None:
            # A dangling organization_id is a data defect of its own, but not
            # this gate's; fall back rather than crash.
            org = db.session.query(Organization).order_by(Organization.id).first()
    if org is None:
        return None, None
    user = (db.session.query(User)
            .filter(User.organization_id == org.id)
            .order_by(User.id)
            .first())
    return org, user


def observe_live():
    """Ask every registered surface, inside one tenant. Returns (obs, notes)."""
    notes = []
    os.environ.setdefault("FLASK_CONFIG", "testing")
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from flask import g

        from app import create_app, db
    except Exception as exc:  # pragma: no cover - import environment
        return {}, ["  [no-evidence] the application could not be imported: %s"
                    % str(exc)[:200]]

    try:
        app = create_app("testing")
    except Exception as exc:
        return {}, ["  [no-evidence] the application could not be booted: %s"
                    % str(exc)[:200]]

    observations = {}
    # A test REQUEST context, not a bare app context. tests/conftest.py's
    # tenant_ctx fixture does the same, and the reason is load-bearing: the
    # hybrid capability scoping in app/models/unified_capability.py returns
    # early unless has_request_context() is true, so a bare app context leaves
    # UnifiedCapability entirely unfiltered. Measured: it counted 31 rows
    # belonging to 31 OTHER organisations while the HTTP surface correctly
    # answered 0, and the gate reported that as a store disagreement. It was
    # the harness. This is the single largest false-positive source here.
    with app.test_request_context("/"):
        try:
            org, user = _pick_tenant(db)
        except Exception as exc:
            return {}, ["  [no-evidence] the database is unreachable, so no "
                        "surface could be asked: %s" % str(exc)[:200]]
        if org is None:
            return {}, ["  [no-evidence] no Organization row exists, so there "
                        "is no tenant whose numbers could be compared."]

        # Multi-tenancy in this codebase is enforced by ORM events keyed on
        # g.current_org_id (app/middleware/tenant_isolation.py), and it is a
        # deliberate no-op when that is unset. Nothing establishes it outside a
        # real request, so the ORM surfaces below would count EVERY
        # organisation's rows while the HTTP surfaces -- which run as a
        # logged-in user -- count one. That difference is an artefact of this
        # script, not a defect in the product, and it would be reported as a
        # finding on every multi-tenant install. Setting it explicitly is what
        # makes the two halves answer the same question.
        g.current_org_id = org.id

        client = app.test_client()
        if user is not None:
            with client.session_transaction() as sess:
                sess["_user_id"] = str(user.id)
                sess["_fresh"] = True

        for concept, surfaces in CONCEPTS.items():
            rows = []
            for surface in surfaces:
                if surface.waived and ALLOW_MARKER in surface.waived:
                    continue
                count, why = _ask(surface, db, client)
                if count is None:
                    notes.append("  %s [unanswered] %s: %s"
                                 % (concept, surface.name, why))
                    continue
                rows.append((surface.name, count, surface.scope))
            observations[concept] = rows

        notes.insert(0, "  tenant: organization id=%s%s"
                     % (org.id, "" if user else " (no user; HTTP surfaces will "
                        "redirect to login and be reported unanswered)"))
    return observations, notes


def _ask(surface, db, client):
    """(count, reason-it-could-not-answer)."""
    if surface.kind == "orm":
        module, _, cls = surface.target.rpartition(".")
        try:
            model = getattr(__import__(module, fromlist=[cls]), cls)
        except Exception as exc:
            return None, "model %s could not be imported (%s)" % (
                surface.target, str(exc)[:120])
        try:
            return int(db.session.query(model).count()), None
        except Exception as exc:
            db.session.rollback()
            return None, "the query failed: %s" % str(exc)[:160]

    try:
        response = client.get(surface.target)
    except Exception as exc:
        return None, "the request raised: %s" % str(exc)[:160]
    if response.status_code != 200:
        return None, "HTTP %d (not an answer, so not compared)" % response.status_code
    try:
        payload = response.get_json()
    except Exception:
        payload = None
    if payload is None:
        return None, "the response was not JSON"
    try:
        return _extract(payload, surface.extract or "len:"), None
    except KeyError as exc:
        return None, "the response did not carry a count: %s" % exc


def observe_synthetic(root):
    """Observations recorded in <root>/store_agreement_probe.json.

    The synthetic form of a boot: the numbers the surfaces WOULD have returned.
    It exists so the comparison judgement -- the part of this gate that can be
    wrong -- is testable without a seeded database.
    """
    path = os.path.join(root, "store_agreement_probe.json")
    if not os.path.exists(path):
        return {}, ["  [no-evidence] no store_agreement_probe.json under %s"
                    % root]
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    observations = {}
    for concept, rows in raw.items():
        kept = []
        for row in rows:
            if ALLOW_MARKER in str(row.get("waived", "")):
                continue
            kept.append((row["surface"], row.get("count"),
                         row.get("scope", "all")))
        observations[concept] = kept
    return observations, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()

    if args.root:
        observations, notes = observe_synthetic(os.path.abspath(args.root))
    else:
        observations, notes = observe_live()

    findings, more_notes = compare(observations)
    notes += more_notes

    if not args.count:
        for line in notes:
            print(line)
        for line in findings:
            print(line)
        if findings:
            print()
            print(
                "Two surfaces answered one question differently. Pick the "
                "canonical store,\nrepoint the other surface at it, and delete "
                "the duplicate read. If the\ndifference is real and permanent, "
                "declare it -- give the narrower surface a\n`scope=` naming its "
                "filter, or `waived=\"store-agreement-ok: <reason>\"`\nsaying "
                "what keeps the divergence bounded.")
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
