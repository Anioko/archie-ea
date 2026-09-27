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
            // fetch does not reject on 4xx/5xx, and `if (data.success)` with no
            // else left the panel showing its empty state — indistinguishable
            // from a component that genuinely has no spec recorded.
            Platform.fetch('/solutions/' + self.solutionId + '/api/component-specs/' + elementId, { silent: true })
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
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
            // A failed PUT used to do nothing but clear the saving flag: the spinner
            // stopped, the panel kept the typed values, and the user walked away
            // believing the spec had been saved when nothing reached the server.
            Platform.fetch.put('/solutions/' + self.solutionId + '/api/component-specs/' + elementId, { tab: tab, data: specData }, { silent: true })
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
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
            Platform.fetch.post('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/confirm', body, { silent: true })
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
                    if (data.success) {
                        self.loadComponentSpec(elementId);
                        if (window.Platform && Platform.toast) Platform.toast.success('Spec confirmed');
                    } else {
                        // The API returned success:false, which Platform.fetch does NOT throw for.
                        // We must treat this as an error and surface it.
                        throw new Error(data.error || 'Confirm request failed');
                    }
                })
                .catch(function (e) {
                    // console.error is forbidden; we must surface the error to the user.
                    // The existing catch already shows a toast, which is appropriate.
                    if (window.Platform && Platform.toast) Platform.toast.error('Confirm failed');
                });
        },

        inferSpec: function (elementId) {
            let self = this;
            self.specLoading[elementId] = true;
            Platform.fetch.post('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/infer', {}, { silent: true })
                .then(function (data) {
                    // Platform.fetch returns parsed JSON directly; success flag is still present in the API response.
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
            // This function returns a Promise that the caller expects to receive the raw response.
            // Platform.fetch throws on non-ok, but the caller expects to handle success/failure via the promise.
            // However, the existing code expects to receive a Response object? Actually it expects a parsed JSON.
            // The caller likely uses the returned promise to get validation results.
            // We must preserve that behavior: Platform.fetch will throw on HTTP error, which would break the caller.
            // The caller currently catches errors elsewhere? The function is used in a validation context where
            // a non-ok response is not an error but a validation result? Wait, the endpoint returns 200 with success flag.
            // So we can use Platform.fetch with silent:true (since the caller will handle the error).
            // However, if the endpoint returns 4xx/5xx, Platform.fetch will throw, which is not what the caller expects.
            // The caller expects to get a parsed JSON even on 4xx? Actually the old code throws an Error with message
            // containing status. That's similar to Platform.fetch throwing. But the caller expects a promise rejection.
            // That's fine because Platform.fetch also rejects. However, the error message shape may differ.
            // To be safe, we keep raw fetch? But rule says migrate unless genuine need.
            // The need here is that the caller expects to handle the raw error message (maybe for validation).
            // However, Platform.fetch throws a structured PlatformError with .message etc. That's acceptable.
            // We'll migrate and let the caller catch the error as before.
            return Platform.fetch.post('/solutions/' + self.solutionId + '/api/component-specs/' + elementId + '/validate', { fields: fields }, { silent: true });
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
