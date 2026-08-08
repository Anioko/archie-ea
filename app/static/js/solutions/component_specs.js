/**
 * solutions/component_specs.js
 * Alpine.js mixin for Component Specification panels.
 * Merged into blueprintPage() via Object.assign pattern.
 *
 * API base: /solutions/<id>/api/component-specs/<elementId>
 */

function componentSpecsMixin() {
    return {
        componentSpecs: {},
        specLoading: {},
        specSaving: {},
        specExpanded: {},
        activeSpecTab: {},

        loadComponentSpec: function (elementId) {
            let self = this;
            self.specLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId)
                // fetch does not reject on 4xx/5xx, and `if (data.success)` with no
                // else left the panel showing its empty state — indistinguishable
                // from a component that genuinely has no spec recorded.
                .then(function (r) {
                    if (!r.ok) { throw new Error('HTTP ' + r.status); }
                    return r.json();
                })
                .then(function (data) {
                    if (!data.success) { throw new Error(data.error || 'Request failed'); }
                    self.componentSpecs[elementId] = data.data;
                    self.specLoading[elementId] = false;
                })
                .catch(function (e) {
                    self.specLoading[elementId] = false;
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error('Could not load the component spec: ' + (e.message || 'request failed'));
                    }
                });
        },

        saveComponentSpec: function (elementId, tab, specData) {
            let self = this;
            self.specSaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ tab: tab, data: specData })
            })
            // A failed PUT used to do nothing but clear the saving flag: the spinner
            // stopped, the panel kept the typed values, and the user walked away
            // believing the spec had been saved when nothing reached the server.
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (data) {
                if (!data.success) { throw new Error(data.error || 'Request failed'); }
                self.specSaving[elementId] = false;
                self.loadComponentSpec(elementId);
            })
            .catch(function (e) {
                self.specSaving[elementId] = false;
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Component spec NOT saved: ' + (e.message || 'request failed'));
                }
            });
        },

        confirmSpec: function (elementId, tab, ruleId) {
            let self = this;
            const body = { tab: tab };
            if (ruleId) { body.rule_id = ruleId; }
            fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify(body)
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadComponentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Spec confirmed');
                }
            })
            .catch(function (e) {
                console.error('[component_specs] confirmSpec error:', e);
                if (window.Platform && Platform.toast) Platform.toast.error('Confirm failed');
            });
        },

        inferSpec: function (elementId) {
            let self = this;
            self.specLoading[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/infer', {
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
                self.specLoading[elementId] = false;
                self.loadComponentSpec(elementId);
                if (window.Platform && Platform.toast) Platform.toast.success('Fields inferred');
            })
            .catch(function (e) {
                self.specLoading[elementId] = false;
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Could not infer fields: ' + (e.message || 'request failed'));
                }
            });
        },

        validateSpec: function (elementId, fields) {
            let self = this;
            return fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ fields: fields })
            })
            .then(function (r) {
                if (!r.ok) { throw new Error('validate spec request failed: ' + r.status); }
                return r.json();
            });
        },

        toggleSpecExpanded: function (elementId) {
            this.specExpanded[elementId] = !this.specExpanded[elementId];
            if (this.specExpanded[elementId] && !this.componentSpecs[elementId]) {
                this.loadComponentSpec(elementId);
            }
        },

        setSpecTab: function (elementId, tab) {
            this.activeSpecTab[elementId] = tab;
        }
    };
}
