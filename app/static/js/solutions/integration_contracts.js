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
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.integrationContracts[elementId] = data.data;
                    }
                    self.contractLoading[elementId] = false;
                })
                .catch(function () { self.contractLoading[elementId] = false; });
        },

        saveIntegrationContract: function (elementId, targetId, contract) {
            let self = this;
            self.contractSaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ target_element_id: targetId, contract: contract })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadIntegrationContracts(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Contract saved');
                }
                self.contractSaving[elementId] = false;
            })
            .catch(function () { self.contractSaving[elementId] = false; });
        },

        suggestIntegrationContract: function (elementId) {
            let self = this;
            self.contractLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/suggest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadIntegrationContracts(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Contract suggested');
                }
                self.contractLoading[elementId] = false;
            })
            .catch(function () { self.contractLoading[elementId] = false; });
        },

        validateIntegrationContract: function (elementId) {
            let self = this;
            return fetch('/solutions/' + self.solutionId + '/api/integration-contracts/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); });
        },

        toggleContractExpanded: function (elementId) {
            this.contractExpanded[elementId] = !this.contractExpanded[elementId];
            if (this.contractExpanded[elementId] && !this.integrationContracts[elementId]) {
                this.loadIntegrationContracts(elementId);
            }
        }
    };
}
