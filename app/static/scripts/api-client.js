/**
 * API Client - Standardized API v1 Client
 *
 * Implements PRD-003: API Response Standardization
 * Provides a standardized client for consuming the v1 API endpoints
 */

class APIClient {
    constructor(baseURL = '/api/v1') {
        this.baseURL = baseURL;
    }

    /**
     * Get CSRF token from meta tag
     */
    getCSRFToken() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : '';
    }

    /**
     * Make a request to the API
     * @param {string} endpoint - API endpoint (e.g., '/applications')
     * @param {Object} options - Request options
     * @returns {Promise} - Response data
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken(),
            'Accept': 'application/json',
            ...options.headers
        };

        const config = {
            method: 'GET',
            headers,
            ...options
        };

        // Add body for POST/PUT requests
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            // Check for API error responses
            if (!data.success) {
                const error = new Error(data.error?.message || 'API request failed');
                error.code = data.error?.code || 'API_ERROR';
                error.details = data.error?.details;
                error.status = response.status;
                throw error;
            }

            return data.data;
        } catch (error) {
            // Handle network errors or API errors
            console.error('API Request Error:', error);
            throw error;
        }
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @returns {Promise} - Response data
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;

        return this.request(url, {
            method: 'GET'
        });
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {Object} body - Request body
     * @returns {Promise} - Response data
     */
    async post(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body
        });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {Object} body - Request body
     * @returns {Promise} - Response data
     */
    async put(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body
        });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @returns {Promise} - Response data
     */
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    /**
     * Handle API errors consistently
     * @param {Error} error - The error object
     * @param {Function} callback - Optional callback for custom error handling
     */
    handleError(error, callback = null) {
        if (callback) {
            callback(error);
        } else {
            // Default error handling
            const message = error.message || 'An unexpected error occurred';

            // Show user-friendly error message
            if (typeof window !== 'undefined' && window.alert) {
                alert(message);
            }

            // Log detailed error for debugging
            console.error('API Error Details:', {
                message: error.message,
                code: error.code,
                details: error.details,
                status: error.status
            });
        }
    }
}

// Applications API methods
class ApplicationsAPI extends APIClient {
    constructor() {
        super('/api/v1/applications');
    }

    async getApplications(params = {}) {
        return this.get('/', params);
    }

    async getApplication(id) {
        return this.get(`/${id}`);
    }

    async createApplication(data) {
        return this.post('/', data);
    }

    async updateApplication(id, data) {
        return this.put(`/${id}`, data);
    }

    async deleteApplication(id) {
        return this.delete(`/${id}`);
    }
}

// Vendors API methods
class VendorsAPI extends APIClient {
    constructor() {
        super('/api/v1/vendors');
    }

    async getVendors(params = {}) {
        return this.get('/', params);
    }

    async getVendor(id) {
        return this.get(`/${id}`);
    }

    async createVendor(data) {
        return this.post('/', data);
    }

    async updateVendor(id, data) {
        return this.put(`/${id}`, data);
    }

    async deleteVendor(id) {
        return this.delete(`/${id}`);
    }
}

// Capabilities API methods
class CapabilitiesAPI extends APIClient {
    constructor() {
        super('/api/v1/capabilities');
    }

    async getCapabilities(params = {}) {
        return this.get('/', params);
    }

    async getCapability(id) {
        return this.get(`/${id}`);
    }

    async getManufacturingCapabilities(params = {}) {
        return this.get('/manufacturing', params);
    }

    async getDomains() {
        return this.get('/domains');
    }

    async getLevels() {
        return this.get('/levels');
    }
}

// Enterprise API methods
class EnterpriseAPI extends APIClient {
    constructor() {
        super('/api/v1/enterprise');
    }

    async getCanvas() {
        return this.get('/canvas');
    }

    async updateCanvas(data) {
        return this.post('/canvas', data);
    }

    async getCapabilities() {
        return this.get('/capabilities');
    }

    async getMetrics() {
        return this.get('/metrics');
    }
}

// Dashboard API methods
class DashboardAPI extends APIClient {
    constructor() {
        super('/api/v1/dashboard');
    }

    async getApplicationsTableData(params = {}) {
        return this.get('/applications/table-data', params);
    }

    async getMetrics() {
        return this.get('/metrics');
    }

    async getWidgets() {
        return this.get('/widgets');
    }
}

// Mappings API methods
class MappingsAPI extends APIClient {
    constructor() {
        super('/api/v1/mappings');
    }

    // Technical to Vendor Product Mappings
    async getTechnicalToVendorMappings(params = {}) {
        return this.get('/technical-to-vendor', params);
    }

    async getTechnicalToVendorMapping(id) {
        return this.get(`/technical-to-vendor/${id}`);
    }

    async createTechnicalToVendorMapping(data) {
        return this.post('/technical-to-vendor', data);
    }

    async updateTechnicalToVendorMapping(id, data) {
        return this.put(`/technical-to-vendor/${id}`, data);
    }

    async deleteTechnicalToVendorMapping(id) {
        return this.delete(`/technical-to-vendor/${id}`);
    }

    // Unified Capability to Application Mappings
    async getUnifiedToApplicationMappings(params = {}) {
        return this.get('/unified-to-application', params);
    }

    async getUnifiedToApplicationMapping(id) {
        return this.get(`/unified-to-application/${id}`);
    }

    async createUnifiedToApplicationMapping(data) {
        return this.post('/unified-to-application', data);
    }

    async updateUnifiedToApplicationMapping(id, data) {
        return this.put(`/unified-to-application/${id}`, data);
    }

    async deleteUnifiedToApplicationMapping(id) {
        return this.delete(`/unified-to-application/${id}`);
    }

    // Unified Capability to Vendor Organization Mappings
    async getUnifiedToVendorOrgMappings(params = {}) {
        return this.get('/unified-to-vendor-org', params);
    }

    async getUnifiedToVendorOrgMapping(id) {
        return this.get(`/unified-to-vendor-org/${id}`);
    }

    async createUnifiedToVendorOrgMapping(data) {
        return this.post('/unified-to-vendor-org', data);
    }

    async updateUnifiedToVendorOrgMapping(id, data) {
        return this.put(`/unified-to-vendor-org/${id}`, data);
    }

    async deleteUnifiedToVendorOrgMapping(id) {
        return this.delete(`/unified-to-vendor-org/${id}`);
    }

    // Application to Vendor Product Mappings
    async getApplicationToVendorMappings(params = {}) {
        return this.get('/application-to-vendor', params);
    }

    async getApplicationToVendorMapping(id) {
        return this.get(`/application-to-vendor/${id}`);
    }

    async createApplicationToVendorMapping(data) {
        return this.post('/application-to-vendor', data);
    }

    async updateApplicationToVendorMapping(id, data) {
        return this.put(`/application-to-vendor/${id}`, data);
    }

    async deleteApplicationToVendorMapping(id) {
        return this.delete(`/application-to-vendor/${id}`);
    }

    // Analytics & Summary
    async getMappingsSummary() {
        return this.get('/summary');
    }

    async getTechnicalCapabilityCoverage() {
        return this.get('/coverage/technical-capabilities');
    }
}

// Create global API instances
const api = new APIClient();
const applicationsAPI = new ApplicationsAPI();
const vendorsAPI = new VendorsAPI();
const capabilitiesAPI = new CapabilitiesAPI();
const enterpriseAPI = new EnterpriseAPI();
const dashboardAPI = new DashboardAPI();
const mappingsAPI = new MappingsAPI();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        APIClient,
        ApplicationsAPI,
        VendorsAPI,
        CapabilitiesAPI,
        EnterpriseAPI,
        DashboardAPI,
        MappingsAPI,
        api,
        applicationsAPI,
        vendorsAPI,
        capabilitiesAPI,
        enterpriseAPI,
        dashboardAPI,
        mappingsAPI
    };
} else {
    // Browser environment
    window.APIClient = APIClient;
    window.ApplicationsAPI = ApplicationsAPI;
    window.VendorsAPI = VendorsAPI;
    window.CapabilitiesAPI = CapabilitiesAPI;
    window.EnterpriseAPI = EnterpriseAPI;
    window.DashboardAPI = DashboardAPI;
    window.MappingsAPI = MappingsAPI;
    window.api = api;
    window.applicationsAPI = applicationsAPI;
    window.vendorsAPI = vendorsAPI;
    window.capabilitiesAPI = capabilitiesAPI;
    window.enterpriseAPI = enterpriseAPI;
    window.dashboardAPI = dashboardAPI;
    window.mappingsAPI = mappingsAPI;
}
