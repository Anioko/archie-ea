"""
CA-001: CapabilityArchiMateBindingService

Name-matches BusinessCapability records to ArchiMate 3.2 Capability elements
and writes the FK `archimate_element_id` on each matched capability.

Exposes coverage metrics via `get_coverage_summary()`.
"""
import logging

logger = logging.getLogger(__name__)


class CapabilityArchiMateBindingService:
    """
    Binds BusinessCapability rows to ArchiMate elements by name matching.

    ArchiMate 3.2 Capability (motivation layer) maps naturally to TOGAF
    capability catalogue entries.  This service performs normalised-name
    matching and writes the FK so the rest of the platform can traverse
    Capability → ArchiMate element → viewpoint.
    """

    def name_match(self, architecture_id: int = None, dry_run: bool = False) -> dict:
        """
        Scan BusinessCapability rows where archimate_element_id IS NULL.
        For each, look for an ArchiMate element of type 'Capability' with
        a normalised matching name.  Write the FK unless dry_run=True.

        Args:
            architecture_id: optional filter — only match elements from
                this architecture.  None = search across all architectures.
            dry_run: if True, return counts/matches without writing to DB.

        Returns:
            {matched: int, unmatched: int, skipped: int, dry_run: bool}
        """
        from app import db
        from app.models.business_capabilities import BusinessCapability
        from app.models.archimate_core import ArchiMateElement

        q = BusinessCapability.query.filter(
            BusinessCapability.archimate_element_id.is_(None)
        )
        capabilities = q.all()

        archimate_q = ArchiMateElement.query.filter_by(type="Capability")
        if architecture_id is not None:
            archimate_q = archimate_q.filter_by(architecture_id=int(architecture_id))
        archimate_caps = archimate_q.all()

        # Build lookup: normalised name → element id
        element_lookup = {
            self._normalise(e.name): e.id
            for e in archimate_caps
            if e.name
        }

        matched = 0
        unmatched = 0
        for cap in capabilities:
            key = self._normalise(cap.name)
            elem_id = element_lookup.get(key)
            if elem_id is not None:
                if not dry_run:
                    cap.archimate_element_id = elem_id
                matched += 1
            else:
                unmatched += 1

        if not dry_run and matched > 0:
            try:
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.error("CA-001 name_match commit failed: %s", exc)
                raise

        logger.info(
            "CA-001 name_match: matched=%d unmatched=%d dry_run=%s",
            matched, unmatched, dry_run,
        )
        return {"matched": matched, "unmatched": unmatched, "skipped": 0, "dry_run": dry_run}

    def get_coverage_summary(self) -> dict:
        """
        Return capability ↔ ArchiMate element binding coverage statistics.

        Returns:
            {
              total_capabilities: int,
              matched: int,
              unmatched: int,
              coverage_pct: float,   # 0.0–100.0
            }
        """
        from app.models.business_capabilities import BusinessCapability

        total = BusinessCapability.query.count()
        matched = BusinessCapability.query.filter(
            BusinessCapability.archimate_element_id.isnot(None)
        ).count()
        unmatched = total - matched
        coverage_pct = round((matched / total * 100), 1) if total > 0 else 0.0

        return {
            "total_capabilities": total,
            "matched": matched,
            "unmatched": unmatched,
            "coverage_pct": coverage_pct,
        }

    @staticmethod
    def _normalise(name: str) -> str:
        """Lower-case, strip whitespace, remove common noise words."""
        if not name:
            return ""
        return " ".join(
            w for w in name.lower().strip().split()
            if w not in ("the", "a", "an", "of", "and", "&")
        )
