# Enterprise Architecture Python SDK

A comprehensive Python SDK for interacting with the Enterprise Architecture Platform API.

## Features

- **Knowledge Graph Operations**: Query and manipulate enterprise knowledge graphs
- **ArchiMate Model Management**: Create, read, update, and delete ArchiMate elements
- **Capability Analysis**: Analyze and manage enterprise capabilities
- **Vendor Analysis**: Access vendor information and analysis
- **Application Portfolio**: Manage application portfolios and relationships
- **Options Analysis**: Perform strategic options analysis
- **Workflow Orchestration**: Execute and monitor enterprise workflows

## Installation

```bash
pip install enterprise-sdk
```

## Quick Start

```python
from enterprise_sdk import EnterpriseClient

# Initialize the client
client = EnterpriseClient(
    base_url="https://your-platform.com",
    api_key="your-api-key"
)

# Query knowledge graph
kg_data = client.knowledge_graph.query("MATCH (n) RETURN n LIMIT 10")

# Create an ArchiMate element
element = client.archimate.create_element({
    "type": "BusinessActor",
    "name": "Customer",
    "properties": {"description": "External customer"}
})

# Analyze capabilities
capabilities = client.capabilities.get_all()
```

## Authentication

The SDK supports API key authentication:

```python
client = EnterpriseClient(
    base_url="https://your-platform.com",
    api_key="your-api-key"
)
```

## Error Handling

The SDK provides comprehensive error handling:

```python
try:
    result = client.knowledge_graph.query("INVALID QUERY")
except EnterpriseSDKError as e:
    print(f"SDK Error: {e}")
except requests.RequestException as e:
    print(f"HTTP Error: {e}")
```

## Advanced Usage

### Custom HTTP Client Configuration

```python
import requests
from enterprise_sdk import EnterpriseClient

# Custom session with proxy
session = requests.Session()
session.proxies = {"https": "https://proxy.company.com:8080"}

client = EnterpriseClient(
    base_url="https://your-platform.com",
    api_key="your-api-key",
    session=session
)
```

### Batch Operations

```python
# Batch create multiple elements
elements = [
    {"type": "BusinessActor", "name": "Actor 1"},
    {"type": "BusinessActor", "name": "Actor 2"},
]

results = client.archimate.batch_create_elements(elements)
```

## API Reference

### EnterpriseClient

Main client class that provides access to all services.

#### Methods

- `knowledge_graph`: Access to Knowledge Graph operations
- `archimate`: Access to ArchiMate model management
- `capabilities`: Access to capability analysis
- `vendors`: Access to vendor analysis
- `applications`: Access to application portfolio
- `options`: Access to options analysis
- `workflows`: Access to workflow orchestration

### Service Clients

Each service client provides methods for CRUD operations and specialized queries.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
