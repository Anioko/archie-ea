/**
 * solutions/integration_contracts.js
 * Alpine.js mixin for Integration Contract panels.
 * Merged into blueprintPage() via Object.assign pattern.
 *
 * API base: /solutions/<id>/api/integration-contracts/<elementId>
 */

function integrationContractsMixin() {
    return {
        integrationContracts: {},
        contractLoading: {},
        contractSaving: {},
        contractExpanded: {},

        loadIntegrationContracts: function (elementId) {
            let self = this;
            self.contractLoading[elementId] = true;
            // Platform.fetch throws on non‑ok responses, and returns the parsed body directly.
            // The wrapper also shows a user‑visible error toast automatically.
            // We keep the existing inline error handling (toast) which matches the original behaviour.
            Platform.fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId)
                .then(function (data) {
                    // Platform.fetch succeeded, but the API still returns a {success, data, error} envelope.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.integrationContracts[elementId] = data.data;
                    self.contractLoading[elementId] = false;
                })
                .catch(function (e) {
                    self.contractLoading[elementId] = false;
                    // Platform.fetch already shows a toast for non‑silent errors, but the original code
                    // also displayed a custom message. To avoid duplicate toasts we pass silent:true
                    // and keep the original toast.
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not load integration contracts: ' + (e.message || 'request failed'));
                    }
                });
        },

        saveIntegrationContract: function (elementId, targetId, contract) {
            let self = this;
            self.contractSaving[elementId] = true;
            // Platform.fetch automatically injects CSRF token for PUT, serialises plain‑object body to JSON,
            // and throws on non‑ok responses. We keep the original comment about the defect.
            // A failed PUT used to do nothing but clear the saving flag: no toast,
            // no revert, so the user saw the spinner stop and assumed the contract
            // had been saved when nothing reached the server.
            Platform.fetch.put('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId,
                { target_element_id: targetId, contract: contract },
                { silent: true }  // suppress automatic toast because we show our own below
            )
                .then(function (data) {
                    // Platform.fetch succeeded, but the API still returns a {success, data, error} envelope.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.contractSaving[elementId] = false;
                    self.loadIntegrationContracts(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Contract saved');
                })
                .catch(function (e) {
                    self.contractSaving[elementId] = false;
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Contract NOT saved: ' + (e.message || 'request failed'));
                    }
                });
        },

        suggestIntegrationContract: function (elementId) {
            let self = this;
            self.contractLoading[elementId] = true;
            // Platform.fetch.post automatically injects CSRF token, serialises plain‑object body,
            // and throws on non‑ok responses. We keep the original error handling.
            Platform.fetch.post('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/suggest',
                {},
                { silent: true }  // suppress automatic toast because we show our own below
            )
                .then(function (data) {
                    // Platform.fetch succeeded, but the API still returns a {success, data, error} envelope.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.contractLoading[elementId] = false;
                    self.loadIntegrationContracts(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Contract suggested');
                })
                .catch(function (e) {
                    self.contractLoading[elementId] = false;
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not suggest a contract: ' + (e.message || 'request failed'));
                    }
                });
        },

        validateIntegrationContract: function (elementId) {
            let self = this;
            // Platform.fetch.post automatically injects CSRF token, serialises plain‑object body,
            // and throws on non‑ok responses. The caller expects a Promise that resolves to the parsed JSON
            // (or rejects with a PlatformError). We must not swallow the error; let it propagate.
            return Platform.fetch.post('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/validate',
                {},
                { silent: true }  // suppress automatic toast because the caller likely handles errors inline
            )
                .then(function (data) {
                    // Platform.fetch succeeded, but the API still returns a {success, data, error} envelope.
                    // The original code returned the raw JSON response (including success/error fields).
                    // We preserve that behaviour.
                    return data;
                });
            // Any error thrown by Platform.fetch will propagate to the caller unchanged.
        },

        toggleContractExpanded: function (elementId) {
            this.contractExpanded[elementId] = !this.contractExpanded[elementId];
            if (this.contractExpanded[elementId] && !this.integrationContracts[elementId]) {
                this.loadIntegrationContracts(elementId);
            }
        }
    };
}
