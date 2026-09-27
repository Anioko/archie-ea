/**
 * Owner Picker for the Application Edit form.
 *
 * Provides:
 *  - Debounced live-search (300 ms) against the person-picker endpoint
 *  - Enables the "Add owner" button only when a user is selected
 *  - POST /applications/<id>/owners to add
 *  - DELETE /applications/<id>/owners/<id> to remove
 *  - PUT /applications/<id>/owners/<id> to change type
 *  - Re-renders the owner list after each mutation
 *  - Platform.toast on error
 *
 * Requires: core/00-namespace.js, core/03-fetch.js, lucide
 */
(function () {
    'use strict';

    if (!window.Platform || !window.Platform.fetch) return;

    var OWNERSHIP_TYPES = ['primary', 'backup', 'technical', 'business'];

    // ── State ─────────────────────────────────────────────────────────────────
    var state = {
        selectedUserId: null,
        selectedLabel: null,
    };

    // ── DOM refs ──────────────────────────────────────────────────────────────
    var searchInput = document.getElementById('owner_picker_search');
    var resultsContainer = document.getElementById('owner_picker_results');
    var addBtn = document.getElementById('add-owner-btn');
    var typeSelect = document.getElementById('owner_type_select');
    var ownerListContainer = document.getElementById('owner-list');

    if (!searchInput || !resultsContainer || !addBtn || !ownerListContainer) return;

    var appId = searchInput.getAttribute('data-app-id');

    // ── Debounce helper ───────────────────────────────────────────────────────
    function debounce(fn, ms) {
        var timer = null;
        return function () {
            var args = arguments;
            var ctx = this;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
        };
    }

    // ── Search ────────────────────────────────────────────────────────────────
    function doSearch(query) {
        query = (query || '').trim();
        if (query.length < 2) {
            resultsContainer.innerHTML = '';
            resultsContainer.classList.add('hidden');
            return;
        }

        Platform.fetch.get('/applications/' + appId + '/owners/search', { q: query }, { silent: true })
            .then(function (data) {
                renderResults(data.results || []);
            })
            .catch(function () {
                // Platform.toast already handled by fetch core
            });
    }

    var debouncedSearch = debounce(doSearch, 300);

    searchInput.addEventListener('input', function () {
        debouncedSearch(searchInput.value);
        // Clear selection when user types anew
        state.selectedUserId = null;
        state.selectedLabel = null;
        addBtn.disabled = true;
    });

    searchInput.addEventListener('focus', function () {
        if (searchInput.value.trim().length >= 2) {
            doSearch(searchInput.value);
        }
    });

    // Hide results when clicking outside
    document.addEventListener('click', function (e) {
        if (!searchInput.contains(e.target) && !resultsContainer.contains(e.target)) {
            resultsContainer.classList.add('hidden');
        }
    });

    // ── Render results ────────────────────────────────────────────────────────
    function renderResults(users) {
        if (users.length === 0) {
            resultsContainer.innerHTML =
                '<div class="px-3 py-2 text-sm text-muted-foreground">No matching users</div>';
            resultsContainer.classList.remove('hidden');
            return;
        }

        var html = '';
        users.forEach(function (u) {
            html +=
                '<div class="owner-picker-result px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground border-b border-border last:border-b-0" data-user-id="' +
                u.id + '" data-label="' + escapeHtml(u.label) + '" data-email="' + escapeHtml(u.email) + '">' +
                '<div class="font-medium">' + escapeHtml(u.label) + '</div>' +
                '<div class="text-xs text-muted-foreground">' + escapeHtml(u.email) + '</div>' +
                '</div>';
        });
        resultsContainer.innerHTML = html;
        resultsContainer.classList.remove('hidden');

        // Bind click on each result
        resultsContainer.querySelectorAll('.owner-picker-result').forEach(function (el) {
            el.addEventListener('click', function () {
                state.selectedUserId = parseInt(el.getAttribute('data-user-id'), 10);
                state.selectedLabel = el.getAttribute('data-label');
                searchInput.value = state.selectedLabel;
                resultsContainer.classList.add('hidden');
                addBtn.disabled = false;
            });
        });
    }

    // ── Escape HTML for safe innerHTML ────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ── Add owner ─────────────────────────────────────────────────────────────
    addBtn.addEventListener('click', function () {
        if (!state.selectedUserId) return;
        var otype = typeSelect ? typeSelect.value : 'primary';

        addBtn.disabled = true;
        addBtn.innerHTML = '<i data-lucide="loader" class="h-4 w-4 animate-spin"></i> Adding…';

        Platform.fetch.post('/applications/' + appId + '/owners', {
            user_id: state.selectedUserId,
            ownership_type: otype,
        }, { silent: true })
            .then(function () {
                state.selectedUserId = null;
                state.selectedLabel = null;
                searchInput.value = '';
                addBtn.disabled = true;
                addBtn.innerHTML = '<i data-lucide="plus" class="h-4 w-4"></i> Add owner';
                return reloadOwnerList();
            })
            .catch(function () {
                addBtn.disabled = false;
                addBtn.innerHTML = '<i data-lucide="plus" class="h-4 w-4"></i> Add owner';
                // Toast already shown by Platform.fetch
            })
            .finally(function () {
                lucide.createIcons();
            });
    });

    // ── Remove owner ──────────────────────────────────────────────────────────
    ownerListContainer.addEventListener('click', function (e) {
        var btn = e.target.closest('.remove-owner-btn');
        if (!btn) return;
        var ownerId = btn.getAttribute('data-owner-id');
        if (!ownerId) return;

        if (!confirm('Remove this owner?')) return;

        Platform.fetch.delete('/applications/' + appId + '/owners/' + ownerId, { silent: true })
            .then(function () {
                return reloadOwnerList();
            })
            .catch(function () {
                // Toast already shown
            });
    });

    // ── Reload owner list ─────────────────────────────────────────────────────
    function reloadOwnerList() {
        return Platform.fetch.get('/applications/' + appId + '/owners', null, { silent: true })
            .then(function (data) {
                renderOwnerList(data.owners || []);
            })
            .catch(function () {
                // Toast already shown
            });
    }

    function renderOwnerList(owners) {
        if (owners.length === 0) {
            ownerListContainer.innerHTML =
                '<p class="text-sm text-muted-foreground" id="no-owners-msg">No owners assigned yet.</p>';
            return;
        }

        var html = '<p class="text-sm font-medium">Current owners</p>';
        owners.forEach(function (o) {
            var typeLabel = o.ownership_type.charAt(0).toUpperCase() + o.ownership_type.slice(1);
            html +=
                '<div class="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2 text-sm" data-owner-id="' +
                o.id + '">' +
                '<div>' +
                '<span class="font-medium">' + escapeHtml(o.user_name) + '</span>' +
                '<span class="text-muted-foreground ml-2">(' + typeLabel + ')</span>' +
                '</div>' +
                '<button type="button" class="text-destructive hover:text-destructive-emphasis text-xs remove-owner-btn" data-owner-id="' +
                o.id + '" data-app-id="' + appId + '">Remove</button>' +
                '</div>';
        });
        ownerListContainer.innerHTML = html;
        lucide.createIcons();
    }

    // ── Initial load ──────────────────────────────────────────────────────────
    reloadOwnerList();

})();