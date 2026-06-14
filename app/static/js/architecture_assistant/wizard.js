/**
 * Architecture Assistant Wizard — Alpine.js Component
 *
 * Powers the 9-step TOGAF-aligned solution design wizard.
 * Reads config from window.__WIZARD_CONFIG__ (set by Jinja2 template).
 *
 * Steps 1-6: Design phase (pre-ARB)
 * Steps 7-9: Execution phase (post-ARB, P2 placeholders)
 */

function architectureWizard() {
  let cfg = window.__WIZARD_CONFIG__ || {};

  return {
    // -- Core state --
    solutionId: cfg.solutionId || null,
    currentStep: cfg.currentStep || 1,
    maxStep: cfg.maxStep || 6,
    llmAvailable: cfg.llmAvailable || false,
    csrfToken: cfg.csrfToken || '',
    saving: false,

    // Step definitions
    steps: [
      { num: 1, label: 'Scope', phase: 'A', complete: false },
      { num: 2, label: 'Capabilities', phase: 'B', complete: false },
      { num: 3, label: 'Gaps', phase: 'B-D', complete: false },
      { num: 4, label: 'Options', phase: 'E', complete: false },
      { num: 5, label: 'Roadmap', phase: 'F', complete: false },
      { num: 6, label: 'ARB', phase: 'G', complete: false },
      { num: 7, label: 'Execution', phase: 'F', complete: false },
      { num: 8, label: 'Governance', phase: 'G', complete: false },
      { num: 9, label: 'Lessons', phase: 'H', complete: false },
    ],

    // -- Step 1: Scope --
    scope: {
      name: '',
      business_domain: '',
      business_problem: '',
      linked_applications: [],
      drivers: [],
      goals: [],
      constraints: [],
      stakeholders: [],
      archimate_elements: [],
    },
    // Step 1 sub-phase: 'scope' | 'quality_baseline'
    step1Phase: 'scope',

    // -- Step 1B: Quality Baseline --
    qualityBaseline: {
      // Mandatory (6 domains)
      identity_access: { auth_provider: '', authz_model: 'RBAC', mfa_required: false, sso_required: false },
      data_management: { primary_db: '', backup_frequency: 'daily', rto_hours: '', rpo_hours: '', data_retention_years: '' },
      security_controls: { data_classification: 'internal', encryption_at_rest: true, encryption_in_transit: true, secret_management: '', vulnerability_scanning: false },
      integration: { api_style: [], rate_limiting: false, api_gateway: '', event_streaming: false },
      observability: { logging_platform: '', metrics_enabled: true, distributed_tracing: false, alerting_required: true },
      reliability: { availability_target: '99.9', redundancy_model: '', auto_scaling: false, dr_strategy: '' },
      // Recommended (6 domains)
      performance: { p99_latency_ms: '', peak_rps: '', caching_strategy: '' },
      deployment_release: { hosting: '', containerized: false, deployment_pattern: '', ci_cd_platform: '' },
      compliance_audit: { regulatory_frameworks: [], audit_logging: false, data_sovereignty_required: false },
      operational_support: { support_tier: '', incident_response_sla_minutes: '', runbooks_required: false },
      testing_quality: { unit_coverage_target_pct: '', e2e_tests_required: false, performance_tests_required: false, security_tests_required: false },
      cost_sustainability: { budget_model: '', monthly_budget_usd: '', cost_review_frequency: '' },
    },
    qbOpenDomain: 'identity_access',
    qualityBaselineWarnings: [],
    qbValidating: false,

    scopeApproved: false,
    scopeReviewPending: false,
    appSearch: '',
    appSearchResults: [],
    driverSearch: '',
    driverResults: [],
    goalSearch: '',
    goalResults: [],
    constraintSearch: '',
    constraintResults: [],
    stakeholderSearch: '',
    stakeholderResults: [],
    problemLoading: false,
    importSummary: '',
    archimateSearch: '',
    archimateSearchResults: [],
    showCreateElementForm: false,
    elementTypesByLayer: {},
    newElement: { name: '', type: '', layer: '' },
    newElementTypes: [],
    creatingElement: false,

    // -- Step 2: Capabilities --
    capabilities: [],
    prePopulatedCapabilities: [],
    capabilitySearch: '',
    capabilitySearchResults: [],
    capabilityPage: 1,
    capabilityPageSize: 50,

    // -- Step 3: Gaps --
    gaps: [],
    gapAnalysisLoading: false,
    gapAnalysisAiGenerated: false,
    affectedLayers: [],

    // -- Step 4: Options --
    options: [],
    optionsLoading: false,
    selectedOptionId: null,
    compareModalOpen: false,
    comparisonData: null,

    // -- Step 5: Roadmap --
    roadmap: { plateaus: [], workPackages: [] },
    roadmapLoading: false,

    // -- Step 6: ARB --
    arbDraft: null,
    arbDraftOriginal: null,
    arbLoading: false,
    arbDraftSaving: false,

    // -- Step 7: Execution Tracking --
    executionItems: [],
    composerRenderer: null,
    composerStatus: '',

    // -- Step 8: Governance Checkpoints --
    governanceCheckpoints: [],

    // -- Step 9: Lessons Learned --
    outcomeMetrics: [],
    lessonsLearned: [],

    // -- Governance --
    governanceStatus: '',

    // -- Toast notifications --
    toasts: [],

    // =========================================================================
    // Initialization
    // =========================================================================

    init() {
      // Hydrate governance status
      let gs = (cfg.solution && cfg.solution.governance_status) || '';
      this.governanceStatus = gs;
      // Initialize governance checkpoints with defaults
      this.governanceCheckpoints = this._defaultCheckpoints();
      if (['arb_submitted', 'arb_approved', 'approved'].indexOf(gs) !== -1) {
        this.maxStep = 9;
      }

      // Hydrate from existing solution if resuming
      if (cfg.solution) {
        this._hydrateSolution(cfg.solution);
      }
      // Mark completed steps
      this._updateStepCompletion();
      // Initialize Lucide icons after Alpine renders
      this.$nextTick(function () {
        if (window.lucide) window.lucide.createIcons();
      });
    },

    showToast(message, type) {
      type = type || 'info';
      let id = Date.now() + '-' + Math.random().toString(36).substr(2, 5);
      this.toasts.push({ id: id, message: message, type: type });
      let self = this;
      setTimeout(function () { self.removeToast(id); }, 4000);
    },

    removeToast(id) {
      this.toasts = this.toasts.filter(function (t) { return t.id !== id; });
    },

    _hydrateSolution(sol) {
      this.scope.name = sol.name || '';
      this.scope.business_domain = sol.business_domain || '';
      this.scope.business_problem = sol.description || '';

      // Linked apps come from solution.applications relationship (serialized)
      if (sol.linked_applications) {
        this.scope.linked_applications = sol.linked_applications;
      }
      // Motivation elements
      if (sol.drivers) this.scope.drivers = sol.drivers;
      if (sol.goals) this.scope.goals = sol.goals;
      if (sol.constraints) this.scope.constraints = sol.constraints;
      if (sol.stakeholders) this.scope.stakeholders = sol.stakeholders;
      if (sol.archimate_elements) this.scope.archimate_elements = sol.archimate_elements;

      // Step 1B: Quality baseline
      if (sol.quality_baseline_data) {
        let qb = sol.quality_baseline_data;
        let self = this;
        Object.keys(qb).forEach(function (domain) {
          if (self.qualityBaseline[domain]) {
            Object.assign(self.qualityBaseline[domain], qb[domain]);
          }
        });
      }
      // Step 2
      if (sol.capabilities) {
        this.capabilities = sol.capabilities;
        this.prePopulatedCapabilities = sol.capabilities.filter(function (c) { return c.from_app; });
      }
      // Step 3
      if (sol.gaps) this.gaps = sol.gaps;
      // Step 4
      if (sol.options) this.options = sol.options;
      if (sol.selected_option_id) this.selectedOptionId = sol.selected_option_id;
      else if (sol.recommended_option_id) this.selectedOptionId = sol.recommended_option_id;
      // Step 5
      if (sol.roadmap) this.roadmap = sol.roadmap;
      // Step 6
      if (sol.arb_draft) {
        this.arbDraft = sol.arb_draft;
        this.arbDraftOriginal = JSON.parse(JSON.stringify(sol.arb_draft));
      }
      // Step 7: Execution items
      if (sol.execution_items) this.executionItems = sol.execution_items;
      // Step 8: Governance checkpoints
      if (sol.governance_checkpoints && sol.governance_checkpoints.length) {
        this.governanceCheckpoints = sol.governance_checkpoints;
      }
      // Step 9: Lessons learned + outcome metrics
      if (sol.outcome_metrics) this.outcomeMetrics = sol.outcome_metrics;
      if (sol.lessons_learned) this.lessonsLearned = sol.lessons_learned;
    },

    // =========================================================================
    // Step 8: Governance helpers
    // =========================================================================

    _defaultCheckpoints() {
      return ['A','B','C','D','E','F','G','H'].map(function (p) {
        return { phase: p, status: 'not_started', notes: '', reviewer: '' };
      });
    },

    phaseLabel(phase) {
      let labels = {
        'A': 'Architecture Vision',
        'B': 'Business Architecture',
        'C': 'Information Systems',
        'D': 'Technology Architecture',
        'E': 'Opportunities & Solutions',
        'F': 'Migration Planning',
        'G': 'Implementation Governance',
        'H': 'Architecture Change Management',
      };
      return labels[phase] || phase;
    },

    // =========================================================================
    // Step 9: Lessons Learned helpers
    // =========================================================================

    addMetric() {
      this.outcomeMetrics.push({
        metric_name: '',
        unit: '',
        baseline_value: '',
        target_value: '',
        actual_value: '',
      });
      let self = this;
      this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
    },

    addLesson() {
      this.lessonsLearned.push({
        category: 'other',
        description: '',
        recommendation: '',
      });
      let self = this;
      this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
    },

    // =========================================================================
    // Navigation
    // =========================================================================

    canNavigateTo(stepNum) {
      if (stepNum < 1) return false;
      if (stepNum > 9) return false;
      if (stepNum > 6) {
        // Steps 7-9 require ARB approval
        let gs = this.governanceStatus || '';
        return ['arb_submitted', 'arb_approved', 'approved'].indexOf(gs) !== -1;
      }
      if (stepNum > this.maxStep) return false;
      // Can always go back to completed steps or current
      if (stepNum <= this.currentStep) return true;
      // Can go forward one step if current step is complete
      if (stepNum === this.currentStep + 1) return true;
      return false;
    },

    goToStep(stepNum) {
      if (!this.canNavigateTo(stepNum)) return;
      this.currentStep = stepNum;
      this._updateURL();
      let self = this;
      this.$nextTick(function () {
        if (window.lucide) window.lucide.createIcons();
        if (stepNum === 7) self.initComposer();
      });
    },

    canProceed() {
      if (this.saving) return false;
      switch (this.currentStep) {
        case 1:
          if (this.step1Phase === 'quality_baseline') return true; // soft gate — always can proceed
          // ENH-004: If AI generated the scope, require explicit approval
          if (this.scopeReviewPending && !this.scopeApproved) return false;
          return this.scope.name.trim() !== '' && this.scope.business_domain !== '';
        case 2:
          return this.capabilities.length > 0;
        case 3:
          return this.gaps.length > 0;
        case 4:
          return this.selectedOptionId !== null;
        case 5:
          return this.roadmap.workPackages.length > 0;
        case 6:
          // ENH-005: Block submission if AI-generated draft is pending review
          if (this.arbDraft && this.arbDraft.ai_generated && this.arbDraft.approval_status === 'pending_review') return false;
          return this.arbDraft !== null;
        default:
          return true;
      }
    },

    async nextStep() {
      if (!this.canProceed()) return;

      // Step 1 scope sub-phase: save scope and advance to quality baseline
      if (this.currentStep === 1 && this.step1Phase === 'scope') {
        let saved = await this._saveCurrentStep();
        if (!saved) return;
        this.step1Phase = 'quality_baseline';
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
        // Run validation after Alpine renders the panel
        let self = this;
        setTimeout(function () { self.validateQualityBaseline(); }, 500);
        return;
      }

      // Persist current step data
      let saved = await this._saveCurrentStep();
      if (!saved) return;

      // Mark current step complete
      this.steps[this.currentStep - 1].complete = true;

      // Advance
      if (this.currentStep < this.maxStep) {
        this.currentStep++;
        this.step1Phase = 'scope'; // reset sub-phase when leaving step 1
        this._updateURL();
        let self = this;
        this.$nextTick(function () {
          if (window.lucide) window.lucide.createIcons();
          if (self.currentStep === 7) self.initComposer();
        });
      }
    },

    _updateURL() {
      if (this.solutionId) {
        let url = '/architecture-assistant/' + this.solutionId + '/step/' + this.currentStep;
        history.replaceState(null, '', url);
      }
    },

    _updateStepCompletion() {
      let self = this;
      this.steps.forEach(function (s) {
        if (s.num < self.currentStep) s.complete = true;
      });
    },

    // =========================================================================
    // Step 1: Application search
    // =========================================================================

    async searchApplications() {
      let q = this.appSearch.trim();
      if (q.length < 2) { this.appSearchResults = []; return; }
      try {
        let resp = await this._fetch('/applications/api/list?search=' + encodeURIComponent(q) + '&limit=10');
        this.appSearchResults = resp.applications || resp.items || resp || [];
      } catch (e) {
        this.appSearchResults = [];
      }
    },

    linkApplication(app) {
      let exists = this.scope.linked_applications.find(function (a) { return a.id === app.id; });
      if (!exists) {
        this.scope.linked_applications.push({ id: app.id, name: app.name, vendor: app.vendor || '' });
        this._updateImportSummary();
      }
      this.appSearch = '';
      this.appSearchResults = [];
    },

    unlinkApplication(id) {
      this.scope.linked_applications = this.scope.linked_applications.filter(function (a) { return a.id !== id; });
      this._updateImportSummary();
    },

    _updateImportSummary() {
      let count = this.scope.linked_applications.length;
      this.importSummary = count + ' application' + (count !== 1 ? 's' : '') + ' linked — ArchiMate elements, vendors, and capabilities will be auto-imported.';
    },

    // =========================================================================
    // Step 1: Motivation element search (Drivers, Goals, Constraints, Stakeholders)
    // =========================================================================

    async searchMotivationElements(type) {
      let searchMap = {
        Driver: 'driverSearch',
        Goal: 'goalSearch',
        Constraint: 'constraintSearch',
        Stakeholder: 'stakeholderSearch',
      };
      let resultMap = {
        Driver: 'driverResults',
        Goal: 'goalResults',
        Constraint: 'constraintResults',
        Stakeholder: 'stakeholderResults',
      };

      let q = this[searchMap[type]].trim();
      if (q.length < 2) { this[resultMap[type]] = []; return; }

      try {
        let resp = await this._fetch(
          '/api/architecture-assistant/motivation-elements?q=' + encodeURIComponent(q) + '&type=' + encodeURIComponent(type)
        );
        this[resultMap[type]] = resp.elements || resp.results || [];
      } catch (e) {
        this[resultMap[type]] = [];
      }
    },

    addMotivationElement(category, el) {
      let list = this.scope[category];
      let exists = list.find(function (e) { return e.id === el.id; });
      if (!exists) {
        list.push({ id: el.id, name: el.name, type: el.type || category });
      }
      // Clear search
      let searchKeys = { drivers: 'driverSearch', goals: 'goalSearch', constraints: 'constraintSearch', stakeholders: 'stakeholderSearch' };
      let resultKeys = { drivers: 'driverResults', goals: 'goalResults', constraints: 'constraintResults', stakeholders: 'stakeholderResults' };
      this[searchKeys[category]] = '';
      this[resultKeys[category]] = [];
    },

    createMotivationElement(category, type, name) {
      if (!name || !name.trim()) return;
      let list = this.scope[category];
      list.push({ id: null, name: name.trim(), type: type, _new: true });
      let searchKeys = { drivers: 'driverSearch', goals: 'goalSearch', constraints: 'constraintSearch', stakeholders: 'stakeholderSearch' };
      let resultKeys = { drivers: 'driverResults', goals: 'goalResults', constraints: 'constraintResults', stakeholders: 'stakeholderResults' };
      this[searchKeys[category]] = '';
      this[resultKeys[category]] = [];
    },

    removeMotivationElement(category, el) {
      this.scope[category] = this.scope[category].filter(function (e) {
        return (e.id || e.name) !== (el.id || el.name);
      });
    },

    // =========================================================================
    // Step 1: General ArchiMate element search (all layers)
    // =========================================================================

    async searchArchimateElements() {
      let q = this.archimateSearch.trim();
      if (q.length < 2) { this.archimateSearchResults = []; return; }
      try {
        let resp = await this._fetch(
          '/api/architecture-assistant/motivation-elements?q=' + encodeURIComponent(q)
        );
        // Filter out elements already linked
        let linked = (this.scope.archimate_elements || []).map(function (e) { return e.id; });
        this.archimateSearchResults = (resp.elements || resp.results || []).filter(function (el) {
          return linked.indexOf(el.id) === -1;
        });
      } catch (e) {
        this.archimateSearchResults = [];
      }
    },

    linkArchimateElement(el) {
      if (!this.scope.archimate_elements) this.scope.archimate_elements = [];
      let exists = this.scope.archimate_elements.find(function (e) { return e.id === el.id; });
      if (!exists) {
        this.scope.archimate_elements.push({
          id: el.id, name: el.name, type: el.type, layer: el.layer
        });
      }
      this.archimateSearch = '';
      this.archimateSearchResults = [];
    },

    unlinkArchimateElement(id) {
      this.scope.archimate_elements = (this.scope.archimate_elements || []).filter(function (e) {
        return e.id !== id;
      });
    },

    async openInlineCreate() {
      this.newElement.name = this.archimateSearch.trim();
      this.newElement.type = '';
      this.newElement.layer = '';
      this.newElementTypes = [];
      this.showCreateElementForm = true;
      this.archimateSearchResults = [];
      if (Object.keys(this.elementTypesByLayer).length === 0) {
        try {
          let resp = await this._fetch('/api/architecture-assistant/archimate-element-types');
          this.elementTypesByLayer = resp.types_by_layer || {};
        } catch (e) {
          this.showToast('Failed to load element types', 'error');
        }
      }
    },

    onLayerChange() {
      let layer = this.newElement.layer;
      this.newElementTypes = this.elementTypesByLayer[layer] || [];
      this.newElement.type = '';
    },

    async createArchimateElement() {
      let name = (this.newElement.name || '').trim();
      let type = this.newElement.type;
      let layer = this.newElement.layer;
      if (!name || !type || !layer) return;
      this.creatingElement = true;
      try {
        let resp = await this._post('/api/architecture-assistant/create-element', {
          name: name, type: type, layer: layer,
        });
        if (resp.element) {
          this.linkArchimateElement(resp.element);
          this.newElement = { name: '', type: '', layer: '' };
          this.newElementTypes = [];
          this.showCreateElementForm = false;
          this.archimateSearch = '';
          this.$nextTick(function () {
            if (window.lucide) window.lucide.createIcons();
          });
        }
      } catch (e) {
        this.showToast('Failed to create element: ' + (e.message || e), 'error');
      } finally {
        this.creatingElement = false;
      }
    },

    async generateProblemStatement() {
      if (!this.llmAvailable) return;
      this.problemLoading = true;
      try {
        let resp = await this._post('/api/architecture-assistant/generate-problem', {
          name: this.scope.name,
          domain: this.scope.business_domain,
          applications: this.scope.linked_applications.map(function (a) { return a.name; }),
          drivers: this.scope.drivers.map(function (d) { return d.name; }),
        });
        if (resp.problem_statement) {
          this.scope.business_problem = resp.problem_statement;
          // ENH-004: AI-generated scope needs human review before proceeding
          this.scopeApproved = false;
          this.scopeReviewPending = true;
        }
      } catch (e) {
        this.showToast('Problem statement generation failed', 'error');
      } finally {
        this.problemLoading = false;
      }
    },

    // ENH-004: Approve AI-extracted scope before proceeding to orchestration
    approveScope() {
      this.scopeApproved = true;
      this.scopeReviewPending = false;
      this.showToast('Scope approved — you may proceed to the next step', 'success');
    },

    // Step 1B: Navigate back to scope sub-phase
    backToScope() {
      this.step1Phase = 'scope';
      this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
    },

    // Step 1B: Run server-side contradiction detection
    async validateQualityBaseline() {
      this.qbValidating = true;
      try {
        let resp = await this._post('/api/architecture-assistant/wizard/validate-quality-baseline', {
          quality_baseline: this.qualityBaseline,
        });
        this.qualityBaselineWarnings = resp.warnings || [];
      } catch (e) {
        this.qualityBaselineWarnings = [];
      } finally {
        this.qbValidating = false;
      }
    },

    // Step 1B: Toggle quality baseline domain accordion; re-validate on close
    toggleQbDomain(domain) {
      let wasOpen = this.qbOpenDomain === domain;
      this.qbOpenDomain = wasOpen ? null : domain;
      if (wasOpen) {
        // User just finished editing this domain — re-validate
        let self = this;
        setTimeout(function () { self.validateQualityBaseline(); }, 200);
      }
    },

    // Step 1B: Check if a mandatory domain has its key field filled
    qbDomainComplete(domain) {
      let qb = this.qualityBaseline;
      let checks = {
        identity_access: qb.identity_access.auth_provider.trim() !== '',
        data_management: qb.data_management.primary_db.trim() !== '',
        security_controls: qb.security_controls.data_classification.trim() !== '',
        integration: qb.integration.api_style.length > 0,
        observability: qb.observability.logging_platform.trim() !== '',
        reliability: qb.reliability.availability_target.trim() !== '',
        performance: qb.performance.p99_latency_ms !== '',
        deployment_release: qb.deployment_release.hosting.trim() !== '',
        compliance_audit: true, // fully optional domain
        operational_support: qb.operational_support.support_tier.trim() !== '',
        testing_quality: qb.testing_quality.unit_coverage_target_pct !== '',
        cost_sustainability: qb.cost_sustainability.budget_model.trim() !== '',
      };
      return checks[domain] || false;
    },

    get qbCompleteness() {
      let domains = ['identity_access','data_management','security_controls','integration','observability','reliability','performance','deployment_release','compliance_audit','operational_support','testing_quality','cost_sustainability'];
      let self = this;
      let filled = domains.filter(function (d) { return self.qbDomainComplete(d); }).length;
      return Math.round(filled / domains.length * 100);
    },

    get qbMandatoryComplete() {
      let self = this;
      return ['identity_access','data_management','security_controls','integration','observability','reliability'].every(function (d) { return self.qbDomainComplete(d); });
    },

    // Step 1B: Toggle api_style multiselect
    toggleApiStyle(style) {
      let arr = this.qualityBaseline.integration.api_style;
      let idx = arr.indexOf(style);
      if (idx === -1) arr.push(style);
      else arr.splice(idx, 1);
    },

    // Step 1B: Toggle regulatory framework multiselect
    toggleRegulatoryFramework(fw) {
      let arr = this.qualityBaseline.compliance_audit.regulatory_frameworks;
      let idx = arr.indexOf(fw);
      if (idx === -1) arr.push(fw);
      else arr.splice(idx, 1);
    },

    // ENH-004: Reset scope approval when scope is manually edited
    onScopeEdited() {
      if (this.scopeReviewPending) {
        // Scope was AI-generated and is being edited — still needs approval
        this.scopeApproved = false;
      }
    },

    // =========================================================================
    // Step 2: Capability search
    // =========================================================================

    async searchCapabilities() {
      let q = this.capabilitySearch.trim();
      if (q.length < 2) { this.capabilitySearchResults = []; return; }
      try {
        let resp = await this._fetch('/capability-map/api/unified-capabilities?search=' + encodeURIComponent(q));
        this.capabilitySearchResults = resp.capabilities || resp || [];
        this.capabilityPage = 1;
      } catch (e) {
        this.capabilitySearchResults = [];
      }
    },

    // AA-010: Paginated slice of capability search results
    get paginatedCapabilities() {
      let start = (this.capabilityPage - 1) * this.capabilityPageSize;
      return this.capabilitySearchResults.slice(start, start + this.capabilityPageSize);
    },

    get capabilityTotalPages() {
      return Math.max(1, Math.ceil(this.capabilitySearchResults.length / this.capabilityPageSize));
    },

    capabilityPrevPage() {
      if (this.capabilityPage > 1) this.capabilityPage--;
    },

    capabilityNextPage() {
      if (this.capabilityPage < this.capabilityTotalPages) this.capabilityPage++;
    },

    addCapability(cap) {
      let exists = this.capabilities.find(function (c) { return c.id === cap.id; });
      if (!exists) {
        this.capabilities.push({
          id: cap.id,
          name: cap.name,
          level: cap.level || 1,
          maturity_current: 2,
          maturity_target: 4,
          from_app: false,
        });
      }
      this.capabilitySearch = '';
      this.capabilitySearchResults = [];
    },

    removeCapability(idx) {
      this.capabilities.splice(idx, 1);
    },

    openCapabilityModal() {
      if (typeof openUnifiedMappingModalDiscovery === 'function') {
        let self = this;
        openUnifiedMappingModalDiscovery({
          context: 'capability',
          allowTargetSelectOnly: true,
          onTargetSelected: function (target) {
            self.addCapability({ id: target.id, name: target.name });
          },
        });
      }
    },

    // =========================================================================
    // Step 3: Gap Analysis
    // =========================================================================

    async runGapAnalysis() {
      if (this.capabilities.length === 0) return;
      this.gapAnalysisLoading = true;
      try {
        let resp = await this._post('/api/architecture-assistant/analyze-gap', {
          solution_id: this.solutionId,
          capabilities: this.capabilities.map(function (c) {
            return { id: c.id, name: c.name, maturity_current: c.maturity_current, maturity_target: c.maturity_target };
          }),
        });
        this.gaps = (resp.gaps || []).map(function (g) {
          g.expanded = false;
          return g;
        });
        this.gapAnalysisAiGenerated = resp.ai_generated || false;
        this.affectedLayers = resp.affected_layers || [];
      } catch (e) {
        // Fallback: compute raw deltas locally
        this.gaps = this.capabilities
          .filter(function (c) { return c.maturity_target > c.maturity_current; })
          .map(function (c) {
            let delta = c.maturity_target - c.maturity_current;
            return {
              capability_id: c.id,
              capability_name: c.name,
              maturity_current: c.maturity_current,
              maturity_target: c.maturity_target,
              severity: delta >= 3 ? 'critical' : delta >= 2 ? 'high' : 'medium',
              description: '',
              impact: '',
              recommendation: '',
              expanded: false,
            };
          });
        this.gapAnalysisAiGenerated = false;
      } finally {
        this.gapAnalysisLoading = false;
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
      }
    },

    // =========================================================================
    // Step 4: Solution Options
    // =========================================================================

    async generateOptions() {
      if (this.gaps.length === 0) return;
      this.optionsLoading = true;
      try {
        let resp = await this._post('/api/architecture-assistant/generate-options', {
          solution_id: this.solutionId,
          gaps: this.gaps.map(function (g) { return { capability_id: g.capability_id, severity: g.severity }; }),
          constraints: this.scope.constraints.map(function (c) { return c.name; }),
        });
        this.options = (resp.options || []).map(function (opt) {
          opt.ai_generated = true;
          return opt;
        });
      } catch (e) {
        this.showToast('Option generation failed', 'error');
      } finally {
        this.optionsLoading = false;
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
      }
    },

    // ENH-007: Vendor/product search state for option validation
    optionVendorSearch: '',
    optionVendorResults: [],
    optionVendorWarning: '',

    addManualOption() {
      this.options.push({
        id: 'manual-' + Date.now(),
        name: 'Option ' + (this.options.length + 1),
        description: '',
        vendor_name: '',
        vendor_id: null,
        vendor_validated: false,
        strategic_fit: 0,
        risk_score: 0,
        coverage: 0,
        total_cost: '',
        timeline: '',
        pros: [],
        cons: [],
        from_catalog: false,
        ai_generated: false,
      });
    },

    // ENH-007: Search vendors for option validation
    async searchOptionVendors(query) {
      if (!query || query.trim().length < 2) {
        this.optionVendorResults = [];
        return;
      }
      try {
        let resp = await this._fetch('/api/vendors?search=' + encodeURIComponent(query.trim()));
        this.optionVendorResults = resp.vendors || [];
      } catch (e) {
        this.optionVendorResults = [];
      }
    },

    // ENH-007: Validate vendor name against catalog
    async validateOptionVendor(opt) {
      let name = (opt.vendor_name || '').trim();
      if (!name) {
        opt.vendor_validated = false;
        opt.vendor_id = null;
        this.optionVendorWarning = '';
        return;
      }
      try {
        let resp = await this._fetch('/api/vendors?search=' + encodeURIComponent(name));
        let vendors = resp.vendors || [];
        let exact = vendors.find(function (v) { return v.name && v.name.toLowerCase() === name.toLowerCase(); });
        if (exact) {
          opt.vendor_id = exact.id;
          opt.vendor_validated = true;
          this.optionVendorWarning = '';
        } else {
          opt.vendor_id = null;
          opt.vendor_validated = false;
          this.optionVendorWarning = 'Vendor "' + name + '" not found in catalog. Consider selecting from existing vendors.';
        }
      } catch (e) {
        opt.vendor_validated = false;
        this.optionVendorWarning = '';
      }
    },

    // ENH-007: Select vendor from search results for an option
    selectOptionVendor(opt, vendor) {
      opt.vendor_name = vendor.name;
      opt.vendor_id = vendor.id;
      opt.vendor_validated = true;
      this.optionVendorResults = [];
      this.optionVendorSearch = '';
      this.optionVendorWarning = '';
    },

    selectOption(id) {
      this.selectedOptionId = this.selectedOptionId === id ? null : id;
    },

    async compareOptions() {
      if (this.options.length < 2) {
        this.showToast('Add at least 2 options to compare', 'warning');
        return;
      }
      let solutionId = this.solutionId || (window.__WIZARD_CONFIG__ && window.__WIZARD_CONFIG__.solutionId);
      if (!solutionId) {
        this.showToast('Save the solution first', 'warning');
        return;
      }
      try {
        let resp = await fetch('/api/architecture-assistant/wizard/compare-options?solution_id=' + solutionId, {
          headers: { 'Accept': 'application/json' },
          credentials: 'same-origin',
        });
        if (!resp.ok) {
          let err = {};
          try { err = await resp.json(); } catch (_) {}
          throw new Error(err.error || 'Comparison failed');
        }
        this.comparisonData = await resp.json();
        this.compareModalOpen = true;
        let self = this;
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
      } catch (e) {
        this.showToast('Failed to load comparison: ' + e.message, 'error');
      }
    },

    // =========================================================================
    // Step 5: Roadmap
    // =========================================================================

    async generateRoadmap() {
      if (!this.selectedOptionId) return;
      this.roadmapLoading = true;
      try {
        let resp = await this._post('/api/architecture-assistant/roadmap-elements', {
          solution_id: this.solutionId,
          selected_option_id: this.selectedOptionId,
          constraints: this.scope.constraints.map(function (c) { return c.name; }),
        });
        this.roadmap.plateaus = resp.plateaus || [];
        this.roadmap.workPackages = resp.work_packages || [];
        this.roadmap._ai_generated = true;
      } catch (e) {
        this.showToast('Roadmap generation failed', 'error');
      } finally {
        this.roadmapLoading = false;
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
      }
    },

    addWorkPackage() {
      this.roadmap.workPackages.push({
        id: 'wp-' + Date.now(),
        name: 'Work Package ' + (this.roadmap.workPackages.length + 1),
        plateau: this.roadmap.plateaus.length > 0 ? this.roadmap.plateaus[0].name : '',
        duration: '',
        dependencies: [],
      });
    },

    removeWorkPackage(idx) {
      this.roadmap.workPackages.splice(idx, 1);
    },

    addPlateau() {
      this.roadmap.plateaus.push({
        id: 'plateau-' + Date.now(),
        name: 'Plateau ' + (this.roadmap.plateaus.length + 1),
        duration: '',
      });
      this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
    },

    async autoSequence() {
      if (this.roadmap.workPackages.length === 0) return;
      try {
        let resp = await this._post('/api/architecture-assistant/auto-sequence', {
          work_packages: this.roadmap.workPackages,
          plateaus: this.roadmap.plateaus,
        });
        if (resp.work_packages) this.roadmap.workPackages = resp.work_packages;
        if (resp.plateaus) this.roadmap.plateaus = resp.plateaus;
      } catch (e) {
        this.showToast('Auto-sequence failed', 'error');
      }
    },

    // =========================================================================
    // Step 6: ARB Draft
    // =========================================================================

    async generateARBDraft() {
      this.arbLoading = true;
      try {
        let resp = await this._post('/api/architecture-assistant/draft-arb', {
          solution_id: this.solutionId,
        });
        this.arbDraft = resp.draft || resp || {};
        this.arbDraft.ai_generated = resp.ai_generated || false;
        // ENH-005: AI-generated drafts require approval before submission
        if (this.arbDraft.ai_generated) {
          this.arbDraft.approval_status = 'pending_review';
        }
        this.arbDraftOriginal = JSON.parse(JSON.stringify(this.arbDraft));
      } catch (e) {
        // Fallback: create editable template from existing data
        this.arbDraft = {
          business_justification: this.scope.business_problem || '',
          technical_assessment: '',
          risk_analysis: '',
          implementation_approach: '',
          cost_summary: '',
          archimate_count: 0,
          relationship_count: 0,
          ai_generated: false,
        };
        this.arbDraftOriginal = JSON.parse(JSON.stringify(this.arbDraft));
      } finally {
        this.arbLoading = false;
        this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
      }
    },

    async submitToARB() {
      if (!this.arbDraft || !this.solutionId) return;

      // ENH-005: Block submission if AI-generated draft has not been approved
      if (this.arbDraft.ai_generated && this.arbDraft.approval_status === 'pending_review') {
        this.showToast('AI-generated ARB draft requires approval before submission. Please review and approve the draft first.', 'warning');
        return;
      }

      try {
        await this._post('/api/architecture-assistant/wizard/save-step', {
          step: 6,
          solution_id: this.solutionId,
          arb_draft: this.arbDraft,
          submit: true,
        });
        this.showToast('Solution submitted to ARB for review', 'success');
      } catch (e) {
        this.showToast('ARB submission failed: ' + (e.message || 'Unknown error'), 'error');
      }
    },

    // ENH-005: Approve the ARB draft for submission
    approveARBDraft() {
      if (!this.arbDraft) return;
      this.arbDraft.approval_status = 'approved';
      this.showToast('ARB draft approved for submission', 'success');
    },

    // AA-009: Check if a draft section has been edited from original
    isArbSectionEdited(field) {
      if (!this.arbDraftOriginal || !this.arbDraft) return false;
      return (this.arbDraft[field] || '') !== (this.arbDraftOriginal[field] || '');
    },

    // AA-009: Check if any draft section has unsaved edits
    hasArbDraftEdits() {
      let fields = ['business_justification', 'technical_assessment', 'risk_analysis', 'implementation_approach', 'cost_summary'];
      let self = this;
      return fields.some(function (f) { return self.isArbSectionEdited(f); });
    },

    // AA-009: Save edited draft content to server
    async saveArbDraftEdits() {
      if (!this.arbDraft || !this.solutionId) return;
      this.arbDraftSaving = true;
      try {
        await this._post('/api/architecture-assistant/wizard/save-step', {
          step: 6,
          solution_id: this.solutionId,
          arb_draft: this.arbDraft,
        });
        this.arbDraftOriginal = JSON.parse(JSON.stringify(this.arbDraft));
        this.showToast('Draft edits saved', 'success');
      } catch (e) {
        this.showToast('Failed to save edits: ' + (e.message || 'Unknown error'), 'error');
      } finally {
        this.arbDraftSaving = false;
      }
    },

    async downloadDraft() {
      if (!this.solutionId || !this.arbDraft) return;
      // Save edited draft content before exporting so the server has the latest edits
      try {
        await this._post('/api/architecture-assistant/wizard/save-step', {
          step: 6,
          solution_id: this.solutionId,
          arb_draft: this.arbDraft,
        });
      } catch (e) {
        // Proceed with download even if save fails
      }
      window.open('/api/architecture-assistant/export-arb/' + this.solutionId + '?format=pdf', '_blank');
    },

    // =========================================================================
    // Step 7: Execution Tracking
    // =========================================================================

    addExecutionItem() {
      this.executionItems.push({
        work_package_name: '',
        status: 'planned',
        percent_complete: 0,
        milestone_name: '',
        blockers: '',
      });
      this.$nextTick(function () { if (window.lucide) window.lucide.createIcons(); });
    },

    initComposer() {
      let self = this;
      if (!this.solutionId) {
        this.composerStatus = 'Save solution first to enable diagram editing';
        return;
      }
      let container = document.getElementById('wizard-composer-canvas');
      if (!container || typeof ComposerRenderer === 'undefined') return;

      // Destroy previous instance if reinitializing
      if (this.composerRenderer) {
        this.composerRenderer.destroy();
        this.composerRenderer = null;
      }

      this.composerRenderer = ComposerRenderer.create(container, {
        mode: 'edit',
        height: 400,
      });

      fetch('/solutions/' + this.solutionId + '/archimate-elements', { credentials: 'same-origin' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          let allElements = [];
          let layers = data.elements_by_layer || {};
          Object.keys(layers).forEach(function(layer) {
            layers[layer].forEach(function(el) {
              el.layer = layer;
              allElements.push(el);
            });
          });
          if (allElements.length > 0) {
            self.composerRenderer.loadElements(allElements, []);
            self.composerRenderer.fitToContent();
            self.composerStatus = allElements.length + ' elements loaded';
          } else {
            self.composerStatus = 'No elements yet';
          }
        })
        .catch(function(err) {
          self.composerStatus = 'Error loading elements';
          console.error('[Wizard Composer]', err);
        });
    },

    // =========================================================================
    // Persistence
    // =========================================================================

    async saveDraft() {
      await this._saveCurrentStep();
    },

    async _saveCurrentStep() {
      this.saving = true;
      try {
        let payload = {
          step: this.currentStep,
          solution_id: this.solutionId,
        };

        switch (this.currentStep) {
          case 1:
            payload.scope = this.scope;
            payload.quality_baseline = this.qualityBaseline;
            break;
          case 2:
            payload.capabilities = this.capabilities;
            break;
          case 3:
            payload.gaps = this.gaps;
            break;
          case 4:
            payload.selected_option_id = this.selectedOptionId;
            payload.options = this.options;
            break;
          case 5:
            payload.roadmap = this.roadmap;
            break;
          case 6:
            payload.arb_draft = this.arbDraft;
            break;
          case 7:
            payload.execution_items = this.executionItems;
            break;
          case 8:
            payload.checkpoints = this.governanceCheckpoints;
            break;
          case 9:
            payload.metrics = this.outcomeMetrics;
            payload.lessons = this.lessonsLearned;
            break;
        }

        let resp = await this._post('/api/architecture-assistant/wizard/save-step', payload);

        // First save creates the solution — capture ID and update URL
        if (resp.solution_id && !this.solutionId) {
          this.solutionId = resp.solution_id;
          this._updateURL();
        }

        this.showToast('Draft saved', 'success');
        return true;
      } catch (e) {
        let msg = e.message || 'Unknown error';
        if (msg.indexOf('modified by another user') !== -1) {
          this.showToast('Solution was modified by another user. Please refresh.', 'warning');
        } else {
          this.showToast('Save failed: ' + msg, 'error');
        }
        return false;
      } finally {
        this.saving = false;
      }
    },

    // =========================================================================
    // HTTP helpers
    // =========================================================================

    async _fetch(url) {
      let resp = await fetch(url, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin',
      });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    },

    async _post(url, data) {
      let headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };
      if (this.csrfToken) {
        headers['X-CSRFToken'] = this.csrfToken;
      }
      let resp = await fetch(url, {
        method: 'POST',
        headers: headers,
        credentials: 'same-origin',
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        let errText = '';
        try { errText = (await resp.json()).error || ''; } catch (_) {}
        throw new Error(errText || 'HTTP ' + resp.status);
      }
      return resp.json();
    },
  };
}

// Register with Alpine
document.addEventListener('alpine:init', function () {
  Alpine.data('architectureWizard', architectureWizard);
});
