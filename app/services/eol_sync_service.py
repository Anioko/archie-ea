"""
EOL Sync Service

Fetches end-of-life dates from https://endoflife.date for vendor product families
and writes them to VendorProductFamily.end_of_life_date and last_update_date.

Only writes to DB if the API returned valid data — never fabricates values.
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests

from app import db
from app.models.vendor.vendor_product import VendorProductFamily

logger = logging.getLogger(__name__)

EOL_API_BASE = "https://endoflife.date/api"
REQUEST_TIMEOUT = 10

# Known aliases: canonical product name fragment → endoflife.date slug
_SLUG_ALIASES: dict[str, str] = {
    "windows 10": "windows-10",
    "windows 11": "windows-11",
    "windows server 2019": "windows-server-2019",
    "windows server 2022": "windows-server-2022",
    "oracle database": "oracle-database",
    "oracle db": "oracle-database",
    "java se": "java",
    "java": "java",
    "rhel": "rhel",
    "red hat enterprise linux": "rhel",
    "ubuntu": "ubuntu",
    "debian": "debian",
    "centos": "centos",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mongodb": "mongodb",
    "redis": "redis",
    "elasticsearch": "elasticsearch",
    "nginx": "nginx",
    "apache http server": "apache",
    "apache": "apache",
    "tomcat": "tomcat",
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "python": "python",
    "django": "django",
    "ruby on rails": "ruby-on-rails",
    "rails": "ruby-on-rails",
    "ruby": "ruby",
    "php": "php",
    "golang": "go",
    "go": "go",
    "dotnet": "dotnet",
    ".net": "dotnet",
    "spring framework": "spring-framework",
    "spring boot": "spring-boot",
    "angular": "angular",
    "react": "react",
    "vue.js": "vue",
    "vue": "vue",
    "drupal": "drupal",
    "wordpress": "wordpress",
    "magento": "magento",
    "sap hana": "sap-hana",
    "hana": "sap-hana",
    "sharepoint": "sharepoint",
    "exchange server": "exchange-server",
    "sql server": "mssqlserver",
    "microsoft sql server": "mssqlserver",
    "iis": "iis",
    "internet information services": "iis",
    "amazon linux": "amazon-linux",
    "amazon linux 2": "amazon-linux",
    "android": "android",
    "ios": "ios",
    "macos": "macos",
    "vmware esxi": "esxi",
    "esxi": "esxi",
    "jenkins": "jenkins",
    "gitlab": "gitlab",
    "kubernetes": "kubernetes",
    "istio": "istio",
    "graalvm": "graalvm",
    "kotlin": "kotlin",
    "swift": "swift",
    "terraform": "terraform",
}


def _name_to_slug(name: str) -> str:
    """Convert a product family name to an endoflife.date API slug."""
    lower = name.strip().lower()

    # Check exact alias matches first
    if lower in _SLUG_ALIASES:
        return _SLUG_ALIASES[lower]

    # Check partial matches (e.g. "SAP HANA 2.0" → matches "sap hana")
    for alias, slug in _SLUG_ALIASES.items():
        if alias in lower:
            return slug

    # Generic conversion: lowercase, replace spaces/special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    return slug


def _fetch_eol_data(slug: str) -> Optional[list]:
    """Fetch EOL data from endoflife.date API. Returns list of release cycles or None."""
    url = f"{EOL_API_BASE}/{slug}.json"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data
        return None
    except requests.RequestException as exc:
        logger.warning("EOL API request failed for slug '%s': %s", slug, exc)
        return None
    except ValueError as exc:
        logger.warning("EOL API returned invalid JSON for slug '%s': %s", slug, exc)
        return None


def _latest_eol_date(cycles: list) -> Optional[datetime]:
    """
    Extract the latest (most recent) EOL date from a list of release cycles.
    Each cycle may have an 'eol' field that is a date string or boolean.
    Returns the latest date as a datetime, or None if none found.
    """
    latest: Optional[datetime] = None
    for cycle in cycles:
        eol = cycle.get("eol")
        if not eol or isinstance(eol, bool):
            continue
        try:
            dt = datetime.strptime(str(eol), "%Y-%m-%d")
            if latest is None or dt > latest:
                latest = dt
        except ValueError:
            continue
    return latest


def sync_product_eol(product_family_name: str) -> dict:
    """
    Sync end-of-life date for a single product family by name.

    Returns a status dict:
      {"status": "updated"|"skipped"|"not_found"|"no_eol_data"|"error",
       "product": name, "eol_date": iso_string_or_none, "slug": slug}
    """
    slug = _name_to_slug(product_family_name)
    result = {"product": product_family_name, "slug": slug, "eol_date": None}

    cycles = _fetch_eol_data(slug)
    if cycles is None:
        result["status"] = "not_found"
        return result

    eol_date = _latest_eol_date(cycles)
    if eol_date is None:
        result["status"] = "no_eol_data"
        return result

    result["eol_date"] = eol_date.isoformat()

    try:
        families = VendorProductFamily.query.filter(
            VendorProductFamily.family_name.ilike(f"%{product_family_name}%")
        ).all()

        if not families:
            result["status"] = "skipped"
            result["note"] = "No matching VendorProductFamily rows"
            return result

        now = datetime.utcnow()
        for family in families:
            family.end_of_life_date = eol_date
            family.last_update_date = now

        db.session.commit()
        result["status"] = "updated"
        result["rows_updated"] = len(families)
    except Exception as exc:
        db.session.rollback()
        logger.error("DB write failed for product '%s': %s", product_family_name, exc)
        result["status"] = "error"
        result["error"] = str(exc)

    return result


def sync_all(limit: int = 50) -> dict:
    """
    Sync EOL dates for up to `limit` VendorProductFamily records.

    Prioritises families that have never been updated (last_update_date is null),
    then oldest-updated first.

    Returns a summary dict with per-product results.
    """
    families = (
        VendorProductFamily.query.order_by(
            VendorProductFamily.last_update_date.asc().nullsfirst()
        )
        .limit(limit)
        .all()
    )

    summary = {
        "total": len(families),
        "updated": 0,
        "skipped": 0,
        "not_found": 0,
        "errors": 0,
        "results": [],
    }

    seen_slugs: set[str] = set()

    for family in families:
        slug = _name_to_slug(family.family_name)

        # Deduplicate API calls for the same slug within one batch
        if slug in seen_slugs:
            result = {
                "product": family.family_name,
                "slug": slug,
                "status": "skipped",
                "note": "Duplicate slug in batch",
            }
        else:
            seen_slugs.add(slug)
            result = sync_product_eol(family.family_name)

        status = result.get("status", "error")
        if status == "updated":
            summary["updated"] += 1
        elif status in ("skipped", "not_found", "no_eol_data"):
            summary["skipped"] += 1
        else:
            summary["errors"] += 1

        summary["results"].append(result)

    return summary
