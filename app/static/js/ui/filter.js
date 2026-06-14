/**
 * ui/filter.js — Unified filtering module
 *
 * Requires: core/00-namespace.js through core/05-error.js
 *
 * Replaces:
 *   - handleFilter() / handleSearch() in shared/data-table.js
 *   - filterTable() in capability_map/index.js and capability_map/index_inline.js
 *   - filterTable() in framework_management/manufacturing_table.js
 *   - Inline filter logic in consolidation_list/dashboard.js
 *   - Inline search in vendors/list.js, solutions/list.js
 *   - Duplicate debounce wrappers on search inputs across all feature modules
 *
 * Design:
 *   - Platform.filter.create(options) — attach filter state to a data source
 *   - Declarative HTML: data-filter-for="instanceId", data-filter-key="status"
 *   - Search inputs: data-search-for="instanceId"
 *   - Debounced search (300ms default)
 *   - onChange callback receives the full current filter state
 *   - Supports: text search, select filters, multi-select, date range
 *   - No DOM manipulation — purely state management + callback
 *
 * Usage:
 *   const filters = Platform.filter.create({
 *       id:       'applications',
 *       debounce: 300,
 *       onChange: (state) => loadData(state)
 *   });
 *
 *   // Programmatic control
 *   filters.set('status', 'active');
 *   filters.set('search', 'MyApp');
 *   filters.clear('status');
 *   filters.reset();
 *   const current = filters.getAll();
 *
 *   // HTML wiring (no JS needed):
 *   <input data-search-for="applications" placeholder="Search...">
 *   <select data-filter-for="applications" data-filter-key="status">
 *     <option value="">All</option>
 *     <option value="active">Active</option>
 *   </select>
 *   <button data-filter-reset="applications">Clear</button>
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before ui/filter.js');
    }

    let log = global.Platform.log
        ? global.Platform.log.child('filter')
        : { debug: function(){}, warn: function(){} };

    // ── Registry ──────────────────────────────────────────────────────────────
    let _instances = Object.create(null);

    // ── Debounce (use Platform.debounce if available, else inline) ────────────
    function _debounce(fn, ms) {
        if (global.Platform.has && global.Platform.has('debounce')) {
            return global.Platform.debounce(fn, ms);
        }
        if (typeof global.debounce === 'function') {
            return global.debounce(fn, ms);
        }
        let timer = null;
        return function () {
            let ctx  = this;
            let args = arguments;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () { timer = null; fn.apply(ctx, args); }, ms);
        };
    }

    // ── Instance factory ──────────────────────────────────────────────────────
    function _createInstance(options) {
        options = options || {};
        let id       = options.id || ('filter-' + Date.now());
        let debounce = options.debounce !== undefined ? options.debounce : 300;
        let onChange = options.onChange || null;

        // Internal state: key → value (string | string[] | null)
        let _state = Object.create(null);

        // Merge initial values
        if (options.initial && typeof options.initial === 'object') {
            Object.keys(options.initial).forEach(function (k) {
                _state[k] = options.initial[k];
            });
        }

        // ── Notify ────────────────────────────────────────────────────────────
        function _notify() {
            log.debug(id, 'changed', _state);
            global.Platform.emit('filter:change', { id: id, state: _getAll() });
            if (onChange) onChange(_getAll());
        }

        let _notifyDebounced = debounce > 0 ? _debounce(_notify, debounce) : _notify;

        // ── State accessors ───────────────────────────────────────────────────
        function _getAll() {
            // Return a copy with empty/null values stripped
            let out = Object.create(null);
            Object.keys(_state).forEach(function (k) {
                let v = _state[k];
                if (v !== null && v !== undefined && v !== '') {
                    out[k] = v;
                }
            });
            return out;
        }

        function _set(key, value) {
            let prev = _state[key];
            _state[key] = value;
            if (prev !== value) _notifyDebounced();
        }

        function _clear(key) {
            if (key) {
                delete _state[key];
            } else {
                _state = Object.create(null);
            }
            _notify();
        }

        function _reset() {
            _state = Object.create(null);
            if (options.initial) {
                Object.keys(options.initial).forEach(function (k) {
                    _state[k] = options.initial[k];
                });
            }
            // Reset DOM elements
            _syncDom();
            _notify();
        }

        // ── DOM sync (reset UI to match state) ────────────────────────────────
        function _syncDom() {
            global.document.querySelectorAll('[data-filter-for="' + id + '"]').forEach(function (el) {
                let key = el.getAttribute('data-filter-key');
                if (!key) return;
                let val = _state[key] !== undefined ? _state[key] : '';
                if (el.tagName === 'SELECT' || el.tagName === 'INPUT') {
                    el.value = val || '';
                }
            });
            global.document.querySelectorAll('[data-search-for="' + id + '"]').forEach(function (el) {
                el.value = _state['search'] || '';
            });
        }

        // ── Event delegation handlers ─────────────────────────────────────────
        let _searchHandler = _debounce(function (e) {
            let el = e.target.closest('[data-search-for="' + id + '"]');
            if (!el) return;
            _set('search', el.value.trim());
        }, debounce);

        let _filterHandler = function (e) {
            let el = e.target.closest('[data-filter-for="' + id + '"]');
            if (!el) return;
            let key = el.getAttribute('data-filter-key');
            if (!key) return;
            let value = el.value;
            if (el.type === 'checkbox') {
                value = el.checked ? (el.value || 'true') : '';
            }
            _set(key, value);
        };

        let _resetHandler = function (e) {
            let el = e.target.closest('[data-filter-reset="' + id + '"]');
            if (!el) return;
            _reset();
        };

        // Attach to document (event delegation — works for dynamically added elements)
        global.document.addEventListener('input',  _searchHandler);
        global.document.addEventListener('change', _filterHandler);
        global.document.addEventListener('click',  _resetHandler);

        // ── Public instance API ───────────────────────────────────────────────
        let instance = {
            id: id,

            set: function (key, value) { _set(key, value); return instance; },

            clear: function (key) { _clear(key); return instance; },

            reset: _reset,

            getAll: _getAll,

            get: function (key) { return _state[key]; },

            /**
             * Build a URLSearchParams-compatible object from current filter state.
             * Suitable for appending to API URLs.
             * @param {object} [extra] - Additional params to merge
             * @returns {URLSearchParams}
             */
            toParams: function (extra) {
                let all = _getAll();
                if (extra) Object.assign(all, extra);
                return new URLSearchParams(all);
            },

            destroy: function () {
                global.document.removeEventListener('input',  _searchHandler);
                global.document.removeEventListener('change', _filterHandler);
                global.document.removeEventListener('click',  _resetHandler);
                delete _instances[id];
                log.debug('destroyed', id);
            }
        };

        _instances[id] = instance;
        log.debug('created', id);
        return instance;
    }

    // ── Public API ────────────────────────────────────────────────────────────
    let filter = {
        /**
         * Create a filter controller.
         * @param {object} options
         * @param {string}   [options.id]        - Unique instance ID
         * @param {number}   [options.debounce]  - Debounce ms for search (default 300)
         * @param {object}   [options.initial]   - Initial filter values
         * @param {Function} [options.onChange]  - Called with current filter state on change
         * @returns {object} Filter instance
         */
        create: _createInstance,

        get: function (id) { return _instances[id] || null; },

        destroyAll: function () {
            Object.keys(_instances).forEach(function (id) {
                _instances[id].destroy();
            });
        }
    };

    global.Platform.register('filter', filter);

}(window));
