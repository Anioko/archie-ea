# Enterprise Architecture JavaScript SDK

A comprehensive JavaScript SDK for interacting with the Enterprise Architecture Platform API.

## Features

- **Knowledge Graph Operations**: Query and manipulate enterprise knowledge graphs
- **ArchiMate Model Management**: Create, read, update, and delete ArchiMate elements
- **Capability Analysis**: Analyze and manage enterprise capabilities
- **Vendor Analysis**: Access vendor information and analysis
- **Application Portfolio**: Manage application portfolios and relationships
- **Options Analysis**: Perform strategic options analysis
- **Workflow Orchestration**: Execute and monitor enterprise workflows
- **Universal Compatibility**: Works in Node.js, browsers, and bundlers

## Installation

### NPM
```bash
npm install enterprise-sdk
```

### CDN
```html
<script src="https://cdn.jsdelivr.net/npm/enterprise-sdk@2.0.0/enterprise-sdk.js"></script>
```

## Quick Start

### Node.js
```javascript
const { EnterpriseClient } = require('enterprise-sdk');

const client = new EnterpriseClient(
  'https://your-platform.com',
  'your-api-key'
);

// Query knowledge graph
async function queryKG() {
  try {
    const result = await client.knowledgeGraph.query(
      'MATCH (n) RETURN n LIMIT 10'
    );
    console.log(result);
  } catch (error) {
    console.error('Error:', error.message);
  }
}
```

### Browser
```html
<!DOCTYPE html>
<html>
<head>
  <script src="enterprise-sdk.js"></script>
</head>
<body>
  <script>
    const client = new window.EnterpriseSDK.EnterpriseClient(
      'https://your-platform.com',
      'your-api-key'
    );

    // Create an ArchiMate element
    client.archimate.createElement({
      type: 'BusinessActor',
      name: 'Customer',
      properties: { description: 'External customer' }
    }).then(result => {
      console.log('Created element:', result);
    }).catch(error => {
      console.error('Error:', error.message);
    });
  </script>
</body>
</html>
```

### ES6 Modules
```javascript
import { EnterpriseClient } from 'enterprise-sdk';

const client = new EnterpriseClient(
  'https://your-platform.com',
  'your-api-key'
);

// Analyze capabilities
const capabilities = await client.capabilities.getCapabilities();
console.log(capabilities);
```

## Authentication

The SDK supports Bearer token authentication:

```javascript
const client = new EnterpriseClient(
  'https://your-platform.com',
  'your-api-key'
);
```

## Error Handling

The SDK provides comprehensive error handling:

```javascript
try {
  const result = await client.knowledgeGraph.query('INVALID QUERY');
} catch (error) {
  if (error instanceof EnterpriseSDKError) {
    console.log(`SDK Error (${error.status}): ${error.message}`);
  } else {
    console.log(`Network Error: ${error.message}`);
  }
}
```

## Advanced Usage

### Custom HTTP Configuration

```javascript
const client = new EnterpriseClient(
  'https://your-platform.com',
  'your-api-key',
  {
    timeout: 5000, // 5 seconds
    headers: {
      'X-Custom-Header': 'value'
    }
  }
);
```

### Batch Operations

```javascript
// Batch create multiple elements
const elements = [
  { type: 'BusinessActor', name: 'Actor 1' },
  { type: 'BusinessActor', name: 'Actor 2' }
];

const results = await Promise.all(
  elements.map(element => client.archimate.createElement(element))
);
```

### Streaming Responses

```javascript
// For large result sets, handle streaming
const response = await client.knowledgeGraph.query('MATCH (n) RETURN n');
const stream = response.body;

// Process stream chunks
for await (const chunk of stream) {
  console.log('Chunk:', chunk);
}
```

## API Reference

### EnterpriseClient

Main client class that provides access to all services.

#### Constructor
```javascript
new EnterpriseClient(baseURL, apiKey, options)
```

- `baseURL` (string): Base URL of the Enterprise Architecture Platform
- `apiKey` (string): API key for authentication
- `options` (object, optional): Configuration options
  - `timeout` (number): Request timeout in milliseconds (default: 30000)
  - `headers` (object): Additional headers to send with requests

#### Service Clients

- `knowledgeGraph`: Knowledge Graph operations
- `archimate`: ArchiMate model management
- `capabilities`: Capability analysis
- `vendors`: Vendor analysis
- `applications`: Application portfolio
- `options`: Options analysis
- `workflows`: Workflow orchestration

### Service Client Methods

Each service client provides methods for CRUD operations and specialized queries. All methods return Promises.

#### Common Patterns

- `get*()`: Retrieve single or multiple resources
- `create*()`: Create new resources
- `update*()`: Update existing resources
- `delete*()`: Delete resources
- `analyze*()`: Perform analysis operations

## Examples

### Complete Workflow Example

```javascript
const { EnterpriseClient } = require('enterprise-sdk');

async function enterpriseWorkflow() {
  const client = new EnterpriseClient(
    'https://ea-platform.company.com',
    process.env.EA_API_KEY
  );

  try {
    // 1. Create a business capability
    const capability = await client.capabilities.createCapability({
      name: 'Digital Transformation',
      description: 'Enable digital transformation initiatives',
      domain: 'Business'
    });

    // 2. Create an ArchiMate element
    const element = await client.archimate.createElement({
      type: 'BusinessCapability',
      name: capability.name,
      properties: {
        description: capability.description,
        capability_id: capability.id
      }
    });

    // 3. Analyze the capability
    const analysis = await client.capabilities.analyzeCapability(capability.id);

    // 4. Create a workflow for implementation
    const workflow = await client.workflows.createWorkflow({
      name: 'Capability Implementation',
      description: 'Implement the digital transformation capability',
      steps: [
        { name: 'Assessment', type: 'analysis' },
        { name: 'Planning', type: 'planning' },
        { name: 'Execution', type: 'execution' }
      ]
    });

    console.log('Workflow created:', workflow.id);

  } catch (error) {
    console.error('Workflow failed:', error.message);
  }
}

enterpriseWorkflow();
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Testing

```bash
npm test
```

## Building

```bash
npm run build
```

## License

MIT License - see LICENSE file for details
