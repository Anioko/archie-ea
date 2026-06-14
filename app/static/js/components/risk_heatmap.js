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
            this.saveError = '';
            const url = `/api/solution-risks/${this.editRisk.id}`;
            try {
                const csrfToken = document.querySelector('[name=csrf_token]')?.value || '';
                const resp = await fetch(url, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        probability: this.editRisk.probability,
                        impact: this.editRisk.impact,
                        status: this.editRisk.status,
                        owner: this.editRisk.owner,
                        mitigation: this.editRisk.mitigation,
                    }),
                });
                if (resp.ok) {
                    const idx = this.risks.findIndex(r => r.id === this.editRisk.id);
                    if (idx !== -1) this.risks[idx] = { ...this.editRisk };
                    this.editOpen = false;
                } else {
                    this.saveError = `Save failed (${resp.status})`;
                }
            } catch (e) {
                this.saveError = 'Network error — please try again';
                console.error('Risk save error:', e);
            }
        },
    };
}
