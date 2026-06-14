"""
Vendor-Product Data Transformation

Transforms the provided vendor-product data into the existing vendor catalogue structure
with APQC process mappings and comprehensive vendor metadata.
"""

import json
from typing import Any, Dict, List

# Rich vendor dataset provided by user
RICH_VENDOR_DATA = [
    {
        "vendor_name": "SAP",
        "product_name": "SAP S/4HANA Finance",
        "domain": "ERP",
        "apqc_processes": [
            {"level2": "8.2 Manage Revenue", "level3": "8.2.1 Process customer billing"},
            {
                "level2": "8.3 Manage General Accounting and Reporting",
                "level3": "8.3.2 Perform general accounting",
            },
            {
                "level2": "8.4 Manage Accounts Payable and Expense Reimbursements",
                "level3": "8.4.1 Process accounts payable",
            },
        ],
        "capabilities": [
            "Financial Planning and Analysis",
            "Accounting and Financial Close",
            "Treasury and Risk Management",
            "Accounts Payable and Receivable",
            "Financial Operations",
            "Governance, Risk, and Compliance",
        ],
    },
    {
        "vendor_name": "Salesforce",
        "product_name": "Salesforce Sales Cloud",
        "domain": "CRM",
        "apqc_processes": [
            {"level2": "3.2 Generate Demand", "level3": "3.2.2 Generate and manage leads"},
            {"level2": "3.4 Manage Sales Orders", "level3": "3.4.1 Create and manage sales orders"},
        ],
        "capabilities": [
            "Opportunity Management",
            "Lead Management",
            "Sales Forecasting",
            "Pipeline Management",
            "Contact and Account Management",
            "Mobile Sales Productivity",
        ],
    },
    {
        "vendor_name": "Workday",
        "product_name": "Workday Human Capital Management",
        "domain": "HCM",
        "apqc_processes": [
            {
                "level2": "10.2 Recruit, Source, and Select Employees",
                "level3": "10.2.2 Recruit and source candidates",
            },
            {
                "level2": "10.3 Develop and Counsel Employees",
                "level3": "10.3.1 Manage employee performance",
            },
        ],
        "capabilities": [
            "Talent Management",
            "Employee Lifecycle Management",
            "Compensation and Benefits Admin",
            "Workforce Planning",
            "Recruiting and Onboarding",
            "Payroll Management",
        ],
    },
    {
        "vendor_name": "Oracle",
        "product_name": "Oracle Fusion Cloud SCM",
        "domain": "SCM",
        "apqc_processes": [
            {
                "level2": "4.1 Plan for and Align Supply Chain Resources",
                "level3": "4.1.2 Create and manage supply plans",
            },
            {
                "level2": "4.3 Schedule and Production Products",
                "level3": "4.3.2 Schedule production",
            },
        ],
        "capabilities": [
            "Inventory Management",
            "Manufacturing Execution",
            "Logistics and Order Management",
            "Procurement Automation",
            "Product Lifecycle Management",
            "Supply Chain Planning",
        ],
    },
    {
        "vendor_name": "IBM",
        "product_name": "IBM Maximo Application Suite",
        "domain": "EAM",
        "apqc_processes": [
            {
                "level2": "9.1 Manage Product/Service Assets",
                "level3": "9.1.2 Maintain and repair assets",
            },
            {
                "level2": "9.2 Manage Physical Assets",
                "level3": "9.2.2 Monitor and evaluate asset health",
            },
        ],
        "capabilities": [
            "Asset Lifecycle Management",
            "Work Order Management",
            "Predictive Maintenance",
            "Inventory and Spare Parts Control",
            "Mobile Asset Inspection",
            "Health, Safety and Environment (HSE)",
        ],
    },
]

# Product-to-APQC mapping based on existing patterns
PRODUCT_APQC_MAPPING = {
    "ERP Suite": [
        "1.1",
        "1.2",
        "2.1",
        "2.2",
        "3.1",
        "3.2",
        "4.1",
        "4.2",
        "5.1",
        "5.2",
        "6.1",
        "6.2",
        "7.1",
        "7.2",
        "8.1",
        "8.2",
        "9.1",
        "9.2",
        "10.1",
        "10.2",
        "11.1",
        "11.2",
        "12.1",
        "12.2",
        "13.1",
        "13.2",
    ],
    "Cloud Platform": [
        "8.1",
        "8.2",
        "8.3",
        "8.4",
        "8.5",
        "8.6",
        "8.7",
        "10.1",
        "10.2",
        "11.1",
        "11.2",
        "13.1",
        "13.2",
    ],
    "Analytics Tool": [
        "1.1",
        "1.2",
        "2.1",
        "2.2",
        "3.1",
        "3.2",
        "4.1",
        "4.2",
        "5.1",
        "5.2",
        "6.1",
        "6.2",
        "7.1",
        "7.2",
        "9.1",
        "9.2",
        "10.1",
        "10.2",
        "11.1",
        "11.2",
        "12.1",
        "12.2",
        "13.1",
        "13.2",
    ],
    "Manufacturing System": [
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "5.5",
        "6.1",
        "6.2",
        "6.3",
        "6.4",
        "6.5",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "13.1",
        "13.2",
    ],
    "IoT Platform": [
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "8.1",
        "8.2",
        "8.3",
        "8.4",
        "8.5",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "13.1",
        "13.2",
    ],
    "SCADA System": [
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "8.1",
        "8.2",
        "8.3",
        "8.4",
        "8.5",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "13.1",
        "13.2",
    ],
    "MES Software": [
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "8.1",
        "8.2",
        "8.3",
        "8.4",
        "8.5",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "13.1",
        "13.2",
    ],
    "CRM Module": [
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "2.1",
        "2.2",
        "2.3",
        "2.4",
        "2.5",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "5.5",
        "7.1",
        "7.2",
        "7.3",
        "7.4",
        "7.5",
        "13.1",
        "13.2",
    ],
    "Inventory Optimization": [
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "6.1",
        "6.2",
        "6.3",
        "6.4",
        "6.5",
        "10.1",
        "10.2",
        "10.3",
        "10.4",
        "10.5",
        "13.1",
        "13.2",
    ],
    "Demand Planning": [
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "2.1",
        "2.2",
        "2.3",
        "2.4",
        "2.5",
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "3.5",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.5",
        "6.1",
        "6.2",
        "6.3",
        "6.4",
        "6.5",
        "13.1",
        "13.2",
    ],
}

# Enhanced vendor metadata for rich dataset
ENHANCED_VENDOR_METADATA = {
    "SAP": {
        "vendorType": "ENTERPRISE_SOFTWARE",
        "category": "ERP",
        "deploymentModel": ["CLOUD", "ON_PREMISE", "HYBRID"],
        "licenseModel": "Subscription",
        "headquarters": "Walldorf, Germany",
        "website": "https://www.sap.com",
        "founded": 1972,
        "marketPosition": "LEADER",
    },
    "Salesforce": {
        "vendorType": "CLOUD_PROVIDER",
        "category": "CRM",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "headquarters": "San Francisco, California, USA",
        "website": "https://www.salesforce.com",
        "founded": 1999,
        "marketPosition": "LEADER",
    },
    "Workday": {
        "vendorType": "CLOUD_PROVIDER",
        "category": "HCM",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "headquarters": "Pleasanton, California, USA",
        "website": "https://www.workday.com",
        "founded": 2005,
        "marketPosition": "LEADER",
    },
    "Oracle": {
        "vendorType": "ENTERPRISE_SOFTWARE",
        "category": "SCM",
        "deploymentModel": ["CLOUD", "ON_PREMISE", "HYBRID"],
        "licenseModel": "Subscription",
        "headquarters": "Austin, Texas, USA",
        "website": "https://www.oracle.com",
        "founded": 1977,
        "marketPosition": "LEADER",
    },
    "IBM": {
        "vendorType": "ENTERPRISE_SOFTWARE",
        "category": "EAM",
        "deploymentModel": ["CLOUD", "ON_PREMISE", "HYBRID"],
        "licenseModel": "Subscription",
        "headquarters": "Armonk, New York, USA",
        "website": "https://www.ibm.com",
        "founded": 1911,
        "marketPosition": "LEADER",
    },
}


def transform_rich_vendor_data() -> Dict[str, Any]:
    """Transform rich vendor dataset into vendor catalogue structure."""

    vendor_catalogue = {}

    for item in RICH_VENDOR_DATA:
        vendor_name = item["vendor_name"]
        product_name = item["product_name"]
        domain = item["domain"]
        apqc_processes = item["apqc_processes"]
        capabilities = item["capabilities"]

        # Create vendor entry if not exists
        if vendor_name not in vendor_catalogue:
            metadata = ENHANCED_VENDOR_METADATA.get(vendor_name, {})
            vendor_catalogue[vendor_name] = {
                "id": vendor_name.lower().replace(" ", "_").replace(".", ""),
                "name": vendor_name,
                "vendorType": metadata.get("vendorType", "ENTERPRISE_SOFTWARE"),
                "category": domain,
                "deploymentModel": metadata.get("deploymentModel", ["CLOUD"]),
                "licenseModel": metadata.get("licenseModel", "Subscription"),
                "headquarters": metadata.get("headquarters", "Unknown"),
                "website": metadata.get("website", ""),
                "founded": metadata.get("founded", 2000),
                "marketPosition": metadata.get("marketPosition", "NICHE"),
                "products": {},
                "apqcProcesses": [],
                "capabilities": [],
            }

        # Extract APQC process codes from hierarchical structure
        apqc_process_codes = []
        for process in apqc_processes:
            # Extract level2 code (e.g., "8.2" from "8.2 Manage Revenue")
            level2_code = process["level2"].split(" ")[0]
            if level2_code not in apqc_process_codes:
                apqc_process_codes.append(level2_code)

        # Add product with enriched data
        vendor_catalogue[vendor_name]["products"][product_name] = {
            "name": product_name,
            "category": domain,
            "deploymentModel": vendor_catalogue[vendor_name]["deploymentModel"],
            "licenseModel": vendor_catalogue[vendor_name]["licenseModel"],
            "apqcProcesses": apqc_process_codes,
            "apqcProcessDetails": apqc_processes,  # Keep full hierarchy
            "capabilities": capabilities,
            "description": f"{vendor_name} {product_name} - Enterprise {domain} solution",
            "targetMarket": "Enterprise",
            "maturityLevel": "MANAGED",
            "verified": True,  # Rich data is verified
        }

        # Merge APQC processes (avoid duplicates)
        for process_code in apqc_process_codes:
            if process_code not in vendor_catalogue[vendor_name]["apqcProcesses"]:
                vendor_catalogue[vendor_name]["apqcProcesses"].append(process_code)

        # Merge capabilities (avoid duplicates)
        for capability in capabilities:
            if capability not in vendor_catalogue[vendor_name]["capabilities"]:
                vendor_catalogue[vendor_name]["capabilities"].append(capability)

    return vendor_catalogue


def generate_vendor_seeds(vendor_catalogue: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate vendor seed data for existing seed command pattern."""

    vendor_seeds = []

    for vendor_id, vendor_data in vendor_catalogue.items():
        # Create vendor seed entry
        vendor_seed = {
            "id": vendor_data["id"],
            "name": vendor_data["name"],
            "vendorType": vendor_data["vendorType"],
            "category": vendor_data["category"],
            "deploymentModel": vendor_data["deploymentModel"],
            "licenseModel": vendor_data["licenseModel"],
            "headquarters": vendor_data["headquarters"],
            "website": vendor_data["website"],
            "founded": vendor_data["founded"],
            "marketPosition": vendor_data["marketPosition"],
            "apqcProcesses": vendor_data["apqcProcesses"],
            "capabilities": vendor_data.get(
                "capabilities", []
            ),  # Include vendor-level capabilities
            "products": vendor_data["products"],
        }
        vendor_seeds.append(vendor_seed)

    return vendor_seeds


def main():
    """Main transformation function for rich vendor data."""
    print("🔄 Transforming rich vendor-product data to vendor catalogue structure...")

    # Transform rich data
    vendor_catalogue = transform_rich_vendor_data()
    vendor_seeds = generate_vendor_seeds(vendor_catalogue)

    print(f"✅ Transformed {len(vendor_seeds)} vendors")
    print(
        f"📊 Total APQC process coverage: {len(set([p for v in vendor_seeds for p in v['apqcProcesses']]))} processes"
    )
    print(
        f"🎯 Total capabilities: {len(set([c for v in vendor_seeds for c in v.get('capabilities', [])]))} capabilities"
    )

    # Display transformation results
    print("\n=== Transformed Rich Vendor Catalogue ===")
    for vendor in vendor_seeds:
        print(f"\n📋 {vendor['name']} ({vendor['vendorType']})")
        print(f"   Category: {vendor['category']}")
        print(f"   Products: {list(vendor['products'].keys())}")
        print(f"   APQC Processes: {len(vendor['apqcProcesses'])}")
        print(f"   Capabilities: {len(vendor.get('capabilities', []))}")
        print(f"   Deployment: {vendor['deploymentModel']}")

        # Show product details
        for product_name, product_data in vendor["products"].items():
            print(f"     📦 {product_name}")
            print(f"        APQC: {product_data['apqcProcesses']}")
            print(f"        Verified: {product_data.get('verified', False)}")

    return vendor_catalogue, vendor_seeds


if __name__ == "__main__":
    vendor_catalogue, vendor_seeds = main()

    # Save transformed rich data
    with open("transformed_rich_vendor_catalogue.json", "w") as f:
        json.dump(vendor_catalogue, f, indent=2)

    with open("transformed_rich_vendor_seeds.json", "w") as f:
        json.dump(vendor_seeds, f, indent=2)

    print(f"\n💾 Saved transformed rich data to:")
    print(f"   - transformed_rich_vendor_catalogue.json")
    print(f"   - transformed_rich_vendor_seeds.json")
