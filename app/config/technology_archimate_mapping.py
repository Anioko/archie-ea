"""
Technology to ArchiMate Mapping Configuration

This module provides comprehensive mappings from technology keywords to ArchiMate
Technology Layer elements. It enables automatic derivation of ArchiMate technology
elements from application technology stacks, vendor products, and infrastructure
descriptions.

ArchiMate Technology Layer Elements used:
- Node: Computational or physical resource (servers, VMs, containers, cloud instances)
- SystemSoftware: Software that provides execution environment (OS, databases, runtimes)
- TechnologyInterface: Point of access for technology services (APIs, protocols)
- TechnologyService: Externally visible unit of functionality (cloud services)
- Artifact: Piece of data used/produced (deployable packages, files)
- CommunicationNetwork: Set of structures connecting nodes (networks, VPNs)
- Device: Physical IT resource (hardware devices)
- Path: Link between nodes for communication
- TechnologyFunction: Internal behavior of a node
- TechnologyProcess: Sequence of technology behaviors
- TechnologyInteraction: Unit of joint technology behavior
- TechnologyCollaboration: Aggregate of nodes for joint functionality
- TechnologyEvent: Technology state change

Phase 4.1 of APQC to ArchiMate derivation system.
"""

import re
from typing import Any, Dict, List, Optional

# =============================================================================
# TECHNOLOGY KEYWORD TO ARCHIMATE MAPPING
# =============================================================================

TECHNOLOGY_KEYWORD_MAP: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # CLOUD PLATFORMS → Node (cloud infrastructure)
    # -------------------------------------------------------------------------
    "aws": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Amazon Web Services",
        "description": "Amazon Web Services cloud computing platform",
    },
    "amazon web services": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Amazon Web Services",
        "description": "Amazon Web Services cloud computing platform",
    },
    "azure": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Microsoft",
        "description": "Microsoft Azure cloud computing platform",
    },
    "microsoft azure": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Microsoft",
        "description": "Microsoft Azure cloud computing platform",
    },
    "gcp": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Google",
        "description": "Google Cloud Platform",
    },
    "google cloud": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Google",
        "description": "Google Cloud Platform",
    },
    "google cloud platform": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Google",
        "description": "Google Cloud Platform",
    },
    "ibm cloud": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "IBM",
        "description": "IBM Cloud computing platform",
    },
    "oracle cloud": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Oracle",
        "description": "Oracle Cloud Infrastructure",
    },
    "oci": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Oracle",
        "description": "Oracle Cloud Infrastructure",
    },
    "alibaba cloud": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "Alibaba",
        "description": "Alibaba Cloud computing platform",
    },
    "digitalocean": {
        "element_type": "Node",
        "subtype": "cloud_platform",
        "vendor": "DigitalOcean",
        "description": "DigitalOcean cloud platform",
    },
    "heroku": {
        "element_type": "Node",
        "subtype": "cloud_paas",
        "vendor": "Salesforce",
        "description": "Heroku Platform as a Service",
    },
    "cloudflare": {
        "element_type": "Node",
        "subtype": "cloud_cdn",
        "vendor": "Cloudflare",
        "description": "Cloudflare CDN and edge platform",
    },
    # -------------------------------------------------------------------------
    # CLOUD SERVICES → TechnologyService
    # -------------------------------------------------------------------------
    "ec2": {
        "element_type": "TechnologyService",
        "subtype": "compute_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Elastic Compute Cloud",
    },
    "s3": {
        "element_type": "TechnologyService",
        "subtype": "storage_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Simple Storage Service",
    },
    "lambda": {
        "element_type": "TechnologyService",
        "subtype": "serverless",
        "vendor": "Amazon Web Services",
        "description": "AWS Lambda serverless compute",
    },
    "azure functions": {
        "element_type": "TechnologyService",
        "subtype": "serverless",
        "vendor": "Microsoft",
        "description": "Azure Functions serverless compute",
    },
    "cloud functions": {
        "element_type": "TechnologyService",
        "subtype": "serverless",
        "vendor": "Google",
        "description": "Google Cloud Functions serverless compute",
    },
    "rds": {
        "element_type": "TechnologyService",
        "subtype": "managed_database",
        "vendor": "Amazon Web Services",
        "description": "Amazon Relational Database Service",
    },
    "dynamodb": {
        "element_type": "TechnologyService",
        "subtype": "nosql_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon DynamoDB NoSQL database service",
    },
    "cosmos db": {
        "element_type": "TechnologyService",
        "subtype": "nosql_service",
        "vendor": "Microsoft",
        "description": "Azure Cosmos DB multi-model database",
    },
    "cloud sql": {
        "element_type": "TechnologyService",
        "subtype": "managed_database",
        "vendor": "Google",
        "description": "Google Cloud SQL managed database",
    },
    # -------------------------------------------------------------------------
    # DATABASES → SystemSoftware
    # -------------------------------------------------------------------------
    "oracle": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Oracle",
        "category": "relational",
        "description": "Oracle Database",
    },
    "oracle database": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Oracle",
        "category": "relational",
        "description": "Oracle Database",
    },
    "sql server": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Microsoft",
        "category": "relational",
        "description": "Microsoft SQL Server",
    },
    "mssql": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Microsoft",
        "category": "relational",
        "description": "Microsoft SQL Server",
    },
    "postgresql": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "PostgreSQL Global Development Group",
        "category": "relational",
        "description": "PostgreSQL open-source database",
    },
    "postgres": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "PostgreSQL Global Development Group",
        "category": "relational",
        "description": "PostgreSQL open-source database",
    },
    "mysql": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Oracle",
        "category": "relational",
        "description": "MySQL database",
    },
    "mariadb": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "MariaDB Foundation",
        "category": "relational",
        "description": "MariaDB database",
    },
    "mongodb": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "MongoDB Inc",
        "category": "nosql_document",
        "description": "MongoDB document database",
    },
    "redis": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Redis Ltd",
        "category": "nosql_keyvalue",
        "description": "Redis in-memory data store",
    },
    "cassandra": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Apache",
        "category": "nosql_columnar",
        "description": "Apache Cassandra distributed database",
    },
    "elasticsearch": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Elastic",
        "category": "search_engine",
        "description": "Elasticsearch search and analytics engine",
    },
    "couchdb": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Apache",
        "category": "nosql_document",
        "description": "Apache CouchDB document database",
    },
    "neo4j": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Neo4j Inc",
        "category": "graph",
        "description": "Neo4j graph database",
    },
    "db2": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "IBM",
        "category": "relational",
        "description": "IBM Db2 database",
    },
    "sqlite": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "SQLite Consortium",
        "category": "embedded",
        "description": "SQLite embedded database",
    },
    "memcached": {
        "element_type": "SystemSoftware",
        "subtype": "cache",
        "vendor": "Open Source",
        "category": "cache",
        "description": "Memcached distributed memory caching",
    },
    "influxdb": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "InfluxData",
        "category": "timeseries",
        "description": "InfluxDB time series database",
    },
    "snowflake": {
        "element_type": "SystemSoftware",
        "subtype": "database",
        "vendor": "Snowflake Inc",
        "category": "data_warehouse",
        "description": "Snowflake cloud data warehouse",
    },
    # -------------------------------------------------------------------------
    # CONTAINER & ORCHESTRATION → Node / SystemSoftware
    # -------------------------------------------------------------------------
    "kubernetes": {
        "element_type": "Node",
        "subtype": "container_orchestration",
        "vendor": "CNCF",
        "description": "Kubernetes container orchestration",
    },
    "k8s": {
        "element_type": "Node",
        "subtype": "container_orchestration",
        "vendor": "CNCF",
        "description": "Kubernetes container orchestration",
    },
    "docker": {
        "element_type": "SystemSoftware",
        "subtype": "container_runtime",
        "vendor": "Docker Inc",
        "description": "Docker container platform",
    },
    "openshift": {
        "element_type": "Node",
        "subtype": "container_platform",
        "vendor": "Red Hat",
        "description": "Red Hat OpenShift container platform",
    },
    "ecs": {
        "element_type": "TechnologyService",
        "subtype": "container_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Elastic Container Service",
    },
    "eks": {
        "element_type": "TechnologyService",
        "subtype": "managed_kubernetes",
        "vendor": "Amazon Web Services",
        "description": "Amazon Elastic Kubernetes Service",
    },
    "aks": {
        "element_type": "TechnologyService",
        "subtype": "managed_kubernetes",
        "vendor": "Microsoft",
        "description": "Azure Kubernetes Service",
    },
    "gke": {
        "element_type": "TechnologyService",
        "subtype": "managed_kubernetes",
        "vendor": "Google",
        "description": "Google Kubernetes Engine",
    },
    "podman": {
        "element_type": "SystemSoftware",
        "subtype": "container_runtime",
        "vendor": "Red Hat",
        "description": "Podman container engine",
    },
    "containerd": {
        "element_type": "SystemSoftware",
        "subtype": "container_runtime",
        "vendor": "CNCF",
        "description": "containerd container runtime",
    },
    "rancher": {
        "element_type": "SystemSoftware",
        "subtype": "container_management",
        "vendor": "SUSE",
        "description": "Rancher Kubernetes management platform",
    },
    "docker swarm": {
        "element_type": "Node",
        "subtype": "container_orchestration",
        "vendor": "Docker Inc",
        "description": "Docker Swarm container orchestration",
    },
    # -------------------------------------------------------------------------
    # WEB SERVERS → SystemSoftware
    # -------------------------------------------------------------------------
    "apache": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "Apache",
        "description": "Apache HTTP Server",
    },
    "apache httpd": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "Apache",
        "description": "Apache HTTP Server",
    },
    "nginx": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "F5/NGINX",
        "description": "NGINX web server",
    },
    "iis": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "Microsoft",
        "description": "Internet Information Services",
    },
    "lighttpd": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "Open Source",
        "description": "lighttpd web server",
    },
    "caddy": {
        "element_type": "SystemSoftware",
        "subtype": "web_server",
        "vendor": "Open Source",
        "description": "Caddy web server",
    },
    "traefik": {
        "element_type": "SystemSoftware",
        "subtype": "reverse_proxy",
        "vendor": "Traefik Labs",
        "description": "Traefik edge router",
    },
    "haproxy": {
        "element_type": "SystemSoftware",
        "subtype": "load_balancer",
        "vendor": "HAProxy Technologies",
        "description": "HAProxy load balancer",
    },
    # -------------------------------------------------------------------------
    # APPLICATION SERVERS → SystemSoftware
    # -------------------------------------------------------------------------
    "tomcat": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Apache",
        "description": "Apache Tomcat application server",
    },
    "apache tomcat": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Apache",
        "description": "Apache Tomcat application server",
    },
    "websphere": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "IBM",
        "description": "IBM WebSphere Application Server",
    },
    "weblogic": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Oracle",
        "description": "Oracle WebLogic Server",
    },
    "jboss": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Red Hat",
        "description": "JBoss/WildFly Application Server",
    },
    "wildfly": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Red Hat",
        "description": "WildFly Application Server",
    },
    "glassfish": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Eclipse Foundation",
        "description": "GlassFish application server",
    },
    "jetty": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Eclipse Foundation",
        "description": "Eclipse Jetty server",
    },
    "undertow": {
        "element_type": "SystemSoftware",
        "subtype": "application_server",
        "vendor": "Red Hat",
        "description": "Undertow web server",
    },
    # -------------------------------------------------------------------------
    # MESSAGE QUEUES & STREAMING → SystemSoftware
    # -------------------------------------------------------------------------
    "kafka": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "Apache",
        "category": "streaming",
        "description": "Apache Kafka streaming platform",
    },
    "apache kafka": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "Apache",
        "category": "streaming",
        "description": "Apache Kafka streaming platform",
    },
    "rabbitmq": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "VMware",
        "category": "message_queue",
        "description": "RabbitMQ message broker",
    },
    "activemq": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "Apache",
        "category": "message_queue",
        "description": "Apache ActiveMQ message broker",
    },
    "sqs": {
        "element_type": "TechnologyService",
        "subtype": "message_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Simple Queue Service",
    },
    "sns": {
        "element_type": "TechnologyService",
        "subtype": "notification_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Simple Notification Service",
    },
    "azure service bus": {
        "element_type": "TechnologyService",
        "subtype": "message_service",
        "vendor": "Microsoft",
        "description": "Azure Service Bus",
    },
    "pubsub": {
        "element_type": "TechnologyService",
        "subtype": "message_service",
        "vendor": "Google",
        "description": "Google Cloud Pub/Sub",
    },
    "pulsar": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "Apache",
        "category": "streaming",
        "description": "Apache Pulsar messaging",
    },
    "zeromq": {
        "element_type": "SystemSoftware",
        "subtype": "message_library",
        "vendor": "Open Source",
        "description": "ZeroMQ messaging library",
    },
    "nats": {
        "element_type": "SystemSoftware",
        "subtype": "message_broker",
        "vendor": "Synadia",
        "description": "NATS messaging system",
    },
    # -------------------------------------------------------------------------
    # API TYPES → TechnologyInterface
    # -------------------------------------------------------------------------
    "rest": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "REST",
        "description": "RESTful API interface",
    },
    "rest api": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "REST",
        "description": "RESTful API interface",
    },
    "restful": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "REST",
        "description": "RESTful API interface",
    },
    "graphql": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "GraphQL",
        "description": "GraphQL API interface",
    },
    "soap": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "SOAP",
        "description": "SOAP web service interface",
    },
    "grpc": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "gRPC",
        "description": "gRPC remote procedure call",
    },
    "websocket": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "WebSocket",
        "description": "WebSocket bidirectional protocol",
    },
    "odata": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "OData",
        "description": "OData protocol interface",
    },
    "json-rpc": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "JSON-RPC",
        "description": "JSON-RPC protocol",
    },
    "xml-rpc": {
        "element_type": "TechnologyInterface",
        "subtype": "api",
        "protocol": "XML-RPC",
        "description": "XML-RPC protocol",
    },
    # -------------------------------------------------------------------------
    # PROGRAMMING RUNTIMES → SystemSoftware
    # -------------------------------------------------------------------------
    "java": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Oracle/OpenJDK",
        "description": "Java Runtime Environment",
    },
    "jvm": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Oracle/OpenJDK",
        "description": "Java Virtual Machine",
    },
    "jre": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Oracle/OpenJDK",
        "description": "Java Runtime Environment",
    },
    ".net": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Microsoft",
        "description": ".NET Runtime",
    },
    "dotnet": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Microsoft",
        "description": ".NET Runtime",
    },
    ".net core": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Microsoft",
        "description": ".NET Core Runtime",
    },
    ".net framework": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Microsoft",
        "description": ".NET Framework",
    },
    "node.js": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "OpenJS Foundation",
        "description": "Node.js JavaScript runtime",
    },
    "nodejs": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "OpenJS Foundation",
        "description": "Node.js JavaScript runtime",
    },
    "node": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "OpenJS Foundation",
        "description": "Node.js JavaScript runtime",
    },
    "python": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Python Software Foundation",
        "description": "Python runtime",
    },
    "ruby": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Ruby Community",
        "description": "Ruby runtime",
    },
    "php": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "PHP Group",
        "description": "PHP runtime",
    },
    "go": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Google",
        "description": "Go runtime",
    },
    "golang": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Google",
        "description": "Go runtime",
    },
    "rust": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Rust Foundation",
        "description": "Rust runtime",
    },
    "scala": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Lightbend",
        "description": "Scala runtime (JVM-based)",
    },
    "kotlin": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "JetBrains",
        "description": "Kotlin runtime (JVM-based)",
    },
    "deno": {
        "element_type": "SystemSoftware",
        "subtype": "runtime",
        "vendor": "Deno Land",
        "description": "Deno JavaScript/TypeScript runtime",
    },
    # -------------------------------------------------------------------------
    # OPERATING SYSTEMS → SystemSoftware
    # -------------------------------------------------------------------------
    "linux": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Various",
        "description": "Linux operating system",
    },
    "ubuntu": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Canonical",
        "description": "Ubuntu Linux",
    },
    "rhel": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Red Hat",
        "description": "Red Hat Enterprise Linux",
    },
    "red hat": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Red Hat",
        "description": "Red Hat Enterprise Linux",
    },
    "centos": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "CentOS Project",
        "description": "CentOS Linux",
    },
    "debian": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Debian Project",
        "description": "Debian Linux",
    },
    "suse": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "SUSE",
        "description": "SUSE Linux Enterprise",
    },
    "windows server": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Microsoft",
        "description": "Windows Server",
    },
    "windows": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Microsoft",
        "description": "Microsoft Windows",
    },
    "unix": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Various",
        "description": "Unix operating system",
    },
    "aix": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "IBM",
        "description": "IBM AIX",
    },
    "solaris": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Oracle",
        "description": "Oracle Solaris",
    },
    "macos": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Apple",
        "description": "macOS",
    },
    "alpine": {
        "element_type": "SystemSoftware",
        "subtype": "operating_system",
        "vendor": "Alpine Linux",
        "description": "Alpine Linux (container-optimized)",
    },
    # -------------------------------------------------------------------------
    # NETWORKING → CommunicationNetwork / Node
    # -------------------------------------------------------------------------
    "load balancer": {
        "element_type": "Node",
        "subtype": "network_device",
        "category": "load_balancing",
        "description": "Load balancer device",
    },
    "elb": {
        "element_type": "TechnologyService",
        "subtype": "load_balancer_service",
        "vendor": "Amazon Web Services",
        "description": "Elastic Load Balancer",
    },
    "alb": {
        "element_type": "TechnologyService",
        "subtype": "load_balancer_service",
        "vendor": "Amazon Web Services",
        "description": "Application Load Balancer",
    },
    "firewall": {
        "element_type": "Node",
        "subtype": "security_device",
        "category": "network_security",
        "description": "Network firewall",
    },
    "waf": {
        "element_type": "TechnologyService",
        "subtype": "security_service",
        "category": "web_application_firewall",
        "description": "Web Application Firewall",
    },
    "vpn": {
        "element_type": "CommunicationNetwork",
        "subtype": "virtual_network",
        "category": "secure_tunnel",
        "description": "Virtual Private Network",
    },
    "cdn": {
        "element_type": "CommunicationNetwork",
        "subtype": "content_delivery",
        "description": "Content Delivery Network",
    },
    "cloudfront": {
        "element_type": "TechnologyService",
        "subtype": "cdn_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon CloudFront CDN",
    },
    "dns": {
        "element_type": "TechnologyService",
        "subtype": "network_service",
        "category": "name_resolution",
        "description": "Domain Name System",
    },
    "route53": {
        "element_type": "TechnologyService",
        "subtype": "dns_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon Route 53 DNS",
    },
    "vnet": {
        "element_type": "CommunicationNetwork",
        "subtype": "virtual_network",
        "vendor": "Microsoft",
        "description": "Azure Virtual Network",
    },
    "vpc": {
        "element_type": "CommunicationNetwork",
        "subtype": "virtual_network",
        "vendor": "Amazon Web Services",
        "description": "Virtual Private Cloud",
    },
    "api gateway": {
        "element_type": "Node",
        "subtype": "gateway",
        "category": "api_management",
        "description": "API Gateway",
    },
    "kong": {
        "element_type": "SystemSoftware",
        "subtype": "api_gateway",
        "vendor": "Kong Inc",
        "description": "Kong API Gateway",
    },
    "apigee": {
        "element_type": "TechnologyService",
        "subtype": "api_management",
        "vendor": "Google",
        "description": "Apigee API Management",
    },
    # -------------------------------------------------------------------------
    # MONITORING & OBSERVABILITY → SystemSoftware
    # -------------------------------------------------------------------------
    "prometheus": {
        "element_type": "SystemSoftware",
        "subtype": "monitoring",
        "vendor": "CNCF",
        "description": "Prometheus monitoring system",
    },
    "grafana": {
        "element_type": "SystemSoftware",
        "subtype": "visualization",
        "vendor": "Grafana Labs",
        "description": "Grafana dashboards",
    },
    "datadog": {
        "element_type": "TechnologyService",
        "subtype": "monitoring_service",
        "vendor": "Datadog",
        "description": "Datadog monitoring platform",
    },
    "splunk": {
        "element_type": "SystemSoftware",
        "subtype": "log_management",
        "vendor": "Splunk",
        "description": "Splunk log analytics",
    },
    "elk": {
        "element_type": "SystemSoftware",
        "subtype": "log_management",
        "vendor": "Elastic",
        "description": "ELK Stack (Elasticsearch, Logstash, Kibana)",
    },
    "new relic": {
        "element_type": "TechnologyService",
        "subtype": "apm_service",
        "vendor": "New Relic",
        "description": "New Relic APM",
    },
    "dynatrace": {
        "element_type": "TechnologyService",
        "subtype": "apm_service",
        "vendor": "Dynatrace",
        "description": "Dynatrace APM",
    },
    "cloudwatch": {
        "element_type": "TechnologyService",
        "subtype": "monitoring_service",
        "vendor": "Amazon Web Services",
        "description": "Amazon CloudWatch",
    },
    "jaeger": {
        "element_type": "SystemSoftware",
        "subtype": "tracing",
        "vendor": "CNCF",
        "description": "Jaeger distributed tracing",
    },
    "zipkin": {
        "element_type": "SystemSoftware",
        "subtype": "tracing",
        "vendor": "Open Source",
        "description": "Zipkin distributed tracing",
    },
    # -------------------------------------------------------------------------
    # CI/CD & DEVOPS → SystemSoftware
    # -------------------------------------------------------------------------
    "jenkins": {
        "element_type": "SystemSoftware",
        "subtype": "ci_cd",
        "vendor": "Jenkins Community",
        "description": "Jenkins automation server",
    },
    "gitlab": {
        "element_type": "SystemSoftware",
        "subtype": "devops_platform",
        "vendor": "GitLab",
        "description": "GitLab DevOps platform",
    },
    "github actions": {
        "element_type": "TechnologyService",
        "subtype": "ci_cd_service",
        "vendor": "GitHub",
        "description": "GitHub Actions CI/CD",
    },
    "azure devops": {
        "element_type": "TechnologyService",
        "subtype": "devops_service",
        "vendor": "Microsoft",
        "description": "Azure DevOps",
    },
    "circleci": {
        "element_type": "TechnologyService",
        "subtype": "ci_cd_service",
        "vendor": "CircleCI",
        "description": "CircleCI CI/CD",
    },
    "travis ci": {
        "element_type": "TechnologyService",
        "subtype": "ci_cd_service",
        "vendor": "Travis CI",
        "description": "Travis CI",
    },
    "ansible": {
        "element_type": "SystemSoftware",
        "subtype": "configuration_management",
        "vendor": "Red Hat",
        "description": "Ansible automation",
    },
    "terraform": {
        "element_type": "SystemSoftware",
        "subtype": "infrastructure_as_code",
        "vendor": "HashiCorp",
        "description": "Terraform IaC",
    },
    "puppet": {
        "element_type": "SystemSoftware",
        "subtype": "configuration_management",
        "vendor": "Puppet",
        "description": "Puppet configuration management",
    },
    "chef": {
        "element_type": "SystemSoftware",
        "subtype": "configuration_management",
        "vendor": "Progress",
        "description": "Chef configuration management",
    },
    "argocd": {
        "element_type": "SystemSoftware",
        "subtype": "gitops",
        "vendor": "CNCF",
        "description": "Argo CD GitOps",
    },
    "helm": {
        "element_type": "SystemSoftware",
        "subtype": "package_manager",
        "vendor": "CNCF",
        "description": "Helm Kubernetes package manager",
    },
    # -------------------------------------------------------------------------
    # SECURITY → SystemSoftware / TechnologyService
    # -------------------------------------------------------------------------
    "oauth": {
        "element_type": "TechnologyInterface",
        "subtype": "security_protocol",
        "category": "authentication",
        "description": "OAuth authentication protocol",
    },
    "oauth2": {
        "element_type": "TechnologyInterface",
        "subtype": "security_protocol",
        "category": "authentication",
        "description": "OAuth 2.0 authentication",
    },
    "saml": {
        "element_type": "TechnologyInterface",
        "subtype": "security_protocol",
        "category": "sso",
        "description": "SAML single sign-on",
    },
    "ldap": {
        "element_type": "TechnologyInterface",
        "subtype": "directory_protocol",
        "category": "authentication",
        "description": "LDAP directory protocol",
    },
    "active directory": {
        "element_type": "SystemSoftware",
        "subtype": "directory_service",
        "vendor": "Microsoft",
        "description": "Active Directory",
    },
    "keycloak": {
        "element_type": "SystemSoftware",
        "subtype": "identity_management",
        "vendor": "Red Hat",
        "description": "Keycloak identity management",
    },
    "okta": {
        "element_type": "TechnologyService",
        "subtype": "identity_service",
        "vendor": "Okta",
        "description": "Okta identity platform",
    },
    "auth0": {
        "element_type": "TechnologyService",
        "subtype": "identity_service",
        "vendor": "Okta",
        "description": "Auth0 identity platform",
    },
    "vault": {
        "element_type": "SystemSoftware",
        "subtype": "secrets_management",
        "vendor": "HashiCorp",
        "description": "HashiCorp Vault secrets management",
    },
    "ssl": {
        "element_type": "TechnologyInterface",
        "subtype": "security_protocol",
        "category": "encryption",
        "description": "SSL/TLS encryption",
    },
    "tls": {
        "element_type": "TechnologyInterface",
        "subtype": "security_protocol",
        "category": "encryption",
        "description": "TLS encryption",
    },
    # -------------------------------------------------------------------------
    # DATA PROCESSING & ANALYTICS → SystemSoftware
    # -------------------------------------------------------------------------
    "spark": {
        "element_type": "SystemSoftware",
        "subtype": "data_processing",
        "vendor": "Apache",
        "description": "Apache Spark analytics engine",
    },
    "hadoop": {
        "element_type": "SystemSoftware",
        "subtype": "data_platform",
        "vendor": "Apache",
        "description": "Apache Hadoop distributed processing",
    },
    "flink": {
        "element_type": "SystemSoftware",
        "subtype": "stream_processing",
        "vendor": "Apache",
        "description": "Apache Flink stream processing",
    },
    "airflow": {
        "element_type": "SystemSoftware",
        "subtype": "workflow_orchestration",
        "vendor": "Apache",
        "description": "Apache Airflow workflow",
    },
    "databricks": {
        "element_type": "TechnologyService",
        "subtype": "data_platform",
        "vendor": "Databricks",
        "description": "Databricks data platform",
    },
    "redshift": {
        "element_type": "TechnologyService",
        "subtype": "data_warehouse",
        "vendor": "Amazon Web Services",
        "description": "Amazon Redshift data warehouse",
    },
    "bigquery": {
        "element_type": "TechnologyService",
        "subtype": "data_warehouse",
        "vendor": "Google",
        "description": "Google BigQuery data warehouse",
    },
    "synapse": {
        "element_type": "TechnologyService",
        "subtype": "data_warehouse",
        "vendor": "Microsoft",
        "description": "Azure Synapse Analytics",
    },
    # -------------------------------------------------------------------------
    # STORAGE → SystemSoftware / TechnologyService
    # -------------------------------------------------------------------------
    "nfs": {
        "element_type": "TechnologyInterface",
        "subtype": "storage_protocol",
        "description": "Network File System",
    },
    "cifs": {
        "element_type": "TechnologyInterface",
        "subtype": "storage_protocol",
        "description": "Common Internet File System",
    },
    "san": {
        "element_type": "Node",
        "subtype": "storage_device",
        "category": "block_storage",
        "description": "Storage Area Network",
    },
    "nas": {
        "element_type": "Node",
        "subtype": "storage_device",
        "category": "file_storage",
        "description": "Network Attached Storage",
    },
    "ebs": {
        "element_type": "TechnologyService",
        "subtype": "block_storage",
        "vendor": "Amazon Web Services",
        "description": "Amazon Elastic Block Store",
    },
    "azure blob": {
        "element_type": "TechnologyService",
        "subtype": "object_storage",
        "vendor": "Microsoft",
        "description": "Azure Blob Storage",
    },
    "minio": {
        "element_type": "SystemSoftware",
        "subtype": "object_storage",
        "vendor": "MinIO",
        "description": "MinIO object storage",
    },
    "ceph": {
        "element_type": "SystemSoftware",
        "subtype": "distributed_storage",
        "vendor": "Red Hat",
        "description": "Ceph distributed storage",
    },
}


# =============================================================================
# ARCHIMATE RELATIONSHIP MAPPING
# =============================================================================

ARCHIMATE_TECHNOLOGY_RELATIONSHIPS = {
    # Node relationships
    "Node": {
        "deploys": ["Artifact", "SystemSoftware"],
        "serves": ["TechnologyService"],
        "realizes": ["TechnologyService"],
        "assigned_to": ["TechnologyFunction", "TechnologyProcess"],
    },
    # SystemSoftware relationships
    "SystemSoftware": {
        "assigned_to": ["Node", "Device"],
        "realizes": ["TechnologyService"],
        "serves": ["TechnologyInterface"],
        "accesses": ["Artifact"],
    },
    # TechnologyInterface relationships
    "TechnologyInterface": {
        "assigned_to": ["Node", "SystemSoftware"],
        "serves": ["ApplicationComponent", "ApplicationService"],
    },
    # TechnologyService relationships
    "TechnologyService": {
        "realized_by": ["Node", "SystemSoftware"],
        "serves": ["ApplicationService", "BusinessService"],
        "composed_of": ["TechnologyService"],
    },
    # Artifact relationships
    "Artifact": {
        "deployed_on": ["Node"],
        "realizes": ["DataObject"],
        "associated_with": ["Artifact"],
    },
    # CommunicationNetwork relationships
    "CommunicationNetwork": {
        "realizes": ["Path"],
        "connects": ["Node"],
        "serves": ["TechnologyService"],
    },
    # Device relationships
    "Device": {
        "realizes": ["Node"],
        "assigned_to": ["SystemSoftware"],
        "serves": ["TechnologyService"],
    },
}

# Standard relationship suggestions based on element type combinations
RELATIONSHIP_SUGGESTIONS = [
    {
        "source_type": "Node",
        "target_type": "Artifact",
        "relationship": "deploys",
        "description": "Node deploys Artifact",
    },
    {
        "source_type": "SystemSoftware",
        "target_type": "Node",
        "relationship": "assigned-to",
        "description": "SystemSoftware is assigned to Node",
    },
    {
        "source_type": "TechnologyInterface",
        "target_type": "Node",
        "relationship": "assigned-to",
        "description": "TechnologyInterface is assigned to Node",
    },
    {
        "source_type": "TechnologyInterface",
        "target_type": "SystemSoftware",
        "relationship": "assigned-to",
        "description": "TechnologyInterface is assigned to SystemSoftware",
    },
    {
        "source_type": "TechnologyService",
        "target_type": "Node",
        "relationship": "realized-by",
        "description": "TechnologyService is realized by Node",
    },
    {
        "source_type": "TechnologyService",
        "target_type": "SystemSoftware",
        "relationship": "realized-by",
        "description": "TechnologyService is realized by SystemSoftware",
    },
    {
        "source_type": "Node",
        "target_type": "TechnologyService",
        "relationship": "realizes",
        "description": "Node realizes TechnologyService",
    },
    {
        "source_type": "SystemSoftware",
        "target_type": "TechnologyService",
        "relationship": "realizes",
        "description": "SystemSoftware realizes TechnologyService",
    },
    {
        "source_type": "CommunicationNetwork",
        "target_type": "Node",
        "relationship": "connects",
        "description": "CommunicationNetwork connects Nodes",
    },
    {
        "source_type": "Artifact",
        "target_type": "Node",
        "relationship": "deployed-on",
        "description": "Artifact is deployed on Node",
    },
]


# =============================================================================
# ELEMENT TYPE CATEGORIES
# =============================================================================

ELEMENT_TYPE_CATEGORIES = {
    "Node": {
        "subtypes": [
            "cloud_platform",
            "cloud_paas",
            "cloud_cdn",
            "container_orchestration",
            "container_platform",
            "network_device",
            "security_device",
            "gateway",
            "storage_device",
        ],
        "description": "Computational or physical resource that hosts/manipulates/interacts with other resources",
    },
    "SystemSoftware": {
        "subtypes": [
            "database",
            "cache",
            "container_runtime",
            "container_management",
            "web_server",
            "reverse_proxy",
            "load_balancer",
            "application_server",
            "message_broker",
            "message_library",
            "runtime",
            "operating_system",
            "monitoring",
            "visualization",
            "log_management",
            "tracing",
            "ci_cd",
            "devops_platform",
            "configuration_management",
            "infrastructure_as_code",
            "gitops",
            "package_manager",
            "directory_service",
            "identity_management",
            "secrets_management",
            "data_processing",
            "data_platform",
            "stream_processing",
            "workflow_orchestration",
            "object_storage",
            "distributed_storage",
            "api_gateway",
        ],
        "description": "Software that provides execution environment for artifacts",
    },
    "TechnologyInterface": {
        "subtypes": ["api", "security_protocol", "directory_protocol", "storage_protocol"],
        "description": "Point of access where technology services are exposed",
    },
    "TechnologyService": {
        "subtypes": [
            "compute_service",
            "storage_service",
            "serverless",
            "managed_database",
            "nosql_service",
            "container_service",
            "managed_kubernetes",
            "message_service",
            "notification_service",
            "load_balancer_service",
            "security_service",
            "cdn_service",
            "dns_service",
            "monitoring_service",
            "apm_service",
            "ci_cd_service",
            "devops_service",
            "identity_service",
            "data_warehouse",
            "data_platform",
            "api_management",
            "block_storage",
            "object_storage",
        ],
        "description": "Explicitly defined exposed technology functionality",
    },
    "CommunicationNetwork": {
        "subtypes": ["virtual_network", "content_delivery", "secure_tunnel"],
        "description": "Set of structures connecting computing nodes",
    },
    "Artifact": {
        "subtypes": ["deployable", "configuration", "data_file"],
        "description": "Piece of data used or produced in software development",
    },
    "Device": {
        "subtypes": ["server", "workstation", "mobile", "iot"],
        "description": "Physical IT resource",
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_archimate_element_for_technology(keyword: str) -> Optional[Dict[str, Any]]:
    """
    Get ArchiMate element mapping for a technology keyword.

    Args:
        keyword: Technology keyword to look up (case-insensitive)

    Returns:
        Dictionary with ArchiMate element mapping or None if not found

    Example:
        >>> get_archimate_element_for_technology('kubernetes')
        {'element_type': 'Node', 'subtype': 'container_orchestration',
         'vendor': 'CNCF', 'description': 'Kubernetes container orchestration'}
    """
    if not keyword:
        return None

    # Normalize keyword for lookup
    normalized_keyword = keyword.lower().strip()

    # Direct lookup
    if normalized_keyword in TECHNOLOGY_KEYWORD_MAP:
        return TECHNOLOGY_KEYWORD_MAP[normalized_keyword].copy()

    # Try partial matching for compound terms
    for key, value in TECHNOLOGY_KEYWORD_MAP.items():
        if key in normalized_keyword or normalized_keyword in key:
            return value.copy()

    return None


def extract_technology_elements(technology_stack: str) -> List[Dict[str, Any]]:
    """
    Extract ArchiMate technology elements from a technology stack description.

    Parses a technology stack string and identifies all matching technology
    keywords, returning their ArchiMate element mappings.

    Args:
        technology_stack: Comma-separated or space-separated list of technologies

    Returns:
        List of ArchiMate element mappings with matched keywords

    Example:
        >>> extract_technology_elements('AWS, Kubernetes, PostgreSQL, REST API')
        [
            {'keyword': 'aws', 'element_type': 'Node', 'subtype': 'cloud_platform', ...},
            {'keyword': 'kubernetes', 'element_type': 'Node', 'subtype': 'container_orchestration', ...},
            {'keyword': 'postgresql', 'element_type': 'SystemSoftware', 'subtype': 'database', ...},
            {'keyword': 'rest', 'element_type': 'TechnologyInterface', 'subtype': 'api', ...}
        ]
    """
    if not technology_stack:
        return []

    elements = []
    seen_keywords = set()

    # Normalize and tokenize the technology stack
    normalized_stack = technology_stack.lower()

    # Try to match multi-word keywords first (sorted by length, longest first)
    sorted_keywords = sorted(TECHNOLOGY_KEYWORD_MAP.keys(), key=len, reverse=True)

    for keyword in sorted_keywords:
        # Use word boundary matching to avoid partial matches
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, normalized_stack) and keyword not in seen_keywords:
            mapping = TECHNOLOGY_KEYWORD_MAP[keyword].copy()
            mapping["keyword"] = keyword
            elements.append(mapping)
            seen_keywords.add(keyword)
            # Remove matched keyword to avoid duplicate matches from aliases
            normalized_stack = re.sub(pattern, "", normalized_stack)

    return elements


def get_all_keywords_for_element_type(element_type: str) -> List[str]:
    """
    Get all technology keywords that map to a specific ArchiMate element type.

    Args:
        element_type: ArchiMate element type (e.g., 'Node', 'SystemSoftware')

    Returns:
        List of technology keywords that map to the specified element type

    Example:
        >>> get_all_keywords_for_element_type('TechnologyInterface')
        ['rest', 'rest api', 'restful', 'graphql', 'soap', 'grpc', 'websocket', ...]
    """
    if not element_type:
        return []

    return [
        keyword
        for keyword, mapping in TECHNOLOGY_KEYWORD_MAP.items()
        if mapping.get("element_type") == element_type
    ]


def get_all_keywords_for_subtype(subtype: str) -> List[str]:
    """
    Get all technology keywords that map to a specific subtype.

    Args:
        subtype: Technology subtype (e.g., 'database', 'api', 'cloud_platform')

    Returns:
        List of technology keywords that map to the specified subtype

    Example:
        >>> get_all_keywords_for_subtype('database')
        ['oracle', 'sql server', 'postgresql', 'mysql', 'mongodb', ...]
    """
    if not subtype:
        return []

    return [
        keyword
        for keyword, mapping in TECHNOLOGY_KEYWORD_MAP.items()
        if mapping.get("subtype") == subtype
    ]


def get_keywords_by_vendor(vendor: str) -> List[str]:
    """
    Get all technology keywords associated with a specific vendor.

    Args:
        vendor: Vendor name (case-insensitive partial match)

    Returns:
        List of technology keywords from the specified vendor

    Example:
        >>> get_keywords_by_vendor('Microsoft')
        ['azure', 'microsoft azure', 'sql server', 'mssql', '.net', 'dotnet', ...]
    """
    if not vendor:
        return []

    vendor_lower = vendor.lower()
    return [
        keyword
        for keyword, mapping in TECHNOLOGY_KEYWORD_MAP.items()
        if vendor_lower in mapping.get("vendor", "").lower()
    ]


def get_suggested_relationships(element_type: str) -> List[Dict[str, Any]]:
    """
    Get suggested ArchiMate relationships for a given element type.

    Args:
        element_type: ArchiMate element type

    Returns:
        List of relationship suggestions with source, target, and relationship type

    Example:
        >>> get_suggested_relationships('SystemSoftware')
        [{'source_type': 'SystemSoftware', 'target_type': 'Node',
          'relationship': 'assigned-to', ...}, ...]
    """
    if not element_type:
        return []

    return [
        rel
        for rel in RELATIONSHIP_SUGGESTIONS
        if rel["source_type"] == element_type or rel["target_type"] == element_type
    ]


def categorize_technology_stack(technology_stack: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize extracted technologies by their ArchiMate element types.

    Args:
        technology_stack: Technology stack description

    Returns:
        Dictionary with element types as keys and lists of matched technologies

    Example:
        >>> categorize_technology_stack('AWS, PostgreSQL, REST API, Docker')
        {
            'Node': [{'keyword': 'aws', ...}],
            'SystemSoftware': [{'keyword': 'postgresql', ...}, {'keyword': 'docker', ...}],
            'TechnologyInterface': [{'keyword': 'rest', ...}]
        }
    """
    elements = extract_technology_elements(technology_stack)

    categorized: Dict[str, List[Dict[str, Any]]] = {}

    for element in elements:
        element_type = element.get("element_type", "Unknown")
        if element_type not in categorized:
            categorized[element_type] = []
        categorized[element_type].append(element)

    return categorized


def generate_archimate_elements_from_stack(
    technology_stack: str, include_relationships: bool = True
) -> Dict[str, Any]:
    """
    Generate complete ArchiMate elements and relationships from a technology stack.

    This is the main function for Phase 4.1 derivation - it takes a technology
    stack description and produces ArchiMate elements with suggested relationships.

    Args:
        technology_stack: Technology stack description
        include_relationships: Whether to include relationship suggestions

    Returns:
        Dictionary containing:
        - elements: List of ArchiMate elements
        - relationships: List of suggested relationships (if requested)
        - summary: Statistics about extracted elements

    Example:
        >>> result = generate_archimate_elements_from_stack('AWS, Kubernetes, PostgreSQL, REST')
        >>> result['summary']
        {'total_elements': 4, 'by_type': {'Node': 2, 'SystemSoftware': 1, 'TechnologyInterface': 1}}
    """
    elements = extract_technology_elements(technology_stack)
    categorized = categorize_technology_stack(technology_stack)

    result = {
        "elements": elements,
        "by_type": categorized,
        "summary": {
            "total_elements": len(elements),
            "by_type": {k: len(v) for k, v in categorized.items()},
        },
    }

    if include_relationships:
        relationships = []
        element_types = set(e.get("element_type") for e in elements)

        for rel in RELATIONSHIP_SUGGESTIONS:
            if rel["source_type"] in element_types or rel["target_type"] in element_types:
                relationships.append(rel)

        result["suggested_relationships"] = relationships

    return result


def get_element_type_info(element_type: str) -> Optional[Dict[str, Any]]:
    """
    Get information about an ArchiMate element type.

    Args:
        element_type: ArchiMate element type

    Returns:
        Dictionary with element type information or None if not found
    """
    return ELEMENT_TYPE_CATEGORIES.get(element_type)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main mapping
    "TECHNOLOGY_KEYWORD_MAP",
    "ARCHIMATE_TECHNOLOGY_RELATIONSHIPS",
    "RELATIONSHIP_SUGGESTIONS",
    "ELEMENT_TYPE_CATEGORIES",
    # Core functions
    "get_archimate_element_for_technology",
    "extract_technology_elements",
    "get_all_keywords_for_element_type",
    # Utility functions
    "get_all_keywords_for_subtype",
    "get_keywords_by_vendor",
    "get_suggested_relationships",
    "categorize_technology_stack",
    "generate_archimate_elements_from_stack",
    "get_element_type_info",
]
