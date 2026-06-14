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
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.deploymentSpecs[elementId] = data.data;
                    }
                    self.deployLoading[elementId] = false;
                })
                .catch(function () { self.deployLoading[elementId] = false; });
        },

        saveDeploymentSpec: function (elementId, deployment) {
            let self = this;
            self.deploySaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ deployment: deployment })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadDeploymentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec saved');
                }
                self.deploySaving[elementId] = false;
            })
            .catch(function () { self.deploySaving[elementId] = false; });
        },

        suggestDeploymentSpec: function (elementId) {
            let self = this;
            self.deployLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/suggest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadDeploymentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Deployment spec suggested');
                }
                self.deployLoading[elementId] = false;
            })
            .catch(function () { self.deployLoading[elementId] = false; });
        },

        validateDeploymentSpec: function (elementId) {
            let self = this;
            return fetch('/solutions/' + self.solutionId + '/api/deployment-specs/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({})
            })
            .then(function (r) { return r.json(); });
        },

        toggleDeployExpanded: function (elementId) {
            this.deployExpanded[elementId] = !this.deployExpanded[elementId];
            if (this.deployExpanded[elementId] && !this.deploymentSpecs[elementId]) {
                this.loadDeploymentSpec(elementId);
            }
        }
    };
}
