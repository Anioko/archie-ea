(function (global) {
    'use strict';

    const API_BASE = '/solutions';

    /**
     * Safe fetch wrapper.
     * - Auto-injects CSRF token from <meta name="csrf-token">
     * - Rejects on non-2xx HTTP status (so .catch() fires on 404/500)
     * - Always returns parsed JSON
     */
    function _fetch(url, opts) {
        opts = opts || {};
        opts.credentials = 'same-origin';
        if (!opts.headers) opts.headers = {};
        const csrf = document.querySelector('meta[name=csrf-token]');
        if (csrf) opts.headers['X-CSRFToken'] = csrf.content;
        return fetch(url, opts).then(function (r) {
            if (!r.ok) {
                return r.json().catch(function () { return {}; }).then(function (body) {
                    const err = new Error(body.error || ('HTTP ' + r.status));
                    err.status = r.status;
                    err.body = body;
                    throw err;
                });
            }
            return r.json();
        });
    }

    global.journeyFlow = function (solutionId) {
        return {
            solutionId: solutionId,
            currentStep: 1,
            completedSteps: [],
            solution: null,
            isProcessing: false,
            processingLabel: 'Analyzing...',

            // Co-pilot
            copilotMessage: 'Describe your business problem to get started.',
            copilotSuggestions: [],

            // Entity counts (shown in co-pilot panel)
            entityCounts: { drivers: 0, goals: 0, capabilities: 0, requirements: 0, apps: 0, elements: 0 },

            // Step 1 data
            inputMode: 'type',
            brief: '',
            uploadedFile: null,
            uploading: false,
            motivationElements: [],

            // Step 2 data
            capabilitySearch: '',
            capabilityResults: [],
            selectedCapabilities: [],
            derivedRequirements: [],

            // Capability catalog (loaded once on init)
            allCapabilities: [],
            capabilitiesLoaded: false,

            // AI-suggested capabilities (from intelligence chain)
            suggestedCapabilities: [],
            suggestionsLoading: false,

            // Three-tier AI suggestions (from backend matching)
            suggestedExisting: [],     // match_type === 'exact'
            suggestedPartial: [],      // match_type === 'partial'
            suggestedNovel: [],        // match_type === 'novel'
            gapSummary: '',            // from LLM response

            // Capability tree (Wave 5) — open by default for browse-first UX
            showCapabilityTree: true,
            capabilityTreeData: [],
            capabilityTreeLoading: false,
            treeFilter: '',

            // Step 2b: System Capability Blueprint (TCM + ACM)
            technicalCapabilities: [],
            applicationCapabilities: [],
            systemCapsLoading: false,
            systemCapsGenerated: false,

            // Duplicate generation guard
            showRegenerateWarning: false,
            regenerateConfirmed: false,

            // Architecture generation idempotency
            _architectureGeneratedForCaps: '',

            // Step 3 data — architecture element review (Wave 6)
            architectureElements: [],
            archElementsLoading: false,

            // Step 5 data — implementation element review (Wave 6)
            implementationElements: [],
            implElementsLoading: false,

            // Inline edit state
            editingElement: null,
            editName: '',
            editDescription: '',

            // Manual element addition
            addElementLayer: null,
            addElementName: '',
            addElementType: '',
            addElementDesc: '',

            // Relationship drawing (connect mode)
            connectMode: false,
            connectSource: null,
            connectValidTypes: [],
            connectPickerOpen: false,

            // Decision tracking (Wave 6)
            elementDecisions: [],
            _consecutiveNewRejections: 0,
            suppressNewSuggestions: false,
            whyModalElement: null,

            // Change propagation + versioning (Wave 7)
            staleElementIds: [],
            snapshots: [],
            snapshotCompare: null,
            showVersionPanel: false,

            // Quality score (Wave 10)
            qualityScore: null,

            // Traceability chain (loaded on demand in Step 6)
            traceabilityData: null,
            traceabilityLoading: false,
            showTraceability: false,

            // Step 4 data — options comparison
            solutionOptions: [],
            optionsLoading: false,
            selectedOptionIdx: -1,

            // Step 6 data
            completenessScore: 0,
            blockingIssues: [],

            // ── Initialization ────────────────────────────────────────

            init: function () {
                let self = this;
                self.$nextTick(function () { self.loadSolution(); });
            },

            loadSolution: function () {
                let self = this;

                // Load brief from hidden input (set by server template)
                const briefEl = document.getElementById('journey-solution-description');
                if (briefEl && briefEl.value) {
                    self.brief = briefEl.value;
                }

                // Load both in parallel with error handling and retry
                let entitiesLoaded = false;
                let capsLoaded = false;

                function _checkAndTriggerSuggestions() {
                    if (entitiesLoaded && capsLoaded) {
                        if (self.motivationElements.length > 0 && self.capabilitiesLoaded) {
                            self.suggestCapabilitiesFromEntities();
                        }
                        self._restoreStepProgress();
                        self.updateEntityCounts();
                    }
                }

                self.loadGeneratedEntities()
                    .then(function () { entitiesLoaded = true; _checkAndTriggerSuggestions(); })
                    .catch(function (e) {
                        console.error('Failed to load entities:', e);
                        self.copilotMessage = 'Failed to load motivation elements. Retrying...';
                        // Retry once after 2s
                        setTimeout(function () {
                            self.loadGeneratedEntities()
                                .then(function () { entitiesLoaded = true; _checkAndTriggerSuggestions(); })
                                .catch(function () { self.copilotMessage = 'Could not load motivation elements. Try refreshing the page.'; });
                        }, 2000);
                    });

                self.loadAllCapabilities()
                    .then(function () { capsLoaded = true; _checkAndTriggerSuggestions(); })
                    .catch(function (e) {
                        console.error('Failed to load capabilities:', e);
                        // Retry once after 2s
                        setTimeout(function () {
                            self.loadAllCapabilities()
                                .then(function () { capsLoaded = true; _checkAndTriggerSuggestions(); })
                                .catch(function () { console.error('Capabilities retry failed'); });
                        }, 2000);
                    });

                // Restore persisted capability blueprint
                self.loadCapabilityBlueprint();
            },

            updateEntityCounts: function () {
                this.entityCounts = {
                    drivers: this.motivationElements.filter(function (e) { return e.type === 'Driver'; }).length,
                    goals: this.motivationElements.filter(function (e) { return e.type === 'Goal'; }).length,
                    capabilities: this.selectedCapabilities.length,
                    requirements: this.derivedRequirements.length,
                    apps: 0,
                    elements: this.motivationElements.length,
                };
            },

            _restoreStepProgress: function () {
                // Detect which steps are already complete based on persisted data
                const hasMotivation = this.motivationElements.length >= 2;
                const hasCaps = this.selectedCapabilities.length >= 1;
                const hasArch = this.architectureElements && this.architectureElements.length > 0;
                const hasImpl = this.implementationElements && this.implementationElements.length > 0;

                if (hasMotivation && this.completedSteps.indexOf(1) === -1) this.completedSteps.push(1);
                if (hasCaps && this.completedSteps.indexOf(2) === -1) this.completedSteps.push(2);
                if (hasArch && this.completedSteps.indexOf(3) === -1) this.completedSteps.push(3);
                if (hasImpl && this.completedSteps.indexOf(4) === -1) this.completedSteps.push(4);

                // Jump to the furthest incomplete step
                if (hasImpl) { this.currentStep = 5; this.loadImplementationElements(); }
                else if (hasArch) this.currentStep = 4;
                else if (hasCaps) this.currentStep = 3;
                else if (hasMotivation) this.currentStep = 2;

                // Auto-load capability tree when landing on Step 2
                if (this.currentStep === 2 && this.capabilityTreeData.length === 0) {
                    this.loadCapabilityTree();
                }
            },

            // ── Step navigation ───────────────────────────────────────

            canProceed: function () {
                switch (this.currentStep) {
                    case 1: return this.brief.length >= 20 || this.motivationElements.length >= 2;
                    case 2: return this.selectedCapabilities.length >= 1;
                    case 3: return true;
                    case 4: return true;
                    case 5: return true;
                    default: return true;
                }
            },

            canSubmit: function () {
                return this.completedSteps.length >= 2;
            },

            nextStep: function () {
                if (!this.canProceed()) return;
                if (this.completedSteps.indexOf(this.currentStep) === -1) {
                    this.completedSteps.push(this.currentStep);
                    // Wave 7: Auto-snapshot on step completion
                    this.createSnapshot(this.currentStep);
                }

                // === INTELLIGENCE CHAIN: generate architecture when leaving Step 2 ===
                if (this.currentStep === 2 && this.selectedCapabilities.length > 0) {
                    let self = this;
                    self.isProcessing = true;
                    self.processingLabel = 'Generating strategy + architecture layers from ' + self.selectedCapabilities.length + ' capabilities...';
                    self.copilotMessage = 'Generating architecture: Strategy layer first, then Business + Technology in parallel, then Application. This takes 30-60 seconds.';
                    self.generateStrategyLayer().then(function () {
                        return self.generateArchitectureFromCapabilities();
                    }).then(function () {
                        self.isProcessing = false;
                        self.copilotMessage = 'Architecture generated. Review the elements in Step 3 — accept, reject, or ask "Why?" for each.';
                    }).catch(function () {
                        self.isProcessing = false;
                    });
                }

                // === INTELLIGENCE CHAIN: generate implementation when leaving Step 4 ===
                if (this.currentStep === 4 && this.selectedCapabilities.length > 0) {
                    const self2 = this;
                    self2.isProcessing = true;
                    self2.processingLabel = 'Generating migration plan: work packages, plateaus, deliverables...';
                    self2.copilotMessage = 'Creating implementation plan with work packages, gap analysis, and transition plateaus. This takes 15-30 seconds.';
                    // Wrap in promise to clear processing state
                    Promise.resolve().then(function () {
                        return self2.generateImplementationLayer();
                    }).then(function () {
                        self2.isProcessing = false;
                        self2.copilotMessage = 'Implementation plan generated. Review work packages and milestones in Step 5.';
                    }).catch(function () {
                        self2.isProcessing = false;
                    });
                }

                this.currentStep = Math.min(this.currentStep + 1, 6);
                this.updateCopilot();
                this.updateEntityCounts();

                // Auto-actions on entering certain steps
                if (this.currentStep === 2) {
                    // Auto-load tree when entering Step 2
                    if (this.capabilityTreeData.length === 0) {
                        this.loadCapabilityTree();
                    }
                    if (this.suggestedCapabilities.length > 0) {
                        this.copilotMessage = 'I found ' + this.suggestedCapabilities.length + ' capabilities that match your drivers and goals. Browse the tree below — AI suggestions are highlighted.';
                    } else {
                        this.copilotMessage = 'Browse the capability tree to find relevant capabilities. Use search for semantic matching (e.g., "CRM" finds "Customer Relationship Management").';
                    }
                }
                if (this.currentStep === 3 && this.architectureElements.length === 0) {
                    this.loadArchitectureElements();
                }
                if (this.currentStep === 4 && this.solutionOptions.length === 0) {
                    this.loadOptions();
                }
                if (this.currentStep === 5 && this.implementationElements.length === 0) {
                    this.loadImplementationElements();
                }
                if (this.currentStep === 6) {
                    this.loadCompleteness();
                }
            },

            prevStep: function () {
                this.currentStep = Math.max(this.currentStep - 1, 1);
                this.updateCopilot();
            },

            goToStep: function (step) {
                const maxReached = this.completedSteps.length > 0 ? Math.max.apply(null, this.completedSteps) + 1 : 1;
                if (step <= maxReached) {
                    this.currentStep = step;
                    this.updateCopilot();
                }
            },

            // ── Dynamic co-pilot (context-aware) ─────────────────────

            updateCopilot: function () {
                let self = this;
                const dCount = self.entityCounts.drivers || 0;
                const gCount = self.entityCounts.goals || 0;
                const capCount = self.selectedCapabilities.length;
                const sugCount = self.suggestedCapabilities.length;

                switch (self.currentStep) {
                    case 1:
                        if (self.motivationElements.length > 0) {
                            self.copilotMessage = self.motivationElements.length + ' entities generated. Edit or remove any, then proceed to capabilities.';
                        } else {
                            self.copilotMessage = 'Describe the business problem you\'re solving. I\'ll extract stakeholders, drivers, and goals.';
                        }
                        break;
                    case 2:
                        if (sugCount > 0) {
                            self.copilotMessage = 'Based on your ' + dCount + ' drivers and ' + gCount + ' goals, I suggest ' + sugCount + ' capabilities. Accept or search for more.';
                        } else if (capCount > 0) {
                            self.copilotMessage = capCount + ' capabilities selected. Click "Generate Requirements" to derive EARS-format requirements, or search for more.';
                        } else if (dCount > 0 || gCount > 0) {
                            self.copilotMessage = 'You have ' + dCount + ' drivers and ' + gCount + ' goals. Search the 516 capabilities to find matches.';
                        } else {
                            self.copilotMessage = 'Select the capabilities your solution needs. I\'ll identify gaps and derive requirements.';
                        }
                        break;
                    case 3:
                        if (capCount > 0) {
                            self.copilotMessage = 'Generating architecture from your ' + capCount + ' capabilities. Elements span business, application, and technology layers.';
                        } else {
                            self.copilotMessage = 'Review the architecture elements across business, application, and technology layers.';
                        }
                        break;
                    case 4:
                        self.copilotMessage = 'Review solution options scored on strategic fit, risk, cost, and complexity.';
                        break;
                    case 5:
                        self.copilotMessage = 'Review the migration plan with work packages and transition plateaus.';
                        break;
                    case 6:
                        if (self.completenessScore > 0) {
                            self.copilotMessage = 'SAD completeness: ' + self.completenessScore + '%. ' + (self.blockingIssues.length > 0 ? self.blockingIssues.length + ' issues to resolve.' : 'Ready for ARB submission.');
                        } else {
                            self.copilotMessage = 'Review your complete SAD. Submit to ARB when all blocking issues are resolved.';
                        }
                        break;
                    default:
                        self.copilotMessage = '';
                }
            },

            // ── Step 1: Generate motivation elements from brief ───────

            generateFromBrief: function () {
                let self = this;
                if (self.brief.length < 20 || self.isProcessing) return;

                // Duplicate guard: if entities already exist, confirm before regenerating
                if (self.motivationElements.length > 0 && !self.regenerateConfirmed) {
                    self.showRegenerateWarning = true;
                    return;
                }
                self.regenerateConfirmed = false;
                self.showRegenerateWarning = false;

                self.isProcessing = true;
                self.processingLabel = 'AI is generating architecture elements from your brief...';

                _fetch('/solutions/' + self.solutionId + '/generate-draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_statement: self.brief })
                }).then(function (data) {
                    if (data.success) {
                        const created = data.created || {};
                        let total = data.total || 0;

                        self.copilotMessage = data.summary || ('Generated ' + total + ' entities. Loading details...');
                        self.entityCounts.drivers = created.drivers || 0;
                        self.entityCounts.goals = created.goals || 0;
                        self.entityCounts.requirements = created.requirements || 0;
                        self.entityCounts.elements = total;

                        // Fetch actual entity names, then trigger intelligence chain
                        self.loadGeneratedEntities().then(function () {
                            self.suggestCapabilitiesFromEntities();
                        });
                    } else {
                        self.copilotMessage = 'Generation failed: ' + (data.error || 'Unknown error. Check API key settings.');
                    }
                }).catch(function (e) {
                    console.error('Generation failed:', e);
                    self.copilotMessage = 'Generation failed: ' + (e.message || 'Unknown error') + '. Check that LLM API keys are configured in Admin > API Settings.';
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            confirmRegenerate: function () {
                this.regenerateConfirmed = true;
                this.showRegenerateWarning = false;
                this.motivationElements = [];
                this.suggestedCapabilities = [];
                this._architectureGeneratedForCaps = '';
                this.generateFromBrief();
            },

            cancelRegenerate: function () {
                this.showRegenerateWarning = false;
                this.regenerateConfirmed = false;
            },

            /**
             * Loads entities from server. Returns a Promise so callers can chain.
             */
            loadGeneratedEntities: function () {
                let self = this;
                const base = '/solutions/' + self.solutionId;

                const endpoints = [
                    { url: base + '/stakeholders', type: 'Stakeholder', layer: 'Motivation' },
                    { url: base + '/drivers', type: 'Driver', layer: 'Motivation' },
                    { url: base + '/goals', type: 'Goal', layer: 'Motivation' },
                    { url: base + '/constraints', type: 'Constraint', layer: 'Motivation' },
                    { url: base + '/requirements', type: 'Requirement', layer: 'Motivation' },
                    { url: base + '/risks', type: 'Assessment', layer: 'Motivation', nameField: 'risk_description' },
                    { url: base + '/motivation-elements', type: null, layer: 'Motivation' },
                ];

                const fetches = endpoints.map(function (ep) {
                    return fetch(ep.url, { credentials: 'same-origin' })
                        .then(function (r) { return r.ok ? r.json() : { data: [] }; })
                        .then(function (d) { return { type: ep.type, layer: ep.layer, nameField: ep.nameField, items: d.data || d.items || d || [] }; })
                        .catch(function () { return { type: ep.type, layer: ep.layer, nameField: ep.nameField, items: [] }; });
                });

                return Promise.all(fetches).then(function (results) {
                    let elements = [];
                    let driverCount = 0;
                    let goalCount = 0;
                    let reqCount = 0;

                    results.forEach(function (result) {
                        if (!Array.isArray(result.items)) return;
                        result.items.forEach(function (item) {
                            const elType = result.type || item.type || 'Unknown';
                            // Dedup by id+type (motivation-elements may overlap with specific endpoints)
                            const key = elType + ':' + item.id;
                            if (elements.some(function(e) { return (e.type + ':' + e.id) === key; })) return;
                            // Use endpoint-specific nameField if provided (e.g. risk_description for risks)
                            let elName = (result.nameField ? item[result.nameField] : null) || item.name || item.aspect || item.description || item.title;
                            if (!elName || elName === elType) elName = (item.description || item.risk_description || item.statement || '').substring(0, 60) || elType;
                            elements.push({
                                name: elName,
                                type: elType,
                                layer: result.layer,
                                description: item.description || item.current_state || item.statement || item.rationale || '',
                                accepted: true,
                                ai: !!item.ai_generated,
                                id: item.id,
                                impact_level: item.impact_level,
                                priority: item.priority,
                                urgency: item.urgency,
                                measurement_criteria: item.measurement_criteria,
                                gap_severity: item.gap_severity,
                            });
                        });
                        if (result.type === 'Driver') driverCount = result.items.length;
                        if (result.type === 'Goal') goalCount = result.items.length;
                        if (result.type === 'Requirement') reqCount = result.items.length;
                    });

                    self.motivationElements = elements;
                    self.entityCounts.drivers = driverCount;
                    self.entityCounts.goals = goalCount;
                    self.entityCounts.requirements = reqCount;
                    self.entityCounts.elements = elements.length;

                    if (elements.length > 0) {
                        self.copilotMessage = elements.length + ' entities found. Review them below, then proceed to capabilities.';
                    }
                });
            },

            removeMotivationElement: function (idx) {
                this.motivationElements.splice(idx, 1);
                this.updateEntityCounts();
            },

            toggleElementAccepted: function (idx) {
                this.motivationElements[idx].accepted = !this.motivationElements[idx].accepted;
            },

            saveElementEdit: function (el) {
                // Persist inline edits back to the server
                if (!el || !el.id) return;
                let self = this;
                const payload = { name: el.name, description: el.description || '' };
                if (el.impact_level !== undefined) payload.impact_level = el.impact_level;
                if (el.priority !== undefined) payload.priority = el.priority;
                if (el.measurement_criteria !== undefined) payload.measurement_criteria = el.measurement_criteria;

                _fetch(API_BASE + '/' + self.solutionId + '/entities/' + el.id, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).then(function () {
                    el._saved = true;
                    setTimeout(function () { el._saved = false; }, 2000);
                }).catch(function () {
                    // Silent fail — edit stays in local state
                });
            },

            // ── Step 4: Options Comparison ─────────────────────────────
            addOption: function () {
                this.solutionOptions.push({
                    name: '',
                    approach: '',
                    estimated_cost: null,
                    timeline: '',
                    risk_level: '',
                    score: 5,
                    rationale: '',
                    recommended: false,
                });
            },

            saveOptions: function () {
                let self = this;
                _fetch(API_BASE + '/' + self.solutionId + '/update-json', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ options: self.solutionOptions })
                }).catch(function () {});
            },

            loadOptions: function () {
                let self = this;
                // First try loading existing options from solution data
                _fetch(API_BASE + '/' + self.solutionId).then(function (data) {
                    if (data && data.options && data.options.length > 0) {
                        self.solutionOptions = data.options;
                    } else if (self.solutionOptions.length === 0 && !self.optionsLoading) {
                        // No options exist — auto-generate variants
                        self.generateVariants();
                    }
                }).catch(function () {});
            },

            generateVariants: function () {
                let self = this;
                if (self.optionsLoading) return;
                self.optionsLoading = true;
                self.copilotMessage = 'Generating 3 architecture options (cost-optimized, timeline-optimized, risk-balanced)...';

                _fetch(API_BASE + '/' + self.solutionId + '/generate-variants', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                }).then(function (data) {
                    if (data.success && data.variants) {
                        self.solutionOptions = data.variants.map(function (v, i) {
                            v._selected = false;
                            v._idx = i;
                            return v;
                        });
                        self.copilotMessage = 'Generated 3 options. Compare trade-offs and select one to drive implementation.';
                    } else {
                        self.copilotMessage = 'Option generation failed: ' + (data.error || 'Unknown error. You can proceed without options.');
                    }
                }).catch(function (e) {
                    console.error('Variant generation failed:', e);
                    self.copilotMessage = 'Option generation failed. You can still proceed.';
                }).then(function () {
                    self.optionsLoading = false;
                });
            },

            selectOption: function (idx) {
                this.selectedOptionIdx = idx;
                const opt = this.solutionOptions[idx];
                if (opt) {
                    this.copilotMessage = 'Selected: "' + opt.name + '". Proceed to Step 5 to plan the implementation.';
                }
            },

            // ── Intelligence Chain: Step 1 → Step 2 ──────────────────

            /**
             * Two-phase capability suggestion:
             *   Phase 1 (instant): keyword match driver/goal names against 516 capabilities
             *   Phase 2 (async):   LLM call to ai-suggest-capabilities, merge results
             *
             * Called after generateFromBrief succeeds AND entities are loaded.
             * No polling — uses Promise chain from loadGeneratedEntities().
             */
            suggestCapabilitiesFromEntities: function () {
                let self = this;

                // Guard: need both entities and capability catalog
                if (self.motivationElements.length === 0 || !self.capabilitiesLoaded) {
                    return;
                }

                // Phase 1: Instant keyword matching — extract from brief + driver/goal names
                const stopwords = ['with', 'from', 'that', 'this', 'will', 'must', 'should', 'have', 'been',
                    'into', 'each', 'more', 'also', 'than', 'need', 'ensure', 'needs', 'currently',
                    'running', 'over', 'across', 'budget', 'months', 'years', 'team', 'must', 'comply'];
                let keywords = [];
                // Extract from brief (the problem description itself)
                if (self.brief) {
                    (self.brief).toLowerCase().split(/[\s,\-\/\.\(\)]+/).forEach(function (w) {
                        if (w.length > 4 && stopwords.indexOf(w) === -1) {
                            keywords.push(w);
                        }
                    });
                }
                // Extract from driver/goal names
                self.motivationElements.forEach(function (el) {
                    if (el.type === 'Driver' || el.type === 'Goal') {
                        const words = (el.name || '').toLowerCase().split(/[\s,\-\/]+/);
                        words.forEach(function (w) {
                            if (w.length > 3 && stopwords.indexOf(w) === -1) {
                                keywords.push(w);
                            }
                        });
                    }
                });
                // Deduplicate
                keywords = keywords.filter(function (w, i) { return keywords.indexOf(w) === i; });

                const scored = [];
                self.allCapabilities.forEach(function (cap) {
                    const capName = (cap.name || '').toLowerCase();
                    const capCode = (cap.code || '').toLowerCase();
                    let score = 0;
                    keywords.forEach(function (kw) {
                        if (capName.indexOf(kw) !== -1) score += 2;
                        if (capCode.indexOf(kw) !== -1) score += 1;
                    });
                    if (score > 0) {
                        scored.push({ cap: cap, score: score });
                    }
                });

                scored.sort(function (a, b) { return b.score - a.score; });
                self.suggestedCapabilities = scored.slice(0, 5).map(function (s) {
                    return Object.assign({}, s.cap, { source: 'keyword', confidence: Math.min(s.score / 4, 1) });
                });

                // Phase 2: LLM-powered suggestions with backend matching
                self.suggestionsLoading = true;

                const entityNames = self.motivationElements
                    .filter(function (el) { return el.type === 'Driver' || el.type === 'Goal'; })
                    .map(function (el) { return el.type + ': ' + el.name; })
                    .join('; ');

                _fetch('/solutions/ai-suggest-capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: self.brief + '\n\nKey drivers and goals: ' + entityNames,
                        solution_id: self.solutionId,
                        motivation_elements: self.motivationElements
                            .filter(function (el) { return el.type === 'Driver' || el.type === 'Goal' || el.type === 'Constraint'; })
                            .map(function (el) {
                                const prefix = el.type === 'Driver' ? 'drv_' : el.type === 'Goal' ? 'goal_' : 'con_';
                                return { id: el.id, prefixed_id: prefix + el.id, type: el.type, name: el.name };
                            })
                    })
                }).then(function (data) {
                    let inner = data.data || data;
                    let caps = inner.suggestions || inner.capabilities || [];
                    self.gapSummary = '';
                    const gapData = inner.gap_summary;
                    if (typeof gapData === 'string') {
                        self.gapSummary = gapData;
                    } else if (gapData && typeof gapData === 'object') {
                        self.gapSummary = (gapData.exact + gapData.partial + gapData.novel) + ' capabilities needed: ' + gapData.exact + ' exist, ' + gapData.partial + ' similar, ' + gapData.novel + ' new';
                    }

                    // Split into three tiers
                    self.suggestedExisting = [];
                    self.suggestedPartial = [];
                    self.suggestedNovel = [];

                    caps.forEach(function (cap) {
                        // Skip if already in selectedCapabilities
                        if (cap.existing_id && self.selectedCapabilities.some(function (s) { return s.id === cap.existing_id; })) return;

                        switch (cap.match_type) {
                            case 'exact':
                                self.suggestedExisting.push(cap);
                                break;
                            case 'partial':
                                self.suggestedPartial.push(cap);
                                break;
                            case 'novel':
                            default:
                                self.suggestedNovel.push(cap);
                                break;
                        }
                    });

                    // Merge Phase 1 keyword results into existing tier (deduplicate)
                    const aiExistingIds = self.suggestedExisting.map(function (c) { return c.existing_id; });
                    self.suggestedCapabilities.forEach(function (kwCap) {
                        if (kwCap.id && aiExistingIds.indexOf(kwCap.id) === -1) {
                            self.suggestedExisting.push({
                                name: kwCap.name,
                                match_type: 'exact',
                                existing_id: kwCap.id,
                                existing_name: kwCap.name,
                                level: kwCap.level,
                                coverage_status: kwCap.coverage_status,
                                app_count: kwCap.app_count,
                                match_score: kwCap.confidence || 0.5,
                                source: 'keyword',
                                rationale: '',
                                quality_score: 1.0,
                                quality_warnings: [],
                            });
                        }
                    });

                    // Clear old flat suggestedCapabilities (replaced by three-tier)
                    self.suggestedCapabilities = [];

                }).catch(function (e) {
                    console.error('AI capability suggestion failed:', e);
                    self.copilotMessage = 'AI capability suggestion failed: ' + (e.message || 'Unknown error') + '. Browse the tree or search manually.';
                }).then(function () {
                    self.suggestionsLoading = false;
                    self._updateCopilotAfterSuggestions();
                });
            },

            _updateCopilotAfterSuggestions: function () {
                let self = this;
                const totalSuggestions = self.suggestedExisting.length + self.suggestedPartial.length + self.suggestedNovel.length;

                if (totalSuggestions > 0) {
                    self.copilotMessage = self.gapSummary || (
                        'Found ' + totalSuggestions + ' capabilities: ' +
                        self.suggestedExisting.length + ' exist, ' +
                        self.suggestedPartial.length + ' similar, ' +
                        self.suggestedNovel.length + ' new. Click Next to review.'
                    );
                    self.copilotSuggestions = [{
                        label: 'Review ' + totalSuggestions + ' suggested capabilities \u2192',
                        action: 'nextStep',
                        data: null
                    }];
                } else {
                    self.copilotMessage = 'Generated ' + self.motivationElements.length + ' motivation elements. Proceed to Step 2 to select capabilities manually.';
                }
            },

            // ── Step 2: Capability search and selection ───────────────

            loadAllCapabilities: function () {
                let self = this;
                // Only skip if we actually have data, not just the flag
                if (self.capabilitiesLoaded && self.allCapabilities.length > 0) return Promise.resolve();

                return _fetch('/capability-map/api/capabilities').then(function (data) {
                    let caps = data.capabilities || data;
                    if (Array.isArray(caps) && caps.length > 0) {
                        self.allCapabilities = caps;
                        self.capabilitiesLoaded = true;
                    } else {
                        console.warn('Capabilities API returned empty array');
                        self.capabilitiesLoaded = false;
                    }
                }).catch(function (e) {
                    console.error('Failed to load capabilities:', e);
                    self.capabilitiesLoaded = false;
                    throw e;  // Propagate so the caller knows it failed
                });
            },

            searchCapabilities: function () {
                let self = this;
                let q = self.capabilitySearch.trim().toLowerCase();
                if (q.length < 2) { self.capabilityResults = []; return; }

                if (!self.capabilitiesLoaded) {
                    self.loadAllCapabilities();
                    return;
                }

                const selectedIds = self.selectedCapabilities.map(function (c) { return c.id; });
                const suggestedIds = self.suggestedCapabilities.map(function (c) { return c.id; });

                // Phase 1: keyword search (instant)
                const keywordResults = self.allCapabilities.filter(function (c) {
                    if (selectedIds.indexOf(c.id) !== -1) return false;
                    if (suggestedIds.indexOf(c.id) !== -1) return false;
                    let name = (c.name || '').toLowerCase();
                    const code = (c.code || '').toLowerCase();
                    return name.indexOf(q) !== -1 || code.indexOf(q) !== -1;
                }).slice(0, 10);

                self.capabilityResults = keywordResults;

                // Phase 2: vector search if keyword results are sparse (< 3 results)
                if (keywordResults.length < 3 && q.length >= 3) {
                    _fetch('/capability-map/api/capabilities/semantic-search', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: q, top_k: 10 })
                    }).then(function (data) {
                        if (!data || !data.capabilities) return;
                        const existingIds = self.capabilityResults.map(function (c) { return c.id; });
                        const newResults = data.capabilities.filter(function (c) {
                            return existingIds.indexOf(c.id) === -1
                                && selectedIds.indexOf(c.id) === -1
                                && suggestedIds.indexOf(c.id) === -1;
                        });
                        // Merge: keyword results first, then vector results
                        self.capabilityResults = self.capabilityResults.concat(newResults).slice(0, 10);
                    }).catch(function () {});
                }
            },

            // ── Capability Tree (Wave 5) ────────────────────────────
            loadCapabilityTree: function () {
                let self = this;
                if (self.capabilityTreeData.length > 0) return;
                self.capabilityTreeLoading = true;

                // Build highlight param from suggested capability IDs
                const highlightIds = self.suggestedCapabilities.map(function (c) { return c.id; }).join(',');
                let url = '/capability-map/api/capabilities/tree';
                if (highlightIds) url += '?highlight=' + highlightIds;

                _fetch(url).then(function (data) {
                    if (data && data.tree) {
                        // Add _expanded state to each node
                        data.tree.forEach(function (node) {
                            node._expanded = false;
                            (node.children || []).forEach(function (child) {
                                child._expanded = false;
                            });
                        });
                        self.capabilityTreeData = data.tree;
                    }
                    self.capabilityTreeLoading = false;
                }).catch(function () {
                    self.capabilityTreeLoading = false;
                });
            },

            filteredTreeData: function () {
                let self = this;
                let q = (self.treeFilter || '').trim().toLowerCase();
                if (!q) return self.capabilityTreeData;

                // Filter tree — show L1 nodes that contain matching children
                return self.capabilityTreeData.filter(function (node) {
                    if ((node.name || '').toLowerCase().indexOf(q) !== -1) return true;
                    return (node.children || []).some(function (child) {
                        if ((child.name || '').toLowerCase().indexOf(q) !== -1) return true;
                        return (child.children || []).some(function (leaf) {
                            return (leaf.name || '').toLowerCase().indexOf(q) !== -1;
                        });
                    });
                });
            },

            isCapabilitySelected: function (capId) {
                return this.selectedCapabilities.some(function (c) { return c.id === capId; });
            },

            createMissingCapability: function () {
                let self = this;
                let name = self.capabilitySearch.trim();
                if (!name || name.length < 3) return;

                _fetch('/capability-map/api/capabilities/create-missing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, level: 2, description: 'Created during solution design' })
                }).then(function (data) {
                    if (data && data.capability) {
                        self.selectCapability(data.capability);
                        // Also add to allCapabilities cache
                        self.allCapabilities.push(data.capability);
                        self.copilotMessage = 'Created new capability: ' + data.capability.name;
                    }
                }).catch(function () {
                    self.copilotMessage = 'Failed to create capability. Please try again.';
                });
            },

            selectCapability: function (cap) {
                if (this.selectedCapabilities.findIndex(function (c) { return c.id === cap.id; }) === -1) {
                    this.selectedCapabilities.push(cap);
                }
                this.capabilitySearch = '';
                this.capabilityResults = [];
                this.updateEntityCounts();

                // Link to solution in the background
                _fetch(API_BASE + '/' + this.solutionId + '/capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ capability_id: cap.id })
                }).catch(function (e) {
                    console.error('Failed to link capability ' + cap.id + ':', e.message || e);
                });
            },

            acceptSuggestion: function (cap) {
                let self = this;
                if (self.selectedCapabilities.findIndex(function (c) { return c.id === cap.id; }) === -1) {
                    self.selectedCapabilities.push(cap);
                    self.updateEntityCounts();

                    _fetch(API_BASE + '/' + self.solutionId + '/capabilities', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ capability_id: cap.id })
                    }).catch(function (e) {
                        console.error('Failed to link capability ' + cap.id + ':', e.message || e);
                    });
                }
                self.suggestedCapabilities = self.suggestedCapabilities.filter(function (s) { return s.id !== cap.id; });
            },

            dismissSuggestion: function (cap) {
                this.suggestedCapabilities = this.suggestedCapabilities.filter(function (s) { return s.id !== cap.id; });
            },

            acceptExistingSuggestion: function (cap) {
                // Tier 1: exact match — link catalog capability
                let catalogCap = {
                    id: cap.existing_id,
                    name: cap.existing_name || cap.name,
                    level: cap.level,
                    coverage_status: cap.coverage_status,
                    app_count: cap.app_count,
                };
                this.selectCapability(catalogCap);
                this.suggestedExisting = this.suggestedExisting.filter(function (s) { return s.existing_id !== cap.existing_id; });
            },

            acceptAsExisting: function (cap) {
                // Tier 2: user chose "Use existing" — link the closest_match catalog capability
                let catalogCap = {
                    id: cap.closest_match_id,
                    name: cap.closest_match_name,
                    level: cap.level,
                    coverage_status: cap.coverage_status,
                    app_count: cap.app_count,
                };
                this.selectCapability(catalogCap);
                this.suggestedPartial = this.suggestedPartial.filter(function (s) { return s.name !== cap.name; });
            },

            acceptAsNovel: function (cap) {
                // Tier 2 "Keep as new" or Tier 3 "Accept" — create SolutionCapability
                let self = this;

                _fetch(API_BASE + '/' + self.solutionId + '/solution-capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: cap.name,
                        description: cap.description || '',
                        category: cap.category || 'required',
                        match_type: cap.match_type,
                        match_score: cap.match_score,
                        closest_match_id: cap.closest_match_id,
                        quality_score: cap.quality_score,
                        quality_warnings: cap.quality_warnings || [],
                    })
                }).then(function (data) {
                    let inner = data.data || data;
                    if (inner && inner.id) {
                        self.selectedCapabilities.push({
                            id: 'sol_cap_' + inner.id,
                            _solution_cap_id: inner.id,
                            name: inner.name,
                            description: inner.description,
                            level: null,
                            solution_scoped: true,
                            promoted_to_id: null,
                        });
                        self.updateEntityCounts();
                    }
                }).catch(function (e) {
                    console.error('Failed to create solution capability:', e);
                    self.copilotMessage = 'Failed to save capability. Try again.';
                });

                // Remove from suggestion tier
                self.suggestedPartial = self.suggestedPartial.filter(function (s) { return s.name !== cap.name; });
                self.suggestedNovel = self.suggestedNovel.filter(function (s) { return s.name !== cap.name; });
            },

            promoteSolutionCapability: function (cap) {
                let self = this;
                if (!cap._solution_cap_id) return;

                _fetch(API_BASE + '/' + self.solutionId + '/capabilities/' + cap._solution_cap_id + '/promote', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                }).then(function (data) {
                    let inner = data.data || data;
                    const promoted = inner.promoted_to;
                    if (promoted) {
                        cap.id = promoted.id;
                        cap.promoted_to_id = promoted.id;
                        cap.solution_scoped = false;
                        cap.level = promoted.level;
                        self.copilotMessage = 'Promoted "' + cap.name + '" to global capability catalog.';
                        if (inner.quality_warning) {
                            self.copilotMessage += ' Note: ' + inner.quality_warning;
                        }
                    }
                }).catch(function (e) {
                    console.error('Promote failed:', e);
                    self.copilotMessage = 'Failed to promote capability. Try again.';
                });
            },

            dismissTieredSuggestion: function (cap, tier) {
                if (tier === 'existing') {
                    this.suggestedExisting = this.suggestedExisting.filter(function (s) { return s.name !== cap.name; });
                } else if (tier === 'partial') {
                    this.suggestedPartial = this.suggestedPartial.filter(function (s) { return s.name !== cap.name; });
                } else {
                    this.suggestedNovel = this.suggestedNovel.filter(function (s) { return s.name !== cap.name; });
                }
            },

            acceptAllSuggestions: function () {
                let self = this;
                self.suggestedExisting.slice().forEach(function (cap) {
                    self.acceptExistingSuggestion(cap);
                });
                // Don't auto-accept partial or novel — user must decide per item
            },

            removeCapability: function (idx) {
                this.selectedCapabilities.splice(idx, 1);
                this.updateEntityCounts();
            },

            generateRequirements: function () {
                let self = this;
                if (self.selectedCapabilities.length === 0 || self.isProcessing) return;

                self.isProcessing = true;
                self.processingLabel = 'Deriving requirements from ' + self.selectedCapabilities.length + ' capabilities...';

                _fetch(API_BASE + '/' + self.solutionId + '/generate-from-capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capability_ids: self.selectedCapabilities.map(function (c) { return c.id; })
                    })
                }).then(function (data) {
                    if (data.requirements) {
                        self.derivedRequirements = data.requirements;
                    } else if (data.elements) {
                        self.derivedRequirements = data.elements;
                    }
                    self.copilotMessage = 'Generated ' + (self.derivedRequirements.length || 0) + ' requirements. Deriving system capabilities...';
                    self.updateEntityCounts();
                    // Auto-derive system capabilities after requirements
                    if (!self.systemCapsGenerated) {
                        self.deriveSystemCapabilities();
                    }
                }).catch(function (e) {
                    console.error('Requirement generation failed:', e);
                    self.copilotMessage = 'Requirement generation failed. Try again or proceed manually.';
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            // ── Intelligence Chain: Step 2 → Step 3 ──────────────────

            generateStrategyLayer: function () {
                let self = this;
                if (self.selectedCapabilities.length === 0) return Promise.resolve();

                self.isProcessing = true;
                self.processingLabel = 'Generating strategy layer — courses of action and value streams...';

                return _fetch('/solutions/' + self.solutionId + '/generate-strategy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capability_ids: self.selectedCapabilities.map(function (c) { return c.id; })
                    })
                }).then(function (data) {
                    if (data.success) {
                        self.copilotMessage = data.summary || 'Strategy layer generated.';
                    } else {
                        self.copilotMessage = 'Strategy generation: ' + (data.error || 'completed with issues');
                    }
                }).catch(function (e) {
                    console.error('Strategy generation failed:', e);
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            /**
             * Idempotent: only fires if the capability set has changed since last run.
             * Tracks via _architectureGeneratedForCaps (sorted ID string).
             */
            generateArchitectureFromCapabilities: function () {
                let self = this;
                if (self.selectedCapabilities.length === 0) return;

                // Idempotency: don't regenerate for the same capability set
                const capKey = self.selectedCapabilities.map(function (c) { return c.id; }).sort().join(',');
                if (capKey === self._architectureGeneratedForCaps) return;

                self.isProcessing = true;
                self.processingLabel = 'Generating architecture across business, application, and technology layers...';

                _fetch('/solutions/' + self.solutionId + '/generate-architecture-layers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capability_ids: self.selectedCapabilities.map(function (c) { return c.id; }),
                        capabilities: self.selectedCapabilities.map(function (c) {
                            const prefixedId = c.solution_scoped ? ('sol_cap_' + c._solution_cap_id) : ('cap_' + c.id);
                            return { id: c.id, prefixed_id: prefixedId, name: c.name, type: c.solution_scoped ? 'SolutionCapability' : 'BusinessCapability' };
                        })
                    })
                }).then(function (data) {
                    if (data.success !== false) {
                        self._architectureGeneratedForCaps = capKey;
                        self.copilotMessage = data.summary || 'Architecture elements generated across all layers.';
                        // Load generated elements into the review UI
                        self.loadArchitectureElements();
                    } else {
                        self.copilotMessage = 'Architecture generation failed: ' + (data.error || 'Unknown error');
                    }
                }).catch(function (e) {
                    console.error('Architecture generation failed:', e);
                    self.copilotMessage = 'Architecture generation failed. You can still proceed and add elements manually.';
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            generateImplementationLayer: function () {
                let self = this;
                if (self.selectedCapabilities.length === 0) return Promise.resolve();

                self.isProcessing = true;
                self.processingLabel = 'Generating migration plan — work packages, Kanban cards, Gantt timeline...';

                return _fetch('/solutions/' + self.solutionId + '/generate-implementation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capability_ids: self.selectedCapabilities.map(function (c) { return c.id; }),
                        architecture_elements: self.architectureElements
                            .filter(function (el) { return el.accepted; })
                            .map(function (el) { return { id: el.id, prefixed_id: 'elem_' + el.id, name: el.name, type: el.type, layer: el.layer }; })
                    })
                }).then(function (data) {
                    if (data.success) {
                        self.copilotMessage = data.summary || 'Migration plan generated.';
                        self.loadImplementationElements();
                    } else {
                        self.copilotMessage = 'Implementation generation: ' + (data.error || 'completed with issues');
                    }
                }).catch(function (e) {
                    console.error('Implementation generation failed:', e);
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            // ── Step 6: Completeness and ARB submission ───────────────

            loadCompleteness: function () {
                let self = this;
                _fetch(API_BASE + '/' + self.solutionId).then(function (data) {
                    const sol = data.solution || data;
                    const issues = [];
                    let score = 0;
                    let total = 6;

                    if (self.motivationElements.length > 0) score++;
                    else issues.push('No motivation elements (drivers, goals)');

                    if (self.selectedCapabilities.length > 0) score++;
                    else issues.push('No capabilities mapped');

                    if (self.derivedRequirements.length > 0) score++;
                    else issues.push('No requirements defined');

                    if (sol.in_scope_applications && sol.in_scope_applications.length > 0) score++;
                    else issues.push('No applications linked');

                    score++; // Architecture placeholder
                    score++; // Options placeholder

                    self.completenessScore = Math.round((score / total) * 100);
                    self.blockingIssues = issues;
                }).catch(function () {});

                // Wave 10: Load quality score
                _fetch('/api/solutions/' + self.solutionId + '/quality-score')
                    .then(function (data) { self.qualityScore = data; })
                    .catch(function () {});
            },

            submitToArb: function () {
                let self = this;
                if (self.isProcessing) return;
                self.isProcessing = true;
                self.processingLabel = 'Submitting to Architecture Review Board...';

                _fetch(API_BASE + '/' + self.solutionId + '/update-json', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ governance_status: 'arb_review' })
                }).then(function () {
                    self.copilotMessage = 'Solution submitted to ARB for review!';
                    if (global.Platform && global.Platform.toast) {
                        global.Platform.toast.success('Solution submitted to ARB');
                    }
                    setTimeout(function () {
                        window.location = '/solutions/' + self.solutionId;
                    }, 1500);
                }).catch(function (e) {
                    console.error('ARB submission failed:', e);
                    self.copilotMessage = 'Submission failed. Please try again.';
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            // ── Document upload ────────────────────────────────────────

            handleFileSelect: function (event) {
                let file = event.target.files[0];
                if (file) this.uploadDocument(file);
            },

            handleFileDrop: function (event) {
                let file = event.dataTransfer.files[0];
                if (file) this.uploadDocument(file);
            },

            uploadDocument: function (file) {
                let self = this;
                const maxSize = 10 * 1024 * 1024; // 10MB
                if (file.size > maxSize) {
                    self.copilotMessage = 'File too large (max 10MB). Try a smaller document.';
                    return;
                }

                self.isProcessing = true;
                self.processingLabel = 'Extracting text from ' + file.name + '...';

                const formData = new FormData();
                formData.append('file', file);

                const csrfEl = document.querySelector('meta[name=csrf-token]');
                fetch('/ai-chat/upload-document', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfEl ? csrfEl.content : '' },
                    body: formData,
                    credentials: 'same-origin'
                }).then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success && data.extracted_text) {
                        let extracted = data.extracted_text;
                        if (extracted.length > 3000) extracted = extracted.substring(0, 3000) + '\n\n[Document truncated at 3000 characters]';
                        self.brief = (self.brief ? self.brief + '\n\n--- Extracted from ' + file.name + ' ---\n\n' : '') + extracted;
                        self.uploadedFile = file.name;
                        self.inputMode = 'type';
                        self.copilotMessage = 'Extracted ' + extracted.length + ' characters from ' + file.name + '. Review the text and click Generate.';
                    } else if (data.success && data.elements) {
                        self.brief = (self.brief ? self.brief + '\n\n' : '') + (data.summary || data.text || 'Document processed: ' + file.name);
                        self.copilotMessage = 'Document processed. ' + (data.elements.length || 0) + ' elements extracted. Review and generate motivation elements.';
                    } else {
                        self.copilotMessage = 'Could not extract text: ' + (data.error || 'Unknown error');
                    }
                }).catch(function (e) {
                    console.error('Upload failed:', e);
                    self.copilotMessage = 'Upload failed: ' + e.message;
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            applySuggestion: function (s) {
                if (s.action && typeof this[s.action] === 'function') {
                    this[s.action](s.data);
                }
            },

            // ── Capability Blueprint: TCM + ACM derivation ─────────────

            deriveSystemCapabilities: function () {
                let self = this;
                if (self.selectedCapabilities.length === 0 || self.systemCapsLoading) return;

                self.systemCapsLoading = true;
                self.copilotMessage = 'Deriving technical and application capabilities from your business capabilities...';

                _fetch('/solutions/' + self.solutionId + '/derive-system-capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                }).then(function (data) {
                    if (data.success) {
                        self.technicalCapabilities = (data.technical_capabilities || []).map(function (tc) {
                            tc.accepted = true;
                            return tc;
                        });
                        self.applicationCapabilities = (data.application_capabilities || []).map(function (ac) {
                            ac.accepted = true;
                            return ac;
                        });
                        self.systemCapsGenerated = true;
                        self.copilotMessage = 'Derived ' + self.technicalCapabilities.length + ' technical + ' + self.applicationCapabilities.length + ' application capabilities. Review the blueprint below.';
                        // Persist to server
                        self.saveCapabilityBlueprint();
                    } else {
                        self.copilotMessage = 'System capability derivation failed: ' + (data.error || 'Unknown error');
                    }
                }).catch(function (e) {
                    console.error('System capability derivation failed:', e);
                    self.copilotMessage = 'Failed to derive system capabilities. You can still proceed manually.';
                }).then(function () {
                    self.systemCapsLoading = false;
                });
            },

            toggleTechCap: function (idx) {
                this.technicalCapabilities[idx].accepted = !this.technicalCapabilities[idx].accepted;
                this.saveCapabilityBlueprint();
            },

            toggleAppCap: function (idx) {
                this.applicationCapabilities[idx].accepted = !this.applicationCapabilities[idx].accepted;
                this.saveCapabilityBlueprint();
            },

            removeTechCap: function (idx) {
                this.technicalCapabilities.splice(idx, 1);
                this.saveCapabilityBlueprint();
            },

            removeAppCap: function (idx) {
                this.applicationCapabilities.splice(idx, 1);
                this.saveCapabilityBlueprint();
            },

            saveCapabilityBlueprint: function () {
                _fetch('/api/solutions/' + this.solutionId + '/capability-blueprint', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        technical_capabilities: this.technicalCapabilities,
                        application_capabilities: this.applicationCapabilities,
                    })
                }).catch(function () {});
            },

            loadCapabilityBlueprint: function () {
                let self = this;
                _fetch('/api/solutions/' + self.solutionId + '/capability-blueprint')
                    .then(function (data) {
                        const tc = data.technical_capabilities || [];
                        const ac = data.application_capabilities || [];
                        if (tc.length > 0 || ac.length > 0) {
                            self.technicalCapabilities = tc;
                            self.applicationCapabilities = ac;
                            self.systemCapsGenerated = true;
                        }
                    })
                    .catch(function () {});
            },

            // ── Wave 6: Element Review + Decision Feedback ───────────────

            loadArchitectureElements: function () {
                let self = this;
                self.archElementsLoading = true;
                _fetch('/api/solutions/' + self.solutionId + '/archimate-elements')
                    .then(function (data) {
                        let elements = [];
                        let byLayer = data.elements_by_layer || {};
                        ['Business', 'business', 'Application', 'application', 'Technology', 'technology'].forEach(function (layer) {
                            (byLayer[layer] || []).forEach(function (el) {
                                elements.push({
                                    id: el.id,
                                    name: el.name,
                                    type: el.type,
                                    layer: (el.layer || layer).toLowerCase(),
                                    description: el.description || '',
                                    element_role: el.element_role || 'ai_derived',
                                    accepted: true,
                                    isNew: el.element_role === 'ai_derived',
                                });
                            });
                        });
                        self.architectureElements = elements;
                    })
                    .catch(function (e) {
                        console.error('Failed to load architecture elements:', e);
                    })
                    .then(function () {
                        self.archElementsLoading = false;
                    });
            },

            loadImplementationElements: function () {
                let self = this;
                self.implElementsLoading = true;
                _fetch('/api/solutions/' + self.solutionId + '/archimate-elements')
                    .then(function (data) {
                        let elements = [];
                        let byLayer = data.elements_by_layer || {};
                        ['Implementation', 'implementation', 'Strategy', 'strategy'].forEach(function (layer) {
                            (byLayer[layer] || []).forEach(function (el) {
                                if (['WorkPackage', 'Gap', 'Plateau', 'Deliverable', 'ImplementationEvent'].indexOf(el.type) !== -1) {
                                    elements.push({
                                        id: el.id,
                                        name: el.name,
                                        type: el.type,
                                        layer: (el.layer || layer).toLowerCase(),
                                        description: el.description || '',
                                        element_role: el.element_role || 'ai_derived',
                                        accepted: true,
                                        isNew: el.element_role === 'ai_derived',
                                    });
                                }
                            });
                        });
                        self.implementationElements = elements;
                    })
                    .catch(function (e) {
                        console.error('Failed to load implementation elements:', e);
                    })
                    .then(function () {
                        self.implElementsLoading = false;
                    });
            },

            toggleArchElement: function (idx) {
                let el = this.architectureElements[idx];
                el.accepted = !el.accepted;
                this.logElementDecision(el, el.accepted ? 'accept' : 'reject');
            },

            toggleImplElement: function (idx) {
                let el = this.implementationElements[idx];
                el.accepted = !el.accepted;
                this.logElementDecision(el, el.accepted ? 'accept' : 'reject');
            },

            removeArchElement: function (idx) {
                let el = this.architectureElements[idx];
                this.logElementDecision(el, 'reject');
                this.architectureElements.splice(idx, 1);
                // Propagate stale to downstream dependents (Wave 7)
                this.propagateStale(el);
                // Unlink from solution
                _fetch('/api/solutions/' + this.solutionId + '/element-decisions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        element_id: el.id,
                        action: 'reject',
                        element_name: el.name,
                        element_type: el.type,
                        element_layer: el.layer,
                    })
                }).catch(function () {});
            },

            removeImplElement: function (idx) {
                let el = this.implementationElements[idx];
                this.logElementDecision(el, 'reject');
                this.implementationElements.splice(idx, 1);
                _fetch('/api/solutions/' + this.solutionId + '/element-decisions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        element_id: el.id,
                        action: 'reject',
                        element_name: el.name,
                        element_type: el.type,
                        element_layer: el.layer,
                    })
                }).catch(function () {});
            },

            showWhy: function (el) {
                let self = this;
                self.whyModalElement = el;
                // Load real reasoning chain from API
                if (el.id && !el._chainLoaded) {
                    el._chainLoading = true;
                    _fetch('/api/solutions/' + self.solutionId + '/elements/' + el.id + '/trace')
                        .then(function (data) {
                            el.reasoning = data.reasoning || el.description || '';
                            el.chain = data.chain || [];
                            el._chainLoaded = true;
                        })
                        .catch(function () {})
                        .then(function () { el._chainLoading = false; });
                }
            },

            closeWhy: function () {
                this.whyModalElement = null;
            },

            startEdit: function (el) {
                this.editingElement = el;
                this.editName = el.name;
                this.editDescription = el.description || '';
            },

            saveEdit: function () {
                let self = this;
                let el = self.editingElement;
                if (!el) return;

                _fetch('/api/solutions/' + self.solutionId + '/elements/' + el.id + '/update', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: self.editName, description: self.editDescription })
                }).then(function (data) {
                    if (data.success) {
                        el.name = data.name;
                        el.description = data.description;
                        self.logElementDecision(el, 'edit');
                        // Propagate stale to dependents since name/desc changed
                        self.propagateStale(el);
                    }
                }).catch(function (e) {
                    console.error('Edit failed:', e);
                });
                self.editingElement = null;
            },

            cancelEdit: function () {
                this.editingElement = null;
            },

            startAddElement: function (layer) {
                this.addElementLayer = layer;
                this.addElementName = '';
                this.addElementDesc = '';
                // Default type based on layer
                const defaults = {business: 'BusinessProcess', application: 'ApplicationComponent', technology: 'Node'};
                this.addElementType = defaults[layer] || 'ApplicationComponent';
            },

            cancelAddElement: function () {
                this.addElementLayer = null;
            },

            saveNewElement: function () {
                let self = this;
                if (!self.addElementName.trim() || !self.addElementLayer) return;

                _fetch('/api/solutions/' + self.solutionId + '/elements/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: self.addElementName.trim(),
                        type: self.addElementType,
                        layer: self.addElementLayer,
                        description: self.addElementDesc.trim(),
                    })
                }).then(function (data) {
                    if (data.success && data.element) {
                        self.architectureElements.push(data.element);
                        self.copilotMessage = 'Added "' + data.element.name + '" to ' + self.addElementLayer + ' layer.';
                    }
                }).catch(function (e) {
                    console.error('Add element failed:', e);
                    self.copilotMessage = 'Failed to add element: ' + e.message;
                });
                self.addElementLayer = null;
            },

            // ── Relationship drawing (Connect mode) ─────────────────────

            toggleConnectMode: function () {
                this.connectMode = !this.connectMode;
                this.connectSource = null;
                this.connectPickerOpen = false;
                this.connectValidTypes = [];
                if (this.connectMode) {
                    this.copilotMessage = 'Connect mode ON. Click a source element, then click a target to draw a relationship.';
                } else {
                    this.copilotMessage = 'Connect mode OFF.';
                }
            },

            handleChipClick: function (el) {
                if (!this.connectMode) {
                    this.showWhy(el);
                    return;
                }

                if (!this.connectSource) {
                    // First click — set source
                    this.connectSource = el;
                    this.copilotMessage = 'Source: "' + el.name + '". Now click the target element.';
                } else if (this.connectSource.id === el.id) {
                    // Clicked same element — cancel
                    this.connectSource = null;
                    this.copilotMessage = 'Cancelled. Click a source element to start again.';
                } else {
                    // Second click — fetch valid types and show picker
                    this.fetchValidRelTypes(this.connectSource, el);
                }
            },

            fetchValidRelTypes: function (source, target) {
                let self = this;
                self._connectTarget = target;
                _fetch('/archimate/api/valid-relationship-types?source_id=' + source.id + '&target_id=' + target.id)
                    .then(function (data) {
                        self.connectValidTypes = data.valid_types_detailed || [];
                        if (self.connectValidTypes.length === 0) {
                            self.connectValidTypes = (data.valid_types || ['association']).map(function (t) {
                                return { type: t, tier: 'standard', description: '' };
                            });
                        }
                        self.connectPickerOpen = true;
                        self.copilotMessage = 'Select relationship type: ' + source.name + ' → ' + target.name;
                    })
                    .catch(function () {
                        self.copilotMessage = 'Failed to load valid types. Try again.';
                        self.connectSource = null;
                    });
            },

            createConnection: function (relType) {
                let self = this;
                const source = self.connectSource;
                self.connectPickerOpen = false;

                _fetch('/archimate/api/relationships', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_element_id: source.id,
                        target_element_id: self._connectTarget.id,
                        relationship_type: relType,
                        solution_id: self.solutionId,
                    })
                }).then(function (data) {
                    if (data.id) {
                        // Track relationship count on elements
                        source._relCount = (source._relCount || 0) + 1;
                        self._connectTarget._relCount = (self._connectTarget._relCount || 0) + 1;
                        self.copilotMessage = 'Created ' + relType + ': ' + source.name + ' → ' + self._connectTarget.name;
                    } else {
                        self.copilotMessage = 'Relationship creation failed: ' + (data.error || 'unknown error');
                    }
                }).catch(function (e) {
                    self.copilotMessage = 'Failed: ' + e.message;
                });
                self.connectSource = null;
                self._connectTarget = null;
            },

            cancelConnect: function () {
                this.connectPickerOpen = false;
                this.connectSource = null;
                this._connectTarget = null;
                this.copilotMessage = 'Cancelled. Click a source element to start again.';
            },

            logElementDecision: function (el, action) {
                const decision = {
                    element_id: el.id,
                    element_name: el.name,
                    element_type: el.type,
                    action: action,
                    timestamp: new Date().toISOString(),
                };
                this.elementDecisions.push(decision);

                // Session-level learning: track consecutive "new" rejections
                if (action === 'reject' && el.isNew) {
                    this._consecutiveNewRejections++;
                    if (this._consecutiveNewRejections >= 2) {
                        this.suppressNewSuggestions = true;
                        this.copilotMessage = 'Noted: suppressing "create new" suggestions for this session. You prefer existing catalog matches.';
                    }
                } else if (action === 'accept') {
                    this._consecutiveNewRejections = 0;
                }

                // Fire-and-forget to server
                _fetch('/api/solutions/' + this.solutionId + '/element-decisions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(decision)
                }).catch(function () {});
            },

            getArchElementsByLayer: function (layer) {
                return this.architectureElements.filter(function (el) {
                    return el.layer === layer;
                });
            },

            // ── Wave 7: Change Propagation + Versioning ─────────────────

            isStale: function (elId) {
                return this.staleElementIds.indexOf(elId) !== -1;
            },

            propagateStale: function (el) {
                let self = this;
                _fetch('/api/solutions/' + self.solutionId + '/elements/' + el.id + '/propagate-stale', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                }).then(function (data) {
                    const ids = data.stale_ids || [];
                    ids.forEach(function (id) {
                        if (self.staleElementIds.indexOf(id) === -1) {
                            self.staleElementIds.push(id);
                        }
                    });
                    if (ids.length > 0) {
                        self.copilotMessage = ids.length + ' downstream element(s) flagged as potentially stale after your change to "' + el.name + '". Review or regenerate them.';
                    }
                }).catch(function () {});
            },

            regenerateStale: function () {
                let self = this;
                if (self.staleElementIds.length === 0 || self.isProcessing) return;

                self.isProcessing = true;
                self.processingLabel = 'Regenerating ' + self.staleElementIds.length + ' stale elements...';

                _fetch('/solutions/' + self.solutionId + '/generate-architecture-layers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capability_ids: self.selectedCapabilities.map(function (c) { return c.id; }),
                        regenerate_stale: true,
                    })
                }).then(function (data) {
                    self.staleElementIds = [];
                    self.loadArchitectureElements();
                    self.copilotMessage = 'Stale elements regenerated. ' + (data.summary || '');
                }).catch(function (e) {
                    console.error('Regeneration failed:', e);
                    self.copilotMessage = 'Regeneration failed. Try again or proceed manually.';
                }).then(function () {
                    self.isProcessing = false;
                });
            },

            createSnapshot: function (step) {
                let self = this;
                const labels = {1: 'Problem defined', 2: 'Capabilities mapped', 3: 'Architecture designed', 4: 'Options evaluated', 5: 'Migration planned', 6: 'Review complete'};
                _fetch('/api/solutions/' + self.solutionId + '/snapshots', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ step: step, label: labels[step] || ('Step ' + step) })
                }).then(function (data) {
                    if (data.success) {
                        self.snapshots.push({
                            version_number: data.version_number,
                            label: labels[step] || ('Step ' + step),
                            element_count: data.element_count,
                            relationship_count: data.relationship_count,
                        });
                    }
                }).catch(function () {});
            },

            loadSnapshots: function () {
                let self = this;
                _fetch('/api/solutions/' + self.solutionId + '/snapshots')
                    .then(function (data) {
                        self.snapshots = data || [];
                    })
                    .catch(function () {});
            },

            compareSnapshots: function (v1, v2) {
                let self = this;
                _fetch('/api/solutions/' + self.solutionId + '/snapshots/' + v1 + '/compare/' + v2)
                    .then(function (data) {
                        self.snapshotCompare = data;
                    })
                    .catch(function (e) {
                        console.error('Comparison failed:', e);
                    });
            },

            toggleVersionPanel: function () {
                this.showVersionPanel = !this.showVersionPanel;
                if (this.showVersionPanel && this.snapshots.length === 0) {
                    this.loadSnapshots();
                }
            },

            loadTraceability: function () {
                let self = this;
                if (self.traceabilityLoading) return;
                self.traceabilityLoading = true;
                self.showTraceability = true;

                _fetch(API_BASE + '/' + self.solutionId + '/traceability')
                    .then(function (data) {
                        self.traceabilityData = data.data || data;
                    })
                    .catch(function (e) {
                        console.error('Failed to load traceability:', e);
                        self.copilotMessage = 'Failed to load traceability chain.';
                    })
                    .then(function () {
                        self.traceabilityLoading = false;
                    });
            },
        };
    };
})(window);
