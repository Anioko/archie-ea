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
                const resp = await fetch(`/api/wizard/${solutionId}/copilot/review-field`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({ step, field_name: fieldName, field_value: fieldValue }),
                });

                const json = await resp.json();
                const data = json.data || json;

                if (data.suggestion) {
                    // Replace existing suggestion for this field, or add new
                    const idx = this.suggestions.findIndex(s => s.field_name === fieldName);
                    if (idx >= 0) {
                        this.suggestions[idx] = data.suggestion;
                    } else {
                        this.suggestions.push(data.suggestion);
                    }
                    this.sidebarOpen = true;
                }
            } catch (e) {
                // Non-blocking — don't show errors for field reviews
                console.warn('Copilot field review failed:', e);
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
                const resp = await fetch(`/api/wizard/${solutionId}/copilot/review-step`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({ step, step_data: stepData }),
                });

                const json = await resp.json();
                const data = json.data || json;

                this.suggestions = data.suggestions || [];
                if (this.suggestions.length > 0) {
                    this.sidebarOpen = true;
                }

                return data;

            } catch (e) {
                console.error('Copilot step review failed:', e);
                this.error = 'AI suggestions unavailable';
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
            fetch(`/api/wizard/${this.solutionId}/copilot/accept`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                },
                body: JSON.stringify({
                    suggestion_id: suggestion.suggestion_id,
                    field_name: suggestion.field_name,
                    new_value: suggestion.suggested_value,
                }),
            }).catch(() => {});

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
