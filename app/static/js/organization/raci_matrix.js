/**
 * Enterprise RACI matrix — capabilities (columns) x stakeholders (rows).
 *
 * Alpine.js component: raciMatrix()
 * Click a cell to cycle it through R -> A -> C -> I -> (cleared).
 * Saved via app/modules/organization/routes.py's JSON API:
 *   POST   /organization/raci/api/cell   { stakeholder_type, stakeholder_id, stakeholder_name, capability_id, raci }
 *   DELETE /organization/raci/api/cell   { stakeholder_type, stakeholder_id, capability_id }
 */
const RACI_CYCLE = [null, 'R', 'A', 'C', 'I'];

document.addEventListener('alpine:init', () => {
    Alpine.data('raciMatrix', () => ({
        loading: true,
        capabilities: [],
        assignments: [],
        stakeholders: [],
        searchQuery: '',
        searchResults: [],
        searching: false,

        async init() {
            await this.loadData();
        },

        async loadData() {
            this.loading = true;
            try {
                const resp = await fetch('/organization/raci/api/data');
                const json = await resp.json();
                const data = json.data ?? json;

                this.capabilities = data.capabilities || [];
                this.assignments = data.assignments || [];
                this.stakeholders = this.deriveStakeholders(this.assignments);
            } catch (e) {
                console.error('Failed to load RACI matrix data:', e);
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Failed to load RACI matrix data.');
                }
            } finally {
                this.loading = false;
            }
        },

        deriveStakeholders(assignments) {
            const seen = new Map();
            for (const a of assignments) {
                const key = `${a.stakeholder_type}:${a.stakeholder_id}`;
                if (!seen.has(key)) {
                    seen.set(key, {
                        type: a.stakeholder_type,
                        id: a.stakeholder_id,
                        name: a.stakeholder_name || `#${a.stakeholder_id}`,
                    });
                }
            }
            return Array.from(seen.values()).sort((a, b) => a.name.localeCompare(b.name));
        },

        cellValue(stakeholder, capability) {
            const found = this.assignments.find(
                a => a.stakeholder_type === stakeholder.type &&
                     a.stakeholder_id === stakeholder.id &&
                     a.capability_id === capability.id
            );
            return found ? found.raci : null;
        },

        cellClass(value) {
            switch (value) {
                case 'R': return 'bg-primary/10 text-primary border-primary/30';
                case 'A': return 'bg-destructive/10 text-destructive border-destructive/30';
                case 'C': return 'bg-amber-500/10 text-amber-600 border-amber-500/30';
                case 'I': return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30';
                default: return 'bg-muted text-muted-foreground border-border';
            }
        },

        async cycleCell(stakeholder, capability) {
            const current = this.cellValue(stakeholder, capability);
            const idx = RACI_CYCLE.indexOf(current);
            const next = RACI_CYCLE[(idx + 1) % RACI_CYCLE.length];

            try {
                if (next === null) {
                    await fetch('/organization/raci/api/cell', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            stakeholder_type: stakeholder.type,
                            stakeholder_id: stakeholder.id,
                            capability_id: capability.id,
                        }),
                    });
                    this.assignments = this.assignments.filter(
                        a => !(a.stakeholder_type === stakeholder.type &&
                               a.stakeholder_id === stakeholder.id &&
                               a.capability_id === capability.id)
                    );
                } else {
                    const resp = await fetch('/organization/raci/api/cell', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            stakeholder_type: stakeholder.type,
                            stakeholder_id: stakeholder.id,
                            stakeholder_name: stakeholder.name,
                            capability_id: capability.id,
                            raci: next,
                        }),
                    });
                    if (!resp.ok) {
                        const err = await resp.json();
                        if (window.Platform && Platform.toast) {
                            Platform.toast.error(err.error?.message || err.error || 'Failed to save RACI cell');
                        }
                        return;
                    }
                    const saved = await resp.json();
                    const data = saved.data ?? saved;
                    const existingIdx = this.assignments.findIndex(
                        a => a.stakeholder_type === stakeholder.type &&
                             a.stakeholder_id === stakeholder.id &&
                             a.capability_id === capability.id
                    );
                    if (existingIdx >= 0) {
                        this.assignments[existingIdx] = data;
                    } else {
                        this.assignments.push(data);
                    }
                }
            } catch (e) {
                console.error('Failed to update RACI cell:', e);
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Failed to update RACI cell.');
                }
            }
        },

        async runSearch() {
            const q = this.searchQuery.trim();
            if (!q) {
                this.searchResults = [];
                return;
            }
            this.searching = true;
            try {
                const resp = await fetch(`/organization/api/stakeholders/search?q=${encodeURIComponent(q)}`);
                const json = await resp.json();
                this.searchResults = json.results || [];
            } catch (e) {
                console.error('Stakeholder search failed:', e);
            } finally {
                this.searching = false;
            }
        },

        addStakeholder(result) {
            const exists = this.stakeholders.some(sh => sh.type === result.type && sh.id === result.id);
            if (!exists) {
                this.stakeholders.push({ type: result.type, id: result.id, name: result.name });
                this.stakeholders.sort((a, b) => a.name.localeCompare(b.name));
            }
            this.searchQuery = '';
            this.searchResults = [];
            if (window.Platform && Platform.modal) {
                Platform.modal.close('org-raci-add-stakeholder');
            }
            if (window.Platform && Platform.toast) {
                Platform.toast.success(`${result.name} added to the matrix.`);
            }
        },
    }));
});
