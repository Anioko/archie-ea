/**
 * RATX-006: Rationalization Tracking Alpine component
 *
 * Portfolio-level outcomes: dependency risk table, retirement sequence.
 */
'use strict';

function trackingApp() {
    const baseUrl = '/applications/rationalization/api';

    return {
        /* ── Dependency Risk state ────────────────────── */
        depResults: [],
        depLoading: false,
        depPage: 1,
        depTotalPages: 1,
        depRiskFilter: '',

        /* ── Retirement Sequence state ────────────────── */
        retWaves: [],
        retLoading: false,

        /* ── RATA-012: Import state ─────────────────── */
        showImportModal: false,
        importFile: null,
        importPreview: [],
        importLoading: false,
        importResult: null,

        /* ── Load dependency risk ─────────────────────── */
        loadDependencyRisk: function() {
            const self = this;
            self.depLoading = true;

            const params = new URLSearchParams();
            params.set('page', self.depPage);
            params.set('per_page', 25);
            if (self.depRiskFilter) params.set('risk_level', self.depRiskFilter);

            fetch(baseUrl + '/portfolio-dependencies?' + params.toString(), {
                headers: { 'Accept': 'application/json' }
            })
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                self.depResults = (data.applications || data.dependencies || []).map(function(d) {
                    return {
                        id: d.application_id || d.id,
                        name: d.application_name || d.name || 'Unknown',
                        blocker_count: d.blocker_count || d.total_blockers || 0,
                        critical_count: d.critical_blocker_count || d.critical_blockers || 0,
                        downstream_count: d.downstream_count || d.downstream_apps || 0,
                        risk_level: d.risk_level || 'unknown'
                    };
                });
                self.depTotalPages = data.total_pages || Math.ceil((data.total || self.depResults.length) / 25) || 1;
                self.depLoading = false;
            })
            .catch(function(err) {
                console.error('Dependency risk load failed:', err);
                self.depLoading = false;
                self.depResults = [];
            });
        },

        /* ── Load benefits (placeholder for future) ───── */
        loadBenefits: function() {
            /* Benefits data comes from server-side context (financial_summary).
               Future enhancement: load per-app benefits table from API. */
        },

        /* ── RATA-012: Handle import file ───────────── */
        handleImportFile: function(event) {
            const self = this;
            const file = event.target.files[0];
            if (!file) return;
            self.importFile = file;

            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const text = e.target.result;
                    let data;
                    if (file.name.endsWith('.json')) {
                        const parsed = JSON.parse(text);
                        data = parsed.dependencies || parsed;
                    } else {
                        // CSV parsing (simple)
                        const lines = text.split('\n').filter(function(l) { return l.trim(); });
                        if (lines.length < 2) { self.importPreview = []; return; }
                        const headers = lines[0].split(',').map(function(h) { return h.trim().replace(/"/g, ''); });
                        data = [];
                        for (let i = 1; i < lines.length; i++) {
                            const vals = lines[i].split(',').map(function(v) { return v.trim().replace(/"/g, ''); });
                            const obj = {};
                            headers.forEach(function(h, idx) { obj[h] = vals[idx] || ''; });
                            obj.source_app_id = parseInt(obj.source_app_id) || 0;
                            obj.target_app_id = parseInt(obj.target_app_id) || 0;
                            data.push(obj);
                        }
                    }
                    self.importPreview = Array.isArray(data) ? data.slice(0, 10) : [];
                } catch (err) {
                    console.error('Import parse error:', err);
                    self.importPreview = [];
                }
            };
            reader.readAsText(file);
        },

        submitImport: function() {
            const self = this;
            self.importLoading = true;
            let csrfToken = document.querySelector('meta[name="csrf-token"]');
            csrfToken = csrfToken ? csrfToken.getAttribute('content') : '';

            if (self.importFile && self.importFile.name.endsWith('.csv')) {
                const formData = new FormData();
                formData.append('file', self.importFile);
                fetch('/applications/rationalization/api/dependencies/import', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData
                })
                .then(function(r) { return r.json(); })
                .then(function(data) { self.importResult = data; self.importLoading = false; })
                .catch(function(err) { self.importResult = { success: false, error: err.message }; self.importLoading = false; });
            } else {
                // JSON import — reconstruct full array from preview source
                const reader = new FileReader();
                reader.onload = function(e) {
                    try {
                        const parsed = JSON.parse(e.target.result);
                        const deps = parsed.dependencies || parsed;
                        fetch('/applications/rationalization/api/dependencies/import', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify({ dependencies: deps })
                        })
                        .then(function(r) { return r.json(); })
                        .then(function(data) { self.importResult = data; self.importLoading = false; })
                        .catch(function(err) { self.importResult = { success: false, error: err.message }; self.importLoading = false; });
                    } catch (err) {
                        self.importResult = { success: false, error: 'Invalid JSON' };
                        self.importLoading = false;
                    }
                };
                reader.readAsText(self.importFile);
            }
        },

        /* ── Load retirement sequence ─────────────────── */
        loadRetirementSequence: function() {
            const self = this;
            self.retLoading = true;

            fetch(baseUrl + '/retirement-sequence', {
                headers: { 'Accept': 'application/json' }
            })
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                self.retWaves = (data.waves || data.sequence || []).map(function(wave) {
                    return {
                        apps: (wave.applications || wave.apps || []).map(function(a) {
                            return { id: a.id || a.application_id, name: a.name || a.application_name || 'Unknown' };
                        })
                    };
                });
                self.retLoading = false;
            })
            .catch(function(err) {
                console.error('Retirement sequence load failed:', err);
                self.retLoading = false;
                self.retWaves = [];
            });
        }
    };
}
