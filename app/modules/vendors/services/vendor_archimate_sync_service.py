"""
-> app.modules.vendors.services.integration_service

Vendor ArchiMate Synchronization Service

Intelligently converts vendor catalogue JSON data (capabilities, services, processes, components)
into proper ArchiMate 3.2 elements that can be queried and displayed across all application views.

This service enables the platform to be ArchiMate-aware by:
1. Converting VendorStackTemplate JSON fields to individual ArchiMate element records
2. Linking ArchiMate elements to ApplicationComponents via relationships
3. Maintaining shared ArchiMate elements across multiple application instances
"""

import json
import logging

from sqlalchemy import func

from app import db
from app.models import VendorStackTemplate
from app.models.application_layer import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.process_data import BusinessProcess

logger = logging.getLogger(__name__)


def transactional(func):
    """Simple transactional decorator for methods that need DB commits."""

    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            db.session.rollback()
            raise e

    return wrapper


class VendorArchiMateSync:
    """Syncs vendor catalogue data to ArchiMate elements"""

    @transactional
    def __init__(self, vendor_template: VendorStackTemplate):
        self.vendor_template = vendor_template
        self.vendor_name = vendor_template.name
        self.synced_elements = {
            "capabilities": [],
            "resources": [],
            "value_streams": [],
            "courses_of_action": [],
            "services": [],
            "processes": [],
            "components": [],
            "requirements": [],
            "stakeholders": [],
        }

    @transactional
    def sync_all(self):
        """Sync all ArchiMate elements from vendor template"""
        logger.info(f"Starting ArchiMate sync for vendor: {self.vendor_name}")

        # Strategy Layer
        self._sync_capabilities()

        # Business Layer
        self._sync_services()
        self._sync_processes()

        # Application Layer
        self._sync_components()

        db.session.commit()
        logger.info(f"Completed ArchiMate sync for vendor: {self.vendor_name}")

        return self.synced_elements

    @transactional
    def _sync_capabilities(self):
        """Sync capabilities from vendor template to BusinessCapability model (Strategy Layer)"""
        capabilities_json = self.vendor_template.capabilities_enabled
        if not capabilities_json:
            return

        capabilities = (
            json.loads(capabilities_json)
            if isinstance(capabilities_json, str)
            else capabilities_json
        )
        for cap_data in capabilities:
            # Create unique identifier for capability
            cap_code = cap_data.get("code", cap_data.get("name", "").replace(" ", "_"))
            cap_name = cap_data.get("name")

            if not cap_name:
                continue

            # Check if capability already exists by name
            capability = BusinessCapability.query.filter(
                func.lower(BusinessCapability.name) == cap_name.lower()
            ).first()

            if not capability:
                capability = BusinessCapability(
                    name=cap_name,
                    description=cap_data.get("description"),
                    level=cap_data.get("level", 1),
                    category="vendor_template",
                    domain=self.vendor_name,
                    discovered_by_ai=True,
                    discovery_source="vendor_archimate_sync",
                )
                db.session.add(capability)
                logger.info(f"Created capability: {capability.name}")
            else:
                # Update existing capability
                if cap_data.get("description"):
                    capability.description = cap_data.get("description")
                if cap_data.get("level"):
                    capability.level = cap_data.get("level")
                logger.info(f"Updated capability: {capability.name}")

            self.synced_elements["capabilities"].append(capability)

    @transactional
    def _sync_services(self):
        """Sync services to BusinessProcess model (Business Layer - treating services as processes)"""
        services_json = getattr(self.vendor_template, "business_services", None)
        if not services_json:
            return

        services = json.loads(services_json) if isinstance(services_json, str) else services_json
        for svc_data in services:
            service_name = f"{self.vendor_name}: {svc_data.get('name')}"

            # Check if already exists
            service = BusinessProcess.query.filter_by(name=service_name).first()

            if not service:
                service = BusinessProcess(
                    name=service_name,
                    description=svc_data.get("description", ""),
                    process_type="vendor_service",
                    level=2,
                )
                db.session.add(service)
                logger.info(f"Created business service: {service_name}")

            self.synced_elements["services"].append(service)

    @transactional
    def _sync_processes(self):
        """Sync processes to BusinessProcess model (Business Layer)"""
        processes_json = getattr(self.vendor_template, "business_processes", None)
        if not processes_json:
            return

        processes = (
            json.loads(processes_json) if isinstance(processes_json, str) else processes_json
        )
        for proc_data in processes:
            process_code = proc_data.get("code", proc_data.get("name", "").replace(" ", "_"))
            process_name = f"{self.vendor_name}: {proc_data.get('name')}"

            # Check by unique process_code if available
            process = BusinessProcess.query.filter_by(
                process_code=f"{self.vendor_name}_{process_code}"
            ).first()

            if not process:
                process = BusinessProcess(
                    name=process_name,
                    process_code=f"{self.vendor_name}_{process_code}",
                    description=proc_data.get("description", ""),
                    automation_percentage=proc_data.get("automation_percentage"),
                    process_type="vendor",
                    level=proc_data.get("level", 2),
                )
                db.session.add(process)
                logger.info(f"Created business process: {process_name}")
            else:
                process.automation_percentage = proc_data.get(
                    "automation_percentage", process.automation_percentage
                )
                process.description = proc_data.get("description", process.description)
                logger.info(f"Updated business process: {process_name}")

            self.synced_elements["processes"].append(process)

    @transactional
    def _sync_components(self):
        """Sync components to ApplicationComponent model (Application Layer)"""
        components_json = getattr(self.vendor_template, "application_components", None) or getattr(
            self.vendor_template, "components", None
        )
        if not components_json:
            return

        components = (
            json.loads(components_json) if isinstance(components_json, str) else components_json
        )
        for comp_data in components:
            comp_name = f"{self.vendor_name} {comp_data.get('name')}"

            component = ApplicationComponent.query.filter_by(name=comp_name).first()

            # Capture vendor classification separately and normalize canonical type
            vendor_class = comp_data.get("component_type") or comp_data.get("type") or None
            canonical_type = "ApplicationComponent"

            if not component:
                component = ApplicationComponent(
                    name=comp_name,
                    description=comp_data.get("description"),
                    component_type=canonical_type,
                    technology_stack=comp_data.get("technology")
                    or comp_data.get("technology_stack"),
                    version=comp_data.get("version"),
                    deployment_status="production",
                )
                # Store vendor classification in tags (JSON) to keep metadata but remain ArchiMate-compliant
                try:
                    vendor_meta = {"vendor_classification": vendor_class} if vendor_class else {}
                    component.tags = json.dumps(vendor_meta) if vendor_meta else None
                except Exception:
                    component.tags = None

                db.session.add(component)
                logger.info(f"Created application component: {component.name}")
            else:
                component.description = comp_data.get("description", component.description)
                component.component_type = canonical_type
                component.technology_stack = (
                    comp_data.get("technology")
                    or comp_data.get("technology_stack")
                    or component.technology_stack
                )
                try:
                    existing_tags = {}
                    if component.tags:
                        try:
                            existing_tags = json.loads(component.tags)
                        except Exception:
                            existing_tags = {}

                    if vendor_class:
                        existing_tags["vendor_classification"] = vendor_class
                        component.tags = json.dumps(existing_tags)
                except Exception:
                    logger.exception("Failed to compute existing_tags")
                    pass

                logger.info(f"Updated application component: {component.name}")

            self.synced_elements["components"].append(component)

    @transactional
    def link_to_application(self, application: ApplicationComponent):
        """
        Link all synced ArchiMate elements to a specific application instance
        Elements are already linked via vendor_name matching
        """
        logger.info(f"ArchiMate elements linked to application via vendor_name: {application.name}")
        db.session.commit()


def sync_vendor_template_to_archimate(vendor_template_id: int, link_to_app_id: int = None):
    """
    Main entry point to sync a vendor template to ArchiMate elements

    Args:
        vendor_template_id: ID of VendorStackTemplate to sync
        link_to_app_id: Optional ApplicationComponent ID to link elements to

    Returns:
        dict: Summary of synced elements
    """
    vendor_template = VendorStackTemplate.query.get(vendor_template_id)
    if not vendor_template:
        raise ValueError(f"VendorStackTemplate with ID {vendor_template_id} not found")

    sync_service = VendorArchiMateSync(vendor_template)
    synced_elements = sync_service.sync_all()

    # Link to application if specified
    if link_to_app_id:
        application = ApplicationComponent.query.get(link_to_app_id)
        if application:
            sync_service.link_to_application(application)
        else:
            logger.warning(f"ApplicationComponent with ID {link_to_app_id} not found")

    return {
        "vendor_name": vendor_template.name,
        "synced_counts": {
            "capabilities": len(synced_elements["capabilities"]),
            "services": len(synced_elements["services"]),
            "processes": len(synced_elements["processes"]),
            "components": len(synced_elements["components"]),
        },
    }


def sync_all_vendor_templates():
    """Sync all existing vendor templates to ArchiMate elements"""
    vendor_templates = VendorStackTemplate.query.all()
    results = []

    for template in vendor_templates:
        try:
            result = sync_vendor_template_to_archimate(template.id)
            results.append(result)
            logger.info(f"Synced vendor template: {template.name}")
        except Exception as e:
            logger.error(f"Failed to sync vendor template {template.name}: {str(e)}")
            results.append({"vendor_name": template.name, "error": str(e)})

    return results
