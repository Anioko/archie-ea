/**
 * ai_chat/ai_personas_table.js — AI Prompt Templates data table Alpine component.
 *
 * Extends Platform.dataTable.mixin() with:
 *   - Inline Edit modal for prompt template fields
 *   - Create new prompt template
 *   - Bulk delete with typed confirmation
 *   - Category badge helper
 *
 * Requires: Platform.dataTable (components/data_table.js), Platform.fetch, Platform.toast, Platform.modal
 */
(function () {
    'use strict';

    Platform.require('fetch', 'toast', 'modal', 'dataTable');

    document.addEventListener('alpine:init', function () {
        Alpine.data('aiPersonasTable', function () {
            return Object.assign(
                {},
                Platform.dataTable.mixin({
                    apiUrl: '/ai-chat/api/prompt-templates',
                    perPage: 25,
                    itemsKey: 'prompt_templates',
                    storageKey: 'ai-prompt-templates'
                }),
                {
                    // ── Edit form state ───────────────────────────────
                    editForm: {
                        id: null,
                        name: '',
                        description: '',
                        category: '',
                        system_prompt: '',
                        user_prompt_template: ''
                    },
                    editSaving: false,
                    editError: '',

                    // ── Create form state ─────────────────────────────
                    createForm: {
                        name: '',
                        description: '',
                        category: 'Generation',
                        system_prompt: '',
                        user_prompt_template: ''
                    },
                    createSaving: false,
                    createError: '',

                    // ── Bulk delete state ─────────────────────────────
                    deleteConfirmText: '',
                    deleteInProgress: false,

                    // ── Init ──────────────────────────────────────────
                    init: function () {
                        this._tableInit();
                    },

                    // ── Edit modal ─────────────────────────────────────
                    openEditModal: function (row) {
                        this.editForm.id                   = row.id;
                        this.editForm.name                 = row.name || '';
                        this.editForm.description          = row.description || '';
                        this.editForm.category             = row.category || '';
                        this.editForm.system_prompt        = row.system_prompt || '';
                        this.editForm.user_prompt_template = row.user_prompt_template || '';
                        this.editError  = '';
                        this.editSaving = false;
                        Platform.modal.open('edit-prompt-template-modal');
                    },

                    saveEdit: async function () {
                        if (this.editSaving) return;
                        this.editSaving = true;
                        this.editError  = '';
                        try {
                            const result = await Platform.fetch.patch(
                                '/ai-chat/api/prompt-templates/' + this.editForm.id,
                                {
                                    name:                 this.editForm.name,
                                    description:          this.editForm.description,
                                    category:             this.editForm.category,
                                    system_prompt:        this.editForm.system_prompt,
                                    user_prompt_template: this.editForm.user_prompt_template
                                }
                            );
                            if (result && result.success) {
                                Platform.modal.close('edit-prompt-template-modal');
                                this._loadItems();
                                Platform.toast.success('Prompt template updated.');
                            } else {
                                this.editError = (result && result.error) || 'Save failed.';
                            }
                        } catch (e) {
                            this.editError = (e && e.message) || 'Network error.';
                        } finally {
                            this.editSaving = false;
                        }
                    },

                    // ── Bulk delete ────────────────────────────────────
                    confirmBulkDelete: function () {
                        this.deleteConfirmText = '';
                        Platform.modal.open('bulk-delete-confirm-modal');
                    },

                    executeBulkDelete: async function () {
                        if (this.deleteConfirmText !== 'DELETE') return;
                        this.deleteInProgress = true;
                        try {
                            await Platform.fetch('/ai-chat/api/prompt-templates/bulk', {
                                method: 'DELETE',
                                body: { ids: this._selectedIds.slice() }
                            });
                            Platform.modal.close('bulk-delete-confirm-modal');
                            this.deleteConfirmText = '';
                            this.clearSelection();
                            this._loadItems();
                            Platform.toast.success('Prompt templates deleted.');
                        } catch (e) {
                            Platform.toast.error((e && e.message) || 'Delete failed.');
                        } finally {
                            this.deleteInProgress = false;
                        }
                    },

                    // ── Helpers ────────────────────────────────────────
                    selectionCount: function () {
                        return this._selectedIds.length + ' prompt template(s)';
                    },

                    categoryClass: function (cat) {
                        if (cat === 'Audit') {
                            return 'bg-primary/10 text-primary/90 dark:bg-blue-900/30 dark:text-blue-300';
                        }
                        if (cat === 'Generation') {
                            return 'bg-emerald-500/10 text-green-800 dark:bg-green-900/30 dark:text-green-300';
                        }
                        if (cat === 'Transformation') {
                            return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300';
                        }
                        return 'bg-muted text-muted-foreground';
                    }
                }
            );
        });
    });
}());
