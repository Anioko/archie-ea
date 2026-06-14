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
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.componentSpecs[elementId] = data.data;
                    }
                    self.specLoading[elementId] = false;
                })
                .catch(function () { self.specLoading[elementId] = false; });
        },

        saveComponentSpec: function (elementId, tab, specData) {
            let self = this;
            self.specSaving[elementId] = true;
            fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ tab: tab, data: specData })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadComponentSpec(elementId);
                }
                self.specSaving[elementId] = false;
            })
            .catch(function () { self.specSaving[elementId] = false; });
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
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.loadComponentSpec(elementId);
                    if (window.Platform && Platform.toast) Platform.toast.success('Fields inferred');
                }
                self.specLoading[elementId] = false;
            })
            .catch(function () { self.specLoading[elementId] = false; });
        },

        validateSpec: function (elementId, fields) {
            let self = this;
            return fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': self.csrfToken },
                body: JSON.stringify({ fields: fields })
            })
            .then(function (r) { return r.json(); });
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
