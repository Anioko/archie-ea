/**
 * core/load-order.js — Canonical script load order for the platform
 *
 * This file is NOT loaded itself. It documents the REQUIRED load order
 * for all platform JS. Include this comment block in any base template
 * that loads platform scripts.
 *
 * ─── REQUIRED LOAD ORDER ─────────────────────────────────────────────────────
 *
 * <!-- 1. Third-party libraries (CDN, no defer on DOMPurify) -->
 * <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
 * <script src="https://unpkg.com/lucide@latest"></script>
 * <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
 *
 * <!-- 2. Platform core (must load synchronously, in order) -->
 * <script src="{{ url_for('static', filename='js/core/00-namespace.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/core/01-logger.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/core/02-sanitize.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/core/03-fetch.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/core/04-toast.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/core/05-error.js') }}"></script>
 *
 * <!-- 3. Platform UI modules -->
 * <script src="{{ url_for('static', filename='js/ui/modal.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/ui/pagination.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/ui/filter.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/ui/selection.js') }}"></script>
 * <script src="{{ url_for('static', filename='js/ui/table.js') }}"></script>
 *
 * <!-- 4. Shared utilities (debounce, export-utils, etc.) -->
 * <script src="{{ url_for('static', filename='js/shared/debounce.js') }}"></script>
 *
 * <!-- 5. Feature modules (domain-specific, loaded per-page) -->
 * {% block extra_js %}{% endblock %}
 *
 * ─── RULES ───────────────────────────────────────────────────────────────────
 *
 * ✅ DO:
 *   - Load core/* in numeric order (00 → 05)
 *   - Load ui/* after all core/* modules
 *   - Load feature modules in {% block extra_js %}
 *   - Use Platform.require('fetch', 'toast') at the top of feature modules
 *   - Use Platform.fetch.get/post/put/patch/delete for all HTTP calls
 *   - Use Platform.toast.success/error/warning/info for all notifications
 *   - Use Platform.modal.open/close for all modal operations
 *   - Use Platform.sanitize.html() for all innerHTML assignments
 *   - Use Platform.log.debug/info/warn/error for all console output
 *   - Use Platform.error.boundary(asyncFn) to wrap event handlers
 *   - Use Platform.pagination.create() for all paginated tables
 *   - Use Platform.filter.create() for all search/filter UIs
 *   - Use Platform.selection.create() for all checkbox selection UIs
 *   - Use Platform.table.create() for all paginated data tables
 *   - Use Platform.table.alpineMixin() inside Alpine.data() table components
 *
 * ❌ DO NOT:
 *   - Call window.fetch() directly — always use Platform.fetch
 *   - Call alert() — always use Platform.toast
 *   - Use innerHTML directly — always use Platform.sanitize.html()
 *   - Use console.log/error directly — always use Platform.log
 *   - Create new modal systems — always use Platform.modal
 *   - Create new toast systems — always use Platform.toast
 *   - Create new pagination implementations — always use Platform.pagination
 *   - Create new filter implementations — always use Platform.filter
 *   - Create new selection implementations — always use Platform.selection
 *   - Attach functions directly to window — always use Platform.register()
 *   - Load modal_manager.js or modal-system.js (replaced by ui/modal.js)
 *   - Load toast-notifications.js (replaced by core/04-toast.js)
 *   - Load safe_html.js (replaced by core/02-sanitize.js)
 *   - Load api-fetch.js or api-client.js (replaced by core/03-fetch.js)
 *   - Load shared/data-table.js without also using Platform.pagination + Platform.selection
 *
 * ─── DEPRECATED FILES (do not load on new pages) ─────────────────────────────
 *
 * | Deprecated file                    | Replacement                    |
 * |------------------------------------|--------------------------------|
 * | js/safe_html.js                    | core/02-sanitize.js            |
 * | js/shared/api-fetch.js             | core/03-fetch.js               |
 * | scripts/api-client.js             | core/03-fetch.js               |
 * | js/shared/toast-notifications.js   | core/04-toast.js               |
 * | js/modal_manager.js                | ui/modal.js                    |
 * | js/modal-system.js                 | ui/modal.js                    |
 * | js/shared/data-table.js            | ui/table.js                    |
 * | js/sidebar.js                      | js/sidebar_hardened.js         |
 * | scripts/shadcn-data-table.js       | (empty — already replaced)     |
 * | scripts/shadcn-data-table-exact.js | (empty — already replaced)     |
 *
 * ─── FEATURE MODULE TEMPLATE ─────────────────────────────────────────────────
 *
 * (function (global) {
 *     'use strict';
 *
 *     // Declare dependencies
 *     global.Platform.require('log', 'fetch', 'toast', 'sanitize', 'error');
 *
 *     var log      = global.Platform.log.child('myFeature');
 *     var fetch    = global.Platform.fetch;
 *     var toast    = global.Platform.toast;
 *     var sanitize = global.Platform.sanitize;
 *     var error    = global.Platform.error;
 *
 *     // Alpine.data registration (if needed)
 *     // document.addEventListener('alpine:init', function () {
 *     //     Alpine.data('myFeature', function (config) { ... });
 *     // });
 *
 *     // DOM-ready initialisation
 *     global.document.addEventListener('DOMContentLoaded', error.boundary(async function () {
 *         // ... initialise feature ...
 *     }, 'myFeature:init'));
 *
 * }(window));
 */
