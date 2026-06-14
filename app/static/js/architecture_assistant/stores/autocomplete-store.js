/**
 * Auto-Complete Alpine Store — manages bulk field completion state.
 *
 * Shows a review modal where users can accept/reject/edit each
 * AI-generated field completion. Triggered by quality gate "Auto-fix"
 * or the copilot "Auto-complete step" button.
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('autocomplete', {
        // State
        loading: false,
        visible: false,
        completions: [],
        fieldsCompleted: 0,
        fieldsSkipped: 0,
        qualityDelta: 0,
        error: null,

        // Selection state — tracks which completions user has accepted
        selected: {},  // { field_path: true/false }

        // Context
        solutionId: null,
        currentStep: null,

        /**
         * Run auto-complete for a step (fills all weak fields).
         */
        async completeStep(solutionId, step, stepData, fieldsToComplete) {
            this.solutionId = solutionId;
            this.currentStep = step;
            this.loading = true;
            this.error = null;

            try {
                const resp = await fetch(`/api/wizard/${solutionId}/autocomplete/step`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({
                        step,
                        step_data: stepData,
                        fields_to_complete: fieldsToComplete || null,
                    }),
                });

                const json = await resp.json();
                const data = json.data || json;

                this.completions = data.completions || [];
                this.fieldsCompleted = data.fields_completed || 0;
                this.fieldsSkipped = data.fields_skipped || 0;
                this.qualityDelta = data.estimated_quality_delta || 0;

                // Pre-select all completions
                this.selected = {};
                for (const c of this.completions) {
                    this.selected[c.field_path] = true;
                }

                if (this.completions.length > 0) {
                    this.visible = true;
                }

                return data;

            } catch (e) {
                console.error('Auto-complete failed:', e);
                this.error = 'Auto-complete unavailable';
                return null;
            } finally {
                this.loading = false;
            }
        },

        /**
         * Auto-fix: triggered from quality gate overlay.
         * Only completes the failing field paths.
         */
        async autoFix(solutionId, step, stepData, failingPaths) {
            return this.completeStep(solutionId, step, stepData, failingPaths);
        },

        /**
         * Toggle selection for a specific field.
         */
        toggleField(fieldPath) {
            this.selected[fieldPath] = !this.selected[fieldPath];
        },

        /**
         * Select all completions.
         */
        selectAll() {
            for (const c of this.completions) {
                this.selected[c.field_path] = true;
            }
        },

        /**
         * Deselect all completions.
         */
        deselectAll() {
            for (const c of this.completions) {
                this.selected[c.field_path] = false;
            }
        },

        /**
         * Apply accepted completions to the journey state.
         */
        async applySelected() {
            if (!this.solutionId) return;

            const accepted = {};
            for (const c of this.completions) {
                if (this.selected[c.field_path]) {
                    accepted[c.field_path] = c.completed_value;
                }
            }

            const rejectedCount = this.completions.length - Object.keys(accepted).length;

            if (Object.keys(accepted).length === 0) {
                this.dismiss();
                return;
            }

            this.loading = true;
            try {
                await fetch(`/api/wizard/${this.solutionId}/autocomplete/apply`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({ accepted_fields: accepted }),
                });

                // Dispatch event so journey component can refresh its state
                window.dispatchEvent(new CustomEvent('autocomplete-applied', {
                    detail: {
                        accepted,
                        accepted_count: Object.keys(accepted).length,
                        rejected_count: rejectedCount,
                    },
                }));

            } catch (e) {
                console.error('Failed to apply completions:', e);
            } finally {
                this.loading = false;
                this.dismiss();
            }
        },

        /**
         * Dismiss the review modal.
         */
        dismiss() {
            this.visible = false;
            this.completions = [];
            this.selected = {};
        },

        // Computed helpers
        get selectedCount() {
            return Object.values(this.selected).filter(Boolean).length;
        },

        get totalCount() {
            return this.completions.length;
        },
    });
});
