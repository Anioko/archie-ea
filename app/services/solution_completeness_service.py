"""SA-008: Solution design completeness checker.

Scores how complete a solution architecture is across ArchiMate layers
and TOGAF ADM phases.  Returns a structured dict (JSON-serialisable).
"""
import logging

logger = logging.getLogger(__name__)

# ── Dimension definitions ────────────────────────────────────────────────────

_DIMENSIONS = [
    {
        "key": "motivation",
        "name": "Motivation Layer",
        "max_score": 20,
        "layer": "Motivation",
        "required_types": ["Stakeholder", "Driver", "Goal", "Requirement"],
        "recommendation_tpl": "Add at least one {missing} element to the Motivation layer",
    },
    {
        "key": "business",
        "name": "Business Layer",
        "max_score": 20,
        "layer": "Business",
        "required_types": ["BusinessActor", "BusinessProcess", "BusinessService"],
        "recommendation_tpl": "Add at least one {missing} element to the Business layer",
    },
    {
        "key": "application",
        "name": "Application Layer",
        "max_score": 20,
        "layer": "Application",
        "required_types": ["ApplicationComponent", "ApplicationService"],
        "recommendation_tpl": "Add at least one {missing} element to the Application layer",
    },
    {
        "key": "technology",
        "name": "Technology Layer",
        "max_score": 15,
        "layer": "Technology",
        "required_types": ["Node", "TechnologyService"],
        "recommendation_tpl": "Add at least one {missing} element to the Technology layer",
    },
]

# ADM phases mapped to ArchiMate element types commonly associated with each phase
_ADM_PHASE_TYPES: dict[str, list[str]] = {
    "Preliminary": ["Principle", "Constraint"],
    "A-Vision": ["Goal", "Stakeholder", "Driver"],
    "B-Business": ["BusinessActor", "BusinessProcess", "BusinessService", "BusinessRole"],
    "C-Application": ["ApplicationComponent", "ApplicationService", "ApplicationInterface"],
    "D-Technology": ["Node", "TechnologyService", "Device", "SystemSoftware"],
    "E-Opportunities": ["Plateau", "Gap"],
    "F-Migration": ["WorkPackage", "ImplementationEvent"],
    "G-Implementation": ["Deliverable", "ImplementationEvent"],
    "H-Change": ["Driver", "Assessment"],
}

_SCORE_BANDS = [
    (91, 100, "Complete"),
    (71, 90, "Substantial"),
    (41, 70, "Partial"),
    (0, 40, "Incomplete"),
]


def _band(score: int) -> str:
    for lo, hi, label in _SCORE_BANDS:
        if lo <= score <= hi:
            return label
    return "Incomplete"


# ── Public API ───────────────────────────────────────────────────────────────

def check_completeness(solution_id: int) -> dict:
    """Return a completeness report for *solution_id*.

    Returns::

        {
            "solution_id": int,
            "total_score": int,        # 0-100
            "band": str,               # Incomplete | Partial | Substantial | Complete
            "dimensions": [...],       # 6 dimension dicts
            "recommendations": [...]   # top-3 action strings
        }
    """
    from app import db
    from sqlalchemy import text

    # ── 1. Collect element types linked to this solution ───────────────────
    element_types: set[str] = set()
    layers_present: dict[str, set[str]] = {}  # layer → set of element types

    try:
        rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            text(
                """
                SELECT ae.layer, ae.type
                FROM   solution_elements se
                JOIN   archimate_elements ae ON ae.id = se.archimate_element_id
                WHERE  se.solution_id = :sid
                """
            ),
            {"sid": solution_id},
        ).fetchall()
        for layer, etype in rows:
            layer = (layer or "").strip()
            etype = (etype or "").strip()
            element_types.add(etype)
            layers_present.setdefault(layer, set()).add(etype)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SA-008 element query failed: %s", exc)
        try:
            db.session.rollback()
        except Exception as rb_exc:  # noqa: BLE001
            logger.debug("SA-008 rollback failed: %s", rb_exc)

    # Also pull counts from archimate_elements directly scoped to this solution
    # via the solution_elements join (already done above).

    # ── 2. Score each of the 4 layer dimensions ────────────────────────────
    dimensions: list[dict] = []
    total_score = 0
    low_score_dims: list[dict] = []

    for dim in _DIMENSIONS:
        layer_types = layers_present.get(dim["layer"], set())
        found = [t for t in dim["required_types"] if t in layer_types or t in element_types]
        missing = [t for t in dim["required_types"] if t not in found]
        n_total = len(dim["required_types"])
        score = round(dim["max_score"] * len(found) / n_total) if n_total else 0
        pct = round(100 * len(found) / n_total) if n_total else 0
        rec = (
            dim["recommendation_tpl"].format(missing=", ".join(missing[:2]))
            if missing
            else ""
        )
        entry = {
            "name": dim["name"],
            "max_score": dim["max_score"],
            "score": score,
            "pct": pct,
            "found": found,
            "missing": missing,
            "recommendation": rec,
        }
        dimensions.append(entry)
        total_score += score
        if score < dim["max_score"]:
            low_score_dims.append(entry)

    # ── 3. Cross-layer traceability (15 pts) ──────────────────────────────
    xlt_score, xlt_pct, xlt_found, xlt_missing, xlt_rec = _score_cross_layer(
        solution_id, layers_present
    )
    total_score += xlt_score
    xlt_entry = {
        "name": "Cross-Layer Traceability",
        "max_score": 15,
        "score": xlt_score,
        "pct": xlt_pct,
        "found": xlt_found,
        "missing": xlt_missing,
        "recommendation": xlt_rec,
    }
    dimensions.append(xlt_entry)
    if xlt_score < 15:
        low_score_dims.append(xlt_entry)

    # ── 4. ADM phase coverage (10 pts) ────────────────────────────────────
    adm_score, adm_pct, adm_found, adm_missing, adm_rec = _score_adm_phases(element_types)
    total_score += adm_score
    adm_entry = {
        "name": "ADM Phase Coverage",
        "max_score": 10,
        "score": adm_score,
        "pct": adm_pct,
        "found": adm_found,
        "missing": adm_missing,
        "recommendation": adm_rec,
    }
    dimensions.append(adm_entry)
    if adm_score < 10:
        low_score_dims.append(adm_entry)

    # ── 5. Build top-3 recommendations ────────────────────────────────────
    # Sort low-score dims by gap (max - score) descending, pick top 3
    low_score_dims.sort(key=lambda d: d["max_score"] - d["score"], reverse=True)
    recommendations = [
        d["recommendation"] for d in low_score_dims if d["recommendation"]
    ][:3]
    if not recommendations:
        recommendations = ["Solution is well-defined across all dimensions."]

    return {
        "solution_id": solution_id,
        "total_score": min(total_score, 100),
        "band": _band(min(total_score, 100)),
        "dimensions": dimensions,
        "recommendations": recommendations,
    }


# ── Dimension helpers ────────────────────────────────────────────────────────

def _score_cross_layer(
    solution_id: int, layers_present: dict[str, set[str]]
) -> tuple[int, int, list[str], list[str], str]:
    """Score cross-layer traceability (15 pts).

    Checks whether ArchiMate relationships link elements across different layers
    for this solution.
    """
    from app import db
    from sqlalchemy import text

    linked_pairs: set[str] = set()
    try:
        rows = db.session.execute(  # tenant-filtered: scoped via parent FK (solution_id)
            text(
                """
                SELECT DISTINCT src.layer, tgt.layer
                FROM   solution_elements se
                JOIN   archimate_elements src ON src.id = se.archimate_element_id
                JOIN   archimate_relationships ar ON (
                           ar.source_id = src.id OR ar.target_id = src.id
                       )
                JOIN   archimate_elements tgt ON (
                           tgt.id = CASE WHEN ar.source_id = src.id
                                         THEN ar.target_id ELSE ar.source_id END
                       )
                WHERE  se.solution_id = :sid
                  AND  src.layer IS NOT NULL
                  AND  tgt.layer IS NOT NULL
                  AND  src.layer <> tgt.layer
                LIMIT  50
                """
            ),
            {"sid": solution_id},
        ).fetchall()
        for r in rows:
            pair = tuple(sorted([r[0] or "", r[1] or ""]))
            linked_pairs.add(f"{pair[0]}↔{pair[1]}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("SA-008 cross-layer query failed: %s", exc)
        try:
            db.session.rollback()
        except Exception as rb_exc:  # noqa: BLE001
            logger.debug("SA-008 cross-layer rollback failed: %s", rb_exc)

    # Check also from layers_present: if ≥ 2 distinct layers present, partial credit
    present_layers = [la for la in layers_present if la]
    if not linked_pairs and len(present_layers) >= 2:
        linked_pairs = {f"{present_layers[i]}↔{present_layers[j]}"
                        for i in range(len(present_layers))
                        for j in range(i + 1, len(present_layers))}

    expected_pairs = {"Business↔Application", "Application↔Technology", "Motivation↔Business"}
    found = [p for p in linked_pairs if p in expected_pairs or
             any(p == f"{b}↔{a}" for b, a in [p.split("↔")] for _ in [None])]
    # Simpler: just count distinct cross-layer pairs
    found_list = list(linked_pairs)[:3]
    missing_list = [p for p in expected_pairs if p not in linked_pairs]

    n_found = min(len(linked_pairs), 3)
    score = round(15 * n_found / 3)
    pct = round(100 * n_found / 3)
    rec = (
        f"Link elements across {', '.join(list(missing_list)[:2])} layers via relationships"
        if missing_list
        else ""
    )
    return score, pct, found_list, missing_list, rec


def _score_adm_phases(element_types: set[str]) -> tuple[int, int, list[str], list[str], str]:
    """Score ADM phase coverage (10 pts, target ≥ 5 of 9 phases)."""
    covered: list[str] = []
    uncovered: list[str] = []
    for phase, types in _ADM_PHASE_TYPES.items():
        if any(t in element_types for t in types):
            covered.append(phase)
        else:
            uncovered.append(phase)

    n_covered = len(covered)
    target = 5
    score = round(10 * min(n_covered, target) / target)
    pct = round(100 * min(n_covered, target) / target)
    rec = (
        f"Cover ADM phases {', '.join(uncovered[:3])} with at least one element each"
        if uncovered
        else ""
    )
    return score, pct, covered, uncovered, rec
