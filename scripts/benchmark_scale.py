#!/usr/bin/env python
"""ARCH-090: seed a large synthetic dataset and benchmark key endpoints at scale.

This is NOT a pytest test — it is a standalone operational script, deliberately
outside ``tests/`` and carrying no ``pytest`` marker, so a bare ``pytest`` run
never touches it and it is not wired into ``scripts/verify.py`` or CI. It also
does real, non-trivial writes (thousands of rows), which the CI/local test
database is not sized or scoped for.

Usage
-----
    python scripts/benchmark_scale.py --i-know-this-is-not-prod \\
        --applications 10000 --elements 50000 --solutions 500 --users 1000

Safety
------
Refuses to run unless BOTH of the following hold:
  1. ``--i-know-this-is-not-prod`` is passed explicitly.
  2. The resolved ``DATABASE_URL`` (or ``TEST_DATABASE_URL`` if set) does not
     look like a production URL — no host/db name containing "prod", and the
     script only proceeds against a database whose name contains "test" or
     was explicitly confirmed via the flag above. Both checks must pass;
     either one failing aborts before any write.

What it does
------------
1. Seeds N synthetic ApplicationComponent / ArchiMateElement / Solution / User
   rows in bulk (fast inserts, not one-row-at-a-time ORM writes) under one
   throwaway benchmark Organization.
2. Times a fixed set of "key endpoint" code paths — the same query patterns
   the real routes execute — across a number of iterations, and reports p50/
   p95/p99 latency against a budget (default: 1s list views, 2s analysis
   views, per ARCH-090's acceptance criteria).
3. Prints a pass/fail table. Does not modify the schema-drift or verify.py
   gates. Does not delete its own data automatically — pass ``--cleanup`` to
   remove the benchmark organization's rows afterward.

This script intentionally does not import ``app.testing`` fixtures or run
under pytest's transaction-rollback ``db_session`` — a benchmark of realistic
scale needs a real, committed dataset, and cleanup is opt-in and explicit.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid


def _looks_like_prod(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if "prod" in lowered:
        return True
    # A URL naming neither "test" nor "dev" nor "local" is treated as
    # unknown/risky and refused — this script only ever proceeds against a
    # database that positively identifies itself as non-production.
    return not any(tag in lowered for tag in ("test", "dev", "local", "benchmark"))


def _resolve_db_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""


def _safety_check(force: bool) -> None:
    if not force:
        print(
            "Refusing to run: pass --i-know-this-is-not-prod to confirm this is not "
            "a production database.",
            file=sys.stderr,
        )
        sys.exit(2)
    url = _resolve_db_url()
    if _looks_like_prod(url):
        print(
            f"Refusing to run: the resolved database URL looks like production "
            f"or is not clearly identified as a test/dev database ({url!r} redacted "
            f"pattern check failed). Set TEST_DATABASE_URL to a database whose name "
            f"contains 'test', 'dev', 'local' or 'benchmark'.",
            file=sys.stderr,
        )
        sys.exit(2)


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return float("nan")
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))
    return ordered[idx]


def seed(app, db, org_id: int, n_apps: int, n_elements: int, n_solutions: int, n_users: int):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import Solution
    from app.models.user import User

    tag = uuid.uuid4().hex[:8]
    print(f"Seeding: {n_apps} applications, {n_elements} elements, {n_solutions} solutions, {n_users} users (tag={tag})")

    t0 = time.perf_counter()
    batch = []
    for i in range(n_apps):
        batch.append(
            ApplicationComponent(
                name=f"BENCH-{tag} App {i}",
                organization_id=org_id,
                lifecycle_status="operational",
            )
        )
        if len(batch) >= 1000:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            batch = []
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
    print(f"  applications: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    batch = []
    for i in range(n_elements):
        batch.append(
            ArchiMateElement(
                name=f"BENCH-{tag} Element {i}",
                type="ApplicationComponent",
                layer="application",
                organization_id=org_id,
            )
        )
        if len(batch) >= 1000:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            batch = []
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
    print(f"  elements: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    batch = []
    for i in range(n_solutions):
        batch.append(Solution(name=f"BENCH-{tag} Solution {i}", organization_id=org_id))
        if len(batch) >= 1000:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            batch = []
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
    print(f"  solutions: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    batch = []
    for i in range(n_users):
        batch.append(
            User(
                email=f"bench-{tag}-{i}@example.com",
                first_name="Bench",
                last_name=f"User{i}",
                organization_id=org_id,
                confirmed=True,
            )
        )
        if len(batch) >= 1000:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            batch = []
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
    print(f"  users: {time.perf_counter() - t0:.1f}s")

    return tag


def benchmark(app, db, org_id: int, iterations: int):
    from flask import g

    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import Solution

    results = {}

    def _timed(label, fn, budget_s):
        g.current_org_id = org_id
        samples = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            samples.append(time.perf_counter() - t0)
        p50, p95, p99 = _percentile(samples, 50), _percentile(samples, 95), _percentile(samples, 99)
        results[label] = (p50, p95, p99, budget_s, p95 <= budget_s)

    with app.test_request_context("/"):
        _timed(
            "applications list (page 1, 50/page)",
            lambda: ApplicationComponent.query.order_by(ApplicationComponent.name)
            .paginate(page=1, per_page=50, error_out=False),
            1.0,
        )
        _timed(
            "archimate elements list (page 1, 50/page)",
            lambda: ArchiMateElement.query.order_by(ArchiMateElement.id)
            .paginate(page=1, per_page=50, error_out=False),
            1.0,
        )
        _timed(
            "solutions count (analysis-style aggregate)",
            lambda: Solution.query.count(),
            2.0,
        )

    return results


def cleanup(db, org_id: int):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import Solution
    from app.models.user import User

    for model in (ApplicationComponent, ArchiMateElement, Solution, User):
        model.query.filter_by(organization_id=org_id).delete(synchronize_session=False)
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--i-know-this-is-not-prod", action="store_true", dest="force")
    parser.add_argument("--applications", type=int, default=10000)
    parser.add_argument("--elements", type=int, default=50000)
    parser.add_argument("--solutions", type=int, default=500)
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=20, help="samples per benchmarked query")
    parser.add_argument("--cleanup", action="store_true", help="delete the benchmark org's rows afterward")
    args = parser.parse_args()

    _safety_check(args.force)

    os.environ.setdefault("FLASK_CONFIG", "testing" if os.environ.get("TEST_DATABASE_URL") else "development")
    from app import create_app, db
    from app.models.organization import Organization

    app = create_app(os.environ["FLASK_CONFIG"])
    with app.app_context():
        tag = uuid.uuid4().hex[:8]
        org = Organization(name=f"Benchmark {tag}", slug=f"benchmark-{tag}")
        db.session.add(org)
        db.session.commit()

        seed(app, db, org.id, args.applications, args.elements, args.solutions, args.users)
        results = benchmark(app, db, org.id, args.iterations)

        print("\np95 latency vs budget (ARCH-090):")
        print(f"{'query':45s} {'p50':>8s} {'p95':>8s} {'p99':>8s} {'budget':>8s}  status")
        all_pass = True
        for label, (p50, p95, p99, budget, ok) in results.items():
            all_pass = all_pass and ok
            print(
                f"{label:45s} {p50 * 1000:7.1f}ms {p95 * 1000:7.1f}ms {p99 * 1000:7.1f}ms "
                f"{budget * 1000:7.0f}ms  {'PASS' if ok else 'FAIL'}"
            )

        if args.cleanup:
            print("\nCleaning up benchmark rows...")
            cleanup(db, org.id)
            db.session.delete(org)
            db.session.commit()
        else:
            print(f"\nBenchmark org id={org.id} left in place (pass --cleanup to remove).")

        sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
