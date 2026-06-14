/**
 * Enterprise Architecture JavaScript SDK
 * A comprehensive SDK for interacting with the Enterprise Architecture Platform API
 */

class EnterpriseSDKError extends Error {
  constructor(message, status, response) {
    super(message);
    this.name = 'EnterpriseSDKError';
    this.status = status;
    this.response = response;
  }
}

class BaseClient {
  constructor(baseURL, apiKey, options = {}) {
    this.baseURL = baseURL.replace(/\/$/, ''); // Remove trailing slash
    this.apiKey = apiKey;
    this.timeout = options.timeout || 30000;
    this.headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      ...options.headers
    };
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      method: options.method || 'GET',
      headers: { ...this.headers, ...options.headers },
      signal: AbortSignal.timeout(this.timeout),
      ...options
    };

    if (options.body && typeof options.body === 'object') {
      config.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new EnterpriseSDKError(
          errorData.message || `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          errorData
        );
      }

      return await response.json();
    } catch (error) {
      if (error instanceof EnterpriseSDKError) {
        throw error;
      }
      throw new EnterpriseSDKError(`Network error: ${error.message}`, 0, null);
    }
  }

  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url);
  }

  async post(endpoint, data) {
    return this.request(endpoint, { method: 'POST', body: data });
  }

  async put(endpoint, data) {
    return this.request(endpoint, { method: 'PUT', body: data });
  }

  async patch(endpoint, data) {
    return this.request(endpoint, { method: 'PATCH', body: data });
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

class KnowledgeGraphClient extends BaseClient {
  async query(cypherQuery, params = {}) {
    return this.post('/api/enterprise/knowledge-graph/query', {
      query: cypherQuery,
      parameters: params
    });
  }

  async getNode(nodeId) {
    return this.get(`/api/enterprise/knowledge-graph/nodes/${nodeId}`);
  }

  async createNode(nodeData) {
    return this.post('/api/enterprise/knowledge-graph/nodes', nodeData);
  }

  async updateNode(nodeId, nodeData) {
    return this.put(`/api/enterprise/knowledge-graph/nodes/${nodeId}`, nodeData);
  }

  async deleteNode(nodeId) {
    return this.delete(`/api/enterprise/knowledge-graph/nodes/${nodeId}`);
  }

  async getRelationship(relId) {
    return this.get(`/api/enterprise/knowledge-graph/relationships/${relId}`);
  }

  async createRelationship(relData) {
    return this.post('/api/enterprise/knowledge-graph/relationships', relData);
  }

  async updateRelationship(relId, relData) {
    return this.put(`/api/enterprise/knowledge-graph/relationships/${relId}`, relData);
  }

  async deleteRelationship(relId) {
    return this.delete(`/api/enterprise/knowledge-graph/relationships/${relId}`);
  }
}

class ArchimateClient extends BaseClient {
  async getElements(params = {}) {
    return this.get('/api/enterprise/archimate/elements', params);
  }

  async getElement(elementId) {
    return this.get(`/api/enterprise/archimate/elements/${elementId}`);
  }

  async createElement(elementData) {
    return this.post('/api/enterprise/archimate/elements', elementData);
  }

  async updateElement(elementId, elementData) {
    return this.put(`/api/enterprise/archimate/elements/${elementId}`, elementData);
  }

  async deleteElement(elementId) {
    return this.delete(`/api/enterprise/archimate/elements/${elementId}`);
  }

  async getRelationships(params = {}) {
    return this.get('/api/enterprise/archimate/relationships', params);
  }

  async getRelationship(relId) {
    return this.get(`/api/enterprise/archimate/relationships/${relId}`);
  }

  async createRelationship(relData) {
    return this.post('/api/enterprise/archimate/relationships', relData);
  }

  async updateRelationship(relId, relData) {
    return this.put(`/api/enterprise/archimate/relationships/${relId}`, relData);
  }

  async deleteRelationship(relId) {
    return this.delete(`/api/enterprise/archimate/relationships/${relId}`);
  }

  async getViews(params = {}) {
    return this.get('/api/enterprise/archimate/views', params);
  }

  async getView(viewId) {
    return this.get(`/api/enterprise/archimate/views/${viewId}`);
  }

  async createView(viewData) {
    return this.post('/api/enterprise/archimate/views', viewData);
  }

  async updateView(viewId, viewData) {
    return this.put(`/api/enterprise/archimate/views/${viewId}`, viewData);
  }

  async deleteView(viewId) {
    return this.delete(`/api/enterprise/archimate/views/${viewId}`);
  }
}

class CapabilityClient extends BaseClient {
  async getCapabilities(params = {}) {
    return this.get('/api/enterprise/capabilities', params);
  }

  async getCapability(capabilityId) {
    return this.get(`/api/enterprise/capabilities/${capabilityId}`);
  }

  async createCapability(capabilityData) {
    return this.post('/api/enterprise/capabilities', capabilityData);
  }

  async updateCapability(capabilityId, capabilityData) {
    return this.put(`/api/enterprise/capabilities/${capabilityId}`, capabilityData);
  }

  async deleteCapability(capabilityId) {
    return this.delete(`/api/enterprise/capabilities/${capabilityId}`);
  }

  async analyzeCapability(capabilityId, analysisType = 'comprehensive') {
    return this.post(`/api/enterprise/capabilities/${capabilityId}/analyze`, {
      analysis_type: analysisType
    });
  }

  async getCapabilityMap(params = {}) {
    return this.get('/api/enterprise/capabilities/map', params);
  }
}

class VendorClient extends BaseClient {
  async getVendors(params = {}) {
    return this.get('/api/enterprise/vendors', params);
  }

  async getVendor(vendorId) {
    return this.get(`/api/enterprise/vendors/${vendorId}`);
  }

  async createVendor(vendorData) {
    return this.post('/api/enterprise/vendors', vendorData);
  }

  async updateVendor(vendorId, vendorData) {
    return this.put(`/api/enterprise/vendors/${vendorId}`, vendorData);
  }

  async deleteVendor(vendorId) {
    return this.delete(`/api/enterprise/vendors/${vendorId}`);
  }

  async analyzeVendor(vendorId, analysisType = 'comprehensive') {
    return this.post(`/api/enterprise/vendors/${vendorId}/analyze`, {
      analysis_type: analysisType
    });
  }

  async getVendorLandscape(params = {}) {
    return this.get('/api/enterprise/vendors/landscape', params);
  }
}

class ApplicationClient extends BaseClient {
  async getApplications(params = {}) {
    return this.get('/api/enterprise/applications', params);
  }

  async getApplication(appId) {
    return this.get(`/api/enterprise/applications/${appId}`);
  }

  async createApplication(appData) {
    return this.post('/api/enterprise/applications', appData);
  }

  async updateApplication(appId, appData) {
    return this.put(`/api/enterprise/applications/${appId}`, appData);
  }

  async deleteApplication(appId) {
    return this.delete(`/api/enterprise/applications/${appId}`);
  }

  async getPortfolioAnalysis(params = {}) {
    return this.get('/api/enterprise/applications/portfolio-analysis', params);
  }

  async getApplicationDependencies(appId) {
    return this.get(`/api/enterprise/applications/${appId}/dependencies`);
  }
}

class OptionsClient extends BaseClient {
  async getOptions(params = {}) {
    return this.get('/api/enterprise/options', params);
  }

  async getOption(optionId) {
    return this.get(`/api/enterprise/options/${optionId}`);
  }

  async createOption(optionData) {
    return this.post('/api/enterprise/options', optionData);
  }

  async updateOption(optionId, optionData) {
    return this.put(`/api/enterprise/options/${optionId}`, optionData);
  }

  async deleteOption(optionId) {
    return this.delete(`/api/enterprise/options/${optionId}`);
  }

  async analyzeOption(optionId, criteria = {}) {
    return this.post(`/api/enterprise/options/${optionId}/analyze`, criteria);
  }

  async compareOptions(optionIds, criteria = {}) {
    return this.post('/api/enterprise/options/compare', {
      option_ids: optionIds,
      criteria: criteria
    });
  }
}

class WorkflowClient extends BaseClient {
  async getWorkflows(params = {}) {
    return this.get('/api/enterprise/workflows', params);
  }

  async getWorkflow(workflowId) {
    return this.get(`/api/enterprise/workflows/${workflowId}`);
  }

  async createWorkflow(workflowData) {
    return this.post('/api/enterprise/workflows', workflowData);
  }

  async updateWorkflow(workflowId, workflowData) {
    return this.put(`/api/enterprise/workflows/${workflowId}`, workflowData);
  }

  async deleteWorkflow(workflowId) {
    return this.delete(`/api/enterprise/workflows/${workflowId}`);
  }

  async executeWorkflow(workflowId, inputs = {}) {
    return this.post(`/api/enterprise/workflows/${workflowId}/execute`, {
      inputs: inputs
    });
  }

  async getWorkflowStatus(executionId) {
    return this.get(`/api/enterprise/workflows/executions/${executionId}`);
  }

  async cancelWorkflowExecution(executionId) {
    return this.post(`/api/enterprise/workflows/executions/${executionId}/cancel`);
  }
}

class EnterpriseClient {
  constructor(baseURL, apiKey, options = {}) {
    this.knowledgeGraph = new KnowledgeGraphClient(baseURL, apiKey, options);
    this.archimate = new ArchimateClient(baseURL, apiKey, options);
    this.capabilities = new CapabilityClient(baseURL, apiKey, options);
    this.vendors = new VendorClient(baseURL, apiKey, options);
    this.applications = new ApplicationClient(baseURL, apiKey, options);
    this.options = new OptionsClient(baseURL, apiKey, options);
    this.workflows = new WorkflowClient(baseURL, apiKey, options);
  }
}

// Export for different environments
if (typeof module !== 'undefined' && module.exports) {
  // Node.js/CommonJS
  module.exports = { EnterpriseClient, EnterpriseSDKError };
} else if (typeof define === 'function' && define.amd) {
  // AMD
  define([], function() {
    return { EnterpriseClient, EnterpriseSDKError };
  });
} else if (typeof window !== 'undefined') {
  // Browser global
  window.EnterpriseSDK = { EnterpriseClient, EnterpriseSDKError };
}
