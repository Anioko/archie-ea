let APP_CONFIG = window.__APP_CONFIG__ || {};

// Market Intelligence Application
let MarketIntel = {
    vendors: [],
    riskAlerts: [],
    trends: [],
    currentTab: 'quadrant',

    init: function() {
        this.setupEventListeners();
        this.loadData();
        lucide.createIcons();
    },

    setupEventListeners: function() {
        let self = this;
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) { self.switchTab(e.target.dataset.tab); });
        });

        // Actions
        document.getElementById('btn-sync-data').addEventListener('click', function() { self.syncData(); });
        document.getElementById('close-vendor-detail').addEventListener('click', function() { self.hideDialog('vendor-detail-dialog'); });

        // Filters
        document.getElementById('filter-risk-severity').addEventListener('change', function() { self.renderRiskAlerts(); });
        document.getElementById('filter-risk-type').addEventListener('change', function() { self.renderRiskAlerts(); });

        // Alternatives
        document.getElementById('current-vendor-select').addEventListener('change', function(e) {
            if (e.target.value) self.loadAlternatives(e.target.value);
        });
    },

    loadData: function() {
        let self = this;
        Promise.all([
            self.loadVendorQuadrant(),
            self.loadRiskAlerts(),
            self.loadTrends()
        ]);
    },

    extractPayload: function(response) {
        if (!response || response.success === false) return null;
        let payload = response.data !== undefined ? response.data : response;
        if (payload && payload.success === true && payload.data !== undefined) {
            payload = payload.data;
        }
        return payload;
    },

    flattenQuadrantVendors: function(quadrantData) {
        if (!quadrantData || typeof quadrantData !== 'object') return [];
        let mapping = {
            leaders: 'leader',
            challengers: 'challenger',
            visionaries: 'visionary',
            niche_players: 'niche'
        };
        let colors = {
            leader: '#0ea5e9',
            challenger: '#f59e0b',
            visionary: '#8b5cf6',
            niche: '#64748b'
        };
        let flattened = [];
        Object.keys(mapping).forEach(function(key) {
            (quadrantData[key] || []).forEach(function(vendor) {
                let quadrant = mapping[key];
                flattened.push({
                    id: vendor.vendor_id,
                    name: vendor.vendor_name,
                    quadrant: quadrant,
                    x: typeof vendor.position_x === 'number' ? vendor.position_x : 50,
                    y: typeof vendor.position_y === 'number' ? vendor.position_y : 50,
                    color: colors[quadrant]
                });
            });
        });
        return flattened;
    },

    normalizeRiskType: function(type) {
        let normalized = String(type || '').toLowerCase();
        let typeMap = {
            stock_price_drop: 'STOCK_DROP',
            acquisition: 'ACQUISITION',
            leadership_change: 'LEADERSHIP_CHANGE',
            financial_downgrade: 'FINANCIAL_DOWNGRADE',
            product_eol: 'PRODUCT_EOL',
            market_share_decline: 'MARKET_SHARE_DECLINE',
            quadrant_change: 'QUADRANT_CHANGE',
            security_incident: 'SECURITY_INCIDENT',
            layoffs: 'LAYOFFS',
            customer_churn: 'CUSTOMER_CHURN'
        };
        return typeMap[normalized] || String(type || 'UNKNOWN').toUpperCase();
    },

    normalizeRiskAlert: function(alert) {
        return {
            id: alert.id || alert.alert_id,
            vendor_id: alert.vendor_id,
            vendor_name: alert.vendor_name,
            type: this.normalizeRiskType(alert.type || alert.alert_type),
            severity: String(alert.severity || 'info').toLowerCase(),
            message: alert.message || alert.description || '',
            created_at: alert.created_at || alert.detected_at || ''
        };
    },

    normalizeTrend: function(trend) {
        return {
            id: trend.id || trend.trend_id,
            name: trend.name || trend.trend_name,
            category: trend.category || 'market',
            impact: trend.impact || trend.impact_level || 'medium',
            description: trend.description || '',
            direction: trend.direction || 'up'
        };
    },

    loadVendorQuadrant: function() {
        let self = this;
        return fetch('/api/market-intelligence/quadrant')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                let payload = self.extractPayload(data);
                let vendors = self.flattenQuadrantVendors(payload && payload.quadrant_data);
                if (!data.success || !Array.isArray(vendors)) {
                    throw new Error(data.error || 'Failed to load vendor quadrant');
                }
                self.vendors = vendors;

                document.getElementById('total-vendors').textContent = self.vendors.length;
                document.getElementById('leaders-count').textContent = self.vendors.filter(function(v) { return v.quadrant === 'leader'; }).length;
                self.renderQuadrant();
                self.renderVendorList();
                self.populateVendorSelect();
            })
            .catch(function(err) {
                console.error('Error loading quadrant:', err);
                self.vendors = [];
                document.getElementById('total-vendors').textContent = '0';
                document.getElementById('leaders-count').textContent = '0';
                self.renderQuadrant();
                self.renderVendorList();
                self.populateVendorSelect();
            });
    },

    renderQuadrant: function() {
        let self = this;
        let cells = {
            'leader': document.querySelector('.quadrant-leaders'),
            'challenger': document.querySelector('.quadrant-challengers'),
            'visionary': document.querySelector('.quadrant-visionaries'),
            'niche': document.querySelector('.quadrant-niche')
        };

        // Clear existing dots
        document.querySelectorAll('.vendor-dot').forEach(function(d) { d.remove(); });

        self.vendors.forEach(function(vendor) {
            let cell = cells[vendor.quadrant];
            if (!cell) return;

            let dot = document.createElement('div');
            dot.className = 'vendor-dot';
            dot.style.backgroundColor = vendor.color || '#3b82f6';

            // Calculate position within cell (0-100 maps to cell dimensions)
            let xValue = typeof vendor.x === 'number' ? vendor.x : 50;
            let yValue = typeof vendor.y === 'number' ? vendor.y : 50;
            let xPercent = (xValue % 50) * 2;
            let yPercent = 100 - ((yValue % 50) * 2);

            dot.style.left = Math.max(10, Math.min(85, xPercent)) + '%';
            dot.style.top = Math.max(20, Math.min(80, yPercent)) + '%';
            dot.textContent = vendor.name.charAt(0);
            dot.title = vendor.name;
            dot.onclick = function() { self.showVendorDetail(vendor.id); };

            cell.appendChild(dot);
        });
    },

    renderVendorList: function() {
        let self = this;
        let container = document.getElementById('vendor-list');
        let grouped = {
            'leader': self.vendors.filter(function(v) { return v.quadrant === 'leader'; }),
            'challenger': self.vendors.filter(function(v) { return v.quadrant === 'challenger'; }),
            'visionary': self.vendors.filter(function(v) { return v.quadrant === 'visionary'; }),
            'niche': self.vendors.filter(function(v) { return v.quadrant === 'niche'; })
        };

        let html = '';
        Object.keys(grouped).forEach(function(quadrant) {
            let vendors = grouped[quadrant];
            if (vendors.length === 0) return;
            html += '<div class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mt-3 mb-2">' + quadrant + 's</div>';
            vendors.forEach(function(v) {
                html += '<div class="p-2 hover:bg-accent rounded-md cursor-pointer flex items-center gap-2" data-action="MarketIntel.showVendorDetail" data-id="' + v.id + '">' +
                    '<div class="w-6 h-6 rounded-full flex items-center justify-center text-primary-foreground text-xs" style="background: ' + v.color + '">' + v.name.charAt(0) + '</div>' +
                    '<span class="text-sm">' + v.name + '</span>' +
                '</div>';
            });
        });
        safeHTML(container, html || '<div class="text-muted-foreground text-sm">No vendors tracked</div>');
    },

    loadRiskAlerts: function() {
        let self = this;
        return fetch('/api/market-intelligence/risk-alerts')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                let payload = self.extractPayload(data);
                let alerts = payload && payload.alerts ? payload.alerts : [];
                if (!data.success || !Array.isArray(alerts)) {
                    throw new Error(data.error || 'Failed to load risk alerts');
                }
                self.riskAlerts = alerts.map(function(alert) {
                    return self.normalizeRiskAlert(alert);
                });

                document.getElementById('risk-alerts').textContent = self.riskAlerts.filter(function(a) { return ['critical', 'high'].indexOf(a.severity) !== -1; }).length;
                self.renderRiskAlerts();
            })
            .catch(function(err) {
                console.error('Error loading risk alerts:', err);
                self.riskAlerts = [];
                document.getElementById('risk-alerts').textContent = '0';
                self.renderRiskAlerts();
            });
    },

    renderRiskAlerts: function() {
        let self = this;
        let severityFilter = document.getElementById('filter-risk-severity').value;
        let typeFilter = document.getElementById('filter-risk-type').value;

        let filtered = self.riskAlerts;
        if (severityFilter) filtered = filtered.filter(function(a) { return a.severity === severityFilter; });
        if (typeFilter) filtered = filtered.filter(function(a) { return a.type === typeFilter; });

        let container = document.getElementById('risk-alerts-list');
        if (filtered.length === 0) {
            safeHTML(container,
                '<div class="p-8 text-center text-muted-foreground">' +
                    '<i data-lucide="check-circle" class="h-8 w-8 mx-auto mb-2 text-emerald-500"></i>' +
                    '<p>No risk alerts matching filters</p>' +
                '</div>');
            lucide.createIcons();
            return;
        }

        safeHTML(container, filtered.map(function(alert) {
            let vendorName = alert.vendor_name || 'Unknown Vendor';
            return '<div class="p-4 hover:bg-accent/50">' +
                '<div class="flex justify-between items-start">' +
                    '<div>' +
                        '<div class="flex items-center gap-2 mb-2">' +
                            '<span class="font-medium">' + vendorName + '</span>' +
                            '<span class="risk-indicator risk-' + alert.severity + '">' + alert.severity + '</span>' +
                            '<span class="px-2 py-1 text-xs bg-muted rounded">' + self.formatAlertType(alert.type) + '</span>' +
                        '</div>' +
                        '<p class="text-sm text-muted-foreground">' + alert.message + '</p>' +
                        '<div class="text-xs text-muted-foreground mt-2">' + alert.created_at + '</div>' +
                    '</div>' +
                    '<button data-action="MarketIntel.viewAlternatives" data-id="' + vendorName + '" class="px-3 py-1 text-sm border border-border rounded-md hover:bg-accent">' +
                        'View Alternatives' +
                    '</button>' +
                '</div>' +
            '</div>';
        }).join(''));
    },

    formatAlertType: function(type) {
        return String(type || 'unknown').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, function(l) { return l.toUpperCase(); });
    },

    loadTrends: function() {
        let self = this;
        return fetch('/api/market-intelligence/trends')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                let payload = self.extractPayload(data);
                let trends = payload && payload.trends ? payload.trends : [];
                if (!data.success || !Array.isArray(trends)) {
                    throw new Error(data.error || 'Failed to load trends');
                }
                self.trends = trends.map(function(trend) {
                    return self.normalizeTrend(trend);
                });

                document.getElementById('market-trends').textContent = self.trends.length;
                self.renderTrends();
            })
            .catch(function(err) {
                console.error('Error loading trends:', err);
                self.trends = [];
                document.getElementById('market-trends').textContent = '0';
                self.renderTrends();
            });
    },

    renderTrends: function() {
        let container = document.getElementById('trends-grid');
        safeHTML(container, this.trends.map(function(trend) {
            let impactColor = trend.impact === 'high' ? 'text-destructive' : trend.impact === 'medium' ? 'text-amber-600' : 'text-emerald-600';
            let directionIcon = trend.direction === 'up' ? 'trending-up' : 'trending-down';
            let directionColor = trend.direction === 'up' ? 'text-emerald-600' : 'text-destructive';

            return '<div class="trend-card bg-card border border-border rounded-lg p-4">' +
                '<div class="flex justify-between items-start mb-2">' +
                    '<span class="px-2 py-1 text-xs bg-muted rounded">' + trend.category + '</span>' +
                    '<i data-lucide="' + directionIcon + '" class="h-5 w-5 ' + directionColor + '"></i>' +
                '</div>' +
                '<h3 class="font-medium mb-2">' + trend.name + '</h3>' +
                '<p class="text-sm text-muted-foreground mb-3">' + trend.description + '</p>' +
                '<div class="flex items-center gap-2 text-sm">' +
                    '<span class="text-muted-foreground">Impact:</span>' +
                    '<span class="' + impactColor + ' font-medium capitalize">' + trend.impact + '</span>' +
                '</div>' +
            '</div>';
        }).join(''));
        lucide.createIcons();
    },

    populateVendorSelect: function() {
        let select = document.getElementById('current-vendor-select');
        safeHTML(select, '<option value="">Choose a vendor...</option>');
        this.vendors.forEach(function(v) {
            let option = document.createElement('option');
            option.value = v.id;
            option.textContent = v.name;
            select.appendChild(option);
        });
    },

    loadAlternatives: function(vendorId) {
        let self = this;
        let container = document.getElementById('alternatives-results');
        safeHTML(container,
            '<div class="text-center py-8 text-muted-foreground">' +
                '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
                '<p>Finding alternatives...</p>' +
            '</div>');
        lucide.createIcons();

        fetch('/api/market-intelligence/alternatives/' + vendorId)
            .then(function(res) { return res.json(); })
            .then(function(data) {
                let payload = self.extractPayload(data);
                let alternatives = payload && payload.alternatives ? payload.alternatives : [];
                if (!data.success || !Array.isArray(alternatives)) {
                    throw new Error(data.error || 'Failed to load alternatives');
                }
                self.renderAlternatives(alternatives);
            })
            .catch(function(err) {
                console.error('Error loading alternatives:', err);
                safeHTML(container, '<div class="text-center py-8 text-destructive">Error loading alternatives</div>');
            });
    },

    renderAlternatives: function(alternatives) {
        let container = document.getElementById('alternatives-results');
        if (alternatives.length === 0) {
            safeHTML(container, '<div class="text-center py-8 text-muted-foreground">No alternatives found</div>');
            return;
        }

        safeHTML(container, alternatives.map(function(alt) {
            let vendorName = alt.name || alt.vendor_name || 'Unknown Vendor';
            let quadrant = alt.quadrant || alt.quadrant_position || 'niche';
            let fitScore = alt.fit_score !== undefined ? alt.fit_score : (alt.capability_coverage || 0);
            let migrationEffort = alt.migration_effort || alt.estimated_migration_effort || 'unknown';
            let pros = alt.pros || [];
            let cons = alt.cons || [];
            let prosHtml = pros.map(function(p) {
                return '<li class="text-emerald-700"><i data-lucide="plus" class="h-3 w-3 inline mr-1"></i>' + p + '</li>';
            }).join('');
            let consHtml = cons.map(function(c) {
                return '<li class="text-destructive"><i data-lucide="minus" class="h-3 w-3 inline mr-1"></i>' + c + '</li>';
            }).join('');

            return '<div class="border border-border rounded-lg p-4">' +
                '<div class="flex justify-between items-start mb-4">' +
                    '<div class="flex items-center gap-3">' +
                        '<div class="w-10 h-10 rounded-full flex items-center justify-center text-primary-foreground text-sm font-bold" style="background: ' + (alt.color || '#3b82f6') + '">' +
                            vendorName.charAt(0) +
                        '</div>' +
                        '<div>' +
                            '<div class="font-semibold">' + vendorName + '</div>' +
                            '<div class="text-sm text-muted-foreground capitalize">' + quadrant.replace('_', ' ') + ' Player</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="text-right">' +
                        '<div class="text-2xl font-bold text-primary">' + fitScore + '%</div>' +
                        '<div class="text-xs text-muted-foreground">Fit Score</div>' +
                    '</div>' +
                '</div>' +
                '<div class="grid grid-cols-2 gap-4 mb-4">' +
                    '<div>' +
                        '<div class="text-xs text-muted-foreground mb-1">Migration Effort</div>' +
                        '<div class="font-medium capitalize">' + migrationEffort + '</div>' +
                    '</div>' +
                    '<div>' +
                        '<div class="text-xs text-muted-foreground mb-1">Market Position</div>' +
                        '<div class="font-medium capitalize">' + quadrant.replace('_', ' ') + '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="grid grid-cols-2 gap-4">' +
                    '<div>' +
                        '<div class="text-xs text-muted-foreground mb-2">Pros</div>' +
                        '<ul class="text-sm space-y-1">' + prosHtml + '</ul>' +
                    '</div>' +
                    '<div>' +
                        '<div class="text-xs text-muted-foreground mb-2">Cons</div>' +
                        '<ul class="text-sm space-y-1">' + consHtml + '</ul>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join(''));
        lucide.createIcons();
    },

    viewAlternatives: function(vendorName) {
        let self = MarketIntel;
        let vendor = self.vendors.find(function(v) { return v.name === vendorName; });
        if (vendor) {
            self.switchTab('alternatives');
            document.getElementById('current-vendor-select').value = vendor.id;
            self.loadAlternatives(vendor.id);
        }
    },

    showVendorDetail: function(vendorId) {
        let self = MarketIntel;
        let vendor = self.vendors.find(function(v) { return String(v.id) === String(vendorId); });
        if (!vendor) return;

        document.getElementById('vendor-detail-name').textContent = vendor.name;
        safeHTML(document.getElementById('vendor-detail-content'),
            '<div class="space-y-4">' +
                '<div class="flex items-center gap-4">' +
                    '<div class="w-16 h-16 rounded-full flex items-center justify-center text-primary-foreground text-2xl font-bold" style="background: ' + vendor.color + '">' +
                        vendor.name.charAt(0) +
                    '</div>' +
                    '<div>' +
                        '<div class="text-xl font-semibold">' + vendor.name + '</div>' +
                        '<div class="text-muted-foreground capitalize">' + vendor.quadrant + ' Player</div>' +
                    '</div>' +
                '</div>' +
                '<div class="grid grid-cols-2 gap-4">' +
                    '<div class="p-4 bg-muted rounded-lg text-center">' +
                        '<div class="text-2xl font-bold">' + vendor.x + '</div>' +
                        '<div class="text-sm text-muted-foreground">Vision Score</div>' +
                    '</div>' +
                    '<div class="p-4 bg-muted rounded-lg text-center">' +
                        '<div class="text-2xl font-bold">' + vendor.y + '</div>' +
                        '<div class="text-sm text-muted-foreground">Execution Score</div>' +
                    '</div>' +
                '</div>' +
                '<div class="flex justify-end pt-4">' +
                    '<button data-action="MarketIntel.viewAlternatives" data-id="' + vendor.name + '" class="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90">' +
                        'Find Alternatives' +
                    '</button>' +
                '</div>' +
            '</div>');

        self.showDialog('vendor-detail-dialog');
        lucide.createIcons();
    },

    syncData: function() {
        let self = this;
        fetch('/api/market-intelligence/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sync_all: true })
        })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.success) {
                    self.showToast('Data sync initiated', 'success');
                    setTimeout(function() { self.loadData(); }, 2000);
                } else {
                    self.showToast(data.error || 'Sync failed', 'error');
                }
            })
            .catch(function(err) {
                console.error('Error syncing data:', err);
                self.showToast('Error syncing data', 'error');
            });
    },

    switchTab: function(tab) {
        this.currentTab = tab;
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.classList.remove('border-b-2', 'border-primary', 'text-primary');
            btn.classList.add('text-muted-foreground');
        });
        let activeBtn = document.querySelector('.tab-btn[data-tab="' + tab + '"]');
        if (!activeBtn) return;
        activeBtn.classList.remove('text-muted-foreground');
        activeBtn.classList.add('border-b-2', 'border-primary', 'text-primary');

        document.querySelectorAll('.tab-panel').forEach(function(panel) { panel.classList.add('hidden'); });
        document.getElementById(tab + '-tab').classList.remove('hidden');
    },

    showDialog: function(id) {
        document.getElementById(id).classList.remove('hidden');
        document.getElementById(id).classList.add('flex');
    },

    hideDialog: function(id) {
        document.getElementById(id).classList.add('hidden');
        document.getElementById(id).classList.remove('flex');
    },

    showToast: function(message, type) {
        type = type || 'info';
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            alert(message);
        }
    }
};

document.addEventListener('DOMContentLoaded', function() {
    MarketIntel.init();
});
