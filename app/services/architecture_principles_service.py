"""VA-001: Architecture Principles register service.

Wraps the Principle ORM (app.models.motivation_extended) with query and
compliance-checking methods.  All access is via ORM — no raw SQL.
"""
import logging
from typing import Dict, List

from app import db
from app.models.motivation_extended import Principle

logger = logging.getLogger(__name__)


class ArchitecturePrinciplesService:
    """Service for querying and enforcing Architecture Principles.

    Uses the Principle ORM backed by the `principles` table.
    No raw SQL; all queries through SQLAlchemy ORM.
    """

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_all_principles(self) -> List[Principle]:
        """Return all Principle rows ordered by category then name.

        Returns an empty list if the table is empty or an error occurs;
        never raises.
        """
        try:
            return (
                db.session.query(Principle)
                .order_by(Principle.category, Principle.name)
                .all()
            )
        except Exception as exc:
            logger.warning("get_all_principles: query failed: %s", exc)
            return []

    def get_principles_by_adm_phase(self, phase: str) -> List[Principle]:
        """Return Principle rows whose adm_phase matches *phase* exactly.

        Returns an empty list on error; never raises.
        """
        if not phase:
            return []
        try:
            return (
                db.session.query(Principle)
                .filter(Principle.adm_phase == phase)
                .order_by(Principle.name)
                .all()
            )
        except Exception as exc:
            logger.warning("get_principles_by_adm_phase(%s): query failed: %s", phase, exc)
            return []

    def get_principles_by_phase(self, adm_phase: str) -> List[Dict]:
        """Return list of dicts for all Principles matching *adm_phase*.

        Queries Principle.adm_phase == adm_phase and returns all fields
        including enforcement_status.

        Returns an empty list on error; never raises.
        """
        if not adm_phase:
            return []
        try:
            rows = (
                db.session.query(Principle)
                .filter_by(adm_phase=adm_phase)
                .all()
            )
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "statement": p.statement,
                    "rationale": p.rationale,
                    "implications": p.implications,
                    "category": p.category,
                    "enforcement_level": p.enforcement_level,
                    "enforcement_status": p.enforcement_status,
                    "adm_phase": p.adm_phase,
                    "status": getattr(p, "status", None),
                }
                for p in rows
            ]
        except Exception as exc:
            logger.warning("get_principles_by_phase(%s): query failed: %s", adm_phase, exc)
            return []

    def get_active_principles(self) -> List[Principle]:
        """Return principles with status='approved' (active / in-force)."""
        try:
            return (
                db.session.query(Principle)
                .filter(Principle.status == "approved")
                .order_by(Principle.category, Principle.name)
                .all()
            )
        except Exception as exc:
            logger.warning("get_active_principles: query failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Compliance checking
    # ------------------------------------------------------------------

    def check_application_compliance(self, app_id: int) -> Dict:
        """Check whether an Application satisfies all mandatory principles.

        Algorithm (ORM-only, no raw SQL):
        1. Load the Application row; return ``{"compliant": True}`` stub
           if not found (no data to check against).
        2. Load all Principle rows with enforcement_level='mandatory'.
        3. For each mandatory principle that references an archimate_element
           (via archimate_element_id), verify the Application row also
           references the *same* element.  If the principle has no element
           link, it is considered satisfied (structural check only).
        4. Violations include the principle's DB id and name — no
           fabricated strings.

        Returns:
            {
                "app_id": <int>,
                "compliant": <bool>,
                "violated_principles": [
                    {"principle_id": <int>, "principle_name": <str>,
                     "violation_reason": <str>}
                ]
            }
        """
        from app.models.application import Application

        result: Dict = {
            "app_id": app_id,
            "compliant": True,
            "violated_principles": [],
        }

        try:
            application = db.session.get(Application, app_id)
            if application is None:
                logger.debug("check_application_compliance: app_id=%s not found", app_id)
                return result

            mandatory_principles = (
                db.session.query(Principle)
                .filter(Principle.enforcement_level == "mandatory")
                .filter(Principle.status == "approved")
                .all()
            )

            for principle in mandatory_principles:
                if principle.archimate_element_id is None:
                    # No structural constraint to enforce
                    continue
                if application.archimate_element_id != principle.archimate_element_id:
                    result["violated_principles"].append(
                        {
                            "principle_id": principle.id,
                            "principle_name": principle.name,
                            "violation_reason": (
                                f"Application archimate_element_id="
                                f"{application.archimate_element_id!r} does not match "
                                f"required element_id={principle.archimate_element_id!r} "
                                f"from principle '{principle.name}' (id={principle.id})"
                            ),
                        }
                    )

            result["compliant"] = len(result["violated_principles"]) == 0
        except Exception as exc:
            logger.warning("check_application_compliance(app_id=%s): error: %s", app_id, exc)
            result["error"] = str(exc)

        return result
