/**
 * components/data_table.js — Shared dataTable Alpine component
 *
 * Composes Platform.table.alpineMixin() and layers on:
 *   - Selection (three-state Select All, Shift+Click range, cross-page)
 *   - Expansion (async detail loading per row)
 *   - Formatting (currency, date, percent, number — null-safe)
 *   - Status badges (platform-wide STATUS_CLASSES mapping)
 *   - Pagination helpers (getVisiblePages with ellipsis)
 *
 * Spec: docs/design_system/TABLE_COMPONENT_SPEC.md
 *
 * Usage (direct — simple tables):
 *   <div x-data="dataTable({apiUrl: '/api/entries', perPage: 25})">
 *
 * Usage (composition — complex tables):
 *   Alpine.data('consolidationTable', function() {
 *       return Object.assign({}, Platform.dataTable.mixin({
 *           apiUrl: '/api/entries',
 *           perPage: 25,
 *           itemsKey: 'entries',
 *           onResponse: function(data) { this.summary = data.summary || {}; }
 *       }), { summary: {}, ...pageSpecificMethods });
 *   });
 *
 * Requires: Platform.table (ui/table.js), Alpine.js
 * Optional: window.currencyManager (currency.js), window.lucide (Lucide icons)
 */
(function(global) {
    'use strict';

    if (!global.Platform || !global.Platform.table) {
        throw new Error('[Platform.dataTable] ui/table.js must be loaded before components/data_table.js');
    }

    // ── Status badge classes (platform-wide, using semantic tokens) ─────
    // Uses semantic tokens from docs/design_system/token_map.json.
    // Semantic tokens handle dark mode automatically via CSS variables.
    let STATUS_CLASSES = {
        // Pipeline statuses
        'identified':         'bg-muted text-foreground',
        'under_review':       'bg-primary/10 text-primary',
        'impact_assessed':    'bg-primary/10 text-primary',
        'migration_planned':  'bg-violet-500/10 text-violet-600',
        'approved':           'bg-amber-500/10 text-amber-600',
        'in_progress':        'bg-orange-500/10 text-orange-600',
        'completed':          'bg-emerald-500/10 text-emerald-600',

        // TIME actions
        'tolerate':           'bg-muted text-foreground',
        'invest':             'bg-emerald-500/10 text-emerald-600',
        'migrate':            'bg-primary/10 text-primary',
        'eliminate':          'bg-destructive/10 text-destructive',

        // Consolidation actions
        'decommission':       'bg-destructive/10 text-destructive',
        'retire':             'bg-destructive/10 text-destructive',
        'merge':              'bg-amber-500/10 text-amber-600',
        'replace':            'bg-primary/10 text-primary',
        'modernize':          'bg-violet-500/10 text-violet-600',
        'pending_review':     'bg-muted text-foreground',

        // Criticality
        'critical':           'bg-destructive/10 text-destructive',
        'high':               'bg-orange-500/10 text-orange-600',
        'medium':             'bg-amber-500/10 text-amber-600',
        'low':                'bg-emerald-500/10 text-emerald-600',

        // Lifecycle
        'active':             'bg-emerald-500/10 text-emerald-600',
        'planned':            'bg-primary/10 text-primary',
        'retiring':           'bg-amber-500/10 text-amber-600',
        'retired':            'bg-muted text-foreground',
        'deprecated':         'bg-destructive/10 text-destructive',

        // Generic
        'draft':              'bg-muted text-foreground',
        'submitted':          'bg-primary/10 text-primary',
        'rejected':           'bg-destructive/10 text-destructive',
        'archived':           'bg-muted text-foreground',
        'cancelled':          'bg-muted text-foreground'
    };

    // ── Formatting helpers (null-safe — return null for null/undefined) ──

    let fmt = {
        currency: function(value) {
            if (value == null) return null;
            if (global.currencyManager) {
                try { return global.currencyManager.format(value); }
                catch(e) { /* fall through */ }
            }
            let num = typeof value === 'string' ? parseFloat(value) : value;
            if (isNaN(num)) return null;
            return new Intl.NumberFormat('en-GB', {
                style: 'currency', currency: 'GBP',
                minimumFractionDigits: 0, maximumFractionDigits: 0
            }).format(num);
        },

        date: function(value) {
            if (!value) return null;
            let date = new Date(value);
            if (isNaN(date.getTime())) return null;
            let now = new Date();
            let diffDays = Math.floor((now - date) / 86400000);
            if (diffDays === 0) return 'Today';
            if (diffDays === 1) return 'Yesterday';
            if (diffDays < 7) return diffDays + ' days ago';
            return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
        },

        percent: function(value) {
            if (value == null) return null;
            return Math.round(value * 100) + '%';
        },

        number: function(value) {
            if (value == null) return null;
            return new Intl.NumberFormat('en-GB').format(value);
        },

        nullSafe: function(value) {
            return (value == null || value === '') ? '\u2014' : value;
        }
    };

    // ── Pagination helper ────────────────────────────────────────────────

    function getVisiblePages(current, total) {
        if (total <= 7) {
            let pages = [];
            for (let i = 1; i <= total; i++) pages.push(i);
            return pages;
        }
        if (current <= 3) return [1, 2, 3, 4, '...', total];
        if (current >= total - 2) return [1, '...', total - 3, total - 2, total - 1, total];
        return [1, '...', current - 1, current, current + 1, '...', total];
    }

    // ── Mixin factory ────────────────────────────────────────────────────

    /**
     * Creates an Alpine mixin with table state, selection, expansion, and formatting.
     *
     * @param {object} config
     * @param {string}   config.apiUrl      - API endpoint
     * @param {number}   [config.perPage=25]
     * @param {string}   [config.itemsKey='items'] - Key in API response for items array
     * @param {boolean}  [config.syncUrl=false]
     * @param {string}   [config.detailUrl]  - URL pattern for row expansion, e.g. '/api/entry/{id}/detail'
     * @param {string}   [config.storageKey] - localStorage namespace for page size preference
     * @param {Function} [config.onResponse] - Called with raw API response data (for page-specific extraction)
     * @returns {object} Alpine mixin
     */
    function mixin(config) {
        config = config || {};
        let _detailUrl  = config.detailUrl  || '';
        let _storageKey = config.storageKey  || '';
        let _onResponse = config.onResponse  || null;

        // Get the base mixin from Platform.table
        let base = global.Platform.table.alpineMixin({
            apiUrl:   config.apiUrl   || '',
            perPage:  config.perPage  || 25,
            syncUrl:  config.syncUrl  || false,
            itemsKey: config.itemsKey || 'items'
        });

        // Override _loadItems to add onResponse hook and selection clearing
        let origLoadItems = base._loadItems;

        let baseMixin = Object.assign({}, base, {

            // ── Selection state (arrays for Alpine reactivity) ───────
            _selectedIds:    [],
            _lastClickedIdx: null,
            selectAllState:  'none',   // 'none' | 'page' | 'cross-page'

            // ── Expansion state ──────────────────────────────────────
            _expandedIds:    [],
            expandedData:    {},

            // ── Formatting namespace ─────────────────────────────────
            fmt: fmt,

            // ── Status helpers ───────────────────────────────────────
            statusClass: function(status) {
                if (!status) return STATUS_CLASSES['draft'];
                return STATUS_CLASSES[status.toLowerCase()] || STATUS_CLASSES['draft'];
            },

            formatStatus: function(status) {
                if (!status) return '\u2014';
                return status.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
            },

            // ── Selection methods ────────────────────────────────────
            isSelected: function(id) {
                if (this.selectAllState === 'cross-page') return true;
                return this._selectedIds.indexOf(id) !== -1;
            },

            toggleRow: function(id) {
                let idx = this._selectedIds.indexOf(id);
                if (idx !== -1) {
                    this._selectedIds.splice(idx, 1);
                } else {
                    this._selectedIds.push(id);
                }
                this.selectAllState = 'none';
            },

            toggleSelectAll: function() {
                let self = this;
                if (this.allPageSelected) {
                    // Deselect all on current page
                    this.items.forEach(function(item) {
                        let idx = self._selectedIds.indexOf(item.id);
                        if (idx !== -1) self._selectedIds.splice(idx, 1);
                    });
                    this.selectAllState = 'none';
                } else {
                    // Select all on current page
                    this.items.forEach(function(item) {
                        if (self._selectedIds.indexOf(item.id) === -1) {
                            self._selectedIds.push(item.id);
                        }
                    });
                    this.selectAllState = 'page';
                }
            },

            selectAllCrossPage: function() {
                this.selectAllState = 'cross-page';
            },

            clearSelection: function() {
                this._selectedIds = [];
                this.selectAllState = 'none';
                this._lastClickedIdx = null;
            },

            handleRowCheckboxClick: function(event, index) {
                if (event.shiftKey && this._lastClickedIdx !== null) {
                    let start = Math.min(this._lastClickedIdx, index);
                    let end = Math.max(this._lastClickedIdx, index);
                    for (let i = start; i <= end; i++) {
                        let id = this.items[i].id;
                        if (this._selectedIds.indexOf(id) === -1) {
                            this._selectedIds.push(id);
                        }
                    }
                    this.selectAllState = 'none';
                } else {
                    this.toggleRow(this.items[index].id);
                }
                this._lastClickedIdx = index;
            },

            getSelectedIds: function() {
                return this._selectedIds.slice();
            },

            // ── Expansion methods ────────────────────────────────────
            isExpanded: function(id) {
                return this._expandedIds.indexOf(id) !== -1;
            },

            toggleExpand: function(id) {
                let idx = this._expandedIds.indexOf(id);
                if (idx !== -1) {
                    this._expandedIds.splice(idx, 1);
                } else {
                    this._expandedIds.push(id);
                    if (_detailUrl && !this.expandedData[id]) {
                        this.loadDetail(id);
                    }
                }
            },

            loadDetail: function(id) {
                if (!_detailUrl) return;
                let self = this;
                let url = _detailUrl.replace('{id}', id);
                let fetchFn = (global.Platform && global.Platform.fetch && global.Platform.fetch.get)
                    ? global.Platform.fetch.get.bind(global.Platform.fetch)
                    : function(u) { return global.fetch(u).then(function(r) { return r.json(); }); };

                fetchFn(url).then(function(data) {
                    self.expandedData[id] = data;
                }).catch(function(err) {
                    self.expandedData[id] = { _error: (err && err.message) || 'Failed to load details' };
                });
            },

            // ── Pagination helpers ───────────────────────────────────
            getVisiblePages: function(max) {
                return getVisiblePages(this.page, max || this.totalPages);
            },

            // ── Init override ────────────────────────────────────────
            _tableInit: function() {
                // Restore page size from localStorage
                if (_storageKey) {
                    let saved = global.localStorage.getItem('archie_table_pageSize_' + _storageKey);
                    if (saved) this.pageSize = parseInt(saved, 10) || this.pageSize;
                }
                // Call base _tableInit which calls _loadItems
                base._tableInit.call(this);
            },

            // ── Load override (adds onResponse + selection clear) ────
            _loadItems: async function() {
                // Clear page-level selection on page change
                this._selectedIds = [];
                this.selectAllState = 'none';
                this._lastClickedIdx = null;

                // Call base load
                await origLoadItems.call(this);

                // Call onResponse hook with full API data
                if (_onResponse && this.items) {
                    try { _onResponse.call(this, this._lastResponseData || {}); } catch(e) {}
                }

                // Re-render Lucide icons in new content
                if (global.lucide && global.lucide.createIcons) {
                    let self = this;
                    this.$nextTick(function() {
                        global.lucide.createIcons();
                    });
                }
            },

            // ── Page size with localStorage ──────────────────────────
            setPerPage: function(n) {
                this.pageSize = Math.max(1, parseInt(n, 10) || 25);
                this.page = 1;
                if (_storageKey) {
                    global.localStorage.setItem('archie_table_pageSize_' + _storageKey, this.pageSize);
                }
                this._loadItems();
            }
        });

        // ── Computed getters (must use defineProperty, not Object.assign) ──
        // Object.assign evaluates getters during copy. defineProperty preserves
        // them so Alpine can call them with the correct `this` context.
        Object.defineProperty(baseMixin, 'selectedCount', {
            get: function() {
                if (this.selectAllState === 'cross-page') return this.totalItems;
                return this._selectedIds.length;
            },
            configurable: true
        });

        Object.defineProperty(baseMixin, 'hasSelection', {
            get: function() {
                return this._selectedIds.length > 0 || this.selectAllState === 'cross-page';
            },
            configurable: true
        });

        Object.defineProperty(baseMixin, 'allPageSelected', {
            get: function() {
                if (!this.items || this.items.length === 0) return false;
                let ids = this._selectedIds;
                return this.items.every(function(item) { return ids.indexOf(item.id) !== -1; });
            },
            configurable: true
        });

        Object.defineProperty(baseMixin, 'hasActiveFilters', {
            get: function() {
                if (this.search) return true;
                let f = this.filters;
                for (let k in f) {
                    if (f.hasOwnProperty(k) && f[k] !== '' && f[k] != null) return true;
                }
                return false;
            },
            configurable: true
        });

        return baseMixin;
    }

    // ── Override base _loadItems to capture raw response ─────────────────
    // We need access to the full API response for onResponse hooks.
    // Patch the mixin's _loadItems to store the raw data.
    let _origAlpineMixin = global.Platform.table.alpineMixin;
    global.Platform.table.alpineMixin = function(options) {
        let baseMixin = _origAlpineMixin(options);
        let origLoad = baseMixin._loadItems;

        baseMixin._loadItems = async function() {
            this.loading = true;
            this.errorMsg = '';
            try {
                if (typeof Alpine !== 'undefined' && Alpine.store && Alpine.store('loading')) {
                    Alpine.store('loading').start();
                }
            } catch(e) {}
            try {
                let _apiUrl = options.apiUrl || this.apiUrl || '';
                let _itemsKey = options.itemsKey || 'items';
                let qs = this._buildQueryString();
                let url = _apiUrl + (_apiUrl.indexOf('?') === -1 ? '?' : '&') + qs;
                let fetchFn = global.Platform.fetch
                    ? (global.Platform.fetch.get ? global.Platform.fetch.get.bind(global.Platform.fetch) : global.Platform.fetch)
                    : function(u) { return global.fetch(u).then(function(r) { return r.json(); }); };

                let data = await fetchFn(url);
                this._lastResponseData = data;
                this.items = data[_itemsKey] || data.items || data.results || data.data || [];
                // Support both flat (data.total) and nested (data.pagination.total) response shapes
                let pag = data.pagination || {};
                this.totalItems = data.total || data.count || pag.total || this.items.length;

                if (options.syncUrl) this._syncUrl();
            } catch(err) {
                this.errorMsg = (err && err.message) ? err.message : 'Failed to load data.';
                let t = (global.Platform && global.Platform.toast) || global.toast;
                if (t) t.error(this.errorMsg);
            } finally {
                this.loading = false;
                try {
                    if (typeof Alpine !== 'undefined' && Alpine.store && Alpine.store('loading')) {
                        Alpine.store('loading').stop();
                    }
                } catch(e) {}
            }
        };

        return baseMixin;
    };

    // ── Register Alpine.data('dataTable', ...) at alpine:init ────────────
    // Uses 'dataTable' name — distinct from window.dataTable() in data_table.html
    document.addEventListener('alpine:init', function() {
        if (typeof Alpine !== 'undefined') {
            Alpine.data('dataTable', function(cfg) {
                cfg = cfg || {};
                let m = mixin(cfg);
                return Object.assign({}, m, {
                    init: function() { this._tableInit(); },
                    destroy: function() { this._tableDestroy(); }
                });
            });
        }
    });

    // ── Public API on Platform namespace ──────────────────────────────────
    let dataTableModule = {
        mixin:          mixin,
        STATUS_CLASSES: STATUS_CLASSES,
        fmt:            fmt,
        getVisiblePages: getVisiblePages
    };

    global.Platform.register('dataTable', dataTableModule);

}(window));
