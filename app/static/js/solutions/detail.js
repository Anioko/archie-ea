/**
 * solutions/detail.js
 * Solution detail page — CRUD for risks, metrics, TCO, plateaus + capability loader.
 * Reads config from window.__SOLUTION_CONFIG__:
 *   { solutionId, deleteUrl, capabilitiesApiUrl, apiBase, initialData }
 */

function deleteSolution() {
    let modalId = window.modalManager.createModal({
        title: 'Delete Solution',
        content: '<p class="text-sm text-muted-foreground">Are you sure you want to delete this solution? This action cannot be undone.</p>',
        size: 'small',
        buttons: [
            { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-input rounded-md hover:bg-accent', action: 'cancel', handler: function() {} },
            { text: 'Delete', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'delete', handler: async function() {
                let url = window.__SOLUTION_CONFIG__?.deleteUrl;
                if (!url) { console.error('[solutions/detail] deleteUrl not set'); return; }
                let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('[name=csrf_token]')?.value || '';
                try {
                    let resp = await fetch(url, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' }
                    });
                    let data = await resp.json();
                    if (data.success) {
                        window.location.href = data.redirect_url || window.__SOLUTION_CONFIG__?.listUrl || '/solutions/';
                    } else {
                        Platform.toast.error('Delete failed: ' + (data.error || 'unknown error'));
                    }
                } catch(err) {
                    Platform.toast.error('Delete failed: ' + err.message);
                }
            } }
        ]
    });
    window.modalManager.open(modalId);
}

function getCoverageClass(type) {
    switch (type) {
        case 'core': return 'bg-emerald-500';
        case 'supporting': return 'bg-amber-500';
        case 'optional': return 'bg-primary';
        default: return 'bg-primary';
    }
}

async function loadSolutionCapabilities() {
    const container = document.getElementById('solution-capabilities-container');
    if (!container) return;

    const solutionId = window.__SOLUTION_CONFIG__?.solutionId;
    if (!solutionId) { console.error('[solutions/detail] solutionId not set'); return; }

    const apiUrl = window.__SOLUTION_CONFIG__?.capabilitiesApiUrl;
    if (!apiUrl) { console.error('[solutions/detail] capabilitiesApiUrl not set'); return; }

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        const capabilities = result.capabilities || [];

        if (capabilities.length === 0) {
            safeHTML(container, `
              <div class="text-center py-8 text-muted-foreground border-2 border-dashed border-border rounded-lg">
                <i data-lucide="zap" class="h-12 w-12 mx-auto mb-4 opacity-50"></i>
                <h3 class="text-base font-semibold text-foreground mb-1">No Capabilities Mapped</h3>
                <p class="text-sm">This solution does not have any business capabilities mapped yet.</p>
              </div>
            `);
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        let tableHTML = `
          <div class="overflow-x-auto border border-border rounded-lg">
            <table class="min-w-full">
              <thead class="bg-muted/50 border-b border-border">
                <tr>
                  <th class="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Capability</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Category</th>
                  <th class="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Priority</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
        `;

        capabilities.forEach(cap => {
            let category = cap.category || 'required';
            let categoryClass = category === 'required' ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/30'
                : category === 'optional' ? 'bg-amber-500/10 text-amber-600 border border-amber-500/30'
                : 'bg-primary/10 text-primary border border-primary/30';
            let categoryLabel = escapeHtml(category.charAt(0).toUpperCase() + category.slice(1));

            tableHTML += `
              <tr class="hover:bg-muted/50 transition-colors">
                <td class="px-4 py-3 text-sm">
                  <div class="flex flex-col gap-0.5">
                    <span class="font-medium text-foreground">${escapeHtml(cap.name || 'N/A')}</span>
                    ${cap.description ? '<span class="text-xs text-muted-foreground">' + escapeHtml(cap.description.substring(0, 80)) + '</span>' : ''}
                  </div>
                </td>
                <td class="px-4 py-3 text-sm">
                  <span class="inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-medium ${categoryClass}">${categoryLabel}</span>
                </td>
                <td class="px-4 py-3 text-sm text-muted-foreground">
                  ${cap.priority != null ? 'P' + cap.priority : '\u2014'}
                </td>
              </tr>
            `;
        });

        tableHTML += `</tbody></table></div>`;
        safeHTML(container, tableHTML);

    } catch (error) {
        console.error('[solutions/detail] Error loading capabilities:', error);
        safeHTML(container, `
          <div class="text-center py-8 text-muted-foreground border-2 border-dashed border-border rounded-lg">
            <p class="text-sm">Unable to load capabilities. The API may be loading or no data has been configured.</p>
          </div>
        `);
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Alpine component: solutionDetail
 * Full CRUD for risks, metrics, TCO items, plateaus, drivers, goals, constraints
 * ═══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('alpine:init', function () {
    Alpine.data('solutionDetail', function () {
        let cfg = window.__SOLUTION_CONFIG__ || {};
        let base = cfg.apiBase || '/solutions/' + cfg.solutionId;
        let initial = cfg.initialData || {};

        let _solutionDetailBase = {
            apiBase: base,
            risks: initial.risks || [],
            metrics: initial.metrics || [],
            tcoItems: initial.tcoItems || [],
            plateaus: initial.plateaus || [],
            drivers: initial.drivers || [],
            goals: initial.goals || [],
            constraints: initial.constraints || [],
            requirements: initial.requirements || [],
            recommendations: initial.recommendations || [],
            analyzingOptions: false,
            submittingArb: false,
            activeSection: 'sec-1',
            expandedSections: {},

            /* ── Tab-based navigation (replaces sidebar vertical nav) ── */
            activeTab: 'vision',
            _tabSections: {
                vision: ['sec-1','sec-2'],
                business: ['sec-3'],
                infosys: ['sec-4'],
                opportunities: ['sec-5'],
                migration: ['sec-6'],
                governance: ['sec-7','sec-8','sec-9','sec-10'],
            },
            _secToTab: {
                'sec-1':'vision','sec-2':'vision','sec-3':'business','sec-4':'infosys',
                'sec-5':'opportunities','sec-6':'migration','sec-7':'governance',
                'sec-8':'governance','sec-9':'governance','sec-10':'governance'
            },

            /** Auto-navigate to the first section that needs work */
            autoNavToIncomplete() {
                let order = ['sec-1','sec-2','sec-3','sec-4','sec-5','sec-6','sec-7','sec-8','sec-9','sec-10'];
                let self = this;
                let first = null;
                for (let i = 0; i < order.length; i++) {
                    const interp = self.phaseInterpretation(order[i]);
                    if (interp.completePct > 0 && interp.completePct < 100) {
                        first = order[i];
                        break;
                    }
                }
                if (first) {
                    self.activeSection = first;
                    self.activeTab = self._secToTab[first] || 'vision';
                }
                /* Auto-expand all sections in the active tab */
                let secs = self._tabSections[self.activeTab] || ['sec-1'];
                secs.forEach(function(s) { self.expandedSections[s] = true; });
                self.expandedSections = Object.assign({}, self.expandedSections);
                let phaseMap = {'sec-1':'A_exec','sec-2':'A','sec-3':'B','sec-4':'C','sec-5':'E','sec-6':'F','sec-7':'G','sec-8':'R','sec-9':'H','sec-10':'T'};
                secs.forEach(function(s) { self.initSectionCanvas(phaseMap[s] || 'A'); });
            },

            // SOL-006: Persona selector — controls which tabs are visible
            activePersona: 'sa',
            _personaSections: {
                'sa':  ['sec-1','sec-2','sec-3','sec-4','sec-5','sec-6','sec-7','sec-8','sec-9','sec-10'],
                'arb': ['sec-1','sec-2','sec-7','sec-8'],
                'ea':  ['sec-1','sec-3','sec-4','sec-8','sec-10'],
                'cto': ['sec-1','sec-5','sec-6','sec-9'],
            },
            _personaTabs: {
                sa:  ['vision','business','infosys','opportunities','migration','governance'],
                arb: ['vision','governance'],
                ea:  ['vision','business','infosys','governance'],
                cto: ['vision','opportunities','migration','governance'],
            },
            personaVisible(secId) {
                /* Keep for backward compat with section_shell — always true since tabs handle filtering */
                return true;
            },
            tabVisible(tabId) {
                let key = (this.activePersona || 'sa').toLowerCase();
                let visible = this._personaTabs[key] || this._personaTabs.sa;
                return visible.indexOf(tabId) !== -1;
            },
            setPersona(p) {
                this.activePersona = p;
                /* If current tab is now hidden, jump to first visible tab */
                if (!this.tabVisible(this.activeTab)) {
                    let visible = this._personaTabs[p] || this._personaTabs.sa;
                    this.activeTab = visible[0] || 'vision';
                }
            },
            governanceStatus: cfg.governanceStatus || 'draft',
            canSubmitArb: cfg.canSubmitArb || false,
            workspaceSummary: cfg.workspaceSummary || {},
            maturityGaps: cfg.maturityGaps || [],
            maturityScore: cfg.maturityScore || 0,
            nextActions: [],
            nextActionsLoading: false,
            nextActionsError: '',
            has_ai_generated_content: false,
            showArbAiConfirmModal: false,
            require_second_review: false,
            second_reviewer_id: null,
            costSource: cfg.costSource || null,
            arbChecklist: [
                { label: 'Architecture principles checked', checked: false },
                { label: 'Risks documented', checked: false },
                { label: 'Stakeholders consulted', checked: false },
                { label: 'Cost validated', checked: false },
                { label: 'Alternatives analyzed', checked: false },
            ],
            pendingArbAction: '',
            showResubmitModal: false,
            resubmissionNotes: '',
            arbConditions: cfg.arbConditions || [],
            togglingCondition: -1,
            suggestingElements: false,
            aiSuggestions: [],
            aiSuggestPhase: null,
            aiReasoningStateId: null,
            generatingReqs: false,
            generatingArchitecture: false, // CAP-008 (legacy name kept for compat)
            stagingGenerating: false, // CAP-009 staging panel generation state
            aiRequirementSuggestions: [],
            aiReqReasoningStateId: null,
            checkingReadiness: false,
            readinessChecks: [],
            showCreationSummary: new URLSearchParams(window.location.search).has('from_analysis'),
            vendorCompareView: false,

            // SAD-08: AI Insights panel state (methods in detail-ai.js)
            aiInsightsLoaded: false,
            aiInsightsLoading: false,
            aiInsightsOpen: false,
            aiInsightsTab: 'vendors',
            aiInsightsData: { vendors: null, costs: null, risks: null, actions: null, archimate: null },
            // SAD-11: Explainability modal state
            explainOpen: false,
            explainLoading: false,
            explainData: null,

            // ENT-019: Outcome recording (Phase H)
            outcomeForm: { go_live_date: '', actual_duration_weeks: '', actual_cost_usd: '', lessons_learned: '', what_went_well: '', what_to_improve: '' },
            outcomeSubmitting: false,
            outcomeSuccess: '',
            outcomeError: '',


            // ArchiMate diagram (SDX-011)
            archimateElements: cfg.archimateElements || [],
            linkedArchimateElements: [],
            linkedArchimateLoading: false,
            // PRD-007: ArchiMate element picker
            archimatePickerQuery: '',
            archimatePickerLayer: '',
            archimatePickerResults: [],
            archimatePickerLoading: false,
            archimatePickerOpen: false,
            _archimatePickerTimer: null,
            // PRD-008 / CAP-016: Capability picker (hierarchical tree)
            capabilityPickerQuery: '',
            capabilityPickerResults: [],
            capabilityPickerLoading: false,
            capabilityPickerOpen: false,
            linkedCapabilities: [],
            linkedCapabilitiesLoading: false,
            _capabilityPickerTimer: null,
            // CAP-016: Tree picker state
            capTreeAll: [],
            capTreeFiltered: [],
            capTreeDomains: [],
            capTreeDomainFilter: '',
            capTreeExpanded: {},
            capTreeLoading: false,
            capTreeVisible: false,
            // PRD-009: Vendor Product picker
            vendorProductPickerQuery: '',
            vendorProductPickerResults: [],
            vendorProductPickerLoading: false,
            vendorProductPickerOpen: false,
            linkedVendorProducts: [],
            linkedVendorProductsLoading: false,
            _vendorProductPickerTimer: null,
            // ENT-006: Vendor comparison table toggle
            vendorComparisonView: false,
            // PRD-010: APQC Process picker
            apqcPickerQuery: '',
            apqcPickerResults: [],
            apqcPickerLoading: false,
            apqcPickerOpen: false,
            linkedAPQCProcesses: [],
            linkedAPQCLoading: false,
            _apqcPickerTimer: null,
            // PRD-012: Application picker
            appPickerQuery: '',
            appPickerResults: [],
            appPickerLoading: false,
            appPickerOpen: false,
            linkedApplications: [],
            linkedAppsLoading: false,
            _appPickerTimer: null,
            // PLT-004: CSV junction import
            csvImporting: false,
            csvImportResult: null,
            csvImportError: '',
            // ARC-E04: Architect Scratchpad
            scratchpadOpen: false,
            scratchpadItems: [],
            scratchpadLoading: false,
            // SAD-019: Related solutions
            relatedSolutions: [],
            relatedSolutionsLoading: false,
            relatedSolutionsLoaded: false,
            // SAD-BOOTSTRAP: Generate content for empty solutions
            bootstrapLoading: false,
            // SMART-DEFAULTS: NON-LLM smart population from real data
            smartDefaultsLoading: false,
            smartDefaultsPreview: null,
            smartDefaultsDone: false,
            smartDefaultsError: null,
            smartDefaultsResult: null,
            smartDefaultsCreatedIds: null,
            // GUIDED WIZARD: 4-step overlay for new solutions
            wizardActive: false,
            wizardStep: 1,
            wizardDismissed: false,
            // BPP-014: Phase generation preview
            generatePreview: null,
            generateLoading: null,
            generateError: null,

            // SEC-UNI: Section canvas data for ArchiMate mini-diagrams
            sectionCanvasData: {},

            // BIZBOK: Viewpoint diagram state per tab
            _viewpointDiagrams: {},
            _viewpointRenderers: {},
            _tabViewpoints: {
                vision: 'motivation',
                business: 'strategy',
                infosys: 'solution_architecture',
                governance: 'layered',
                migration: 'implementation_migration',
            },

            _layerOrder: ['motivation', 'strategy', 'business', 'application', 'technology', 'implementation'],
            _layerColors: {
                motivation: '#B3A2C7',
                strategy: '#F5D742',
                business: '#FFFFB5',
                application: '#B5E3FF',
                technology: '#C9E6B5',
                implementation: '#FFB5B5'
            },
            _layerTextColors: {
                motivation: '#6B21A8',
                strategy: '#854D0E',
                business: '#713F12',
                application: '#075985',
                technology: '#166534',
                implementation: '#991B1B'
            },
            get archimateByLayer() {
                let groups = {};
                let order = this._layerOrder;
                for (let i = 0; i < this.archimateElements.length; i++) {
                    let el = this.archimateElements[i];
                    let layer = (el.layer || '').toLowerCase();
                    if (!groups[layer]) groups[layer] = [];
                    groups[layer].push(el);
                }
                let result = [];
                for (let j = 0; j < order.length; j++) {
                    if (groups[order[j]] && groups[order[j]].length > 0) {
                        result.push({ layer: order[j], elements: groups[order[j]] });
                    }
                }
                return result;
            },

            // Phase completeness (SDX-008)
            _phaseDeliverables: {
                'A': ['drivers', 'goals', 'constraints'],
                'BCD': ['requirements'],
                'E': ['recommendations'],
            },

            // SAD gap models (14 models completing TOGAF SAD coverage)
            sad: initial.sad || {},
            get sadIntegrationFlows() { return this.sad.integration_flows || []; },
            get sadComposition() { return this.sad.composition || []; },
            get sadRiskSnapshots() { return this.sad.risk_snapshots || []; },
            get sadQualityAttributes() { return this.sad.quality_attributes || []; },
            get sadSLAs() { return this.sad.slas || []; },
            get sadMigrationDeps() { return this.sad.migration_dependencies || []; },
            get sadInvestmentPhases() { return this.sad.investment_phases || []; },
            get sadGovernanceExceptions() { return this.sad.governance_exceptions || []; },
            get sadComplianceMappings() { return this.sad.compliance_mappings || []; },
            get sadChangeRequests() { return this.sad.change_requests || []; },
            get sadFeasibilityReviews() { return this.sad.feasibility_reviews || []; },
            get sadBenefitRealizations() { return this.sad.benefit_realizations || []; },
            get sadOrgImpacts() { return this.sad.org_impacts || []; },
            get sadLessonsLearned() { return this.sad.lessons_learned || []; },
            // ArchiMate 3.2 phase element getters
            get sadPrinciples() { return this.sad.principles || []; },
            get sadAssessments() { return this.sad.assessments || []; },
            get sadStakeholdersSad() { return this.sad.stakeholders_sad || []; },
            get sadBusinessElements() { return this.sad.business_elements || []; },
            get sadAppElements() { return this.sad.app_elements || []; },
            get sadTechElements() { return this.sad.tech_elements || []; },
            get sadTotalCount() {
                let s = this.sad;
                if (!s) return 0;
                let keys = ['integration_flows','composition','risk_snapshots','quality_attributes','slas',
                    'migration_dependencies','investment_phases','governance_exceptions','compliance_mappings',
                    'change_requests','feasibility_reviews','benefit_realizations','org_impacts','lessons_learned',
                    'principles','assessments','stakeholders_sad','business_elements','app_elements','tech_elements'];
                let total = 0;
                for (let i = 0; i < keys.length; i++) { total += (s[keys[i]] || []).length; }
                return total;
            },
            // SAD section completion checklist for progress card
            get sadChecklist() {
                let desc = (window.__SOLUTION_CONFIG__ || {}).hasDescription;
                // SDX-014: Count drivers, goals, constraints, requirements toward SAD completeness
                let hasDrivers = this.drivers && this.drivers.length > 0;
                let hasGoals = this.goals && this.goals.length > 0;
                let hasConstraints = this.constraints && this.constraints.length > 0;
                let hasRequirements = this.requirements && this.requirements.length > 0;
                return [
                    { anchor: 'sec-1', label: 'Summary', done: !!desc || !!hasDrivers },
                    { anchor: 'sec-2', label: 'Strategic', done: hasDrivers || hasGoals || hasConstraints || hasRequirements },
                    { anchor: 'sec-3', label: 'Architecture', done: (this.linkedApplications && this.linkedApplications.length > 0) || (this.linkedVendorProducts && this.linkedVendorProducts.length > 0) || (this.linkedCapabilities && this.linkedCapabilities.length > 0) || (this.archimateElements && this.archimateElements.length > 0) },
                    { anchor: 'sec-4', label: 'Decisions', done: this.linkedADRs && this.linkedADRs.length > 0 },
                    { anchor: 'sec-5', label: 'Risks', done: this.risks && this.risks.length > 0 },
                    { anchor: 'sec-6', label: 'Delivery', done: (this.metrics && this.metrics.length > 0) || (this.tcoItems && this.tcoItems.length > 0) || (this.plateaus && this.plateaus.length > 0) },
                    { anchor: 'sec-7', label: 'Governance', done: this.governanceStatus !== 'draft' || (this.arbConditions && this.arbConditions.length > 0) },
                ];
            },
            get sadCompletionCount() {
                let list = this.sadChecklist;
                let count = 0;
                for (let i = 0; i < list.length; i++) { if (list[i].done) count++; }
                return count;
            },
            // ENT-009: Build guidance text for each maturity gap
            maturityGapGuidance(gap) {
                const entityLabels = {
                    'driver': 'Add a driver',
                    'goal': 'Define a goal',
                    'constraint': 'Add a constraint',
                    'requirement': 'Define requirements',
                    'risk': 'Add a risk',
                    'option': 'Evaluate an option',
                    'plateau': 'Define a transition plateau',
                    'metric': 'Add a success metric'
                };
                const action = entityLabels[gap.entity_type] || gap.phase.replace(/^Phase [A-H][-:]?\s*/i, '');
                return action + ' to reach ' + gap.projected_score + '%';
            },
            get totalEntityCount() {
                return (this.drivers && this.drivers.length) + (this.goals && this.goals.length) + (this.constraints && this.constraints.length) +
                    (this.requirements && this.requirements.length) + (this.recommendations && this.recommendations.length) +
                    (this.risks && this.risks.length) + (this.metrics && this.metrics.length) + (this.tcoItems && this.tcoItems.length) +
                    (this.plateaus && this.plateaus.length) || 0;
            },
            gaps: [],
            gapsLoading: false,
            savingAsTemplate: false,
            outcomeForm: { go_live_date: '', actual_duration_weeks: '', actual_cost_usd: '', business_value_realized: '', lessons_learned: '', what_went_well: '', what_to_improve: '' },
            outcomeSubmitting: false,


            activityList: null,
            activityLoading: false,
            mentionUsers: [],



            // WF-01: EA Workflow trigger panel
            wfDefinitions: [],
            wfDefinitionsLoading: false,
            wfDefinitionsLoaded: false,
            wfStarting: null,
            wfStartError: null,
            wfStarted: null,



            // ENT-060: Business Capability Mappings (Phase B)
            capabilityMappings: [],
            capabilityMappingsLoading: false,
            capabilityMappingsLoaded: false,



            // SAD-13: Lessons Learned panel (Phase H)
            lessonsLearned: [],
            lessonsLoading: false,
            lessonsLoaded: false,

            // CEV-001: Inline traceability panel
            traceabilityData: null,
            traceabilityLoading: false,
            traceabilityLoaded: false,
            traceabilityError: '',

            // SAD-015: Inline viewpoint workspace
            viewpointWorkspace: null,
            viewpointLoading: false,
            viewpointLoadedPhases: {},
            viewpointError: '',
            viewpointActivePhase: 'C',



            // SAD-04: MCDA Solution Options (Phase E)
            solutionOptions: [],
            solutionOptionsLoading: false,
            solutionOptionsLoaded: false,

            // SAD-005: Advanced TCO
            advancedTco: null,
            advancedTcoLoading: false,
            advancedTcoLoaded: false,
            // SAD-002: Predictive Analytics (cost forecasts)
            costForecasts: null,
            costForecastsLoading: false,
            costForecastsLoaded: false,
            // SAD-009: Compliance Gap
            complianceGap: null,
            complianceGapLoading: false,
            complianceGapLoaded: false,
            // SA-008: Design Completeness
            completenessReport: null,
            completenessLoading: false,
            completenessLoaded: false,
            // PLT-008: Suggest Connections
            suggestionsOpen: false,
            suggestionsLoading: false,
            suggestionsData: null,
            suggestionsError: '',
            suggestionsLinking: {},
            // SA-009: ADM Deliverables per solution
            solDeliverableData: {},
            solDeliverablePhases: [],
            solDeliverablesLoading: false,
            solDeliverablesLoaded: false,
            // SAD-012: Version History
            versionHistory: [],
            versionHistoryLoading: false,
            versionHistoryLoaded: false,

            // FRAG-005: Strategic analysis lazy-load state
            strategicRiskAnalysis: null,
            strategicRiskLoading: false,
            strategicRiskLoaded: false,
            strategicInvestment: null,
            strategicInvestmentLoading: false,
            strategicInvestmentLoaded: false,
            strategicDependency: null,
            strategicDependencyLoading: false,
            strategicDependencyLoaded: false,
            strategicTechnology: null,
            strategicTechnologyLoading: false,
            strategicTechnologyLoaded: false,



            mentionOpen: false,
            mentionSectionKey: null,
            mentionQuery: '',

            // Phase awareness (visual indicators only — no locking)
            currentPhase: (cfg.currentPhase || 'A').toUpperCase(),
            activePhase: (cfg.currentPhase || 'A').toUpperCase(),
            completedPhases: cfg.completedPhases || [],
            _pgOrder: { A: 0, B: 1, C: 1, D: 1, E: 2, F: 3, G: 4, H: 5 },

            pgIdx(phase) {
                let p = (phase || 'A').charAt(0).toUpperCase();
                let idx = this._pgOrder[p];
                return idx !== undefined ? idx : -1;
            },
            currentPgIdx() { return this.pgIdx(this.currentPhase); },
            // isSectionActive now reflects the user-selected tab (activePhase), not just server phase
            isSectionActive(phase) { return this.pgIdx(phase) === this.pgIdx(this.activePhase); },
            isSectionCompleted(phase) { return this.pgIdx(phase) < this.currentPgIdx(); },
            isSectionFuture(phase) { return this.pgIdx(phase) > this.currentPgIdx(); },
            setActivePhase(phase) { this.activePhase = (phase || 'A').charAt(0).toUpperCase(); },

            // ARC-E02: Phase-to-section mapping for navigation
            _phaseToSection: { A: 'sec-2', B: 'sec-3', C: 'sec-3', D: 'sec-3', E: 'sec-4', F: 'sec-6', G: 'sec-7', H: 'sec-6' },
            phaseHasContent(letter) {
                return this.completedPhases && this.completedPhases.indexOf(letter) !== -1;
            },
            scrollToPhaseSection(letter) {
                const target = this._phaseToSection[letter];
                if (!target) return;
                let el = document.getElementById(target);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            },

            // SOL-005: Section expand/collapse + entity counts + phase interpretation callouts
            toggleSection(secId) {
                // Use spread to trigger Alpine reactivity for new keys
                const copy = Object.assign({}, this.expandedSections);
                copy[secId] = !copy[secId];
                this.expandedSections = copy;
                this.activeSection = secId;
            },
            isSectionExpanded(secId) {
                return !!this.expandedSections[secId];
            },
            sectionEntityCount(secId) {
                switch (secId) {
                    case 'sec-1': return (this.drivers.length > 0 || this.goals.length > 0) ? 1 : 0; // summary present
                    case 'sec-2': return this.drivers.length + this.goals.length + this.constraints.length + this.requirements.length;
                    case 'sec-3': return (this.linkedCapabilities || []).length + (this.linkedApplications || []).length + (this.linkedVendorProducts || []).length;
                    case 'sec-4': return (this.linkedApplications || []).length + (this.archimateElements || []).filter(function(e) { return e.layer === 'application' || e.layer === 'technology'; }).length;
                    case 'sec-5': return this.recommendations.length;
                    case 'sec-6': return this.plateaus.length + this.tcoItems.length;
                    case 'sec-7': return this.governanceStatus !== 'draft' ? 1 : 0;
                    case 'sec-8': return this.risks.length + (this.linkedADRs || []).length;
                    case 'sec-9': return this.metrics.length;
                    case 'sec-10': return this.drivers.length + this.goals.length + this.requirements.length + (this.linkedCapabilities || []).length;
                    default: return 0;
                }
            },
            /**
             * SOL-005: Per-phase interpretation callout data.
             * Returns { present: [], missing: [], completePct: N } for a given section.
             */
            phaseInterpretation(secId) {
                const present = [];
                const missing = [];
                let total = 0;
                let filled = 0;
                function check(label, count) {
                    total++;
                    if (count > 0) { filled++; present.push(count + ' ' + label); }
                    else { missing.push(label); }
                }
                switch (secId) {
                    case 'sec-1': // Executive Summary (Phase A)
                        check('description', (cfg.hasDescription ? 1 : 0));
                        break;
                    case 'sec-2': // Strategic Context (Phase A)
                        check('driver' + (this.drivers.length !== 1 ? 's' : ''), this.drivers.length);
                        check('goal' + (this.goals.length !== 1 ? 's' : ''), this.goals.length);
                        check('constraint' + (this.constraints.length !== 1 ? 's' : ''), this.constraints.length);
                        check('requirement' + (this.requirements.length !== 1 ? 's' : ''), this.requirements.length);
                        const stk = cfg.stakeholders || {};
                        const stkCount = (stk.solution_owner ? 1 : 0) + (stk.business_sponsor ? 1 : 0) + (stk.technical_lead ? 1 : 0) + (stk.architecture_lead ? 1 : 0);
                        check('stakeholder' + (stkCount !== 1 ? 's' : ''), stkCount);
                        break;
                    case 'sec-3': // Business Architecture (Phase B)
                        check('capabilit' + ((this.linkedCapabilities || []).length !== 1 ? 'ies' : 'y'), (this.linkedCapabilities || []).length);
                        check('application' + ((this.linkedApplications || []).length !== 1 ? 's' : ''), (this.linkedApplications || []).length);
                        check('vendor product' + ((this.linkedVendorProducts || []).length !== 1 ? 's' : ''), (this.linkedVendorProducts || []).length);
                        check('APQC process' + ((this.linkedAPQCProcesses || []).length !== 1 ? 'es' : ''), (this.linkedAPQCProcesses || []).length);
                        break;
                    case 'sec-4': // Application & Technology (Phases C/D)
                        const appElems = (this.archimateElements || []).filter(function(e) { return e.layer === 'application'; }).length;
                        const techElems = (this.archimateElements || []).filter(function(e) { return e.layer === 'technology'; }).length;
                        check('app element' + (appElems !== 1 ? 's' : ''), appElems);
                        check('tech element' + (techElems !== 1 ? 's' : ''), techElems);
                        check('application' + ((this.linkedApplications || []).length !== 1 ? 's' : ''), (this.linkedApplications || []).length);
                        break;
                    case 'sec-5': // Options & Financial (Phase E)
                        check('option' + (this.recommendations.length !== 1 ? 's' : ''), this.recommendations.length);
                        let selected = this.recommendations.filter(function(r) { return r.is_recommended || r.selected; }).length;
                        check('selected option' + (selected !== 1 ? 's' : ''), selected);
                        check('TCO item' + (this.tcoItems.length !== 1 ? 's' : ''), this.tcoItems.length);
                        check('ADR' + ((this.linkedADRs || []).length !== 1 ? 's' : ''), (this.linkedADRs || []).length);
                        check('quality attribute' + (this.sadQualityAttributes.length !== 1 ? 's' : ''), this.sadQualityAttributes.length);
                        break;
                    case 'sec-6': // Delivery (Phase F)
                        check('plateau' + (this.plateaus.length !== 1 ? 's' : ''), this.plateaus.length);
                        check('metric' + (this.metrics.length !== 1 ? 's' : ''), this.metrics.length);
                        check('TCO item' + (this.tcoItems.length !== 1 ? 's' : ''), this.tcoItems.length);
                        check('investment phase' + (this.sadInvestmentPhases.length !== 1 ? 's' : ''), this.sadInvestmentPhases.length);
                        break;
                    case 'sec-7': // Governance (Phase G)
                        check('ARB submission', this.governanceStatus !== 'draft' ? 1 : 0);
                        check('condition' + ((this.arbConditions || []).length !== 1 ? 's' : ''), (this.arbConditions || []).length);
                        check('governance exception' + (this.sadGovernanceExceptions.length !== 1 ? 's' : ''), this.sadGovernanceExceptions.length);
                        check('compliance mapping' + (this.sadComplianceMappings.length !== 1 ? 's' : ''), this.sadComplianceMappings.length);
                        break;
                    case 'sec-8': // Risks & Decisions
                        check('risk' + (this.risks.length !== 1 ? 's' : ''), this.risks.length);
                        check('ADR' + ((this.linkedADRs || []).length !== 1 ? 's' : ''), (this.linkedADRs || []).length);
                        check('risk snapshot' + (this.sadRiskSnapshots.length !== 1 ? 's' : ''), this.sadRiskSnapshots.length);
                        break;
                    case 'sec-9': // Operational Readiness (Phase H)
                        check('metric' + (this.metrics.length !== 1 ? 's' : ''), this.metrics.length);
                        check('benefit realization' + (this.sadBenefitRealizations.length !== 1 ? 's' : ''), this.sadBenefitRealizations.length);
                        check('lesson' + (this.sadLessonsLearned.length !== 1 ? 's' : '') + ' learned', this.sadLessonsLearned.length);
                        break;
                    case 'sec-10': // Traceability Evidence
                        check('driver' + (this.drivers.length !== 1 ? 's' : ''), this.drivers.length);
                        check('goal' + (this.goals.length !== 1 ? 's' : ''), this.goals.length);
                        check('requirement' + (this.requirements.length !== 1 ? 's' : ''), this.requirements.length);
                        check('capabilit' + ((this.linkedCapabilities || []).length !== 1 ? 'ies' : 'y'), (this.linkedCapabilities || []).length);
                        check('ArchiMate element' + ((this.archimateElements || []).length !== 1 ? 's' : ''), (this.archimateElements || []).length);
                        break;
                }
                return {
                    present: present,
                    missing: missing,
                    completePct: total > 0 ? Math.round((filled / total) * 100) : 0
                };
            },

            /**
             * SOL-005: Cached per-section interpretation data (computed getter).
             * Alpine.js caches getter results per reactive cycle, so this runs once per render
             * instead of 3× per section.
             */
            get phaseSummaries() {
                let self = this;
                let secs = ['sec-1','sec-2','sec-3','sec-4','sec-5','sec-6','sec-7','sec-8','sec-9','sec-10'];
                let result = {};
                for (let i = 0; i < secs.length; i++) {
                    result[secs[i]] = self.phaseInterpretation(secs[i]);
                }
                return result;
            },

            /**
             * SEC-UNI: Lazy canvas init — only runs when section scrolls into view (x-intersect.once).
             * Filters archimateElements by phase-appropriate layer/type for mini-diagrams.
             */
            initSectionCanvas(phaseKey) {
                const filterMap = {
                    'A': function(el) { return el.layer === 'motivation'; },
                    'B': function(el) { return el.layer === 'business'; },
                    'C': function(el) { return el.layer === 'application' || el.layer === 'technology'; },
                    'E': function(el) { return el.layer === 'application'; },
                    'F': function(el) { return el.layer === 'implementation'; },
                    'G': function(el) { return el.layer === 'motivation' && ['Goal','Requirement','Principle','Constraint'].indexOf(el.type) !== -1; },
                    'R': function(el) { return el.layer === 'motivation' && el.type === 'Assessment'; },
                    'H': function(el) { return el.layer === 'motivation' && ['Outcome','Goal','Deliverable'].indexOf(el.type) !== -1; },
                    'T': function(el) { return true; },
                };
                const filterFn = filterMap[phaseKey] || function() { return false; };
                this.sectionCanvasData[phaseKey] = (this.archimateElements || []).filter(filterFn);
            },

            /**
             * BIZBOK: Load a viewpoint diagram into a container element.
             * Fetches from /solutions/<id>/viewpoint-elements?viewpoint=<type>
             * and renders via ComposerRenderer.
             */
            async loadViewpointDiagram(tabKey, viewpointType, containerId) {
                if (!viewpointType || !containerId) return;
                if (this._viewpointDiagrams[tabKey]) return; // already loaded

                let container = document.getElementById(containerId);
                if (!container) return;

                try {
                    let resp = await fetch(this.apiBase + '/viewpoint-elements?viewpoint=' + viewpointType, {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json', 'X-CSRFToken': this.csrfToken }
                    });
                    let data = await resp.json();
                    if (!resp.ok || !data.success) return;

                    if (!data.elements || data.elements.length === 0) {
                        container.innerHTML = '<div class="flex items-center justify-center h-full text-muted-foreground text-sm">' +
                            '<div class="text-center"><p>' + (data.empty_reason || 'No elements for this viewpoint.') + '</p>' +
                            '<p class="mt-1 text-xs">Link ArchiMate elements to populate this diagram.</p></div></div>';
                        return;
                    }

                    // Cap at 30 elements for performance (spec requirement)
                    let elements = data.elements.slice(0, 30);
                    const elementIds = {};
                    elements.forEach(function(e) { elementIds[e.id] = true; });
                    const relationships = (data.relationships || []).filter(function(r) {
                        return elementIds[r.source_id] && elementIds[r.target_id];
                    });

                    // Destroy previous renderer if exists
                    if (this._viewpointRenderers[tabKey]) {
                        this._viewpointRenderers[tabKey].destroy();
                    }

                    if (typeof ComposerRenderer !== 'undefined') {
                        const renderer = ComposerRenderer.create(container, {
                            mode: 'view', width: '100%', height: 350
                        });
                        renderer.loadElements(elements, relationships);
                        renderer.fitToContent();
                        this._viewpointRenderers[tabKey] = renderer;
                    }

                    this._viewpointDiagrams[tabKey] = data;

                    // Show overflow link if elements were capped
                    if (data.elements.length > 30) {
                        const overflow = document.createElement('div');
                        overflow.className = 'text-xs text-muted-foreground text-center mt-2';
                        overflow.textContent = 'Showing 30 of ' + data.elements.length + ' elements. View full diagram in Composer.';
                        container.parentNode.appendChild(overflow);
                    }
                } catch (e) {
                    console.warn('[BIZBOK] viewpoint diagram load failed:', e);
                }
            },

            // Modal state
            activeModal: null,
            editingEntity: null,
            entityType: null,
            deleteTarget: null,

            // Form data per type
            formData: {},
            saving: false,
            syncing: false,
            generatingDraft: false,
            draftBrief: { problem_statement: '', current_state: '', budget_range: '', timeline_months: null, compliance_needs: '', key_stakeholders: '', industry_context: '', technology_preferences: '' },
            draftResult: null,
            draftError: null,

            // ENT-018: live impact summary (updated after every entity CRUD)
            maturityPct: cfg.maturityScore || 0,
            riskSummaryLive: {},
            nextMilestone: '',

            // ENT-005: Architecture variants (cost / timeline / risk)
            generatingVariants: false,
            architectureVariants: [],
            applyingVariantId: null,

            // ENT-058: Options Analysis (TCO aggregation + MCDA scoring)
            optionsAnalysisData: null,
            optionsAnalysisLoading: false,
            mcdaCriteria: [],
            editingMcdaCriteria: false,
            savingCriteria: false,

            // Multi-select picker modal state
            manageModalType: null,
            manageAllItems: [],
            manageSelectedIds: new Set(),
            manageLoading: false,
            manageSaving: false,
            manageFilter: '',
            manageLayerFilter: '',
            linkedApplications: cfg.linkedApplications || [],
            linkedVendorProducts: cfg.linkedVendorProducts || [],
            vendorViewMode: 'list',
            linkedADRs: cfg.linkedADRs || [],
            linkedAPQCProcesses: cfg.linkedAPQCProcesses || [],
            linkedCapabilities: cfg.linkedCapabilities || [],
            linkedRequirements: cfg.linkedRequirements || [],

            csrfToken: (document.querySelector('meta[name="csrf-token"]') || {}).content || '',

            // --- Computed: TCO totals for reactive sidebar ---
            get tcoTotal() {
                let sum = 0;
                for (let i = 0; i < this.tcoItems.length; i++) {
                    sum += parseFloat(this.tcoItems[i].amount) || 0;
                }
                return sum;
            },
            // ENT-007: TCO category breakdown for bar chart
            get tcoCategories() {
                let cats = {};
                for (let i = 0; i < this.tcoItems.length; i++) {
                    let cat = this.tcoItems[i].cost_category || 'Other';
                    cats[cat] = (cats[cat] || 0) + (parseFloat(this.tcoItems[i].amount) || 0);
                }
                let total = this.tcoTotal || 1;
                return Object.entries(cats).map(function([k, v]) {
                    return { label: k, amount: v, pct: Math.round(v / total * 100) };
                }).sort(function(a, b) { return b.amount - a.amount; });
            },
            // ENT-008: Risk heatmap grid (impact × probability)
            get riskHeatmap() {
                let levels = ['low', 'medium', 'high', 'critical'];
                let grid = {};
                for (let i = 0; i < this.risks.length; i++) {
                    let r = this.risks[i];
                    let key = (r.impact || 'medium') + '|' + (r.probability || 'medium');
                    if (!grid[key]) grid[key] = 0;
                    grid[key]++;
                }
                return levels.map(function(imp) {
                    return levels.map(function(prob) {
                        return { impact: imp, probability: prob, count: grid[imp + '|' + prob] || 0 };
                    });
                });
            },
            get vendorComparison() {
                return (this.recommendations || []).map(function(o) {
                    return {
                        id: o.id,
                        name: o.option_name || o.name || 'Unnamed',
                        costScore: o.cost_estimate ? Math.max(0, 100 - Math.round((parseFloat(o.cost_estimate) / 1000000) * 10)) : null,
                        riskLevel: o.risk_level || o.risk || null,
                        maturityNote: o.maturity_level || o.notes || null,
                        recommended: o.is_recommended || (o.rank === 1) || false,
                    };
                });
            },
            get openRiskCount() {
                let count = 0;
                for (let i = 0; i < this.risks.length; i++) {
                    if (this.risks[i].status === 'open') count++;
                }
                return count;
            },
            get metricsMet() {
                let count = 0;
                for (let i = 0; i < this.metrics.length; i++) {
                    if (this.metrics[i].status === 'met') count++;
                }
                return count;
            },
            // CAP-023: Capability maturity roadmap data for Phase F
            get maturityRoadmapData() {
                return this.linkedCapabilities
                    .filter(function(c) { return c.maturity_current != null; })
                    .map(function(c) {
                        const current = parseInt(c.maturity_current, 10) || 0;
                        const target = parseInt(c.maturity_target, 10) || current;
                        return {
                            name: c.capability_name || c.name,
                            domain: c.domain || null,
                            current: current,
                            target: target,
                            gap: Math.max(0, target - current),
                            currentPct: Math.round((current / 5) * 100),
                            targetPct: Math.round((target / 5) * 100)
                        };
                    })
                    .sort(function(a, b) { return b.gap - a.gap; });
            },

            // --- Badge helpers ---
            impactClass(val) {
                if (val === 'critical') return 'bg-destructive/10 text-destructive';
                if (val === 'high') return 'bg-amber-500/10 text-amber-600';
                return 'bg-primary/10 text-primary';
            },
            probabilityClass(val) {
                if (val === 'high') return 'bg-destructive/10 text-destructive';
                return 'bg-primary/10 text-primary';
            },
            riskStatusClass(val) {
                if (val === 'mitigated') return 'bg-emerald-500/10 text-emerald-600';
                if (val === 'accepted') return 'bg-violet-500/10 text-violet-600';
                return 'bg-amber-500/10 text-amber-600';
            },
            metricStatusClass(val) {
                if (val === 'met') return 'bg-emerald-500/10 text-emerald-600';
                if (val === 'at_risk') return 'bg-destructive/10 text-destructive';
                return 'bg-amber-500/10 text-amber-600';
            },
            driverTypeClass(val) {
                if (val === 'external') return 'bg-violet-500/10 text-violet-600';
                if (val === 'technology') return 'bg-primary/10 text-primary';
                if (val === 'stakeholder') return 'bg-amber-500/10 text-amber-600';
                return 'bg-emerald-500/10 text-emerald-600';
            },
            constraintTypeClass(val) {
                if (val === 'budget' || val === 'timeline') return 'bg-destructive/10 text-destructive';
                if (val === 'compliance') return 'bg-amber-500/10 text-amber-600';
                return 'bg-primary/10 text-primary';
            },
            requirementTypeClass(val) {
                if (val === 'functional') return 'bg-primary/10 text-primary';
                if (val === 'quality') return 'bg-violet-500/10 text-violet-600';
                if (val === 'constraint') return 'bg-amber-500/10 text-amber-600';
                return 'bg-primary/10 text-primary';
            },
            optionTypeClass(val) {
                if (val === 'buy') return 'bg-emerald-500/10 text-emerald-600';
                if (val === 'build') return 'bg-primary/10 text-primary';
                if (val === 'reuse') return 'bg-violet-500/10 text-violet-600';
                if (val === 'partner') return 'bg-amber-500/10 text-amber-600';
                if (val === 'hybrid') return 'bg-rose-500/10 text-rose-600';
                return 'bg-primary/10 text-primary';
            },
            get mandatoryReqCount() {
                let count = 0;
                for (let i = 0; i < this.requirements.length; i++) {
                    if (this.requirements[i].is_mandatory) count++;
                }
                return count;
            },
            get topOption() {
                if (this.recommendations.length === 0) return null;
                let best = this.recommendations[0];
                for (let i = 1; i < this.recommendations.length; i++) {
                    if ((this.recommendations[i].rank || 999) < (best.rank || 999)) best = this.recommendations[i];
                }
                return best;
            },

            // --- ArchiMate sync ---
            async syncArchimate() {
                this.syncing = true;
                try {
                    let resp = await fetch(this.apiBase + '/sync-archimate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                    });
                    let data = await resp.json();
                    if (data.success) {
                        window.location.reload();
                    } else {
                        Platform.toast.error('Sync failed: ' + (data.error || 'Unknown error'));
                    }
                } catch (err) {
                    console.error('[solutionDetail] sync error:', err);
                    Platform.toast.error('Sync failed. Check console for details.');
                }
                this.syncing = false;
            },

            // openManageModal, closeManageModal: moved to detail-phase-crud.js
            get manageFilteredItems() {
                let q = (this.manageFilter || '').toLowerCase();
                let layer = (this.manageLayerFilter || '').toLowerCase();
                let items = this.manageAllItems;
                if (layer) {
                    items = items.filter(function(item) {
                        return (item.layer || '').toLowerCase() === layer;
                    });
                }
                if (!q) return items;
                return items.filter(function(item) {
                    return (item.name || '').toLowerCase().indexOf(q) >= 0 ||
                           (item.sub || '').toLowerCase().indexOf(q) >= 0;
                });
            },
            get manageModalTitle() {
                let titles = {
                    application: 'Applications',
                    vendor_product: 'Vendor Products',
                    adr: 'Architecture Decisions',
                    apqc_process: 'APQC Processes',
                    archimate_element: 'ArchiMate Repository Elements',
                };
                return 'Manage ' + (titles[this.manageModalType] || '');
            },
            // isManageSelected, toggleManageItem, saveManageModal, unlinkEntity: moved to detail-phase-crud.js

            async advancePhase(force) {
                try {
                    let resp = await fetch(this.apiBase + '/advance-phase', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ force: !!force }),
                    });
                    let data = await resp.json();
                    if (data.success || data.completed) {
                        window.location.reload();
                    } else {
                        let errors = (data.errors || []);
                        let warnings = (data.warnings || []);
                        if (errors.length > 0) {
                            // Show blocking errors — user must fix before advancing
                            let errMsg = '⛔ Phase gate requirements not met:\n\n' + errors.map(e => '• ' + e).join('\n');
                            if (warnings.length > 0) {
                                errMsg += '\n\n⚠️ Warnings:\n' + warnings.map(w => '• ' + w).join('\n');
                            }
                            if (window.Platform && Platform.toast && Platform.toast.error) {
                                Platform.toast.error('Phase gate not met: ' + errors[0]);
                            }
                            Platform.toast.info(errMsg);
                        } else if (warnings.length > 0) {
                            // Only warnings — allow force advance
                            let warnMsg = '⚠️ Phase gate warnings:\n\n' + warnings.map(w => '• ' + w).join('\n') + '\n\nAdvance anyway?';
                            if ((await Platform.modal.confirm(warnMsg))) {
                                this.advancePhase(true);
                            }
                        } else {
                            let msg = data.message || 'Phase advance failed.';
                            if (window.Platform && Platform.toast && Platform.toast.error) {
                                Platform.toast.error(msg);
                            } else {
                                Platform.toast.info(msg);
                            }
                        }
                    }
                } catch (err) {
                    console.error('[solutionDetail] advance error:', err);
                }
            },

            async submitToArb() {
                if (this.submittingArb) return;
                if (this.has_ai_generated_content) {
                    this.pendingArbAction = 'submit';
                    this.showArbAiConfirmModal = true;
                    return;
                }
                if (!(await Platform.modal.confirm('Submit this solution for Architecture Review Board review?'))) return;
                this.doSubmitToArb(false);
            },
            async doSubmitToArb(aiContentReviewed) {
                if (this.submittingArb) return;
                this.submittingArb = true;
                try {
                    let body = {};
                    if (aiContentReviewed) body.ai_content_reviewed = true;
                    if (this.require_second_review && this.second_reviewer_id) body.second_reviewer_id = this.second_reviewer_id;
                    // ENH-008: Include cost_source when solution has estimated cost
                    if (this.costSource) body.cost_source = this.costSource;
                    // ENH-009: Include pre-submission checklist snapshot
                    body.arb_checklist = this.arbChecklist.map(function(item) { return { label: item.label, checked: item.checked }; });
                    let resp = await fetch(this.apiBase + '/submit-for-arb', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: Object.keys(body).length ? JSON.stringify(body) : undefined
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.governanceStatus = data.governance_status || 'arb_review';
                        this.canSubmitArb = false;
                    } else {
                        if (data.requires_ai_review) {
                            this.has_ai_generated_content = true;
                            this.pendingArbAction = 'submit';
                            this.showArbAiConfirmModal = true;
                        } else if (data.requires_cost_source) {
                            // ENH-008: Prompt user to declare cost source
                            let src = prompt('Solution has a cost estimate. Declare cost source:\n- Type "tco_engine" if cost comes from TCO calculation\n- Type "manual_override" if entered manually');
                            if (src === 'tco_engine' || src === 'manual_override') {
                                this.costSource = src;
                                this.doSubmitToArb(aiContentReviewed);
                                return;
                            } else {
                                Platform.toast.info('ARB submission requires cost_source to be "tco_engine" or "manual_override".');
                            }
                        } else {
                            Platform.toast.error(data.error || 'Submission failed.');
                        }
                    }
                } catch (err) {
                    console.error('[solutionDetail] ARB submit error:', err);
                    Platform.toast.error('Failed to submit to ARB. Check console for details.');
                }
                this.submittingArb = false;
            },
            arbChecklistComplete() {
                // ENH-009: All checklist items must be checked before ARB submit
                return this.arbChecklist.every(function(item) { return item.checked; });
            },
            confirmArbAiReviewedAndSubmit() {
                this.showArbAiConfirmModal = false;
                if (this.pendingArbAction === 'resubmit') {
                    this.pendingArbAction = '';
                    this.confirmResubmit();
                } else {
                    this.pendingArbAction = '';
                    this.doSubmitToArb(true);
                }
            },

            async submitOutcome() {
                if (this.outcomeSubmitting || !this.outcomeForm.go_live_date) return;
                this.outcomeSubmitting = true;
                let cfg = window.__SOLUTION_CONFIG__ || {};
                let base = (cfg.governanceApiBase || '/api') + '/solutions/' + (cfg.solutionId || this.apiBase.split('/').filter(Boolean).pop());
                try {
                    let resp = await fetch(base + '/record-outcome', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({
                            go_live_date: this.outcomeForm.go_live_date,
                            actual_duration_weeks: this.outcomeForm.actual_duration_weeks ? parseFloat(this.outcomeForm.actual_duration_weeks) : null,
                            actual_cost_usd: this.outcomeForm.actual_cost_usd ? parseFloat(this.outcomeForm.actual_cost_usd) : null,
                            business_value_realized: this.outcomeForm.business_value_realized || '',
                            lessons_learned: this.outcomeForm.lessons_learned || '',
                            what_went_well: this.outcomeForm.what_went_well || '',
                            what_to_improve: this.outcomeForm.what_to_improve || ''
                        })
                    });
                    let data = await resp.json();
                    if (data.success) {
                        if (window.Platform && Platform.toast && Platform.toast.success) Platform.toast.success('Outcome recorded.');
                        this.outcomeForm = { go_live_date: '', actual_duration_weeks: '', actual_cost_usd: '', business_value_realized: '', lessons_learned: '', what_went_well: '', what_to_improve: '' };
                    } else { Platform.toast.error(data.error || 'Failed to save outcome.'); }
                } catch (err) { console.error(err); Platform.toast.error('Failed to save outcome.'); }
                this.outcomeSubmitting = false;
            },

            async loadActivity() {
                this.activityLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/activity', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    let data = await resp.json();
                    this.activityList = (data && data.activities) || [];
                } catch (e) { this.activityList = []; }
                this.activityLoading = false;
            },

            async loadGaps() {
                this.gapsLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/gaps', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    let data = await resp.json();
                    this.gaps = (data && data.gaps) || [];
                } catch (e) { this.gaps = []; }
                this.gapsLoading = false;
            },


            async loadLinkedRequirements() {
                try {
                    let resp = await fetch(this.apiBase + '/all-requirements', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    let data = await resp.json();
                    this.linkedRequirements = (data && data.items) || [];
                } catch (e) { this.linkedRequirements = []; }
            },

            get traceabilityPreviewRows() {
                let rows = (this.traceabilityData && this.traceabilityData.rows) || [];
                return rows.slice(0, 5);
            },

            traceabilitySummaryValue(key) {
                let summary = (this.traceabilityData && this.traceabilityData.summary) || {};
                let value = summary[key];
                return value == null ? 0 : value;
            },

            formatTraceabilityCell(value) {
                if (value == null || value === '') return '\u2014';
                if (typeof value === 'string' || typeof value === 'number') return String(value);
                return value.name || value.element_name || value.capability_name || value.vendor_name || value.title || '\u2014';
            },

            async loadTraceability(force = false) {
                if (this.traceabilityLoading || (this.traceabilityLoaded && !force)) return;
                this.traceabilityLoading = true;
                this.traceabilityError = '';
                try {
                    let resp = await fetch(this.apiBase + '/traceability?format=json', {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json', 'X-CSRFToken': this.csrfToken }
                    });
                    if (!resp.ok) {
                        throw new Error('Unable to load traceability evidence (HTTP ' + resp.status + ')');
                    }
                    let payload = await resp.json();
                    if (payload.success === false) {
                        throw new Error(payload.error || 'Unable to load traceability evidence');
                    }
                    this.traceabilityData = payload.data || payload;
                    this.traceabilityLoaded = true;
                } catch (e) {
                    console.warn('[CEV-001] traceability fetch failed:', e);
                    this.traceabilityData = null;
                    this.traceabilityError = e && e.message ? e.message : 'Unable to load traceability evidence';
                } finally {
                    this.traceabilityLoading = false;
                }
            },

            jumpToTraceability() {
                this.loadTraceability(true);
                let panel = document.getElementById('solution-traceability-panel');
                if (panel && typeof panel.scrollIntoView === 'function') {
                    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            },

            formatLayerName(layer) {
                if (!layer) return 'Unknown';
                return String(layer).charAt(0).toUpperCase() + String(layer).slice(1);
            },

            viewpointLayerGroups() {
                let grouped = (this.viewpointWorkspace && this.viewpointWorkspace.grouped_elements) || {};
                let groups = [];
                let order = this._layerOrder || [];
                for (let i = 0; i < order.length; i++) {
                    let layer = order[i];
                    if (grouped[layer] && grouped[layer].length > 0) {
                        groups.push({ layer: layer, elements: grouped[layer] });
                    }
                }
                Object.keys(grouped).forEach(function(layer) {
                    if (order.indexOf(layer) === -1 && grouped[layer] && grouped[layer].length > 0) {
                        groups.push({ layer: layer, elements: grouped[layer] });
                    }
                });
                return groups;
            },

            async loadViewpoint(phase, force = false) {
                let phaseUpper = (phase || 'C').toString().toUpperCase();
                this.viewpointActivePhase = phaseUpper;
                if (
                    this.viewpointWorkspace &&
                    this.viewpointWorkspace.phase === phaseUpper &&
                    this.viewpointLoadedPhases[phaseUpper] &&
                    !force
                ) {
                    return;
                }

                this.viewpointLoading = true;
                this.viewpointError = '';
                try {
                    let resp = await fetch(this.apiBase + '/generate-viewpoint/' + phaseUpper, {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json', 'X-CSRFToken': this.csrfToken }
                    });
                    let data = await resp.json();
                    if (!resp.ok || data.success === false) {
                        throw new Error(data.error || ('Unable to load Phase ' + phaseUpper + ' viewpoint'));
                    }
                    this.viewpointWorkspace = data;
                    this.viewpointLoadedPhases = Object.assign({}, this.viewpointLoadedPhases, { [phaseUpper]: true });
                } catch (e) {
                    console.warn('[SAD-015] viewpoint fetch failed:', e);
                    this.viewpointWorkspace = {
                        phase: phaseUpper,
                        viewpoint_name: 'Phase ' + phaseUpper + ' Viewpoint',
                        layers: [],
                        grouped_elements: {},
                        elements: [],
                        count: 0,
                        empty_reason: 'Unable to load viewpoint data right now.'
                    };
                    this.viewpointError = e && e.message ? e.message : 'Unable to load viewpoint data';
                } finally {
                    this.viewpointLoading = false;
                }
            },

            async loadAdvancedTco() {
                if (this.advancedTcoLoading || this.advancedTcoLoaded) return;
                this.advancedTcoLoading = true;
                try {
                    const resp = await fetch('/api/advanced-tco/calculate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken},
                        body: JSON.stringify({solution_id: window.__SOLUTION_CONFIG__.solutionId})
                    });
                    const data = await resp.json();
                    if (data.success !== false) {
                        this.advancedTco = data;
                        this.advancedTcoLoaded = true;
                    }
                } catch(e) { console.warn('Advanced TCO fetch failed', e); }
                finally { this.advancedTcoLoading = false; }
            },

            // SAD-002: Predictive Analytics (cost forecasts)
            async loadCostForecasts() {
                if (this.costForecastsLoading || this.costForecastsLoaded) return;
                this.costForecastsLoading = true;
                try {
                    let resp = await fetch('/api/solutions/' + cfg.solutionId + '/suggestions/costs', {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (resp.ok) {
                        let data = await resp.json();
                        if (data.suggestion) {
                            this.costForecasts = data;
                        }
                    }
                } catch (e) {
                    console.warn('[solutionDetail] Cost forecasts fetch failed:', e);
                } finally {
                    this.costForecastsLoading = false;
                    this.costForecastsLoaded = true;
                }
            },

            async loadComplianceGap() {
                if (this.complianceGapLoading || this.complianceGapLoaded) return;
                this.complianceGapLoading = true;
                try {
                    const resp = await fetch('/strategic/api/check-compliance', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken},
                        body: JSON.stringify({solution_id: window.__SOLUTION_CONFIG__.solutionId})
                    });
                    const data = await resp.json();
                    if (data.success !== false) {
                        this.complianceGap = data;
                        this.complianceGapLoaded = true;
                    }
                } catch(e) { console.warn('Compliance gap fetch failed', e); }
                finally { this.complianceGapLoading = false; }
            },

            async loadVersionHistory() {
                if (this.versionHistoryLoading || this.versionHistoryLoaded) return;
                this.versionHistoryLoading = true;
                try {
                    const resp = await fetch(`${this.apiBase}/versions`, {
                        headers: {'X-CSRFToken': this.csrfToken}
                    });
                    const data = await resp.json();
                    if (data.versions) {
                        this.versionHistory = data.versions;
                        this.versionHistoryLoaded = true;
                    }
                } catch(e) { console.warn('Version history fetch failed', e); }
                finally { this.versionHistoryLoading = false; }
            },

            // SA-008: Load completeness report
            async loadCompleteness() {
                if (this.completenessLoading || this.completenessLoaded) return;
                this.completenessLoading = true;
                try {
                    let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                    let resp = await fetch('/solutions/api/' + sid + '/completeness', {
                        headers: {'Accept': 'application/json'}
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.completenessReport = data;
                        this.completenessLoaded = true;
                    }
                } catch(e) { console.warn('Completeness check failed', e); }
                finally { this.completenessLoading = false; }
            },

            // PLT-008: Load connection suggestions
            async loadSuggestions() {
                if (this.suggestionsLoading) return;
                this.suggestionsLoading = true;
                this.suggestionsError = '';
                this.suggestionsData = null;
                try {
                    let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                    let resp = await fetch('/solutions/' + sid + '/suggest-connections', {
                        headers: {'Accept': 'application/json'}
                    });
                    if (!resp.ok) {
                        let errData = await resp.json().catch(() => ({}));
                        this.suggestionsError = errData.error || 'Failed to load suggestions (HTTP ' + resp.status + ')';
                        return;
                    }
                    let data = await resp.json();
                    this.suggestionsData = data.suggestions || {};
                    // Check if all categories are empty
                    let total = (this.suggestionsData.applications || []).length +
                                (this.suggestionsData.capabilities || []).length +
                                (this.suggestionsData.vendors || []).length +
                                (this.suggestionsData.archimate || []).length;
                    if (total === 0) {
                        this.suggestionsError = 'No suggestions found — this solution may already be well-connected, or try adding more detail to the description.';
                    }
                } catch(e) {
                    this.suggestionsError = 'Network error: ' + e.message;
                } finally {
                    this.suggestionsLoading = false;
                }
            },

            openSuggestionsPanel() {
                this.suggestionsOpen = true;
                if (!this.suggestionsData && !this.suggestionsLoading) {
                    this.loadSuggestions();
                }
            },

            async linkSuggestion(entityType, entityId, extraData) {
                let key = entityType + '_' + entityId;
                if (this.suggestionsLinking[key]) return;
                this.suggestionsLinking[key] = true;
                this.suggestionsLinking = { ...this.suggestionsLinking };  // trigger reactivity
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                let url = '';
                let body = {};
                let method = 'POST';
                try {
                    if (entityType === 'application') {
                        url = '/solutions/' + sid + '/link-application';
                        body = { application_id: entityId };
                    } else if (entityType === 'capability') {
                        url = '/solutions/' + sid + '/link-capability';
                        body = { capability_id: entityId };
                    } else if (entityType === 'vendor_product') {
                        url = '/solutions/' + sid + '/link-vendor-product';
                        body = { vendor_product_id: entityId };
                    } else if (entityType === 'archimate') {
                        url = '/solutions/' + sid + '/link-archimate-element';
                        body = {
                            element_id: entityId,
                            layer_type: (extraData && extraData.layer) || 'application',
                            element_name: (extraData && extraData.name) || ''
                        };
                    }
                    let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                    let headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
                    if (csrfMeta) headers['X-CSRFToken'] = csrfMeta.content;
                    let resp = await fetch(url, { method: method, headers: headers, body: JSON.stringify(body) });
                    if (resp.ok) {
                        // Remove from suggestions list
                        if (this.suggestionsData) {
                            let catKey = entityType === 'application' ? 'applications' :
                                         entityType === 'capability' ? 'capabilities' :
                                         entityType === 'vendor_product' ? 'vendors' : 'archimate';
                            this.suggestionsData[catKey] = (this.suggestionsData[catKey] || []).filter(s => s.id !== entityId);
                        }
                    }
                } catch(e) {
                    console.warn('Failed to link suggestion', e);
                } finally {
                    delete this.suggestionsLinking[key];
                    this.suggestionsLinking = { ...this.suggestionsLinking };
                }
            },

            // SA-009: Load ADM deliverable checklists for this solution
            async loadSolutionDeliverables() {
                if (this.solDeliverablesLoading || this.solDeliverablesLoaded) return;
                this.solDeliverablesLoading = true;
                try {
                    let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                    let resp = await fetch('/solutions/api/' + sid + '/deliverables', {
                        headers: {'Accept': 'application/json'}
                    });
                    let data = await resp.json();
                    if (data.success && data.phases) {
                        this.solDeliverableData = data.phases;
                        // Build ordered phase list (only phases with deliverables)
                        let phases = ['A','B','C','D','E','F','G','H','Requirements'];
                        let active = [];
                        for (let i = 0; i < phases.length; i++) {
                            if (data.phases[phases[i]] && data.phases[phases[i]].total > 0) {
                                active.push(phases[i]);
                            }
                        }
                        this.solDeliverablePhases = active;
                        this.solDeliverablesLoaded = true;
                    }
                } catch(e) { console.warn('Solution deliverables fetch failed', e); }
                finally { this.solDeliverablesLoading = false; }
            },

            // SA-009: Toggle a deliverable check for this solution
            async toggleSolutionDeliverable(deliverableId, phaseKey, checked) {
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                try {
                    let resp = await fetch('/solutions/api/' + sid + '/deliverables/' + deliverableId + '/check', {
                        method: 'PATCH',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken},
                        body: JSON.stringify({checked: checked})
                    });
                    let data = await resp.json();
                    if (data.success && this.solDeliverableData[phaseKey]) {
                        // Update local state
                        let items = this.solDeliverableData[phaseKey].deliverables;
                        for (let i = 0; i < items.length; i++) {
                            if (items[i].id === deliverableId) {
                                items[i].checked = checked;
                                items[i].check_id = data.check ? data.check.id : items[i].check_id;
                                break;
                            }
                        }
                        // Recount
                        let count = 0;
                        for (let j = 0; j < items.length; j++) { if (items[j].checked) count++; }
                        this.solDeliverableData[phaseKey].checked = count;
                    }
                } catch(e) { console.warn('Toggle deliverable failed', e); }
            },

            async init() {
                /* Auto-expand sections + init canvases when tab changes */
                let self = this;
                this.$watch('activeTab', function(newTab) {
                    let secs = self._tabSections[newTab] || [];
                    secs.forEach(function(secId) { self.expandedSections[secId] = true; });
                    self.expandedSections = Object.assign({}, self.expandedSections);
                    let phaseMap = {'sec-1':'A_exec','sec-2':'A','sec-3':'B','sec-4':'C','sec-5':'E','sec-6':'F','sec-7':'G','sec-8':'R','sec-9':'H','sec-10':'T'};
                    secs.forEach(function(s) { self.initSectionCanvas(phaseMap[s] || 'A'); });
                    // FRAG-005: Lazy-load strategic analysis when governance tab shown
                    if (newTab === 'governance') {
                        self.loadStrategicRiskAnalysis();
                        self.loadStrategicInvestment();
                    }
                    if (newTab === 'infosys') {
                        self.loadStrategicDependency();
                        self.loadStrategicTechnology();
                    }
                    // BIZBOK: Load viewpoint diagram for the active tab
                    const vpType = self._tabViewpoints[newTab];
                    if (vpType) {
                        self.loadViewpointDiagram(newTab, vpType, 'viewpoint-diagram-' + newTab);
                    }
                });
                this.loadGaps();
                this.loadWorkflowDefinitions();
                this.loadCapabilityMappings();
                this.loadLessonsLearned();
                this.loadSolutionOptions();
                this.loadTraceability();
                this.loadViewpoint(this.viewpointActivePhase);
                this.loadLinkedRequirements();
                this.loadLinkedArchimateElements();
                this.loadLinkedCapabilities();
                this.loadLinkedVendorProducts();
                this.loadLinkedAPQCProcesses();
                this.loadLinkedApplications();
                this.loadNextActions();
                // SAD-08: Load AI suggestion endpoints (vendors, costs, risks, archimate)
                if (this.loadAIInsights) this.loadAIInsights();
                this.loadScratchpad();
                this._initSectionObserver();
                // BIZBOK: Load viewpoint diagram for initial active tab
                const initVp = this._tabViewpoints[this.activeTab];
                if (initVp) {
                    this.loadViewpointDiagram(this.activeTab, initVp, 'viewpoint-diagram-' + this.activeTab);
                }
                // CAP-015: Restore staged ArchiMate elements from localStorage
                if (this._restoreStagedElements) {
                    this._restoreStagedElements();
                }
                // Register lightweight toast for link feedback
                window.__archieToast = function(msg) {
                    let el = document.createElement('div');
                    el.className = 'fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg bg-foreground text-background text-sm font-medium shadow-lg transition-all';
                    el.style.opacity = '1';
                    el.textContent = msg;
                    document.body.appendChild(el);
                    setTimeout(function() { el.style.opacity = '0'; }, 2000);
                    setTimeout(function() { el.remove(); }, 2500);
                };
            },
            async loadNextActions() {
                this.nextActionsLoading = true;
                this.nextActionsError = '';
                try {
                    let resp = await fetch('/api/solutions/' + cfg.solutionId + '/suggestions/next-actions', {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (!resp.ok) {
                        throw new Error('Unable to load next actions (HTTP ' + resp.status + ')');
                    }
                    const ct = resp.headers.get('content-type') || '';
                    if (ct.indexOf('application/json') === -1) {
                        throw new Error('No suggestions available');
                    }
                    let data = await resp.json();
                    this.nextActions = Array.isArray(data.next_actions) ? data.next_actions : [];
                } catch (e) {
                    this.nextActionsError = e && e.message ? e.message : 'Unable to load next actions';
                    this.nextActions = [];
                } finally {
                    this.nextActionsLoading = false;
                }
            },
            // SAD-019: Related solutions
            async loadRelatedSolutions() {
                if (this.relatedSolutionsLoading || this.relatedSolutionsLoaded) return;
                this.relatedSolutionsLoading = true;
                try {
                    let resp = await fetch(base + '/related-solutions', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    if (resp.ok) {
                        let data = await resp.json();
                        this.relatedSolutions = Array.isArray(data.related) ? data.related : [];
                    }
                } catch (e) {
                    console.error('[solutionDetail] related solutions load error:', e);
                } finally {
                    this.relatedSolutionsLoading = false;
                    this.relatedSolutionsLoaded = true;
                }
            },
            // SAD-BOOTSTRAP: Generate motivation layer content for empty solutions
            async bootstrapSolutionContent() {
                if (this.bootstrapLoading) return;
                this.bootstrapLoading = true;
                try {
                    let csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] || '';
                    let headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
                    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
                    let resp = await fetch(base + '/bootstrap', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: headers,
                        body: JSON.stringify({}),
                    });
                    let data = await resp.json();
                    if (data.success) {
                        // Reload the page to show generated content
                        window.location.reload();
                    } else {
                        Platform.toast.error(data.error || 'Generation failed. Please try again.');
                    }
                } catch (e) {
                    console.error('[solutionDetail] bootstrap error:', e);
                    Platform.toast.error('Content generation failed. Please check your connection and try again.');
                } finally {
                    this.bootstrapLoading = false;
                }
            },
            // SMART-DEFAULTS: NON-LLM smart population from real data
            async previewSmartDefaults() {
                if (this.smartDefaultsLoading) return;
                this.smartDefaultsLoading = true;
                this.smartDefaultsError = null;
                try {
                    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    let resp = await fetch('/api/solutions/' + window.__SOLUTION_CONFIG__.solutionId + '/smart-defaults', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ dry_run: true }),
                    });
                    let data = await resp.json();
                    if (data.error) {
                        this.smartDefaultsError = data.error;
                    } else {
                        // Fix 2: Add selected=true to each item for per-item checkboxes
                        let preview = data.defaults;
                        ['capabilities', 'applications', 'vendor_products', 'drivers', 'goals', 'constraints'].forEach(function(key) {
                            (preview[key] || []).forEach(function(item) { item.selected = true; });
                        });
                        this.smartDefaultsPreview = preview;
                    }
                } catch (e) {
                    this.smartDefaultsError = e.message || 'Failed to load suggestions';
                } finally {
                    this.smartDefaultsLoading = false;
                    this.$nextTick(function() { if (typeof lucide !== 'undefined') lucide.createIcons(); });
                }
            },

            // GUIDED WIZARD methods (Fix 4: persist step in sessionStorage)
            wizardNext() {
                if (this.wizardStep < 4) {
                    this.wizardStep++;
                    try { sessionStorage.setItem('wizard_step_' + window.__SOLUTION_CONFIG__.solutionId, this.wizardStep); } catch(e) {}
                }
            },
            wizardPrev() {
                if (this.wizardStep > 1) {
                    this.wizardStep--;
                    try { sessionStorage.setItem('wizard_step_' + window.__SOLUTION_CONFIG__.solutionId, this.wizardStep); } catch(e) {}
                }
            },
            wizardDismiss() {
                this.wizardActive = false;
                this.wizardDismissed = true;
                try {
                    sessionStorage.setItem('wizard_dismissed_' + window.__SOLUTION_CONFIG__.solutionId, '1');
                    sessionStorage.removeItem('wizard_step_' + window.__SOLUTION_CONFIG__.solutionId);
                } catch(e) {}
            },
            wizardShouldShow() {
                if (this.wizardDismissed) return false;
                try { if (sessionStorage.getItem('wizard_dismissed_' + window.__SOLUTION_CONFIG__.solutionId)) return false; } catch(e) {}
                // Restore wizard step from sessionStorage (Fix 4)
                try {
                    const savedStep = sessionStorage.getItem('wizard_step_' + window.__SOLUTION_CONFIG__.solutionId);
                    if (savedStep) this.wizardStep = parseInt(savedStep, 10) || 1;
                } catch(e) {}
                return this.maturityScore < 50;
            },

            async applySmartDefaults() {
                if (this.smartDefaultsLoading) return;
                this.smartDefaultsLoading = true;
                this.smartDefaultsError = null;
                try {
                    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    // Fix 2: Build selected map — only send checked items
                    let preview = this.smartDefaultsPreview;
                    let selected = {};
                    selected.capabilities = (preview.capabilities || []).filter(function(i) { return i.selected; }).map(function(i) { return i.id; });
                    selected.applications = (preview.applications || []).filter(function(i) { return i.selected; }).map(function(i) { return i.id; });
                    selected.vendor_products = (preview.vendor_products || []).filter(function(i) { return i.selected; }).map(function(i) { return i.id; });
                    selected.drivers = (preview.drivers || []).filter(function(i) { return i.selected; }).map(function(i) { return i.name; });
                    selected.goals = (preview.goals || []).filter(function(i) { return i.selected; }).map(function(i) { return i.name; });
                    selected.constraints = (preview.constraints || []).filter(function(i) { return i.selected; }).map(function(i) { return i.name; });

                    let resp = await fetch('/api/solutions/' + window.__SOLUTION_CONFIG__.solutionId + '/smart-defaults', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ dry_run: false, selected: selected }),
                    });
                    let data = await resp.json();
                    if (data.error) {
                        this.smartDefaultsError = data.error;
                    } else {
                        // Fix 3: Show summary instead of immediately reloading
                        this.smartDefaultsDone = true;
                        this.smartDefaultsResult = data.created;
                        this.smartDefaultsCreatedIds = data.created_ids;
                        // Fix 4: If wizard is active, advance to step 2 instead of reload
                        if (this.wizardActive && this.wizardStep === 1) {
                            this.wizardStep = 2;
                        }
                    }
                } catch (e) {
                    this.smartDefaultsError = e.message || 'Failed to apply defaults';
                } finally {
                    this.smartDefaultsLoading = false;
                    this.$nextTick(function() { if (typeof lucide !== 'undefined') lucide.createIcons(); });
                }
            },

            reloadAfterSmartDefaults() {
                window.location.reload();
            },

            async revertSmartDefaults() {
                if (!this.smartDefaultsCreatedIds) return;
                this.smartDefaultsLoading = true;
                try {
                    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    let resp = await fetch('/api/solutions/' + window.__SOLUTION_CONFIG__.solutionId + '/revert-smart-defaults', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ created_ids: this.smartDefaultsCreatedIds }),
                    });
                    let data = await resp.json();
                    if (data.error) {
                        this.smartDefaultsError = data.error;
                    } else {
                        this.smartDefaultsDone = false;
                        this.smartDefaultsResult = null;
                        this.smartDefaultsCreatedIds = null;
                        this.smartDefaultsPreview = null;
                        window.location.reload();
                    }
                } catch (e) {
                    this.smartDefaultsError = e.message || 'Failed to revert';
                } finally {
                    this.smartDefaultsLoading = false;
                }
            },

            // BPP-014: Phase generation (preview → confirm → reload)
            async generatePhase(phase) {
                this.generateLoading = phase;
                this.generatePreview = null;
                this.generateError = null;
                try {
                    let sid = window.__SOLUTION_CONFIG__.solutionId;
                    let resp = await fetch("/api/solutions/" + sid + "/generate-phase", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({phase: phase, dry_run: true}),
                    });
                    if (!resp.ok) {
                        let err = await resp.json();
                        this.generateError = err.error || "Preview failed";
                        return;
                    }
                    this.generatePreview = await resp.json();
                } catch (e) {
                    this.generateError = e.message || "Unknown error";
                } finally {
                    this.generateLoading = null;
                    this.$nextTick(function () {
                        if (typeof lucide !== "undefined") lucide.createIcons();
                    });
                }
            },

            async confirmGenerate() {
                if (!this.generatePreview) return;
                let phase = this.generatePreview.phase;
                this.generateLoading = phase;
                try {
                    let sid = window.__SOLUTION_CONFIG__.solutionId;
                    let resp = await fetch("/api/solutions/" + sid + "/generate-phase", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({phase: phase, dry_run: false}),
                    });
                    if (!resp.ok) {
                        let err = await resp.json();
                        this.generateError = err.error || "Generation failed";
                        return;
                    }
                    this.generatePreview = null;
                    window.location.reload();
                } catch (e) {
                    this.generateError = e.message || "Unknown error";
                } finally {
                    this.generateLoading = null;
                }
            },

            cancelGenerate() {
                this.generatePreview = null;
                this.generateError = null;
            },

            // ARC-E04: Scratchpad methods
            async loadScratchpad() {
                try {
                    let resp = await fetch(base + '/scratchpad', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    if (resp.ok) {
                        let data = await resp.json();
                        this.scratchpadItems = Array.isArray(data.items) ? data.items : [];
                    }
                } catch (e) {
                    console.error('[solutionDetail] scratchpad load error:', e);
                }
            },
            async promoteScratchpadItem(itemId) {
                try {
                    let resp = await fetch(base + '/scratchpad/' + itemId + '/promote', {
                        method: 'POST', credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.content || '' }
                    });
                    if (resp.ok) {
                        this.scratchpadItems = this.scratchpadItems.filter(function(i) { return i.id !== itemId; });
                    }
                } catch (e) {
                    console.error('[solutionDetail] scratchpad promote error:', e);
                }
            },
            async discardScratchpadItem(itemId) {
                try {
                    let resp = await fetch(base + '/scratchpad/' + itemId, {
                        method: 'DELETE', credentials: 'same-origin',
                        headers: { 'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.content || '' }
                    });
                    if (resp.ok) {
                        this.scratchpadItems = this.scratchpadItems.filter(function(i) { return i.id !== itemId; });
                    }
                } catch (e) {
                    console.error('[solutionDetail] scratchpad discard error:', e);
                }
            },
            _initSectionObserver() {
                let self = this;
                let sections = document.querySelectorAll('section[id^="sec-"]');
                if (!sections.length) return;
                // Sections scroll inside <main>, so use it as the observer root
                let scrollRoot = document.querySelector('main.flex-1') || document.querySelector('main');
                let observer = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting) {
                            self.activeSection = entry.target.id;
                        }
                    });
                }, { root: scrollRoot, rootMargin: '-10% 0px -60% 0px', threshold: 0 });
                sections.forEach(function(sec) { observer.observe(sec); });
            },
            onCommentInput(sectionKey) {
                let draft = (this.commentDrafts && this.commentDrafts[sectionKey]) || '';
                let atIdx = draft.lastIndexOf('@');
                if (atIdx === -1) { this.mentionOpen = false; return; }
                let after = draft.slice(atIdx + 1);
                let space = after.indexOf(' ');
                let query = space === -1 ? after : after.slice(0, space);
                if (query.length < 1) { this.mentionUsers = []; this.mentionOpen = true; this.mentionSectionKey = sectionKey; return; }
                this.mentionSectionKey = sectionKey;
                this.mentionQuery = query;
                let base = this.apiBase.replace(/\/\d+$/, '');
                fetch(base + '/users?search=' + encodeURIComponent(query), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                    .then(function(r) { return r.json(); })
                    .then(function(d) { this.mentionUsers = (d && d.users) || []; this.mentionOpen = true; }.bind(this))
                    .catch(function() { this.mentionUsers = []; }.bind(this));
            },
            selectMention(sectionKey, user) {
                let name = (user && (user.name || user.email)) || '';
                if (!name) return;
                let draft = (this.commentDrafts && this.commentDrafts[sectionKey]) || '';
                let atIdx = draft.lastIndexOf('@');
                let before = atIdx >= 0 ? draft.slice(0, atIdx) : draft;
                let after = draft.slice(atIdx + 1);
                let space = after.indexOf(' ');
                let rest = space === -1 ? '' : after.slice(space);
                if (!this.commentDrafts) this.commentDrafts = {};
                this.commentDrafts[sectionKey] = before + '@' + name + (rest ? ' ' + rest : '');
                this.mentionOpen = false;
                this.mentionUsers = [];
            },

            async saveAsTemplate() {
                if (this.savingAsTemplate) return;
                let name = (document.querySelector('h1') && document.querySelector('h1').textContent) || 'Solution Template';
                this.savingAsTemplate = true;
                try {
                    let resp = await fetch(this.apiBase + '/save-as-template', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ name: name, description: '', domain: '' })
                    });
                    let data = await resp.json();
                    if (data.success) {
                        if (window.Platform && Platform.toast && Platform.toast.success) Platform.toast.success('Saved as template.');
                        else Platform.toast.success('Saved as template.');
                    } else {
                        Platform.toast.error(data.error || 'Failed to save template.');
                    }
                } catch (err) {
                    console.error('[solutionDetail] saveAsTemplate error:', err);
                    Platform.toast.error('Failed to save template.');
                }
                this.savingAsTemplate = false;
            },

            // SAD-08 loadAIInsights, openExplainability, confidenceBadge, confidencePct: moved to detail-ai.js

            // WF-01: Load solution-relevant EA workflow definitions
            async loadWorkflowDefinitions() {
                if (this.wfDefinitionsLoaded || this.wfDefinitionsLoading) return;
                this.wfDefinitionsLoading = true;
                try {
                    let r = await fetch('/api/ea-workflows/definitions', { credentials: 'same-origin' });
                    if (r.ok) {
                        let data = await r.json();
                        // Filter to solution-context workflows only
                        let solutionWorkflows = ['VENDOR_SELECTION', 'COMPLIANCE_SCAN', 'ARCHITECTURE_REVIEW',
                            'GAP_REMEDIATION', 'ADM_PHASE_A_VISION', 'ADM_PRELIMINARY'];
                        let all = data.definitions || [];
                        this.wfDefinitions = all.filter(function(d) {
                            return solutionWorkflows.indexOf(d.workflow_code) !== -1 || d.category === 'solution';
                        });
                        if (!this.wfDefinitions.length) this.wfDefinitions = all.slice(0, 6);
                    }
                } catch (e) {
                    console.warn('[WF-01] workflow definitions fetch failed:', e);
                }
                this.wfDefinitionsLoaded = true;
                this.wfDefinitionsLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            // WF-01: Start a workflow with this solution in context
            async startWorkflow(workflowCode) {
                if (this.wfStarting) return;
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                this.wfStarting = workflowCode;
                this.wfStartError = null;
                this.wfStarted = null;
                try {
                    let r = await fetch('/api/ea-workflows/start', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ workflow_code: workflowCode, context: { solution_id: sid, solution_name: document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : '' } })
                    });
                    let data = await r.json();
                    if (data.success || data.instance_id) {
                        this.wfStarted = data;
                        if (window.Platform && Platform.toast && Platform.toast.success) Platform.toast.success('Workflow started.');
                    } else {
                        this.wfStartError = data.error || 'Failed to start workflow.';
                    }
                } catch (e) {
                    this.wfStartError = 'Network error. Please try again.';
                }
                this.wfStarting = null;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            openResubmitModal() {
                this.resubmissionNotes = '';
                this.showResubmitModal = true;
            },

            // SAD-01 loadVendorRiskSignals, vendorRiskLevel: moved to detail-phase-e.js

            // SAD-12: Load solution version history
            // ENT-060: Business Capability Mappings
            async loadCapabilityMappings() {
                if (this.capabilityMappingsLoaded || this.capabilityMappingsLoading) return;
                this.capabilityMappingsLoading = true;
                try {
                    let r = await fetch(this.apiBase + '/capabilities', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    if (r.ok) {
                        let data = await r.json();
                        this.capabilityMappings = (data && data.data) || [];
                    }
                } catch (e) { console.warn('[ENT-060] capability mappings fetch failed:', e); }
                this.capabilityMappingsLoaded = true;
                this.capabilityMappingsLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            async deleteCapabilityMapping(mappingId) {
                if (!(await Platform.modal.confirm('Remove this capability mapping?'))) return;
                let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('[name=csrf_token]')?.value || '';
                try {
                    let r = await fetch(this.apiBase + '/capabilities/' + mappingId, {
                        method: 'DELETE',
                        credentials: 'same-origin',
                        headers: { 'X-CSRFToken': csrfToken }
                    });
                    if (r.ok) {
                        this.capabilityMappings = this.capabilityMappings.filter(function(m) { return m.id !== mappingId; });
                    }
                } catch (e) { console.error('[ENT-060] delete capability mapping failed:', e); }
            },

            // SAD-13: Lessons Learned panel
            async loadLessonsLearned() {
                if (this.lessonsLoaded || this.lessonsLoading) return;
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                if (!sid) { this.lessonsLoaded = true; return; }
                this.lessonsLoading = true;
                try {
                    let r = await fetch('/api/solutions/' + sid + '/backtest-results', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    if (r.ok) {
                        let d = await r.json();
                        this.lessonsLearned = d.lessons_learned || d.results || d.backtests || [];
                    }
                } catch (e) { console.warn('[SAD-13] lessons learned fetch failed:', e); }
                this.lessonsLoaded = true;
                this.lessonsLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },



            // SAD-04 loadSolutionOptions: moved to detail-phase-e.js



            prepareResubmit() {
                if (this.has_ai_generated_content) {
                    this.pendingArbAction = 'resubmit';
                    this.showArbAiConfirmModal = true;
                } else {
                    this.confirmResubmit();
                }
            },
            async confirmResubmit() {
                if (this.submittingArb) return;
                this.submittingArb = true;
                let payload = { resubmission_notes: this.resubmissionNotes };
                if (this.has_ai_generated_content) payload.ai_content_reviewed = true;
                try {
                    let resp = await fetch(this.apiBase + '/submit-for-arb', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify(payload)
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.governanceStatus = data.governance_status || 'arb_review';
                        this.canSubmitArb = false;
                        this.showResubmitModal = false;
                        this.showArbAiConfirmModal = false;
                        this.resubmissionNotes = '';
                    } else {
                        Platform.toast.error(data.error || 'Resubmission failed.');
                    }
                } catch (err) {
                    console.error('[solutionDetail] ARB resubmit error:', err);
                    Platform.toast.error('Failed to resubmit to ARB. Check console for details.');
                }
                this.submittingArb = false;
            },

            get allConditionsMet() {
                if (!this.arbConditions || this.arbConditions.length === 0) return false;
                for (let i = 0; i < this.arbConditions.length; i++) {
                    let c = this.arbConditions[i];
                    if (!(typeof c === 'object' ? c.completed : false)) return false;
                }
                return true;
            },

            async toggleCondition(index) {
                if (this.togglingCondition >= 0) return;
                this.togglingCondition = index;
                try {
                    let resp = await fetch(this.apiBase + '/arb-condition/' + index + '/toggle', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        }
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.arbConditions = data.conditions;
                    } else {
                        Platform.toast.error(data.error || 'Failed to toggle condition.');
                    }
                } catch (err) {
                    console.error('[solutionDetail] condition toggle error:', err);
                }
                this.togglingCondition = -1;
            },

            // SDX-005 _phaseToLayers, aiSuggestElements, acceptSuggestion: moved to detail-phase-e.js
            // --- AI requirements generation (SDX-006) ---
            // aiGenerateRequirements, acceptRequirement, _recordAiFeedback: moved to detail-phase-crud.js
            // --- Phase completeness (SDX-008) ---
            phaseCompleteness(phase) {
                let deliverables = this._phaseDeliverables[phase];
                if (!deliverables) return { filled: 0, total: 0, percent: 0, label: '' };
                let filled = 0;
                let total = deliverables.length;
                for (let i = 0; i < deliverables.length; i++) {
                    let arr = this[deliverables[i]];
                    if (arr && arr.length > 0) filled++;
                }
                let pct = total > 0 ? Math.round((filled / total) * 100) : 0;
                return { filled: filled, total: total, percent: pct, label: filled + '/' + total };
            },

            // searchUsers, selectRoleUser: moved to detail-phase-crud.js
            // --- Section Comment Threads (SDX-022) ---
            commentSections: {},
            commentDrafts: {},
            commentOpen: {},
            commentLoading: {},
            commentPosting: {},

            async toggleComments(section) {
                if (this.commentOpen[section]) {
                    this.commentOpen[section] = false;
                    return;
                }
                this.commentOpen[section] = true;
                if (!this.commentSections[section]) {
                    await this.loadComments(section);
                }
            },

            async loadComments(section) {
                this.commentLoading[section] = true;
                try {
                    let resp = await fetch(this.apiBase + '/comments?section=' + encodeURIComponent(section), {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.commentSections[section] = data.comments;
                    }
                } catch (err) {
                    console.error('[solutionDetail] load comments error:', err);
                }
                this.commentLoading[section] = false;
            },

            async addComment(section) {
                let text = (this.commentDrafts[section] || '').trim();
                if (!text) return;
                this.commentPosting[section] = true;
                try {
                    let resp = await fetch(this.apiBase + '/comments', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ section_name: section, content: text })
                    });
                    let data = await resp.json();
                    if (data.success && data.comment) {
                        if (!this.commentSections[section]) this.commentSections[section] = [];
                        this.commentSections[section].push(data.comment);
                        this.commentDrafts[section] = '';
                    }
                } catch (err) {
                    console.error('[solutionDetail] add comment error:', err);
                }
                this.commentPosting[section] = false;
            },

            commentCount(section) {
                return (this.commentSections[section] || []).length;
            },

            formatCommentDate(iso) {
                if (!iso) return '';
                let d = new Date(iso);
                return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
            },

            // --- ArchiMate diagram helpers (SDX-011) ---
            scrollToArchimateElement(elementId) {
                let el = document.getElementById('archimate-elem-' + elementId);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    el.classList.add('ring-2', 'ring-primary');
                    setTimeout(function() { el.classList.remove('ring-2', 'ring-primary'); }, 2000);
                }
            },

            // --- ARB readiness assessment (SDX-007) ---
            async checkArbReadiness() {
                if (this.checkingReadiness) return;
                this.checkingReadiness = true;
                try {
                    let resp = await fetch(this.apiBase + '/governance-status', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.readinessChecks = data.readiness_checks || [];
                        this.governanceStatus = data.governance_status || this.governanceStatus;
                        this.canSubmitArb = data.can_submit_arb || false;
                        this.has_ai_generated_content = data.has_ai_generated_content === true;
                        this.require_second_review = data.require_second_review === true;
                    }
                } catch (err) {
                    console.error('[solutionDetail] readiness check error:', err);
                }
                this.checkingReadiness = false;
            },

            // openEntityModal, closeModal, _defaults, _apiPath, _listKey: moved to detail-phase-crud.js

            // APQC state, searchApqcProcesses, submitEntity, confirmDeleteEntity, executeDeleteEntity, refreshEntityData: moved to detail-phase-crud.js
            // runOptionsAnalysis, refreshArchitectureVariantsFromRecommendations, loadArchitectureVariants, applyVariant: moved to detail-phase-e.js

            formatAmount(val) {
                let num = parseFloat(val);
                if (isNaN(num)) return '0';
                let symbol = (window.__SOLUTION_CONFIG__ || {}).currencySymbol || '£';
                return symbol + num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
            },

            // ENT-006: Compute average fit score from available ratings (1-10 scale)
            vendorFitScore(vp) {
                const ratings = [vp.scalability_rating, vp.usability_rating, vp.reliability_rating].filter(function(r) { return r != null && r > 0; });
                if (ratings.length === 0) return null;
                let sum = ratings.reduce(function(a, b) { return a + b; }, 0);
                return Math.round(sum / ratings.length);
            },

            // ENT-006: Derive risk level label from security rating
            vendorRiskLevel(vp) {
                if (!vp.security_rating) return null;
                if (vp.security_rating >= 7) return 'Low';
                if (vp.security_rating >= 4) return 'Medium';
                return 'High';
            },

            // --- Draft Architecture Generation ---
            openDraftModal() {
                this.draftBrief = {
                    problem_statement: '',
                    current_state: '',
                    budget_range: '',
                    timeline_months: null,
                    compliance_needs: '',
                    key_stakeholders: '',
                    industry_context: '',
                    technology_preferences: ''
                };
                this.draftResult = null;
                this.draftError = null;
                this.generatingDraft = false;
                this.activeModal = 'generate_draft';
            },

            async generateDraftArchitecture() {
                if (!this.draftBrief.problem_statement || !this.draftBrief.problem_statement.trim()) {
                    this.draftError = 'Problem statement is required.';
                    return;
                }
                this.generatingDraft = true;
                this.draftError = null;
                this.draftResult = null;

                try {
                    let resp = await fetch(this.apiBase + '/generate-draft', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify(this.draftBrief)
                    });
                    let json;
                    let contentType = resp.headers.get('content-type') || '';
                    if (contentType.indexOf('application/json') !== -1) {
                        json = await resp.json();
                    } else {
                        // Server returned HTML (error page) instead of JSON
                        if (resp.status === 404) {
                            this.draftError = 'API endpoint not found. The server may need to be restarted.';
                        } else if (resp.status === 400) {
                            this.draftError = 'Invalid request. Please check your input and try again.';
                        } else {
                            this.draftError = 'Server error (HTTP ' + resp.status + '). Please try again later.';
                        }
                        this.generatingDraft = false;
                        return;
                    }
                    if (!resp.ok || !json.success) {
                        this.draftError = json.error || 'Generation failed. Please try again.';
                        this.generatingDraft = false;
                        return;
                    }
                    this.draftResult = json;

                    // Refresh all entity lists that were generated
                    let types = ['driver', 'goal', 'constraint', 'requirement', 'risk', 'metric', 'tco', 'plateau'];
                    let refreshPromises = [];
                    for (let i = 0; i < types.length; i++) {
                        refreshPromises.push(this.refreshEntityData(types[i]));
                    }
                    await Promise.all(refreshPromises);
                    // ARCH-008: refresh linked archimate elements for review panel
                    await this.loadLinkedArchimateElements();
                } catch (err) {
                    console.error('[solutionDetail] draft generation error:', err);
                    this.draftError = 'Network error. Check connection and try again.';
                }
                this.generatingDraft = false;
            },

            async loadLinkedArchimateElements() {
                this.linkedArchimateLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/archimate-elements', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        let json = await resp.json();
                        // API returns elements grouped by layer — flatten to array with layer field
                        let flat = [];
                        let layerDict = json.elements || {};
                        Object.entries(layerDict).forEach(function(entry) {
                            let layer = entry[0], items = entry[1];
                            (items || []).forEach(function(el) {
                                flat.push(Object.assign({}, el, { layer: layer }));
                            });
                        });
                        this.linkedArchimateElements = flat;
                    }
                } catch (e) {
                    console.warn('[solutionDetail] loadLinkedArchimateElements error:', e);
                } finally {
                    this.linkedArchimateLoading = false;
                }
            },

            async removeLinkedArchimateElement(mappingId) {
                if (!(await Platform.modal.confirm('Remove this ArchiMate element from the solution?'))) return;
                try {
                    let resp = await fetch(this.apiBase + '/archimate-elements/' + mappingId, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        this.linkedArchimateElements = this.linkedArchimateElements.filter(
                            function(e) { return e.mapping_id !== mappingId; }
                        );
                    }
                } catch (e) {
                    console.warn('[solutionDetail] removeLinkedArchimateElement error:', e);
                }
            },

            get archimateReviewByLayer() {
                let grouped = {};
                (this.linkedArchimateElements || []).forEach(function(el) {
                    let layer = (el.layer || 'unknown').toLowerCase();
                    if (!grouped[layer]) grouped[layer] = [];
                    grouped[layer].push(el);
                });
                return Object.entries(grouped).sort(function(a, b) {
                    let order = ['strategy', 'motivation', 'business', 'application', 'technology', 'physical', 'unknown'];
                    return order.indexOf(a[0]) - order.indexOf(b[0]);
                });
            },

            /* ── PRD-007: ArchiMate element picker ────────────────────── */
            searchArchimateElements() {
                let self = this;
                clearTimeout(this._archimatePickerTimer);
                if (this.archimatePickerQuery.length < 2 && !this.archimatePickerLayer) {
                    this.archimatePickerResults = [];
                    this.archimatePickerOpen = false;
                    return;
                }
                this._archimatePickerTimer = setTimeout(function() {
                    self.archimatePickerLoading = true;
                    let layer = self.archimatePickerLayer;
                    let url;
                    if (layer) {
                        url = '/solutions/archimate/' + layer + '/elements?search=' + encodeURIComponent(self.archimatePickerQuery);
                    } else {
                        url = '/adm-kanban/api/elements/search?q=' + encodeURIComponent(self.archimatePickerQuery);
                    }
                    fetch(url, { headers: { 'X-CSRFToken': self.csrfToken } })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            let elements = [];
                            if (data.success && data.elements) {
                                elements = data.elements;
                            } else if (data.results) {
                                elements = data.results;
                            }
                            let linkedIds = (self.linkedArchimateElements || []).map(function(e) { return e.element_id; });
                            self.archimatePickerResults = elements.filter(function(e) {
                                return linkedIds.indexOf(e.id) === -1;
                            });
                            self.archimatePickerOpen = self.archimatePickerResults.length > 0;
                        })
                        .catch(function(e) { console.warn('[picker] archimate search error:', e); })
                        .finally(function() { self.archimatePickerLoading = false; });
                }, 300);
            },

            async addArchimateElement(element) {
                try {
                    let resp = await fetch(this.apiBase + '/archimate-elements', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({
                            elements: [{
                                element_id: element.id,
                                element_table: 'archimate_elements',
                                element_name: element.name,
                                layer_type: element.layer || this.archimatePickerLayer || 'business'
                            }]
                        })
                    });
                    if (resp.ok) {
                        await this.loadLinkedArchimateElements();
                        this.archimatePickerQuery = '';
                        this.archimatePickerResults = [];
                        this.archimatePickerOpen = false;
                        if (window.__archieToast) window.__archieToast('Linked: ' + (element.name || 'ArchiMate element'));
                    }
                } catch (e) {
                    console.warn('[picker] addArchimateElement error:', e);
                }
            },

            /* ── PRD-008: Capability picker ───────────────────────────── */
            async loadLinkedCapabilities() {
                this.linkedCapabilitiesLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/capabilities', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        let json = await resp.json();
                        this.linkedCapabilities = json.capabilities || json.data || [];
                    }
                } catch (e) {
                    console.warn('[picker] loadLinkedCapabilities error:', e);
                } finally {
                    this.linkedCapabilitiesLoading = false;
                }
            },

            searchCapabilities() {
                let self = this;
                clearTimeout(this._capabilityPickerTimer);
                if (this.capabilityPickerQuery.length < 2) {
                    this.capabilityPickerResults = [];
                    this.capabilityPickerOpen = false;
                    return;
                }
                this._capabilityPickerTimer = setTimeout(function() {
                    self.capabilityPickerLoading = true;
                    let url = '/solutions/capabilities/search?q=' + encodeURIComponent(self.capabilityPickerQuery);
                    fetch(url, { headers: { 'X-CSRFToken': self.csrfToken } })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            let linkedIds = (self.linkedCapabilities || []).map(function(c) { return c.id || c.capability_id; });
                            self.capabilityPickerResults = (data.capabilities || data.results || []).filter(function(c) {
                                return linkedIds.indexOf(c.id) === -1;
                            });
                            self.capabilityPickerOpen = true;
                        })
                        .catch(function(e) { console.warn('[picker] capability search error:', e); })
                        .finally(function() { self.capabilityPickerLoading = false; });
                }, 300);
            },

            async addCapability(cap) {
                if (this.isCapLinked(cap.id)) return;
                try {
                    let resp = await fetch(this.apiBase + '/capabilities/link', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ capability_id: cap.id, capability_name: cap.name })
                    });
                    if (resp.ok) {
                        await this.loadLinkedCapabilities();
                        if (!this.capTreeVisible) {
                            /* Legacy flat picker: clear search */
                            this.capabilityPickerQuery = '';
                            this.capabilityPickerResults = [];
                            this.capabilityPickerOpen = false;
                        }
                        /* Tree picker stays open — linked state updates reactively */
                        if (window.__archieToast) window.__archieToast('Linked: ' + (cap.name || 'Capability'));
                    }
                } catch (e) {
                    console.warn('[picker] addCapability error:', e);
                }
            },

            async removeCapability(capId) {
                if (!(await Platform.modal.confirm('Remove this capability from the solution?'))) return;
                try {
                    let resp = await fetch(this.apiBase + '/capabilities/' + capId, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        this.linkedCapabilities = this.linkedCapabilities.filter(function(c) { return (c.id || c.capability_id) !== capId; });
                    }
                } catch (e) {
                    console.warn('[picker] removeCapability error:', e);
                }
            },

            /* ── CAP-016: Hierarchical tree picker ─────────────────────── */
            async loadCapabilityTree() {
                this.capTreeLoading = true;
                try {
                    let url = '/solutions/capabilities/tree';
                    if (this.capTreeDomainFilter) {
                        url += '?domain=' + encodeURIComponent(this.capTreeDomainFilter);
                    }
                    let resp = await fetch(url, { headers: { 'X-CSRFToken': this.csrfToken } });
                    if (resp.ok) {
                        let data = await resp.json();
                        this.capTreeAll = data.capabilities || [];
                        if (!this.capTreeDomainFilter && data.domains) {
                            this.capTreeDomains = data.domains;
                        }
                        this.filterCapabilityTree();
                    }
                } catch (e) {
                    console.warn('[picker] loadCapabilityTree error:', e);
                } finally {
                    this.capTreeLoading = false;
                }
            },

            buildCapabilityTree(caps) {
                /* Build a parent→children tree from flat list.
                   Returns array of L1 root nodes, each with a .children array of L2,
                   each L2 with .children array of L3. */
                const byId = {};
                const roots = [];
                let i, cap, parentId;

                for (i = 0; i < caps.length; i++) {
                    cap = Object.assign({}, caps[i], { children: [] });
                    byId[cap.id] = cap;
                }
                for (i = 0; i < caps.length; i++) {
                    cap = byId[caps[i].id];
                    parentId = caps[i].parent_capability_id;
                    if (parentId && byId[parentId]) {
                        byId[parentId].children.push(cap);
                    } else {
                        roots.push(cap);
                    }
                }
                return roots;
            },

            filterCapabilityTree() {
                let self = this;
                let q = (this.capabilityPickerQuery || '').toLowerCase().trim();
                let caps = this.capTreeAll;

                if (q.length > 0) {
                    /* When searching, include any capability whose name matches,
                       plus its ancestors so the tree structure remains visible. */
                    const matchIds = {};
                    let i, cap;
                    for (i = 0; i < caps.length; i++) {
                        if (caps[i].name && caps[i].name.toLowerCase().indexOf(q) !== -1) {
                            matchIds[caps[i].id] = true;
                            /* Walk up parent chain to include ancestors */
                            let pid = caps[i].parent_capability_id;
                            while (pid) {
                                matchIds[pid] = true;
                                let parent = null;
                                for (let j = 0; j < caps.length; j++) {
                                    if (caps[j].id === pid) { parent = caps[j]; break; }
                                }
                                pid = parent ? parent.parent_capability_id : null;
                            }
                        }
                    }
                    caps = caps.filter(function(c) { return matchIds[c.id]; });
                    /* Auto-expand all nodes when searching */
                    const expanded = {};
                    for (i = 0; i < caps.length; i++) {
                        expanded[caps[i].id] = true;
                    }
                    this.capTreeExpanded = expanded;
                }

                this.capTreeFiltered = this.buildCapabilityTree(caps);
            },

            toggleCapTreeNode(nodeId) {
                const expanded = Object.assign({}, this.capTreeExpanded);
                expanded[nodeId] = !expanded[nodeId];
                this.capTreeExpanded = expanded;
            },

            isCapLinked(capId) {
                const linked = this.linkedCapabilities || [];
                for (let i = 0; i < linked.length; i++) {
                    if ((linked[i].id || linked[i].capability_id) === capId) return true;
                }
                return false;
            },

            /* ── PRD-009: Vendor Product picker ───────────────────────── */
            async loadLinkedVendorProducts() {
                this.linkedVendorProductsLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/linked-vendor-products', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        let json = await resp.json();
                        this.linkedVendorProducts = json.products || json.data || [];
                    }
                } catch (e) {
                    console.warn('[picker] loadLinkedVendorProducts error:', e);
                } finally {
                    this.linkedVendorProductsLoading = false;
                }
            },

            searchVendorProducts() {
                let self = this;
                clearTimeout(this._vendorProductPickerTimer);
                if (this.vendorProductPickerQuery.length < 2) {
                    this.vendorProductPickerResults = [];
                    this.vendorProductPickerOpen = false;
                    return;
                }
                this._vendorProductPickerTimer = setTimeout(function() {
                    self.vendorProductPickerLoading = true;
                    let url = '/solutions/vendor-products/search?q=' + encodeURIComponent(self.vendorProductPickerQuery);
                    fetch(url, { headers: { 'X-CSRFToken': self.csrfToken } })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            let linkedIds = (self.linkedVendorProducts || []).map(function(p) { return p.id || p.product_id; });
                            self.vendorProductPickerResults = (data.results || data.products || []).filter(function(p) {
                                return linkedIds.indexOf(p.id) === -1;
                            });
                            self.vendorProductPickerOpen = true;
                        })
                        .catch(function(e) { console.warn('[picker] vendor product search error:', e); })
                        .finally(function() { self.vendorProductPickerLoading = false; });
                }, 300);
            },

            async addVendorProduct(product) {
                try {
                    let resp = await fetch(this.apiBase + '/link-vendor-product', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ vendor_product_id: product.id })
                    });
                    if (resp.ok) {
                        await this.loadLinkedVendorProducts();
                        this.vendorProductPickerQuery = '';
                        this.vendorProductPickerResults = [];
                        this.vendorProductPickerOpen = false;
                        if (window.__archieToast) window.__archieToast('Linked: ' + (product.name || 'Vendor product'));
                    }
                } catch (e) {
                    console.warn('[picker] addVendorProduct error:', e);
                }
            },

            async removeVendorProduct(productId) {
                if (!(await Platform.modal.confirm('Remove this vendor product from the solution?'))) return;
                try {
                    let resp = await fetch(this.apiBase + '/unlink-vendor-product/' + productId, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        this.linkedVendorProducts = this.linkedVendorProducts.filter(function(p) { return (p.id || p.product_id) !== productId; });
                    }
                } catch (e) {
                    console.warn('[picker] removeVendorProduct error:', e);
                }
            },

            /* ── PRD-010: APQC Process picker ─────────────────────────── */
            async loadLinkedAPQCProcesses() {
                this.linkedAPQCLoading = true;
                try {
                    let resp = await fetch(this.apiBase + '/linked-apqc-processes', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        let json = await resp.json();
                        this.linkedAPQCProcesses = json.processes || json.data || [];
                    }
                } catch (e) {
                    console.warn('[picker] loadLinkedAPQCProcesses error:', e);
                } finally {
                    this.linkedAPQCLoading = false;
                }
            },

            searchAPQCProcesses() {
                let self = this;
                clearTimeout(this._apqcPickerTimer);
                if (this.apqcPickerQuery.length < 2) {
                    this.apqcPickerResults = [];
                    this.apqcPickerOpen = false;
                    return;
                }
                this._apqcPickerTimer = setTimeout(function() {
                    self.apqcPickerLoading = true;
                    let url = '/api/apqc/search?q=' + encodeURIComponent(self.apqcPickerQuery);
                    fetch(url, { headers: { 'X-CSRFToken': self.csrfToken } })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            let linkedIds = (self.linkedAPQCProcesses || []).map(function(p) { return p.process_id || p.id; });
                            self.apqcPickerResults = (data.matches || data.processes || data.results || []).filter(function(p) {
                                return linkedIds.indexOf(p.process_id || p.id) === -1;
                            });
                            self.apqcPickerOpen = true;
                        })
                        .catch(function(e) { console.warn('[picker] APQC search error:', e); })
                        .finally(function() { self.apqcPickerLoading = false; });
                }, 300);
            },

            async addAPQCProcess(process) {
                try {
                    let resp = await fetch(this.apiBase + '/link-apqc-process', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ apqc_process_id: process.process_id || process.id })
                    });
                    if (resp.ok) {
                        await this.loadLinkedAPQCProcesses();
                        this.apqcPickerQuery = '';
                        this.apqcPickerResults = [];
                        this.apqcPickerOpen = false;
                        if (window.__archieToast) window.__archieToast('Linked: ' + (process.process_name || process.name || 'APQC process'));
                    }
                } catch (e) {
                    console.warn('[picker] addAPQCProcess error:', e);
                }
            },

            async removeAPQCProcess(processId) {
                if (!(await Platform.modal.confirm('Remove this APQC process from the solution?'))) return;
                try {
                    let resp = await fetch(this.apiBase + '/unlink-apqc-process/' + processId, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        this.linkedAPQCProcesses = this.linkedAPQCProcesses.filter(function(p) { return (p.process_id || p.id) !== processId; });
                    }
                } catch (e) {
                    console.warn('[picker] removeAPQCProcess error:', e);
                }
            },

            /* ── PRD-012: Application picker ──────────────────────────── */
            async loadLinkedApplications() {
                this.linkedAppsLoading = true;
                try {
                    const resp = await fetch(this.apiBase + '/linked-applications', {
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        const json = await resp.json();
                        this.linkedApplications = json.applications || json.data || [];
                    }
                } catch (e) {
                    console.warn('[picker] loadLinkedApplications error:', e);
                } finally {
                    this.linkedAppsLoading = false;
                }
            },

            searchApplications() {
                let self = this;
                clearTimeout(this._appPickerTimer);
                if (this.appPickerQuery.length < 2) {
                    this.appPickerResults = [];
                    this.appPickerOpen = false;
                    return;
                }
                this._appPickerTimer = setTimeout(function() {
                    self.appPickerLoading = true;
                    let url = '/applications/api/list?search=' + encodeURIComponent(self.appPickerQuery) + '&limit=10&sort=relevance';
                    fetch(url, { headers: { 'X-CSRFToken': self.csrfToken } })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            let linkedIds = (self.linkedApplications || []).map(function(a) { return a.id || a.app_id; });
                            let items = data.applications || data.results || data.data || [];
                            self.appPickerResults = items.filter(function(a) {
                                return linkedIds.indexOf(a.id) === -1;
                            });
                            self.appPickerOpen = true;
                        })
                        .catch(function(e) { console.warn('[picker] app search error:', e); })
                        .finally(function() { self.appPickerLoading = false; });
                }, 300);
            },

            async addApplication(app) {
                try {
                    let resp = await fetch(this.apiBase + '/link-application', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                        body: JSON.stringify({ application_id: app.id })
                    });
                    if (resp.ok) {
                        await this.loadLinkedApplications();
                        this.appPickerQuery = '';
                        this.appPickerResults = [];
                        this.appPickerOpen = false;
                        if (window.__archieToast) window.__archieToast('Linked: ' + (app.name || 'Application'));
                    }
                } catch (e) {
                    console.warn('[picker] addApplication error:', e);
                }
            },

            async removeApplication(appId) {
                if (!(await Platform.modal.confirm('Remove this application from the solution?'))) return;
                try {
                    let resp = await fetch(this.apiBase + '/unlink-application/' + appId, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': this.csrfToken }
                    });
                    if (resp.ok) {
                        this.linkedApplications = this.linkedApplications.filter(function(a) { return (a.id || a.app_id) !== appId; });
                    }
                } catch (e) {
                    console.warn('[picker] removeApplication error:', e);
                }
            },

            // PLT-004: CSV junction import
            async importJunctionsCsv(event) {
                let file = event.target && event.target.files && event.target.files[0];
                if (!file) return;
                this.csvImporting = true;
                this.csvImportResult = null;
                this.csvImportError = '';
                try {
                    let formData = new FormData();
                    formData.append('file', file);
                    let resp = await fetch(this.apiBase + '/import-junctions', {
                        method: 'POST',
                        headers: { 'X-CSRFToken': this.csrfToken },
                        body: formData
                    });
                    let data = await resp.json();
                    if (!resp.ok) {
                        this.csvImportError = data.error || ('Import failed (HTTP ' + resp.status + ')');
                    } else {
                        this.csvImportResult = data;
                    }
                } catch (err) {
                    this.csvImportError = 'Import failed: ' + err.message;
                } finally {
                    this.csvImporting = false;
                    // Reset file input so the same file can be re-uploaded
                    if (event.target) event.target.value = '';
                }
            }
        };
        return Object.assign(_solutionDetailBase, window._detailCrud || {}, window._detailPhaseE || {}, window._detailAI || {});
    });
});

/* ═══════════════════════════════════════════════════════════════════════════
 * Alpine component: phaseHReview
 * Phase H value realization dashboard — metric comparison, cost variance,
 * risk outcomes, and new ADM cycle creation.
 * ═══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('alpine:init', function () {
    Alpine.data('phaseHReview', function () {
        let cfg = window.__SOLUTION_CONFIG__ || {};
        let base = cfg.apiBase || '/solutions/' + cfg.solutionId;

        return {
            apiBase: base,
            loading: false,
            loaded: false,
            reviewData: { metrics: [], cost_variance: {}, risk_outcomes: [] },
            overallAchievement: null,
            newCycleName: '',
            newCycleDriver: '',
            creatingCycle: false,
            csrfToken: (document.querySelector('meta[name="csrf-token"]') || {}).content || '',

            async loadReview() {
                this.loading = true;
                try {
                    let resp = await fetch(this.apiBase + '/phase-h/review');
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    let data = await resp.json();
                    this.reviewData = {
                        metrics: data.metrics || [],
                        cost_variance: data.cost_variance || {},
                        risk_outcomes: data.risk_outcomes || [],
                    };
                    this.overallAchievement = data.overall_achievement;
                    this.loaded = true;
                } catch (err) {
                    console.error('[phaseHReview] load error:', err);
                }
                this.loading = false;
            },

            async startNewCycle() {
                if (!this.newCycleName) return;
                this.creatingCycle = true;
                try {
                    let body = { name: this.newCycleName };
                    if (this.newCycleDriver && this.newCycleDriver.trim()) {
                        body.new_drivers = [this.newCycleDriver.trim()];
                    }
                    let resp = await fetch(this.apiBase + '/phase-h/new-cycle', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken,
                        },
                        body: JSON.stringify(body),
                    });
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    let data = await resp.json();
                    if (data.success && data.redirect_url) {
                        window.location.href = data.redirect_url;
                    }
                } catch (err) {
                    console.error('[phaseHReview] new cycle error:', err);
                    Platform.toast.error('Failed to create new ADM cycle. Check console for details.');
                }
                this.creatingCycle = false;
            },


            // ENT-019: Outcome recording
            async submitOutcome() {
                if (!this.outcomeForm.go_live_date) return;
                this.outcomeSubmitting = true;
                this.outcomeSuccess = '';
                this.outcomeError = '';
                const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
                try {
                    const resp = await fetch(`${this.apiBase}/record-outcome`.replace('/solutions/', '/api/solutions/'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                        body: JSON.stringify(this.outcomeForm),
                    });
                    const data = await resp.json();
                    if (data.success) {
                        this.outcomeSuccess = 'Outcome saved successfully.';
                        this.outcomeForm = { go_live_date: '', actual_duration_weeks: '', actual_cost_usd: '', lessons_learned: '', what_went_well: '', what_to_improve: '' };
                    } else {
                        this.outcomeError = data.error || 'Failed to save outcome.';
                    }
                } catch (err) {
                    this.outcomeError = 'Network error: ' + err.message;
                } finally {
                    this.outcomeSubmitting = false;
                }
            },

        };
    });
});

document.addEventListener('DOMContentLoaded', function () {
    loadSolutionCapabilities();
});

window.deleteSolution = deleteSolution;
window.loadSolutionCapabilities = loadSolutionCapabilities;

/* ═══════════════════════════════════════════════════════════════════════════
 * BPP-014: Per-phase "Suggest Elements" Alpine component
 * ═══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('alpine:init', function () {
    Alpine.data('phaseSuggestions', function () {
        let cfg = window.__SOLUTION_CONFIG__ || {};
        let solutionId = cfg.solutionId;
        let csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

        return {
            phase: '',
            loading: false,
            suggestions: { existing_elements: [], new_elements: [] },
            showPanel: false,
            applying: false,
            statusMsg: '',

            async suggestElements(phase) {
                this.phase = phase;
                this.loading = true;
                this.showPanel = true;
                this.statusMsg = '';
                try {
                    let resp = await fetch('/solutions/' + solutionId + '/api/suggest-elements', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ phases: [phase] })
                    });
                    let data = await resp.json();
                    if (data.error) {
                        this.statusMsg = data.error;
                        this.suggestions = { existing_elements: [], new_elements: [] };
                    } else {
                        this.suggestions = data.suggestions[phase] || { existing_elements: [], new_elements: [] };
                        // Pre-check high confidence items
                        this.suggestions.existing_elements.forEach(function (el) {
                            el._accepted = el.confidence >= 0.8;
                        });
                        this.suggestions.new_elements.forEach(function (el) {
                            el._accepted = false; // never pre-check new elements
                        });
                    }
                } catch (e) {
                    this.statusMsg = 'Failed to load suggestions';
                    console.error(e);
                } finally {
                    this.loading = false;
                }
            },

            async applySelections() {
                this.applying = true;
                const accepted = this.suggestions.existing_elements
                    .filter(function (el) { return el._accepted; })
                    .map(function (el) { return { element_id: el.element_id, phase: this.phase, relationship_type: el.relationship_type }; }.bind(this));
                const newEls = this.suggestions.new_elements
                    .filter(function (el) { return el._accepted; })
                    .map(function (el) { return { name: el.name, type: el.type, layer: el.layer, phase: this.phase }; }.bind(this));

                try {
                    let resp = await fetch('/solutions/' + solutionId + '/api/accept-suggestions', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ accepted: accepted, new_elements: newEls })
                    });
                    let data = await resp.json();
                    if (data.error) {
                        this.statusMsg = data.error;
                    } else {
                        this.statusMsg = (data.accepted_count + data.created_count) + ' elements added';
                        this.showPanel = false;
                        // Reload the page to show new elements
                        setTimeout(function () { location.reload(); }, 1500);
                    }
                } catch (e) {
                    this.statusMsg = 'Failed to apply selections';
                } finally {
                    this.applying = false;
                }
            },

            // FRAG-005: Strategic Analysis lazy-load methods
            async loadStrategicRiskAnalysis() {
                if (this.strategicRiskLoaded || this.strategicRiskLoading) return;
                this.strategicRiskLoading = true;
                try {
                    let resp = await fetch('/strategic/api/risk-analysis', { credentials: 'same-origin' });
                    if (resp.ok) {
                        this.strategicRiskAnalysis = await resp.json();
                        this.strategicRiskLoaded = true;
                    }
                } catch(e) { console.warn('[FRAG-005] risk-analysis fetch failed', e); }
                this.strategicRiskLoading = false;
            },
            async loadStrategicInvestment() {
                if (this.strategicInvestmentLoaded || this.strategicInvestmentLoading) return;
                this.strategicInvestmentLoading = true;
                try {
                    let resp = await fetch('/strategic/api/investment-analysis', { credentials: 'same-origin' });
                    if (resp.ok) {
                        this.strategicInvestment = await resp.json();
                        this.strategicInvestmentLoaded = true;
                    }
                } catch(e) { console.warn('[FRAG-005] investment-analysis fetch failed', e); }
                this.strategicInvestmentLoading = false;
            },
            async loadStrategicDependency() {
                if (this.strategicDependencyLoaded || this.strategicDependencyLoading) return;
                this.strategicDependencyLoading = true;
                try {
                    let resp = await fetch('/strategic/api/dependency-analysis', { credentials: 'same-origin' });
                    if (resp.ok) {
                        this.strategicDependency = await resp.json();
                        this.strategicDependencyLoaded = true;
                    }
                } catch(e) { console.warn('[FRAG-005] dependency-analysis fetch failed', e); }
                this.strategicDependencyLoading = false;
            },
            async loadStrategicTechnology() {
                if (this.strategicTechnologyLoaded || this.strategicTechnologyLoading) return;
                this.strategicTechnologyLoading = true;
                try {
                    let resp = await fetch('/strategic/api/technology-analysis', { credentials: 'same-origin' });
                    if (resp.ok) {
                        this.strategicTechnology = await resp.json();
                        this.strategicTechnologyLoaded = true;
                    }
                } catch(e) { console.warn('[FRAG-005] technology-analysis fetch failed', e); }
                this.strategicTechnologyLoading = false;
            },
            riskLevelBadge(level) {
                const map = { critical: 'bg-red-500/10 text-red-600 border-red-500/30', high: 'bg-orange-500/10 text-orange-600 border-orange-500/30', medium: 'bg-amber-500/10 text-amber-600 border-amber-500/30', low: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' };
                return map[(level || '').toLowerCase()] || 'bg-muted text-muted-foreground border-border';
            },

            layerBadgeClass: function (layer) {
                const classes = {
                    'motivation': 'bg-violet-500/10 text-violet-600 border-violet-500/30',
                    'strategy': 'bg-indigo-500/10 text-indigo-600 border-indigo-500/30',
                    'business': 'bg-amber-500/10 text-amber-600 border-amber-500/30',
                    'application': 'bg-blue-500/10 text-blue-600 border-blue-500/30',
                    'technology': 'bg-green-500/10 text-green-600 border-green-500/30',
                    'implementation': 'bg-slate-500/10 text-slate-600 border-slate-500/30',
                };
                return classes[(layer || '').toLowerCase()] || 'bg-muted text-muted-foreground border-input';
            }
        };
    });
});
