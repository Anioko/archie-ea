let APP_CONFIG = window.__APP_CONFIG__ || {};

function duplicateDetection() {
    return {
        showRunDetectionModal: false,
        isRunningDetection: false,
        isLoading: true,
        stats: {
            total_groups: 0,
            total_estimated_savings: 0,
            high_priority_groups: 0,
            last_run_date: 'Never',
            last_run_summary: 'Run detection to generate results'
        },
        allGroups: [],
        currentPage: 1,
        perPage: 20,
        sortColumn: 'estimated_savings',
        sortDirection: 'desc',
        filters: {
            search: '',
            type: '',
            status: '',
            risk: ''
        },
        detectionConfig: {
            strategy: 'hybrid',
            similarity_threshold: 0.60,
            run_name: 'Duplicate Detection'
        },
        runFeedback: {
            status: '',
            title: '',
            message: '',
            run_id: null,
            run_name: '',
            groups_found: 0,
            exact_matches: 0,
            fuzzy_matches: 0,
            applications_analyzed: 0,
            estimated_savings: 0,
            duration_seconds: null
        },
        runElapsedSeconds: 0,
        runProgressMessage: '',
        runFeedbackTimer: null,

        init() {
            this.loadStats();
            this.loadGroups();
            this.$nextTick(function() { lucide.createIcons(); });
        },

        clearRunFeedback() {
            this.stopRunFeedbackTimer();
            this.runFeedback = {
                status: '',
                title: '',
                message: '',
                run_id: null,
                run_name: '',
                groups_found: 0,
                exact_matches: 0,
                fuzzy_matches: 0,
                applications_analyzed: 0,
                estimated_savings: 0,
                duration_seconds: null
            };
            this.runElapsedSeconds = 0;
            this.runProgressMessage = '';
        },

        stopRunFeedbackTimer() {
            if (this.runFeedbackTimer) {
                clearInterval(this.runFeedbackTimer);
                this.runFeedbackTimer = null;
            }
        },

        startRunFeedback() {
            this.stopRunFeedbackTimer();
            this.runElapsedSeconds = 0;
            this.runProgressMessage = 'Preparing applications for comparison...';

            let thresholdValue = parseFloat(this.detectionConfig.similarity_threshold || 0.6);
            if (isNaN(thresholdValue)) {
                thresholdValue = 0.6;
            }

            this.runFeedback = {
                status: 'running',
                title: 'Detection is running',
                message: this.getStrategyLabel(this.detectionConfig.strategy) +
                    ' at ' + Math.round(thresholdValue * 100) + '% threshold. Results will appear automatically when complete.',
                run_id: null,
                run_name: this.detectionConfig.run_name || '',
                groups_found: 0,
                exact_matches: 0,
                fuzzy_matches: 0,
                applications_analyzed: 0,
                estimated_savings: 0,
                duration_seconds: null
            };

            let self = this;
            this.runFeedbackTimer = setInterval(function() {
                self.runElapsedSeconds += 1;
                if (self.runElapsedSeconds < 8) {
                    self.runProgressMessage = 'Preparing applications for comparison...';
                } else if (self.runElapsedSeconds < 20) {
                    self.runProgressMessage = 'Computing exact and fuzzy matches...';
                } else {
                    self.runProgressMessage = 'Scoring groups and calculating estimated savings...';
                }
            }, 1000);
        },

        getFilteredGroups() {
            let groups = this.allGroups.slice();
            let self = this;

            if (this.filters.search) {
                let term = this.filters.search.toLowerCase();
                groups = groups.filter(function(g) {
                    return (g.name || '').toLowerCase().includes(term) ||
                        (g.description || '').toLowerCase().includes(term);
                });
            }
            if (this.filters.type) {
                let filterType = this.filters.type;
                groups = groups.filter(function(g) { return g.duplicate_type === filterType; });
            }
            if (this.filters.status) {
                let filterStatus = this.filters.status;
                groups = groups.filter(function(g) { return g.status === filterStatus; });
            }
            if (this.filters.risk) {
                let filterRisk = this.filters.risk;
                groups = groups.filter(function(g) { return g.risk_level === filterRisk; });
            }

            if (this.sortColumn) {
                groups.sort(function(a, b) {
                    let aVal = a[self.sortColumn];
                    let bVal = b[self.sortColumn];
                    if (typeof aVal === 'string') aVal = (aVal || '').toLowerCase();
                    if (typeof bVal === 'string') bVal = (bVal || '').toLowerCase();
                    aVal = aVal || 0;
                    bVal = bVal || 0;
                    if (aVal < bVal) return self.sortDirection === 'asc' ? -1 : 1;
                    if (aVal > bVal) return self.sortDirection === 'asc' ? 1 : -1;
                    return 0;
                });
            }

            return groups;
        },

        paginatedGroups() {
            let filtered = this.getFilteredGroups();
            let start = (this.currentPage - 1) * this.perPage;
            return filtered.slice(start, start + this.perPage);
        },

        totalPages() {
            return Math.max(1, Math.ceil(this.getFilteredGroups().length / this.perPage));
        },

        sortBy(column) {
            if (this.sortColumn === column) {
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortColumn = column;
                this.sortDirection = 'asc';
            }
            this.currentPage = 1;
        },

        applyFilters() {
            this.currentPage = 1;
        },

        typeBadgeClass(type) {
            let map = {
                'exact': 'bg-green-500/10 text-emerald-600 border border-green-500/30',
                'fuzzy': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'functional': 'bg-blue-500/10 text-primary border border-blue-500/30',
                'technical': 'bg-purple-500/10 text-primary border border-purple-500/30',
                'capability': 'bg-cyan-500/10 text-cyan-600 border border-cyan-500/30'
            };
            return map[type] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        statusBadgeClass(status) {
            let map = {
                'pending': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'reviewing': 'bg-blue-500/10 text-primary border border-blue-500/30',
                'approved': 'bg-green-500/10 text-emerald-600 border border-green-500/30',
                'resolved': 'bg-green-500/10 text-emerald-600 border border-green-500/30',
                'ignored': 'bg-slate-500/10 text-slate-600 border border-slate-500/30'
            };
            return map[status] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        riskBadgeClass(risk) {
            let map = {
                'high': 'bg-red-500/10 text-destructive border border-red-500/30',
                'medium': 'bg-amber-500/10 text-amber-600 border border-amber-500/30',
                'low': 'bg-green-500/10 text-emerald-600 border border-green-500/30'
            };
            return map[risk] || 'bg-slate-500/10 text-slate-600 border border-slate-500/30';
        },

        async loadStats() {
            try {
                let response = await fetch('/duplicate-detection/simple/api/statistics');
                let data = await response.json();
                let self = this;
                let latestRun = data.latest_run || null;
                let groupsFound = latestRun && latestRun.groups_found != null ? latestRun.groups_found : 0;
                let lastRunSummary = 'Run detection to generate results';

                if (latestRun) {
                    if ((latestRun.status || '').toLowerCase() !== 'completed') {
                        lastRunSummary = 'Last run status: ' + self.formatRunStatus(latestRun.status);
                    } else if (groupsFound === 0) {
                        lastRunSummary = 'Last run found no duplicate groups';
                    } else {
                        lastRunSummary = 'Last run found ' + groupsFound + ' duplicate group' + (groupsFound === 1 ? '' : 's');
                    }
                }

                this.stats = {
                    total_groups: data.total_groups || 0,
                    total_estimated_savings: data.total_estimated_savings || 0,
                    high_priority_groups: data.high_priority_groups || 0,
                    last_run_date: latestRun ? self.formatDate(latestRun.created_at) : 'Never',
                    last_run_summary: lastRunSummary
                };
                this.$nextTick(function() { lucide.createIcons(); });
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        },

        async loadGroups() {
            this.isLoading = true;
            try {
                let response = await fetch('/duplicate-detection/simple/api/groups');
                let data = await response.json();
                this.allGroups = data.groups || [];
                this.currentPage = 1;
                this.$nextTick(function() { lucide.createIcons(); });
            } catch (error) {
                console.error('Error loading groups:', error);
            } finally {
                this.isLoading = false;
            }
        },

        async runDetection() {
            this.isRunningDetection = true;
            this.showRunDetectionModal = false;
            this.startRunFeedback();
            let threshold = parseFloat(this.detectionConfig.similarity_threshold);
            if (isNaN(threshold)) {
                threshold = 0.6;
            }

            try {
                let response = await fetch('/duplicate-detection/simple/api/run-detection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        method: this.detectionConfig.strategy || 'hybrid',
                        threshold: threshold,
                        run_name: this.detectionConfig.run_name || ''
                    })
                });
                let data = await response.json();

                if (data.success) {
                    await this.loadStats();
                    await this.loadGroups();
                    let feedbackMessage = data.message || 'Duplicate detection finished successfully.';
                    if (data.warning) {
                        feedbackMessage += ' ' + data.warning;
                    }
                    this.runFeedback = {
                        status: 'success',
                        title: 'Detection completed',
                        message: feedbackMessage,
                        run_id: data.run_id || null,
                        run_name: this.detectionConfig.run_name || '',
                        groups_found: data.groups_found != null ? data.groups_found : 0,
                        exact_matches: data.exact_matches != null ? data.exact_matches : 0,
                        fuzzy_matches: data.fuzzy_matches != null ? data.fuzzy_matches : 0,
                        applications_analyzed: data.applications_analyzed != null ? data.applications_analyzed : 0,
                        estimated_savings: data.estimated_savings != null ? data.estimated_savings : 0,
                        duration_seconds: data.duration_seconds != null ? data.duration_seconds : this.runElapsedSeconds
                    };
                } else {
                    this.runFeedback = {
                        status: 'error',
                        title: 'Detection failed',
                        message: data.error || data.message || 'Unknown error',
                        run_id: null,
                        run_name: '',
                        groups_found: 0,
                        exact_matches: 0,
                        fuzzy_matches: 0,
                        applications_analyzed: 0,
                        estimated_savings: 0,
                        duration_seconds: null
                    };
                }
            } catch (error) {
                console.error('Error running detection:', error);
                this.runFeedback = {
                    status: 'error',
                    title: 'Detection failed',
                    message: error.message || 'Unexpected error occurred',
                    run_id: null,
                    run_name: '',
                    groups_found: 0,
                    exact_matches: 0,
                    fuzzy_matches: 0,
                    applications_analyzed: 0,
                    estimated_savings: 0,
                    duration_seconds: null
                };
            } finally {
                this.isRunningDetection = false;
                this.stopRunFeedbackTimer();
                this.$nextTick(function() { lucide.createIcons(); });
            }
        },

        async addToConsolidation(groupId) {
            let self = this;
            let modalId = window.modalManager.createModal({
                title: 'Add to Consolidation List',
                content: '<p class="text-sm text-muted-foreground">Add all applications from this group to the consolidation list?</p>',
                size: 'small',
                buttons: [
                    { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                    { text: 'Add to List', class: 'px-4 py-2 text-sm font-medium text-primary-foreground bg-primary border border-transparent rounded-md hover:bg-primary/90', action: 'add', handler: async function() {
                        try {
                            let response = await fetch('/duplicate-detection/api/groups/' + groupId + '/add-to-consolidation', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'include'
                            });
                            let data = await response.json();
                            if (data.success) {
                                let msg = 'Added ' + (data.added_count || 0) + ' application(s) to consolidation list' +
                                    (data.skipped_count ? ' (' + data.skipped_count + ' already listed)' : '');
                                alert(msg);
                                await self.loadGroups();
                            } else {
                                alert('Error: ' + (data.error || 'Unknown error'));
                            }
                        } catch (error) {
                            console.error('Error adding to consolidation:', error);
                            alert('Failed to add to consolidation: ' + error.message);
                        }
                    } }
                ]
            });
            window.modalManager.open(modalId);
        },

        async dismissGroup(groupId) {
            let self = this;
            let modalId = window.modalManager.createModal({
                title: 'Dismiss Group',
                content: '<p class="text-sm text-muted-foreground">Are you sure you want to dismiss this group? It will be marked as ignored.</p>',
                size: 'small',
                buttons: [
                    { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                    { text: 'Dismiss', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'dismiss', handler: async function() {
                        try {
                            let response = await fetch('/duplicate-detection/api/groups/' + groupId + '/ignore', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'include'
                            });
                            let data = await response.json();
                            if (data.success) {
                                self.allGroups = self.allGroups.filter(function(g) { return g.id !== groupId; });
                                await self.loadStats();
                            } else {
                                alert('Error: ' + (data.error || 'Unknown error'));
                            }
                        } catch (error) {
                            console.error('Error dismissing group:', error);
                            alert('Failed to dismiss group: ' + error.message);
                        }
                    } }
                ]
            });
            window.modalManager.open(modalId);
        },

        formatNumber(num) {
            if (!num) return '0';
            return new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 }).format(num);
        },

        formatPercent(num) {
            if (!num) return '0%';
            return Math.round(num * 100) + '%';
        },

        formatDate(dateString) {
            if (!dateString) return 'N/A';
            let date = new Date(dateString);
            return date.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' });
        },

        formatRunStatus(status) {
            if (!status) return 'Unknown';
            return status.charAt(0).toUpperCase() + status.slice(1);
        },

        getStrategyLabel(strategy) {
            let strategyMap = {
                hybrid: 'Hybrid detection',
                fast: 'Fast detection',
                enhanced: 'Enhanced detection'
            };
            return strategyMap[strategy] || 'Duplicate detection';
        },

        formatDuration(totalSeconds) {
            let seconds = Number(totalSeconds || 0);
            if (seconds <= 0) {
                return '<1s';
            }
            if (seconds < 60) {
                return seconds + 's';
            }
            let minutes = Math.floor(seconds / 60);
            let remainingSeconds = seconds % 60;
            return minutes + 'm ' + remainingSeconds + 's';
        }
    };
}
