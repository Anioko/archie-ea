/**
 * solutions/detail-phase-crud.js
 * Phase A/B/C/D entity CRUD (drivers, goals, constraints, stakeholders, requirements)
 * extracted from detail.js (Phase 1 decomposition).
 * Methods are merged into Alpine.data("solutionDetail") via window._detailCrud.
 * Load this file BEFORE detail.js in the HTML template.
 *
 * NOTE: get manageFilteredItems and get manageModalTitle are Alpine.js getter computed
 * properties and must remain in detail.js (Object.assign cannot transfer getter descriptors).
 */
(function () {
    "use strict";
    window._detailCrud = {
            // --- Multi-select picker modal methods ---
            async openManageModal(type) {
                this.manageModalType = type;
                this.manageFilter = '';
                this.manageAllItems = [];
                this.manageLoading = true;
                this.manageSaving = false;
                // Pre-check currently linked IDs
                let currentIds = [];
                if (type === 'application') currentIds = this.linkedApplications.map(function(a) { return a.id; });
                else if (type === 'vendor_product') currentIds = this.linkedVendorProducts.map(function(v) { return v.id; });
                else if (type === 'adr') currentIds = this.linkedADRs.map(function(a) { return a.id; });
                else if (type === 'apqc_process') currentIds = this.linkedAPQCProcesses.map(function(p) { return p.id; });
                else if (type === 'capability') currentIds = (this.linkedCapabilities || []).map(function(c) { return c.capability_id || c.id; });
                else if (type === 'requirement') currentIds = (this.linkedRequirements || []).map(function(r) { return r.id; });
                this.manageSelectedIds = new Set(currentIds);
                // Fetch all available items
                let urlMap = {
                    application: this.apiBase + '/all-applications',
                    vendor_product: this.apiBase + '/all-vendor-products',
                    adr: this.apiBase + '/all-adrs',
                    apqc_process: this.apiBase + '/all-apqc-processes',
                    archimate_element: '/solutions/api/archimate-all-elements',
                    capability: this.apiBase + '/all-capabilities',
                    requirement: this.apiBase + '/all-requirements',
                };
                try {
                    let resp = await fetch(urlMap[type]);
                    let data = await resp.json();
                    if (type === 'archimate_element') {
                        this.manageAllItems = (data.elements || []).map(function(el) {
                            return { id: el.id, name: el.name, sub: (el.type || '') + (el.layer ? ' · ' + el.layer : ''), layer: el.layer, element_type: el.type };
                        });
                    } else {
                        this.manageAllItems = data.items || [];
                    }
                } catch (err) {
                    console.error('[solutionDetail] load all items error:', err);
                    this.manageAllItems = [];
                }
                this.manageLoading = false;
            },
            closeManageModal() {
                this.manageModalType = null;
                this.manageAllItems = [];
                this.manageSelectedIds = new Set();
                this.manageFilter = '';
                this.manageLayerFilter = '';
            },
            // get manageFilteredItems — getter, remains in detail.js
            // get manageModalTitle — getter, remains in detail.js

            isManageSelected(id) {
                return this.manageSelectedIds.has(id);
            },
            async toggleManageItem(id) {
                if (this.manageSelectedIds.has(id)) {
                    this.manageSelectedIds.delete(id);
                } else {
                    // Warn before linking duplicate-flagged applications
                    if (this.manageModalType === 'application') {
                        let item = (this.manageAllItems || []).find(function(i) { return i.id === id; });
                        if (item && (String(item.name || '').startsWith('(Duplicate)') || item.is_duplicate)) {
                            if (!(await Platform.modal.confirm('⚠️ This application is flagged as a duplicate:\n"' + item.name + '"\n\nLinking duplicate applications to solutions can create misleading traceability data. Resolve the duplicate first.\n\nLink anyway?'))) {
                                return;
                            }
                        }
                    }
                    this.manageSelectedIds.add(id);
                }
                // Force Alpine reactivity by reassigning
                this.manageSelectedIds = new Set(this.manageSelectedIds);
            },
            async saveManageModal() {
                // FAR-017: Prevent double-click duplicates
                if (this.manageSaving) return;
                let type = this.manageModalType;
                this.manageSaving = true;
                try {
                    let resp;
                    if (type === 'archimate_element') {
                        let allItems = this.manageAllItems;
                        let selectedIds = this.manageSelectedIds;
                        let elements = allItems.filter(function(i) { return selectedIds.has(i.id); }).map(function(i) {
                            return { element_id: i.id, element_table: 'archimate_elements', layer_type: i.layer || 'unknown', element_name: i.name, relationship_type: 'linked' };
                        });
                        resp = await fetch(this.apiBase + '/archimate-elements', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                            body: JSON.stringify({ elements: elements, replace: true }),
                        });
                    } else {
                        let syncUrls = {
                            application: this.apiBase + '/sync-applications',
                            vendor_product: this.apiBase + '/sync-vendor-products',
                            adr: this.apiBase + '/sync-adrs',
                            apqc_process: this.apiBase + '/sync-apqc-processes',
                            capability: this.apiBase + '/sync-capabilities',
                            requirement: this.apiBase + '/sync-requirements',
                        };
                        resp = await fetch(syncUrls[type], {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                            body: JSON.stringify({ ids: Array.from(this.manageSelectedIds) }),
                        });
                    }
                    let data = await resp.json();
                    if (data.success) {
                        window.location.reload();
                    } else {
                        Platform.toast.error('Save failed: ' + (data.error || 'Unknown error'));
                    }
                } catch (err) {
                    console.error('[solutionDetail] sync error:', err);
                    Platform.toast.error('Save failed. Check console for details.');
                }
                this.manageSaving = false;
            },
            async unlinkEntity(type, id) {
                if (!(await Platform.modal.confirm('Remove this item?'))) return;
                if (type === 'capability' && !id) {
                    Platform.toast.error('Cannot remove this capability: no mapping record found. Try re-linking it first.');
                    return;
                }
                let urlMap = {
                    application: this.apiBase + '/unlink-application/' + id,
                    vendor_product: this.apiBase + '/unlink-vendor-product/' + id,
                    adr: this.apiBase + '/unlink-adr/' + id,
                    apqc_process: this.apiBase + '/unlink-apqc-process/' + id,
                    capability: this.apiBase + '/capabilities/' + id,
                };
                try {
                    let resp = await fetch(urlMap[type], {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken },
                    });
                    let data = await resp.json();
                    if (data.success) {
                        window.location.reload();
                    } else {
                        Platform.toast.error('Remove failed: ' + (data.error || 'Unknown error'));
                    }
                } catch (err) {
                    console.error('[solutionDetail] unlink error:', err);
                    Platform.toast.error('Remove failed. Check console for details.');
                }
            },

            async aiGenerateRequirements() {
                if (this.generatingReqs) return;
                this.generatingReqs = true;
                this.aiRequirementSuggestions = [];
                try {
                    let cfgData = window.__SOLUTION_CONFIG__ || {};
                    let resp = await fetch(this.apiBase.replace(/\/\d+$/, '') + '/ai-generate-requirements', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({
                            description: cfgData.solutionDescription || '',
                            solution_type: cfgData.solutionType || '',
                            business_domain: cfgData.businessDomain || '',
                            solution_id: cfgData.solutionId || null
                        })
                    });
                    let data = await resp.json();
                    if (data.success && data.requirements) {
                        this.aiRequirementSuggestions = data.requirements;
                        this.aiReqReasoningStateId = data.reasoning_state_id || null;
                    } else if (data.success && data.suggestions) {
                        this.aiRequirementSuggestions = data.suggestions;
                        this.aiReqReasoningStateId = data.reasoning_state_id || null;
                    }
                } catch (err) {
                    console.error('[solutionDetail] AI requirements error:', err);
                    Platform.toast.error('AI requirements generation failed.');
                }
                this.generatingReqs = false;
            },

            async acceptRequirement(idx) {
                let s = this.aiRequirementSuggestions[idx];
                if (!s) return;
                try {
                    let resp = await fetch(this.apiBase + '/requirements', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({
                            name: s.name || s.title || '',
                            description: s.description || '',
                            requirement_type: s.type || s.requirement_type || 'functional',
                            priority: s.priority || 3,
                            is_mandatory: s.is_mandatory || false,
                            source: 'ai_generated'
                        })
                    });
                    let data = await resp.json();
                    if (data.success && data.data) {
                        this.requirements.push(data.data);
                        this.aiRequirementSuggestions.splice(idx, 1);
                        this._recordAiFeedback(this.aiReqReasoningStateId, 'accept', 'req-' + idx, 'requirement');
                    }
                } catch (err) {
                    console.error('[solutionDetail] accept requirement error:', err);
                }
            },

            dismissRequirement(idx) {
                this._recordAiFeedback(this.aiReqReasoningStateId, 'reject', 'req-' + idx, 'requirement');
                this.aiRequirementSuggestions.splice(idx, 1);
            },

            // --- AI feedback helper ---
            async _recordAiFeedback(stateId, action, suggestionId, entityType) {
                if (!stateId) return;
                try {
                    await fetch(this.apiBase + '/ai-suggestion-feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({
                            reasoning_state_id: stateId,
                            action: action,
                            suggestion_id: suggestionId,
                            entity_type: entityType
                        })
                    });
                } catch (err) {
                    console.warn('[solutionDetail] Failed to record AI feedback:', err);
                }
            },


            // --- ArchiMate staging panel (CAP-009) ---
            stagedElements: [],
            stagingGenerating: false,

            async generateArchitectureFromCapabilities() {
                if (this.stagingGenerating) return;
                this.stagingGenerating = true;
                this.stagedElements = [];
                try {
                    const capIds = (this.linkedCapabilities || []).map(function(c) {
                        return c.capability_id || c.id;
                    });
                    if (capIds.length === 0) {
                        this.showNotification('No capabilities linked. Link capabilities first.', 'warning');
                        this.stagingGenerating = false;
                        return;
                    }
                    let resp = await fetch(this.apiBase + '/generate-from-capabilities', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({ capability_ids: capIds })
                    });
                    let data = await resp.json();
                    if (data.success && data.data && data.data.elements_created) {
                        this.stagedElements = data.data.elements_created.map(function(el) {
                            return {
                                id: el.id,
                                name: el.name || '',
                                type: el.type || '',
                                layer: el.layer || 'unknown',
                                relationship_type: el.relationship_type || 'realizes',
                                source_entity_type: el.source_entity_type || ''
                            };
                        });
                        // CAP-015: Persist staged elements to localStorage
                        try {
                            const storageKey = 'archie_staged_' + this.apiBase.split('/').filter(Boolean).pop();
                            localStorage.setItem(storageKey, JSON.stringify(this.stagedElements));
                        } catch(e) { /* localStorage full or disabled */ }
                        if (this.stagedElements.length > 0) {
                            this.showNotification('Generated ' + this.stagedElements.length + ' elements. Review below.', 'success');
                        } else {
                            this.showNotification('No new elements generated (may already exist).', 'info');
                        }
                    } else {
                        this.showNotification(data.error || 'Generation failed.', 'error');
                    }
                } catch (err) {
                    console.error('[solutionDetail] generate architecture error:', err);
                    this.showNotification('Generation failed. Check console.', 'error');
                }
                this.stagingGenerating = false;
            },

            async acceptStagedElement(index) {
                const el = this.stagedElements[index];
                if (!el) return;
                try {
                    let resp = await fetch(this.apiBase + '/link-archimate-element', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({
                            element_id: el.id,
                            element_type: el.type || '',
                            layer_type: el.layer,
                            element_name: el.name,
                            relationship_type: el.relationship_type || 'realizes'
                        })
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.stagedElements.splice(index, 1);
                        // KAN-003: Show chain completion result if inference engine ran
                        if (data.chain_result) {
                            let cr = data.chain_result;
                            this.showNotification('Accepted: ' + el.name + '. Engine inferred ' + cr.nodes_created + ' element(s) and ' + cr.relationships_created + ' relationship(s).', 'success');
                        } else {
                            this.showNotification('Accepted: ' + el.name, 'success');
                        }
                    } else {
                        this.showNotification('Link failed: ' + (data.error || 'Unknown error'), 'error');
                    }
                } catch (err) {
                    console.error('[solutionDetail] accept staged element error:', err);
                    this.showNotification('Accept failed. Check console.', 'error');
                }
            },

            rejectStagedElement(index) {
                const el = this.stagedElements[index];
                if (!el) return;
                this.stagedElements.splice(index, 1);
                this.showNotification('Rejected: ' + el.name, 'info');
            },

            async acceptAllStaged() {
                const self = this;
                let elements = this.stagedElements.slice();
                // CAP-015: Capture completeness before accepting
                let beforeScore = null;
                try {
                    const beforeResp = await fetch(self.apiBase + '/completeness');
                    if (beforeResp.ok) {
                        const beforeData = await beforeResp.json();
                        beforeScore = beforeData.score || 0;
                    }
                } catch(e) { /* completeness endpoint may not exist */ }
                const promises = elements.map(function(el) {
                    return fetch(self.apiBase + '/link-archimate-element', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': self.csrfToken
                        },
                        body: JSON.stringify({
                            element_id: el.id,
                            element_type: el.type || '',
                            layer_type: el.layer,
                            element_name: el.name,
                            relationship_type: el.relationship_type || 'realizes'
                        })
                    }).then(function(r) { return r.json(); });
                });
                try {
                    const results = await Promise.all(promises);
                    const accepted = results.filter(function(r) { return r.success; }).length;
                    // KAN-003: Aggregate chain completion results from all accepts
                    let totalNodesCreated = 0;
                    let totalRelsCreated = 0;
                    results.forEach(function(r) {
                        if (r.success && r.chain_result) {
                            totalNodesCreated += r.chain_result.nodes_created || 0;
                            totalRelsCreated += r.chain_result.relationships_created || 0;
                        }
                    });
                    let chainSuffix = '';
                    if (totalNodesCreated > 0 || totalRelsCreated > 0) {
                        chainSuffix = ' Engine inferred ' + totalNodesCreated + ' element(s) and ' + totalRelsCreated + ' relationship(s).';
                    }
                    self.stagedElements = [];
                    // CAP-015: Clear persisted staged elements
                    try {
                        const storageKey = 'archie_staged_' + self.apiBase.split('/').filter(Boolean).pop();
                        localStorage.removeItem(storageKey);
                    } catch(e) { /* ignore */ }
                    // KAN-003: Clear inference preview cache after bulk accept
                    if (typeof self.clearInferencePreviewCache === 'function') {
                        self.clearInferencePreviewCache();
                    }
                    // CAP-015: Show completeness delta if available
                    if (beforeScore !== null) {
                        try {
                            const afterResp = await fetch(self.apiBase + '/completeness');
                            if (afterResp.ok) {
                                const afterData = await afterResp.json();
                                const afterScore = afterData.score || 0;
                                self.showNotification('Completeness: ' + beforeScore + '% \u2192 ' + afterScore + '%. Accepted ' + accepted + ' elements.' + chainSuffix, 'success');
                            } else {
                                self.showNotification('Accepted ' + accepted + ' elements.' + chainSuffix, 'success');
                            }
                        } catch(e) {
                            self.showNotification('Accepted ' + accepted + ' elements.' + chainSuffix, 'success');
                        }
                    } else {
                        self.showNotification('Accepted ' + accepted + ' elements.' + chainSuffix, 'success');
                    }
                    window.location.reload();
                } catch (err) {
                    console.error('[solutionDetail] accept all staged error:', err);
                    self.showNotification('Some elements failed to link.', 'error');
                }
            },

            rejectAllStaged() {
                const count = this.stagedElements.length;
                this.stagedElements = [];
                // CAP-015: Clear persisted staged elements
                try {
                    const storageKey = 'archie_staged_' + this.apiBase.split('/').filter(Boolean).pop();
                    localStorage.removeItem(storageKey);
                } catch(e) { /* ignore */ }
                this.showNotification('Rejected ' + count + ' elements', 'info');
            },

            // CAP-015: Restore staged elements from localStorage on page load
            _restoreStagedElements() {
                try {
                    const storageKey = 'archie_staged_' + this.apiBase.split('/').filter(Boolean).pop();
                    const stored = localStorage.getItem(storageKey);
                    if (stored) {
                        this.stagedElements = JSON.parse(stored);
                    }
                } catch(e) { /* ignore parse errors */ }
            },

            // --- ArchiMate picker for motivation entity modals ---
            archimateSearchResults: [],
            selectedArchimateElement: null,
            archimateSearchLoading: false,
            archimateDropdownOpen: false,
            archimateSearchError: '',
            showMoreProperties: false,
            _archimateDebounceTimer: null,

            _archimateTypeForEntity(type) {
                const map = {
                    driver: 'Driver', goal: 'Goal', constraint: 'Constraint',
                    requirement: 'Requirement', risk: 'Assessment',
                    metric: 'Outcome', plateau: 'Plateau'
                };
                return map[type] || null;
            },

            _archimateLayerForEntity(type) {
                return type === 'plateau' ? 'Implementation' : 'Motivation';
            },

            _nameFieldForEntity(type) {
                return type === 'risk' ? 'risk_description' : 'name';
            },

            searchArchimateElements(entityType) {
                const self = this;
                const nameField = this._nameFieldForEntity(entityType);
                const query = (this.formData[nameField] || '').trim();
                if (query.length < 2) {
                    this.archimateSearchResults = [];
                    this.archimateDropdownOpen = false;
                    return;
                }
                if (this._archimateDebounceTimer) clearTimeout(this._archimateDebounceTimer);
                this._archimateDebounceTimer = setTimeout(async function() {
                    self.archimateSearchLoading = true;
                    self.archimateSearchError = '';
                    const archType = self._archimateTypeForEntity(entityType);
                    try {
                        let url = '/archimate/api/elements/search?q=' + encodeURIComponent(query) +
                                  '&type=' + encodeURIComponent(archType) + '&limit=15';
                        let resp = await fetch(url);
                        let json = await resp.json();
                        self.archimateSearchResults = json.data || [];
                        self.archimateDropdownOpen = true;
                    } catch (err) {
                        console.error('[solutionDetail] archimate search error:', err);
                        self.archimateSearchResults = [];
                        self.archimateSearchError = 'Search unavailable \u2014 type a name to create new.';
                        self.archimateDropdownOpen = true;
                    }
                    self.archimateSearchLoading = false;
                }, 300);
            },

            selectArchimateElement(element) {
                this.selectedArchimateElement = element;
                const nameField = this._nameFieldForEntity(this.entityType);
                this.formData[nameField] = element.name || '';
                if (element.description && this.entityType !== 'risk') {
                    this.formData.description = element.description;
                }
                this.formData.archimate_element_id = element.id;
                this.formData._archimate_linked = true;
                this.formData._archimate_element_name = element.name;
                this.formData._archimate_element_type = element.type;
                this.archimateSearchResults = [];
                this.archimateDropdownOpen = false;
                this.showNotification('Linked to existing: ' + element.name, 'info');
            },

            clearArchimateSelection() {
                this.selectedArchimateElement = null;
                const nameField = this._nameFieldForEntity(this.entityType);
                this.formData[nameField] = '';
                if (this.entityType !== 'risk') {
                    this.formData.description = '';
                }
                delete this.formData.archimate_element_id;
                this.archimateSearchResults = [];
                this.archimateDropdownOpen = false;
            },

            // --- Stakeholder autocomplete (SDX-021) ---
            editingRole: null,
            roleSearch: '',
            roleResults: [],
            roleSearching: false,
            stakeholders: {
                solution_owner: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.solution_owner : '',
                business_sponsor: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.business_sponsor : '',
                technical_lead: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.technical_lead : '',
                architecture_lead: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.architecture_lead : '',
                security_lead: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.security_lead : '',
                data_protection_officer: (typeof cfg !== 'undefined' && cfg.stakeholders) ? cfg.stakeholders.data_protection_officer : '',
            },
            async searchUsers() {
                if (this.roleSearch.length < 2) { this.roleResults = []; return; }
                this.roleSearching = true;
                try {
                    let resp = await fetch('/api/users', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    let data = await resp.json();
                    if (data.success) {
                        let q = this.roleSearch.toLowerCase();
                        this.roleResults = data.users.filter(function(u) {
                            return u.name.toLowerCase().indexOf(q) > -1 || u.email.toLowerCase().indexOf(q) > -1;
                        }).slice(0, 5);
                    }
                } catch (err) {
                    console.error('[solutionDetail] user search error:', err);
                }
                this.roleSearching = false;
            },
            async selectRoleUser(user) {
                if (!this.editingRole) return;
                let field = this.editingRole;
                this.stakeholders[field] = user.name;
                this.editingRole = null;
                this.roleSearch = '';
                this.roleResults = [];
                try {
                    let body = {};
                    body[field] = user.name;
                    await fetch(this.apiBase + '/update-json', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify(body)
                    });
                } catch (err) {
                    console.error('[solutionDetail] role update error:', err);
                }
            },
            startEditRole(field) {
                this.editingRole = field;
                this.roleSearch = this.stakeholders[field] || '';
                this.roleResults = [];
            },
            cancelEditRole() {
                this.editingRole = null;
                this.roleSearch = '';
                this.roleResults = [];
            },


            // --- Modal control ---
            openEntityModal(type, entity) {
                this.entityType = type;
                this.editingEntity = entity || null;
                this.formData = entity ? Object.assign({}, entity) : this._defaults(type);
                this.activeModal = type;
                // Reset ArchiMate picker state
                this.archimateSearchResults = [];
                this.selectedArchimateElement = null;
                this.archimateSearchLoading = false;
                this.archimateDropdownOpen = false;
                this.archimateSearchError = '';
                this.showMoreProperties = false;
                // Populate APQC search field when editing business element with linked process
                if (type === 'business_element') {
                    this.apqcResults = [];
                    this.apqcQuery = (entity && entity.apqc_process_name) ? entity.apqc_process_name : '';
                }
            },

            closeModal() {
                this.activeModal = null;
                this.editingEntity = null;
                this.formData = {};
                this.saving = false;
            },

            _defaults(type) {
                if (type === 'risk') return { risk_description: '', impact: 'medium', probability: 'medium', mitigation: '', status: 'open', owner: '' };
                if (type === 'metric') return { name: '', unit: '', baseline_value: '', target_value: '', actual_value: '', status: 'not_measured' };
                if (type === 'tco') return { option_label: 'Proposed', cost_category: '', is_recurring: true, year: 1, amount: 0, notes: '' };
                if (type === 'plateau') return { name: '', description: '', order: 0, target_date: '' };
                if (type === 'driver') return { name: '', description: '', driver_type: 'internal', impact_level: 3, urgency: 3, source: '' };
                if (type === 'goal') return { name: '', description: '', priority: 3, measurement_criteria: '' };
                if (type === 'constraint') return { name: '', description: '', constraint_type: 'technical', value: '', severity: 3 };
                if (type === 'requirement') return { name: '', description: '', requirement_type: 'functional', priority: 3, is_mandatory: false, source: '', rationale: '', acceptance_criteria: '' };
                if (type === 'option') return { name: '', option_type: 'build', justification: '', estimated_cost_min: null, estimated_cost_max: null, timeline_months: null, score: null, confidence: null, is_recommended: false, pros: [], cons: [], risks: [] };
                // SAD models
                if (type === 'integration_flow') return { flow_name: '', source_app_id: null, target_app_id: null, flow_type: 'sync', protocol: '', criticality: 'medium', notes: '' };
                if (type === 'composition') return { component_type: 'application', component_id: null, component_name: '', role: 'supporting', criticality: 'medium', coupling: 'loosely_coupled', notes: '' };
                if (type === 'risk_snapshot') return { risk_name: '', risk_category: 'technical', adm_phase: '', impact: 3, probability: 3, trend: 'stable', mitigation_status: 'identified', notes: '' };
                if (type === 'quality_attribute') return { attribute_name: '', attribute_type: 'performance', target_value: '', current_value: '', verification_method: '', test_status: 'not_tested', notes: '' };
                if (type === 'sla') return { sla_name: '', availability_target: null, response_time_ms: null, rto_hours: null, rpo_hours: null, support_hours: '', status: 'draft', notes: '' };
                if (type === 'investment_phase') return { phase_name: '', phase_number: 1, authorized_amount: null, currency: 'GBP', funding_source: '', status: 'pending', notes: '' };
                if (type === 'governance_exception') return { exception_description: '', justification: '', principle_name: '', risk_accepted: '', status: 'requested', notes: '' };
                if (type === 'compliance_mapping') return { framework: '', control_id: '', control_description: '', element_name: '', verification_status: 'not_assessed', notes: '' };
                if (type === 'change_request') return { change_type: 'scope', title: '', description: '', justification: '', priority: 'medium', affected_phase: '', notes: '' };
                if (type === 'feasibility_review') return { review_type: 'technical', review_phase: '', feasible: null, confidence_level: 'medium', recommendation: 'proceed', technical_risks: '', notes: '' };
                if (type === 'benefit_realization') return { benefit_name: '', benefit_type: 'operational', metric_name: '', baseline_value: null, target_value: null, status: 'not_started', notes: '' };
                if (type === 'org_impact') return { impact_area: '', description: '', headcount_delta: 0, reskilling_required: false, change_readiness: 'unknown', notes: '' };
                if (type === 'lesson_learned') return { title: '', category: 'technical', adm_phase: '', description: '', root_cause: '', recommendation: '', impact: 'medium', notes: '' };
                // ArchiMate 3.2 phase element defaults
                if (type === 'principle') return { name: '', description: '', rationale: '', implications: '', priority: 'medium', source: '', notes: '' };
                if (type === 'assessment') return { assessment_type: 'gap', name: '', current_state: '', target_state: '', gap_description: '', severity: 3, notes: '' };
                if (type === 'stakeholder_sad') return { name: '', role: '', organization: '', influence_level: 'medium', interest_level: 'medium', engagement_strategy: '', notes: '' };
                if (type === 'business_element') return { element_type: 'service', name: '', description: '', owner: '', status: 'current', apqc_process_id: null, notes: '' };
                if (type === 'app_element') return { element_type: 'service', name: '', description: '', technology: '', status: 'current', notes: '' };
                if (type === 'tech_element') return { element_type: 'node', name: '', description: '', specification: '', status: 'current', notes: '' };
                return {};
            },

            _apiPath(type) {
                if (type === 'risk') return '/risks';
                if (type === 'metric') return '/metrics';
                if (type === 'tco') return '/tco';
                if (type === 'plateau') return '/plateaus';
                if (type === 'driver') return '/drivers';
                if (type === 'goal') return '/goals';
                if (type === 'constraint') return '/constraints';
                if (type === 'requirement') return '/requirements';
                if (type === 'option') return '/options';
                // SAD models (served by solution_sad_bp)
                if (type === 'integration_flow') return '/integration-flows';
                if (type === 'composition') return '/composition';
                if (type === 'risk_snapshot') return '/risk-snapshots';
                if (type === 'quality_attribute') return '/quality-attributes';
                if (type === 'sla') return '/slas';
                if (type === 'investment_phase') return '/investment-phases';
                if (type === 'governance_exception') return '/governance-exceptions';
                if (type === 'compliance_mapping') return '/compliance-mappings';
                if (type === 'change_request') return '/change-requests';
                if (type === 'feasibility_review') return '/feasibility-reviews';
                if (type === 'benefit_realization') return '/benefit-realizations';
                if (type === 'org_impact') return '/org-impacts';
                if (type === 'lesson_learned') return '/lessons-learned';
                // ArchiMate 3.2 phase elements
                if (type === 'principle') return '/principles';
                if (type === 'assessment') return '/assessments';
                if (type === 'stakeholder_sad') return '/stakeholders-sad';
                if (type === 'business_element') return '/business-elements';
                if (type === 'app_element') return '/app-elements';
                if (type === 'tech_element') return '/tech-elements';
                return '';
            },

            _listKey(type) {
                if (type === 'risk') return 'risks';
                if (type === 'metric') return 'metrics';
                if (type === 'tco') return 'tcoItems';
                if (type === 'plateau') return 'plateaus';
                if (type === 'driver') return 'drivers';
                if (type === 'goal') return 'goals';
                if (type === 'constraint') return 'constraints';
                if (type === 'requirement') return 'requirements';
                if (type === 'option') return 'recommendations';
                // SAD models → nested under this.sad.*
                if (type === 'integration_flow') return 'sad.integration_flows';
                if (type === 'composition') return 'sad.composition';
                if (type === 'risk_snapshot') return 'sad.risk_snapshots';
                if (type === 'quality_attribute') return 'sad.quality_attributes';
                if (type === 'sla') return 'sad.slas';
                if (type === 'investment_phase') return 'sad.investment_phases';
                if (type === 'governance_exception') return 'sad.governance_exceptions';
                if (type === 'compliance_mapping') return 'sad.compliance_mappings';
                if (type === 'change_request') return 'sad.change_requests';
                if (type === 'feasibility_review') return 'sad.feasibility_reviews';
                if (type === 'benefit_realization') return 'sad.benefit_realizations';
                if (type === 'org_impact') return 'sad.org_impacts';
                if (type === 'lesson_learned') return 'sad.lessons_learned';
                // ArchiMate 3.2 phase elements
                if (type === 'principle') return 'sad.principles';
                if (type === 'assessment') return 'sad.assessments';
                if (type === 'stakeholder_sad') return 'sad.stakeholders_sad';
                if (type === 'business_element') return 'sad.business_elements';
                if (type === 'app_element') return 'sad.app_elements';
                if (type === 'tech_element') return 'sad.tech_elements';
                return '';
            },

            // --- APQC Process search for Business Elements ---
            apqcQuery: '',
            apqcResults: [],
            apqcSearching: false,

            async searchApqcProcesses() {
                let q = this.apqcQuery.trim();
                if (q.length < 2) { this.apqcResults = []; return; }
                this.apqcSearching = true;
                try {
                    let resp = await fetch('/dashboard/api/apqc-processes');
                    if (resp.ok) {
                        let data = await resp.json();
                        let procs = Array.isArray(data) ? data : (data.processes || []);
                        let lq = q.toLowerCase();
                        this.apqcResults = procs.filter(function(p) {
                            return (p.process_name || '').toLowerCase().indexOf(lq) >= 0
                                || (p.process_code || '').toLowerCase().indexOf(lq) >= 0;
                        }).slice(0, 10);
                    }
                } catch (e) { console.warn('[APQC search]', e); }
                this.apqcSearching = false;
            },

            selectApqcProcess(proc) {
                this.formData.apqc_process_id = proc.id;
                this.apqcQuery = (proc.process_code || '') + ' ' + (proc.process_name || '');
                this.apqcResults = [];
            },

            clearApqcProcess() {
                this.formData.apqc_process_id = null;
                this.apqcQuery = '';
                this.apqcResults = [];
            },

            // --- CRUD ---
            async submitEntity() {
                // FAR-017: Prevent double-click duplicates
                if (this.saving) return;
                this.saving = true;
                let type = this.entityType;
                let isEdit = this.editingEntity && this.editingEntity.id;
                let url = this.apiBase + this._apiPath(type) + (isEdit ? '/' + this.editingEntity.id : '');
                let method = isEdit ? 'PUT' : 'POST';

                try {
                    let resp = await fetch(url, {
                        method: method,
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify(this.formData)
                    });
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    await this.refreshEntityData(type);
                    this.closeModal();
                } catch (err) {
                    console.error('[solutionDetail] save error:', err);
                    this.saving = false;
                }
            },

            confirmDeleteEntity(type, entity) {
                this.entityType = type;
                this.deleteTarget = entity;
                this.activeModal = 'delete';
            },

            async executeDeleteEntity() {
                // FAR-017: Prevent double-click on delete
                if (!this.deleteTarget || this.saving) return;
                this.saving = true;
                let type = this.entityType;
                let url = this.apiBase + this._apiPath(type) + '/' + this.deleteTarget.id;

                try {
                    let resp = await fetch(url, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    await this.refreshEntityData(type);
                    this.closeModal();
                } catch (err) {
                    console.error('[solutionDetail] delete error:', err);
                    this.saving = false;
                }
            },

            async refreshEntityData(type) {
                let url = this.apiBase + this._apiPath(type);
                try {
                    let resp = await fetch(url);
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    let json = await resp.json();
                    let listKey = this._listKey(type);
                    let items = json.data || json.items || [];
                    // Handle nested SAD paths like "sad.integration_flows"
                    if (listKey.indexOf('sad.') === 0) {
                        let sadKey = listKey.substring(4);
                        if (!this.sad) this.sad = {};
                        this.sad[sadKey] = items;
                    } else {
                        this[listKey] = items;
                    }
                    if (listKey === 'recommendations') this.refreshArchitectureVariantsFromRecommendations();
                } catch (err) {
                    console.error('[solutionDetail] refresh error:', err);
                }
                // ENT-018: silently update impact summary after any entity change
                this._refreshImpact();
            },

            _refreshImpact() {
                fetch(this.apiBase + '/recalculate-impact', {
                    method: 'POST', headers: { 'X-CSRFToken': this.csrfToken }
                }).then(function(r) { return r.ok ? r.json() : null; }).then((data) => {
                    if (!data) return;
                    if (typeof data.maturity_percentage === 'number') {
                        this.maturityPct = data.maturity_percentage;
                    }
                    if (data.risk_summary) this.riskSummaryLive = data.risk_summary;
                    if (data.next_milestone) this.nextMilestone = data.next_milestone;
                }).catch(() => {});
            },
    };
})();
