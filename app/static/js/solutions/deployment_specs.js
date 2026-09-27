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
            // fetch does not reject on 4xx/5xx, and `if (data.success)` with no
            // else left the panel showing its empty state — indistinguishable
            // from a component that genuinely has no deployment spec.
            Platform.fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId)
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.deploymentSpecs[elementId] = data.data;
                    self.deployLoading[elementId] = false;
                })
                .catch(function (e) {
                    self.deployLoading[elementId] = false;
                    // Platform.fetch already shows a toast unless silent:true; we keep the inline error path.
                    // The toast is already shown, but we still want to surface the failure to the user.
                    // No fallback data is used; the panel will remain empty.
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not load the deployment spec: ' + (e.message || 'request failed'));
                    }
                });
        },

        saveDeploymentSpec: function (elementId, deployment) {
            let self = this;
            self.deploySaving[elementId] = true;
            // A failed PUT used to do nothing but clear the saving flag: no toast,
            // no revert, so the user saw the spinner stop and assumed the
            // deployment spec had been saved when nothing reached the server.
            Platform.fetch.put('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId, { deployment: deployment })
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.deploySaving[elementId] = false;
                    self.loadDeploymentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec saved');
                })
                .catch(function (e) {
                    self.deploySaving[elementId] = false;
                    // Platform.fetch already shows a toast unless silent:true; we keep the inline error path.
                    // The toast is already shown, but we still want to surface the failure to the user.
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Deployment spec NOT saved: ' + (e.message || 'request failed'));
                    }
                });
        },

        suggestDeploymentSpec: function (elementId) {
            let self = this;
            self.deployLoading[elementId] = true;
            Platform.fetch.post('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/suggest', {})
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.deployLoading[elementId] = false;
                    self.loadDeploymentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec suggested');
                })
                .catch(function (e) {
                    self.deployLoading[elementId] = false;
                    // Platform.fetch already shows a toast unless silent:true; we keep the inline error path.
                    // The toast is already shown, but we still want to surface the failure to the user.
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not suggest a deployment spec: ' + (e.message || 'request failed'));
                    }
                });
        },

        validateDeploymentSpec: function (elementId) {
            let self = this;
            // This function returns the parsed JSON directly (or throws) via Platform.fetch.
            // The caller expects a Promise that resolves to the API response (including success flag).
            // We must not swallow errors; Platform.fetch will throw on non-ok responses.
            // The caller is responsible for handling the error (e.g., showing inline error state).
            // Since the caller already paints its own inline error state, we pass { silent: true }
            // to avoid duplicate global toasts.
            return Platform.fetch.post('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/validate', {}, { silent: true });
        },

        toggleDeployExpanded: function (elementId) {
            this.deployExpanded[elementId] = !this.deployExpanded[elementId];
            if (this.deployExpanded[elementId] && !this.deploymentSpecs[elementId]) {
                this.loadDeploymentSpec(elementId);
            }
        }
    };
}
