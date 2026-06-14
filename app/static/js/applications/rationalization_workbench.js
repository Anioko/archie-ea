/**
 * RATX-004: Rationalization Workbench Alpine component
 *
 * Filter, paginate, select, and bulk-action scored applications.
 */
'use strict';

function workbenchApp() {
    let csrfToken = document.querySelector('meta[name="csrf-token"]');
    csrfToken = csrfToken ? csrfToken.getAttribute('content') : '';

    return {
        /* ── State ────────────────────────────────────── */
        results: [],
        totalCount: 0,
        totalPages: 1,
        page: 1,
        perPage: 200,
        loading: false,
        error: false,

        filters: {
            search: '',
            readiness: '',
            disposition: '',
            reviewStatus: '',
            businessUnit: '',
            lifecycle: '',
            sort: 'health_desc',
            includeUnscored: false
        },

        facets: {
            dispositions: [],
            business_units: [],
            lifecycle_statuses: {}
        },

        selectedIds: {},

        get selectedCount() {
            return Object.keys(this.selectedIds || {}).filter(function(k) { return this.selectedIds[k]; }.bind(this)).length;
        },

        get allSelected() {
            const self = this;
            return self.results.length > 0 && self.results.every(function(r) { return self.selectedIds[r.id]; });
        },

        /* ── Load workbench data ──────────────────────── */
        load: function() {
            const self = this;
            self.loading = true;
            self.error = false;

            const params = new URLSearchParams();
            params.set('page', self.page);
            params.set('per_page', self.perPage);
            if (self.filters.search) params.set('search', self.filters.search);
            if (self.filters.readiness) params.set('readiness', self.filters.readiness);
            if (self.filters.disposition) params.set('disposition', self.filters.disposition);
            if (self.filters.reviewStatus) params.set('review_status', self.filters.reviewStatus);
            if (self.filters.businessUnit) params.set('business_unit', self.filters.businessUnit);
            if (self.filters.lifecycle) params.set('lifecycle', self.filters.lifecycle);
            if (self.filters.includeUnscored) params.set('include_unscored', 'true');
            /* Map JS sort value to API sort_by + sort_dir params */
            if (self.filters.sort) {
                const sortParts = self.filters.sort.match(/^(.+?)_(asc|desc)$/);
                if (sortParts) {
                    params.set('sort_by', sortParts[1]);
                    params.set('sort_dir', sortParts[2]);
                } else {
                    params.set('sort_by', self.filters.sort);
                }
            }

            fetch('/applications/rationalization/api/portfolio-workbench?' + params.toString(), {
                headers: { 'Accept': 'application/json' }
            })
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                const dispDefinitions = {
                    'retain': 'Keep as-is, no action needed',
                    'rehost': 'Move to new infrastructure without code changes',
                    'replatform': 'Move with minor optimizations',
                    'refactor': 'Re-architect for cloud-native or modernization',
                    'replace': 'Substitute with a different product or service',
                    'consolidate': 'Merge functionality into another application',
                    'retire': 'Decommission and remove from portfolio',
                    'insufficient_evidence': 'Not enough data for a recommendation'
                };

                self.results = (data.applications || data.results || []).map(function(app) {
                    const dispKey = (app.disposition_action || '').toLowerCase();
                    let dispLabel = dispKey.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
                    let dispDesc = dispDefinitions[dispKey] || '';
                    const confValue = app.confidence_score || app.disposition_confidence || null;

                    /* RAT-001: Show actionable label when data is missing */
                    if (dispKey === 'insufficient_evidence' && (!confValue || confValue === 'none')) {
                        dispLabel = 'Needs Data Enrichment';
                        dispDesc = 'Enrich this application with cost, owner, and criticality data to enable scoring';
                    }

                    return {
                        id: app.id || app.app_id || app.application_id,
                        name: app.name || app.app_name || app.application_name || 'Unknown',
                        health: app.overall_health_score || 0,
                        disposition_label: app.disposition_label || dispLabel || '—',
                        disposition_desc: dispDesc,
                        is_ready: app.is_decision_ready || false,
                        review_status: app.review_status || 'draft',
                        confidence: confValue,
                        business_unit: app.business_unit || null
                    };
                });

                self.totalCount = data.total || self.results.length;
                self.totalPages = Math.ceil(self.totalCount / self.perPage) || 1;

                if (data.facets) {
                    /* API returns dispositions as {key: count} dict — convert to array */
                    const rawDisp = data.facets.dispositions || {};
                    if (Array.isArray(rawDisp)) {
                        self.facets.dispositions = rawDisp;
                    } else {
                        self.facets.dispositions = Object.keys(rawDisp).map(function(k) {
                            return { value: k, label: k.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); }), count: rawDisp[k] };
                        });
                    }
                    const rawBu = data.facets.business_units || {};
                    if (Array.isArray(rawBu)) {
                        self.facets.business_units = rawBu;
                    } else {
                        self.facets.business_units = Object.keys(rawBu).map(function(k) {
                            return { value: k, label: k, count: rawBu[k] };
                        });
                    }
                    self.facets.lifecycle_statuses = data.facets.lifecycle_statuses || {};
                }

                self.loading = false;

                /* Re-initialize Lucide icons for dynamically rendered content */
                if (window.lucide) {
                    self.$nextTick(function() { window.lucide.createIcons(); });
                }
            })
            .catch(function(err) {
                console.error('Workbench load failed:', err);
                self.loading = false;
                self.error = true;
            });
        },

        /* ── Selection ────────────────────────────────── */
        toggleSelect: function(id) {
            if (this.selectedIds[id]) {
                delete this.selectedIds[id];
            } else {
                this.selectedIds[id] = true;
            }
        },

        toggleAll: function(checked) {
            const self = this;
            if (checked) {
                self.results.forEach(function(r) { self.selectedIds[r.id] = true; });
            } else {
                self.selectedIds = {};
            }
        },

        /* ── Bulk actions ─────────────────────────────── */
        bulkDisposition: '',
        bulkAction: async function(action) {
            const self = this;
            const ids = Object.keys(self.selectedIds).filter(function(k) { return self.selectedIds[k]; }).map(Number);
            if (ids.length === 0) return;

            const labels = { approve: 'Approve', defer: 'Defer', request_data: 'Request Data for', set_disposition: 'Set disposition for' };
            let confirmMsg = (labels[action] || action) + ' ' + ids.length + ' application(s)?';
            if (action === 'set_disposition') {
                if (!self.bulkDisposition) { Platform.toast.warning('Select a disposition first.'); return; }
                confirmMsg = 'Set disposition to "' + self.bulkDisposition + '" for ' + ids.length + ' application(s)?';
            }
            if (!(await Platform.modal.confirm(confirmMsg))) return;

            const payload = { action: action, app_ids: ids };
            if (action === 'set_disposition') payload.disposition = self.bulkDisposition;

            fetch('/applications/rationalization/api/bulk-review', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    self.selectedIds = {};
                    self.bulkDisposition = '';
                    self.load();
                } else {
                    Platform.toast.error('Bulk action failed: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) {
                console.error('Bulk action error:', err);
                Platform.toast.error('Bulk action request failed.');
            });
        },

        /* ── RATA-019: App comparison ────────────────── */
        compareIds: [],
        compareApps: [],
        comparisonRadarChart: null,

        toggleCompare: function(app) {
            const self = this;
            const idx = self.compareIds.indexOf(app.id);
            if (idx >= 0) {
                self.compareIds.splice(idx, 1);
                self.compareApps = self.compareApps.filter(function(ca) { return ca.id !== app.id; });
            } else {
                if (self.compareIds.length >= 4) {
                    Platform.toast.info('Maximum 4 applications can be compared at once.');
                    return;
                }
                self.compareIds.push(app.id);
                // Fetch evidence trail for this app
                fetch('/applications/rationalization/api/evidence-trail/' + app.id, {
                    headers: { 'Accept': 'application/json' }
                })
                .then(function(r) { return r.ok ? r.json() : {}; })
                .then(function(data) {
                    const scores = data.scores || {};
                    self.compareApps.push({
                        id: app.id,
                        name: app.name,
                        dims: {
                            'Technical Health': Math.round(scores.technical_health || 0),
                            'Business Value': Math.round(scores.business_value || 0),
                            'Cost Efficiency': Math.round(scores.cost_efficiency || 0),
                            'Vendor Risk': Math.round(scores.vendor_risk || 0)
                        }
                    });
                    if (self.compareApps.length >= 2) {
                        self.$nextTick(function() { self.renderComparisonChart(); });
                    }
                });
            }
            if (self.compareApps.length >= 2) {
                self.$nextTick(function() { self.renderComparisonChart(); });
            }
        },

        clearComparison: function() {
            this.compareIds = [];
            this.compareApps = [];
            if (this.comparisonRadarChart) { this.comparisonRadarChart.destroy(); this.comparisonRadarChart = null; }
        },

        renderComparisonChart: function() {
            const self = this;
            if (self.compareApps.length < 2 || typeof Chart === 'undefined') return;
            const ctx = document.getElementById('comparisonRadarChart');
            if (!ctx) return;
            if (self.comparisonRadarChart) self.comparisonRadarChart.destroy();

            const colors = [
                { bg: 'rgba(59, 130, 246, 0.15)', border: 'rgba(59, 130, 246, 0.8)' },
                { bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.8)' },
                { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.8)' },
                { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.8)' }
            ];
            const labels = ['Technical Health', 'Business Value', 'Cost Efficiency', 'Vendor Risk'];
            const datasets = self.compareApps.map(function(ca, i) {
                const c = colors[i % colors.length];
                return {
                    label: ca.name,
                    data: labels.map(function(l) { return ca.dims[l] || 0; }),
                    backgroundColor: c.bg,
                    borderColor: c.border,
                    borderWidth: 2,
                    pointRadius: 3
                };
            });

            self.comparisonRadarChart = new Chart(ctx, {
                type: 'radar',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: { r: { min: 0, max: 100, ticks: { stepSize: 25, display: false }, grid: { color: 'rgba(128,128,128,0.15)' } } },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
                }
            });
        },

        /* ── RATA-008: Score breakdown slide-over ──────── */
        breakdownOpen: false,
        breakdownLoading: false,
        breakdownData: null,
        breakdownAppName: null,
        breakdownRadarChart: null,

        openBreakdown: function(appId) {
            const self = this;
            const app = self.results.find(function(r) { return r.id === appId; });
            self.breakdownAppName = app ? app.name : 'Application';
            self.breakdownOpen = true;
            self.breakdownLoading = true;
            self.breakdownData = null;

            fetch('/applications/rationalization/api/evidence-trail/' + appId, {
                headers: { 'Accept': 'application/json' }
            })
            .then(function(r) { return r.ok ? r.json() : {}; })
            .then(function(data) {
                const scores = data.scores || {};
                const dims = [
                    { name: 'technical', label: 'Technical Health', score: Math.round(scores.technical_health || 0) },
                    { name: 'business', label: 'Business Value', score: Math.round(scores.business_value || 0) },
                    { name: 'cost', label: 'Cost Efficiency', score: Math.round(scores.cost_efficiency || 0) },
                    { name: 'vendor', label: 'Vendor Risk', score: Math.round(scores.vendor_risk || 0) }
                ];

                // Extract top 3 factors per dimension
                const topFactors = (data.evidence_trail || []).map(function(dim) {
                    const factors = (dim.sub_factors || dim.factors || [])
                        .sort(function(a, b) { return Math.abs(b.contribution || 0) - Math.abs(a.contribution || 0); })
                        .slice(0, 3)
                        .map(function(f) {
                            return { name: f.factor || f.name || '—', raw_value: f.raw_value, contribution: f.contribution || f.points || 0 };
                        });
                    return { dimension: dim.dimension || dim.name || '—', factors: factors };
                });

                self.breakdownData = { dimensions: dims, top_factors: topFactors };
                self.breakdownLoading = false;

                // Render mini radar
                self.$nextTick(function() {
                    const ctx = document.getElementById('breakdownRadarChart');
                    if (!ctx || typeof Chart === 'undefined') return;
                    if (self.breakdownRadarChart) self.breakdownRadarChart.destroy();
                    self.breakdownRadarChart = new Chart(ctx, {
                        type: 'radar',
                        data: {
                            labels: dims.map(function(d) { return d.label; }),
                            datasets: [{
                                data: dims.map(function(d) { return d.score; }),
                                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                                borderColor: 'rgba(59, 130, 246, 0.8)',
                                borderWidth: 2,
                                pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                                pointRadius: 3
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: true,
                            scales: { r: { min: 0, max: 100, ticks: { stepSize: 25, display: false }, grid: { color: 'rgba(128,128,128,0.15)' } } },
                            plugins: { legend: { display: false } }
                        }
                    });
                });
            })
            .catch(function(err) {
                console.error('Breakdown load failed:', err);
                self.breakdownLoading = false;
            });
        },

        /* ── Navigation ───────────────────────────────── */
        goToPlanning: function(appId) {
            window.location.href = '/applications/rationalization/planning/' + appId;
        }
    };
}
