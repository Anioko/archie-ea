/**
 * solutions/blueprint.js
 * Alpine.js component for the Solution Architecture Blueprint page.
 *
 * Reads config from window.__BLUEPRINT_CONFIG__:
 *   { solutionId, csrfToken, sectionDefinitions, scores, ... }
 *
 * Template uses: x-data="blueprintPage()"
 */

function blueprintPage() {
    const cfg = window.__BLUEPRINT_CONFIG__ || {};

    const base = {
        solutionId: cfg.solutionId,
        csrfToken: cfg.csrfToken || '',
        narratives: {},
        scores: cfg.scores || {},
        riskImporting: false,
        riskImportResult: null,
        sectionElements: {},
        sectionRelationships: {},
        diagramsLoaded: {},
        renderers: {},
        saving: {},
        narrativeSaving: {},   // 'idle' | 'saving' | 'saved' | 'error' per section
        generatingNarrative: {},  // bool per section — AI generation in flight
        activeSection: '',

        // SAD data arrays for reused partials
        sadIntegrationFlows: [],
        sadComposition: [],
        sadRiskSnapshots: [],
        sadQualityAttributes: [],
        sadSLAs: [],
        sadInvestmentPhases: [],
        sadGovernanceExceptions: [],
        sadComplianceMappings: [],
        sadChangeRequests: [],
        sadFeasibilityReviews: [],
        sadBenefitRealizations: [],
        sadOrgImpacts: [],
        sadLessonsLearned: [],
        sadAppElements: [],
        sadTechElements: [],

        // Motivation layer entities (vision_motivation section)
        drivers: [],
        goals: [],
        constraints: [],

        // Entity modal state
        entityType: '',
        editingEntity: null,
        formData: {},
        activeModal: null,
        deleteTarget: null,
        modalSaving: false,
        apiBase: '/solutions/' + (cfg.solutionId || ''),
        
        // Compliance gap analysis state
        complianceGapLoading: false,
        complianceGapLoaded: false,
        complianceGap: null,

        /* ── lifecycle ───────────────────────────────────────────────── */

        init: function () {
            let self = this;
            let defs = cfg.sectionDefinitions || {};

            // Hydrate from server-rendered config
            Object.keys(defs).forEach(function (key) {
                self.narratives[key] = defs[key].narrative || '';
                self.sectionElements[key] = defs[key].elements || [];
                self.diagramsLoaded[key] = false;
                
                // Initialize specLoading to false for all elements
                const elems = defs[key].elements || [];
                elems.forEach(function(elem) {
                    const elemId = elem.element_id || elem.id;
                    if (elemId) {
                        self.specLoading[elemId] = false;
                    }
                });
            });

            // Hydrate SAD arrays from server context
            const sad = cfg.sadData || {};
            self.sadIntegrationFlows = sad.integration_flows || [];
            self.sadComposition = sad.composition || [];
            self.sadRiskSnapshots = sad.risk_snapshots || [];
            self.sadQualityAttributes = sad.quality_attributes || [];
            self.sadSLAs = sad.slas || [];
            self.sadInvestmentPhases = sad.investment_phases || [];
            self.sadGovernanceExceptions = sad.governance_exceptions || [];
            self.sadComplianceMappings = sad.compliance_mappings || [];
            self.sadChangeRequests = sad.change_requests || [];
            self.sadFeasibilityReviews = sad.feasibility_reviews || [];
            self.sadBenefitRealizations = sad.benefit_realizations || [];
            self.sadOrgImpacts = sad.org_impacts || [];
            self.sadLessonsLearned = sad.lessons_learned || [];
            self.sadAppElements = sad.app_elements || [];
            self.sadTechElements = sad.tech_elements || [];

            // Hydrate motivation layer entities from lifecycle data
            const lc = cfg.lifecycleData || {};
            self.drivers = lc.drivers || [];
            self.goals = lc.goals || [];
            self.constraints = lc.constraints || [];

            self._setupScrollObserver();
            self._loadAllSectionElements();

            // Reload a single section's elements after the link picker links/unlinks something
            window.addEventListener('bp-section-reload', function (e) {
                let sectionId = (e.detail || {}).sectionId;
                if (sectionId) {
                    self._reloadSectionElements(sectionId);
                    self._refreshScores();
                }
            });

            // Reload affected section when the AI Copilot writes to the database
            window.addEventListener('bp-agent-wrote', function (e) {
                let entityType = (e.detail || {}).entity_type;
                const sectionMap = {
                    'driver': 'sec-2',
                    'goal': 'sec-2',
                    'constraint': 'sec-2',
                    'requirement': 'sec-3',
                    'risk': 'sec-8',
                    'option': 'sec-5',
                    'application_link': 'sec-3',
                    'vendor_product_link': 'sec-4',
                };
                let sectionId = sectionMap[entityType];
                if (sectionId) {
                    self._reloadSectionElements(sectionId);
                }
                self._refreshScores();
            });
        },

        /* ── narrative auto-save (debounce handled by Alpine @input.debounce) ── */

        autoSave: function (sectionId) {
            let self = this;
            if (self.saving[sectionId]) return;
            self.saving[sectionId] = true;
            self.narrativeSaving[sectionId] = 'saving';

            fetch('/solutions/' + self.solutionId + '/api/section-narratives/' + sectionId, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                },
                body: JSON.stringify({ narrative: self.narratives[sectionId] })
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Save failed: ' + r.status);
                self.narrativeSaving[sectionId] = 'saved';
                self._refreshScores();
                // Clear the "Saved" indicator after 3 seconds
                setTimeout(function () {
                    if (self.narrativeSaving[sectionId] === 'saved') {
                        self.narrativeSaving[sectionId] = 'idle';
                    }
                }, 3000);
            })
            .catch(function (e) {
                console.error('[blueprint] autoSave error:', e);
                self.narrativeSaving[sectionId] = 'error';
            })
            .finally(function () {
                self.saving[sectionId] = false;
            });
        },

        generateNarrative: function (sectionId) {
            let self = this;
            if (self.generatingNarrative[sectionId]) return;
            self.generatingNarrative[sectionId] = true;

            fetch('/solutions/' + self.solutionId + '/api/blueprint/' + sectionId + '/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                },
                body: JSON.stringify({})
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Generate failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success && data.error) throw new Error(data.error);
                if (data.narrative) {
                    self.narratives[sectionId] = data.narrative;
                    self.narrativeSaving[sectionId] = 'saved';
                    setTimeout(function () {
                        if (self.narrativeSaving[sectionId] === 'saved') {
                            self.narrativeSaving[sectionId] = 'idle';
                        }
                    }, 3000);
                }
                self._refreshScores();
                if (window.Platform && Platform.toast) {
                    Platform.toast.success('Narrative generated (' + (data.word_count || 0) + ' words)');
                }
            })
            .catch(function (e) {
                console.error('[blueprint] generateNarrative error:', e);
                if (window.Platform && Platform.toast) Platform.toast.error(e.message || 'Generation failed');
            })
            .finally(function () {
                self.generatingNarrative[sectionId] = false;
            });
        },

        /* ── diagram lazy-loading (called via x-intersect.once) ────── */

        loadDiagram: function (sectionId) {
            let self = this;
            self.diagramsLoaded[sectionId] = true; // mark container ready

            if (typeof joint === 'undefined' || !joint.dia || typeof ComposerRenderer === 'undefined') {
                // JointJS not yet loaded or not fully initialised — retry once after a short delay
                setTimeout(function () { self._renderDiagram(sectionId); }, 800);
                return;
            }
            self._renderDiagram(sectionId);
        },

        _renderDiagram: function (sectionId) {
            let self = this;

            if (typeof joint === 'undefined' || !joint.dia || typeof ComposerRenderer === 'undefined') return;

            const container = document.getElementById('diagram-' + sectionId);
            if (!container) return;

            // Destroy existing renderer if present
            if (self.renderers[sectionId]) {
                try { self.renderers[sectionId].destroy(); } catch (e) {}
                delete self.renderers[sectionId];
            }

            // Always fetch so relationships are included alongside elements
            fetch('/solutions/' + self.solutionId + '/api/viewpoint/' + sectionId + '/elements')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                const elements = (data.data && data.data.elements) || [];
                const relationships = (data.data && data.data.relationships) || [];
                self.sectionElements[sectionId] = elements;
                self.sectionRelationships[sectionId] = relationships;
                self._doRenderDiagram(sectionId, container, elements, relationships);
            })
            .catch(function (e) {
                console.warn('[blueprint] diagram fetch failed for ' + sectionId + ':', e);
            });
        },

        _doRenderDiagram: function (sectionId, container, elements, relationships) {
            let self = this;
            if (!elements.length) return; // empty — template shows the empty state div

            try {
                container.innerHTML = '';
                let renderer = ComposerRenderer.create(container, { mode: 'view', width: '100%', height: 380 });
                renderer.loadElements(elements, relationships || []);
                renderer.fitToContent();
                self.renderers[sectionId] = renderer;

                // AI Copilot: right-click on diagram element opens context menu
                renderer.paper.on('element:contextmenu', function (elementView, evt) {
                    evt.preventDefault();
                    const el = elementView.model;
                    // Find name: prefer JointJS model attr, then SVG nameLabel text, then any non-dash text
                    let elName = el.attr('label/text') || el.attr('.label/text') || el.attr('body/text') || null;
                    if (!elName) {
                        // Look for joint-selector="nameLabel" text element first
                        const rootEl = elementView.el || (evt.target && evt.target.closest('[model-id]'));
                        if (rootEl) {
                            const nameLabelEl = rootEl.querySelector('[joint-selector="nameLabel"]');
                            if (nameLabelEl && nameLabelEl.textContent.trim() && nameLabelEl.textContent.trim() !== '-') {
                                elName = nameLabelEl.textContent.trim();
                            } else {
                                const texts = Array.from(rootEl.querySelectorAll('text'));
                                const candidate = texts.find(function(t) {
                                    const v = t.textContent.trim();
                                    return v && v !== '-';
                                });
                                elName = candidate ? candidate.textContent.trim() : null;
                            }
                        }
                    }
                    if (!elName) { elName = 'Element'; }
                    const elType = el.get('archimateType') || el.attr('body/stereotype') || el.get('type') || 'Unknown';
                    window.dispatchEvent(new CustomEvent('bp-element-context-menu', {
                        detail: {
                            elementId: el.get('archimateId') || el.id,
                            elementName: elName,
                            elementType: elType,
                            sectionId: sectionId,
                            x: evt.clientX,
                            y: evt.clientY,
                        },
                    }));
                });
            } catch (e) {
                console.warn('[blueprint] diagram render failed for ' + sectionId + ':', e);
            }
        },

        /* ── toolbar actions ─────────────────────────────────────────── */

        openComposer: function (sectionId) {
            let self = this;
            window.open('/archimate/composer?solution=' + self.solutionId + '&section=' + sectionId, '_blank');
        },

        exportPng: function (sectionId) {
            let self = this;
            let renderer = self.renderers[sectionId];
            if (renderer && typeof renderer.exportPng === 'function') {
                renderer.exportPng();
            }
        },

        linkElements: function (sectionId) {
            window.dispatchEvent(new CustomEvent('bp-link-open', {
                detail: { sectionId: sectionId }
            }));
        },

        generateFromJourney: function (sectionId) {
            let self = this;

            // POST to the section-level generate endpoint (added in PLT-040+)
            fetch('/solutions/' + self.solutionId + '/api/blueprint/' + sectionId + '/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                },
                body: JSON.stringify({})
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Generate failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (data.elements && data.elements.length) {
                    self.sectionElements[sectionId] = data.elements;
                }
                if (data.narrative) self.narratives[sectionId] = data.narrative;
                self._refreshScores();
                if (window.Platform && Platform.toast) {
                    Platform.toast.success(data.narrative ? 'Narrative generated (' + (data.word_count || 0) + ' words)' : 'Generation complete');
                }
            })
            .catch(function (e) {
                console.error('[blueprint] generateFromJourney error:', e);
                if (window.Platform && Platform.toast) Platform.toast.error('Generation failed: ' + e.message);
            });
        },

        generateAll: function () {
            let self = this;
            const desc = ((window.__BLUEPRINT_CONFIG__ || {}).sadData || {}).description ||
                       (window.__BLUEPRINT_CONFIG__ || {}).solutionName || '';

            if (!desc) {
                if (window.Platform && Platform.toast) Platform.toast.error('No problem statement — edit the solution description first');
                return;
            }

            if (window.Platform && Platform.toast) Platform.toast.success('Generating — this takes 20-40 seconds…');

            fetch('/solutions/' + self.solutionId + '/generate-draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                },
                body: JSON.stringify({ problem_statement: desc })
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Generate failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (data.success) {
                    self._refreshScores();
                    if (window.Platform && Platform.toast) Platform.toast.success('Created ' + (data.total || 0) + ' entities — reloading…');
                    setTimeout(function () { window.location.reload(); }, 2000);
                } else {
                    if (window.Platform && Platform.toast) Platform.toast.error(data.error || 'Generation failed');
                }
            })
            .catch(function (e) {
                console.error('[blueprint] generateAll error:', e);
                if (window.Platform && Platform.toast) Platform.toast.error('Generation failed: ' + e.message);
            });
        },

        /* ── entity CRUD (ported from detail-phase-crud.js) ─────────── */

        openEntityModal: function (type, entity) {
            this.entityType = type;
            this.editingEntity = entity || null;
            this.formData = entity ? Object.assign({}, entity) : this._defaults(type);
            this.activeModal = type;
        },

        closeModal: function () {
            this.activeModal = null;
            this.editingEntity = null;
            this.formData = {};
            this.modalSaving = false;
        },

        _defaults: function (type) {
            if (type === 'risk') return { risk_description: '', impact: 'medium', probability: 'medium', mitigation: '', status: 'open', owner: '' };
            if (type === 'metric') return { name: '', unit: '', baseline_value: '', target_value: '', actual_value: '', status: 'not_measured' };
            if (type === 'tco') return { option_label: 'Proposed', cost_category: '', is_recurring: true, year: 1, amount: 0, notes: '' };
            if (type === 'plateau') return { name: '', description: '', order: 0, target_date: '' };
            if (type === 'driver') return { name: '', description: '', driver_type: 'internal', impact_level: 3, urgency: 3, source: '' };
            if (type === 'goal') return { name: '', description: '', priority: 3, measurement_criteria: '' };
            if (type === 'constraint') return { name: '', description: '', constraint_type: 'technical', value: '', severity: 3 };
            if (type === 'requirement') return { name: '', description: '', requirement_type: 'functional', priority: 3, is_mandatory: false, source: '', rationale: '', acceptance_criteria: '' };
            if (type === 'option') return { name: '', option_type: 'build', justification: '', estimated_cost_min: null, estimated_cost_max: null, timeline_months: null, score: null, confidence: null, is_recommended: false, pros: [], cons: [], risks: [] };
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
            if (type === 'principle') return { name: '', description: '', rationale: '', implications: '', priority: 'medium', source: '', notes: '' };
            if (type === 'assessment') return { assessment_type: 'gap', name: '', current_state: '', target_state: '', gap_description: '', severity: 3, notes: '' };
            if (type === 'stakeholder_sad') return { name: '', role: '', organization: '', influence_level: 'medium', interest_level: 'medium', engagement_strategy: '', notes: '' };
            if (type === 'business_element') return { element_type: 'service', name: '', description: '', owner: '', status: 'current', apqc_process_id: null, notes: '' };
            if (type === 'app_element') return { element_type: 'service', name: '', description: '', technology: '', status: 'current', notes: '' };
            if (type === 'tech_element') return { element_type: 'node', name: '', description: '', specification: '', status: 'current', notes: '' };
            return {};
        },

        _apiPath: function (type) {
            if (type === 'risk') return '/risks';
            if (type === 'metric') return '/metrics';
            if (type === 'tco') return '/tco';
            if (type === 'plateau') return '/plateaus';
            if (type === 'driver') return '/drivers';
            if (type === 'goal') return '/goals';
            if (type === 'constraint') return '/constraints';
            if (type === 'requirement') return '/requirements';
            if (type === 'option') return '/options';
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
            if (type === 'principle') return '/principles';
            if (type === 'assessment') return '/assessments';
            if (type === 'stakeholder_sad') return '/stakeholders-sad';
            if (type === 'business_element') return '/business-elements';
            if (type === 'app_element') return '/app-elements';
            if (type === 'tech_element') return '/tech-elements';
            return '';
        },

        _listKey: function (type) {
            if (type === 'risk') return 'risks';
            if (type === 'metric') return 'metrics';
            if (type === 'tco') return 'tcoItems';
            if (type === 'plateau') return 'plateaus';
            if (type === 'driver') return 'drivers';
            if (type === 'goal') return 'goals';
            if (type === 'constraint') return 'constraints';
            if (type === 'requirement') return 'requirements';
            if (type === 'option') return 'recommendations';
            if (type === 'integration_flow') return 'sadIntegrationFlows';
            if (type === 'composition') return 'sadComposition';
            if (type === 'risk_snapshot') return 'sadRiskSnapshots';
            if (type === 'quality_attribute') return 'sadQualityAttributes';
            if (type === 'sla') return 'sadSLAs';
            if (type === 'investment_phase') return 'sadInvestmentPhases';
            if (type === 'governance_exception') return 'sadGovernanceExceptions';
            if (type === 'compliance_mapping') return 'sadComplianceMappings';
            if (type === 'change_request') return 'sadChangeRequests';
            if (type === 'feasibility_review') return 'sadFeasibilityReviews';
            if (type === 'benefit_realization') return 'sadBenefitRealizations';
            if (type === 'org_impact') return 'sadOrgImpacts';
            if (type === 'lesson_learned') return 'sadLessonsLearned';
            if (type === 'principle') return 'sadPrinciples';
            if (type === 'assessment') return 'sadAssessments';
            if (type === 'stakeholder_sad') return 'sadStakeholdersSad';
            if (type === 'business_element') return 'sadBusinessElements';
            if (type === 'app_element') return 'sadAppElements';
            if (type === 'tech_element') return 'sadTechElements';
            return '';
        },

        submitEntity: function () {
            let self = this;
            self.modalSaving = true;
            let type = self.entityType;
            const isEdit = self.editingEntity && self.editingEntity.id;
            let url = self.apiBase + self._apiPath(type) + (isEdit ? '/' + self.editingEntity.id : '');
            const method = isEdit ? 'PUT' : 'POST';

            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                },
                body: JSON.stringify(self.formData)
            })
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return self.refreshEntityData(type);
            })
            .then(function () {
                self.closeModal();
            })
            .catch(function (err) {
                console.error('[blueprint] submitEntity error:', err);
                self.modalSaving = false;
                if (window.Platform && Platform.toast) Platform.toast.error('Save failed');
            });
        },

        confirmDeleteEntity: function (type, entity) {
            this.entityType = type;
            this.deleteTarget = entity;
            this.activeModal = 'delete';
        },

        executeDeleteEntity: function () {
            let self = this;
            if (!self.deleteTarget) return;
            self.modalSaving = true;
            let type = self.entityType;
            let url = self.apiBase + self._apiPath(type) + '/' + self.deleteTarget.id;

            fetch(url, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': self.csrfToken }
            })
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return self.refreshEntityData(type);
            })
            .then(function () {
                self.closeModal();
            })
            .catch(function (err) {
                console.error('[blueprint] executeDeleteEntity error:', err);
                self.modalSaving = false;
                if (window.Platform && Platform.toast) Platform.toast.error('Delete failed');
            });
        },

        refreshEntityData: function (type) {
            let self = this;
            let url = self.apiBase + self._apiPath(type);

            return fetch(url)
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (json) {
                const listKey = self._listKey(type);
                const items = json.data || json.items || [];
                self[listKey] = items;
            })
            .catch(function (err) {
                console.error('[blueprint] refreshEntityData error:', err);
            });
        },

        /* ── export / spec actions ───────────────────────────────────── */

        exportPdf: function () {
            let self = this;
            window.open('/solutions/' + self.solutionId + '/api/export/blueprint-pdf', '_blank');
        },

        generateSpecs: function () {
            let self = this;

            fetch('/solutions/' + self.solutionId + '/api/generate-specs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                }
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Spec generation failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (data.download_url) {
                    window.open(data.download_url, '_blank');
                }
                if (window.Platform && Platform.toast) Platform.toast.success('Specs generated');
            })
            .catch(function (e) {
                console.error('[blueprint] generateSpecs error:', e);
                if (window.Platform && Platform.toast) Platform.toast.error('Spec generation failed');
            });
        },

        inferCodeSpecs: function () {
            let self = this;

            fetch('/solutions/' + self.solutionId + '/api/infer-code-specs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.csrfToken
                }
            })
            .then(function (r) {
                if (!r.ok) throw new Error('Code spec inference failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                console.log('[blueprint] inferCodeSpecs result:', data);
            })
            .catch(function (e) {
                console.error('[blueprint] inferCodeSpecs error:', e);
            });
        },

        /* ── internal helpers ────────────────────────────────────────── */

        _loadAllSectionElements: function () {
            let self = this;
            let defs = cfg.sectionDefinitions || {};

            Object.keys(defs).forEach(function (sectionId) {
                const def = defs[sectionId];
                // Only fetch for sections that have a viewpoint defined
                if (!def || !def.viewpoint) return;
                self._reloadSectionElements(sectionId);
            });
        },

        _reloadSectionElements: function (sectionId) {
            let self = this;

            fetch('/solutions/' + self.solutionId + '/api/viewpoint/' + sectionId + '/elements')
            .then(function (r) {
                if (!r.ok) throw new Error('Elements fetch failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                self.sectionElements[sectionId] = (data.data && data.data.elements) || data.elements || [];
                // Re-render diagram if the container is already visible
                if (self.diagramsLoaded[sectionId]) {
                    self._renderDiagram(sectionId);
                }
            })
            .catch(function (e) {
                console.error('[blueprint] _reloadSectionElements error for ' + sectionId + ':', e);
            });
        },

        _refreshScores: function () {
            let self = this;

            fetch('/solutions/' + self.solutionId + '/api/blueprint-scores')
            .then(function (r) {
                if (!r.ok) throw new Error('Scores fetch failed: ' + r.status);
                return r.json();
            })
            .then(function (data) {
                self.scores = data.scores || data;
            })
            .catch(function (e) {
                console.error('[blueprint] _refreshScores error:', e);
            });
        },

        _setupScrollObserver: function () {
            let self = this;

            if (typeof IntersectionObserver === 'undefined') return;

            const sections = document.querySelectorAll('[data-bp-section]');
            if (!sections.length) return;

            const observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        self.activeSection = entry.target.id || '';
                    }
                });
            }, {
                rootMargin: '-120px 0px -60% 0px'
            });

            sections.forEach(function (section) {
                observer.observe(section);
            });
        }
    };

    // ── Universal entity CRUD modal (drivers / goals / constraints / requirements / risks / options / plateaus) ──
    base.modal = { open: false, title: '', entity: '', fields: [], saving: false, error: '' };
    base.form = {};

    base.entityTypes = {
        driver:      { label: 'Driver',      path: '/drivers',      fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'driver_type',label:'Type',type:'select',options:['internal','external','regulatory','technology']}] },
        goal:        { label: 'Goal',        path: '/goals',        fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'priority',label:'Priority',type:'select',options:[{v:1,l:'Critical'},{v:2,l:'High'},{v:3,l:'Medium'},{v:4,l:'Low'}]}] },
        constraint:  { label: 'Constraint',  path: '/constraints',  fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'constraint_type',label:'Type',type:'select',options:['budget','time','technical','regulatory','resource']},{key:'severity',label:'Severity',type:'select',options:[{v:1,l:'Critical'},{v:2,l:'High'},{v:3,l:'Medium'},{v:4,l:'Low'}]}] },
        requirement: { label: 'Requirement', path: '/requirements', fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'requirement_type',label:'Type',type:'select',options:['functional','non_functional','compliance','security']},{key:'priority',label:'Priority',type:'select',options:[{v:1,l:'Critical'},{v:2,l:'High'},{v:3,l:'Medium'},{v:4,l:'Low'}]}] },
        risk:        { label: 'Risk',        path: '/risks',        fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'severity',label:'Severity',type:'select',options:['critical','high','medium','low']},{key:'likelihood',label:'Likelihood',type:'select',options:['almost_certain','likely','possible','unlikely','rare']}] },
        option:      { label: 'Option',      path: '/options',      fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'option_type',label:'Type',type:'select',options:['build','buy','partner','hybrid','reuse']}] },
        plateau:     { label: 'Plateau',     path: '/plateaus',     fields: [{key:'name',label:'Name',required:true},{key:'description',label:'Description',type:'textarea'},{key:'target_date',label:'Target Date',type:'date'}] }
    };

    // importRisksCsv — bulk-import solution risks from a CSV file (GAP-5)
    base.importRisksCsv = async function (event) {
        const file = event.target.files[0];
        if (!file) return;
        this.riskImporting = true;
        this.riskImportResult = null;
        const fd = new FormData();
        fd.append('file', file);
        try {
            const r = await fetch('/solutions/' + this.solutionId + '/risks/import', {
                method: 'POST',
                headers: { 'X-CSRFToken': this.csrfToken },
                body: fd
            });
            const d = await r.json();
            this.riskImportResult = d;
            if (d.created > 0) {
                // Reload risks partial if function exists, else show toast
                if (typeof this.loadRisks === 'function') { this.loadRisks(); }
                let msg = d.created + ' risk' + (d.created !== 1 ? 's' : '') + ' imported';
                if (d.skipped) msg += ', ' + d.skipped + ' skipped';
                window.dispatchEvent(new CustomEvent('bp-toast', { detail: { message: msg, type: 'success' } }));
                if (typeof refreshMaturityScore === 'function') refreshMaturityScore();
            } else {
                const errMsg = d.error || ('No risks imported' + (d.errors && d.errors.length ? ': ' + d.errors[0].reason : ''));
                window.dispatchEvent(new CustomEvent('bp-toast', { detail: { message: errMsg, type: 'error' } }));
            }
        } catch(e) {
            window.dispatchEvent(new CustomEvent('bp-toast', { detail: { message: 'Import failed', type: 'error' } }));
        } finally {
            this.riskImporting = false;
            event.target.value = '';
        }
    };

    // openAdd dispatches an event — the modal lives in {% block modals %} (separate Alpine scope)
    base.openAdd = function (entityType) {
        window.dispatchEvent(new CustomEvent('bp-add-entity', {
            detail: {
                entityType: entityType,
                solutionId: this.solutionId,
                csrfToken: this.csrfToken,
                entityTypes: this.entityTypes
            }
        }));
    };
    
    // Compliance gap analysis loader
    base.loadComplianceGap = function() {
        const self = this;
        self.complianceGapLoading = true;
        fetch('/solutions/' + self.solutionId + '/api/compliance-gap')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    self.complianceGap = data.gap;
                }
                self.complianceGapLoaded = true;
                self.complianceGapLoading = false;
            })
            .catch(function() {
                self.complianceGapLoaded = true;
                self.complianceGapLoading = false;
            });
    };

    // Merge spec panel mixins (component specs, integration contracts, deployment specs)
    const mixins = [
        typeof componentSpecsMixin === 'function' ? componentSpecsMixin() : null,
        typeof integrationContractsMixin === 'function' ? integrationContractsMixin() : null,
        typeof deploymentSpecsMixin === 'function' ? deploymentSpecsMixin() : null
    ];
    for (let i = 0; i < mixins.length; i++) {
        if (mixins[i]) {
            for (let key in mixins[i]) {
                if (mixins[i].hasOwnProperty(key)) {
                    base[key] = mixins[i][key];
                }
            }
        }
    }

    return base;
}
