"""
Salesforce Vendor Stack Template Seed Data

This module contains comprehensive seed data for Salesforce technology stack.

Run with: python manage.py seed-vendor-salesforce
"""

import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig

# Salesforce Template
SALESFORCE_TEMPLATE = {
    "vendor_name": "Salesforce",
    "name": "Salesforce CRM Platform",
    "description": "Cloud-based Customer Relationship Management platform with Sales Cloud, Service Cloud, Marketing Cloud, and Platform services",
    "platform": "cloud",
    "primary_language": "apex",
    "framework": "Lightning",
    "api_standard": "REST",
    "vendor_company_name": "Salesforce, Inc.",
    "market_position": "leader",
    "company_size": "enterprise",
    "founded_year": 1999,
    "headquarters": "San Francisco, CA",
    # Hierarchical data
    "capabilities": [
        {
            "level": 0,
            "code": "CRM",
            "name": "Customer Relationship Management",
            "description": "End-to-end customer lifecycle management",
            "coverage_percentage": 95,
            "maturity_level": "optimized",
        },
        {
            "level": 1,
            "code": "CRM.SALES",
            "name": "Sales Management",
            "description": "Lead-to-opportunity-to-close sales processes",
            "parent_code": "CRM",
            "coverage_percentage": 98,
            "maturity_level": "optimized",
        },
        {
            "level": 1,
            "code": "CRM.SERVICE",
            "name": "Service Management",
            "description": "Case and service request management",
            "parent_code": "CRM",
            "coverage_percentage": 96,
            "maturity_level": "optimized",
        },
        {
            "level": 1,
            "code": "CRM.MARKETING",
            "name": "Marketing Automation",
            "description": "Campaign and journey management",
            "parent_code": "CRM",
            "coverage_percentage": 92,
            "maturity_level": "managed",
        },
        {
            "level": 1,
            "code": "CRM.COMMERCE",
            "name": "Commerce Management",
            "description": "B2B and B2C commerce capabilities",
            "parent_code": "CRM",
            "coverage_percentage": 90,
            "maturity_level": "managed",
        },
        {
            "level": 2,
            "code": "CRM.SALES.LEAD",
            "name": "Lead Management",
            "description": "Lead capture, scoring, and qualification",
            "parent_code": "CRM.SALES",
            "coverage_percentage": 97,
            "maturity_level": "optimized",
        },
        {
            "level": 2,
            "code": "CRM.SALES.OPP",
            "name": "Opportunity Management",
            "description": "Sales pipeline and forecasting",
            "parent_code": "CRM.SALES",
            "coverage_percentage": 98,
            "maturity_level": "optimized",
        },
        {
            "level": 2,
            "code": "CRM.SERVICE.CASE",
            "name": "Case Management",
            "description": "Customer issue tracking and resolution",
            "parent_code": "CRM.SERVICE",
            "coverage_percentage": 97,
            "maturity_level": "optimized",
        },
        {
            "level": 2,
            "code": "CRM.MARKETING.CAMPAIGN",
            "name": "Campaign Management",
            "description": "Multi-channel marketing campaigns",
            "parent_code": "CRM.MARKETING",
            "coverage_percentage": 93,
            "maturity_level": "managed",
        },
        {
            "level": 2,
            "code": "CRM.COMMERCE.ORDER",
            "name": "Order Management",
            "description": "Quote-to-cash order processing",
            "parent_code": "CRM.COMMERCE",
            "coverage_percentage": 91,
            "maturity_level": "managed",
        },
    ],
    "services": [
        {
            "code": "SVC.SALES.ORDER",
            "name": "Sales Order Processing",
            "service_type": "business-service",
            "layer": "business",
            "sla_availability": 99.9,
            "sla_response_time_ms": 500,
            "version": "1.0",
        },
        {
            "code": "SVC.SERVICE.CASE",
            "name": "Case Resolution Service",
            "service_type": "business-service",
            "layer": "business",
            "sla_availability": 99.95,
            "sla_response_time_ms": 300,
            "version": "1.0",
        },
        {
            "code": "SVC.API.REST",
            "name": "Salesforce REST API",
            "service_type": "application-service",
            "layer": "application",
            "sla_availability": 99.99,
            "sla_response_time_ms": 200,
            "version": "v58.0",
        },
        {
            "code": "SVC.API.BULK",
            "name": "Bulk API 2.0",
            "service_type": "application-service",
            "layer": "application",
            "sla_availability": 99.9,
            "sla_response_time_ms": 5000,
            "version": "2.0",
        },
    ],
    "processes": [
        {
            "level": 0,
            "code": "PROC.L2C",
            "name": "Lead-to-Cash",
            "description": "End-to-end sales process",
            "automation_percentage": 75,
            "cycle_time_days": 45,
        },
        {
            "level": 1,
            "code": "PROC.L2C.LEAD",
            "name": "Lead Qualification",
            "description": "Lead capture to qualification",
            "parent_code": "PROC.L2C",
            "automation_percentage": 85,
            "cycle_time_days": 7,
        },
        {
            "level": 1,
            "code": "PROC.L2C.OPP",
            "name": "Opportunity Management",
            "description": "Opportunity creation to close",
            "parent_code": "PROC.L2C",
            "automation_percentage": 70,
            "cycle_time_days": 38,
        },
    ],
    "components": [
        {
            "code": "COMP.UI.LWC",
            "name": "Lightning Web Components",
            "component_type": "ui-framework",
            "layer": "presentation",
            "technology": "JavaScript",
            "version": "2.0",
        },
        {
            "code": "COMP.APEX",
            "name": "Apex Engine",
            "component_type": "business-logic",
            "layer": "application",
            "technology": "Apex",
            "version": "58.0",
        },
        {
            "code": "COMP.DB",
            "name": "Multi-Tenant Database",
            "component_type": "database",
            "layer": "data",
            "technology": "Oracle",
            "version": "19c",
        },
        {
            "code": "COMP.PLATFORM",
            "name": "Force.com Platform",
            "component_type": "platform",
            "layer": "platform",
            "technology": "Proprietary",
            "version": "58.0",
        },
        {
            "code": "COMP.INTEGRATION",
            "name": "MuleSoft Anypoint",
            "component_type": "integration",
            "layer": "integration",
            "technology": "Java",
            "version": "4.5",
        },
    ],
    "integrations": [
        {
            "code": "INT.REST",
            "name": "REST API Integration",
            "integration_pattern": "request-response",
            "protocol": "HTTPS",
            "connector_type": "standard",
            "data_format": "JSON",
        },
        {
            "code": "INT.SOAP",
            "name": "SOAP API Integration",
            "integration_pattern": "request-response",
            "protocol": "HTTPS",
            "connector_type": "standard",
            "data_format": "XML",
        },
        {
            "code": "INT.EVENT",
            "name": "Platform Events",
            "integration_pattern": "event-driven",
            "protocol": "CometD",
            "connector_type": "standard",
            "data_format": "JSON",
        },
    ],
    "costs": [
        {
            "component_name": "Sales Cloud Enterprise",
            "cost_category": "licensing",
            "pricing_model": "per-user-monthly",
            "base_price_usd": 165,
            "tier": "enterprise",
        },
        {
            "component_name": "Service Cloud Enterprise",
            "cost_category": "licensing",
            "pricing_model": "per-user-monthly",
            "base_price_usd": 165,
            "tier": "enterprise",
        },
        {
            "component_name": "Marketing Cloud",
            "cost_category": "licensing",
            "pricing_model": "per-user-monthly",
            "base_price_usd": 1250,
            "tier": "enterprise",
        },
        {
            "component_name": "Data Storage",
            "cost_category": "infrastructure",
            "pricing_model": "per-gb-monthly",
            "base_price_usd": 100,
            "tier": "standard",
        },
        {
            "component_name": "API Calls",
            "cost_category": "usage",
            "pricing_model": "per - 1000 - calls",
            "base_price_usd": 0,
            "tier": "included",
            "hidden_costs": "Overage charges after limits",
        },
    ],
}


def create_salesforce_template():
    """Create Salesforce CRM Platform template from dict."""
    # Convert capabilities list to JSON for capabilities_enabled
    capabilities_enabled = [
        {
            "name": cap.get("name"),
            "description": cap.get("description"),
            "coverage_percentage": cap.get("coverage_percentage", 90),
            "maturity_level": cap.get("maturity_level", "managed"),
        }
        for cap in SALESFORCE_TEMPLATE.get("capabilities", [])
    ]

    return VendorStackTemplate(
        vendor_name=SALESFORCE_TEMPLATE["vendor_name"],
        name=SALESFORCE_TEMPLATE["name"],
        description=SALESFORCE_TEMPLATE["description"],
        platform=SALESFORCE_TEMPLATE.get("platform"),
        primary_language=SALESFORCE_TEMPLATE.get("primary_language"),
        framework=SALESFORCE_TEMPLATE.get("framework"),
        api_standard=SALESFORCE_TEMPLATE.get("api_standard"),
        vendor_company_name=SALESFORCE_TEMPLATE.get("vendor_company_name"),
        market_position=SALESFORCE_TEMPLATE.get("market_position"),
        company_size=SALESFORCE_TEMPLATE.get("company_size"),
        founded_year=SALESFORCE_TEMPLATE.get("founded_year"),
        headquarters=SALESFORCE_TEMPLATE.get("headquarters"),
        capabilities_enabled=json.dumps(capabilities_enabled),
    )


def seed_salesforce(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="Salesforce").first()
            if existing:
                print("⚠️  Salesforce template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_salesforce_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Salesforce CRM template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Product: {template.name}")
            print(f"   - Capabilities: {len(SALESFORCE_TEMPLATE.get('capabilities', []))}")

            # Link capabilities to BusinessCapability records
            if link_capabilities:
                print("\n🔗 Linking capabilities to BusinessCapability records...")
                from app.commands.vendor_capability_linker import VendorCapabilityLinker

                linker = VendorCapabilityLinker()
                results = linker.link_vendor_template_to_capabilities(
                    template,
                    create_missing=True,  # Create BusinessCapability if not exists
                    auto_link_fuzzy=False,  # Don't auto-link fuzzy matches (require exact)
                )

                linker.print_report(results)

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding Salesforce template: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_salesforce()
