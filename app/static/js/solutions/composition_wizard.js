/**
 * ENT-100: Guided Solution Composition Wizard
 * 4-step element and relationship builder for ArchiMate solution architecture.
 *
 * Step 1: Application Structure — pick ApplicationComponents, define serving/composition rels
 * Step 2: Data Objects — pick DataObjects, define access relationships (matrix)
 * Step 3: Technology Deployment — assign components to Nodes
 * Step 4: Review & Save — summary table with validation, batch save
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('compositionWizard', () => ({
        open: false,
        step: 1,
        saving: false,
        saveError: null,
        saveResult: null,

        // Element selections
        appSearch: '',
        appResults: [],
        selectedApps: [],
        dataSearch: '',
        dataResults: [],
        selectedData: [],
        nodeSearch: '',
        nodeResults: [],
        selectedNodes: [],

        // Relationships
        proposedRels: [],
        newRelSource: null,
        newRelTarget: null,
        newRelType: '',

        // Access matrix (step 2)
        accessMap: {},

        // Deployment map (step 3)
        deploymentMap: {},

        get solutionId() {
            return window.__SOLUTION_CONFIG__ ? window.__SOLUTION_CONFIG__.solutionId : null;
        },

        get totalElements() {
            return this.selectedApps.length + this.selectedData.length + this.selectedNodes.length;
        },

        get totalRelationships() {
            let count = this.proposedRels.length;
            count += Object.keys(this.accessMap).length;
            count += Object.values(this.deploymentMap).filter(v => v).length;
            return count;
        },

        launch() {
            if (window.Platform && window.Platform.modal) {
                window.Platform.modal.open('solution-composition-wizard-modal');
            }
            this.open = true;
            this.step = 1;
            this.saving = false;
            this.saveError = null;
            this.saveResult = null;
            this.selectedApps = [];
            this.selectedData = [];
            this.selectedNodes = [];
            this.proposedRels = [];
            this.accessMap = {};
            this.deploymentMap = {};
        },

        close() {
            if (window.Platform && window.Platform.modal) {
                window.Platform.modal.close('solution-composition-wizard-modal');
            }
            this.open = false;
        },

        nextStep() {
            if (this.step < 4) this.step++;
        },

        prevStep() {
            if (this.step > 1) this.step--;
        },

        // Element search (reuses existing ArchiMate search API)
        async searchElements(query, layerFilter) {
            if (!query || query.length < 2) return [];
            try {
                let url = '/solutions/api/archimate-all-elements?search=' + encodeURIComponent(query);
                if (layerFilter) url += '&layer=' + encodeURIComponent(layerFilter);
                const res = await fetch(url, { credentials: 'same-origin' });
                if (!res.ok) return [];
                const data = await res.json();
                return (data.elements || data || []).slice(0, 10);
            } catch (e) {
                return [];
            }
        },

        async searchApps() {
            this.appResults = await this.searchElements(this.appSearch, 'application');
        },

        async searchData() {
            this.dataResults = await this.searchElements(this.dataSearch, 'data');
        },

        async searchNodes() {
            this.nodeResults = await this.searchElements(this.nodeSearch, 'technology');
        },

        addApp(elem) {
            if (!this.selectedApps.find(e => e.id === elem.id)) {
                this.selectedApps.push(elem);
            }
            this.appSearch = '';
            this.appResults = [];
        },

        removeApp(id) {
            this.selectedApps = this.selectedApps.filter(e => e.id !== id);
            this.proposedRels = this.proposedRels.filter(
                r => r.source_id !== id && r.target_id !== id
            );
        },

        addData(elem) {
            if (!this.selectedData.find(e => e.id === elem.id)) {
                this.selectedData.push(elem);
            }
            this.dataSearch = '';
            this.dataResults = [];
        },

        removeData(id) {
            this.selectedData = this.selectedData.filter(e => e.id !== id);
            // Clean access map
            const newMap = {};
            for (const [k, v] of Object.entries(this.accessMap)) {
                if (!k.endsWith('-' + id)) newMap[k] = v;
            }
            this.accessMap = newMap;
        },

        addNode(elem) {
            if (!this.selectedNodes.find(e => e.id === elem.id)) {
                this.selectedNodes.push(elem);
            }
            this.nodeSearch = '';
            this.nodeResults = [];
        },

        removeNode(id) {
            this.selectedNodes = this.selectedNodes.filter(e => e.id !== id);
            // Clean deployment map
            for (const [k, v] of Object.entries(this.deploymentMap)) {
                if (v === id) delete this.deploymentMap[k];
            }
        },

        // Step 1: Add relationship between selected apps
        addRelationship() {
            if (!this.newRelSource || !this.newRelTarget || !this.newRelType) return;
            if (this.newRelSource === this.newRelTarget) return;
            const src = this.selectedApps.find(e => e.id === parseInt(this.newRelSource));
            const tgt = this.selectedApps.find(e => e.id === parseInt(this.newRelTarget));
            if (!src || !tgt) return;

            this.proposedRels.push({
                source_id: src.id,
                source_name: src.name,
                target_id: tgt.id,
                target_name: tgt.name,
                type: this.newRelType,
            });
            this.newRelSource = null;
            this.newRelTarget = null;
            this.newRelType = '';
        },

        removeRelationship(idx) {
            this.proposedRels.splice(idx, 1);
        },

        // Step 2: Access matrix toggle
        accessKey(appId, dataId) {
            return appId + '-' + dataId;
        },

        getAccess(appId, dataId) {
            return this.accessMap[this.accessKey(appId, dataId)] || null;
        },

        toggleAccess(appId, dataId) {
            const key = this.accessKey(appId, dataId);
            const cycle = [null, 'read', 'write', 'readwrite'];
            const cur = this.accessMap[key] || null;
            const idx = cycle.indexOf(cur);
            const next = cycle[(idx + 1) % cycle.length];
            if (next) {
                this.accessMap[key] = next;
            } else {
                delete this.accessMap[key];
            }
        },

        accessLabel(appId, dataId) {
            const v = this.getAccess(appId, dataId);
            if (v === 'read') return 'R';
            if (v === 'write') return 'W';
            if (v === 'readwrite') return 'RW';
            return '\u2014';
        },

        accessBtnClass(appId, dataId) {
            const v = this.getAccess(appId, dataId);
            if (v === 'read') return 'bg-blue-500/10 text-primary border-blue-500/30';
            if (v === 'write') return 'bg-amber-500/10 text-amber-600 border-amber-500/30';
            if (v === 'readwrite') return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30';
            return 'bg-muted/30 text-muted-foreground';
        },

        // Step 4: Batch save
        async saveAll() {
            if (!this.solutionId) return;
            this.saving = true;
            this.saveError = null;
            this.saveResult = null;

            let elementsLinked = 0;
            let relsCreated = 0;
            const errors = [];

            try {
                // Link all selected elements to solution
                const allElements = [
                    ...this.selectedApps,
                    ...this.selectedData,
                    ...this.selectedNodes,
                ];

                for (const el of allElements) {
                    try {
                        const res = await fetch('/api/solutions/' + this.solutionId + '/elements', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                archimate_element_id: el.id,
                                layer: el.layer || 'application',
                            }),
                        });
                        if (res.ok || res.status === 409) elementsLinked++;
                    } catch (e) {
                        errors.push('Link ' + el.name + ': ' + e.message);
                    }
                }

                // Create proposed relationships (step 1)
                for (const rel of this.proposedRels) {
                    try {
                        const res = await fetch('/api/solutions/' + this.solutionId + '/relationships', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                source_element_id: rel.source_id,
                                target_element_id: rel.target_id,
                                relationship_type: rel.type,
                            }),
                        });
                        if (res.ok) relsCreated++;
                    } catch (e) {
                        errors.push('Rel ' + rel.source_name + '->' + rel.target_name + ': ' + e.message);
                    }
                }

                // Create access relationships (step 2)
                for (const [key, accessType] of Object.entries(this.accessMap)) {
                    const [appId, dataId] = key.split('-').map(Number);
                    try {
                        const res = await fetch('/api/solutions/' + this.solutionId + '/relationships', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                source_element_id: appId,
                                target_element_id: dataId,
                                relationship_type: 'access',
                            }),
                        });
                        if (res.ok) relsCreated++;
                    } catch (e) {
                        errors.push('Access rel: ' + e.message);
                    }
                }

                // Create deployment assignments (step 3)
                for (const [appId, nodeId] of Object.entries(this.deploymentMap)) {
                    if (!nodeId) continue;
                    try {
                        const res = await fetch('/api/solutions/' + this.solutionId + '/relationships', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                source_element_id: parseInt(nodeId),
                                target_element_id: parseInt(appId),
                                relationship_type: 'assignment',
                            }),
                        });
                        if (res.ok) relsCreated++;
                    } catch (e) {
                        errors.push('Deploy rel: ' + e.message);
                    }
                }

                this.saveResult = {
                    elementsLinked,
                    relsCreated,
                    errors: errors.length,
                };
            } catch (e) {
                this.saveError = e.message;
            } finally {
                this.saving = false;
            }
        },
    }));
});
