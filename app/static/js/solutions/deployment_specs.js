/**
 * solutions/deployment_specs.js
 * Alpine.js mixin for Deployment Specification panels.
 * Merged into blueprintPage() via Object.assign pattern.
 *
 * API base: /solutions/<id>/api/deployment-specs/<elementId>
 */

function deploymentSpecsMixin() {
    return {
        deploymentSpecs: {},
        deployLoading: {},
        deploySaving: {},
        deployExpanded: {},

        loadDeploymentSpec: function (elementId) {
            let self = this;
            self.deployLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId)
                // fetch does not reject on 4xx/5xx, and `if (data.success)` with no
                // else left the panel showing its empty state — indistinguishable
                // from a component that genuinely has no deployment spec.
                .then(function (r) {
                    if (!r.ok) { throw new Error('HTTP ' + r.status); }
                    return r.json();
                })
                .then(function (data) {
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.deploymentSpecs[elementId] = data.data;
                    self.deployLoading[elementId] = false;
                })
                .catch(function (e) {
                    self.deployLoading[elementId] = false;
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not load the deployment spec: ' + (e.message || 'request failed'));
                    }
                });
        },

        saveDeploymentSpec: function (elementId, deployment) {
            let self = this;
            self.deploySaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ deployment: deployment })
            })
            // A failed PUT used to do nothing but clear the saving flag: no toast,
            // no revert, so the user saw the spinner stop and assumed the
            // deployment spec had been saved when nothing reached the server.
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (data) {
                if (!data.success) { throw new Error(data.error || 'Request failed'); }
                self.deploySaving[elementId] = false;
                self.loadDeploymentSpec(elementId);
                if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec saved');
            })
            .catch(function (e) {
                self.deploySaving[elementId] = false;
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Deployment spec NOT saved: ' + (e.message || 'request failed'));
                }
            });
        },

        suggestDeploymentSpec: function (elementId) {
            let self = this;
            self.deployLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/suggest', {
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
                self.deployLoading[elementId] = false;
                self.loadDeploymentSpec(elementId);
                if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec suggested');
            })
            .catch(function (e) {
                self.deployLoading[elementId] = false;
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Could not suggest a deployment spec: ' + (e.message || 'request failed'));
                }
            });
        },

        validateDeploymentSpec: function (elementId) {
            let self = this;
            return fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) {
                if (!r.ok) { throw new Error('validate deployment spec request failed: ' + r.status); }
                return r.json();
            });
        },

        toggleDeployExpanded: function (elementId) {
            this.deployExpanded[elementId] = !this.deployExpanded[elementId];
            if (this.deployExpanded[elementId] && !this.deploymentSpecs[elementId]) {
                this.loadDeploymentSpec(elementId);
            }
        }
    };
}
