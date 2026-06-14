"""Smart Defaults Service — NON-LLM solution bootstrapping from REAL platform data.

Solves the cold start problem: new solutions have empty forms. This service
queries the platform's ACTUAL data — 2,763 ArchiMate elements, 412
application-capability mappings, 850 applications — and returns intelligent
suggestions based on the solution's description, business_domain, and type.

NO LLM calls. NO template strings. Pure database queries against real data.

Design principles:
- Every suggestion comes from a real database record
- Capabilities are ranked by how many apps they actually have
- Drivers and goals are existing ArchiMate elements, not generated text
- Applications are sorted by relevance (domain match, lifecycle status)
- Vendor products come from actual app-vendor relationships
"""

import logging
from collections import defaultdict

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db

logger = logging.getLogger(__name__)


def generate_smart_defaults(solution):
    """Generate smart defaults for a solution from real platform data.

    Strategy:
    1. Find capabilities matching the solution's domain, ranked by app count
    2. Find applications linked to those capabilities, sorted by lifecycle relevance
    3. Find vendor products linked to those applications
    4. Find existing ArchiMate Driver/Goal/Constraint elements relevant to the domain
    5. Return all as suggestions — every item has a real DB id

    Returns a dict with real database records, not template text.
    """
    domain = (solution.business_domain or "").strip()
    description = (solution.description or solution.name or "").strip().lower()

    # Fix 10: If both description and domain are empty, return early
    if not domain and not description:
        return {
            "capabilities": [],
            "applications": [],
            "vendor_products": [],
            "drivers": [],
            "goals": [],
            "constraints": [],
            "summary": "Add a description and select a business domain to get intelligent suggestions.",
        }

    results = {
        "capabilities": [],
        "applications": [],
        "vendor_products": [],
        "drivers": [],
        "goals": [],
        "constraints": [],
        "summary": "",
    }

    # Build a unified keyword list from domain + description for scoring
    stop_words = {
        "the", "a", "an", "to", "for", "of", "in", "on", "and", "or",
        "is", "are", "was", "will", "be", "this", "that", "with", "from",
        "by", "at", "as", "it", "its", "our", "we", "us", "new", "all",
        "has", "have", "been", "can", "not", "but", "also", "into",
        "solution", "system", "platform", "project",
    }
    all_keywords = []
    if domain:
        for w in domain.lower().split():
            if len(w) > 2 and w not in stop_words:
                all_keywords.append(w)
    if description:
        for w in description.split():
            if len(w) > 3 and w not in stop_words:
                all_keywords.append(w)
    all_keywords = list(dict.fromkeys(all_keywords))[:10]  # deduplicate, limit

    # ── 1. Find capabilities ranked by relevance × app coverage ────────────
    # Score = domain_match_score * max(app_count, 1). A 0-relevance capability
    # scores 0 regardless of app count. A domain-matched capability with 5 apps
    # scores 50 (10 * 5).
    try:
        from app.models.business_capabilities import BusinessCapability
        from app.models.application_capability import ApplicationCapabilityMapping

        # Count apps per capability
        cap_app_counts = dict(
            db.session.query(
                ApplicationCapabilityMapping.business_capability_id,
                func.count(ApplicationCapabilityMapping.id),
            )
            .group_by(ApplicationCapabilityMapping.business_capability_id)
            .all()
        )

        # Build candidate capabilities with scoring
        scored_caps = []
        scored_cap_ids = set()

        # a) Domain match + keyword match combined in a single pass
        if domain or all_keywords:
            domain_filters = []
            if domain:
                domain_filters.extend([
                    BusinessCapability.business_domain.ilike(f"%{domain}%"),
                    BusinessCapability.name.ilike(f"%{domain}%"),
                    BusinessCapability.category.ilike(f"%{domain}%"),
                ])
            if all_keywords:
                domain_filters.extend([BusinessCapability.name.ilike(f"%{kw}%") for kw in all_keywords])

            matching_caps = (
                BusinessCapability.query
                .filter(
                    BusinessCapability.is_deprecated.isnot(True),
                    or_(*domain_filters),
                )
                .all()
            )

            for cap in matching_caps:
                cap_name_lower = (cap.name or "").lower()
                cap_domain_lower = (cap.business_domain or cap.category or "").lower()
                cap_desc_lower = (cap.description or "").lower()
                cap_text = cap_name_lower + " " + cap_domain_lower + " " + cap_desc_lower

                # Calculate relevance score based on keyword matches
                relevance = 0
                if domain and domain.lower() in cap_text:
                    relevance += 10
                for kw in all_keywords:
                    if kw in cap_text:
                        relevance += 2

                if relevance > 0:
                    app_count = cap_app_counts.get(cap.id, 0)
                    # Multiplicative: relevance * max(app_count, 1)
                    score = relevance * max(app_count, 1)
                    scored_caps.append((cap, score))
                    scored_cap_ids.add(cap.id)

        # b) If still sparse, add the most-connected capabilities (ones with most apps)
        if len(scored_caps) < 3 and cap_app_counts:
            top_cap_ids = sorted(cap_app_counts.keys(), key=lambda k: cap_app_counts[k], reverse=True)[:10]
            if top_cap_ids:
                top_caps = BusinessCapability.query.filter(
                    BusinessCapability.id.in_(top_cap_ids),
                    BusinessCapability.is_deprecated.isnot(True),
                ).all()
                for cap in top_caps:
                    if cap.id not in scored_cap_ids:
                        scored_caps.append((cap, cap_app_counts.get(cap.id, 0)))

        # Sort by score descending, take top 5
        scored_caps.sort(key=lambda x: x[1], reverse=True)
        selected_caps = scored_caps[:5]

        results["capabilities"] = [
            {
                "id": cap.id,
                "name": cap.name,
                "domain": cap.business_domain or cap.category or "",
                "level": cap.level or 1,
                "app_count": cap_app_counts.get(cap.id, 0),
                "current_maturity": cap.current_maturity_level,
                "target_maturity": cap.target_maturity_level,
                "description": (cap.description or "")[:120],
            }
            for cap, _score in selected_caps
        ]

    except Exception as e:
        logger.warning("Smart defaults: capability query failed: %s", e)

    # ── 2. Find applications linked to those capabilities ──────────────────
    # Sort order depends on solution context: migration/decommission solutions
    # show TACTICAL/SUNSET first (the migration candidates). Others show STRATEGIC first.
    try:
        from app.models.application_portfolio import ApplicationComponent
        from app.models.application_capability import ApplicationCapabilityMapping

        if results["capabilities"]:
            cap_ids = [c["id"] for c in results["capabilities"]]
            app_mappings = (
                ApplicationCapabilityMapping.query
                .filter(ApplicationCapabilityMapping.business_capability_id.in_(cap_ids))
                .all()
            )
            app_ids = list({m.application_component_id for m in app_mappings})

            if app_ids:
                # Fix 6: Context-aware sort order
                sol_type = (getattr(solution, "solution_type", "") or "").lower()
                sol_desc = description.lower()
                is_migration_context = any(
                    kw in sol_type or kw in sol_desc
                    for kw in ("migration", "decommission", "consolidation", "sunset", "retire")
                )

                if is_migration_context:
                    _lifecycle_order = {
                        "2.2 TACTICAL": 0,
                        "3. SUNSET": 1,
                        "1. UNDETERMINED": 2,
                        "2.1 STRATEGIC": 3,
                    }
                else:
                    _lifecycle_order = {
                        "2.1 STRATEGIC": 0,
                        "2.2 TACTICAL": 1,
                        "1. UNDETERMINED": 2,
                        "3. SUNSET": 3,
                    }
                _exclude = {"5. DECOMMISSIONED", "4.1 DECOM DECIDED", "4.2 DECOM PLANNED", "4.4 STOPPED"}

                apps = (
                    ApplicationComponent.query
                    .filter(ApplicationComponent.id.in_(app_ids))
                    .all()
                )
                # Filter and sort
                active_apps = [a for a in apps if (a.lifecycle_status or "") not in _exclude]
                active_apps.sort(key=lambda a: (
                    _lifecycle_order.get(a.lifecycle_status or "", 99),
                    (a.name or "").lower(),
                ))

                # Count capabilities per app for context
                app_cap_counts = defaultdict(int)
                for m in app_mappings:
                    app_cap_counts[m.application_component_id] += 1

                results["applications"] = [
                    {
                        "id": app.id,
                        "name": app.name or "",
                        "vendor": getattr(app, "vendor_name", "") or "",
                        "lifecycle_status": app.lifecycle_status or "",
                        "capability_count": app_cap_counts.get(app.id, 0),
                    }
                    for app in active_apps[:8]
                ]

    except Exception as e:
        logger.warning("Smart defaults: application query failed: %s", e)

    # ── 3. Find vendor products through app-vendor relationships ───────────
    try:
        from app.models.vendor.vendor_organization import VendorProduct

        # Strategy: Search by solution name keywords AND by domain
        vp_candidates = []

        # a) Keyword match from solution name (e.g., "SAP" in "SAP S/4HANA Migration")
        name_words = [w for w in (solution.name or "").split() if len(w) > 2]
        if name_words:
            kw_filters = [VendorProduct.name.ilike(f"%{kw}%") for kw in name_words[:5]]
            vp_by_name = (
                VendorProduct.query
                .options(joinedload(VendorProduct.vendor_organization))
                .filter(or_(*kw_filters))
                .limit(10)
                .all()
            )
            vp_candidates.extend(vp_by_name)

        # b) If apps were found, check if any have vendor product links
        if results["applications"] and not vp_candidates:
            app_ids_found = [a["id"] for a in results["applications"]]
            try:
                # Check application_vendor_product_mappings
                from app.models.capability_to_vendor_mapping import ApplicationVendorProductMapping
                avp_mappings = (
                    ApplicationVendorProductMapping.query
                    .filter(ApplicationVendorProductMapping.application_component_id.in_(app_ids_found))
                    .limit(10)
                    .all()
                )
                vp_ids = [m.vendor_product_id for m in avp_mappings]
                if vp_ids:
                    vp_candidates = (
                        VendorProduct.query
                        .options(joinedload(VendorProduct.vendor_organization))
                        .filter(VendorProduct.id.in_(vp_ids))
                        .all()
                    )
            except Exception as e:
                logger.debug("App-vendor product mapping query failed: %s", e)

        # Deduplicate
        seen_vp_ids = set()
        unique_vps = []
        for vp in vp_candidates:
            if vp.id not in seen_vp_ids:
                seen_vp_ids.add(vp.id)
                unique_vps.append(vp)

        results["vendor_products"] = [
            {
                "id": vp.id,
                "name": vp.name or "",
                "vendor_name": (vp.vendor_organization.name if vp.vendor_organization else ""),
                "category": getattr(vp, "product_family_name", "") or "",
            }
            for vp in unique_vps[:5]
        ]

    except Exception as e:
        logger.warning("Smart defaults: vendor product query failed: %s", e)

    # ── 4. Find EXISTING ArchiMate motivation elements ─────────────────────
    # Instead of generating template text, suggest real Driver/Goal/Constraint
    # elements already in the database. There are 27 Drivers, 36 Goals, etc.
    try:
        from app.models.archimate_core import ArchiMateElement

        # Build keyword list for relevance scoring
        search_terms = []
        if domain:
            search_terms.append(domain.lower())
        for word in (solution.name or "").lower().split():
            if len(word) > 3:
                search_terms.append(word)
        for word in (solution.description or "").lower().split():
            if len(word) > 4 and word not in {"solution", "system", "platform", "architecture", "enterprise"}:
                search_terms.append(word)
        search_terms = list(dict.fromkeys(search_terms))[:10]  # Deduplicate, limit

        def _score_element(elem):
            """Score an ArchiMate element by keyword relevance."""
            text = ((elem.name or "") + " " + (elem.description or "")).lower()
            score = 0
            for term in search_terms:
                if term in text:
                    score += 1
            return score

        # Query Drivers (type='driver' in archimate_elements)
        all_drivers = ArchiMateElement.query.filter(
            ArchiMateElement.type.in_(["driver", "Driver"]),
        ).all()
        scored_drivers = [(d, _score_element(d)) for d in all_drivers]
        scored_drivers.sort(key=lambda x: x[1], reverse=True)

        results["drivers"] = [
            {
                "id": d.id,
                "name": d.name,
                "description": (d.description or "")[:200],
                "archimate_element_id": d.id,
                "source": "archimate_elements",
            }
            for d, score in scored_drivers[:3]
            if score > 0 or len(scored_drivers) <= 5  # Take top matches, or all if few exist
        ]
        # If no relevant matches, take top 2 anyway — they're real data
        if not results["drivers"] and all_drivers:
            results["drivers"] = [
                {
                    "id": d.id,
                    "name": d.name,
                    "description": (d.description or "")[:200],
                    "archimate_element_id": d.id,
                    "source": "archimate_elements",
                }
                for d in all_drivers[:2]
            ]

        # Query Goals
        all_goals = ArchiMateElement.query.filter(
            ArchiMateElement.type.in_(["goal", "Goal"]),
        ).all()
        scored_goals = [(g, _score_element(g)) for g in all_goals]
        scored_goals.sort(key=lambda x: x[1], reverse=True)

        results["goals"] = [
            {
                "id": g.id,
                "name": g.name,
                "description": (g.description or "")[:200],
                "archimate_element_id": g.id,
                "source": "archimate_elements",
            }
            for g, score in scored_goals[:3]
            if score > 0 or len(scored_goals) <= 5
        ]
        if not results["goals"] and all_goals:
            results["goals"] = [
                {
                    "id": g.id,
                    "name": g.name,
                    "description": (g.description or "")[:200],
                    "archimate_element_id": g.id,
                    "source": "archimate_elements",
                }
                for g in all_goals[:2]
            ]

        # Query Constraints — only suggest if keyword-relevant (Fix 9)
        all_constraints = ArchiMateElement.query.filter(
            ArchiMateElement.type.in_(["constraint", "Constraint"]),
        ).all()
        scored_constraints = [(c, _score_element(c)) for c in all_constraints]
        scored_constraints.sort(key=lambda x: x[1], reverse=True)

        # Only include constraints that actually match keywords. If there are
        # very few total (<=3), include all. Otherwise require score > 0.
        relevant_constraints = [
            (c, score) for c, score in scored_constraints[:2]
            if score > 0 or len(all_constraints) <= 3
        ]

        if relevant_constraints:
            results["constraints"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": (c.description or "")[:200],
                    "archimate_element_id": c.id,
                    "source": "archimate_elements",
                }
                for c, score in relevant_constraints
            ]
        # If nothing matched and there are many constraints, return empty
        # (don't suggest random ones just to fill the list)

    except Exception as e:
        logger.warning("Smart defaults: ArchiMate element query failed: %s", e)

    # ── 5. Build summary ──────────────────────────────────────────────────
    cap_count = len(results["capabilities"])
    app_count = len(results["applications"])
    vp_count = len(results["vendor_products"])
    drv_count = len(results["drivers"])
    goal_count = len(results["goals"])
    cst_count = len(results["constraints"])

    results["summary"] = (
        f"Found {cap_count} capabilities (by app coverage), "
        f"{app_count} applications (strategic first), "
        f"{vp_count} vendor products, "
        f"{drv_count} existing drivers, {goal_count} goals, "
        f"{cst_count} constraints from ArchiMate catalog."
    )

    return results


def apply_smart_defaults(solution, defaults):
    """Apply smart defaults to a solution — creates real DB records.

    For capabilities, apps, vendors: creates junction table links.
    For drivers/goals/constraints: links existing ArchiMate elements to the
    solution via SolutionArchiMateElement AND creates SolutionDriver/Goal/
    Constraint records pointing to those elements.

    Returns a dict with counts of what was created.
    """
    from flask_login import current_user
    from app.models.solution_models import (
        SolutionArchiMateElement,
        SolutionCapabilityMapping,
    )
    from app.models.solution_architect_models import (
        SolutionAnalysisSession,
        SolutionConstraint,
        SolutionDriver,
        SolutionGoal,
        SolutionProblemDefinition,
        ConstraintType,
        DriverType,
    )

    created = {
        "capabilities": 0,
        "applications": 0,
        "vendor_products": 0,
        "drivers": 0,
        "goals": 0,
        "constraints": 0,
    }
    # Track created IDs for revert support (Fix 8)
    created_ids = {
        "capability_mapping_ids": [],
        "application_ids": [],
        "vendor_product_ids": [],
        "driver_ids": [],
        "goal_ids": [],
        "constraint_ids": [],
        "archimate_link_ids": [],
    }

    solution_id = solution.id

    # ── Ensure analysis session + problem definition exist ─────────────────
    if not solution.analysis_session_id:
        session_obj = SolutionAnalysisSession(
            name=f"{solution.name} Analysis",
            created_by_id=current_user.id,
        )
        db.session.add(session_obj)
        db.session.flush()
        pd = SolutionProblemDefinition(
            session_id=session_obj.id,
            problem_description=solution.description or solution.name,
        )
        db.session.add(pd)
        db.session.flush()
        solution.analysis_session_id = session_obj.id
        db.session.flush()
    else:
        session_obj = SolutionAnalysisSession.query.get(solution.analysis_session_id)
        pd = session_obj.problem_definition if session_obj else None
        if not pd:
            pd = SolutionProblemDefinition(
                session_id=session_obj.id,
                problem_description=solution.description or solution.name,
            )
            db.session.add(pd)
            db.session.flush()

    # ── Link capabilities ──────────────────────────────────────────────────
    for cap_data in defaults.get("capabilities", []):
        cap_id = cap_data.get("id")
        if not cap_id:
            continue
        existing = SolutionCapabilityMapping.query.filter_by(
            solution_id=solution_id, capability_id=cap_id,
        ).first()
        if not existing:
            mapping = SolutionCapabilityMapping(
                solution_id=solution_id,
                capability_id=cap_id,
            )
            db.session.add(mapping)
            db.session.flush()
            created_ids["capability_mapping_ids"].append(mapping.id)
            created["capabilities"] += 1

    # ── Link applications ──────────────────────────────────────────────────
    app_tbl = db.metadata.tables.get("solution_applications")
    if app_tbl is not None:
        for app_data in defaults.get("applications", []):
            app_id = app_data.get("id")
            if not app_id:
                continue
            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                app_tbl.select()
                .where(app_tbl.c.solution_id == solution_id)
                .where(app_tbl.c.application_component_id == app_id)
            ).first()
            if not existing:
                db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                    app_tbl.insert().values(
                        solution_id=solution_id,
                        application_component_id=app_id,
                    )
                )
                created_ids["application_ids"].append(app_id)
                created["applications"] += 1

    # ── Link vendor products ───────────────────────────────────────────────
    vp_tbl = db.metadata.tables.get("solution_vendor_products")
    if vp_tbl is not None:
        for vp_data in defaults.get("vendor_products", []):
            vp_id = vp_data.get("id")
            if not vp_id:
                continue
            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                vp_tbl.select()
                .where(vp_tbl.c.solution_id == solution_id)
                .where(vp_tbl.c.vendor_product_id == vp_id)
            ).first()
            if not existing:
                db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                    vp_tbl.insert().values(
                        solution_id=solution_id,
                        vendor_product_id=vp_id,
                    )
                )
                created_ids["vendor_product_ids"].append(vp_id)
                created["vendor_products"] += 1

    # ── Link drivers (existing ArchiMate elements) ─────────────────────────
    for drv in defaults.get("drivers", []):
        archimate_id = drv.get("archimate_element_id")
        driver = SolutionDriver(
            problem_id=pd.id,
            name=drv.get("name", ""),
            description=drv.get("description", ""),
            driver_type=DriverType.TECHNOLOGY,
            source="Smart Defaults (from ArchiMate catalog)",
            ai_generated=False,
        )
        db.session.add(driver)
        db.session.flush()
        created_ids["driver_ids"].append(driver.id)

        # Also link the ArchiMate element to the solution
        if archimate_id:
            existing_link = SolutionArchiMateElement.query.filter_by(
                solution_id=solution_id,
                element_id=archimate_id,
                element_table="archimate_elements",
            ).first()
            if not existing_link:
                link = SolutionArchiMateElement(
                    solution_id=solution_id,
                    layer_type="motivation",
                    element_id=archimate_id,
                    element_table="archimate_elements",
                    element_name=drv.get("name", ""),
                    relationship_type="associated-with",
                )
                db.session.add(link)
                db.session.flush()
                created_ids["archimate_link_ids"].append(link.id)

        created["drivers"] += 1

    # ── Link goals (existing ArchiMate elements) ───────────────────────────
    for goal_data in defaults.get("goals", []):
        archimate_id = goal_data.get("archimate_element_id")
        goal = SolutionGoal(
            problem_id=pd.id,
            name=goal_data.get("name", ""),
            description=goal_data.get("description", ""),
            priority=3,
            ai_generated=False,
        )
        db.session.add(goal)
        db.session.flush()
        created_ids["goal_ids"].append(goal.id)

        if archimate_id:
            existing_link = SolutionArchiMateElement.query.filter_by(
                solution_id=solution_id,
                element_id=archimate_id,
                element_table="archimate_elements",
            ).first()
            if not existing_link:
                link = SolutionArchiMateElement(
                    solution_id=solution_id,
                    layer_type="motivation",
                    element_id=archimate_id,
                    element_table="archimate_elements",
                    element_name=goal_data.get("name", ""),
                    relationship_type="associated-with",
                )
                db.session.add(link)
                db.session.flush()
                created_ids["archimate_link_ids"].append(link.id)

        created["goals"] += 1

    # ── Link constraints (existing ArchiMate elements) ─────────────────────
    for cst in defaults.get("constraints", []):
        archimate_id = cst.get("archimate_element_id")
        constraint = SolutionConstraint(
            problem_id=pd.id,
            name=cst.get("name", ""),
            description=cst.get("description", ""),
            constraint_type=ConstraintType.TECHNICAL,
            source="Smart Defaults (from ArchiMate catalog)",
            ai_generated=False,
        )
        db.session.add(constraint)
        db.session.flush()
        created_ids["constraint_ids"].append(constraint.id)

        if archimate_id:
            existing_link = SolutionArchiMateElement.query.filter_by(
                solution_id=solution_id,
                element_id=archimate_id,
                element_table="archimate_elements",
            ).first()
            if not existing_link:
                link = SolutionArchiMateElement(
                    solution_id=solution_id,
                    layer_type="motivation",
                    element_id=archimate_id,
                    element_table="archimate_elements",
                    element_name=cst.get("name", ""),
                    relationship_type="associated-with",
                )
                db.session.add(link)
                db.session.flush()
                created_ids["archimate_link_ids"].append(link.id)

        created["constraints"] += 1

    db.session.flush()
    return {"counts": created, "created_ids": created_ids}


def revert_smart_defaults(solution, created_ids):
    """Revert a smart defaults apply by deleting all records it created.

    Args:
        solution: The Solution model instance
        created_ids: The created_ids dict returned by apply_smart_defaults
    """
    from app.models.solution_models import (
        SolutionArchiMateElement,
        SolutionCapabilityMapping,
    )
    from app.models.solution_architect_models import (
        SolutionConstraint,
        SolutionDriver,
        SolutionGoal,
    )

    reverted = {
        "capabilities": 0,
        "applications": 0,
        "vendor_products": 0,
        "drivers": 0,
        "goals": 0,
        "constraints": 0,
        "archimate_links": 0,
    }
    solution_id = solution.id

    # Use raw table deletes throughout to avoid ORM autoflush issues
    # with SolutionArchiMateElement's unmapped column on production.

    # Remove ArchiMate links FIRST (before any ORM queries trigger autoflush)
    sae_tbl = db.metadata.tables.get("solution_archimate_elements")
    if sae_tbl is not None:
        for lid in created_ids.get("archimate_link_ids", []):
            db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                sae_tbl.delete()
                .where(sae_tbl.c.id == lid)
                .where(sae_tbl.c.solution_id == solution_id)
            )
            reverted["archimate_links"] += 1

    # Remove drivers via raw SQL
    drv_tbl = db.metadata.tables.get("solution_drivers")
    if drv_tbl is not None:
        for did in created_ids.get("driver_ids", []):
            db.session.execute(drv_tbl.delete().where(drv_tbl.c.id == did))  # tenant-filtered: scoped via parent FK
            reverted["drivers"] += 1

    # Remove goals via raw SQL
    goal_tbl = db.metadata.tables.get("solution_goals")
    if goal_tbl is not None:
        for gid in created_ids.get("goal_ids", []):
            db.session.execute(goal_tbl.delete().where(goal_tbl.c.id == gid))  # tenant-filtered: scoped via parent FK
            reverted["goals"] += 1

    # Remove constraints via raw SQL
    cst_tbl = db.metadata.tables.get("solution_constraints")
    if cst_tbl is not None:
        for cid in created_ids.get("constraint_ids", []):
            db.session.execute(cst_tbl.delete().where(cst_tbl.c.id == cid))  # tenant-filtered: scoped via parent FK
            reverted["constraints"] += 1

    # Remove capability mappings
    for mid in created_ids.get("capability_mapping_ids", []):
        obj = SolutionCapabilityMapping.query.filter_by(id=mid).first()
        if obj and obj.solution_id == solution_id:
            db.session.delete(obj)
            reverted["capabilities"] += 1

    # Remove application links
    app_tbl = db.metadata.tables.get("solution_applications")
    if app_tbl is not None:
        for app_id in created_ids.get("application_ids", []):
            db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                app_tbl.delete()
                .where(app_tbl.c.solution_id == solution_id)
                .where(app_tbl.c.application_component_id == app_id)
            )
            reverted["applications"] += 1

    # Remove vendor product links
    vp_tbl = db.metadata.tables.get("solution_vendor_products")
    if vp_tbl is not None:
        for vp_id in created_ids.get("vendor_product_ids", []):
            db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
                vp_tbl.delete()
                .where(vp_tbl.c.solution_id == solution_id)
                .where(vp_tbl.c.vendor_product_id == vp_id)
            )
            reverted["vendor_products"] += 1

    db.session.flush()
    return reverted
