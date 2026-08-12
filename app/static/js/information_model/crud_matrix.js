/**
 * Capability x business-object CRUD matrix.
 *
 * Backs app/templates/information_model/crud_matrix.html. Reads the grid from
 * GET /information-model/api/crud-matrix and writes one cell at a time through
 * /information-model/api/crud (POST to upsert, DELETE to clear).
 *
 * An unmapped cell renders as an em dash, never as "----" or "no access": the
 * absence of a row means nobody has said, which is not the same as a capability
 * having been assessed and found to touch nothing.
 */
document.addEventListener('alpine:init', function () {
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

    Alpine.data('informationCrudMatrix', function (config) {
        config = config || {};
        return {
            domainId: config.domainId === null || config.domainId === undefined
                ? '' : String(config.domainId),

            loading: true,
            loadError: false,
            objects: [],
            capabilities: [],
            cells: {},

            capabilitySearch: '',
            capabilityResults: [],

            activeCell: null,
            cellForm: {
                creates: false,
                reads: false,
                updates: false,
                deletes: false,
                is_owning_capability: false,
                notes: ''
            },
            saving: false,

            init() {
                this.loadMatrix();
            },

            cellKey(capabilityId, objectId) {
                return capabilityId + ':' + objectId;
            },

            cellLabel(capabilityId, objectId) {
                var cell = this.cells[this.cellKey(capabilityId, objectId)];
                if (!cell || !cell.letters) return '—';
                return cell.letters;
            },

            cellClass(capabilityId, objectId) {
                var cell = this.cells[this.cellKey(capabilityId, objectId)];
                if (!cell || !cell.letters) {
                    return 'bg-muted border-border text-muted-foreground hover:border-primary/50';
                }
                if (cell.creates) {
                    return 'bg-emerald-500/40 border-emerald-500/50 text-emerald-800';
                }
                return 'bg-info/10 border-info/30 text-info-emphasis';
            },

            async loadMatrix() {
                this.loading = true;
                this.loadError = false;
                try {
                    var url = '/information-model/api/crud-matrix';
                    if (this.domainId) {
                        url += '?domain_id=' + encodeURIComponent(this.domainId);
                    }
                    var resp = await fetch(url);
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.objects = data.objects || [];
                    this.capabilities = data.capabilities || [];
                    this.cells = data.cells || {};
                } catch (err) {
                    console.error('Failed to load the CRUD matrix', err);
                    this.loadError = true;
                    this.objects = [];
                    this.capabilities = [];
                    this.cells = {};
                } finally {
                    this.loading = false;
                }
            },

            async searchCapabilities() {
                var term = this.capabilitySearch.trim();
                if (!term) {
                    this.capabilityResults = [];
                    return;
                }
                try {
                    var resp = await fetch(
                        '/information-model/api/capabilities?q=' + encodeURIComponent(term)
                    );
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var data = await resp.json();
                    this.capabilityResults = data.capabilities || [];
                } catch (err) {
                    console.error('Capability search failed', err);
                    this.capabilityResults = [];
                    toast('error', 'Capability search failed — that is a lookup failure, not an empty result.');
                }
            },

            addCapabilityRow(capability) {
                this.capabilitySearch = '';
                this.capabilityResults = [];
                if (this.objects.length === 0) {
                    toast('error', 'There are no business objects in this scope to map to.');
                    return;
                }
                var already = this.capabilities.some(function (c) { return c.id === capability.id; });
                if (!already) {
                    this.capabilities.push(capability);
                }
                this.openCellModal(capability, this.objects[0]);
            },

            openCellModal(capability, object) {
                var existing = this.cells[this.cellKey(capability.id, object.id)];
                this.activeCell = {
                    capabilityId: capability.id,
                    capabilityName: capability.name,
                    objectId: object.id,
                    objectName: object.name,
                    cellId: existing ? existing.id : null
                };
                this.cellForm = {
                    creates: !!(existing && existing.creates),
                    reads: !!(existing && existing.reads),
                    updates: !!(existing && existing.updates),
                    deletes: !!(existing && existing.deletes),
                    is_owning_capability: !!(existing && existing.is_owning_capability),
                    notes: (existing && existing.notes) || ''
                };
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('crud-cell-modal');
                }
            },

            async saveCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/information-model/api/crud', {
                        method: 'POST',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            capability_id: this.activeCell.capabilityId,
                            business_object_id: this.activeCell.objectId,
                            creates: this.cellForm.creates,
                            reads: this.cellForm.reads,
                            updates: this.cellForm.updates,
                            deletes: this.cellForm.deletes,
                            is_owning_capability: this.cellForm.is_owning_capability,
                            notes: this.cellForm.notes
                        })
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.objectId)] = data.cell;
                    this.activeCell.cellId = data.cell.id;
                    toast('success', 'CRUD cell saved.');
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('crud-cell-modal');
                    }
                } catch (err) {
                    console.error('Failed to save the CRUD cell', err);
                    toast('error', 'Failed to save the CRUD cell: ' + err.message);
                } finally {
                    this.saving = false;
                }
            },

            async clearCell() {
                if (!this.activeCell) return;
                this.saving = true;
                try {
                    var resp = await fetch('/information-model/api/crud', {
                        method: 'DELETE',
                        headers: jsonHeaders(),
                        body: JSON.stringify({
                            capability_id: this.activeCell.capabilityId,
                            business_object_id: this.activeCell.objectId
                        })
                    });
                    var data = await resp.json().catch(function () { return {}; });
                    if (!resp.ok || !data.success) {
                        throw new Error(data.error || ('HTTP ' + resp.status));
                    }
                    delete this.cells[this.cellKey(this.activeCell.capabilityId, this.activeCell.objectId)];
                    toast('success', 'CRUD cell cleared.');
                    if (window.Platform && window.Platform.modal) {
                        window.Platform.modal.close('crud-cell-modal');
                    }
                } catch (err) {
                    console.error('Failed to clear the CRUD cell', err);
                    toast('error', 'Failed to clear the CRUD cell: ' + err.message);
                } finally {
                    this.saving = false;
                }
            }
        };
    });
});
