/**
 * TPM-013: Risk Heat Map Alpine.js component.
 * Renders a 5×5 probability × impact matrix with interactive risk chips.
 */
function riskHeatmap(initialRisks) {
    return {
        risks: Array.isArray(initialRisks) ? initialRisks : [],
        editOpen: false,
        editRisk: {},
        saveError: '',
        saving: false,

        /** Return risks positioned at the given probability and impact cell. */
        risksAt(prob, impact) {
            return this.risks.filter(r => r.probability === prob && r.impact === impact);
        },

        /** Return a Tailwind background class based on the risk score (prob × impact). */
        cellColor(prob, impact) {
            const score = prob * impact;
            if (score >= 16) return 'bg-destructive/10 border-destructive/30 dark:bg-red-900/30 dark:border-red-700';
            if (score >= 9)  return 'bg-orange-100 border-orange-300 dark:bg-orange-900/30 dark:border-orange-700';
            if (score >= 4)  return 'bg-amber-500/10 border-yellow-300 dark:bg-yellow-900/30 dark:border-yellow-700';
            return 'bg-emerald-500/10 border-green-300 dark:bg-green-900/30 dark:border-green-700';
        },

        /** Open the edit modal pre-populated with the given risk. */
        openEdit(risk) {
            this.editRisk = { ...risk };
            this.saveError = '';
            this.editOpen = true;
        },

        /** Persist the edited risk via PATCH and update the local risks array. */
        async saveEdit() {
            if (this.saving) return;
            this.saving = true;
            this.saveError = '';
            const url = `/api/solution-risks/${this.editRisk.id}`;
            try {
                // Platform.fetch.patch automatically injects CSRF token and serializes plain objects to JSON.
                // It throws a structured PlatformError on non-ok responses, which we catch below.
                // We pass { silent: true } because we paint our own inline error state (this.saveError).
                await Platform.fetch.patch(url, {
                    probability: this.editRisk.probability,
                    impact: this.editRisk.impact,
                    status: this.editRisk.status,
                    owner: this.editRisk.owner,
                    mitigation: this.editRisk.mitigation,
                }, { silent: true });
                // If we reach here, the request succeeded (204 No Content returns null).
                const idx = this.risks.findIndex(r => r.id === this.editRisk.id);
                if (idx !== -1) this.risks[idx] = { ...this.editRisk };
                this.editOpen = false;
            } catch (e) {
                // Platform.fetch throws on network errors or non-ok responses.
                // We must surface the failure to the user via this.saveError.
                // Do NOT swallow the error or substitute placeholder data.
                if (e.type === 'HttpError') {
                    // e.status contains the HTTP status code.
                    this.saveError = `Save failed (${e.status})`;
                } else {
                    // NetworkError or other PlatformError.
                    this.saveError = 'Network error — please try again';
                }
                // Do NOT use console.error in shipped code; the error is already surfaced to the user via this.saveError.
            } finally {
                this.saving = false;
            }
        },
    };
}
