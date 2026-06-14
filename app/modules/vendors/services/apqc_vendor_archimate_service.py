"""
-> app.modules.vendors.services.integration_service

APQC-Vendor-ArchiMate Integration Service

Enhanced service that combines APQC process mappings with vendor capabilities
to generate intelligent, context-rich ArchiMate 3.2 elements.

This service bridges the gap between:
1. Application → APQC Process mappings
2. APQC Process → Vendor Product mappings
3. Vendor Product → ArchiMate elements

Creates enriched BusinessProcess elements with vendor context, coverage analysis,
and gap assessment.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.apqc_process import APQCProcess, ProcessApplicationMapping
from app.models.archimate_core import ArchiMateElement, ArchitectureModel
from app.models.vendor.vendor_organization import VendorProduct
from app.models.vendor_product_apqc_mapping import VendorProductAPQCMapping
from app.models.vendor_stack_template import VendorStackTemplate

logger = logging.getLogger(__name__)


class APQCVendorArchiMateService:
    """
    Service for generating APQC-vendor-enriched ArchiMate elements.

    This service creates intelligent BusinessProcess elements that combine:
    - APQC process information
    - Vendor product capabilities
    - Coverage levels and gaps
    - Integration requirements
    """

    @staticmethod
    def generate_apqc_vendor_enriched_archimate(
        application_id: int, created_by: Optional[str] = None
    ) -> Dict:
        """
        Generate APQC-vendor-enriched ArchiMate elements for an application.

        Process:
        1. Get APQC processes mapped to application
        2. Find vendor products supporting those processes
        3. Create enriched BusinessProcess elements with vendor context
        4. Generate vendor-specific ArchiMate elements based on coverage
        5. Provide gap analysis and recommendations

        Args:
            application_id: Application to generate elements for
            created_by: User creating the elements

        Returns:
            Dict with generation results, statistics, and gap analysis
        """
        app = db.session.get(ApplicationComponent, application_id)
        if not app:
            return {"success": False, "error": f"Application {application_id} not found"}

        logger.info(f"Starting APQC-vendor enriched ArchiMate generation for {app.name}")

        # 1. Get APQC processes mapped to this application
        app_apqc_mappings = APQCVendorArchiMateService._get_application_apqc_mappings(
            application_id
        )

        if not app_apqc_mappings:
            logger.info(f"No APQC process mappings found for application {app.name}")
            return {
                "success": True,
                "message": "No APQC process mappings found",
                "elements_created": 0,
                "vendor_products_found": 0,
                "gap_analysis": {},
            }

        logger.info(f"Found {len(app_apqc_mappings)} APQC process mappings")

        # 2. Find vendor products supporting these APQC processes
        vendor_coverage = APQCVendorArchiMateService._find_vendor_products_for_apqc_processes(
            [mapping.apqc_process_id for mapping in app_apqc_mappings]
        )

        logger.info(
            f"Found {len(vendor_coverage)} vendor products supporting mapped APQC processes"
        )

        # 3. Create enriched ArchiMate elements
        result = APQCVendorArchiMateService._create_enriched_archimate_elements(
            application_id=application_id,
            apqc_mappings=app_apqc_mappings,
            vendor_coverage=vendor_coverage,
            created_by=created_by,
        )

        # 4. Generate gap analysis
        gap_analysis = APQCVendorArchiMateService._generate_gap_analysis(
            apqc_mappings=app_apqc_mappings, vendor_coverage=vendor_coverage
        )

        result.update(
            {
                "success": True,
                "application_name": app.name,
                "apqc_processes_mapped": len(app_apqc_mappings),
                "vendor_products_found": len(vendor_coverage),
                "gap_analysis": gap_analysis,
                "generated_at": datetime.utcnow().isoformat(),
            }
        )

        logger.info(
            f"Generated {result['elements_created']} enriched ArchiMate elements for {app.name}"
        )
        return result

    @staticmethod
    def _get_application_apqc_mappings(application_id: int) -> List[ProcessApplicationMapping]:
        """Get all APQC process mappings for an application."""
        return ProcessApplicationMapping.query.filter_by(application_id=application_id).all()

    @staticmethod
    def _find_vendor_products_for_apqc_processes(
        apqc_process_ids: List[int],
    ) -> Dict[int, List[Dict]]:
        """
        Find vendor products that support the given APQC processes.

        Returns:
            Dict mapping apqc_process_id to list of vendor product info
        """
        vendor_coverage = {}

        for process_id in apqc_process_ids:
            # Find vendor product mappings for this APQC process
            vendor_mappings = VendorProductAPQCMapping.query.filter_by(
                apqc_process_id=process_id
            ).all()

            vendor_products = []
            for mapping in vendor_mappings:
                vendor_product = VendorProduct.query.get(mapping.vendor_product_id)
                if vendor_product:
                    vendor_products.append(
                        {
                            "vendor_product_id": vendor_product.id,
                            "vendor_name": vendor_product.vendor.organization_name
                            if vendor_product.vendor
                            else "Unknown",
                            "product_name": vendor_product.name,
                            "relevance_score": mapping.relevance_score,
                            "coverage_level": mapping.coverage_level,
                            "coverage_percentage": mapping.coverage_percentage,
                            "automation_capability": mapping.automation_capability,
                            "requires_customization": mapping.requires_customization,
                            "integration_complexity": mapping.integration_complexity,
                            "gaps": mapping.gaps or [],
                            "missing_features": mapping.missing_features or [],
                            "supports_levels": {
                                "level_1": mapping.supports_level_1,
                                "level_2": mapping.supports_level_2,
                                "level_3": mapping.supports_level_3,
                                "level_4": mapping.supports_level_4,
                                "level_5": mapping.supports_level_5,
                            },
                        }
                    )

            vendor_coverage[process_id] = vendor_products

        return vendor_coverage

    @staticmethod
    def _create_enriched_archimate_elements(
        application_id: int,
        apqc_mappings: List[ProcessApplicationMapping],
        vendor_coverage: Dict[int, List[Dict]],
        created_by: Optional[str] = None,
    ) -> Dict:
        """Create enriched ArchiMate elements combining APQC and vendor information."""

        app = db.session.get(ApplicationComponent, application_id)

        # Get or create architecture model
        arch_model = ArchitectureModel.query.filter_by(
            name=f"{app.name} APQC-Vendor Architecture"
        ).first()

        if not arch_model:
            arch_model = ArchitectureModel(
                name=f"{app.name} APQC-Vendor Architecture",
                model_data=json.dumps(
                    {
                        "source": "APQCVendorArchiMateService",
                        "application_id": application_id,
                        "generated_at": datetime.utcnow().isoformat(),
                        "description": f"APQC-vendor enriched architecture for {app.name}",
                    }
                ),
            )
            db.session.add(arch_model)
            db.session.flush()

        created_elements = []
        vendor_elements_created = 0

        # Create enriched BusinessProcess elements for each APQC mapping
        for mapping in apqc_mappings:
            apqc_process = APQCProcess.query.get(mapping.apqc_process_id)
            if not apqc_process:
                continue

            vendor_products = vendor_coverage.get(mapping.apqc_process_id, [])

            # Create primary BusinessProcess element
            process_element = APQCVendorArchiMateService._create_enriched_business_process(
                arch_model=arch_model,
                apqc_process=apqc_process,
                mapping=mapping,
                vendor_products=vendor_products,
                application_id=application_id,
            )
            created_elements.append(process_element)

            # Create vendor-specific supporting elements if good coverage exists
            for vendor_product in vendor_products:
                if vendor_product["coverage_percentage"] >= 70:  # Only for good coverage
                    vendor_element = APQCVendorArchiMateService._create_vendor_support_element(
                        arch_model=arch_model,
                        apqc_process=apqc_process,
                        vendor_product=vendor_product,
                        application_id=application_id,
                    )
                    created_elements.append(vendor_element)
                    vendor_elements_created += 1

        db.session.commit()

        return {
            "elements_created": len(created_elements),
            "vendor_elements_created": vendor_elements_created,
            "architecture_id": arch_model.id,
            "elements": [{"id": e.id, "name": e.name, "type": e.type} for e in created_elements],
        }

    @staticmethod
    def _create_enriched_business_process(
        arch_model: ArchitectureModel,
        apqc_process: APQCProcess,
        mapping: ProcessApplicationMapping,
        vendor_products: List[Dict],
        application_id: int,
    ) -> ArchiMateElement:
        """Create an enriched BusinessProcess element with vendor context."""

        # Calculate vendor coverage summary
        total_coverage = 0
        best_vendor = None
        max_coverage = 0

        for vendor in vendor_products:
            if vendor["coverage_percentage"] > max_coverage:
                max_coverage = vendor["coverage_percentage"]
                best_vendor = vendor
            total_coverage += vendor["coverage_percentage"]

        avg_coverage = total_coverage / len(vendor_products) if vendor_products else 0

        # Build enriched description
        description_parts = [
            f"PCF Process {apqc_process.process_code}: {apqc_process.process_name}",
            f"Category: {apqc_process.category_level_1} > {apqc_process.category_level_2}",
            f"Application Role: {mapping.application_role}",
            f"Support Level: {mapping.support_level}",
            f"Process Coverage: {mapping.process_coverage}%",
        ]

        if vendor_products:
            description_parts.extend(
                [
                    f"",
                    f"Vendor Support: {len(vendor_products)} vendor products",
                    f"Best Coverage: {best_vendor['vendor_name']} - {best_vendor['product_name']} ({max_coverage}%)",
                    f"Average Coverage: {avg_coverage:.1f}%",
                ]
            )

            if best_vendor["requires_customization"]:
                description_parts.append(
                    f"Customization Required: {best_vendor['customization_effort']}"
                )

            if best_vendor["gaps"]:
                description_parts.append(f"Known Gaps: {len(best_vendor['gaps'])} identified")
        else:
            description_parts.extend(
                [
                    "",
                    f"⚠️ NO VENDOR SUPPORT FOUND",
                    f"This process may require custom development or manual implementation",
                ]
            )

        element = ArchiMateElement(
            name=f"[{apqc_process.process_code}] {apqc_process.process_name}",
            type="BusinessProcess",
            layer="business",
            description="\n".join(description_parts),
            architecture_id=arch_model.id,
            properties=json.dumps(
                {
                    "source": "apqc_vendor_enriched",
                    "source_application_id": application_id,
                    "pcf_process_code": apqc_process.process_code,
                    "pcf_process_name": apqc_process.process_name,
                    "pcf_level_1": apqc_process.category_level_1,
                    "pcf_level_2": apqc_process.category_level_2,
                    "application_role": mapping.application_role,
                    "support_level": mapping.support_level,
                    "process_coverage": mapping.process_coverage,
                    "vendor_products_count": len(vendor_products),
                    "best_vendor": best_vendor["vendor_name"] if best_vendor else None,
                    "best_product": best_vendor["product_name"] if best_vendor else None,
                    "max_coverage": max_coverage,
                    "avg_coverage": round(avg_coverage, 1),
                    "has_vendor_support": len(vendor_products) > 0,
                    "requires_customization": best_vendor["requires_customization"]
                    if best_vendor
                    else False,
                    "gaps_count": len(best_vendor["gaps"]) if best_vendor else 0,
                }
            ),
        )

        db.session.add(element)
        return element

    @staticmethod
    def _create_vendor_support_element(
        arch_model: ArchitectureModel,
        apqc_process: APQCProcess,
        vendor_product: Dict,
        application_id: int,
    ) -> ArchiMateElement:
        """Create a vendor-specific supporting element."""

        element = ArchiMateElement(
            name=f"{vendor_product['vendor_name']}: {vendor_product['product_name']} - {apqc_process.process_name}",
            type="ApplicationService",
            layer="application",
            description=f"Vendor product supporting PCF Process {apqc_process.process_code}: {apqc_process.process_name}\n\n"
            f"Vendor: {vendor_product['vendor_name']}\n"
            f"Product: {vendor_product['product_name']}\n"
            f"Coverage: {vendor_product['coverage_percentage']}%\n"
            f"Relevance Score: {vendor_product['relevance_score']}/100\n"
            f"Automation Capability: {vendor_product['automation_capability']}%\n"
            f"Integration Complexity: {vendor_product['integration_complexity']}\n"
            f"Customization Required: {'Yes' if vendor_product['requires_customization'] else 'No'}",
            architecture_id=arch_model.id,
            properties=json.dumps(
                {
                    "source": "vendor_apqc_support",
                    "source_application_id": application_id,
                    "pcf_process_code": apqc_process.process_code,
                    "pcf_process_name": apqc_process.process_name,
                    "vendor_product_id": vendor_product["vendor_product_id"],
                    "vendor_name": vendor_product["vendor_name"],
                    "product_name": vendor_product["product_name"],
                    "coverage_level": vendor_product["coverage_level"],
                    "coverage_percentage": vendor_product["coverage_percentage"],
                    "relevance_score": vendor_product["relevance_score"],
                    "automation_capability": vendor_product["automation_capability"],
                    "integration_complexity": vendor_product["integration_complexity"],
                    "requires_customization": vendor_product["requires_customization"],
                    "supports_apqc_levels": vendor_product["supports_levels"],
                    "gaps_count": len(vendor_product["gaps"]),
                    "missing_features_count": len(vendor_product["missing_features"]),
                }
            ),
        )

        db.session.add(element)
        return element

    @staticmethod
    def _generate_gap_analysis(
        apqc_mappings: List[ProcessApplicationMapping], vendor_coverage: Dict[int, List[Dict]]
    ) -> Dict:
        """Generate comprehensive gap analysis."""

        total_processes = len(apqc_mappings)
        processes_with_vendor_support = 0
        processes_requiring_customization = 0
        high_coverage_processes = 0
        critical_gaps = []

        vendor_analysis = {}

        for mapping in apqc_mappings:
            process_id = mapping.apqc_process_id
            vendors = vendor_coverage.get(process_id, [])

            if vendors:
                processes_with_vendor_support += 1

                # Find best vendor for this process
                best_vendor = max(vendors, key=lambda v: v["coverage_percentage"])

                if best_vendor["requires_customization"]:
                    processes_requiring_customization += 1

                if best_vendor["coverage_percentage"] >= 80:
                    high_coverage_processes += 1

                # Track vendor performance
                vendor_name = best_vendor["vendor_name"]
                if vendor_name not in vendor_analysis:
                    vendor_analysis[vendor_name] = {
                        "processes_supported": 0,
                        "total_coverage": 0,
                        "customization_required": 0,
                    }

                vendor_analysis[vendor_name]["processes_supported"] += 1
                vendor_analysis[vendor_name]["total_coverage"] += best_vendor["coverage_percentage"]
                if best_vendor["requires_customization"]:
                    vendor_analysis[vendor_name]["customization_required"] += 1

                # Identify critical gaps
                if best_vendor["coverage_percentage"] < 50 or len(best_vendor["gaps"]) > 3:
                    critical_gaps.append(
                        {
                            "process_code": best_vendor.get("process_code", "Unknown"),
                            "vendor_name": vendor_name,
                            "coverage": best_vendor["coverage_percentage"],
                            "gaps_count": len(best_vendor["gaps"]),
                            "missing_features": len(best_vendor["missing_features"]),
                        }
                    )

        # Calculate vendor averages
        for vendor_data in vendor_analysis.values():
            vendor_data["avg_coverage"] = (
                vendor_data["total_coverage"] / vendor_data["processes_supported"]
            )

        return {
            "summary": {
                "total_apqc_processes": total_processes,
                "processes_with_vendor_support": processes_with_vendor_support,
                "processes_without_vendor_support": total_processes - processes_with_vendor_support,
                "processes_requiring_customization": processes_requiring_customization,
                "high_coverage_processes": high_coverage_processes,
                "vendor_support_percentage": round(
                    (processes_with_vendor_support / total_processes * 100)
                    if total_processes > 0
                    else 0,
                    1,
                ),
            },
            "vendor_analysis": vendor_analysis,
            "critical_gaps": critical_gaps[:10],  # Top 10 critical gaps
            "recommendations": APQCVendorArchiMateService._generate_recommendations(
                total_processes,
                processes_with_vendor_support,
                processes_requiring_customization,
                critical_gaps,
            ),
        }

    @staticmethod
    def _generate_recommendations(
        total_processes: int,
        processes_with_support: int,
        processes_requiring_customization: int,
        critical_gaps: List[Dict],
    ) -> List[str]:
        """Generate actionable recommendations based on gap analysis."""

        recommendations = []

        support_percentage = (
            (processes_with_support / total_processes * 100) if total_processes > 0 else 0
        )

        if support_percentage < 50:
            recommendations.append(
                "🚨 CRITICAL: Less than 50% of processes have vendor support. "
                "Consider custom development or alternative vendor evaluation."
            )
        elif support_percentage < 75:
            recommendations.append(
                "⚠️ WARNING: Only "
                + str(round(support_percentage, 1))
                + "% of processes have vendor support. "
                "Evaluate additional vendors or develop custom solutions."
            )

        if processes_requiring_customization > total_processes * 0.3:
            recommendations.append(
                "💰 HIGH CUSTOMIZATION: More than 30% of supported processes require customization. "
                "Budget for significant implementation effort."
            )

        if len(critical_gaps) > 5:
            recommendations.append(
                "🔍 MULTIPLE CRITICAL GAPS: "
                + str(len(critical_gaps))
                + " processes have significant coverage gaps. "
                "Prioritize gap analysis and mitigation planning."
            )

        if support_percentage >= 75 and processes_requiring_customization < total_processes * 0.2:
            recommendations.append(
                "✅ GOOD VENDOR COVERAGE: Strong vendor alignment with process requirements. "
                "Focus on integration and optimization."
            )

        return recommendations

    @staticmethod
    def bulk_generate_apqc_vendor_archimate(
        max_applications: int = 50,
        only_with_apqc_mappings: bool = True,
        created_by: Optional[str] = None,
    ) -> Dict:
        """
        Bulk generate APQC-vendor enriched ArchiMate elements for multiple applications.

        Args:
            max_applications: Maximum applications to process
            only_with_apqc_mappings: Only process apps that have APQC mappings
            created_by: User performing the action

        Returns:
            Dict with bulk processing results
        """
        # Find applications to process
        apps_query = ApplicationComponent.query

        if only_with_apqc_mappings:
            # Prioritize apps with APQC mappings
            apps = (
                apps_query.join(ProcessApplicationMapping)
                .order_by(ApplicationComponent.name)
                .limit(max_applications)
                .all()
            )
        else:
            apps = apps_query.order_by(ApplicationComponent.name).limit(max_applications).all()

        results = {
            "total_applications": len(apps),
            "processed": 0,
            "elements_created": 0,
            "vendor_elements_created": 0,
            "applications": [],
        }

        for app in apps:
            try:
                app_result = APQCVendorArchiMateService.generate_apqc_vendor_enriched_archimate(
                    application_id=app.id, created_by=created_by
                )

                results["processed"] += 1
                results["elements_created"] += app_result.get("elements_created", 0)
                results["vendor_elements_created"] += app_result.get("vendor_elements_created", 0)
                results["applications"].append(
                    {
                        "application_id": app.id,
                        "application_name": app.name,
                        "success": app_result.get("success", False),
                        "elements_created": app_result.get("elements_created", 0),
                        "vendor_products_found": app_result.get("vendor_products_found", 0),
                        "message": app_result.get("message", ""),
                    }
                )

            except Exception as e:
                logger.error(f"Error processing app {app.id}: {e}")
                results["applications"].append(
                    {
                        "application_id": app.id,
                        "application_name": app.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results
