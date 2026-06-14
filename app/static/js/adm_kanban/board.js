/**
 * ADM Kanban Board — Alpine.js Component
 *
 * TOGAF ADM-aligned Kanban board with status-based columns,
 * phase filtering, SortableJS drag-and-drop, and card detail panel.
 *
 * Depends on: Alpine.js, SortableJS, Platform.fetch, Platform.toast
 */

/* global Sortable, Platform, Alpine, lucide */

function admKanbanBoard() {
    'use strict';

    const config = window.__KANBAN_CONFIG__ || {};

    const CARD_TEMPLATES = {
        scope_definition: { title: 'Define Architecture Scope', description: 'Establish the boundaries and scope of the architecture effort.', type: 'design', priority: 'high', phase: 'PRELIM' },
        stakeholder_analysis: { title: 'Conduct Stakeholder Analysis', description: 'Identify and analyze all stakeholders. Define their concerns, influence, and communication requirements.', type: 'design', priority: 'high', phase: 'PRELIM' },
        architecture_principles: { title: 'Establish Architecture Principles', description: 'Define fundamental principles that will guide all architecture decisions.', type: 'design', priority: 'high', phase: 'PRELIM' },
        business_case: { title: 'Develop Business Case', description: 'Create a compelling business case demonstrating the value of the proposed architecture initiative.', type: 'design', priority: 'high', phase: 'A' },
        architecture_vision: { title: 'Develop Architecture Vision', description: 'Create a high-level vision of the target architecture addressing business needs.', type: 'design', priority: 'high', phase: 'A' },
        business_capabilities: { title: 'Develop Business Capabilities', description: 'Define and document business capabilities required to achieve strategic objectives.', type: 'design', priority: 'high', phase: 'B' },
        value_streams: { title: 'Define Value Streams', description: 'Map end-to-end value streams that deliver value to customers and stakeholders.', type: 'design', priority: 'high', phase: 'B' },
        data_architecture: { title: 'Develop Data Architecture', description: 'Design logical and physical data structures supporting business and application architectures.', type: 'design', priority: 'high', phase: 'C' },
        application_architecture: { title: 'Develop Application Architecture', description: 'Define application portfolio and interfaces required to support business capabilities.', type: 'design', priority: 'high', phase: 'C' },
        technology_standards: { title: 'Define Technology Standards', description: 'Establish technology standards and guidelines for consistency and interoperability.', type: 'design', priority: 'high', phase: 'D' },
        infrastructure_design: { title: 'Design Infrastructure', description: 'Design infrastructure components (servers, networks, storage) required to support applications.', type: 'design', priority: 'high', phase: 'D' },
        gap_analysis: { title: 'Perform Gap Analysis', description: 'Identify gaps between current and target architectures.', type: 'design', priority: 'high', phase: 'E' },
        migration_planning: { title: 'Plan Migration Strategy', description: 'Develop a phased migration plan to transition from current to target architecture.', type: 'design', priority: 'high', phase: 'F' },
        architecture_contracts: { title: 'Develop Architecture Contracts', description: 'Create contracts defining responsibilities and deliverables for implementing the architecture.', type: 'design', priority: 'high', phase: 'G' },
        continuous_improvement: { title: 'Drive Continuous Improvement', description: 'Continuously improve the architecture practice to deliver organizational value.', type: 'design', priority: 'medium', phase: 'H' }
    };

    return {
        boardId: config.boardId,
        cards: config.cards || {},
        phases: config.phases || {},
        phaseStats: config.phaseStats || {},
        elementIndex: config.elementIndex || {},
        wipLimits: config.wipLimits || {},
        phaseIdMap: config.phaseIdMap || {},
        phaseNameMap: config.phaseNameMap || {},
        users: config.users || [],
        currentAdmPhase: config.currentAdmPhase || null,
        currentPhaseId: config.currentPhaseId || null,

        columns: [
            { id: 'backlog', label: 'Backlog', icon: 'inbox' },
            { id: 'todo', label: 'To Do', icon: 'circle' },
            { id: 'in_progress', label: 'In Progress', icon: 'loader' },
            { id: 'review', label: 'In Review', icon: 'eye' },
            { id: 'done', label: 'Done', icon: 'check-circle' }
        ],

        selectedPhase: 'all',
        searchQuery: '',
        filters: { priority: '', assignee: '', type: '' },

        detailPanelOpen: false,
        activeCardId: null,
        detailTab: 'relationships',

        showCreateModal: false,
        editingCardId: null,
        submitting: false,
        newCard: {},

        showDeleteConfirm: false,
        deleteTargetId: null,

        _sortables: [],

        get totalCards() {
            if (this.selectedPhase === 'all') return Object.keys(this.cards).length;
            return Object.values(this.cards).filter(function(c) {
                return c.phase_code === this.selectedPhase;
            }.bind(this)).length;
        },

        get activeCard() {
            return this.activeCardId ? this.cards[this.activeCardId] : null;
        },

        init: function() {
            this.newCard = this._emptyCard();

            // When board is scoped to a phase, default the filter to that phase
            if (this.currentAdmPhase) {
                this.selectedPhase = this.currentAdmPhase;
            }

            this._initKeyboardShortcuts();

            this.$nextTick(function() {
                this._initSortable();
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }.bind(this));

            this.$watch('selectedPhase', function() {
                this.$nextTick(function() {
                    this._reinitSortable();
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                }.bind(this));
            }.bind(this));

            this.$watch('searchQuery', function() {
                this.$nextTick(function() {
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                }.bind(this));
            }.bind(this));

            this.$watch('filters', function() {
                this.$nextTick(function() {
                    if (typeof lucide !== 'undefined') lucide.createIcons();
                }.bind(this));
            }.bind(this));
        },

        _emptyCard: function() {
            return {
                title: '',
                description: '',
                status: 'todo',
                priority: 'medium',
                card_type: 'requirement',
                adm_phase_id: '',
                assigned_to_id: '',
                template: ''
            };
        },

        // ── Column & Card Getters ────────────────────────────────────────

        getColumnCards: function(status) {
            const self = this;
            return Object.values(this.cards)
                .filter(function(c) { return c.status === status; })
                .filter(function(c) {
                    return self.selectedPhase === 'all' || c.phase_code === self.selectedPhase;
                })
                .filter(function(c) {
                    if (self.searchQuery) {
                        const q = self.searchQuery.toLowerCase();
                        return (c.title || '').toLowerCase().indexOf(q) !== -1 ||
                               (c.description || '').toLowerCase().indexOf(q) !== -1;
                    }
                    return true;
                })
                .filter(function(c) {
                    if (self.filters.assignee && String(c.assigned_to_id) !== String(self.filters.assignee)) return false;
                    if (self.filters.priority && c.priority !== self.filters.priority) return false;
                    if (self.filters.type && c.card_type !== self.filters.type) return false;
                    return true;
                })
                .sort(function(a, b) { return (a.position || 0) - (b.position || 0); });
        },

        getPhaseCount: function(phaseCode) {
            if (phaseCode === 'all') return Object.keys(this.cards).length;
            return Object.values(this.cards).filter(function(c) {
                return c.phase_code === phaseCode;
            }).length;
        },

        selectPhase: function(code) {
            this.selectedPhase = code;
            if (window.Alpine && Alpine.store('announcer')) {
                Alpine.store('announcer').announce(
                    code === 'all' ? 'Showing all phases' : 'Filtered to ' + (this.phaseNameMap[code] || code)
                );
            }
        },

        clearFilters: function() {
            this.searchQuery = '';
            this.filters = { priority: '', assignee: '', type: '' };
        },

        // ── Card Detail Panel ────────────────────────────────────────────

        openCard: function(cardId) {
            this.activeCardId = String(cardId);
            this.detailPanelOpen = true;
            this.detailTab = 'relationships';
            this.$nextTick(function() {
                if (typeof lucide !== 'undefined') lucide.createIcons();
            });
        },

        closeDetailPanel: function() {
            this.detailPanelOpen = false;
            this.activeCardId = null;
        },

        // ── Create/Edit Modal ────────────────────────────────────────────

        openCreateModal: function(status) {
            this.editingCardId = null;
            this.newCard = this._emptyCard();
            if (status) this.newCard.status = status;
            // Pre-set phase: scoped board takes priority, then active filter tab
            if (this.currentPhaseId) {
                this.newCard.adm_phase_id = String(this.currentPhaseId);
            } else if (this.selectedPhase !== 'all') {
                const phaseId = this._phaseCodeToId(this.selectedPhase);
                if (phaseId) this.newCard.adm_phase_id = String(phaseId);
            }
            this.showCreateModal = true;
            this.$nextTick(function() {
                const titleInput = document.getElementById('new-card-title');
                if (titleInput) titleInput.focus();
            });
        },

        applyTemplate: function(key) {
            const tmpl = CARD_TEMPLATES[key];
            if (!tmpl) return;
            this.newCard.title = tmpl.title;
            this.newCard.description = tmpl.description;
            this.newCard.card_type = tmpl.type;
            this.newCard.priority = tmpl.priority;
            // Auto-set phase from template (unless board is scoped — already locked)
            if (tmpl.phase && !this.currentPhaseId) {
                const phaseId = this._phaseCodeToId(tmpl.phase);
                if (phaseId) this.newCard.adm_phase_id = String(phaseId);
            }
        },

        submitCard: function() {
            if (!this.newCard.title || !this.newCard.title.trim()) {
                Platform.toast.error('Card title is required');
                return;
            }
            // FAR-017: Prevent double-click duplicates
            if (this.submitting) return;
            if (!this.newCard.adm_phase_id) {
                Platform.toast.error('ADM Phase is required');
                return;
            }
            // Enforce phase scope on create (not edit — phase is read-only for edits)
            if (this.currentPhaseId && !this.editingCardId &&
                parseInt(this.newCard.adm_phase_id, 10) !== this.currentPhaseId) {
                Platform.toast.error('Cards must be created in the current board phase');
                return;
            }
            this.submitting = true;

            const self = this;
            const isEdit = !!this.editingCardId;
            const url = isEdit
                ? config.apiBase + '/cards/' + this.editingCardId
                : config.apiBase + '/boards/' + this.boardId + '/cards';
            const method = isEdit ? 'PUT' : 'POST';

            const payload = {
                title: this.newCard.title.trim(),
                description: this.newCard.description || '',
                status: this.newCard.status || 'todo',
                priority: this.newCard.priority || 'medium',
                card_type: this.newCard.card_type || 'requirement',
                adm_phase_id: parseInt(this.newCard.adm_phase_id, 10),
                assigned_to_id: this.newCard.assigned_to_id ? parseInt(this.newCard.assigned_to_id, 10) : null
            };

            Platform.fetch(url, { method: method, body: payload })
                .then(function(data) {
                    self.submitting = false;
                    self.showCreateModal = false;

                    const phaseCode = self.phaseIdMap[payload.adm_phase_id] || 'A';
                    const phaseName = self.phaseNameMap[phaseCode] || 'Unknown';

                    if (isEdit) {
                        Object.assign(self.cards[String(self.editingCardId)], payload, {
                            phase_code: phaseCode,
                            phase_name: phaseName
                        });
                        Platform.toast.success('Card updated');
                    } else {
                        const newId = data.id || (data.card && data.card.id);
                        if (newId) {
                            const assignee = self.users.find(function(u) { return u.id === payload.assigned_to_id; });
                            self.cards[String(newId)] = Object.assign({}, payload, {
                                id: newId,
                                phase_code: phaseCode,
                                phase_name: phaseName,
                                assigned_to_name: assignee ? assignee.name : null,
                                position: 0,
                                due_date: null,
                                created_at: new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }),
                                created_at_iso: new Date().toISOString(),
                                archimate_element_ids: [],
                                archimate_elements: [],
                                depends_on: [],
                                blocks: [],
                                arb_review_id: null,
                                application_ids: [],
                                system_ids: [],
                                initiative_ids: []
                            });
                        }
                        Platform.toast.success('Card created');
                    }
                    self.$nextTick(function() {
                        self._reinitSortable();
                        if (typeof lucide !== 'undefined') lucide.createIcons();
                    });
                })
                .catch(function(err) {
                    self.submitting = false;
                    Platform.toast.error('Failed to save card: ' + (err.message || 'Unknown error'));
                });
        },

        // ── Card Field Updates (inline from detail panel) ────────────────

        saveCardField: function(cardId, field, value) {
            // Block phase changes when board is scoped
            if (field === 'adm_phase_id' && this.currentPhaseId) {
                Platform.toast.error('Cannot change phase while board is scoped');
                return;
            }
            const payload = {};
            payload[field] = value === '' ? null : value;

            Platform.fetch(config.apiBase + '/cards/' + cardId, {
                method: 'PUT',
                body: payload,
                silent: true
            }).then(function() {
                Platform.toast.success('Updated', { duration: 1500 });
            }).catch(function(err) {
                Platform.toast.error('Update failed: ' + (err.message || 'Unknown error'));
            });
        },

        moveCardToStatus: function(cardId, newStatus) {
            const card = this.cards[String(cardId)];
            if (!card) return;

            const wipLimit = this.wipLimits[newStatus];
            if (wipLimit) {
                const currentCount = this.getColumnCards(newStatus).length;
                if (currentCount >= wipLimit) {
                    Platform.toast.warning('WIP limit reached for ' + newStatus.replace('_', ' ') + ' (' + wipLimit + ')');
                }
            }

            Platform.fetch(config.apiBase + '/cards/' + cardId, {
                method: 'PUT',
                body: { status: newStatus },
                silent: true
            }).then(function() {
                Platform.toast.success('Status updated');
                if (Alpine.store('announcer')) {
                    Alpine.store('announcer').announce('Card moved to ' + newStatus.replace('_', ' '));
                }
            }).catch(function(err) {
                Platform.toast.error('Move failed: ' + (err.message || 'Unknown error'));
            });

            this.$nextTick(function() {
                this._reinitSortable();
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }.bind(this));
        },

        updateCardPhaseCode: function(card) {
            const phaseId = parseInt(card.adm_phase_id, 10);
            card.phase_code = this.phaseIdMap[phaseId] || card.phase_code;
            card.phase_name = this.phaseNameMap[card.phase_code] || card.phase_name;
        },

        updateAssigneeName: function(card) {
            if (!card.assigned_to_id) {
                card.assigned_to_name = null;
                return;
            }
            const user = this.users.find(function(u) { return String(u.id) === String(card.assigned_to_id); });
            card.assigned_to_name = user ? user.name : null;
        },

        // ── Delete Card ──────────────────────────────────────────────────

        confirmDeleteCard: function(cardId) {
            this.deleteTargetId = cardId;
            this.showDeleteConfirm = true;
        },

        deleteCard: function(cardId) {
            const self = this;
            Platform.fetch(config.apiBase + '/cards/' + cardId, { method: 'DELETE' })
                .then(function() {
                    delete self.cards[String(cardId)];
                    self.showDeleteConfirm = false;
                    self.deleteTargetId = null;
                    if (self.activeCardId === String(cardId)) {
                        self.closeDetailPanel();
                    }
                    Platform.toast.success('Card deleted');
                    self.$nextTick(function() {
                        self._reinitSortable();
                        if (typeof lucide !== 'undefined') lucide.createIcons();
                    });
                })
                .catch(function(err) {
                    Platform.toast.error('Delete failed: ' + (err.message || 'Unknown error'));
                });
        },

        // ── Utility ──────────────────────────────────────────────────────

        _phaseCodeToId: function(code) {
            const map = this.phaseIdMap;
            for (let id in map) {
                if (map[id] === code) return parseInt(id, 10);
            }
            return null;
        },

        formatDate: function(dateStr) {
            if (!dateStr) return '';
            try {
                const d = new Date(dateStr);
                return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } catch (e) {
                return dateStr;
            }
        },

        isOverdue: function(dateStr) {
            if (!dateStr) return false;
            try {
                return new Date(dateStr) < new Date();
            } catch (e) {
                return false;
            }
        },

        // ── SortableJS Drag & Drop ───────────────────────────────────────

        _initSortable: function() {
            if (typeof Sortable === 'undefined') return;

            const self = this;
            this.columns.forEach(function(col) {
                const el = document.getElementById('sortable-' + col.id);
                if (!el) return;

                const sortable = Sortable.create(el, {
                    group: 'kanban',
                    animation: 150,
                    ghostClass: 'sortable-ghost',
                    chosenClass: 'sortable-chosen',
                    dragClass: 'sortable-drag',
                    filter: 'button',
                    draggable: '.kanban-card',
                    delay: 50,
                    delayOnTouchOnly: true,
                    onEnd: function(evt) {
                        self._handleDrop(evt);
                    }
                });
                self._sortables.push(sortable);
            });
        },

        _reinitSortable: function() {
            this._sortables.forEach(function(s) {
                if (s && s.destroy) s.destroy();
            });
            this._sortables = [];
            this._initSortable();
        },

        // ── Keyboard Shortcuts ─────────────────────────────────────────

        showShortcutsHelp: false,

        _initKeyboardShortcuts: function() {
            const self = this;
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
                if (e.target.isContentEditable) return;

                switch (e.key) {
                    case '?':
                        e.preventDefault();
                        self.showShortcutsHelp = !self.showShortcutsHelp;
                        break;
                    case 'n':
                        if (!e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            self.openCreateModal();
                        }
                        break;
                    case '/':
                        e.preventDefault();
                        const searchInput = document.querySelector('[aria-label="Search cards"]');
                        if (searchInput) searchInput.focus();
                        break;
                    case 'Escape':
                        if (self.showShortcutsHelp) {
                            self.showShortcutsHelp = false;
                        }
                        break;
                }
            });
        },

        _handleDrop: function(evt) {
            const cardId = evt.item.dataset.cardId;
            const newStatus = evt.to.dataset.status;
            if (!cardId || !newStatus) return;

            const card = this.cards[String(cardId)];
            if (!card) return;

            const oldStatus = card.status;
            card.status = newStatus;

            const wipLimit = this.wipLimits[newStatus];
            if (wipLimit) {
                const count = this.getColumnCards(newStatus).length;
                if (count > wipLimit) {
                    Platform.toast.warning('WIP limit exceeded for ' + newStatus.replace('_', ' '));
                }
            }

            const self = this;
            Platform.fetch(config.apiBase + '/cards/' + cardId, {
                method: 'PUT',
                body: { status: newStatus },
                silent: true
            }).then(function() {
                Platform.toast.success('Card moved to ' + newStatus.replace('_', ' '));
                if (Alpine.store('announcer')) {
                    Alpine.store('announcer').announce('Card moved to ' + newStatus.replace('_', ' '));
                }
            }).catch(function(err) {
                card.status = oldStatus;
                Platform.toast.error('Move failed: ' + (err.message || 'Unknown error'));
                self.$nextTick(function() {
                    self._reinitSortable();
                });
            });

            this.$nextTick(function() {
                if (typeof lucide !== 'undefined') lucide.createIcons();
            });
        }
    };
}
