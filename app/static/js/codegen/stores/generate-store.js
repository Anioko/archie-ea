/**
 * Alpine store: generate — generation progress, quality scoring state.
 * Depends on Alpine.store('codegen') being registered first.
 */
document.addEventListener('alpine:init', function () {
    Alpine.store('generate', {
        /* ── state ── */
        generating: false,
        label: '',         // current phase label from SSE
        elapsed: 0,        // seconds since generation started
        _timer: null,

        promptGroups: ['models', 'schemas', 'routes', 'services', 'integrations', 'tests', 'infrastructure'],
        promptGroupStatus: {},  // { key: 'pending'|'running'|'done'|'error' }

        qualityScore: null,
        qualityDetails: null,

        /* ── timer helpers ── */
        startTimer: function () {
            this.elapsed = 0;
            let self = this;
            this._timer = setInterval(function () { self.elapsed++; }, 1000);
        },

        stopTimer: function () {
            if (this._timer) {
                clearInterval(this._timer);
                this._timer = null;
            }
        },

        /* ── reset prompt group statuses ── */
        resetGroups: function () {
            let self = this;
            this.promptGroups.forEach(function (k) {
                self.promptGroupStatus[k] = 'pending';
            });
        },

        setGroupStatus: function (key, status) {
            this.promptGroupStatus[key] = status;
        },

        /* ── load quality score from server ── */
        loadQuality: async function () {
            let s = Alpine.store('codegen');
            try {
                let data = await s.apiFetch('/solutions/' + s.solutionId + '/codegen/quality');
                this.qualityScore = data.quality_score;
                this.qualityDetails = data.quality_details;
            } catch (_) {
                // Quality is optional — graceful no-op
            }
        },
    });
});
