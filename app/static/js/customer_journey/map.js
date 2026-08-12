/**
 * Customer journey capability x stage grid.
 *
 * Alpine.data component backing app/templates/customer_journeys/detail.html.
 * Loads the grid (capabilities x stages x links, plus the applications already
 * mapped to each capability) from GET /customer-journeys/<id>/grid, and lets
 * the user click a cell to create, update or clear the stage->capability link
 * via /customer-journeys/api/capability-link.
 *
 * Nothing here invents a value. An unassessed link shows an em dash rather than
 * a zero, and a failed fetch raises so the page can say "this failed to load"
 * instead of silently rendering an empty map.
 */
(function () {
    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function jsonHeaders() {
        return {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken()
        };
    }

    function toast(kind, message) {
        if (window.Platform && window.Platform.toast && window.Platform.toast[kind]) {
            window.Platform.toast[kind](message);
        }
    }

    Alpine.data('customerJourneyMap', function (config) {
        config = config || {};
        return {
            journeyId: config.journeyId,

            // Grid state
            loading: true,
            loadError: false,
            stages: [],
            capabilities: [],
            cells: {},

            // Capability picker
            capabilitySearch: '',
            capabilityResults: [],

            // Cell modal state
            activeCell: null,
            cellForm: {
                support_type: '',
                support_level: '',
                notes: ''
            },
            saving: false,

            // Stage edit / delete modal state, filled from the swimlane buttons
            stageEditForm: {},
            stageDeleteForm: {},

            init() {
                this.loadGrid();
            },

            openStageEditModal(stage) {
                this.stageEditForm = Object.assign({}, stage);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('cj-stage-edit-modal');
                }
            },

            openStageDeleteModal(stage) {
                this.stageDeleteForm = Object.assign({}, stage);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('cj-stage-delete-modal');
                }
            },

            cellKey(capabilityId, stageId) {
                return capabilityId + ':' + stageId;
            },

            cellLabel(capabilityId, stageId) {
                var cell = this.cells[this.cellKey(capabilityId, stageId)];
                if (!cell) return '—';
                // Linked but unassessed is a real, different state from unlinked:
                // a dot, not a number, and never a 0.
                if (cell.support_level === null || cell.support_level === undefined) return '•';
                return String(cell.support_level);
            },

            cellClass(capabilityId, stageId) {
                var cell = this.cells[this.cellKey(capabilityId, stageId)];
                if (!cell) {
                    return 'bg-muted border-border text-muted-foreground hover:border-primary/50';
                }
                var level = cell.support_level;
                if (level === null || level === undefined) {
                    return 'bg-primary/10 border-primary/30 text-primary';
                }
                if (level >= 5) return 'bg-emerald-500/70 border-emerald-600/60 text-emerald-950';
                if (level >= 4) return 'bg-emerald-500/40 border-emerald-500/50 text-emerald-800';
                if (level >= 2) return 'bg-amber-500/25 border-amber-500/40 text-amber-800';
                return 'bg-destructive/20 border-destructive/30 text-destructive';
            },

            applicationLabel(cap) {
                var apps = cap && cap.applications;
                if (!apps || apps.length === 0) return 'No application mapped';
                if (apps.length <= 2) {
                    return apps.map(function (a) { return a.name; }).join(', ');
                }
                return apps[0].name + ', ' + apps[1].name + ' +' + (apps.length - 2) + ' more';
            },

            async loadGrid() {
                this.loading = true;
                this.loadError = false;
                try {
                    var resp = await fetch('/customer-journeys/' + this.journeyId + '/grid');
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.stages = data.stages || [];
                    this.capabilities = data.capabilities || [];
                    this.cells = data.cells || {};
                } catch (err) {
                    console.error('Failed to load the customer journey grid', err);
                    this.loadError = true;
                } finally {
                    this.loading = false;
                }
            },

            async searchCapabilities() {
                var q = this.capabilitySearch.trim();
                if (!q) {
                    this.capabilityResults = [];
                    return;
                }
                try {
                    var resp = await fetch(
                        '/customer-journeys/' + this.journeyId + '/api/capabilities?q=' + encodeURIComponent(q)
                    );
                    // Unchecked, a 500 would read as "no capability matches" and the
                    // architect would conclude the capability is already linked.
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.capabilityResults = data.capabilities || [];
                } catch (err) {
                    console.error('Capability search failed', err);
                    this.capabilityResults = [];
                    toast('error', 'Capability search failed — that is a lookup failure, not an empty result.');
                }
            },

            selectCapabilityToAdd(cap) {
                this.capabilitySearch = '';
                this.capabilityResults = [];
                if (this.stages.length === 0) {
                    toast('error', 'Add a stage before linking capabilities.');
                    return;
                }
                if (!this.capabilities.some(function (c) { return c.id === cap.id; })) {
                    // `applications` is absent until the grid is reloaded from the
                    // server; an empty array here would claim "no application maps
                    // to this capability", which we have not checked.
                    this.capabilities.push(Object.assign({}, cap, { applications: null }));
                }
                this.openCellModal(cap, this.stages[0]);
            },

            openCellModal(cap, stage) {
                var existing = this.cells[this.cellKey(cap.id, stage.id)];
                this.activeCell = {
                    capabilityId: cap.id,
                    capabilityName: cap.name,
                    stageId: stage.id,
                    stageName: stage.name,
                    linkId: existing ? existing.link_id : null
                };
                this.cellForm = {
                    support_type: (existing && existing.support_type) || '',
                    support_level: (existing && existing.support_level != null)
                        ? String(existing.support_level) : '',
                    notes: (existing && existing.notes) || ''
                };
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('cj-cell-modal');
                }
            },

            async saveCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/customer-journeys/api/capability-link', {
                        method: 'POST',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            stage_id: this.activeCell.stageId,
                            capability_id: this.activeCell.capabilityId,
                            support_type: this.cellForm.support_type || null,
                            support_level: this.cellForm.support_level === ''
                                ? null : Number(this.cellForm.support_level),
                            notes: this.cellForm.notes
                        })
                    });
                    var data = await resp.json();
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || 'Save failed');
                    }
                    this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.stageId)] = {
                        link_id: data.link.id,
                        support_type: data.link.support_type,
                        support_level: data.link.support_level,
                        notes: data.link.notes
                    };
                    toast('success', 'Capability link saved.');
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('cj-cell-modal');
                    }
                } catch (err) {
                    console.error('Failed to save the capability link', err);
                    toast('error', 'Failed to save the capability link: ' + err.message);
                } finally {
                    this.saving = false;
                }
            },

            async clearCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/customer-journeys/api/capability-link', {
                        method: 'DELETE',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            stage_id: this.activeCell.stageId,
                            capability_id: this.activeCell.capabilityId
                        })
                    });
                    var data = await resp.json();
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || 'Clear failed');
                    }
                    delete this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.stageId)];
                    toast('success', 'Capability link cleared.');
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('cj-cell-modal');
                    }
                } catch (err) {
                    console.error('Failed to clear the capability link', err);
                    toast('error', 'Failed to clear the capability link: ' + err.message);
                } finally {
                    this.saving = false;
                }
            }
        };
    });
}());
