"""
Enterprise Architecture Python SDK

A comprehensive Python SDK for interacting with the Enterprise Architecture Platform API.

Features:
- Knowledge Graph operations
- ArchiMate model management
- Capability analysis
- Vendor analysis
- Application portfolio management
- Options analysis
- Workflow orchestration

Example:
    from enterprise_sdk import EnterpriseClient

    client = EnterpriseClient(base_url="https://your-platform.com", api_key="your-key")

    # Get ArchiMate elements
    elements = client.kg.get_elements(element_type="BusinessProcess")

    # Perform capability analysis
    analysis = client.capabilities.analyze_gaps(
        current_capabilities=["cap1", "cap2"],
        target_capabilities=["cap3", "cap4"]
    )
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class EnterpriseClient:
    """
    Main client for Enterprise Architecture Platform API
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        """
        Initialize the Enterprise API client

        Args:
            base_url: Base URL of the Enterprise API (e.g., "https://platform.com")
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Enterprise-SDK/2.0.0",
            }
        )

        # Initialize service clients
        self.kg = KnowledgeGraphClient(self)
        self.archimate = ArchimateClient(self)
        self.capabilities = CapabilityClient(self)
        self.vendors = VendorClient(self)
        self.applications = ApplicationClient(self)
        self.options = OptionsClient(self)
        self.workflows = WorkflowClient(self)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to API

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            **kwargs: Additional request parameters

        Returns:
            API response data

        Raises:
            requests.HTTPError: For HTTP errors
            ValueError: For API errors
        """
        url = urljoin(f"{self.base_url}/api/v2/enterprise/", endpoint.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            data = response.json()
            if not data.get("success", False):
                raise ValueError(f"API error: {data.get('error', 'Unknown error')}")

            return data.get("data", {})

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise


class KnowledgeGraphClient:
    """Client for Knowledge Graph operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def get_elements(
        self,
        element_type: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get ArchiMate elements from knowledge graph

        Args:
            element_type: Element type filter
            domain: Business domain filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of ArchiMate elements
        """
        params = {}
        if element_type:
            params["type"] = element_type
        if domain:
            params["domain"] = domain
        params["limit"] = limit
        params["offset"] = offset

        return self.client._request("GET", "kg/elements", params=params)

    def get_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get ArchiMate relationships

        Args:
            relationship_type: Relationship type filter
            source_id: Source element ID
            target_id: Target element ID

        Returns:
            List of relationships
        """
        params = {}
        if relationship_type:
            params["type"] = relationship_type
        if source_id:
            params["source_id"] = source_id
        if target_id:
            params["target_id"] = target_id

        return self.client._request("GET", "kg/relationships", params=params)

    def search(self, query: str, element_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Search knowledge graph elements

        Args:
            query: Search query
            element_type: Element type filter
            limit: Maximum results

        Returns:
            List of matching elements
        """
        params = {"q": query, "limit": limit}
        if element_type:
            params["type"] = element_type

        return self.client._request("GET", "kg/search", params=params)


class ArchimateClient:
    """Client for ArchiMate model operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def get_models(self, domain: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """
        Get available ArchiMate models

        Args:
            domain: Business domain filter
            status: Model status filter

        Returns:
            List of models
        """
        params = {}
        if domain:
            params["domain"] = domain
        if status:
            params["status"] = status

        return self.client._request("GET", "archimate/models", params=params)

    def get_model(self, model_id: str) -> Dict:
        """
        Get specific ArchiMate model

        Args:
            model_id: Model ID

        Returns:
            Model details
        """
        return self.client._request("GET", f"archimate/models/{model_id}")

    def export_model(self, model_id: str, format: str = "xml") -> Dict:
        """
        Export ArchiMate model

        Args:
            model_id: Model ID
            format: Export format ('xml' or 'json')

        Returns:
            Exported model data
        """
        params = {"format": format}
        return self.client._request("GET", f"archimate/export/{model_id}", params=params)


class CapabilityClient:
    """Client for capability analysis operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def analyze_gaps(
        self,
        current_capabilities: List[str],
        target_capabilities: List[str],
        domain: Optional[str] = None,
    ) -> Dict:
        """
        Perform capability gap analysis

        Args:
            current_capabilities: List of current capability IDs
            target_capabilities: List of target capability IDs
            domain: Business domain filter

        Returns:
            Gap analysis results
        """
        data = {
            "current_capabilities": current_capabilities,
            "target_capabilities": target_capabilities,
        }
        if domain:
            data["domain"] = domain

        return self.client._request("POST", "capabilities/analysis", json=data)

    def get_mappings(
        self,
        application_id: Optional[str] = None,
        domain: Optional[str] = None,
        maturity_level: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get capability mappings

        Args:
            application_id: Filter by application
            domain: Business domain filter
            maturity_level: Maturity level filter

        Returns:
            List of capability mappings
        """
        params = {}
        if application_id:
            params["application_id"] = application_id
        if domain:
            params["domain"] = domain
        if maturity_level:
            params["maturity_level"] = maturity_level

        return self.client._request("GET", "capabilities/mapping", params=params)


class VendorClient:
    """Client for vendor analysis operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def analyze(
        self, requirements: List[str], criteria: Dict, vendor_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Perform vendor analysis

        Args:
            requirements: List of requirements
            criteria: Analysis criteria with weights
            vendor_ids: Optional vendor filter

        Returns:
            Vendor analysis results
        """
        data = {"requirements": requirements, "criteria": criteria}
        if vendor_ids:
            data["vendor_ids"] = vendor_ids

        return self.client._request("POST", "vendors/analysis", json=data)

    def get_products(
        self,
        vendor_id: Optional[str] = None,
        category: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get vendor products

        Args:
            vendor_id: Filter by vendor
            category: Product category filter
            capability: Capability filter

        Returns:
            List of vendor products
        """
        params = {}
        if vendor_id:
            params["vendor_id"] = vendor_id
        if category:
            params["category"] = category
        if capability:
            params["capability"] = capability

        return self.client._request("GET", "vendors/products", params=params)


class ApplicationClient:
    """Client for application portfolio operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def get_portfolio(
        self,
        domain: Optional[str] = None,
        criticality: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get application portfolio

        Args:
            domain: Business domain filter
            criticality: Criticality level filter
            status: Application status filter

        Returns:
            List of applications
        """
        params = {}
        if domain:
            params["domain"] = domain
        if criticality:
            params["criticality"] = criticality
        if status:
            params["status"] = status

        return self.client._request("GET", "applications/portfolio", params=params)

    def get_capabilities(self, application_id: str) -> List[Dict]:
        """
        Get capabilities for specific application

        Args:
            application_id: Application ID

        Returns:
            List of capabilities
        """
        return self.client._request("GET", f"applications/capabilities/{application_id}")


class OptionsClient:
    """Client for options analysis operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def analyze(self, scenario: str, options: List[Dict], criteria: Dict) -> Dict:
        """
        Perform multi-criteria options analysis

        Args:
            scenario: Analysis scenario
            options: List of options with costs/benefits
            criteria: Analysis criteria with weights

        Returns:
            Options analysis results
        """
        data = {"scenario": scenario, "options": options, "criteria": criteria}

        return self.client._request("POST", "options/analysis", json=data)


class WorkflowClient:
    """Client for workflow orchestration operations"""

    def __init__(self, client: EnterpriseClient):
        self.client = client

    def create_arb_workflow(
        self,
        title: str,
        description: str,
        artifacts: List[str],
        reviewers: List[str],
        deadline: Optional[str] = None,
    ) -> Dict:
        """
        Create ARB workflow

        Args:
            title: Workflow title
            description: Workflow description
            artifacts: List of artifact IDs
            reviewers: List of reviewer user IDs
            deadline: Optional deadline

        Returns:
            Created workflow details
        """
        data = {
            "title": title,
            "description": description,
            "artifacts": artifacts,
            "reviewers": reviewers,
        }
        if deadline:
            data["deadline"] = deadline

        return self.client._request("POST", "workflows/arb", json=data)

    def get_workflow(self, workflow_id: str) -> Dict:
        """
        Get workflow details

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow details
        """
        return self.client._request("GET", f"workflows/arb/{workflow_id}")


# Export main client
__all__ = ["EnterpriseClient"]
