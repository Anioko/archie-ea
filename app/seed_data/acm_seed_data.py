"""
ACM (Application Capability Model) Seed Data

Comprehensive technical capability taxonomy with 7 domains:
- USER-EXPERIENCE
- APPLICATION-SERVICES
- DATA-STORAGE
- SECURITY-IDENTITY
- DEVOPS-PLATFORM
- AI-ANALYTICS
- COMMUNICATION

Each domain has L1 - L4 capability levels for detailed architecture mapping.
"""

from typing import Any, Dict, List

# ACM Seed Data Structure
# Format: {domain: {L1 capabilities: {L2 capabilities: {L3 capabilities: [L4 patterns]}}}}

ACM_SEED_DATA: Dict[str, Dict[str, Any]] = {
    "USER-EXPERIENCE": {
        "description": "Frontend interfaces, UI/UX design, accessibility, and user interaction patterns",
        "capabilities": {
            "Web Interfaces": {
                "code": "UX - 01",
                "capabilities": {
                    "Responsive Design": {
                        "code": "UX - 01 - 01",
                        "capabilities": {
                            "Mobile-First Layouts": ["CSS Grid", "Flexbox", "Media Queries"],
                            "Adaptive Components": ["Breakpoint System", "Fluid Typography"],
                            "Cross-Device Compatibility": [
                                "Touch Optimization",
                                "Desktop Fallbacks",
                            ],
                        },
                    },
                    "Single Page Applications": {
                        "code": "UX - 01 - 02",
                        "capabilities": {
                            "Client-Side Routing": ["React Router", "Vue Router", "History API"],
                            "State Management": ["Redux", "Vuex", "MobX", "Zustand"],
                            "Component Architecture": ["Atomic Design", "Compound Components"],
                        },
                    },
                    "Progressive Web Apps": {
                        "code": "UX - 01 - 03",
                        "capabilities": {
                            "Offline Capability": ["Service Workers", "Cache API"],
                            "Push Notifications": ["Web Push API", "Firebase Cloud Messaging"],
                            "App Installation": ["Web App Manifest", "Add to Home Screen"],
                        },
                    },
                },
            },
            "Mobile Applications": {
                "code": "UX - 02",
                "capabilities": {
                    "Native Development": {
                        "code": "UX - 02 - 01",
                        "capabilities": {
                            "iOS Development": ["Swift", "SwiftUI", "UIKit"],
                            "Android Development": ["Kotlin", "Jetpack Compose", "XML Layouts"],
                            "Platform Integration": ["Native APIs", "Hardware Access"],
                        },
                    },
                    "Cross-Platform Development": {
                        "code": "UX - 02 - 02",
                        "capabilities": {
                            "React Native Apps": ["Expo", "React Navigation", "Native Modules"],
                            "Flutter Apps": ["Dart", "Material Design", "Cupertino Widgets"],
                            "Hybrid Apps": ["Ionic", "Capacitor", "Cordova"],
                        },
                    },
                },
            },
            "Accessibility": {
                "code": "UX - 03",
                "capabilities": {
                    "WCAG Compliance": {
                        "code": "UX - 03 - 01",
                        "capabilities": {
                            "Screen Reader Support": [
                                "ARIA Labels",
                                "Semantic HTML",
                                "Focus Management",
                            ],
                            "Keyboard Navigation": ["Tab Order", "Skip Links", "Focus Indicators"],
                            "Color Accessibility": ["Contrast Ratios", "Color Blind Support"],
                        },
                    },
                    "Inclusive Design": {
                        "code": "UX - 03 - 02",
                        "capabilities": {
                            "Cognitive Accessibility": ["Clear Language", "Consistent Navigation"],
                            "Motor Accessibility": ["Large Touch Targets", "Voice Control"],
                        },
                    },
                },
            },
            "Design Systems": {
                "code": "UX - 04",
                "capabilities": {
                    "Component Libraries": {
                        "code": "UX - 04 - 01",
                        "capabilities": {
                            "UI Component Catalogs": ["Storybook", "Bit", "Chromatic"],
                            "Theme Management": ["CSS Variables", "Design Tokens"],
                            "Pattern Documentation": ["Style Guides", "Usage Guidelines"],
                        },
                    },
                },
            },
        },
    },
    "APPLICATION-SERVICES": {
        "description": "Backend services, APIs, business logic, and system integration",
        "capabilities": {
            "API Development": {
                "code": "AS - 01",
                "capabilities": {
                    "RESTful APIs": {
                        "code": "AS - 01 - 01",
                        "capabilities": {
                            "Resource Design": ["URI Patterns", "HTTP Methods", "Status Codes"],
                            "Pagination & Filtering": ["Cursor Pagination", "Query Parameters"],
                            "Versioning": ["URL Versioning", "Header Versioning", "Media Type"],
                        },
                    },
                    "GraphQL APIs": {
                        "code": "AS - 01 - 02",
                        "capabilities": {
                            "Schema Design": ["Types", "Queries", "Mutations", "Subscriptions"],
                            "Resolvers": ["Field Resolvers", "DataLoader", "N + 1 Prevention"],
                            "Federation": ["Apollo Federation", "Schema Stitching"],
                        },
                    },
                    "gRPC Services": {
                        "code": "AS - 01 - 03",
                        "capabilities": {
                            "Protocol Buffers": ["Message Types", "Service Definitions"],
                            "Streaming": ["Unary", "Server Streaming", "Bidirectional"],
                        },
                    },
                },
            },
            "Microservices": {
                "code": "AS - 02",
                "capabilities": {
                    "Service Architecture": {
                        "code": "AS - 02 - 01",
                        "capabilities": {
                            "Domain-Driven Design": ["Bounded Contexts", "Aggregates", "Entities"],
                            "Service Decomposition": ["Strangler Pattern", "Anti-Corruption Layer"],
                            "Service Mesh": ["Istio", "Linkerd", "Consul Connect"],
                        },
                    },
                    "Event-Driven Architecture": {
                        "code": "AS - 02 - 02",
                        "capabilities": {
                            "Event Sourcing": ["Event Store", "Projections", "Snapshots"],
                            "CQRS": ["Command Handlers", "Query Handlers", "Read Models"],
                            "Saga Patterns": ["Choreography", "Orchestration"],
                        },
                    },
                },
            },
            "Business Logic": {
                "code": "AS - 03",
                "capabilities": {
                    "Workflow Engines": {
                        "code": "AS - 03 - 01",
                        "capabilities": {
                            "Process Automation": ["BPMN", "Camunda", "Temporal"],
                            "Rule Engines": ["Drools", "Easy Rules", "Decision Tables"],
                            "State Machines": ["XState", "Spring State Machine"],
                        },
                    },
                    "Validation & Processing": {
                        "code": "AS - 03 - 02",
                        "capabilities": {
                            "Input Validation": ["Schema Validation", "Business Rules"],
                            "Data Transformation": ["ETL Pipelines", "Data Mapping"],
                        },
                    },
                },
            },
            "Integration": {
                "code": "AS - 04",
                "capabilities": {
                    "Enterprise Integration": {
                        "code": "AS - 04 - 01",
                        "capabilities": {
                            "Integration Patterns": ["EIP", "Message Router", "Content Enricher"],
                            "ESB/iPaaS": ["MuleSoft", "Dell Boomi", "Apache Camel"],
                            "B2B Integration": ["EDI", "AS2", "Partner APIs"],
                        },
                    },
                    "API Gateway": {
                        "code": "AS - 04 - 02",
                        "capabilities": {
                            "Traffic Management": [
                                "Rate Limiting",
                                "Load Balancing",
                                "Circuit Breaker",
                            ],
                            "Security": ["OAuth Gateway", "API Keys", "JWT Validation"],
                            "Transformation": ["Request/Response Mapping", "Protocol Translation"],
                        },
                    },
                },
            },
        },
    },
    "DATA-STORAGE": {
        "description": "Databases, data lakes, caching layers, and persistent storage solutions",
        "capabilities": {
            "Relational Databases": {
                "code": "DS - 01",
                "capabilities": {
                    "RDBMS Management": {
                        "code": "DS - 01 - 01",
                        "capabilities": {
                            "Schema Design": ["Normalization", "Denormalization", "Indexing"],
                            "Query Optimization": [
                                "Execution Plans",
                                "Query Tuning",
                                "Partitioning",
                            ],
                            "Transaction Management": [
                                "ACID",
                                "Isolation Levels",
                                "Deadlock Prevention",
                            ],
                        },
                    },
                    "Database Platforms": {
                        "code": "DS - 01 - 02",
                        "capabilities": {
                            "PostgreSQL": ["PL/pgSQL", "Extensions", "Replication"],
                            "MySQL/MariaDB": ["InnoDB", "Replication", "Clustering"],
                            "SQL Server": ["T-SQL", "Always On", "In-Memory OLTP"],
                            "Oracle": ["PL/SQL", "RAC", "Partitioning"],
                        },
                    },
                },
            },
            "NoSQL Databases": {
                "code": "DS - 02",
                "capabilities": {
                    "Document Stores": {
                        "code": "DS - 02 - 01",
                        "capabilities": {
                            "MongoDB": ["Aggregation Pipeline", "Sharding", "Atlas"],
                            "Couchbase": ["N1QL", "Mobile Sync", "Full-Text Search"],
                        },
                    },
                    "Key-Value Stores": {
                        "code": "DS - 02 - 02",
                        "capabilities": {
                            "Redis": ["Data Structures", "Pub/Sub", "Clustering"],
                            "DynamoDB": ["Single-Table Design", "Global Tables", "Streams"],
                        },
                    },
                    "Graph Databases": {
                        "code": "DS - 02 - 03",
                        "capabilities": {
                            "Neo4j": ["Cypher", "Graph Algorithms", "Clustering"],
                            "Amazon Neptune": ["Gremlin", "SPARQL", "Serverless"],
                        },
                    },
                    "Time Series": {
                        "code": "DS - 02 - 04",
                        "capabilities": {
                            "InfluxDB": ["Flux", "Continuous Queries", "Retention Policies"],
                            "TimescaleDB": ["Hypertables", "Compression", "Aggregation"],
                        },
                    },
                },
            },
            "Data Lakes & Warehouses": {
                "code": "DS - 03",
                "capabilities": {
                    "Cloud Data Platforms": {
                        "code": "DS - 03 - 01",
                        "capabilities": {
                            "Snowflake": ["Virtual Warehouses", "Data Sharing", "Time Travel"],
                            "Databricks": ["Delta Lake", "Unity Catalog", "Lakehouse"],
                            "BigQuery": ["Partitioning", "Clustering", "ML Integration"],
                        },
                    },
                    "Data Lake Architecture": {
                        "code": "DS - 03 - 02",
                        "capabilities": {
                            "Medallion Architecture": ["Bronze/Silver/Gold", "Data Quality Tiers"],
                            "Data Catalog": ["Metadata Management", "Data Discovery"],
                        },
                    },
                },
            },
            "Caching": {
                "code": "DS - 04",
                "capabilities": {
                    "Distributed Caching": {
                        "code": "DS - 04 - 01",
                        "capabilities": {
                            "In-Memory Cache": ["Redis Cache", "Memcached", "Hazelcast"],
                            "CDN Caching": ["CloudFront", "Cloudflare", "Akamai"],
                            "Application Cache": ["Local Cache", "Cache Invalidation Patterns"],
                        },
                    },
                },
            },
            "File Storage": {
                "code": "DS - 05",
                "capabilities": {
                    "Object Storage": {
                        "code": "DS - 05 - 01",
                        "capabilities": {
                            "Cloud Object Storage": ["S3", "Azure Blob", "GCS"],
                            "Lifecycle Management": ["Tiering", "Retention", "Versioning"],
                        },
                    },
                    "File Systems": {
                        "code": "DS - 05 - 02",
                        "capabilities": {
                            "Distributed File Systems": ["HDFS", "EFS", "Azure Files"],
                            "Block Storage": ["EBS", "Azure Disks", "Persistent Volumes"],
                        },
                    },
                },
            },
        },
    },
    "SECURITY-IDENTITY": {
        "description": "Authentication, authorization, encryption, and security compliance",
        "capabilities": {
            "Authentication": {
                "code": "SI - 01",
                "capabilities": {
                    "Identity Providers": {
                        "code": "SI - 01 - 01",
                        "capabilities": {
                            "Enterprise IdP": ["Azure AD", "Okta", "Ping Identity"],
                            "Social Login": ["OAuth 2.0", "OpenID Connect", "SAML"],
                            "Passwordless": ["WebAuthn", "FIDO2", "Magic Links"],
                        },
                    },
                    "Multi-Factor Authentication": {
                        "code": "SI - 01 - 02",
                        "capabilities": {
                            "MFA Methods": ["TOTP", "Push Notifications", "Hardware Keys"],
                            "Adaptive Authentication": ["Risk-Based Auth", "Behavioral Analysis"],
                        },
                    },
                },
            },
            "Authorization": {
                "code": "SI - 02",
                "capabilities": {
                    "Access Control": {
                        "code": "SI - 02 - 01",
                        "capabilities": {
                            "RBAC": ["Role Definitions", "Permission Sets", "Role Hierarchies"],
                            "ABAC": ["Attribute Policies", "Dynamic Rules", "Context-Aware Access"],
                            "Policy Engines": ["OPA", "Cedar", "Casbin"],
                        },
                    },
                    "API Security": {
                        "code": "SI - 02 - 02",
                        "capabilities": {
                            "Token Management": ["JWT", "OAuth Tokens", "Token Refresh"],
                            "API Keys": ["Key Rotation", "Scoped Access", "Rate Limiting"],
                        },
                    },
                },
            },
            "Encryption": {
                "code": "SI - 03",
                "capabilities": {
                    "Data Encryption": {
                        "code": "SI - 03 - 01",
                        "capabilities": {
                            "At-Rest Encryption": ["AES - 256", "Database TDE", "File Encryption"],
                            "In-Transit Encryption": ["TLS 1.3", "mTLS", "Certificate Management"],
                            "Key Management": ["KMS", "HSM", "Key Rotation"],
                        },
                    },
                    "Secrets Management": {
                        "code": "SI - 03 - 02",
                        "capabilities": {
                            "Vault Solutions": [
                                "HashiCorp Vault",
                                "AWS Secrets Manager",
                                "Azure Key Vault",
                            ],
                            "Secret Injection": ["Environment Variables", "Sidecar Injection"],
                        },
                    },
                },
            },
            "Security Operations": {
                "code": "SI - 04",
                "capabilities": {
                    "Threat Detection": {
                        "code": "SI - 04 - 01",
                        "capabilities": {
                            "SIEM": ["Splunk", "Sentinel", "Elastic Security"],
                            "Intrusion Detection": [
                                "Network IDS",
                                "Host IDS",
                                "Behavioral Analysis",
                            ],
                        },
                    },
                    "Vulnerability Management": {
                        "code": "SI - 04 - 02",
                        "capabilities": {
                            "Scanning": ["SAST", "DAST", "SCA", "Container Scanning"],
                            "Penetration Testing": ["Automated Pentesting", "Bug Bounty"],
                        },
                    },
                },
            },
            "Compliance": {
                "code": "SI - 05",
                "capabilities": {
                    "Regulatory Compliance": {
                        "code": "SI - 05 - 01",
                        "capabilities": {
                            "Data Privacy": ["GDPR", "CCPA", "Data Residency"],
                            "Industry Standards": ["PCI-DSS", "HIPAA", "SOC 2"],
                            "Audit Logging": [
                                "Immutable Logs",
                                "Audit Trails",
                                "Compliance Reports",
                            ],
                        },
                    },
                },
            },
        },
    },
    "DEVOPS-PLATFORM": {
        "description": "CI/CD pipelines, infrastructure, monitoring, and platform operations",
        "capabilities": {
            "CI/CD Pipelines": {
                "code": "DP - 01",
                "capabilities": {
                    "Continuous Integration": {
                        "code": "DP - 01 - 01",
                        "capabilities": {
                            "Build Automation": ["Maven", "Gradle", "npm/yarn", "Docker Build"],
                            "Testing Automation": ["Unit Tests", "Integration Tests", "E2E Tests"],
                            "Code Quality": ["Linting", "Static Analysis", "Code Coverage"],
                        },
                    },
                    "Continuous Deployment": {
                        "code": "DP - 01 - 02",
                        "capabilities": {
                            "Deployment Strategies": ["Blue-Green", "Canary", "Rolling"],
                            "GitOps": ["ArgoCD", "Flux", "Jenkins X"],
                            "Release Management": ["Feature Flags", "Progressive Rollout"],
                        },
                    },
                    "Pipeline Platforms": {
                        "code": "DP - 01 - 03",
                        "capabilities": {
                            "CI/CD Tools": [
                                "GitHub Actions",
                                "GitLab CI",
                                "Jenkins",
                                "Azure DevOps",
                            ],
                            "Artifact Management": ["Nexus", "Artifactory", "Container Registry"],
                        },
                    },
                },
            },
            "Infrastructure": {
                "code": "DP - 02",
                "capabilities": {
                    "Infrastructure as Code": {
                        "code": "DP - 02 - 01",
                        "capabilities": {
                            "Provisioning": ["Terraform", "Pulumi", "CloudFormation"],
                            "Configuration Management": ["Ansible", "Chef", "Puppet"],
                            "Policy as Code": ["Sentinel", "OPA", "Checkov"],
                        },
                    },
                    "Container Orchestration": {
                        "code": "DP - 02 - 02",
                        "capabilities": {
                            "Kubernetes": ["Deployments", "Services", "Ingress", "Operators"],
                            "Container Platforms": ["OpenShift", "EKS", "AKS", "GKE"],
                            "Service Mesh": ["Istio", "Linkerd", "Consul"],
                        },
                    },
                    "Serverless": {
                        "code": "DP - 02 - 03",
                        "capabilities": {
                            "FaaS": ["Lambda", "Azure Functions", "Cloud Functions"],
                            "Serverless Frameworks": ["Serverless Framework", "SAM", "Knative"],
                        },
                    },
                },
            },
            "Observability": {
                "code": "DP - 03",
                "capabilities": {
                    "Monitoring": {
                        "code": "DP - 03 - 01",
                        "capabilities": {
                            "Metrics Collection": ["Prometheus", "Datadog", "New Relic"],
                            "Dashboards": ["Grafana", "Kibana", "Custom Dashboards"],
                            "Alerting": ["PagerDuty", "OpsGenie", "Alert Rules"],
                        },
                    },
                    "Logging": {
                        "code": "DP - 03 - 02",
                        "capabilities": {
                            "Log Aggregation": ["ELK Stack", "Loki", "Splunk"],
                            "Log Analysis": ["Log Parsing", "Pattern Detection", "Correlation"],
                        },
                    },
                    "Tracing": {
                        "code": "DP - 03 - 03",
                        "capabilities": {
                            "Distributed Tracing": ["Jaeger", "Zipkin", "OpenTelemetry"],
                            "APM": ["Dynatrace", "AppDynamics", "Elastic APM"],
                        },
                    },
                },
            },
            "Reliability": {
                "code": "DP - 04",
                "capabilities": {
                    "SRE Practices": {
                        "code": "DP - 04 - 01",
                        "capabilities": {
                            "SLOs/SLIs": ["Error Budgets", "Latency Targets", "Availability SLAs"],
                            "Incident Management": ["On-Call", "Runbooks", "Postmortems"],
                            "Chaos Engineering": ["Chaos Monkey", "Gremlin", "Litmus"],
                        },
                    },
                    "Disaster Recovery": {
                        "code": "DP - 04 - 02",
                        "capabilities": {
                            "Backup & Restore": ["Automated Backups", "Point-in-Time Recovery"],
                            "Failover": ["Active-Passive", "Active-Active", "Multi-Region"],
                        },
                    },
                },
            },
        },
    },
    "AI-ANALYTICS": {
        "description": "Machine learning, business intelligence, analytics, and data science",
        "capabilities": {
            "Machine Learning": {
                "code": "AA - 01",
                "capabilities": {
                    "ML Development": {
                        "code": "AA - 01 - 01",
                        "capabilities": {
                            "Model Training": [
                                "Supervised Learning",
                                "Unsupervised Learning",
                                "Reinforcement Learning",
                            ],
                            "Feature Engineering": [
                                "Feature Stores",
                                "Feature Pipelines",
                                "Embedding",
                            ],
                            "Model Evaluation": ["Cross-Validation", "A/B Testing", "Metrics"],
                        },
                    },
                    "MLOps": {
                        "code": "AA - 01 - 02",
                        "capabilities": {
                            "Model Deployment": [
                                "Model Serving",
                                "Batch Inference",
                                "Real-Time Inference",
                            ],
                            "Model Monitoring": ["Drift Detection", "Performance Tracking"],
                            "ML Pipelines": ["Kubeflow", "MLflow", "SageMaker Pipelines"],
                        },
                    },
                    "ML Platforms": {
                        "code": "AA - 01 - 03",
                        "capabilities": {
                            "Cloud ML": ["SageMaker", "Azure ML", "Vertex AI"],
                            "AutoML": ["AutoML Tables", "H2O", "DataRobot"],
                        },
                    },
                },
            },
            "Generative AI": {
                "code": "AA - 02",
                "capabilities": {
                    "LLM Integration": {
                        "code": "AA - 02 - 01",
                        "capabilities": {
                            "LLM APIs": [
                                "OpenAI",
                                "Anthropic Claude",
                                "Google Gemini",
                                "Azure OpenAI",
                            ],
                            "Prompt Engineering": ["Few-Shot", "Chain-of-Thought", "RAG"],
                            "Fine-Tuning": ["LoRA", "PEFT", "Domain Adaptation"],
                        },
                    },
                    "AI Agents": {
                        "code": "AA - 02 - 02",
                        "capabilities": {
                            "Autonomous Agents": ["LangChain Agents", "AutoGPT", "CrewAI"],
                            "Tool Use": ["Function Calling", "Plugin Architecture"],
                        },
                    },
                },
            },
            "Business Intelligence": {
                "code": "AA - 03",
                "capabilities": {
                    "BI Platforms": {
                        "code": "AA - 03 - 01",
                        "capabilities": {
                            "Visualization Tools": ["Tableau", "Power BI", "Looker", "Metabase"],
                            "Self-Service BI": ["Ad-Hoc Reporting", "Dashboard Builder"],
                            "Embedded Analytics": ["Embedded Dashboards", "White-Label Analytics"],
                        },
                    },
                    "Data Analysis": {
                        "code": "AA - 03 - 02",
                        "capabilities": {
                            "Statistical Analysis": [
                                "Descriptive Stats",
                                "Inferential Stats",
                                "Regression",
                            ],
                            "Predictive Analytics": [
                                "Forecasting",
                                "Trend Analysis",
                                "Anomaly Detection",
                            ],
                        },
                    },
                },
            },
            "Data Science": {
                "code": "AA - 04",
                "capabilities": {
                    "Data Exploration": {
                        "code": "AA - 04 - 01",
                        "capabilities": {
                            "Notebooks": ["Jupyter", "Databricks Notebooks", "Colab"],
                            "Data Profiling": ["Data Quality", "Distribution Analysis"],
                        },
                    },
                    "Advanced Analytics": {
                        "code": "AA - 04 - 02",
                        "capabilities": {
                            "Deep Learning": ["TensorFlow", "PyTorch", "Neural Networks"],
                            "NLP": ["Text Classification", "NER", "Sentiment Analysis"],
                            "Computer Vision": ["Image Classification", "Object Detection", "OCR"],
                        },
                    },
                },
            },
        },
    },
    "COMMUNICATION": {
        "description": "Messaging, notifications, real-time communication, and collaboration tools",
        "capabilities": {
            "Messaging": {
                "code": "CM - 01",
                "capabilities": {
                    "Message Queues": {
                        "code": "CM - 01 - 01",
                        "capabilities": {
                            "Queue Systems": ["RabbitMQ", "Amazon SQS", "Azure Service Bus"],
                            "Message Patterns": ["Point-to-Point", "Pub/Sub", "Request-Reply"],
                            "Dead Letter Handling": ["DLQ", "Retry Policies", "Error Handling"],
                        },
                    },
                    "Event Streaming": {
                        "code": "CM - 01 - 02",
                        "capabilities": {
                            "Streaming Platforms": [
                                "Apache Kafka",
                                "Amazon Kinesis",
                                "Azure Event Hubs",
                            ],
                            "Stream Processing": ["Kafka Streams", "Flink", "Spark Streaming"],
                        },
                    },
                },
            },
            "Notifications": {
                "code": "CM - 02",
                "capabilities": {
                    "Push Notifications": {
                        "code": "CM - 02 - 01",
                        "capabilities": {
                            "Mobile Push": ["FCM", "APNs", "OneSignal"],
                            "Web Push": ["Service Workers", "Push API"],
                            "Desktop Notifications": ["Electron Notifications", "System Tray"],
                        },
                    },
                    "Multi-Channel Notifications": {
                        "code": "CM - 02 - 02",
                        "capabilities": {
                            "Email Delivery": ["SendGrid", "SES", "Mailgun"],
                            "SMS/Voice": ["Twilio", "Vonage", "AWS SNS"],
                            "Notification Hub": ["Notification Center", "Preference Management"],
                        },
                    },
                },
            },
            "Real-Time Communication": {
                "code": "CM - 03",
                "capabilities": {
                    "WebSocket": {
                        "code": "CM - 03 - 01",
                        "capabilities": {
                            "WebSocket Servers": ["Socket.io", "SignalR", "ws"],
                            "Real-Time Sync": ["Presence", "Typing Indicators", "Live Updates"],
                        },
                    },
                    "Video/Voice": {
                        "code": "CM - 03 - 02",
                        "capabilities": {
                            "WebRTC": ["Peer-to-Peer", "SFU", "MCU"],
                            "Video Platforms": ["Twilio Video", "Vonage Video", "Daily.co"],
                        },
                    },
                },
            },
            "Collaboration": {
                "code": "CM - 04",
                "capabilities": {
                    "Team Communication": {
                        "code": "CM - 04 - 01",
                        "capabilities": {
                            "Chat Integration": ["Slack API", "Teams API", "Discord API"],
                            "Bots & Automation": ["Chatbots", "Workflow Automation"],
                        },
                    },
                    "Document Collaboration": {
                        "code": "CM - 04 - 02",
                        "capabilities": {
                            "Real-Time Editing": ["Operational Transformation", "CRDT"],
                            "Version Control": ["Document History", "Change Tracking"],
                        },
                    },
                },
            },
        },
    },
}


DOMAIN_CODE_MAP = {
    "USER-EXPERIENCE": "UX",
    "APPLICATION-SERVICES": "AS",
    "DATA-STORAGE": "DS",
    "SECURITY-IDENTITY": "SI",
    "DEVOPS-PLATFORM": "DP",
    "AI-ANALYTICS": "AA",
    "COMMUNICATION": "CM",
}


def get_flat_capabilities() -> List[Dict[str, Any]]:
    """
    Convert hierarchical ACM data to flat list of capabilities for database seeding.
    Returns list of capability dictionaries ready for TechnicalCapability model.
    """
    capabilities = []

    for domain, domain_data in ACM_SEED_DATA.items():
        domain_code = DOMAIN_CODE_MAP.get(domain, domain[:2])

        # Add L0 domain as root capability
        domain_cap = {
            "name": domain.replace("-", " ").title(),
            "code": domain_code,
            "description": domain_data["description"],
            "acm_domain": domain,
            "level": "L0",
            "level_number": 0,
            "parent_code": None,
            "capability_type": "domain",
            "is_foundational": True,
        }
        capabilities.append(domain_cap)

        for l1_name, l1_data in domain_data.get("capabilities", {}).items():
            l1_code = l1_data.get("code", "")
            l1_cap = {
                "name": l1_name,
                "code": l1_code,
                "description": f"{l1_name} capabilities for {domain}",
                "acm_domain": domain,
                "level": "L1",
                "level_number": 1,
                "parent_code": domain_code,
                "capability_type": "capability_area",
                "is_foundational": False,
            }
            capabilities.append(l1_cap)

            for l2_name, l2_data in l1_data.get("capabilities", {}).items():
                l2_code = l2_data.get("code", "")
                l2_cap = {
                    "name": l2_name,
                    "code": l2_code,
                    "description": f"{l2_name} - {l1_name}",
                    "acm_domain": domain,
                    "level": "L2",
                    "level_number": 2,
                    "parent_code": l1_code,
                    "capability_type": "capability_group",
                    "is_foundational": False,
                }
                capabilities.append(l2_cap)

                for l3_name, l4_patterns in l2_data.get("capabilities", {}).items():
                    l3_code = f"{l2_code}-{len([c for c in capabilities if c.get('parent_code') == l2_code]) + 1:02d}"
                    l3_cap = {
                        "name": l3_name,
                        "code": l3_code,
                        "description": f"{l3_name} - {l2_name}",
                        "acm_domain": domain,
                        "level": "L3",
                        "level_number": 3,
                        "parent_code": l2_code,
                        "capability_type": "specific_capability",
                        "is_foundational": False,
                        "technology_patterns": l4_patterns if isinstance(l4_patterns, list) else [],
                    }
                    capabilities.append(l3_cap)

    return capabilities


def get_domain_list() -> List[Dict[str, str]]:
    """Get list of ACM domains with descriptions."""
    return [
        {
            "code": domain,
            "name": domain.replace("-", " ").title(),
            "description": data["description"],
        }
        for domain, data in ACM_SEED_DATA.items()
    ]
