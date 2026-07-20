/**
 * BIZBOK Capability x Value-Stream-Stage grid.
 *
 * Alpine.data component backing app/templates/value_streams/detail.html.
 * Fetches the grid (capabilities x stages x mapping cells) from
 * GET /value-streams/<id>/grid and lets the user click a cell to
 * create/update/clear the CapabilityValueStreamMapping via the JSON API
 * at /value-streams/api/mapping (POST/PUT to upsert, DELETE to clear).
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

    Alpine.data('bizbokGrid', function (config) {
        config = config || {};
        return {
            valueStreamId: config.valueStreamId,

            // Grid state
            loading: true,
            loadError: false,
            stages: [],
            capabilities: [],
            cells: {},

            // Capability picker
            capabilitySearch: '',
            capabilityResults: [],

            // Cell edit modal state
            activeCell: null,
            cellForm: {
                support_type: 'primary',
                support_level: 3,
                capability_contribution: 50,
                impact_level: 'medium',
                stage_criticality: 'medium'
            },
            saving: false,

            // Stage edit/delete modal state (populated by openStageEditModal /
            // openStageDeleteModal below, called from the swimlane card buttons)
            stageEditForm: {},
            stageDeleteForm: {},

            init() {
                this.loadGrid();
            },

            openStageEditModal(stage) {
                this.stageEditForm = Object.assign({}, stage);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('stage-edit-modal');
                }
            },

            openStageDeleteModal(stage) {
                this.stageDeleteForm = Object.assign({}, stage);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('stage-delete-modal');
                }
            },

            cellKey(capabilityId, stageId) {
                return capabilityId + ':' + stageId;
            },

            cellLabel(capabilityId, stageId) {
                var cell = this.cells[this.cellKey(capabilityId, stageId)];
                if (!cell || !cell.support_level) return '—';
                return String(cell.support_level);
            },

            cellClass(capabilityId, stageId) {
                var cell = this.cells[this.cellKey(capabilityId, stageId)];
                if (!cell || !cell.support_level) {
                    return 'bg-muted border-border text-muted-foreground hover:border-primary/50';
                }
                var level = cell.support_level;
                if (level >= 5) return 'bg-emerald-500/70 border-emerald-600/60 text-emerald-950';
                if (level >= 4) return 'bg-emerald-500/40 border-emerald-500/50 text-emerald-800';
                if (level >= 2) return 'bg-amber-500/25 border-amber-500/40 text-amber-800';
                return 'bg-destructive/20 border-destructive/30 text-destructive';
            },

            async loadGrid() {
                this.loading = true;
                this.loadError = false;
                try {
                    var resp = await fetch('/value-streams/' + this.valueStreamId + '/grid');
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.stages = data.stages || [];
                    this.capabilities = data.capabilities || [];
                    this.cells = data.cells || {};
                } catch (err) {
                    console.error('Failed to load value stream grid', err);
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
                        '/value-streams/' + this.valueStreamId + '/api/unmapped-capabilities?q=' + encodeURIComponent(q)
                    );
                    var data = await resp.json();
                    this.capabilityResults = data.capabilities || [];
                } catch (err) {
                    console.error('Capability search failed', err);
                    this.capabilityResults = [];
                }
            },

            selectCapabilityToAdd(cap) {
                this.capabilitySearch = '';
                this.capabilityResults = [];
                if (this.stages.length === 0) {
                    if (window.Platform && window.Platform.toast) {
                        window.Platform.toast.error('Add a stage before mapping capabilities.');
                    }
                    return;
                }
                // Add as a row immediately (no mapping yet) and open the first
                // stage's cell so the user sets an initial support level.
                if (!this.capabilities.some(function (c) { return c.id === cap.id; })) {
                    this.capabilities.push(cap);
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
                    mappingId: existing ? existing.mapping_id : null
                };
                this.cellForm = {
                    support_type: (existing && existing.support_type) || 'primary',
                    support_level: (existing && existing.support_level) || 3,
                    capability_contribution: (existing && existing.capability_contribution) != null
                        ? existing.capability_contribution : 50,
                    impact_level: (existing && existing.impact_level) || 'medium',
                    stage_criticality: (existing && existing.stage_criticality) || 'medium'
                };
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('cell-edit-modal');
                }
            },

            async saveCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/value-streams/api/mapping', {
                        method: 'POST',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            capability_id: this.activeCell.capabilityId,
                            value_stream_id: this.valueStreamId,
                            value_stream_stage_id: this.activeCell.stageId,
                            support_type: this.cellForm.support_type,
                            support_level: this.cellForm.support_level,
                            capability_contribution: this.cellForm.capability_contribution,
                            impact_level: this.cellForm.impact_level,
                            stage_criticality: this.cellForm.stage_criticality
                        })
                    });
                    var data = await resp.json();
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || 'Save failed');
                    }
                    this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.stageId)] = {
                        mapping_id: data.mapping.id,
                        support_type: data.mapping.support_type,
                        support_level: data.mapping.support_level,
                        capability_contribution: data.mapping.capability_contribution,
                        impact_level: data.mapping.impact_level,
                        stage_criticality: data.mapping.stage_criticality
                    };
                    if (window.Platform && window.Platform.toast) {
                        window.Platform.toast.success('Mapping saved.');
                    }
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('cell-edit-modal');
                    }
                } catch (err) {
                    console.error('Failed to save mapping cell', err);
                    if (window.Platform && window.Platform.toast) {
                        window.Platform.toast.error('Failed to save mapping: ' + err.message);
                    }
                } finally {
                    this.saving = false;
                }
            },

            async clearCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/value-streams/api/mapping', {
                        method: 'DELETE',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            capability_id: this.activeCell.capabilityId,
                            value_stream_id: this.valueStreamId,
                            value_stream_stage_id: this.activeCell.stageId
                        })
                    });
                    var data = await resp.json();
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || 'Clear failed');
                    }
                    delete this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.stageId)];
                    if (window.Platform && window.Platform.toast) {
                        window.Platform.toast.success('Mapping cleared.');
                    }
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('cell-edit-modal');
                    }
                } catch (err) {
                    console.error('Failed to clear mapping cell', err);
                    if (window.Platform && window.Platform.toast) {
                        window.Platform.toast.error('Failed to clear mapping: ' + err.message);
                    }
                } finally {
                    this.saving = false;
                }
            }
        };
    });
}());
