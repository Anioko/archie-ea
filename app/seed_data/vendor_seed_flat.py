"""
Flat vendor seed data for idempotent two-pass seeding.

This minimal flat set includes a few vendors with unique `code` values and
optional parent relationships (not typical for vendors but kept for parity).
Consumers should upsert VendorOrganization by `code` or `name`.
"""

from typing import Any, Dict, List


def get_flat_vendors() -> List[Dict[str, Any]]:
    return [
        {
            "code": "VEND-SF",
            "name": "Salesforce",
            "website": "https://www.salesforce.com",
            "description": "CRM and platform provider",
            "headquarters": "San Francisco, CA",
            "year_founded": 1999,
        },
        {
            "code": "VEND-SAP",
            "name": "SAP",
            "website": "https://www.sap.com",
            "description": "Enterprise ERP and business applications",
            "headquarters": "Walldorf, Germany",
            "year_founded": 1972,
        },
        {
            "code": "VEND-ORCL",
            "name": "Oracle",
            "website": "https://www.oracle.com",
            "description": "Database and enterprise software",
            "headquarters": "Austin, TX",
            "year_founded": 1977,
        },
    ]
