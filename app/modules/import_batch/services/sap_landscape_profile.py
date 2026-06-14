"""SAP landscape export profile for the batch import pipeline (PROG-002).

Detects rows exported from SAP landscape tooling (Solution Manager LMDB
system lists, SAP Readiness Check system sheets, transport landscape
spreadsheets) and normalises them into the shape the existing batch import
pipeline expects (name / description / type / vendor keys). The full original
row is preserved by the pipeline in BatchImportApplication.source_data.

Detection is column-based: a file is treated as an SAP landscape export when
it carries a system-id column (SID / System ID) together with at least one
SAP-ish companion column (product, version, installation number, host,
landscape role). Generic application CSVs are untouched.

No new pipeline, no new tables — this is a pre-normalisation step in front of
BatchImportService._create_batches_and_applications.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Column-name variants (matched case-insensitively, stripped)
SID_COLUMNS = ["sid", "system id", "system_id", "systemid", "system"]
PRODUCT_COLUMNS = ["product", "product version", "product_version", "software component",
                   "component", "sap product", "product name"]
DESCRIPTION_COLUMNS = ["description", "system description", "system name", "name"]
ENVIRONMENT_COLUMNS = ["environment", "landscape role", "role", "system role", "usage",
                       "system type", "tier"]
STATUS_COLUMNS = ["status", "system status", "lifecycle", "lifecycle status"]
HOST_COLUMNS = ["host", "hostname", "server", "message server", "app server"]
INSTALLATION_COLUMNS = ["installation number", "installation_number", "instno", "inst no"]
VERSION_COLUMNS = ["release", "version", "sp level", "support package", "kernel release"]

# At least one companion column besides the SID must look SAP-ish
COMPANION_COLUMNS = (PRODUCT_COLUMNS + ENVIRONMENT_COLUMNS + HOST_COLUMNS
                     + INSTALLATION_COLUMNS + VERSION_COLUMNS)

# SAP landscape role/status vocabulary -> platform lifecycle_status
# (normalised values per DATA_REALITY.md: operational/development/testing/
#  planning/deprecated/retired)
_LIFECYCLE_MAP = {
    "production": "operational",
    "prod": "operational",
    "prd": "operational",
    "live": "operational",
    "active": "operational",
    "quality": "testing",
    "quality assurance": "testing",
    "qas": "testing",
    "qa": "testing",
    "test": "testing",
    "consolidation": "testing",
    "development": "development",
    "dev": "development",
    "sandbox": "development",
    "sbx": "development",
    "training": "development",
    "demo": "development",
    "planned": "planning",
    "to be installed": "planning",
    "sunset": "deprecated",
    "to be decommissioned": "deprecated",
    "decommission planned": "deprecated",
    "decommissioned": "retired",
    "retired": "retired",
    "deleted": "retired",
    "inactive": "retired",
}


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _find_column(columns: List[str], variants: List[str]) -> Optional[str]:
    by_norm = {_norm(c): c for c in columns}
    for v in variants:
        if v in by_norm:
            return by_norm[v]
    return None


class SapLandscapeProfile:
    """Detect + normalise SAP landscape export rows."""

    @staticmethod
    def detect(columns: List[str]) -> bool:
        sid_col = _find_column(columns, SID_COLUMNS)
        if not sid_col:
            return False
        companion = _find_column(columns, COMPANION_COLUMNS)
        return companion is not None

    @classmethod
    def maybe_normalize(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return rows normalised for the pipeline if they are an SAP landscape
        export; otherwise return them unchanged."""
        if not rows:
            return rows
        columns = list(rows[0].keys())
        if not cls.detect(columns):
            return rows

        sid_col = _find_column(columns, SID_COLUMNS)
        product_col = _find_column(columns, PRODUCT_COLUMNS)
        desc_col = _find_column(columns, DESCRIPTION_COLUMNS)
        env_col = _find_column(columns, ENVIRONMENT_COLUMNS)
        status_col = _find_column(columns, STATUS_COLUMNS)
        host_col = _find_column(columns, HOST_COLUMNS)
        version_col = _find_column(columns, VERSION_COLUMNS)

        logger.info(
            "SAP landscape export detected (sid=%r product=%r env=%r) — normalising %d rows",
            sid_col, product_col, env_col, len(rows),
        )

        out = []
        for row in rows:
            sid = str(row.get(sid_col) or "").strip().upper()
            if not sid:
                continue  # landscape rows without a SID are separators/footers
            product = str(row.get(product_col) or "").strip() if product_col else ""
            desc = str(row.get(desc_col) or "").strip() if desc_col else ""
            env = str(row.get(env_col) or "").strip() if env_col else ""
            status_raw = str(row.get(status_col) or "").strip() if status_col else ""
            host = str(row.get(host_col) or "").strip() if host_col else ""
            version = str(row.get(version_col) or "").strip() if version_col else ""

            # Lifecycle precedence: a decommission-signal in Status (Sunset,
            # To Be Decommissioned, ...) always wins; otherwise the landscape
            # role sets the tier (QA -> testing, Development -> development) —
            # SAP "Status: Active" only means the system is running, so it
            # must not mask the role.
            status_mapped = _LIFECYCLE_MAP.get(_norm(status_raw))
            env_mapped = _LIFECYCLE_MAP.get(_norm(env))
            if status_mapped and status_mapped != "operational":
                lifecycle = status_mapped
            else:
                lifecycle = env_mapped or status_mapped

            display_name = f"{sid} — {desc}" if desc and desc.upper() != sid else sid
            description_parts = [p for p in (product, version and f"Release {version}",
                                             env and f"Environment: {env}",
                                             host and f"Host: {host}") if p]

            normalised = dict(row)  # preserve every original column for source_data
            normalised["name"] = display_name
            normalised["description"] = " · ".join(description_parts) or desc
            normalised["type"] = "SAP System"
            normalised["vendor"] = "SAP"
            if lifecycle:
                normalised["lifecycle_status"] = lifecycle
            if env:
                normalised["environment"] = env
            normalised["_sap_landscape"] = True
            out.append(normalised)

        return out
