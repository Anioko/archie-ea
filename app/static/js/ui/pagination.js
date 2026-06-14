/**
 * ui/pagination.js — Unified pagination module
 *
 * Requires: core/00-namespace.js through core/05-error.js
 *
 * Replaces:
 *   - updatePagination() / renderPaginationPages() in shared/data-table.js
 *   - updatePagination() / previousPage() / nextPage() in capability_map/index.js
 *   - Inline pagination in framework_management/manufacturing_table.js
 *   - Inline pagination in consolidation_list/dashboard.js
 *   - All window.dataTableInstances[id].handlePagination() onclick patterns
 *
 * Design:
 *   - Platform.pagination.create(options) — attach pagination to a container
 *   - Declarative HTML: data-pagination="containerId"
 *   - No inline onclick — uses event delegation via data attributes
 *   - Accessible: aria-label, aria-current, aria-disabled
 *   - Configurable window size, ellipsis, page-size selector
 *
 * Usage:
 *   const pager = Platform.pagination.create({
 *       containerId: 'my-table',      // id of the pagination container element
 *       total:       350,
 *       perPage:     25,
 *       page:        1,
 *       onChange:    (page, perPage) => loadData(page, perPage)
 *   });
 *
 *   // Update after data loads
 *   pager.update({ total: 350, page: 2 });
 *
 *   // Destroy when done
 *   pager.destroy();
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before ui/pagination.js');
    }

    let log      = global.Platform.log      ? global.Platform.log.child('pagination') : { debug: function(){}, warn: function(){} };
    let sanitize = global.Platform.sanitize || { html: function(el, h){ el.innerHTML = h; }, escape: function(s){ return String(s||''); } };

    // ── Registry ─────────────────────────────────────────────────────────────
    let _instances = Object.create(null);

    // ── Helpers ──────────────────────────────────────────────────────────────
    function _pageWindow(current, total, windowSize) {
        windowSize = windowSize || 5;
        let half  = Math.floor(windowSize / 2);
        let start = Math.max(1, current - half);
        let end   = Math.min(total, start + windowSize - 1);
        if (end - start + 1 < windowSize) {
            start = Math.max(1, end - windowSize + 1);
        }
        return { start: start, end: end };
    }

    function _renderPages(state) {
        let current    = state.page;
        let total      = state.totalPages;
        let windowSize = state.windowSize || 5;
        let win        = _pageWindow(current, total, windowSize);
        let parts      = [];

        // First page + ellipsis
        if (win.start > 1) {
            parts.push(_pageBtn(1, current));
            if (win.start > 2) parts.push('<span class="px-2 text-muted-foreground select-none" aria-hidden="true">&hellip;</span>');
        }

        for (let p = win.start; p <= win.end; p++) {
            parts.push(_pageBtn(p, current));
        }

        // Ellipsis + last page
        if (win.end < total) {
            if (win.end < total - 1) parts.push('<span class="px-2 text-muted-foreground select-none" aria-hidden="true">&hellip;</span>');
            parts.push(_pageBtn(total, current));
        }

        return parts.join('');
    }

    function _pageBtn(page, current) {
        let isCurrent = page === current;
        let cls = isCurrent
            ? 'inline-flex items-center justify-center w-9 h-9 rounded-md text-sm font-medium bg-primary text-primary-foreground cursor-default'
            : 'inline-flex items-center justify-center w-9 h-9 rounded-md text-sm font-medium border border-input bg-background hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer';
        return '<button type="button" class="' + cls + '" ' +
               'data-page="' + page + '" ' +
               (isCurrent ? 'aria-current="page" ' : '') +
               'aria-label="Page ' + page + '">' +
               page + '</button>';
    }

    function _renderPerPageOptions(perPage, options) {
        let opts = options || [10, 25, 50, 100];
        return opts.map(function (n) {
            return '<option value="' + n + '"' + (n === perPage ? ' selected' : '') + '>' + n + ' per page</option>';
        }).join('');
    }

    // ── Render ────────────────────────────────────────────────────────────────
    function _render(instance) {
        let state = instance.state;
        let el    = instance.element;
        if (!el) return;

        if (state.total === 0 || state.totalPages <= 1) {
            el.classList.add('hidden');
            return;
        }
        el.classList.remove('hidden');

        let prevDisabled = state.page === 1;
        let nextDisabled = state.page === state.totalPages;

        let perPageHtml = state.showPerPage
            ? '<div class="flex items-center gap-2">' +
              '<label class="text-sm text-muted-foreground" for="' + instance.id + '-per-page">Rows:</label>' +
              '<select id="' + instance.id + '-per-page" ' +
              'class="h-8 rounded-md border border-input bg-background px-2 text-sm" ' +
              'data-per-page>' +
              _renderPerPageOptions(state.perPage, state.perPageOptions) +
              '</select></div>'
            : '';

        let countHtml = state.showCount
            ? '<span class="text-sm text-muted-foreground">' +
              'Showing ' + ((state.page - 1) * state.perPage + 1) + '–' +
              Math.min(state.page * state.perPage, state.total) + ' of ' + state.total +
              '</span>'
            : '';

        let html =
            '<div class="flex items-center justify-between gap-4 flex-wrap">' +
            '<div class="flex items-center gap-4">' + countHtml + perPageHtml + '</div>' +
            '<nav class="flex items-center gap-1" aria-label="Pagination">' +
            '<button type="button" class="inline-flex items-center justify-center w-9 h-9 rounded-md border border-input bg-background hover:bg-accent transition-colors ' +
            (prevDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer') + '" ' +
            'data-page="' + (state.page - 1) + '" ' +
            (prevDisabled ? 'disabled aria-disabled="true"' : '') +
            ' aria-label="Previous page">' +
            '<i data-lucide="chevron-left" class="w-4 h-4"></i></button>' +
            _renderPages(state) +
            '<button type="button" class="inline-flex items-center justify-center w-9 h-9 rounded-md border border-input bg-background hover:bg-accent transition-colors ' +
            (nextDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer') + '" ' +
            'data-page="' + (state.page + 1) + '" ' +
            (nextDisabled ? 'disabled aria-disabled="true"' : '') +
            ' aria-label="Next page">' +
            '<i data-lucide="chevron-right" class="w-4 h-4"></i></button>' +
            '</nav></div>';

        sanitize.html(el, html);

        // Re-init Lucide icons
        if (global.lucide && typeof global.lucide.createIcons === 'function') {
            setTimeout(function () { global.lucide.createIcons(); }, 0);
        }
    }

    // ── Instance ──────────────────────────────────────────────────────────────
    function _createInstance(options) {
        let id = options.containerId || ('pagination-' + Date.now());
        let el = global.document.getElementById(id + '-pagination') ||
                 global.document.querySelector('[data-pagination="' + id + '"]');

        if (!el) {
            log.warn('pagination container not found for', id);
        }

        let state = {
            page:           options.page     || 1,
            perPage:        options.perPage  || 25,
            total:          options.total    || 0,
            totalPages:     Math.ceil((options.total || 0) / (options.perPage || 25)) || 1,
            windowSize:     options.windowSize || 5,
            showPerPage:    options.showPerPage !== false,
            showCount:      options.showCount   !== false,
            perPageOptions: options.perPageOptions || [10, 25, 50, 100]
        };

        let instance = {
            id:       id,
            element:  el,
            state:    state,
            onChange: options.onChange || null,

            update: function (patch) {
                if (patch.total    !== undefined) instance.state.total    = patch.total;
                if (patch.page     !== undefined) instance.state.page     = patch.page;
                if (patch.perPage  !== undefined) instance.state.perPage  = patch.perPage;
                instance.state.totalPages = Math.ceil(instance.state.total / instance.state.perPage) || 1;
                _render(instance);
            },

            goTo: function (page) {
                if (page < 1 || page > instance.state.totalPages) return;
                instance.state.page = page;
                _render(instance);
                if (instance.onChange) instance.onChange(page, instance.state.perPage);
            },

            setPerPage: function (perPage) {
                instance.state.perPage    = perPage;
                instance.state.page       = 1;
                instance.state.totalPages = Math.ceil(instance.state.total / perPage) || 1;
                _render(instance);
                if (instance.onChange) instance.onChange(1, perPage);
            },

            destroy: function () {
                if (el) {
                    el.removeEventListener('click', _clickHandler);
                    el.removeEventListener('change', _changeHandler);
                }
                delete _instances[id];
                log.debug('destroyed', id);
            }
        };

        // ── Event delegation ─────────────────────────────────────────────────
        function _clickHandler(e) {
            let btn = e.target.closest('[data-page]');
            if (!btn || btn.disabled) return;
            let page = parseInt(btn.getAttribute('data-page'), 10);
            if (!isNaN(page)) instance.goTo(page);
        }

        function _changeHandler(e) {
            let sel = e.target.closest('[data-per-page]');
            if (!sel) return;
            let perPage = parseInt(sel.value, 10);
            if (!isNaN(perPage)) instance.setPerPage(perPage);
        }

        if (el) {
            el.addEventListener('click',  _clickHandler);
            el.addEventListener('change', _changeHandler);
        }

        _render(instance);
        _instances[id] = instance;
        log.debug('created', id, state);
        return instance;
    }

    // ── Public API ────────────────────────────────────────────────────────────
    let pagination = {
        /**
         * Create a pagination controller.
         * @param {object} options
         * @param {string}   options.containerId    - ID prefix; looks for #{id}-pagination or [data-pagination="{id}"]
         * @param {number}   options.total          - Total record count
         * @param {number}   [options.perPage]      - Records per page (default 25)
         * @param {number}   [options.page]         - Current page (default 1)
         * @param {Function} [options.onChange]     - Called with (page, perPage) on navigation
         * @param {boolean}  [options.showPerPage]  - Show per-page selector (default true)
         * @param {boolean}  [options.showCount]    - Show "Showing X–Y of Z" (default true)
         * @param {number[]} [options.perPageOptions]
         * @returns {object} Pagination instance
         */
        create: _createInstance,

        get: function (id) { return _instances[id] || null; },

        destroyAll: function () {
            Object.keys(_instances).forEach(function (id) {
                _instances[id].destroy();
            });
        }
    };

    global.Platform.register('pagination', pagination);

}(window));
