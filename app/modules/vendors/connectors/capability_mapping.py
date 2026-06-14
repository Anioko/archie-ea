# app/modules/vendors/connectors/capability_mapping.py
"""Cloud service → BusinessCapability name mappings.

These are curated, human-reviewed mappings. The fuzzy matcher in the seed script
is NOT used here — cloud services have deterministic names.
"""

AWS_CAPABILITY_MAP = {
    "AmazonEC2": "Compute",
    "AmazonRDS": "Relational Database",
    "AmazonS3": "Object Storage",
    "AmazonSES": "Email Marketing",
    "AmazonECS": "Container Orchestration",
    "AWSLambda": "Serverless Compute",
    "AmazonSNS": "Messaging",
    "AmazonSQS": "Message Queue",
    "AmazonRedshift": "Data Warehousing",
    "AmazonElastiCache": "Caching",
    "AmazonDynamoDB": "Document Database",
    "AmazonCloudFront": "Content Delivery",
    "AmazonRoute53": "DNS Management",
    "AmazonVPC": "Network Infrastructure",
    "AmazonEKS": "Container Orchestration",
    "AWSFargate": "Container Orchestration",
    "AmazonKinesis": "Event Streaming",
    "AmazonMSK": "Event Streaming",
    "AmazonOpenSearchService": "Search",
    "AmazonSageMaker": "Machine Learning",
    "AmazonEFS": "File Storage",
    "AmazonGuardDuty": "Security Monitoring",
    "AmazonECR": "Container Registry",
    "AmazonAPIGateway": "API Management",
    "AWSCodePipeline": "CI/CD",
    "AWSCodeBuild": "CI/CD",
    "AmazonCloudWatch": "Monitoring",
    "AWSSecretsManager": "Secrets Management",
    "AmazonCognito": "Identity Management",
    "AmazonAurora": "Relational Database",
}

AZURE_CAPABILITY_MAP = {
    "Virtual Machines": "Compute",
    "Azure SQL Database": "Relational Database",
    "Azure Blob Storage": "Object Storage",
    "Azure Kubernetes Service": "Container Orchestration",
    "Azure Functions": "Serverless Compute",
    "Azure Cosmos DB": "Document Database",
    "Azure DevOps": "CI/CD",
    "Azure Active Directory": "Identity Management",
    "Azure Monitor": "Monitoring",
    "Azure Key Vault": "Secrets Management",
    "Azure API Management": "API Management",
    "Azure Cache for Redis": "Caching",
    "Azure Event Hubs": "Event Streaming",
    "Azure Service Bus": "Message Queue",
    "Azure Cognitive Search": "Search",
    "Azure Machine Learning": "Machine Learning",
    "Azure CDN": "Content Delivery",
    "Azure Container Registry": "Container Registry",
    "Azure Front Door": "Content Delivery",
    "Azure Sentinel": "Security Monitoring",
}

GCP_CAPABILITY_MAP = {
    "Compute Engine": "Compute",
    "Cloud SQL": "Relational Database",
    "Cloud Storage": "Object Storage",
    "Google Kubernetes Engine": "Container Orchestration",
    "Cloud Functions": "Serverless Compute",
    "Cloud Run": "Serverless Compute",
    "BigQuery": "Data Warehousing",
    "Pub/Sub": "Event Streaming",
    "Cloud CDN": "Content Delivery",
    "Cloud DNS": "DNS Management",
    "Artifact Registry": "Container Registry",
    "Secret Manager": "Secrets Management",
    "Cloud Build": "CI/CD",
    "Cloud Monitoring": "Monitoring",
    "Vertex AI": "Machine Learning",
    "Memorystore": "Caching",
    "Firestore": "Document Database",
    "API Gateway": "API Management",
    "Identity Platform": "Identity Management",
    "Chronicle Security": "Security Monitoring",
}


def get_capability_map(provider: str) -> dict:
    """Get the capability mapping for a cloud provider."""
    maps = {
        "aws": AWS_CAPABILITY_MAP,
        "azure": AZURE_CAPABILITY_MAP,
        "gcp": GCP_CAPABILITY_MAP,
    }
    return maps.get(provider, {})
