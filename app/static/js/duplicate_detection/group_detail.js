let GROUP_CONFIG = window.__GROUP_CONFIG__ || {};

/** Bigram-based string similarity (0–1), equivalent to Python SequenceMatcher. */
function _stringSimilarity(a, b) {
    if (a === b) return 1.0;
    if (a.length < 2 || b.length < 2) return 0.0;
    let bigramsA = {};
    for (let i = 0; i < a.length - 1; i++) {
        let bg = a.substring(i, i + 2);
        bigramsA[bg] = (bigramsA[bg] || 0) + 1;
    }
    let matches = 0;
    for (let j = 0; j < b.length - 1; j++) {
        let bg2 = b.substring(j, j + 2);
        if (bigramsA[bg2] > 0) {
            matches++;
            bigramsA[bg2]--;
        }
    }
    return (2.0 * matches) / ((a.length - 1) + (b.length - 1));
}

function groupDetail() {
    return {
        activeTab: 'confidence',
        selectedApps: [],
        allAppIds: GROUP_CONFIG.appIds || [],
        breakdownBars: [],
        confidence: { loading: false, data: null, error: null },
        mergePreview: { loading: false, data: null, error: null },
        impact: { loading: false, data: null, error: null },

        init() {
            this._initBreakdown();
            this.loadConfidence();
            this.$nextTick(function() { lucide.createIcons(); });
        },

        _initBreakdown() {
            let bd = GROUP_CONFIG.breakdown || {};
            let f = bd.functional || 0;
            let c = bd.capability || 0;
            let t = bd.technical || 0;
            let d = bd.data || 0;

            // If server values are all zero, compute from app metadata
            if (!f && !c && !t && !d) {
                let computed = this._computeBreakdownFromApps(GROUP_CONFIG.applications || []);
                f = computed.functional;
                c = computed.capability;
                t = computed.technical;
                d = computed.data;
            }

            this.breakdownBars = [
                { label: 'Functional', pct: Math.round(f * 100), color: 'bg-primary' },
                { label: 'Capability', pct: Math.round(c * 100), color: 'bg-cyan-500' },
                { label: 'Technical', pct: Math.round(t * 100), color: 'bg-violet-500' },
                { label: 'Data', pct: Math.round(d * 100), color: 'bg-amber-500' }
            ];
        },

        _computeBreakdownFromApps(apps) {
            if (!apps || apps.length < 2) {
                return { functional: 0, capability: 0, technical: 0, data: 0 };
            }
            let funcScores = [], capScores = [], techScores = [], dataScores = [];
            for (let i = 0; i < apps.length; i++) {
                for (let j = i + 1; j < apps.length; j++) {
                    let a = apps[i], b = apps[j];
                    // Functional: name + description similarity
                    let nameSim = _stringSimilarity((a.name || '').toLowerCase(), (b.name || '').toLowerCase());
                    let descA = (a.description || '').toLowerCase();
                    let descB = (b.description || '').toLowerCase();
                    let descSim = (descA && descB) ? _stringSimilarity(descA, descB) : 0;
                    funcScores.push(nameSim * 0.6 + descSim * 0.4);
                    // Capability: deployment status match
                    let statusA = (a.status || '').toLowerCase();
                    let statusB = (b.status || '').toLowerCase();
                    capScores.push((statusA && statusA === statusB) ? 1.0 : 0.0);
                    // Technical: technology stack similarity
                    let techA = (a.technology_stack || '').toLowerCase();
                    let techB = (b.technology_stack || '').toLowerCase();
                    techScores.push((techA && techB) ? _stringSimilarity(techA, techB) : 0);
                    // Data: owner match
                    let ownerA = (a.application_owner || '').toLowerCase();
                    let ownerB = (b.application_owner || '').toLowerCase();
                    dataScores.push((ownerA && ownerA === ownerB) ? 1.0 : 0.0);
                }
            }
            function _avg(arr) { return arr.length ? arr.reduce(function(s, v) { return s + v; }, 0) / arr.length : 0; }
            return {
                functional: _avg(funcScores),
                capability: _avg(capScores),
                technical: _avg(techScores),
                data: _avg(dataScores)
            };
        },

        switchTab(tab) {
            this.activeTab = tab;
            if (tab === 'confidence' && !this.confidence.data && !this.confidence.loading) {
                this.loadConfidence();
            }
            if (tab === 'merge' && !this.mergePreview.data && !this.mergePreview.loading) {
                this.loadMergePreview();
            }
            if (tab === 'impact' && !this.impact.data && !this.impact.loading) {
                this.loadImpact();
            }
            this.$nextTick(function() { lucide.createIcons(); });
        },

        async loadConfidence() {
            this.confidence.loading = true;
            this.confidence.error = null;
            try {
                let response = await Platform.fetch.get(GROUP_CONFIG.confidenceUrl);
                this.confidence.data = response.data || response;
                this.$nextTick(function() { lucide.createIcons(); });
            } catch (error) {
                Platform.log.error('Error loading confidence:', error);
                this.confidence.error = error.message || 'Failed to load confidence analysis';
            } finally {
                this.confidence.loading = false;
            }
        },

        async loadMergePreview() {
            this.mergePreview.loading = true;
            this.mergePreview.error = null;
            try {
                let response = await Platform.fetch.get(GROUP_CONFIG.mergePreviewUrl);
                this.mergePreview.data = response.data || response;
                this.$nextTick(function() { lucide.createIcons(); });
            } catch (error) {
                Platform.log.error('Error loading merge preview:', error);
                this.mergePreview.error = error.message || 'Failed to load merge preview';
            } finally {
                this.mergePreview.loading = false;
            }
        },

        async loadImpact() {
            this.impact.loading = true;
            this.impact.error = null;
            try {
                let response = await Platform.fetch.get(GROUP_CONFIG.impactUrl);
                this.impact.data = response.data || response;
                this.$nextTick(function() { lucide.createIcons(); });
            } catch (error) {
                Platform.log.error('Error loading impact analysis:', error);
                this.impact.error = error.message || 'Failed to load impact analysis';
            } finally {
                this.impact.loading = false;
            }
        },

        toggleSelectApp(appId) {
            let idx = this.selectedApps.indexOf(appId);
            if (idx >= 0) {
                this.selectedApps.splice(idx, 1);
            } else {
                this.selectedApps.push(appId);
            }
        },

        toggleSelectAllApps() {
            if (this.isAllAppsSelected()) {
                this.selectedApps = [];
            } else {
                this.selectedApps = this.allAppIds.slice();
            }
        },

        isAllAppsSelected() {
            return this.allAppIds.length > 0 && this.allAppIds.every(
                function(id) { return this.selectedApps.includes(id); }.bind(this)
            );
        },

        async addToConsolidation() {
            await this._postToConsolidation();
        },

        async addSelectedToConsolidation() {
            if (this.selectedApps.length === 0) return;
            await this._postToConsolidation(this.selectedApps.slice());
        },

        async _postToConsolidation(appIds) {
            try {
                let body = appIds ? { app_ids: appIds } : {};
                let data = await Platform.fetch.post(GROUP_CONFIG.addToConsolidationUrl, body);
                let added = data.added_count || 0;
                let skipped = data.skipped_count || 0;
                if (added > 0) {
                    Platform.toast.success('Added ' + added + ' application(s) to consolidation list');
                    window.location.href = '/consolidation-list/';
                } else if (skipped > 0) {
                    Platform.toast.info('All applications already in consolidation list');
                }
            } catch (error) {
                Platform.log.error('Error adding to consolidation:', error);
                Platform.toast.error('Failed to add to consolidation list');
            }
        },

        async dismissGroup() {
            let self = this;
            let modalId = window.modalManager.createModal({
                title: 'Dismiss Duplicate Group',
                content: '<p class="text-sm text-muted-foreground">Are you sure you want to dismiss this group? It will be marked as ignored and removed from active results.</p>',
                size: 'small',
                buttons: [
                    {
                        text: 'Cancel',
                        class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted',
                        action: 'cancel',
                        handler: function() {}
                    },
                    {
                        text: 'Dismiss',
                        class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90',
                        action: 'dismiss',
                        handler: async function() {
                            try {
                                await Platform.fetch.post(GROUP_CONFIG.ignoreUrl);
                                Platform.toast.success('Group dismissed');
                                window.location.href = GROUP_CONFIG.dashboardUrl;
                            } catch (error) {
                                Platform.log.error('Error dismissing group:', error);
                                Platform.toast.error('Failed to dismiss group');
                            }
                        }
                    }
                ]
            });
            window.modalManager.open(modalId);
        },

        typeBadgeClass(type) {
            let map = {
                'exact': 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30',
                'fuzzy': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'functional': 'bg-blue-500/10 text-primary border border-blue-500/30',
                'technical': 'bg-violet-500/10 text-primary border border-violet-500/30',
                'capability': 'bg-cyan-500/10 text-cyan-600 border border-cyan-500/30'
            };
            return map[type] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        priorityBadgeClass(priority) {
            let map = {
                'high': 'bg-destructive/10 text-destructive border border-destructive/30',
                'medium': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'low': 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30'
            };
            return map[priority] || 'bg-amber-500/10 text-amber-600 border border-amber-500/30';
        },

        riskBadgeClass(risk) {
            let map = {
                'high': 'bg-destructive/10 text-destructive border border-destructive/30',
                'medium': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'low': 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30'
            };
            return map[risk] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        confidenceBadgeClass(level) {
            let map = {
                'high': 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30',
                'medium': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'low': 'bg-destructive/10 text-destructive border border-destructive/30'
            };
            return map[level] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        conflictStatusClass(status) {
            let map = {
                'match': 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30',
                'conflict': 'bg-destructive/10 text-destructive border border-destructive/30',
                'primary_only': 'bg-blue-500/10 text-primary border border-blue-500/30',
                'duplicate_only': 'bg-amber-500/10 text-amber-600 border border-amber-500/30'
            };
            return map[status] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        formatNumber(num) {
            if (!num && num !== 0) return '0';
            return new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 }).format(num);
        },

        formatPercent(num) {
            if (!num && num !== 0) return '0%';
            return Math.round(num * 100) + '%';
        }
    };
}
