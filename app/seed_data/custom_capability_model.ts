/**
 * Custom Capability Model to Vendor Mapping
 *
 * Maps the three-level capability model to vendors in the catalogue and
 * provides helper functions for coverage analysis.
 */

import { VENDOR_CATALOGUE, type VendorInfo } from "./vendor_catalogue";

// ============================================================================
// CUSTOM CAPABILITY MODEL DEFINITION
// ============================================================================

export interface Level3Capability {
  name: string;
  mappedVendorCapabilities: string[]; // Capability slugs from the vendor catalogue
  mappedVendors?: string[]; // Direct vendor name mappings where applicable
}

export interface Level2Capability {
  name: string;
  level3: Level3Capability[];
}

export interface Level1Domain {
  name: string;
  description: string;
  level2: Level2Capability[];
}

export const CUSTOM_CAPABILITY_MODEL: Level1Domain[] = [
  {
    name: "Information Consumer Capabilities",
    description: "User-facing capabilities for consuming and interacting with information",
    level2: [
      {
        name: "Experience Orchestration",
        level3: [
          {
            name: "Journey mapping service",
            mappedVendorCapabilities: ["workflow-orchestration", "automation"],
            mappedVendors: ["Pega", "Appian", "ServiceNow"],
          },
          {
            name: "Contextual content assembly",
            mappedVendorCapabilities: ["ai-ml", "integration-platform"],
            mappedVendors: ["ServiceNow", "Pega"],
          },
          {
            name: "Adaptive UI layout engine",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: [],
          },
          {
            name: "Accessibility compliance toolkit",
            mappedVendorCapabilities: ["compliance-management"],
            mappedVendors: ["ServiceNow GRC", "MetricStream"],
          },
        ],
      },
      {
        name: "Multi-Channel Delivery",
        level3: [
          {
            name: "Web experience delivery",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["ServiceNow", "AWS", "Azure", "GCP"],
          },
          {
            name: "Native mobile delivery",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "ServiceNow"],
          },
          {
            name: "Conversational interfaces",
            mappedVendorCapabilities: ["ai-ml", "automation"],
            mappedVendors: ["ServiceNow", "Pega", "AWS", "Azure"],
          },
          {
            name: "Kiosk/embedded client delivery",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: [],
          },
        ],
      },
      {
        name: "Personalization & Insight Surfaces",
        level3: [
          {
            name: "Segmentation engine",
            mappedVendorCapabilities: ["ai-ml", "reporting-analytics"],
            mappedVendors: ["ServiceNow", "Dynatrace", "Datadog"],
          },
          {
            name: "Recommendation service",
            mappedVendorCapabilities: ["ai-ml"],
            mappedVendors: ["ServiceNow", "AWS", "Azure", "GCP"],
          },
          {
            name: "Behavioral analytics dashboard",
            mappedVendorCapabilities: ["reporting-analytics", "monitoring-alerting"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
          {
            name: "A/B & feature experimentation",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: [],
          },
        ],
      },
      {
        name: "Workflow Interaction Surfaces",
        level3: [
          {
            name: "Task automation console",
            mappedVendorCapabilities: ["workflow-orchestration", "automation"],
            mappedVendors: ["ServiceNow", "Pega", "Appian"],
          },
          {
            name: "Approval & exception handling UI",
            mappedVendorCapabilities: ["workflow-orchestration"],
            mappedVendors: ["ServiceNow", "Pega", "Appian"],
          },
          {
            name: "Guided decision support",
            mappedVendorCapabilities: ["ai-ml", "workflow-orchestration"],
            mappedVendors: ["Pega", "Appian"],
          },
          {
            name: "Collaborative workspace integration",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["ServiceNow", "GitHub", "GitLab"],
          },
        ],
      },
      {
        name: "Edge & Offline Client Support",
        level3: [
          {
            name: "Sync & conflict resolution",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Edge cache management",
            mappedVendorCapabilities: ["monitoring-alerting"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog"],
          },
          {
            name: "Device provisioning & hardening",
            mappedVendorCapabilities: ["security-management", "configuration-management"],
            mappedVendors: ["CrowdStrike", "Palo Alto"],
          },
          {
            name: "Offline telemetry batching",
            mappedVendorCapabilities: ["monitoring-alerting"],
            mappedVendors: ["Dynatrace", "Datadog", "New Relic"],
          },
        ],
      },
    ],
  },
  {
    name: "Development Capabilities",
    description: "Developer-centric capabilities for building and shipping software",
    level2: [
      {
        name: "Platform Engineering Toolchain",
        level3: [
          {
            name: "CI pipeline orchestration",
            mappedVendorCapabilities: ["automation", "workflow-orchestration"],
            mappedVendors: ["GitHub", "GitLab", "Jenkins"],
          },
          {
            name: "Artifact/version management",
            mappedVendorCapabilities: ["configuration-management"],
            mappedVendors: ["GitHub", "GitLab", "Jenkins"],
          },
          {
            name: "Environment provisioning",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: ["AWS", "Azure", "GCP", "GitHub", "GitLab"],
          },
          {
            name: "IaC blueprint library",
            mappedVendorCapabilities: ["configuration-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "GitHub", "GitLab"],
          },
        ],
      },
      {
        name: "Blueprint & Scaffolding Services",
        level3: [
          {
            name: "Domain templates & archetypes",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: ["GitHub", "GitLab"],
          },
          {
            name: "Boilerplate code generators",
            mappedVendorCapabilities: ["automation", "ai-ml"],
            mappedVendors: ["GitHub", "GitLab"],
          },
          {
            name: "Reference implementations gallery",
            mappedVendorCapabilities: ["knowledge-management"],
            mappedVendors: ["GitHub", "GitLab", "ServiceNow"],
          },
          {
            name: "Compliance-ready stack configs",
            mappedVendorCapabilities: ["compliance-management", "configuration-management"],
            mappedVendors: ["ServiceNow GRC", "MetricStream"],
          },
        ],
      },
      {
        name: "Automation & Testing Services",
        level3: [
          {
            name: "Continuous testing suite",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: ["GitHub", "GitLab", "Jenkins"],
          },
          {
            name: "Quality gate automation",
            mappedVendorCapabilities: ["automation", "governance-framework"],
            mappedVendors: ["GitHub", "GitLab", "Jenkins"],
          },
          {
            name: "Performance & resiliency testing harness",
            mappedVendorCapabilities: ["monitoring-alerting", "performance-management"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
          {
            name: "Security testing pipeline",
            mappedVendorCapabilities: ["security-management", "automation"],
            mappedVendors: ["GitHub", "GitLab", "Splunk", "CrowdStrike", "Palo Alto"],
          },
        ],
      },
      {
        name: "Developer Experience Portal",
        level3: [
          {
            name: "Self-service catalog",
            mappedVendorCapabilities: ["service-catalog"],
            mappedVendors: ["ServiceNow", "Freshservice", "Pega"],
          },
          {
            name: "Workflow automation (golden paths)",
            mappedVendorCapabilities: ["workflow-orchestration", "automation"],
            mappedVendors: ["GitHub", "GitLab", "ServiceNow"],
          },
          {
            name: "Knowledge base & runbooks",
            mappedVendorCapabilities: ["knowledge-management"],
            mappedVendors: ["ServiceNow", "BMC Helix", "Ivanti", "Collibra"],
          },
          {
            name: "Feedback & community features",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["GitHub", "GitLab"],
          },
        ],
      },
      {
        name: "AI-Assisted Development",
        level3: [
          {
            name: "Code completion/co-pilot services",
            mappedVendorCapabilities: ["ai-ml"],
            mappedVendors: ["GitHub", "AWS", "Azure", "GCP"],
          },
          {
            name: "Requirements-to-test generation",
            mappedVendorCapabilities: ["ai-ml", "automation"],
            mappedVendors: ["ServiceNow", "GitHub"],
          },
          {
            name: "Documentation synthesis",
            mappedVendorCapabilities: ["ai-ml", "knowledge-management"],
            mappedVendors: ["GitHub", "ServiceNow", "Collibra"],
          },
          {
            name: "AI model governance for dev tools",
            mappedVendorCapabilities: ["governance-framework", "ai-ml"],
            mappedVendors: ["ServiceNow GRC", "BiZZdesign"],
          },
        ],
      },
    ],
  },
  {
    name: "Brokering Capabilities",
    description: "Integration and mediation capabilities for connecting systems",
    level2: [
      {
        name: "API Mediation Layer",
        level3: [
          {
            name: "API gateway & rate shaping",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "Palo Alto"],
          },
          {
            name: "Protocol transformation",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "ServiceNow"],
          },
          {
            name: "API lifecycle & monetization",
            mappedVendorCapabilities: ["governance-framework", "financial-management"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Developer onboarding & keys",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "Palo Alto"],
          },
        ],
      },
      {
        name: "Event Streaming & Choreography",
        level3: [
          {
            name: "Event bus management",
            mappedVendorCapabilities: ["integration-platform", "monitoring-alerting"],
            mappedVendors: ["AWS", "Azure", "GCP", "ServiceNow"],
          },
          {
            name: "Schema/contract registry",
            mappedVendorCapabilities: ["configuration-management", "governance-framework"],
            mappedVendors: ["GitHub", "GitLab", "ServiceNow"],
          },
          {
            name: "Stream processing",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog"],
          },
          {
            name: "Saga/orchestration framework",
            mappedVendorCapabilities: ["workflow-orchestration"],
            mappedVendors: ["AWS", "Azure", "Pega", "Appian"],
          },
        ],
      },
      {
        name: "Integration Adapter Marketplace",
        level3: [
          {
            name: "Connector library curation",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["ServiceNow", "AWS", "Azure", "GCP"],
          },
          {
            name: "Adapter development sandbox",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Credential vaulting",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "Palo Alto", "CrowdStrike"],
          },
          {
            name: "Managed connectivity monitoring",
            mappedVendorCapabilities: ["monitoring-alerting", "integration-platform"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
        ],
      },
      {
        name: "Data Virtualization & Semantic Mapping",
        level3: [
          {
            name: "Logical data fabric",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "Collibra"],
          },
          {
            name: "Semantic model catalog",
            mappedVendorCapabilities: ["governance-framework", "knowledge-management"],
            mappedVendors: ["Collibra", "Alation"],
          },
          {
            name: "Query federation",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "Collibra", "Alation"],
          },
          {
            name: "Policy-aware data delivery",
            mappedVendorCapabilities: ["governance-framework", "compliance-management"],
            mappedVendors: ["Collibra", "Alation", "ServiceNow GRC"],
          },
        ],
      },
      {
        name: "Service Mesh & Traffic Control",
        level3: [
          {
            name: "Sidecar/mesh management",
            mappedVendorCapabilities: ["integration-platform", "monitoring-alerting"],
            mappedVendors: ["AWS", "Azure", "GCP", "Dynatrace"],
          },
          {
            name: "Zero-trust network policy",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["Palo Alto", "CrowdStrike", "AWS", "Azure", "GCP"],
          },
          {
            name: "Circuit-breaking & QoS routing",
            mappedVendorCapabilities: ["monitoring-alerting", "automation"],
            mappedVendors: ["AWS", "Azure", "GCP", "Dynatrace", "AppDynamics"],
          },
          {
            name: "Runtime topology visualization",
            mappedVendorCapabilities: ["monitoring-alerting", "reporting-analytics"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
        ],
      },
    ],
  },
  {
    name: "Management Utility Capabilities",
    description: "Operational management and observability capabilities",
    level2: [
      {
        name: "Observability & Telemetry",
        level3: [
          {
            name: "Metrics collection & storage",
            mappedVendorCapabilities: ["monitoring-alerting"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic", "Splunk"],
          },
          {
            name: "Distributed tracing",
            mappedVendorCapabilities: ["monitoring-alerting", "performance-management"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
          {
            name: "Log aggregation & analytics",
            mappedVendorCapabilities: ["monitoring-alerting", "reporting-analytics"],
            mappedVendors: ["Splunk", "Datadog", "New Relic", "Dynatrace"],
          },
          {
            name: "Business KPI instrumentation",
            mappedVendorCapabilities: ["reporting-analytics", "performance-management"],
            mappedVendors: ["Dynatrace", "AppDynamics", "BiZZdesign", "MetricStream"],
          },
        ],
      },
      {
        name: "Configuration & Feature Management",
        level3: [
          {
            name: "Centralized config service",
            mappedVendorCapabilities: ["configuration-management"],
            mappedVendors: ["ServiceNow", "BMC Helix", "AWS", "Azure"],
          },
          {
            name: "Feature flag targeting",
            mappedVendorCapabilities: ["configuration-management"],
            mappedVendors: [],
          },
          {
            name: "Release segmentation",
            mappedVendorCapabilities: ["release-management"],
            mappedVendors: ["ServiceNow", "BMC Helix", "GitHub", "GitLab"],
          },
          {
            name: "Compliance drift detection",
            mappedVendorCapabilities: ["compliance-management", "monitoring-alerting"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream"],
          },
        ],
      },
      {
        name: "Policy & Compliance Automation",
        level3: [
          {
            name: "Policy-as-code authoring",
            mappedVendorCapabilities: ["compliance-management", "automation"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "AWS", "Azure"],
          },
          {
            name: "Automated compliance scanning",
            mappedVendorCapabilities: ["compliance-management", "security-management"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "Splunk", "CrowdStrike"],
          },
          {
            name: "Audit evidence vault",
            mappedVendorCapabilities: ["audit-compliance"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "LogicManager"],
          },
          {
            name: "Remediation workflow",
            mappedVendorCapabilities: ["workflow-orchestration", "compliance-management"],
            mappedVendors: ["ServiceNow GRC", "Archer", "Palo Alto"],
          },
        ],
      },
      {
        name: "FinOps & Sustainability Management",
        level3: [
          {
            name: "Cost allocation & showback",
            mappedVendorCapabilities: ["financial-management", "reporting-analytics"],
            mappedVendors: ["Snow Software", "Flexera", "ServiceNow ITAM", "AWS", "Azure", "GCP"],
          },
          {
            name: "Capacity/right-sizing analytics",
            mappedVendorCapabilities: ["capacity-planning", "resource-optimization"],
            mappedVendors: ["AWS", "Azure", "GCP", "Dynatrace", "Snow Software", "Flexera"],
          },
          {
            name: "Carbon impact tracking",
            mappedVendorCapabilities: ["reporting-analytics"],
            mappedVendors: [],
          },
          {
            name: "Optimization recommendation engine",
            mappedVendorCapabilities: ["ai-ml", "resource-optimization"],
            mappedVendors: ["AWS", "Azure", "GCP", "Flexera", "Snow Software"],
          },
        ],
      },
      {
        name: "Incident & Operations Center",
        level3: [
          {
            name: "Event correlation & alerting",
            mappedVendorCapabilities: ["monitoring-alerting", "incident-management"],
            mappedVendors: ["ServiceNow", "Dynatrace", "Splunk", "Datadog", "Palo Alto"],
          },
          {
            name: "Runbook automation",
            mappedVendorCapabilities: ["automation", "incident-management"],
            mappedVendors: ["ServiceNow", "Palo Alto", "Dynatrace"],
          },
          {
            name: "Major incident command center",
            mappedVendorCapabilities: ["incident-management", "workflow-orchestration"],
            mappedVendors: ["ServiceNow", "BMC Helix", "Ivanti"],
          },
          {
            name: "Post-incident review analytics",
            mappedVendorCapabilities: ["reporting-analytics", "problem-management"],
            mappedVendors: ["ServiceNow", "BMC Helix", "Dynatrace", "Splunk"],
          },
        ],
      },
    ],
  },
  {
    name: "Information Provider Capabilities",
    description: "Data ingestion, processing, and serving capabilities",
    level2: [
      {
        name: "Data Ingestion Gateways",
        level3: [
          {
            name: "Batch & streaming ingestion",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog", "Splunk"],
          },
          {
            name: "Source connector management",
            mappedVendorCapabilities: ["integration-platform", "configuration-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "ServiceNow"],
          },
          {
            name: "Data quality gate",
            mappedVendorCapabilities: ["governance-framework"],
            mappedVendors: ["Collibra", "Alation"],
          },
          {
            name: "Landing-zone governance",
            mappedVendorCapabilities: ["governance-framework", "compliance-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "Collibra", "Alation"],
          },
        ],
      },
      {
        name: "Data Processing & Enrichment",
        level3: [
          {
            name: "ETL/ELT orchestration",
            mappedVendorCapabilities: ["workflow-orchestration", "integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "ServiceNow"],
          },
          {
            name: "Real-time enrichment pipelines",
            mappedVendorCapabilities: ["integration-platform", "ai-ml"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog"],
          },
          {
            name: "Metadata & lineage capture",
            mappedVendorCapabilities: ["governance-framework", "configuration-management"],
            mappedVendors: ["Collibra", "Alation", "ServiceNow"],
          },
          {
            name: "Validation & anomaly detection",
            mappedVendorCapabilities: ["monitoring-alerting", "ai-ml"],
            mappedVendors: ["Dynatrace", "Datadog", "Splunk", "Collibra"],
          },
        ],
      },
      {
        name: "Knowledge Graph & Master Data Services",
        level3: [
          {
            name: "Entity resolution",
            mappedVendorCapabilities: ["governance-framework"],
            mappedVendors: ["Collibra", "Alation", "ServiceNow"],
          },
          {
            name: "Hierarchy & relationship management",
            mappedVendorCapabilities: ["configuration-management", "governance-framework"],
            mappedVendors: ["ServiceNow", "Collibra", "Alation", "BiZZdesign", "Ardoq"],
          },
          {
            name: "Golden record stewardship",
            mappedVendorCapabilities: ["governance-framework"],
            mappedVendors: ["Collibra", "Alation", "ServiceNow"],
          },
          {
            name: "Semantic query APIs",
            mappedVendorCapabilities: ["integration-platform"],
            mappedVendors: ["Collibra", "Alation", "AWS", "Azure"],
          },
        ],
      },
      {
        name: "Content & Object Storage Federation",
        level3: [
          {
            name: "Unified content indexing",
            mappedVendorCapabilities: ["knowledge-management"],
            mappedVendors: ["ServiceNow", "Collibra", "Alation"],
          },
          {
            name: "Storage lifecycle policies",
            mappedVendorCapabilities: ["configuration-management", "governance-framework"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Secure content distribution",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "Palo Alto"],
          },
          {
            name: "DRM & legal hold management",
            mappedVendorCapabilities: ["compliance-management", "governance-framework"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream"],
          },
        ],
      },
      {
        name: "Analytic & Model Serving Endpoints",
        level3: [
          {
            name: "Feature store management",
            mappedVendorCapabilities: ["configuration-management", "ai-ml"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog"],
          },
          {
            name: "Online/offline inference services",
            mappedVendorCapabilities: ["ai-ml", "integration-platform"],
            mappedVendors: ["AWS", "Azure", "GCP", "ServiceNow"],
          },
          {
            name: "Model deployment & promotion",
            mappedVendorCapabilities: ["release-management", "ai-ml"],
            mappedVendors: ["AWS", "Azure", "GCP", "GitHub", "GitLab"],
          },
          {
            name: "Monitoring & drift detection",
            mappedVendorCapabilities: ["monitoring-alerting", "ai-ml"],
            mappedVendors: ["Dynatrace", "Datadog", "AWS", "Azure", "GCP"],
          },
        ],
      },
    ],
  },
  {
    name: "Cross-Cutting Qualities",
    description: "Non-functional requirements and quality attributes",
    level2: [
      {
        name: "Performance & SLO Governance",
        level3: [
          {
            name: "SLO definition registry",
            mappedVendorCapabilities: ["governance-framework", "performance-management"],
            mappedVendors: ["ServiceNow", "Dynatrace", "Datadog"],
          },
          {
            name: "Synthetic monitoring",
            mappedVendorCapabilities: ["monitoring-alerting", "performance-management"],
            mappedVendors: ["Dynatrace", "AppDynamics", "Datadog", "New Relic"],
          },
          {
            name: "Auto-scaling policies",
            mappedVendorCapabilities: ["automation", "resource-optimization"],
            mappedVendors: ["AWS", "Azure", "GCP", "Dynatrace"],
          },
          {
            name: "Continuous performance review board",
            mappedVendorCapabilities: ["performance-management", "reporting-analytics"],
            mappedVendors: ["Dynatrace", "AppDynamics", "BiZZdesign"],
          },
        ],
      },
      {
        name: "Management Policy Controls",
        level3: [
          {
            name: "Policy catalog & versioning",
            mappedVendorCapabilities: ["governance-framework", "configuration-management"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "BiZZdesign"],
          },
          {
            name: "Control-mapping automation",
            mappedVendorCapabilities: ["compliance-management", "automation"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream"],
          },
          {
            name: "Change impact analysis",
            mappedVendorCapabilities: ["change-management", "reporting-analytics"],
            mappedVendors: ["ServiceNow", "BMC Helix", "BiZZdesign", "Ardoq"],
          },
          {
            name: "Delegated approval workflow",
            mappedVendorCapabilities: ["workflow-orchestration", "change-management"],
            mappedVendors: ["ServiceNow", "Pega", "Appian", "BMC Helix"],
          },
        ],
      },
      {
        name: "Zero-Trust Security Fabric",
        level3: [
          {
            name: "Identity & access orchestration",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["Palo Alto", "CrowdStrike", "AWS", "Azure", "GCP"],
          },
          {
            name: "Secrets & key management",
            mappedVendorCapabilities: ["security-management"],
            mappedVendors: ["AWS", "Azure", "GCP", "Palo Alto", "CrowdStrike"],
          },
          {
            name: "Continuous posture assessment",
            mappedVendorCapabilities: ["security-management", "compliance-management"],
            mappedVendors: ["CrowdStrike", "Palo Alto", "Splunk", "ServiceNow GRC"],
          },
          {
            name: "Threat detection & response",
            mappedVendorCapabilities: ["security-management", "incident-management"],
            mappedVendors: ["CrowdStrike", "Palo Alto", "Splunk", "ServiceNow"],
          },
        ],
      },
      {
        name: "Mobility & Resiliency Enablement",
        level3: [
          {
            name: "Seamless session continuity",
            mappedVendorCapabilities: ["business-continuity"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Edge-aware routing",
            mappedVendorCapabilities: ["integration-platform", "monitoring-alerting"],
            mappedVendors: ["AWS", "Azure", "GCP", "Dynatrace"],
          },
          {
            name: "Resiliency testing (chaos)",
            mappedVendorCapabilities: ["automation"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Global failover orchestration",
            mappedVendorCapabilities: ["business-continuity", "automation"],
            mappedVendors: ["AWS", "Azure", "GCP", "Datadog"],
          },
        ],
      },
      {
        name: "Compliance & Audit Automation",
        level3: [
          {
            name: "Evidence collection automation",
            mappedVendorCapabilities: ["audit-compliance", "automation"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "LogicManager"],
          },
          {
            name: "Regulator-ready reporting",
            mappedVendorCapabilities: ["audit-compliance", "reporting-analytics"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream"],
          },
          {
            name: "Data residency enforcement",
            mappedVendorCapabilities: ["compliance-management", "governance-framework"],
            mappedVendors: ["AWS", "Azure", "GCP", "Collibra"],
          },
          {
            name: "Exception management",
            mappedVendorCapabilities: ["compliance-management", "workflow-orchestration"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream", "ServiceNow"],
          },
        ],
      },
      {
        name: "Privacy-by-Design Management",
        level3: [
          {
            name: "Data minimization catalog",
            mappedVendorCapabilities: ["governance-framework", "compliance-management"],
            mappedVendors: ["Collibra", "Alation", "ServiceNow GRC"],
          },
          {
            name: "Consent preference services",
            mappedVendorCapabilities: ["compliance-management"],
            mappedVendors: ["ServiceNow", "ServiceNow GRC"],
          },
          {
            name: "Differential privacy toolkit",
            mappedVendorCapabilities: ["security-management", "compliance-management"],
            mappedVendors: ["AWS", "Azure", "GCP"],
          },
          {
            name: "Privacy impact assessment pipeline",
            mappedVendorCapabilities: ["compliance-management", "audit-compliance"],
            mappedVendors: ["ServiceNow GRC", "Archer", "MetricStream"],
          },
        ],
      },
    ],
  },
];

// ============================================================================
// ANALYSIS FUNCTIONS
// ============================================================================

interface CoverageSummary {
  totalLevel1: number;
  totalLevel2: number;
  totalLevel3: number;
  coveredLevel3: number;
  uncoveredLevel3: number;
  partialCoveredLevel3: number;
}

interface Level3CoverageEntry {
  l1Domain: string;
  l2Capability: string;
  l3Capability: string;
  vendors: string[];
  vendorCount: number;
  coverageStatus: "FULL" | "PARTIAL" | "UNCOVERED";
}

interface Level2CoverageEntry {
  l1Domain: string;
  l2Capability: string;
  totalLevel3: number;
  fullyCovered: number;
  partiallyCovered: number;
  uncovered: number;
}

interface Level1CoverageEntry {
  domain: string;
  level2Capabilities: Array<{
    capability: string;
    level3Capabilities: Array<{
      name: string;
      vendors: string[];
      vendorCount: number;
      coverageStatus: "FULL" | "PARTIAL" | "UNCOVERED";
      mappedVendorCapabilities: string[];
    }>;
    vendorCount: number;
    averageVendors: string;
  }>;
}

interface CoverageAnalysis {
  level1: Level1CoverageEntry[];
  level2: Level2CoverageEntry[];
  level3: Level3CoverageEntry[];
  summary: CoverageSummary;
}

/**
 * Get vendor coverage for the entire custom capability model.
 */
export function analyzeCustomCapabilityCoverage(): CoverageAnalysis {
  const coverage: CoverageAnalysis = {
    level1: [],
    level2: [],
    level3: [],
    summary: {
      totalLevel1: 0,
      totalLevel2: 0,
      totalLevel3: 0,
      coveredLevel3: 0,
      uncoveredLevel3: 0,
      partialCoveredLevel3: 0,
    },
  };

  CUSTOM_CAPABILITY_MODEL.forEach((l1) => {
    coverage.summary.totalLevel1 += 1;

    const l1Analysis: Level1CoverageEntry = {
      domain: l1.name,
      level2Capabilities: [],
    };

    l1.level2.forEach((l2) => {
      coverage.summary.totalLevel2 += 1;

      const l2Analysis = {
        capability: l2.name,
        level3Capabilities: [] as Level1CoverageEntry["level2Capabilities"][number]["level3Capabilities"],
        vendorCount: 0,
        averageVendors: "0.0",
      };

      l2.level3.forEach((l3) => {
        coverage.summary.totalLevel3 += 1;

        const vendors = new Set<string>();

        // Direct vendor mappings
        l3.mappedVendors?.forEach((vendor) => vendors.add(vendor));

        // Capability mappings
        l3.mappedVendorCapabilities.forEach((vendorCapability) => {
          VENDOR_CATALOGUE.forEach((catalogueVendor) => {
            if (catalogueVendor.capabilities.includes(vendorCapability)) {
              vendors.add(catalogueVendor.name);
            }
          });
        });

        const vendorArray = Array.from(vendors);
        const coverageStatus: "FULL" | "PARTIAL" | "UNCOVERED" =
          vendorArray.length === 0
            ? "UNCOVERED"
            : vendorArray.length < 3
            ? "PARTIAL"
            : "FULL";

        if (coverageStatus === "UNCOVERED") {
          coverage.summary.uncoveredLevel3 += 1;
        } else if (coverageStatus === "PARTIAL") {
          coverage.summary.partialCoveredLevel3 += 1;
        } else {
          coverage.summary.coveredLevel3 += 1;
        }

        l2Analysis.level3Capabilities.push({
          name: l3.name,
          vendors: vendorArray,
          vendorCount: vendorArray.length,
          coverageStatus,
          mappedVendorCapabilities: l3.mappedVendorCapabilities,
        });

        coverage.level3.push({
          l1Domain: l1.name,
          l2Capability: l2.name,
          l3Capability: l3.name,
          vendors: vendorArray,
          vendorCount: vendorArray.length,
          coverageStatus,
        });
      });

      l2Analysis.vendorCount = l2Analysis.level3Capabilities.reduce(
        (sum, entry) => sum + entry.vendorCount,
        0,
      );
      l2Analysis.averageVendors = (
        l2Analysis.vendorCount / l2Analysis.level3Capabilities.length
      ).toFixed(1);

      l1Analysis.level2Capabilities.push(l2Analysis);
      coverage.level2.push({
        l1Domain: l1.name,
        l2Capability: l2.name,
        totalLevel3: l2.level3.length,
        fullyCovered: l2Analysis.level3Capabilities.filter((entry) => entry.coverageStatus === "FULL").length,
        partiallyCovered: l2Analysis.level3Capabilities.filter((entry) => entry.coverageStatus === "PARTIAL").length,
        uncovered: l2Analysis.level3Capabilities.filter((entry) => entry.coverageStatus === "UNCOVERED").length,
      });
    });

    coverage.level1.push(l1Analysis);
  });

  return coverage;
}

interface VendorRecommendation {
  vendor: VendorInfo;
  score: number;
  matchedL3Capabilities: string[];
  matchedCount: number;
}

/**
 * Find vendors that best match a specific Level 2 capability.
 */
export function recommendVendorsForL2Capability(
  l1DomainName: string,
  l2CapabilityName: string,
): {
  capability: string;
  recommendedVendors: VendorRecommendation[];
} {
  const l1 = CUSTOM_CAPABILITY_MODEL.find((domain) => domain.name === l1DomainName);
  if (!l1) {
    throw new Error(`Domain not found: ${l1DomainName}`);
  }

  const l2 = l1.level2.find((capability) => capability.name === l2CapabilityName);
  if (!l2) {
    throw new Error(`Capability not found: ${l2CapabilityName}`);
  }

  const vendorScores = new Map<string, { vendor: VendorInfo; matches: string[] }>();

  l2.level3.forEach((l3) => {
    const vendors = new Set<string>();

    l3.mappedVendors?.forEach((vendorName) => vendors.add(vendorName));

    l3.mappedVendorCapabilities.forEach((capabilitySlug) => {
      VENDOR_CATALOGUE.forEach((candidateVendor) => {
        if (candidateVendor.capabilities.includes(capabilitySlug)) {
          vendors.add(candidateVendor.name);
        }
      });
    });

    vendors.forEach((vendorName) => {
      if (!vendorScores.has(vendorName)) {
        const catalogueVendor = VENDOR_CATALOGUE.find((vendor) => vendor.name === vendorName);
        if (catalogueVendor) {
          vendorScores.set(vendorName, { vendor: catalogueVendor, matches: [] });
        }
      }
      vendorScores.get(vendorName)?.matches.push(l3.name);
    });
  });

  const recommended = Array.from(vendorScores.values())
    .map(({ vendor, matches }) => ({
      vendor,
      matchedL3Capabilities: matches,
      matchedCount: matches.length,
      score: (matches.length / l2.level3.length) * 100,
    }))
    .sort((a, b) => b.score - a.score);

  return {
    capability: l2CapabilityName,
    recommendedVendors: recommended,
  };
}

interface VendorCapabilityMatrixEntry {
  vendor: string;
  category: string;
  l1Domains: Record<string, number>;
  l2Capabilities: Record<string, number>;
  totalL3Matches: number;
}

/**
 * Get comprehensive vendor-to-custom-capability mapping.
 */
export function getVendorToCustomCapabilityMatrix(): VendorCapabilityMatrixEntry[] {
  const matrix: Record<string, VendorCapabilityMatrixEntry> = {};

  VENDOR_CATALOGUE.forEach((vendor) => {
    matrix[vendor.id] = {
      vendor: vendor.name,
      category: vendor.category,
      l1Domains: {},
      l2Capabilities: {},
      totalL3Matches: 0,
    };

    CUSTOM_CAPABILITY_MODEL.forEach((l1) => {
      l1.level2.forEach((l2) => {
        l2.level3.forEach((l3) => {
          const matches =
            l3.mappedVendors?.includes(vendor.name) ||
            l3.mappedVendorCapabilities.some((capabilitySlug) => vendor.capabilities.includes(capabilitySlug));

          if (matches) {
            matrix[vendor.id].l1Domains[l1.name] = (matrix[vendor.id].l1Domains[l1.name] || 0) + 1;
            matrix[vendor.id].l2Capabilities[l2.name] = (matrix[vendor.id].l2Capabilities[l2.name] || 0) + 1;
            matrix[vendor.id].totalL3Matches += 1;
          }
        });
      });
    });
  });

  return Object.values(matrix).sort((a, b) => b.totalL3Matches - a.totalL3Matches);
}

interface ExportedCapability {
  id: string;
  name: string;
  category: string;
  level2: string;
  level: string;
  mappedVendorCapabilities: string[];
  mappedVendors: string[];
  description: string;
}

/**
 * Export custom capability model for import into ReqArchitect.
 */
export function exportCapabilityModelForReqArchitect(): ExportedCapability[] {
  const capabilities: ExportedCapability[] = [];
  let idCounter = 1;

  CUSTOM_CAPABILITY_MODEL.forEach((l1) => {
    l1.level2.forEach((l2) => {
      l2.level3.forEach((l3) => {
        capabilities.push({
          id: `cap-custom-${idCounter++}`,
          name: l3.name,
          category: l1.name,
          level2: l2.name,
          level: "advanced",
          mappedVendorCapabilities: l3.mappedVendorCapabilities,
          mappedVendors: l3.mappedVendors || [],
          description: `${l2.name} > ${l3.name}`,
        });
      });
    });
  });

  return capabilities;
}
