"""MP-002: Migration Wave Sequencing service.

# mass-deletion-ok
Groups gaps from a gap register into severity-ordered MigrationWave records.
critical -> Wave 1, high -> Wave 2, medium -> Wave 3, low -> Wave 4.
All DB access is via ORM -- no raw SQL.
"""
import logging
from typing import Dict, List

from app import db
from app.models.implementation_migration import MigrationWave

logger = logging.getLogger(__name__)

# Severity -> wave number mapping (separate wave per severity)
_SEVERITY_WAVE: Dict[str, int] = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}

_WAVE_NAMES: Dict[int, str] = {
    1: "Wave 1 - Critical",
    2: "Wave 2 - High",
    3: "Wave 3 - Medium",
    4: "Wave 4 - Low",
}


class MigrationWaveSequencingService:
    """Sequences a gap register into prioritised MigrationWave ORM rows."""

    def sequence_waves(self, gap_register: list) -> list:
        """Group gaps by severity and create/update MigrationWave rows.

        Args:
            gap_register: List of gap dicts, each with at minimum a ``severity``
                key (critical | high | medium | low).

        Returns:
            List of dicts with keys ``wave_number``, ``wave_name``, ``gap_count``,
            ``estimated_apps``, ``status``. Returns [] if *gap_register* is empty.
        """
        if not gap_register:
            return []

        grouped: Dict[int, List[dict]] = {}
        for gap in gap_register:
            severity = (gap.get("severity") or "low").lower()
            wave_num = _SEVERITY_WAVE.get(severity, 4)
            grouped.setdefault(wave_num, []).append(gap)

        # Batch-load all existing MigrationWave rows to avoid N+1 queries
        existing_waves: Dict[int, MigrationWave] = {
            w.wave_number: w for w in MigrationWave.query.all()
        }

        results = []
        for wave_num in sorted(grouped.keys()):
            gaps_in_wave = grouped[wave_num]
            wave_name = _WAVE_NAMES.get(wave_num, f"Wave {wave_num}")

            wave = existing_waves.get(wave_num)
            if wave is None:
                wave = MigrationWave(
                    wave_number=wave_num,
                    name=wave_name,
                    status="planned",
                )
                db.session.add(wave)
            else:
                wave.name = wave_name

            estimated_apps = len(
                {g["affected_app_id"] for g in gaps_in_wave if g.get("affected_app_id")}
            )

            results.append(
                {
                    "wave_number": wave_num,
                    "wave_name": wave_name,
                    "gap_count": len(gaps_in_wave),
                    "estimated_apps": estimated_apps,
                    "status": wave.status,
                }
            )

        db.session.commit()
        return results

    def get_wave_summary(self) -> dict:
        """Return a summary of all MigrationWave rows.

        Returns:
            Dict with keys:
            - ``total_waves``: int
            - ``by_status``: {planned, in_progress, complete} counts
            - ``waves``: list of {id, wave_number, wave_name, status}
        """
        waves = MigrationWave.query.all()
        by_status: Dict[str, int] = {"planned": 0, "in_progress": 0, "complete": 0}
        wave_list = []
        for wave in waves:
            status_key = "complete" if wave.status == "completed" else wave.status
            if status_key in by_status:
                by_status[status_key] += 1
            wave_list.append(
                {
                    "id": wave.id,
                    "wave_number": wave.wave_number,
                    "wave_name": wave.name,
                    "status": wave.status,
                }
            )
        return {
            "total_waves": len(waves),
            "by_status": by_status,
            "waves": wave_list,
        }
