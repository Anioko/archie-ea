/**
 * RATX-005: Rationalization Planning Alpine component
 *
 * Per-app planning page with 5 lazy-loaded tabs:
 * Overview, Options, Replacement, Retirement, Overrides
 */
'use strict';

function planningApp() {
    const appId = window.__PLANNING_APP_ID__;
    let csrfToken = document.querySelector('meta[name="csrf-token"]');
    csrfToken = csrfToken ? csrfToken.getAttribute('content') : '';
    const baseUrl = '/applications/rationalization/api';

    return {
        appId: appId,
        activeTab: 'overview',
        reviewStatus: null,

        tabData: { overview: null, options: null, replacement: null, retirement: null, overrides: null },
        tabLoading: { overview: false, options: false, replacement: false, retirement: false, overrides: false },
        tabLoaded: { overview: false, options: false, replacement: false, retirement: false, overrides: false },

        replacementForm: {
            replacement_type: '', estimated_cost: '', planned_start_date: '',
            planned_cutover_date: '', business_risk_level: '', estimated_savings_annual: ''
        },
        savingReplacement: false,

        overrideForm: { disposition: '', rationale: '', expiry: '' },

        /* ── RATA-004: Score this app ────────────────── */
        isScoringApp: false,
        score: null,
        dataQuality: null,

        /* ── RATA-007: Evidence/breakdown data ───────── */
        evidenceData: null,
        scoreRadarChart: null,

        switchTab: function(tab) {
            this.activeTab = tab;
            if (!this.tabLoaded[tab]) {
                this.loadTab(tab);
            }
        },

        loadTab: function(tab) {
            const self = this;
            self.tabLoading[tab] = true;

            let fetches = [];
            if (tab === 'overview') {
                fetches = [
                    fetch(baseUrl + '/decision-dossier/' + appId, { headers: { 'Accept': 'application/json' } }).then(function(r) { return r.ok ? r.json() : {}; }),
                    fetch(baseUrl + '/evidence-trail/' + appId, { headers: { 'Accept': 'application/json' } }).then(function(r) { return r.ok ? r.json() : {}; })
                ];
                Promise.all(fetches).then(function(results) {
                    const evidenceRaw = results[1] || {};

                    self.tabData.overview = {
                        dossier_html: results[0].dossier_html || results[0].summary || JSON.stringify(results[0], null, 2),
                        evidence: evidenceRaw.dimensions || evidenceRaw.evidence || []
                    };

                    // RATA-007: Build evidence breakdown data
                    const scores = evidenceRaw.scores || {};
                    self.evidenceData = {
                        time_action: evidenceRaw.time_action || evidenceRaw.rationalization_action || null,
                        disposition_confidence: evidenceRaw.disposition_confidence || null,
                        confidence_reasons: evidenceRaw.confidence_reasons || [],
                        dimension_summary: [
                            { name: 'technical', label: 'Technical Health', score: Math.round(scores.technical_health || 0) },
                            { name: 'business', label: 'Business Value', score: Math.round(scores.business_value || 0) },
                            { name: 'cost', label: 'Cost Efficiency', score: Math.round(scores.cost_efficiency || 0) },
                            { name: 'vendor', label: 'Vendor Risk', score: Math.round(scores.vendor_risk || 0) }
                        ],
                        readiness_dimensions: (evidenceRaw.readiness || {}).dimensions || {},
                        evidence_trail: (evidenceRaw.evidence_trail || []).map(function(dim) {
                            return {
                                dimension: dim.dimension || dim.name || '—',
                                score: Math.round(dim.score || dim.weighted_contribution || 0),
                                sub_factors: (dim.sub_factors || dim.factors || []).map(function(f) {
                                    return {
                                        name: f.factor || f.name || '—',
                                        raw_value: f.raw_value != null ? f.raw_value : '—',
                                        contribution: f.contribution || f.points || 0,
                                        source: f.source || f.field || ''
                                    };
                                })
                            };
                        })
                    };

                    self.tabLoading.overview = false;
                    self.tabLoaded.overview = true;

                    // Render radar chart after DOM update
                    self.$nextTick(function() { self.renderScoreRadar(); });
                }).catch(function(err) {
                    console.error('Overview load failed:', err);
                    self.tabLoading.overview = false;
                    self.tabLoaded.overview = true;
                    self.tabData.overview = { dossier_html: '<p>Failed to load dossier.</p>', evidence: [] };
                });

            } else if (tab === 'options') {
                fetch(baseUrl + '/arb-status/' + appId, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.ok ? r.json() : {}; })
                .then(function(data) {
                    self.tabData.options = data;
                    self.tabLoading.options = false;
                    self.tabLoaded.options = true;
                }).catch(function() { self.tabLoading.options = false; self.tabLoaded.options = true; self.tabData.options = {}; });

            } else if (tab === 'replacement') {
                fetch(baseUrl + '/replacement-plan/' + appId, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.ok ? r.json() : {}; })
                .then(function(data) {
                    if (data && data.replacement_type) {
                        self.replacementForm.replacement_type = data.replacement_type || '';
                        self.replacementForm.estimated_cost = data.estimated_cost || '';
                        self.replacementForm.planned_start_date = data.planned_start_date || '';
                        self.replacementForm.planned_cutover_date = data.planned_cutover_date || '';
                        self.replacementForm.business_risk_level = data.business_risk_level || '';
                        self.replacementForm.estimated_savings_annual = data.estimated_savings_annual || '';
                    }
                    self.tabLoading.replacement = false;
                    self.tabLoaded.replacement = true;
                }).catch(function() { self.tabLoading.replacement = false; self.tabLoaded.replacement = true; });

            } else if (tab === 'retirement') {
                Promise.all([
                    fetch(baseUrl + '/retirement-blockers/' + appId, { headers: { 'Accept': 'application/json' } }).then(function(r) { return r.ok ? r.json() : {}; }),
                    fetch(baseUrl + '/dependency-impact/' + appId, { headers: { 'Accept': 'application/json' } }).then(function(r) { return r.ok ? r.json() : {}; })
                ]).then(function(results) {
                    self.tabData.retirement = { blockers: results[0].blockers || [], impact: results[1] };
                    self.tabLoading.retirement = false;
                    self.tabLoaded.retirement = true;
                }).catch(function() { self.tabLoading.retirement = false; self.tabLoaded.retirement = true; self.tabData.retirement = { blockers: [], impact: null }; });

            } else if (tab === 'overrides') {
                fetch(baseUrl + '/override/' + appId, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.ok ? r.json() : {}; })
                .then(function(data) {
                    self.tabData.overrides = data;
                    self.tabLoading.overrides = false;
                    self.tabLoaded.overrides = true;
                }).catch(function() { self.tabLoading.overrides = false; self.tabLoaded.overrides = true; self.tabData.overrides = {}; });
            }
        },

        /* ── RATA-007: Render radar chart ────────────── */
        renderScoreRadar: function() {
            if (!this.evidenceData || typeof Chart === 'undefined') return;
            const ctx = document.getElementById('scoreRadarChart');
            if (!ctx) return;
            if (this.scoreRadarChart) this.scoreRadarChart.destroy();

            const dims = this.evidenceData.dimension_summary;
            this.scoreRadarChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: dims.map(function(d) { return d.label; }),
                    datasets: [{
                        label: 'Score',
                        data: dims.map(function(d) { return d.score; }),
                        backgroundColor: 'rgba(59, 130, 246, 0.15)',
                        borderColor: 'rgba(59, 130, 246, 0.8)',
                        borderWidth: 2,
                        pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        r: { min: 0, max: 100, ticks: { stepSize: 25, display: false }, grid: { color: 'rgba(128,128,128,0.15)' } }
                    },
                    plugins: { legend: { display: false } }
                }
            });

            // Re-init lucide icons for readiness indicators
            if (window.lucide) window.lucide.createIcons();
        },

        /* ── RATA-004: Score this app ────────────────── */
        scoreThisApp: function() {
            const self = this;
            self.isScoringApp = true;
            fetch(baseUrl + '/score/' + appId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success && data.score) {
                    self.score = data.score;
                    self.dataQuality = data.data_quality;
                    // Reload overview tab to refresh breakdown
                    self.tabLoaded.overview = false;
                    self.loadTab('overview');
                }
            })
            .catch(function(err) { console.error('App scoring failed:', err); })
            .finally(function() { self.isScoringApp = false; });
        },

        transitionReview: function(newStatus) {
            const self = this;
            fetch(baseUrl + '/review/' + appId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ new_status: newStatus })
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success || data.status) {
                    self.reviewStatus = newStatus;
                } else {
                    Platform.toast.error('Transition failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) { console.error('Review transition error:', err); });
        },

        saveReplacementPlan: function() {
            const self = this;
            self.savingReplacement = true;
            fetch(baseUrl + '/replacement-plan/' + appId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(self.replacementForm)
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.savingReplacement = false;
                if (data.success || data.id) {
                    Platform.toast.success('Replacement plan saved.');
                } else {
                    Platform.toast.error('Save failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) { self.savingReplacement = false; console.error('Save error:', err); });
        },

        submitToARB: function() {
            const self = this;
            fetch(baseUrl + '/arb-submit/' + appId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    self.tabLoaded.options = false;
                    self.loadTab('options');
                } else {
                    Platform.toast.error('ARB submission failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) { console.error('ARB submit error:', err); });
        },

        saveOverride: function() {
            const self = this;
            fetch(baseUrl + '/override/' + appId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(self.overrideForm)
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    self.tabLoaded.overrides = false;
                    self.loadTab('overrides');
                } else {
                    Platform.toast.error('Override failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) { console.error('Override error:', err); });
        },

        removeOverride: async function() {
            const self = this;
            if (!(await Platform.modal.confirm('Remove this disposition override?'))) return;
            fetch(baseUrl + '/override/' + appId, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': csrfToken }
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    self.tabLoaded.overrides = false;
                    self.loadTab('overrides');
                }
            })
            .catch(function(err) { console.error('Remove override error:', err); });
        }
    };
}
