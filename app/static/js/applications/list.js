/**
 * Applications Portfolio — Unified Alpine.js Component
 *
 * Registered as: Alpine.data('appPortfolio', appPortfolio)
 *
 * Systems:
 *   - Modal manager  : openPortfolioModal(key) / closePortfolioModal()
 *   - Toast/notify   : notify(msg, type)
 *   - Filter system  : onFilterChange() / clearFilters() / hasActiveFilters()
 *   - Pagination     : goToPage(n) / changePageSize(n)
 *   - Row selection  : toggleRow(id, checked) / toggleSelectAll(checked)
 *   - Bulk actions   : bulkExportSelected() / confirmBulkDelete()
 *   - Mapping        : openMappingForApp(id, name, type)
 *   - Export         : exportCSV()
 */
function appPortfolio() {
  return {
    // ── State ──────────────────────────────────────────────────────────────
    loading: false,
    selectedIds: new Set(),
    filters: {
      search: '',
      type: '',
      status: '',
      domain: '',
      capability_level: '',
      process_level: '',
    },

    // ── Lifecycle ──────────────────────────────────────────────────────────
    init() {
      // Sync filter state from current URL params
      const params = new URLSearchParams(window.location.search);
      this.filters.search           = params.get('search')            || '';
      this.filters.type             = params.get('type')              || '';
      this.filters.status           = params.get('status')            || '';
      this.filters.domain           = params.get('domain')            || '';
      this.filters.capability_level = params.get('capability_level')  || '';
      this.filters.process_level    = params.get('process_level')     || '';

      // Mark page ready (removes skeleton)
      this.$nextTick(() => { this.loading = false; });

      // Keyboard: Escape — Platform.modal handles LIFO ESC; no manual listener needed here.
    },

    // ── Modal system ───────────────────────────────────────────────────────
    // Modal keys map to element IDs: 'create' → 'modal-create', etc.
    openPortfolioModal(key) {
      const modalId = 'modal-' + key;
      Platform.modal.open(modalId);
    },

    closePortfolioModal() {
      // Close all modals opened via this component
      ['create', 'import', 'match-vendors', 'consolidation', 'bulk-map'].forEach(key => {
        const modalId = 'modal-' + key;
        if (Platform.modal.isOpen(modalId)) {
          Platform.modal.close(modalId);
        }
      });
    },

    // ── Toast / notification ───────────────────────────────────────────────
    notify(message, type = 'default') {
      if (window.Platform && window.Platform.toast) {
        if (type === 'error') Platform.toast.error(message);
        else if (type === 'success') Platform.toast.success(message);
        else if (type === 'warning') Platform.toast.warning(message);
        else Platform.toast.info(message);
        return;
      }
      // Legacy fallback: appToast store
      if (typeof Alpine !== 'undefined' && Alpine.store('appToast')) {
        const t = Alpine.store('appToast');
        if (t._timer) clearTimeout(t._timer);
        t.message = message;
        t.type    = type;
        t.visible = true;
        t._timer  = setTimeout(() => { t.visible = false; }, 4000);
      }
    },

    // ── Filter system ──────────────────────────────────────────────────────
    onFilterChange() {
      this._navigate(1);
    },

    clearFilters() {
      this.filters.search           = '';
      this.filters.type             = '';
      this.filters.status           = '';
      this.filters.domain           = '';
      this.filters.capability_level = '';
      this.filters.process_level    = '';
      this._navigate(1);
    },

    hasActiveFilters() {
      return Object.values(this.filters).some(v => v !== '');
    },

    // ── Pagination ─────────────────────────────────────────────────────────
    goToPage(page) {
      this._navigate(page);
    },

    changePageSize(size) {
      this._navigate(1, parseInt(size, 10));
    },

    _navigate(page, pageSize = null) {
      const params = new URLSearchParams(window.location.search);
      params.set('page', page);
      if (pageSize) params.set('page_size', pageSize);

      // Apply current filter state
      Object.entries(this.filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
        else params.delete(k);
      });

      window.location.href = `${window.location.pathname}?${params.toString()}`;
    },

    // ── Row selection ──────────────────────────────────────────────────────
    toggleRow(id, checked) {
      if (checked) this.selectedIds.add(id);
      else         this.selectedIds.delete(id);
      // Trigger Alpine reactivity for Set (Alpine 3 doesn't track Set mutations)
      this.selectedIds = new Set(this.selectedIds);
    },

    toggleSelectAll(checked) {
      if (checked) {
        document.querySelectorAll('[data-app-id]').forEach(row => {
          if (row && row.dataset) {
            const id = parseInt(row.dataset.appId, 10);
            if (!isNaN(id)) this.selectedIds.add(id);
          }
        });
      } else {
        this.selectedIds.clear();
      }
      this.selectedIds = new Set(this.selectedIds);
    },

    clearSelection() {
      this.selectedIds = new Set();
    },

    allSelected() {
      const rows = document.querySelectorAll('[data-app-id]');
      return rows.length > 0 && [...rows].every(r => r && r.dataset && this.selectedIds.has(parseInt(r.dataset.appId, 10)));
    },

    someSelected() {
      const rows = document.querySelectorAll('[data-app-id]');
      const count = [...rows].filter(r => r && r.dataset && this.selectedIds.has(parseInt(r.dataset.appId, 10))).length;
      return count > 0 && count < rows.length;
    },

    // ── Export ─────────────────────────────────────────────────────────────
    exportCSV() {
      const params = new URLSearchParams(window.location.search);
      params.delete('export');
      window.location.href = `/applications/export/csv?${params.toString()}`;
    },

    bulkExportSelected() {
      if (this.selectedIds.size === 0) {
        this.notify('No applications selected.', 'error');
        return;
      }
      const ids = [...this.selectedIds].join(',');
      window.location.href = `/applications/export/csv?ids=${ids}`;
    },

    // ── Bulk delete ────────────────────────────────────────────────────────
    confirmBulkDelete() {
      if (this.selectedIds.size === 0) return;
      const count = this.selectedIds.size;
      const ids = [...this.selectedIds];
      const self = this;
      const modalId = window.modalManager.createModal({
          title: 'Delete Applications',
          content: '<p class="text-sm text-muted-foreground">Delete ' + count + ' selected application' + (count !== 1 ? 's' : '') + '? This cannot be undone.</p>',
          size: 'small',
          buttons: [
              { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
              { text: 'Delete', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'delete', handler: function() { self._bulkDelete(ids); } }
          ]
      });
      window.modalManager.open(modalId);
    },

    async _bulkDelete(ids) {
      try {
        await Platform.fetch('/applications/bulk-delete', {
          method: 'POST',
          body: { ids },
          errorMsg: 'Failed to delete selected applications'
        });
        this.notify(`Deleted ${ids.length} application${ids.length !== 1 ? 's' : ''}.`, 'success');
        this.clearSelection();
        setTimeout(() => window.location.reload(), 800);
      } catch (err) {
        console.error('[appPortfolio] bulk delete error:', err);
        Platform.toast.error('Delete failed. Please try again.');
        this.notify('Delete failed. Please try again.', 'error');
      }
    },

    // ── Mapping ────────────────────────────────────────────────────────────
    openMappingForApp(id, name, mappingType) {
      const normalizedType = mappingType || 'capability';

      // Delegate to the unified mapping modal if registered
      if (typeof window.openUnifiedMappingModal === 'function') {
        if (typeof window.initUnifiedMappingModal === 'function') {
          window.initUnifiedMappingModal({
            context: normalizedType,
            apiEndpoint: '/capability-map/api',
          });
        }

        // unified_mapping_modal.js signature: (targetId, targetName, options)
        // fallback shim signature in ui/modal.js: (payload)
        if (window.UnifiedMappingModal) {
          window.openUnifiedMappingModal(id, name, {
            context: normalizedType,
            targetType: normalizedType,
          });
        } else {
          window.openUnifiedMappingModal({
            id,
            name,
            type: normalizedType,
          });
        }
        return;
      }

      // Fallback: navigate to the mapping page
      const routes = {
        capability: `/applications/${id}/map-capabilities`,
        apqc:       `/applications/${id}/map-processes`,
        vendor:     `/applications/${id}/map-vendors`,
        archimate:  `/applications/${id}/map-archimate`,
      };
      const url = routes[normalizedType] || `/applications/${id}`;
      window.location.href = url;
    },
  };
}

/**
 * Create Application inline form component.
 * Used inside the #modal-create panel.
 */
function applicationCreateForm() {
  return {
    submitting: false,
    errorMsg: '',
    form: {
      name: '',
      application_code: '',
      application_type: '',
      criticality: '',
      deployment_status: '',
      business_owner: '',
      description: '',
    },

    async submit() {
      // FAR-017: Prevent double-click duplicates
      if (this.submitting) return;
      if (!this.form.name.trim()) {
        this.errorMsg = 'Application name is required.';
        return;
      }
      this.submitting = true;
      this.errorMsg   = '';

      const url = window.__APP_CONFIG__?.createApplicationUrl || '/applications/create';

      try {
        const data = await Platform.fetch(url, {
          method: 'POST',
          body: this.form,
          silent: true
        });

        // Success: close modal and reload
        Platform.modal.close('modal-create');
        if (data.redirect) {
          window.location.href = data.redirect;
        } else {
          window.location.reload();
        }
      } catch (err) {
        console.error('[applicationCreateForm] submit error:', err);
        const errorDetail = (err.data && (err.data.error || err.data.message)) || err.message || 'An unexpected error occurred';
        this.errorMsg = errorDetail;
        Platform.toast.error('Failed to create application: ' + errorDetail);
      } finally {
        this.submitting = false;
      }
    },
  };
}

// ── Alpine registration ──────────────────────────────────────────────────────
document.addEventListener('alpine:init', () => {
  Alpine.store('appToast', { visible: false, message: '', type: 'default', _timer: null });
  Alpine.data('appPortfolio', appPortfolio);
  Alpine.data('applicationCreateForm', applicationCreateForm);

  // Handle close-modal dispatch from modal backdrop / cancel buttons
  document.addEventListener('app-close-modal', () => {
    if (Platform.modal.isOpen('modal-create')) {
      Platform.modal.close('modal-create');
    }
  });
});
