/**
 * enterprise/work_packages_table.js — Work Packages Table Alpine component.
 *
 * Extends Platform.dataTable.mixin() with:
 *   - Inline edit modal for work package fields
 *   - Bulk delete with typed confirmation
 *   - Status / priority badge helpers
 *   - Progress bar width helper
 *
 * Requires: Platform.dataTable (components/data_table.js), Platform.fetch, Platform.toast, Platform.modal
 */
(function () {
    'use strict';

    Platform.require('fetch', 'toast', 'modal', 'dataTable');

    const STATUS_OPTIONS   = ['Planned', 'In Progress', 'Completed', 'Blocked', 'On Hold'];
    const PRIORITY_OPTIONS = ['Critical', 'High', 'Normal', 'Low'];

    document.addEventListener('alpine:init', function () {
        Alpine.data('workPackagesTable', function () {
            return Object.assign(
                {},
                Platform.dataTable.mixin({
                    apiUrl:     '/enterprise/api/work-packages',
                    perPage:    25,
                    itemsKey:   'work_packages',
                    storageKey: 'work-packages'
                }),
                {
                    // ── Edit form state ───────────────────────────────
                    editForm: {
                        name:             '',
                        summary:          '',
                        status:           'Planned',
                        priority:         'Normal',
                        percent_complete: 0,
                        target_date:      ''
                    },
                    editingId:  null,
                    saveError:  '',
                    editSaving: false,

                    // ── Bulk delete state ─────────────────────────────
                    bulkConfirmText:  '',
                    deleteInProgress: false,

                    // ── Options lists exposed to templates ────────────
                    statusOptions:   STATUS_OPTIONS,
                    priorityOptions: PRIORITY_OPTIONS,

                    // ── Init ──────────────────────────────────────────
                    init: function () {
                        this._tableInit();
                    },

                    // ── Edit modal ─────────────────────────────────────
                    openEditModal: function (row) {
                        this.editingId                    = row.id;
                        this.editForm.name                = row.name             || '';
                        this.editForm.summary             = row.summary          || '';
                        this.editForm.status              = row.status           || 'Planned';
                        this.editForm.priority            = row.priority         || 'Normal';
                        this.editForm.percent_complete    = row.percent_complete != null ? row.percent_complete : 0;
                        this.editForm.target_date         = row.target_date      || '';
                        this.saveError  = '';
                        this.editSaving = false;
                        Platform.modal.open('edit-work-package-modal');
                    },

                    saveWorkPackage: function () {
                        if (this.editSaving) return;
                        this.editSaving = true;
                        this.saveError  = '';
                        const self = this;
                        fetch('/enterprise/api/work-packages/' + this.editingId, {
                            method:  'PATCH',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken':  (document.querySelector('meta[name=csrf-token]') || {}).content || ''
                            },
                            body: JSON.stringify(this.editForm)
                        })
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                            if (data.error) {
                                self.saveError = data.error;
                            } else {
                                Platform.modal.close('edit-work-package-modal');
                                self.refresh();
                                Platform.toast.success('Work package updated.');
                            }
                        })
                        .catch(function () {
                            self.saveError = 'Save failed.';
                        })
                        .finally(function () {
                            self.editSaving = false;
                        });
                    },

                    // ── Bulk delete ────────────────────────────────────
                    confirmBulkDelete: function () {
                        this.bulkConfirmText = '';
                        Platform.modal.open('bulk-delete-work-package-modal');
                    },

                    executeBulkDelete: async function () {
                        if (!this.bulkDeleteEnabled()) return;
                        this.deleteInProgress = true;
                        try {
                            const response = await fetch('/enterprise/api/work-packages/bulk', {
                                method:  'DELETE',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken':  (document.querySelector('meta[name=csrf-token]') || {}).content || ''
                                },
                                body: JSON.stringify({ ids: this._selectedIds.slice() })
                            });
                            const data = await response.json();
                            if (data.error) {
                                Platform.toast.error(data.error);
                            } else {
                                Platform.modal.close('bulk-delete-work-package-modal');
                                this.bulkConfirmText = '';
                                this.clearSelection();
                                this._loadItems();
                                Platform.toast.success('Work packages deleted.');
                            }
                        } catch (e) {
                            Platform.toast.error((e && e.message) || 'Delete failed.');
                        } finally {
                            this.deleteInProgress = false;
                        }
                    },

                    bulkDeleteEnabled: function () {
                        return this.bulkConfirmText === 'DELETE' && this._selectedIds.length > 0;
                    },

                    selectionCount: function () {
                        if (this.selectAllState === 'cross-page') return this.totalItems;
                        return this._selectedIds.length;
                    },

                    // ── Badge helpers ──────────────────────────────────
                    statusClass: function (status) {
                        if (status === 'Completed')  return 'bg-success/20 text-success';
                        if (status === 'In Progress') return 'bg-primary/20 text-primary';
                        if (status === 'Blocked')    return 'bg-destructive/20 text-destructive';
                        return 'bg-muted text-muted-foreground';
                    },

                    priorityClass: function (priority) {
                        if (priority === 'Critical') return 'bg-destructive/20 text-destructive';
                        if (priority === 'High')     return 'bg-warning/20 text-warning';
                        return 'bg-muted text-muted-foreground';
                    },

                    progressWidth: function (pct) {
                        return Math.min(100, Math.max(0, pct || 0)) + '%';
                    }
                }
            );
        });
    });
}());
