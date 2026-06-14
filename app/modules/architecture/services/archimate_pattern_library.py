"""
-> app.modules.architecture.services.modeling_service

ArchiMate Pattern Library
Reusable architecture patterns for common enterprise scenarios
"""

import logging
from typing import Any, Dict, List, Optional

from app.models.application_portfolio import ApplicationComponent

logger = logging.getLogger(__name__)


class ArchiMatePatternLibrary:
    """Library of reusable ArchiMate architecture patterns."""

    PATTERNS = {
        "3_tier_web": {
            "name": "3 - Tier Web Application",
            "description": "Classic web architecture with presentation, business logic, and data tiers",
            "triggers": ["web application", "web-based", "browser", "http", "web app", "portal"],
            "confidence_threshold": 0.7,
            "elements": [
                {
                    "name": "{app} Web UI",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Web-based user interface",
                },
                {
                    "name": "{app} REST API",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "RESTful API service",
                },
                {
                    "name": "{app} Business Logic",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Core business logic tier",
                },
                {
                    "name": "{app} Database",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Persistent data storage",
                },
                {
                    "name": "Web Server",
                    "type": "Node",
                    "layer": "technology",
                    "description": "HTTP server hosting UI",
                },
                {
                    "name": "Application Server",
                    "type": "Node",
                    "layer": "technology",
                    "description": "Server hosting business logic",
                },
                {
                    "name": "Database Server",
                    "type": "Node",
                    "layer": "technology",
                    "description": "Database management system",
                },
            ],
            "relationships": [
                {"source": "{app} Web UI", "target": "{app} REST API", "type": "Serving"},
                {"source": "{app} REST API", "target": "{app} Business Logic", "type": "Serving"},
                {"source": "{app} Business Logic", "target": "{app} Database", "type": "Access"},
                {"source": "{app} Web UI", "target": "Web Server", "type": "Assignment"},
                {
                    "source": "{app} Business Logic",
                    "target": "Application Server",
                    "type": "Assignment",
                },
                {"source": "{app} Database", "target": "Database Server", "type": "Assignment"},
            ],
        },
        "microservices": {
            "name": "Microservices Architecture",
            "description": "Distributed architecture with independently deployable services",
            "triggers": [
                "microservice",
                "api gateway",
                "containerized",
                "kubernetes",
                "docker",
                "service mesh",
            ],
            "confidence_threshold": 0.75,
            "elements": [
                {
                    "name": "{app} API Gateway",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Central API gateway",
                },
                {
                    "name": "{app} Service A",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Microservice component A",
                },
                {
                    "name": "{app} Service B",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Microservice component B",
                },
                {
                    "name": "{app} Service C",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Microservice component C",
                },
                {
                    "name": "{app} Message Bus",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Async messaging system",
                },
                {
                    "name": "{app} Service Registry",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Service discovery",
                },
                {
                    "name": "Container Orchestrator",
                    "type": "SystemSoftware",
                    "layer": "technology",
                    "description": "Kubernetes/Docker Swarm",
                },
                {
                    "name": "Load Balancer",
                    "type": "Node",
                    "layer": "technology",
                    "description": "Traffic distribution",
                },
            ],
            "relationships": [
                {"source": "{app} API Gateway", "target": "{app} Service A", "type": "Serving"},
                {"source": "{app} API Gateway", "target": "{app} Service B", "type": "Serving"},
                {"source": "{app} API Gateway", "target": "{app} Service C", "type": "Serving"},
                {"source": "{app} Service A", "target": "{app} Message Bus", "type": "Serving"},
                {"source": "{app} Service B", "target": "{app} Message Bus", "type": "Serving"},
            ],
        },
        "saas_integration": {
            "name": "SaaS Integration",
            "description": "Integration with external SaaS platforms",
            "triggers": ["saas", "cloud service", "external api", "third-party", "integration"],
            "confidence_threshold": 0.7,
            "elements": [
                {
                    "name": "{app} Integration Layer",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Integration middleware",
                },
                {
                    "name": "{app} API Connector",
                    "type": "ApplicationInterface",
                    "layer": "application",
                    "description": "External API connector",
                },
                {
                    "name": "External SaaS Platform",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Third-party SaaS",
                },
                {
                    "name": "{app} Data Sync",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Data synchronization service",
                },
                {
                    "name": "{app} Local Cache",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Local data cache",
                },
            ],
            "relationships": [
                {
                    "source": "{app} Integration Layer",
                    "target": "{app} API Connector",
                    "type": "Serving",
                },
                {
                    "source": "{app} API Connector",
                    "target": "External SaaS Platform",
                    "type": "Serving",
                },
                {"source": "{app} Data Sync", "target": "{app} Local Cache", "type": "Access"},
            ],
        },
        "data_warehouse": {
            "name": "Data Warehouse",
            "description": "Enterprise data warehouse with ETL pipeline",
            "triggers": ["data warehouse", "etl", "bi", "analytics", "reporting", "olap"],
            "confidence_threshold": 0.75,
            "elements": [
                {
                    "name": "{app} ETL Pipeline",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Extract-Transform-Load process",
                },
                {
                    "name": "{app} Data Warehouse",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Central data warehouse",
                },
                {
                    "name": "{app} BI Tools",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Business intelligence tools",
                },
                {
                    "name": "{app} Data Mart",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Department-specific data mart",
                },
                {
                    "name": "Source Systems",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Operational source systems",
                },
                {
                    "name": "DW Server",
                    "type": "Node",
                    "layer": "technology",
                    "description": "Data warehouse server",
                },
            ],
            "relationships": [
                {"source": "{app} ETL Pipeline", "target": "Source Systems", "type": "Access"},
                {
                    "source": "{app} ETL Pipeline",
                    "target": "{app} Data Warehouse",
                    "type": "Access",
                },
                {"source": "{app} BI Tools", "target": "{app} Data Warehouse", "type": "Access"},
                {"source": "{app} Data Mart", "target": "{app} Data Warehouse", "type": "Access"},
            ],
        },
        "mobile_app": {
            "name": "Mobile Application",
            "description": "Mobile app with backend API",
            "triggers": ["mobile", "ios", "android", "mobile app", "smartphone"],
            "confidence_threshold": 0.7,
            "elements": [
                {
                    "name": "{app} Mobile Client",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Mobile application",
                },
                {
                    "name": "{app} Mobile API",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Backend API for mobile",
                },
                {
                    "name": "{app} Push Notification",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Push notification service",
                },
                {
                    "name": "{app} Mobile Backend",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Backend services",
                },
                {
                    "name": "Mobile Device",
                    "type": "Device",
                    "layer": "technology",
                    "description": "User smartphone/tablet",
                },
                {
                    "name": "API Gateway",
                    "type": "Node",
                    "layer": "technology",
                    "description": "Mobile API gateway",
                },
            ],
            "relationships": [
                {"source": "{app} Mobile Client", "target": "{app} Mobile API", "type": "Serving"},
                {"source": "{app} Mobile API", "target": "{app} Mobile Backend", "type": "Serving"},
                {
                    "source": "{app} Push Notification",
                    "target": "{app} Mobile Client",
                    "type": "Serving",
                },
            ],
        },
        "legacy_modernization": {
            "name": "Legacy Modernization",
            "description": "Modernizing legacy systems with adapters",
            "triggers": ["legacy", "mainframe", "modernization", "migration", "adapter"],
            "confidence_threshold": 0.7,
            "elements": [
                {
                    "name": "Legacy System",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Existing legacy system",
                },
                {
                    "name": "{app} Adapter Layer",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Legacy system adapter",
                },
                {
                    "name": "{app} Modern Interface",
                    "type": "ApplicationInterface",
                    "layer": "application",
                    "description": "Modern API interface",
                },
                {
                    "name": "{app} New System",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "New modern system",
                },
                {
                    "name": "{app} Data Migration",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Data migration service",
                },
            ],
            "relationships": [
                {"source": "{app} Adapter Layer", "target": "Legacy System", "type": "Serving"},
                {
                    "source": "{app} Modern Interface",
                    "target": "{app} Adapter Layer",
                    "type": "Serving",
                },
                {
                    "source": "{app} New System",
                    "target": "{app} Modern Interface",
                    "type": "Serving",
                },
            ],
        },
        "api_platform": {
            "name": "API Platform",
            "description": "API management and gateway platform",
            "triggers": ["api platform", "api management", "api gateway", "api portal"],
            "confidence_threshold": 0.75,
            "elements": [
                {
                    "name": "{app} API Gateway",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Central API gateway",
                },
                {
                    "name": "{app} API Manager",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "API lifecycle management",
                },
                {
                    "name": "{app} Developer Portal",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "API documentation portal",
                },
                {
                    "name": "{app} Rate Limiter",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "API rate limiting",
                },
                {
                    "name": "{app} Analytics",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "API usage analytics",
                },
            ],
            "relationships": [
                {"source": "{app} API Gateway", "target": "{app} Rate Limiter", "type": "Serving"},
                {"source": "{app} API Manager", "target": "{app} API Gateway", "type": "Serving"},
                {
                    "source": "{app} Developer Portal",
                    "target": "{app} API Manager",
                    "type": "Serving",
                },
            ],
        },
        "event_driven": {
            "name": "Event-Driven Architecture",
            "description": "Event-driven system with message brokers",
            "triggers": ["event-driven", "event sourcing", "cqrs", "message broker", "kafka"],
            "confidence_threshold": 0.75,
            "elements": [
                {
                    "name": "{app} Event Producer",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Event generation component",
                },
                {
                    "name": "{app} Event Bus",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Message broker/event bus",
                },
                {
                    "name": "{app} Event Consumer A",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Event consumer service A",
                },
                {
                    "name": "{app} Event Consumer B",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Event consumer service B",
                },
                {
                    "name": "{app} Event Store",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Event log storage",
                },
            ],
            "relationships": [
                {"source": "{app} Event Producer", "target": "{app} Event Bus", "type": "Serving"},
                {
                    "source": "{app} Event Bus",
                    "target": "{app} Event Consumer A",
                    "type": "Serving",
                },
                {
                    "source": "{app} Event Bus",
                    "target": "{app} Event Consumer B",
                    "type": "Serving",
                },
                {"source": "{app} Event Bus", "target": "{app} Event Store", "type": "Access"},
            ],
        },
        "batch_processing": {
            "name": "Batch Processing",
            "description": "Scheduled batch processing system",
            "triggers": ["batch", "scheduled", "cron", "batch processing", "etl batch"],
            "confidence_threshold": 0.7,
            "elements": [
                {
                    "name": "{app} Scheduler",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Job scheduler",
                },
                {
                    "name": "{app} Batch Processor",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Batch processing engine",
                },
                {
                    "name": "{app} Input Queue",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Input data queue",
                },
                {
                    "name": "{app} Output Store",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Processed data storage",
                },
                {
                    "name": "{app} Monitor",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Batch job monitoring",
                },
            ],
            "relationships": [
                {
                    "source": "{app} Scheduler",
                    "target": "{app} Batch Processor",
                    "type": "Triggering",
                },
                {
                    "source": "{app} Batch Processor",
                    "target": "{app} Input Queue",
                    "type": "Access",
                },
                {
                    "source": "{app} Batch Processor",
                    "target": "{app} Output Store",
                    "type": "Access",
                },
                {"source": "{app} Monitor", "target": "{app} Batch Processor", "type": "Serving"},
            ],
        },
        "serverless": {
            "name": "Serverless Architecture",
            "description": "Function-as-a-Service serverless pattern",
            "triggers": ["serverless", "lambda", "function", "faas", "cloud functions"],
            "confidence_threshold": 0.75,
            "elements": [
                {
                    "name": "{app} API Gateway",
                    "type": "ApplicationComponent",
                    "layer": "application",
                    "description": "Serverless API gateway",
                },
                {
                    "name": "{app} Function A",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Serverless function A",
                },
                {
                    "name": "{app} Function B",
                    "type": "ApplicationService",
                    "layer": "application",
                    "description": "Serverless function B",
                },
                {
                    "name": "{app} Object Storage",
                    "type": "DataObject",
                    "layer": "application",
                    "description": "Cloud object storage",
                },
                {
                    "name": "Serverless Platform",
                    "type": "SystemSoftware",
                    "layer": "technology",
                    "description": "FaaS platform",
                },
            ],
            "relationships": [
                {"source": "{app} API Gateway", "target": "{app} Function A", "type": "Triggering"},
                {"source": "{app} API Gateway", "target": "{app} Function B", "type": "Triggering"},
                {"source": "{app} Function A", "target": "{app} Object Storage", "type": "Access"},
            ],
        },
    }

    def detect_pattern(self, app: ApplicationComponent) -> Optional[Dict[str, Any]]:
        """Detect which pattern best matches the application."""
        try:
            description = (getattr(app, "description", None) or "").lower()
            tech_stack = (getattr(app, "technology_stack", None) or "").lower()
            functions = (getattr(app, "application_functions_text", None) or "").lower()

            combined_text = f"{description} {tech_stack} {functions}"

            best_match = None
            best_score = 0.0

            for pattern_id, pattern in self.PATTERNS.items():
                score = 0.0
                triggers = pattern["triggers"]

                for trigger in triggers:
                    if trigger in combined_text:
                        score += 1.0

                # Normalize score
                confidence = score / len(triggers) if triggers else 0.0

                if confidence >= pattern["confidence_threshold"] and confidence > best_score:
                    best_score = confidence
                    best_match = {
                        "pattern_id": pattern_id,
                        "pattern_name": pattern["name"],
                        "confidence": confidence,
                        "pattern": pattern,
                    }

            if best_match:
                logger.info(
                    f"✅ Detected pattern '{best_match['pattern_name']}' for {app.name} (confidence: {best_match['confidence']:.2%})"
                )
            else:
                logger.info(f"ℹ️ No pattern match for {app.name}, using generic generation")

            return best_match

        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return None

    def apply_pattern(self, pattern_id: str, app: ApplicationComponent) -> Dict[str, Any]:
        """Apply pattern template with app-specific names."""
        try:
            if pattern_id not in self.PATTERNS:
                return {"elements": [], "relationships": []}

            pattern = self.PATTERNS[pattern_id]
            app_name = app.name

            # Replace placeholders in elements
            elements = []
            for elem_template in pattern["elements"]:
                elem = elem_template.copy()
                elem["name"] = elem["name"].replace("{app}", app_name)
                elem["description"] = elem.get("description", "").replace("{app}", app_name)
                elements.append(elem)

            # Replace placeholders in relationships
            relationships = []
            for rel_template in pattern["relationships"]:
                rel = rel_template.copy()
                rel["source"] = rel["source"].replace("{app}", app_name)
                rel["target"] = rel["target"].replace("{app}", app_name)
                rel["description"] = rel.get("description", "").replace("{app}", app_name)
                relationships.append(rel)

            logger.info(
                f"✅ Applied pattern '{pattern['name']}' to {app_name}: {len(elements)} elements, {len(relationships)} relationships"
            )

            return {
                "elements": elements,
                "relationships": relationships,
                "pattern_name": pattern["name"],
                "pattern_id": pattern_id,
            }

        except Exception as e:
            logger.error(f"Pattern application error: {e}")
            return {"elements": [], "relationships": []}
