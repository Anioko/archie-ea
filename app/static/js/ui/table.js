/**
 * ui/table.js — Unified table module
 *
 * Requires: core/00-namespace.js through core/05-error.js
 *           ui/pagination.js, ui/filter.js, ui/selection.js
 *
 * Replaces:
 *   - shared/data-table.js (DataTable class)
 *   - Inline _loadItems() implementations in alpine-architecture.js
 *   - All window.dataTableInstances[id] patterns
 *
 * Design:
 *   - Platform.table.create(options) — attach a managed table to a container
 *   - Integrates Platform.pagination, Platform.filter, Platform.selection
 *   - URL state sync (pushState / replaceState)
 *   - Alpine.js mixin factory: Platform.table.alpineMixin(options)
 *   - No DOM rendering — purely state + callback driven
 *
 * Usage (imperative):
 *   const table = Platform.table.create({
 *       id:       'vendors',
 *       apiUrl:   '/api/vendors/',
 *       perPage:  25,
 *       syncUrl:  true,
 *       onLoad:   (data) => renderRows(data.items),
 *       onError:  (err)  => showError(err.message)
 *   });
 *   table.load();
 *   table.setSearch('acme');
 *   table.setFilter('status', 'active');
 *   table.setSort('name', 'asc');
 *   table.goToPage(2);
 *   table.refresh();
 *   table.destroy();
 *
 * Usage (Alpine mixin — preferred for Alpine components):
 *   Alpine.data('vendorTable', function(cfg) {
 *       return Object.assign(
 *           {},
 *           Platform.table.alpineMixin({ apiUrl: cfg.apiUrl || '/api/vendors/' }),
 *           {
 *               init() { this._tableInit(); },
 *               destroy() { this._tableDestroy(); }
 *           }
 *       );
 *   });
 *
 *   Template:
 *   <div x-data="vendorTable({ apiUrl: '/api/vendors/' })">
 *       <input @input.debounce.300ms="setSearch($event.target.value)">
 *       <template x-for="item in items" :key="item.id">...</template>
 *       <button @click="prevPage()" :disabled="!hasPrev">Prev</button>
 *       <button @click="nextPage()" :disabled="!hasNext">Next</button>
 *   </div>
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before ui/table.js');
    }

    let log   = global.Platform.log   ? global.Platform.log.child('table')   : { debug: function(){}, warn: function(){}, error: function(){} };
    let error = global.Platform.error || { handle: function(e){ console.error(e); }, boundary: function(fn){ return fn; } };

    // ── Registry ──────────────────────────────────────────────────────────────
    let _instances = Object.create(null);

    // ── Helpers ───────────────────────────────────────────────────────────────

    function _fetch(url, opts) {
        if (global.Platform.fetch) return global.Platform.fetch(url, opts);
        if (global.apiFetch)       return global.apiFetch(url, opts);
        return global.fetch(url, opts).then(function (r) { return r.json(); });
    }

    function _buildQS(state) {
        let p = new URLSearchParams();
        p.set('page',     state.page);
        p.set('per_page', state.perPage);
        if (state.search) { p.set('search', state.search); p.set('q', state.search); }
        if (state.sortField) { p.set('sort', state.sortField); p.set('dir', state.sortDir); }
        Object.keys(state.filters).forEach(function (k) {
            let v = state.filters[k];
            if (v !== '' && v !== null && v !== undefined) p.set(k, v);
        });
        return p.toString();
    }

    function _readUrlState(defaults) {
        let url = new URL(global.location.href);
        return {
            page:      parseInt(url.searchParams.get('page')     || defaults.page,    10),
            perPage:   parseInt(url.searchParams.get('per_page') || defaults.perPage, 10),
            search:    url.searchParams.get('search')    || '',
            sortField: url.searchParams.get('sort')      || '',
            sortDir:   url.searchParams.get('dir')       || 'asc',
            filters:   (function () {
                let f = {};
                let reserved = ['page', 'per_page', 'search', 'sort', 'dir'];
                url.searchParams.forEach(function (v, k) {
                    if (reserved.indexOf(k) === -1) f[k] = v;
                });
                return f;
            }())
        };
    }

    function _syncUrl(state) {
        let url = new URL(global.location.href);
        let qs  = _buildQS(state);
        new URLSearchParams(qs).forEach(function (v, k) { url.searchParams.set(k, v); });
        global.history.replaceState({}, '', url.toString());
    }

    // ── Instance factory ──────────────────────────────────────────────────────

    /**
     * Create a managed table instance.
     * @param {object} options
     * @param {string}   options.id       - Unique instance ID
     * @param {string}   options.apiUrl   - API endpoint (GET, returns {items, total, page, per_page})
     * @param {number}   [options.perPage=25]
     * @param {boolean}  [options.syncUrl=false]  - Sync state to URL query params
     * @param {Function} [options.onLoad]  - Called with API response after successful load
     * @param {Function} [options.onError] - Called with Error after failed load
     * @param {Function} [options.onStateChange] - Called with full state after any state change
     * @returns {object} Table instance
     */
    function create(options) {
        if (!options || !options.id) throw new Error('[Platform.table] options.id is required');
        if (!options.apiUrl)         throw new Error('[Platform.table] options.apiUrl is required');

        if (_instances[options.id]) {
            log.warn('Table instance "' + options.id + '" already exists — returning existing.');
            return _instances[options.id];
        }

        let defaults = {
            page:      1,
            perPage:   options.perPage || 25,
            search:    '',
            sortField: '',
            sortDir:   'asc',
            filters:   {}
        };

        // Restore from URL if syncUrl enabled
        let state = options.syncUrl ? _readUrlState(defaults) : Object.assign({}, defaults);

        let _loading   = false;
        let _destroyed = false;
        let _abortCtrl = null;

        // ── Private load ─────────────────────────────────────────────────────

        function _load() {
            if (_destroyed) return;
            if (_abortCtrl) _abortCtrl.abort();

            _loading = true;
            let qs = _buildQS(state);
            let url = options.apiUrl + (options.apiUrl.indexOf('?') === -1 ? '?' : '&') + qs;

            log.debug('Loading table "' + options.id + '"', url);

            _fetch(url)
                .then(function (data) {
                    if (_destroyed) return;
                    _loading = false;

                    // Normalise response shape
                    let items = data.items || data.results || data.data || [];
                    let total = data.total  || data.count  || items.length;

                    if (options.syncUrl) _syncUrl(state);
                    if (typeof options.onLoad === 'function') {
                        options.onLoad({
                            items:    items,
                            total:    total,
                            page:     data.page     || state.page,
                            perPage:  data.per_page || state.perPage,
                            pages:    data.pages    || Math.max(1, Math.ceil(total / state.perPage)),
                            hasPrev:  (data.page || state.page) > 1,
                            hasNext:  (data.page || state.page) < Math.max(1, Math.ceil(total / state.perPage))
                        });
                    }
                    if (typeof options.onStateChange === 'function') options.onStateChange(getState());
                })
                .catch(function (err) {
                    if (_destroyed) return;
                    _loading = false;
                    log.error('Table "' + options.id + '" load failed', err);
                    if (typeof options.onError === 'function') options.onError(err);
                    else if (global.Platform.toast) global.Platform.toast.error(err.message || 'Failed to load data.');
                });
        }

        // ── Public API ───────────────────────────────────────────────────────

        let instance = {

            load: function () { _load(); return instance; },

            refresh: function () { _load(); return instance; },

            setSearch: function (q) {
                state.search = q || '';
                state.page   = 1;
                _load();
                return instance;
            },

            setFilter: function (key, value) {
                state.filters = Object.assign({}, state.filters);
                if (value === '' || value === null || value === undefined) {
                    delete state.filters[key];
                } else {
                    state.filters[key] = value;
                }
                state.page = 1;
                _load();
                return instance;
            },

            clearFilters: function () {
                state.filters = {};
                state.search  = '';
                state.page    = 1;
                _load();
                return instance;
            },

            setSort: function (field, dir) {
                if (state.sortField === field && !dir) {
                    state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
                } else {
                    state.sortField = field;
                    state.sortDir   = dir || 'asc';
                }
                state.page = 1;
                _load();
                return instance;
            },

            goToPage: function (n) {
                state.page = Math.max(1, n);
                _load();
                return instance;
            },

            setPerPage: function (n) {
                state.perPage = Math.max(1, n);
                state.page    = 1;
                _load();
                return instance;
            },

            getState: function () { return Object.assign({}, state, { filters: Object.assign({}, state.filters) }); },

            isLoading: function () { return _loading; },

            destroy: function () {
                _destroyed = true;
                if (_abortCtrl) _abortCtrl.abort();
                delete _instances[options.id];
                log.debug('Table "' + options.id + '" destroyed');
            }
        };

        // Alias
        function getState() { return instance.getState(); }

        _instances[options.id] = instance;
        return instance;
    }

    // ── Alpine mixin factory ──────────────────────────────────────────────────

    /**
     * Returns an Alpine.js component mixin that provides table state + methods.
     * Compose with _asyncMixin() from alpine-architecture.js.
     *
     * @param {object} options
     * @param {string}  options.apiUrl
     * @param {number}  [options.perPage=25]
     * @param {boolean} [options.syncUrl=false]
     * @param {string}  [options.itemsKey='items']  - Key in API response for items array
     * @returns {object} Alpine mixin
     */
    function alpineMixin(options) {
        options = options || {};
        let _apiUrl    = options.apiUrl    || '';
        let _perPage   = options.perPage   || 25;
        let _syncUrl   = options.syncUrl   || false;
        let _itemsKey  = options.itemsKey  || 'items';

        return {
            // ── State ─────────────────────────────────────────────────────────
            items:      [],
            totalItems: 0,
            page:       1,
            pageSize:   _perPage,
            search:     '',
            sortField:  '',
            sortDir:    'asc',
            filters:    {},
            loading:    false,
            errorMsg:   '',

            // ── Computed ──────────────────────────────────────────────────────
            get totalPages() { return Math.max(1, Math.ceil(this.totalItems / this.pageSize)); },
            get hasPrev()    { return this.page > 1; },
            get hasNext()    { return this.page < this.totalPages; },
            get pageStart()  { return this.totalItems === 0 ? 0 : (this.page - 1) * this.pageSize + 1; },
            get pageEnd()    { return Math.min(this.page * this.pageSize, this.totalItems); },

            // ── Init / destroy ────────────────────────────────────────────────
            _tableInit() {
                if (_syncUrl) {
                    let url = new URL(global.location.href);
                    this.page      = parseInt(url.searchParams.get('page')     || '1',           10);
                    this.pageSize  = parseInt(url.searchParams.get('per_page') || String(_perPage), 10);
                    this.search    = url.searchParams.get('search')    || '';
                    this.sortField = url.searchParams.get('sort')      || '';
                    this.sortDir   = url.searchParams.get('dir')       || 'asc';
                    let self = this;
                    url.searchParams.forEach(function (v, k) {
                        if (['page','per_page','search','sort','dir'].indexOf(k) === -1) {
                            self.filters[k] = v;
                        }
                    });
                }
                this._loadItems();
            },

            _tableDestroy() { /* override to clean up timers */ },

            // ── Data loading ──────────────────────────────────────────────────
            async _loadItems() {
                this.loading  = true;
                this.errorMsg = '';
                try {
                    if (typeof Alpine !== 'undefined' && Alpine.store && Alpine.store('loading')) {
                        Alpine.store('loading').start();
                    }
                } catch(e) {}
                try {
                    let qs   = this._buildQueryString();
                    let url  = (_apiUrl || this.apiUrl || '') + ((_apiUrl || this.apiUrl || '').indexOf('?') === -1 ? '?' : '&') + qs;
                    let data = await _fetch(url);

                    this.items      = data[_itemsKey] || data.items || data.results || data.data || [];
                    this.totalItems = data.total || data.count || this.items.length;

                    if (_syncUrl) this._syncUrl();
                } catch (err) {
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
            },

            // ── Query string builder ──────────────────────────────────────────
            _buildQueryString() {
                let p = new URLSearchParams();
                p.set('page',     this.page);
                p.set('per_page', this.pageSize);
                if (this.search) { p.set('search', this.search); p.set('q', this.search); }
                if (this.sortField) { p.set('sort', this.sortField); p.set('dir', this.sortDir); }
                let self = this;
                Object.keys(this.filters).forEach(function (k) {
                    let v = self.filters[k];
                    if (v !== '' && v !== null && v !== undefined) p.set(k, v);
                });
                return p.toString();
            },

            // ── URL sync ──────────────────────────────────────────────────────
            _syncUrl() {
                let url = new URL(global.location.href);
                new URLSearchParams(this._buildQueryString()).forEach(function (v, k) {
                    url.searchParams.set(k, v);
                });
                global.history.replaceState({}, '', url.toString());
            },

            // ── Public actions ────────────────────────────────────────────────
            prevPage()  { if (this.hasPrev) { this.page--; this._loadItems(); } },
            nextPage()  { if (this.hasNext) { this.page++; this._loadItems(); } },
            goToPage(n) { this.page = Math.max(1, Math.min(n, this.totalPages)); this._loadItems(); },

            setSort(field) {
                if (this.sortField === field) {
                    this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortField = field;
                    this.sortDir   = 'asc';
                }
                this.page = 1;
                this._loadItems();
            },

            setSearch(q) {
                this.search = q || '';
                this.page   = 1;
                this._loadItems();
            },

            setFilter(key, value) {
                this.filters = Object.assign({}, this.filters);
                if (value === '' || value === null || value === undefined) {
                    delete this.filters[key];
                } else {
                    this.filters[key] = value;
                }
                this.page = 1;
                this._loadItems();
            },

            clearFilters() {
                this.filters = {};
                this.search  = '';
                this.page    = 1;
                this._loadItems();
            },

            setPerPage(n) {
                this.pageSize = Math.max(1, parseInt(n, 10) || _perPage);
                this.page     = 1;
                this._loadItems();
            },

            refresh() { this._loadItems(); }
        };
    }

    // ── Legacy shim: window.DataTable → Platform.table.create ────────────────
    // Existing code that does `new DataTable({...})` will still work.
    // The shim wraps Platform.table.create and exposes the same surface.
    if (!global.DataTable) {
        global.DataTable = function (opts) {
            let id = opts.containerId || opts.id || ('dt-' + Date.now());
            let instance = create({
                id:      id,
                apiUrl:  opts.apiEndpoint || opts.apiUrl || '',
                perPage: opts.perPage || 50,
                syncUrl: false,
                onLoad:  function (data) {
                    if (typeof opts.onDataLoad === 'function') opts.onDataLoad(data);
                },
                onError: function (err) {
                    if (global.Platform.toast) global.Platform.toast.error(err.message);
                }
            });
            // Expose legacy method names
            this.loadData        = function (p) { return instance.load(p); };
            this.refresh         = function ()  { return instance.refresh(); };
            this.handleSearch    = function (q) { return instance.setSearch(q); };
            this.handleFilter    = function (k, v) { return instance.setFilter(k, v); };
            this.handleSort      = function (f) { return instance.setSort(f); };
            this.handlePagination = function (n) { return instance.goToPage(n); };
            this.destroy         = function ()  { return instance.destroy(); };
            this._instance       = instance;
        };
    }

    // ── Public API ────────────────────────────────────────────────────────────
    let tableModule = {
        create:      create,
        alpineMixin: alpineMixin,
        get:         function (id) { return _instances[id] || null; },
        destroyAll:  function () {
            Object.keys(_instances).forEach(function (id) { _instances[id].destroy(); });
        }
    };

    global.Platform.register('table', tableModule);

    // Backward-compat shim: window.PlatformTable
    global.PlatformTable = tableModule;

}(window));
