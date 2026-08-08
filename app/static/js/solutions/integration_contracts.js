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
            fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId)
                // fetch does not reject on 4xx/5xx, and `if (data.success)` with no
                // else left the panel showing its empty state — indistinguishable
                // from a component that genuinely has no contracts recorded.
                .then(function (r) {
                    if (!r.ok) { throw new Error('HTTP ' + r.status); }
                    return r.json();
                })
                .then(function (data) {
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.integrationContracts[elementId] = data.data;
                    self.contractLoading[elementId] = false;
                })
                .catch(function (e) {
                    self.contractLoading[elementId] = false;
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not load integration contracts: ' + (e.message || 'request failed'));
                    }
                });
        },

        saveIntegrationContract: function (elementId, targetId, contract) {
            let self = this;
            self.contractSaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ target_element_id: targetId, contract: contract })
            })
            // A failed PUT used to do nothing but clear the saving flag: no toast,
            // no revert, so the user saw the spinner stop and assumed the contract
            // had been saved when nothing reached the server.
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (data) {
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
            fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/suggest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (data) {
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
            return fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) {
                if (!r.ok) { throw new Error('validate integration contract request failed: ' + r.status); }
                return r.json();
            });
        },

        toggleContractExpanded: function (elementId) {
            this.contractExpanded[elementId] = !this.contractExpanded[elementId];
            if (this.contractExpanded[elementId] && !this.integrationContracts[elementId]) {
                this.loadIntegrationContracts(elementId);
            }
        }
    };
}
