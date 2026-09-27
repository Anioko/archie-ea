/**
 * Copilot Alpine Store — real-time field-level AI suggestions.
 *
 * Provides debounced field review and batch "Enhance All" for wizard steps.
 * Suggestions appear in a collapsible sidebar panel.
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('copilot', {
        // State
        loading: false,
        sidebarOpen: false,
        suggestions: [],
        error: null,

        // Debounce tracking
        _debounceTimer: null,
        _lastField: null,

        // Context
        solutionId: null,

        /**
         * Debounced field review — call on field input/change.
         * Waits 2s after last keystroke before calling API.
         */
        reviewFieldDebounced(solutionId, step, fieldName, fieldValue) {
            this.solutionId = solutionId;
            clearTimeout(this._debounceTimer);
            this._lastField = fieldName;

            const self = this;
            this._debounceTimer = setTimeout(() => {
                if (self._lastField !== fieldName) return;
                self.reviewField(solutionId, step, fieldName, fieldValue);
            }, 2000);
        },

        /**
         * Immediate single field review.
         */
        async reviewField(solutionId, step, fieldName, fieldValue) {
            if (!fieldValue || fieldValue.length < 3) return;

            try {
                // fetch-guard-ok: unsolicited background advisory fired 2s after typing; a failure adds nothing the user must act on
                const data = await Platform.fetch.post(`/api/wizard/${solutionId}/copilot/review-field`, {
                    step,
                    field_name: fieldName,
                    field_value: fieldValue,
                }, { silent: true });

                const suggestion = data.data || data;
                if (suggestion.suggestion) {
                    // Replace existing suggestion for this field, or add new
                    const idx = this.suggestions.findIndex(s => s.field_name === fieldName);
                    if (idx >= 0) {
                        this.suggestions[idx] = suggestion.suggestion;
                    } else {
                        this.suggestions.push(suggestion.suggestion);
                    }
                    this.sidebarOpen = true;
                }
            } catch (e) {
                // Non-blocking — don't show errors for field reviews
                // Platform.fetch throws on non-ok responses; we catch and ignore as before
                // No console output allowed: remove the console.warn
                // The failure adds nothing the user must act on
            }
        },

        /**
         * Batch review all fields in current step ("Enhance All").
         */
        async reviewStep(solutionId, step, stepData) {
            this.solutionId = solutionId;
            this.loading = true;
            this.error = null;

            try {
                /* "Enhance All" is something the user clicked. Unguarded, a 500 parsed
                   to `{}`, suggestions stayed empty and the sidebar never opened — the
                   button looked like it had run and found nothing to improve. */
                const data = await Platform.fetch.post(`/api/wizard/${solutionId}/copilot/review-step`, {
                    step,
                    step_data: stepData,
                });
                // Platform.fetch returns parsed data directly
                const result = data.data || data;

                this.suggestions = result.suggestions || [];
                if (this.suggestions.length > 0) {
                    this.sidebarOpen = true;
                }

                return result;

            } catch (e) {
                // Platform.fetch throws on non-ok responses
                this.suggestions = [];
                this.error = 'AI suggestions unavailable';
                // No template renders store.error, so without this the click is silent.
                if (window.Platform && window.Platform.toast) {
                    window.Platform.toast.error('AI review is unavailable right now — no suggestions were generated for this step.');
                }
                return null;
            } finally {
                this.loading = false;
            }
        },

        /**
         * Accept a suggestion — track it and dispatch event for field update.
         */
        async acceptSuggestion(suggestion) {
            if (!this.solutionId) return;

            // Track acceptance
            Platform.fetch.post(`/api/wizard/${this.solutionId}/copilot/accept`, {
                suggestion_id: suggestion.suggestion_id,
                field_name: suggestion.field_name,
                new_value: suggestion.suggested_value,
            }, { silent: true }).catch(() => { /* swallow-ok: acceptance counter for analytics only — the service itself documents "actual field update is handled by frontend", and that update is the dispatched event below, which does not depend on this call. Losing a tally must not interrupt the architect mid-form. */ });

            // Dispatch event for journey component to apply the value
            window.dispatchEvent(new CustomEvent('copilot-accepted', {
                detail: {
                    field_name: suggestion.field_name,
                    value: suggestion.suggested_value,
                },
            }));

            // Remove from list
            this.suggestions = this.suggestions.filter(
                s => s.suggestion_id !== suggestion.suggestion_id,
            );
        },

        /**
         * Reject/dismiss a suggestion.
         */
        rejectSuggestion(suggestion) {
            this.suggestions = this.suggestions.filter(
                s => s.suggestion_id !== suggestion.suggestion_id,
            );
        },

        /**
         * Clear all suggestions (on step change).
         */
        clear() {
            this.suggestions = [];
            clearTimeout(this._debounceTimer);
        },

        /**
         * Toggle sidebar visibility.
         */
        toggle() {
            this.sidebarOpen = !this.sidebarOpen;
        },

        // Computed
        get count() {
            return this.suggestions.length;
        },

        get hasSuggestions() {
            return this.suggestions.length > 0;
        },

        get missingSuggestions() {
            return this.suggestions.filter(s => s.severity === 'missing');
        },

        get weakSuggestions() {
            return this.suggestions.filter(s => s.severity === 'weak');
        },

        get improvementSuggestions() {
            return this.suggestions.filter(s => s.severity === 'improvement');
        },
    });
});
