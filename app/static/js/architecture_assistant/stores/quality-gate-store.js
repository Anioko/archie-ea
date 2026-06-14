/**
 * Quality Gate Alpine Store — manages step quality assessment state.
 *
 * Used by the quality gate overlay to show scores, dimensions, and
 * failing items. Talks to /api/wizard/<solution_id>/quality/* routes.
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('qualityGate', {
        // State
        loading: false,
        visible: false,
        assessment: null,
        canAdvance: true,
        error: null,

        // Current context
        solutionId: null,
        currentStep: null,

        init() {
            // Initialized by journey_v2 component
        },

        /**
         * Assess quality for the current step.
         * @param {number} solutionId
         * @param {number} step
         * @param {object} stepData — current step fields
         * @returns {Promise<object>} assessment result
         */
        async assess(solutionId, step, stepData) {
            this.solutionId = solutionId;
            this.currentStep = step;
            this.loading = true;
            this.error = null;

            try {
                const resp = await fetch(`/api/wizard/${solutionId}/quality/assess`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({ step, step_data: stepData }),
                });

                const json = await resp.json();
                const data = json.data || json;

                this.assessment = data;
                this.canAdvance = data.passed || !data.hard_block;
                this.visible = true;
                return data;

            } catch (e) {
                console.error('Quality gate assessment failed:', e);
                this.error = 'Quality assessment unavailable';
                // Degrade gracefully — allow advancement
                this.canAdvance = true;
                return null;
            } finally {
                this.loading = false;
            }
        },

        /**
         * Check if advancement is allowed.
         */
        async checkAdvance(solutionId, step, stepData) {
            this.solutionId = solutionId;
            this.currentStep = step;
            this.loading = true;

            try {
                const resp = await fetch(`/api/wizard/${solutionId}/quality/can-advance`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({ step, step_data: stepData }),
                });

                // Detect session timeout (302 redirect to login returns HTML)
                const contentType = resp.headers.get('content-type') || '';
                if (!contentType.includes('application/json') || resp.status === 401 || resp.status === 403) {
                    if (resp.redirected || !contentType.includes('json')) {
                        window.location.href = '/account/login';
                        return false;
                    }
                }

                const json = await resp.json();
                const data = json.data || json;

                this.assessment = data.assessment;
                this.canAdvance = data.can_advance;

                // Show overlay if not passing
                if (this.assessment && !this.assessment.passed) {
                    this.visible = true;
                }

                return data.can_advance;

            } catch (e) {
                console.error('Can-advance check failed:', e);
                // If the error looks like a login redirect (HTML response), redirect
                if (e.message && e.message.includes('JSON')) {
                    window.location.href = '/account/login';
                    return false;
                }
                this.canAdvance = true;
                return true;
            } finally {
                this.loading = false;
            }
        },

        /**
         * Record that user skipped a soft-block gate.
         */
        async recordSkip() {
            if (!this.assessment || !this.solutionId) return;

            try {
                await fetch(`/api/wizard/${this.solutionId}/quality/skip`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                    },
                    body: JSON.stringify({
                        step: this.currentStep,
                        overall_score: this.assessment.overall_score,
                        threshold: this.assessment.threshold,
                    }),
                });
            } catch (e) {
                console.error('Failed to record quality skip:', e);
            }

            this.dismiss();
        },

        /**
         * Dismiss the overlay.
         */
        dismiss() {
            this.visible = false;
            this.assessment = null;
        },

        // Computed helpers for the template
        get scoreColor() {
            if (!this.assessment) return 'text-muted-foreground';
            if (this.assessment.passed) return 'text-emerald-600';
            if (this.assessment.overall_score >= this.assessment.threshold - 10) return 'text-amber-600';
            return 'text-destructive';
        },

        get scorePercentage() {
            return this.assessment?.overall_score || 0;
        },

        get failingItems() {
            return this.assessment?.failing_items || [];
        },

        get dimensions() {
            return this.assessment?.dimensions || [];
        },

        get isHardBlock() {
            return this.assessment?.hard_block && !this.assessment?.passed;
        },
    });
});
