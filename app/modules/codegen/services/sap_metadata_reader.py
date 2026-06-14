"""SAP metadata reader — connects via RFC and reads DD02L/DD03L/DD04L/TSTC/PFCG/TADIR.

pyrfc (and the underlying SAP NW RFC SDK) is an optional dependency.  The module
degrades gracefully when the native library is absent: every public method raises
``SapRfcUnavailableError`` unless the instance was constructed with ``mock=True``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional RFC import
# ---------------------------------------------------------------------------

try:
    import pyrfc  # type: ignore[import-untyped]

    RFC_AVAILABLE = True
except ImportError:
    pyrfc = None  # type: ignore[assignment]
    RFC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SapRfcUnavailableError(RuntimeError):
    """Raised when pyrfc / SAP NW RFC SDK is not installed."""


class SapConnectionError(RuntimeError):
    """Raised when the RFC connection to the SAP system cannot be established."""


class SapReadError(RuntimeError):
    """Raised when an RFC call to read SAP metadata fails."""


# ---------------------------------------------------------------------------
# Module-prefix inference map
# Tuple of (prefix, module) ordered longest-first so more-specific prefixes win.
# ---------------------------------------------------------------------------

_PREFIX_MODULE_MAP: list[tuple[str, str]] = sorted(
    [
        # Materials Management
        ("MA", "MM"),
        ("MB", "MM"),
        ("MC", "MM"),
        ("ME", "MM"),
        ("MK", "MM"),
        ("ML", "MM"),
        ("MR", "MM"),
        ("MT", "MM"),
        ("MV", "MM"),
        ("MW", "MM"),
        # Sales & Distribution
        ("KN", "SD"),
        ("KO", "SD"),
        ("KV", "SD"),
        ("SD", "SD"),
        ("VB", "SD"),
        ("VK", "SD"),
        ("VL", "SD"),
        ("VS", "SD"),
        # Finance / Controlling
        ("BS", "FI"),
        ("FB", "FI"),
        ("GL", "FI"),
        ("PA", "FI"),
        ("PK", "FI"),
        ("BKPF", "FI"),
        ("BSEG", "FI"),
        # Human Resources
        ("HR", "HR"),
        ("PT", "HR"),
        ("PY", "HR"),
        # Project System / Controlling
        ("CJ", "PS"),
        ("CN", "PS"),
        ("CS", "PS"),
        ("CR", "PS"),
        ("KA", "CO"),
        ("KP", "CO"),
    ],
    key=lambda t: len(t[0]),
    reverse=True,  # longest prefix checked first
)


def _infer_module(table_name: str) -> str:
    """Return the SAP module for *table_name* based on well-known prefix patterns."""
    upper = table_name.upper()
    for prefix, module in _PREFIX_MODULE_MAP:
        if upper.startswith(prefix):
            return module
    return "BASIS"


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_DATA: dict[str, Any] = {
    "tables": [
        # --- MM ---
        {
            "table_name": "MARA",
            "description": "General Material Data",
            "table_type": "T",
            "package": "MM",
            "field_count": 8,
        },
        {
            "table_name": "MARC",
            "description": "Plant Data for Material",
            "table_type": "T",
            "package": "MM",
            "field_count": 7,
        },
        {
            "table_name": "MAKT",
            "description": "Material Descriptions",
            "table_type": "T",
            "package": "MM",
            "field_count": 4,
        },
        {
            "table_name": "MBEW",
            "description": "Material Valuation",
            "table_type": "T",
            "package": "MM",
            "field_count": 6,
        },
        {
            "table_name": "MKPF",
            "description": "Header: Material Document",
            "table_type": "T",
            "package": "MM",
            "field_count": 5,
        },
        {
            "table_name": "MSEG",
            "description": "Document Segment: Material",
            "table_type": "T",
            "package": "MM",
            "field_count": 8,
        },
        {
            "table_name": "EBAN",
            "description": "Purchase Requisition",
            "table_type": "T",
            "package": "MM",
            "field_count": 7,
        },
        {
            "table_name": "EKKO",
            "description": "Purchasing Document Header",
            "table_type": "T",
            "package": "MM",
            "field_count": 6,
        },
        {
            "table_name": "EKPO",
            "description": "Purchasing Document Item",
            "table_type": "T",
            "package": "MM",
            "field_count": 7,
        },
        {
            "table_name": "EKET",
            "description": "Scheduling Agreement Schedule Lines",
            "table_type": "T",
            "package": "MM",
            "field_count": 5,
        },
        # --- SD ---
        {
            "table_name": "VBAK",
            "description": "Sales Document: Header Data",
            "table_type": "T",
            "package": "SD",
            "field_count": 7,
        },
        {
            "table_name": "VBAP",
            "description": "Sales Document: Item Data",
            "table_type": "T",
            "package": "SD",
            "field_count": 8,
        },
        {
            "table_name": "VBEP",
            "description": "Sales Document: Schedule Line Data",
            "table_type": "T",
            "package": "SD",
            "field_count": 5,
        },
        # --- FI ---
        {
            "table_name": "BKPF",
            "description": "Accounting Document Header",
            "table_type": "T",
            "package": "FI",
            "field_count": 6,
        },
        {
            "table_name": "BSEG",
            "description": "Accounting Document Segment",
            "table_type": "T",
            "package": "FI",
            "field_count": 8,
        },
    ],
    "fields": {
        "MARA": [
            {"field_name": "MANDT", "description": "Client",             "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MATNR", "description": "Material Number",    "data_type": "CHAR", "length": 18, "is_key": True},
            {"field_name": "ERSDA", "description": "Created On",         "data_type": "DATS", "length": 8,  "is_key": False},
            {"field_name": "ERNAM", "description": "Created By",         "data_type": "CHAR", "length": 12, "is_key": False},
            {"field_name": "LAEDA", "description": "Last Changed On",    "data_type": "DATS", "length": 8,  "is_key": False},
            {"field_name": "MTART", "description": "Material Type",      "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "MBRSH", "description": "Industry Sector",    "data_type": "CHAR", "length": 1,  "is_key": False},
            {"field_name": "MEINS", "description": "Base Unit of Measure","data_type": "UNIT", "length": 3, "is_key": False},
        ],
        "MARC": [
            {"field_name": "MANDT", "description": "Client",             "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MATNR", "description": "Material Number",    "data_type": "CHAR", "length": 18, "is_key": True},
            {"field_name": "WERKS", "description": "Plant",              "data_type": "CHAR", "length": 4,  "is_key": True},
            {"field_name": "PSTAT", "description": "Maintenance Status", "data_type": "CHAR", "length": 15, "is_key": False},
            {"field_name": "LVORM", "description": "Flag: Delete",       "data_type": "CHAR", "length": 1,  "is_key": False},
            {"field_name": "EKGRP", "description": "Purchasing Group",   "data_type": "CHAR", "length": 3,  "is_key": False},
            {"field_name": "DISGR", "description": "MRP Group",          "data_type": "CHAR", "length": 4,  "is_key": False},
        ],
        "MAKT": [
            {"field_name": "MANDT", "description": "Client",             "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MATNR", "description": "Material Number",    "data_type": "CHAR", "length": 18, "is_key": True},
            {"field_name": "SPRAS", "description": "Language Key",       "data_type": "LANG", "length": 1,  "is_key": True},
            {"field_name": "MAKTX", "description": "Material Description","data_type": "CHAR", "length": 40, "is_key": False},
        ],
        "MBEW": [
            {"field_name": "MANDT", "description": "Client",             "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MATNR", "description": "Material Number",    "data_type": "CHAR", "length": 18, "is_key": True},
            {"field_name": "BWKEY", "description": "Valuation Area",     "data_type": "CHAR", "length": 4,  "is_key": True},
            {"field_name": "BWTAR", "description": "Valuation Type",     "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "STPRS", "description": "Standard Price",     "data_type": "CURR", "length": 13, "is_key": False},
            {"field_name": "VERPR", "description": "Moving Average Price","data_type": "CURR", "length": 13, "is_key": False},
        ],
        "MKPF": [
            {"field_name": "MANDT",  "description": "Client",            "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MBLNR",  "description": "Material Document", "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "MJAHR",  "description": "Material Doc. Year","data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "BLDAT",  "description": "Document Date",     "data_type": "DATS", "length": 8,  "is_key": False},
            {"field_name": "BUDAT",  "description": "Posting Date",      "data_type": "DATS", "length": 8,  "is_key": False},
        ],
        "MSEG": [
            {"field_name": "MANDT",  "description": "Client",            "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "MBLNR",  "description": "Material Document", "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "MJAHR",  "description": "Material Doc. Year","data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "ZEILE",  "description": "Item in Doc.",      "data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "MATNR",  "description": "Material Number",   "data_type": "CHAR", "length": 18, "is_key": False},
            {"field_name": "WERKS",  "description": "Plant",             "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "MENGE",  "description": "Quantity",          "data_type": "QUAN", "length": 13, "is_key": False},
            {"field_name": "BWART",  "description": "Movement Type",     "data_type": "CHAR", "length": 3,  "is_key": False},
        ],
        "EBAN": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "BANFN",  "description": "Purchase Requisition No.",  "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "BNFPO",  "description": "Item Number",               "data_type": "NUMC", "length": 5,  "is_key": True},
            {"field_name": "MATNR",  "description": "Material Number",           "data_type": "CHAR", "length": 18, "is_key": False},
            {"field_name": "MENGE",  "description": "Purchase Requisition Qty",  "data_type": "QUAN", "length": 13, "is_key": False},
            {"field_name": "EKGRP",  "description": "Purchasing Group",          "data_type": "CHAR", "length": 3,  "is_key": False},
            {"field_name": "AFNAM",  "description": "Requisitioner",             "data_type": "CHAR", "length": 12, "is_key": False},
        ],
        "EKKO": [
            {"field_name": "MANDT",  "description": "Client",                "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "EBELN",  "description": "Purchasing Document No.","data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "BUKRS",  "description": "Company Code",          "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "BSTYP",  "description": "Purchasing Doc. Category","data_type": "CHAR", "length": 1, "is_key": False},
            {"field_name": "BSART",  "description": "Purchasing Doc. Type",  "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "EKGRP",  "description": "Purchasing Group",      "data_type": "CHAR", "length": 3,  "is_key": False},
        ],
        "EKPO": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "EBELN",  "description": "Purchasing Document No.",   "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "EBELP",  "description": "Item Number",               "data_type": "NUMC", "length": 5,  "is_key": True},
            {"field_name": "MATNR",  "description": "Material Number",           "data_type": "CHAR", "length": 18, "is_key": False},
            {"field_name": "MENGE",  "description": "PO Quantity",               "data_type": "QUAN", "length": 13, "is_key": False},
            {"field_name": "NETPR",  "description": "Net Price",                 "data_type": "CURR", "length": 13, "is_key": False},
            {"field_name": "WERKS",  "description": "Plant",                     "data_type": "CHAR", "length": 4,  "is_key": False},
        ],
        "EKET": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "EBELN",  "description": "Purchasing Document No.",   "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "EBELP",  "description": "Item Number",               "data_type": "NUMC", "length": 5,  "is_key": True},
            {"field_name": "ETENR",  "description": "Delivery Schedule Line",    "data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "EINDT",  "description": "Delivery Date",             "data_type": "DATS", "length": 8,  "is_key": False},
        ],
        "VBAK": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "VBELN",  "description": "Sales Document",            "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "ERDAT",  "description": "Created On",                "data_type": "DATS", "length": 8,  "is_key": False},
            {"field_name": "AUART",  "description": "Sales Document Type",       "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "KUNNR",  "description": "Sold-to Party",             "data_type": "CHAR", "length": 10, "is_key": False},
            {"field_name": "VKORG",  "description": "Sales Organization",        "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "NETWR",  "description": "Net Value",                 "data_type": "CURR", "length": 15, "is_key": False},
        ],
        "VBAP": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "VBELN",  "description": "Sales Document",            "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "POSNR",  "description": "Item Number",               "data_type": "NUMC", "length": 6,  "is_key": True},
            {"field_name": "MATNR",  "description": "Material Number",           "data_type": "CHAR", "length": 18, "is_key": False},
            {"field_name": "KWMENG", "description": "Cumulative Order Qty",      "data_type": "QUAN", "length": 15, "is_key": False},
            {"field_name": "NETPR",  "description": "Net Price",                 "data_type": "CURR", "length": 15, "is_key": False},
            {"field_name": "WERKS",  "description": "Plant",                     "data_type": "CHAR", "length": 4,  "is_key": False},
            {"field_name": "PSTYV",  "description": "Sales Document Item Category","data_type": "CHAR", "length": 4, "is_key": False},
        ],
        "VBEP": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "VBELN",  "description": "Sales Document",            "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "POSNR",  "description": "Item Number",               "data_type": "NUMC", "length": 6,  "is_key": True},
            {"field_name": "ETENR",  "description": "Schedule Line Number",      "data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "EDATU",  "description": "Schedule Line Date",        "data_type": "DATS", "length": 8,  "is_key": False},
        ],
        "BKPF": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "BUKRS",  "description": "Company Code",              "data_type": "CHAR", "length": 4,  "is_key": True},
            {"field_name": "BELNR",  "description": "Accounting Document No.",   "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "GJAHR",  "description": "Fiscal Year",               "data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "BLDAT",  "description": "Document Date",             "data_type": "DATS", "length": 8,  "is_key": False},
            {"field_name": "BUDAT",  "description": "Posting Date",              "data_type": "DATS", "length": 8,  "is_key": False},
        ],
        "BSEG": [
            {"field_name": "MANDT",  "description": "Client",                    "data_type": "CLNT", "length": 3,  "is_key": True},
            {"field_name": "BUKRS",  "description": "Company Code",              "data_type": "CHAR", "length": 4,  "is_key": True},
            {"field_name": "BELNR",  "description": "Accounting Document No.",   "data_type": "CHAR", "length": 10, "is_key": True},
            {"field_name": "GJAHR",  "description": "Fiscal Year",               "data_type": "NUMC", "length": 4,  "is_key": True},
            {"field_name": "BUZEI",  "description": "Line Item Number",          "data_type": "NUMC", "length": 3,  "is_key": True},
            {"field_name": "HKONT",  "description": "General Ledger Account",    "data_type": "CHAR", "length": 10, "is_key": False},
            {"field_name": "DMBTR",  "description": "Amount in Local Currency",  "data_type": "CURR", "length": 13, "is_key": False},
            {"field_name": "KOSTL",  "description": "Cost Center",               "data_type": "CHAR", "length": 10, "is_key": False},
        ],
    },
    "transactions": [
        {"tcode": "MM01",  "description": "Create Material",                    "program": "SAPMM06E",  "module": "MM"},
        {"tcode": "MM02",  "description": "Change Material",                    "program": "SAPMM06E",  "module": "MM"},
        {"tcode": "MB51",  "description": "Material Doc. List",                 "program": "RM07DOCS",  "module": "MM"},
        {"tcode": "ME21N", "description": "Create Purchase Order",              "program": "SAPMM06E",  "module": "MM"},
        {"tcode": "ME23N", "description": "Display Purchase Order",             "program": "SAPMM06E",  "module": "MM"},
        {"tcode": "MR11",  "description": "GR/IR Account Maintenance",          "program": "RMSEINV0",  "module": "MM"},
        {"tcode": "VA01",  "description": "Create Sales Order",                 "program": "SAPMV45A",  "module": "SD"},
        {"tcode": "VA03",  "description": "Display Sales Order",                "program": "SAPMV45A",  "module": "SD"},
        {"tcode": "VL01N", "description": "Create Outbound Delivery",           "program": "SAPMV50A",  "module": "SD"},
        {"tcode": "FB01",  "description": "Post Document",                      "program": "SAPF040",   "module": "FI"},
        {"tcode": "F110",  "description": "Parameters for Automatic Payment",   "program": "SAPF110S",  "module": "FI"},
        {"tcode": "SE11",  "description": "ABAP Dictionary",                    "program": "SAPLSDIC",  "module": "BASIS"},
    ],
    "roles": [
        {
            "role_name": "Z_MM_BUYER",
            "description": "MM Buyer Role — procurement ordering and requisitions",
            "assigned_tcodes": ["MM01", "MM02", "ME21N", "ME23N"],
        },
        {
            "role_name": "Z_MM_WAREHOUSE",
            "description": "MM Warehouse Clerk — goods movements and inventory",
            "assigned_tcodes": ["MB51", "MR11"],
        },
        {
            "role_name": "Z_SD_SALES_REP",
            "description": "SD Sales Representative — order entry and delivery",
            "assigned_tcodes": ["VA01", "VA03", "VL01N"],
        },
        {
            "role_name": "Z_FI_AP_CLERK",
            "description": "FI Accounts Payable Clerk — invoice posting and payment runs",
            "assigned_tcodes": ["FB01", "F110"],
        },
    ],
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class SapMetadataReader:
    """Read SAP metadata via RFC (DD02L/DD03L/TSTC/PFCG/TADIR).

    Args:
        config: RFC connection parameters (ashost, sysnr, client, user, passwd, lang).
        mock:   When *True* the instance returns hardcoded sample data and never
                attempts an RFC connection.  Use this in tests or when no SAP system
                is available.

    Raises:
        SapRfcUnavailableError: On construction (non-mock) when pyrfc is absent.
        SapConnectionError: When the RFC connection cannot be established.
    """

    def __init__(self, config: dict, mock: bool = False) -> None:
        self._mock = mock
        self._config = config
        self._conn: Optional[Any] = None  # pyrfc.Connection instance

        if not mock:
            if not RFC_AVAILABLE:
                raise SapRfcUnavailableError(
                    "pyrfc is not installed.  Install it together with the SAP NW RFC SDK "
                    "and set LD_LIBRARY_PATH / SAPNWRFC_HOME as described in the pyrfc docs.  "
                    "Alternatively, construct SapMetadataReader with mock=True for testing."
                )
            self._connect()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        required = {"ashost", "sysnr", "client", "user", "passwd"}
        missing = required - set(self._config)
        if missing:
            raise SapConnectionError(
                f"RFC config is missing required keys: {', '.join(sorted(missing))}"
            )
        try:
            self._conn = pyrfc.Connection(
                ashost=self._config["ashost"],
                sysnr=self._config["sysnr"],
                client=self._config["client"],
                user=self._config["user"],
                passwd=self._config["passwd"],
                lang=self._config.get("lang", "EN"),
            )
            logger.info(
                "SAP RFC connection established to %s (client %s)",
                self._config["ashost"],
                self._config["client"],
            )
        except Exception as exc:
            raise SapConnectionError(
                f"Failed to connect to SAP system at {self._config.get('ashost')}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the RFC connection if open."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as exc:
                logger.debug("suppressed error in SapMetadataReader.close (app/modules/codegen/services/sap_metadata_reader.py): %s", exc)
            finally:
                self._conn = None
                logger.debug("SAP RFC connection closed.")

    def __enter__(self) -> "SapMetadataReader":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_rfc(self) -> None:
        """Raise if RFC is not available (non-mock instance)."""
        if not RFC_AVAILABLE:
            raise SapRfcUnavailableError(
                "pyrfc is not installed.  Cannot perform live RFC reads."
            )
        if self._conn is None:
            raise SapConnectionError("RFC connection is not open.")

    def _call(self, fm_name: str, **params: Any) -> dict:
        """Invoke an RFC function module and return its result dict."""
        try:
            return self._conn.call(fm_name, **params)
        except Exception as exc:
            raise SapReadError(
                f"RFC call to {fm_name} failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public read methods
    # ------------------------------------------------------------------

    def read_tables(
        self,
        package_filter: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        """Read the SAP table catalog from DD02L.

        Args:
            package_filter: Restrict results to tables belonging to this SAP package
                            (e.g. ``"MM"``).  ``None`` returns all packages.
            limit:          Maximum number of tables to return.

        Returns:
            List of dicts with keys: ``table_name``, ``description``, ``table_type``,
            ``package``, ``field_count``.
        """
        if self._mock:
            rows = []
            for r in _MOCK_DATA["tables"]:
                row = dict(r)
                # Normalise: expose "module" key so the mapper pipeline works
                # regardless of whether the caller uses "package" or "module".
                row.setdefault("module", row.get("package") or _infer_module(row["table_name"]))
                rows.append(row)
            if package_filter:
                rows = [r for r in rows if r["module"] == package_filter.upper()]
            return rows[:limit]

        self._require_rfc()

        # RFC_READ_TABLE against DD02L
        options = [{"TEXT": "TABCLASS NE 'INTTAB'"}]
        if package_filter:
            options.append({"TEXT": f"AND AS4LOCAL = 'A'"})

        result = self._call(
            "RFC_READ_TABLE",
            QUERY_TABLE="DD02L",
            DELIMITER="|",
            ROWCOUNT=limit,
            OPTIONS=options,
            FIELDS=[
                {"FIELDNAME": "TABNAME"},
                {"FIELDNAME": "DDTEXT"},
                {"FIELDNAME": "TABCLASS"},
                {"FIELDNAME": "DEVCLASS"},
            ],
        )

        tables: list[dict] = []
        for row in result.get("DATA", []):
            parts = [p.strip() for p in row["WA"].split("|")]
            if len(parts) < 4:
                continue
            table_name, description, table_type, package = (parts + [""] * 4)[:4]
            if package_filter and package.upper() != package_filter.upper():
                continue
            tables.append(
                {
                    "table_name": table_name,
                    "description": description,
                    "table_type": table_type,
                    "package": package or _infer_module(table_name),
                    "module": _infer_module(table_name),
                    "field_count": 0,  # populated on demand via read_table_fields
                }
            )
        return tables

    def read_table_fields(self, table_name: str) -> list[dict]:
        """Read field definitions for *table_name* from DD03L.

        Args:
            table_name: SAP transparent table name (e.g. ``"MARA"``).

        Returns:
            List of dicts with keys: ``field_name``, ``description``, ``data_type``,
            ``length``, ``is_key``.
        """
        upper_name = table_name.upper()

        if self._mock:
            return list(_MOCK_DATA["fields"].get(upper_name, []))

        self._require_rfc()

        result = self._call(
            "RFC_READ_TABLE",
            QUERY_TABLE="DD03L",
            DELIMITER="|",
            OPTIONS=[{"TEXT": f"TABNAME = '{upper_name}'"}],
            FIELDS=[
                {"FIELDNAME": "FIELDNAME"},
                {"FIELDNAME": "DDTEXT"},
                {"FIELDNAME": "INTTYPE"},
                {"FIELDNAME": "INTLEN"},
                {"FIELDNAME": "KEYFLAG"},
            ],
        )

        fields: list[dict] = []
        for row in result.get("DATA", []):
            parts = [p.strip() for p in row["WA"].split("|")]
            if len(parts) < 5:
                continue
            field_name, description, data_type, length_str, key_flag = (
                parts + [""] * 5
            )[:5]
            try:
                length = int(length_str)
            except ValueError:
                length = 0
            fields.append(
                {
                    "field_name": field_name,
                    "description": description,
                    "data_type": data_type,
                    "length": length,
                    "is_key": key_flag.strip() == "X",
                }
            )
        return fields

    def read_transactions(
        self,
        module_filter: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Read transaction codes from TSTC joined with descriptions from TSTCT.

        Args:
            module_filter: Only return transactions belonging to this module
                           (e.g. ``"MM"``).  Filtering is done by inferring module
                           from the tcode prefix (TADIR lookup on live systems).
            limit:         Maximum number of transactions to return.

        Returns:
            List of dicts with keys: ``tcode``, ``description``, ``program``, ``module``.
        """
        if self._mock:
            rows = list(_MOCK_DATA["transactions"])
            if module_filter:
                rows = [r for r in rows if r["module"] == module_filter.upper()]
            return rows[:limit]

        self._require_rfc()

        # Read TSTC for tcode → program mapping
        tstc_result = self._call(
            "RFC_READ_TABLE",
            QUERY_TABLE="TSTC",
            DELIMITER="|",
            ROWCOUNT=limit,
            FIELDS=[{"FIELDNAME": "TCODE"}, {"FIELDNAME": "PGMNA"}],
        )

        tcode_program: dict[str, str] = {}
        for row in tstc_result.get("DATA", []):
            parts = [p.strip() for p in row["WA"].split("|")]
            if len(parts) >= 2:
                tcode_program[parts[0]] = parts[1]

        # Read TSTCT for tcode → description mapping (EN language)
        tstct_result = self._call(
            "RFC_READ_TABLE",
            QUERY_TABLE="TSTCT",
            DELIMITER="|",
            OPTIONS=[{"TEXT": "SPRSL = 'EN'"}],
            FIELDS=[{"FIELDNAME": "TCODE"}, {"FIELDNAME": "TTEXT"}],
        )

        tcode_desc: dict[str, str] = {}
        for row in tstct_result.get("DATA", []):
            parts = [p.strip() for p in row["WA"].split("|")]
            if len(parts) >= 2:
                tcode_desc[parts[0]] = parts[1]

        transactions: list[dict] = []
        for tcode, program in tcode_program.items():
            module = _infer_module(tcode)
            if module_filter and module != module_filter.upper():
                continue
            transactions.append(
                {
                    "tcode": tcode,
                    "description": tcode_desc.get(tcode, ""),
                    "program": program,
                    "module": module,
                }
            )
        return transactions[:limit]

    def read_roles(self, limit: int = 50) -> list[dict]:
        """Read PFCG authorization roles and their assigned transaction codes.

        Args:
            limit: Maximum number of roles to return.

        Returns:
            List of dicts with keys: ``role_name``, ``description``,
            ``assigned_tcodes``.
        """
        if self._mock:
            return list(_MOCK_DATA["roles"])[:limit]

        self._require_rfc()

        # Read role headers from AGR_DEFINE
        roles_result = self._call(
            "RFC_READ_TABLE",
            QUERY_TABLE="AGR_DEFINE",
            DELIMITER="|",
            ROWCOUNT=limit,
            FIELDS=[{"FIELDNAME": "AGR_NAME"}, {"FIELDNAME": "TEXT"}],
        )

        roles: list[dict] = []
        for row in roles_result.get("DATA", []):
            parts = [p.strip() for p in row["WA"].split("|")]
            if not parts:
                continue
            role_name = parts[0]
            description = parts[1] if len(parts) > 1 else ""

            # Read assigned tcodes from AGR_TCODES
            tcodes_result = self._call(
                "RFC_READ_TABLE",
                QUERY_TABLE="AGR_TCODES",
                DELIMITER="|",
                OPTIONS=[{"TEXT": f"AGR_NAME = '{role_name}'"}],
                FIELDS=[{"FIELDNAME": "TCD"}],
            )
            assigned: list[str] = []
            for trow in tcodes_result.get("DATA", []):
                tcd = trow["WA"].strip()
                if tcd:
                    assigned.append(tcd)

            roles.append(
                {
                    "role_name": role_name,
                    "description": description,
                    "assigned_tcodes": assigned,
                }
            )
        return roles

    def read_module_summary(self) -> dict:
        """Return a summary of table and transaction counts per SAP module.

        Returns:
            Dict mapping module code to ``{"tables": N, "transactions": M}``.
            Example::

                {
                    "MM": {"tables": 10, "transactions": 6},
                    "SD": {"tables": 3,  "transactions": 3},
                    "FI": {"tables": 2,  "transactions": 2},
                }
        """
        summary: dict[str, dict[str, int]] = {}

        for table in self.read_tables(limit=10_000):
            mod = table.get("package") or _infer_module(table["table_name"])
            entry = summary.setdefault(mod, {"tables": 0, "transactions": 0})
            entry["tables"] += 1

        for tcode in self.read_transactions(limit=10_000):
            mod = tcode.get("module") or _infer_module(tcode["tcode"])
            entry = summary.setdefault(mod, {"tables": 0, "transactions": 0})
            entry["transactions"] += 1

        return summary
