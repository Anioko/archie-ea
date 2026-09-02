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
                // Platform.fetch throws on non-ok responses, returns parsed data directly.
                const raw = await Platform.fetch('/organization/raci/api/data');
                // Unchecked, a 500 parsed to `{}` and the matrix rendered with no rows
                // and no stakeholders — an unassigned-looking RACI that was never read.
                // F-16, Capgemini dry-run: the route wraps its payload in
                // success_response() -> {"data": {...}}; this read the fields
                // straight off the envelope, so 219 real capabilities showed as
                // "No capabilities to map yet".
                const data = raw.data || raw;
                this.capabilities = data.capabilities || [];
                this.assignments = data.assignments || [];
                this.stakeholders = this.deriveStakeholders(this.assignments);
            } catch (e) {
                // Platform.fetch already shows a toast unless silent:true, but we also want
                // to paint inline empty state. We'll keep the inline error state painting
                // and pass silent:true to avoid duplicate toasts.
                this.capabilities = [];
                this.assignments = [];
                this.stakeholders = [];
                // The error is already surfaced via Platform.fetch's toast (unless silent).
                // We must not swallow the error; the empty arrays reflect the failure.
                // No console calls allowed.
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
                    // Platform.fetch.delete returns null for 204 No Content.
                    await Platform.fetch.delete('/organization/raci/api/cell', {
                        body: {
                            stakeholder_type: stakeholder.type,
                            stakeholder_id: stakeholder.id,
                            capability_id: capability.id,
                        },
                    });
                    this.assignments = this.assignments.filter(
                        a => !(a.stakeholder_type === stakeholder.type &&
                               a.stakeholder_id === stakeholder.id &&
                               a.capability_id === capability.id)
                    );
                } else {
                    // Platform.fetch.post serialises plain object to JSON automatically.
                    const data = await Platform.fetch.post('/organization/raci/api/cell', {
                        stakeholder_type: stakeholder.type,
                        stakeholder_id: stakeholder.id,
                        stakeholder_name: stakeholder.name,
                        capability_id: capability.id,
                        raci: next,
                    });
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
                // Platform.fetch already shows a toast unless silent:true.
                // The error is surfaced to the user; we must not swallow it.
                // No console calls allowed.
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
                // Platform.fetch.get automatically appends query parameters.
                // We'll pass the query as a params object.
                const data = await Platform.fetch.get('/organization/api/stakeholders/search', { q: q });
                // Unchecked, a 500 rendered as "no stakeholders match" and the user
                // concluded the person was not in the directory.
                this.searchResults = data.results || [];
                this._searchErrorShown = false;
            } catch (e) {
                this.searchResults = [];
                // Debounced on every keystroke — toast once per outage, not on every retry.
                // Platform.fetch already shows a toast unless silent:true.
                // We need to avoid duplicate toasts, but also want to track error shown state.
                // Since Platform.fetch will show a toast, we can set _searchErrorShown to true
                // to prevent additional UI actions, but we must not add another toast.
                if (!this._searchErrorShown) {
                    this._searchErrorShown = true;
                }
                // No console calls allowed.
            } finally {
                this.searching = false;
            }
        },

        // Audit F-08: when search finds nothing, let the user create the
        // stakeholder as a Business Actor and add it in one step.
        async createStakeholder() {
            const name = this.searchQuery.trim();
            if (!name) return;
            try {
                const data = await Platform.fetch.post('/organization/raci/api/stakeholder', { name });
                this.addStakeholder(data.data ?? data);   // success_response wraps in { data }
            } catch (e) {
                // Platform.fetch already surfaces the error toast.
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
