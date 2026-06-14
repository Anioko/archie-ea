/** solutions/create - External JavaScript
 *  Extracted from app/templates/solutions/create.html
 *  Uses window.__APP_CONFIG__ bridge for server-side values
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

// Solution form state - accessible globally for modal callbacks
window.SolutionFormState = {
    selectedCapabilities: [],
    selectedArchiMateElements: {
        motivation: [],
        strategy: [],
        business: [],
        application: [],
        technology: [],
        implementation: []
    },
    currentCapabilityCategory: 'required'
};

document.addEventListener('alpine:init', function() {
    Alpine.data('solutionCreateForm', function() { return {
        // Form State
        formData: {
            name: '',
            description: '',
            solution_type: '',
            business_domain: '',
            value_proposition: '',
            target_outcomes: '',
            success_metrics: '',
            solution_owner: '',
            business_sponsor: '',
            technical_lead: '',
            architecture_lead: '',
            status: 'planned',
            expected_delivery_date: ''
        },

        // UI State
        isSubmitting: false,
        isAIPopulating: false,
        isGeneratingRequirements: false,
        isGeneratingRoadmap: false,
        activeLayer: 'motivation',
        currentCapabilityCategory: 'required',
        requirementsFilter: 'all',
        roadmapPhaseFilter: 'all',

        // Strategy Layer Capability Controls
        strategyCapabilityType: 'business',      // business, technical, manufacturing, application
        strategyCapabilityLevel: '',             // '', '0', '1', '2', '3'
        strategyCapabilityCategory: 'required',  // required, optional, future
        showCapabilityHierarchy: false,
        autoPopulateRoadmap: true,               // Auto-populate roadmap from capabilities

        // Requirements state
        requirements: [],

        // Roadmap state
        roadmapItems: [],

        // Selection State - sync with global state
        get selectedCapabilities() {
            return window.SolutionFormState.selectedCapabilities;
        },
        set selectedCapabilities(val) {
            window.SolutionFormState.selectedCapabilities = val;
        },
        get selectedArchiMateElements() {
            return window.SolutionFormState.selectedArchiMateElements;
        },
        set selectedArchiMateElements(val) {
            window.SolutionFormState.selectedArchiMateElements = val;
        },

        // Layer Configuration
        layers: [
            { id: 'motivation', label: 'Motivation', color: '#B3A2C7' },
            { id: 'strategy', label: 'Strategy', color: '#F5D742' },
            { id: 'business', label: 'Business', color: '#FFFFB5' },
            { id: 'application', label: 'Application', color: '#B5E3FF' },
            { id: 'technology', label: 'Technology', color: '#C9E6B5' },
            { id: 'implementation', label: 'Implementation', color: '#FFB5B5' }
        ],

        // Computed: Filtered requirements based on category filter
        get filteredRequirements() {
            if (this.requirementsFilter === 'all') {
                return this.requirements;
            }
            return this.requirements.filter(function(r) { return r.category === this.requirementsFilter; }.bind(this));
        },

        // Computed: Filtered roadmap items based on phase filter
        get filteredRoadmapItems() {
            if (this.roadmapPhaseFilter === 'all') {
                return this.roadmapItems;
            }
            return this.roadmapItems.filter(function(i) { return i.phase === this.roadmapPhaseFilter; }.bind(this));
        },

        // Computed: Total roadmap weeks
        get totalRoadmapWeeks() {
            return this.roadmapItems.reduce(function(sum, item) { return sum + (item.duration_weeks || 0); }, 0);
        },

        // Helper: Get phase label
        getPhaseLabel(phase) {
            let labels = {
                'phase1': 'Foundation',
                'phase2': 'Core',
                'phase3': 'Enhance',
                'phase4': 'Go-Live'
            };
            return labels[phase] || phase;
        },

        // Helper: Get strategy capabilities filtered by category
        getStrategyCapabilitiesByCategory(category) {
            let strategyElements = this.selectedArchiMateElements.strategy || [];
            return strategyElements.filter(function(e) {
                return e.element_type === 'Capability' && e.category === category;
            });
        },

        // Open Strategy Layer Capability Modal with type/level/category context
        openStrategyCapabilityModal() {
            let self = this;
            let contextMap = {
                'business': 'capability',
                'technical': 'technical-capability',
                'manufacturing': 'manufacturing-capability',
                'application': 'application-capability'
            };

            openUnifiedMappingModalDiscovery({
                context: contextMap[this.strategyCapabilityType] || 'capability',
                filters: {
                    level: this.strategyCapabilityLevel,
                    specialization_type: this.strategyCapabilityType.toUpperCase()
                },
                onSaveCallback: function(mappings) {
                    mappings.forEach(function(m) {
                        if (!self.selectedArchiMateElements.strategy) {
                            self.selectedArchiMateElements.strategy = [];
                        }

                        let existing = self.selectedArchiMateElements.strategy.find(
                            function(e) { return e.element_id === m.targetId && e.capability_type === self.strategyCapabilityType; }
                        );

                        if (!existing) {
                            self.selectedArchiMateElements.strategy.push({
                                element_id: m.targetId,
                                element_table: 'unified_capabilities',
                                element_type: 'Capability',
                                name: m.targetName,
                                capability_type: self.strategyCapabilityType,
                                capability_level: m.level || self.strategyCapabilityLevel,
                                category: self.strategyCapabilityCategory,
                                color: '#F5D742' // Strategy layer color
                            });
                        }
                    });

                    // Force Alpine reactivity
                    self.selectedArchiMateElements = Object.assign({}, self.selectedArchiMateElements);

                    // Auto-populate roadmap if enabled
                    if (self.autoPopulateRoadmap) {
                        self.$nextTick(function() {
                            self.autoPopulateRoadmapFromCapabilities();
                        });
                    }
                }
            });
        },

        // Auto-populate roadmap from Strategy layer capabilities
        autoPopulateRoadmapFromCapabilities() {
            let strategyCapabilities = (this.selectedArchiMateElements.strategy || []).filter(
                function(e) { return e.element_type === 'Capability'; }
            );

            if (strategyCapabilities.length === 0) return;

            let required = strategyCapabilities.filter(function(c) { return c.category === 'required'; });
            let optional = strategyCapabilities.filter(function(c) { return c.category === 'optional'; });
            let future = strategyCapabilities.filter(function(c) { return c.category === 'future'; });

            let newRoadmapItems = [];
            let existingRoadmap = this.roadmapItems;

            // Phase 1: Foundation - Required L0/L1 capabilities
            required.filter(function(c) { return ['', '0', '1', 'L0', 'L1'].indexOf(c.capability_level) !== -1; }).forEach(function(cap) {
                if (!existingRoadmap.find(function(r) { return r.capability_id === cap.element_id; })) {
                    newRoadmapItems.push({
                        name: 'Implement ' + cap.name,
                        description: 'Foundation: Establish ' + cap.name + ' capability (' + cap.capability_type + ')',
                        phase: 'phase1',
                        priority: 'critical',
                        duration_weeks: 4,
                        capability_id: cap.element_id,
                        capability_name: cap.name
                    });
                }
            });

            // Phase 2: Core - Required L2/L3 capabilities
            required.filter(function(c) { return ['2', '3', 'L2', 'L3'].indexOf(c.capability_level) !== -1; }).forEach(function(cap) {
                if (!existingRoadmap.find(function(r) { return r.capability_id === cap.element_id; })) {
                    newRoadmapItems.push({
                        name: 'Build ' + cap.name,
                        description: 'Core: Develop ' + cap.name + ' capability (' + cap.capability_type + ')',
                        phase: 'phase2',
                        priority: 'high',
                        duration_weeks: 3,
                        capability_id: cap.element_id,
                        capability_name: cap.name
                    });
                }
            });

            // Phase 3: Enhancement - Optional capabilities
            optional.forEach(function(cap) {
                if (!existingRoadmap.find(function(r) { return r.capability_id === cap.element_id; })) {
                    newRoadmapItems.push({
                        name: 'Enhance with ' + cap.name,
                        description: 'Enhancement: Add optional ' + cap.name + ' capability',
                        phase: 'phase3',
                        priority: 'medium',
                        duration_weeks: 2,
                        capability_id: cap.element_id,
                        capability_name: cap.name
                    });
                }
            });

            // Phase 4: Future capabilities
            future.forEach(function(cap) {
                if (!existingRoadmap.find(function(r) { return r.capability_id === cap.element_id; })) {
                    newRoadmapItems.push({
                        name: 'Plan ' + cap.name,
                        description: 'Future: Plan for ' + cap.name + ' capability',
                        phase: 'phase4',
                        priority: 'low',
                        duration_weeks: 1,
                        capability_id: cap.element_id,
                        capability_name: cap.name
                    });
                }
            });

            if (newRoadmapItems.length > 0) {
                this.roadmapItems = [].concat(this.roadmapItems, newRoadmapItems);
            }
        },

        // Export solution data in various formats
        exportSolutionData(format) {
            let strategyCapabilities = (this.selectedArchiMateElements.strategy || []).filter(
                function(e) { return e.element_type === 'Capability'; }
            );

            let exportData = {
                solution: {
                    name: this.formData.name,
                    description: this.formData.description,
                    solution_type: this.formData.solution_type,
                    business_domain: this.formData.business_domain,
                    status: this.formData.status
                },
                capabilities: strategyCapabilities,
                archimate_elements: this.selectedArchiMateElements,
                requirements: this.requirements,
                roadmap: this.roadmapItems
            };

            if (format === 'json') {
                this.downloadJSON(exportData);
            } else if (format === 'csv') {
                this.downloadCSV(exportData);
            } else if (format === 'png') {
                this.exportToPNG();
            }
        },

        downloadJSON(data) {
            let blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            let url = URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = url;
            a.download = 'solution-' + (this.formData.name || 'draft') + '-' + new Date().toISOString().slice(0,10) + '.json';
            a.click();
            URL.revokeObjectURL(url);
        },

        downloadCSV(data) {
            let rows = [];
            rows.push(['Section', 'Field', 'Value']);
            rows.push(['Solution', 'Name', data.solution.name || '']);
            rows.push(['Solution', 'Description', data.solution.description || '']);
            rows.push(['Solution', 'Type', data.solution.solution_type || '']);
            rows.push(['Solution', 'Domain', data.solution.business_domain || '']);

            rows.push([]);
            rows.push(['Capabilities', 'Name', 'Type', 'Level', 'Category']);
            data.capabilities.forEach(function(cap) {
                rows.push(['', cap.name, cap.capability_type, cap.capability_level, cap.category]);
            });

            Object.entries(data.archimate_elements).forEach(function(entry) {
                let layer = entry[0];
                let elements = entry[1];
                if (elements && elements.length > 0) {
                    rows.push([]);
                    rows.push(['ArchiMate ' + layer, 'Name', 'Type']);
                    elements.forEach(function(e) { rows.push(['', e.name, e.element_type]); });
                }
            });

            rows.push([]);
            rows.push(['Requirements', 'Title', 'Category', 'Priority']);
            data.requirements.forEach(function(req) {
                rows.push(['', req.title, req.category, req.priority]);
            });

            rows.push([]);
            rows.push(['Roadmap', 'Name', 'Phase', 'Duration (weeks)']);
            data.roadmap.forEach(function(item) {
                rows.push(['', item.name, item.phase, item.duration_weeks]);
            });

            let csv = rows.map(function(r) {
                return r.map(function(c) { return '"' + (c || '').toString().replace(/"/g, '""') + '"'; }).join(',');
            }).join('\n');
            let blob = new Blob([csv], { type: 'text/csv' });
            let url = URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = url;
            a.download = 'solution-' + (this.formData.name || 'draft') + '-' + new Date().toISOString().slice(0,10) + '.csv';
            a.click();
            URL.revokeObjectURL(url);
        },

        async exportToPNG() {
            // Use html2canvas if available
            if (typeof html2canvas !== 'undefined') {
                let element = document.querySelector('form');
                let canvas = await html2canvas(element, { scale: 2 });
                let url = canvas.toDataURL('image/png');
                let a = document.createElement('a');
                a.href = url;
                a.download = 'solution-' + (this.formData.name || 'draft') + '-' + new Date().toISOString().slice(0,10) + '.png';
                a.click();
            } else {
                Platform.toast.warning('PNG export requires html2canvas library. Please use JSON or CSV export.');
            }
        },

        // Open capability mapping modal using unified modal
        openCapabilityModal() {
            let self = this;
            window.SolutionFormState.currentCapabilityCategory = this.currentCapabilityCategory;
            openUnifiedMappingModalDiscovery({
                context: 'capability',
                onSaveCallback: function(mappings) {
                    // Add selected capabilities with current category
                    mappings.forEach(function(m) {
                        let existing = self.selectedCapabilities.find(function(c) { return c.capability_id === m.targetId; });
                        if (!existing) {
                            self.selectedCapabilities.push({
                                capability_id: m.targetId,
                                name: m.targetName,
                                category: window.SolutionFormState.currentCapabilityCategory,
                                description: m.description || ''
                            });
                        }
                    });
                    // Force Alpine reactivity
                    self.selectedCapabilities = [].concat(self.selectedCapabilities);
                }
            });
        },

        // Handle capabilities selected from unified modal event
        handleCapabilitiesSelected(detail) {
            if (detail && detail.mappings) {
                let self = this;
                detail.mappings.forEach(function(m) {
                    let existing = self.selectedCapabilities.find(function(c) { return c.capability_id === m.targetId; });
                    if (!existing) {
                        self.selectedCapabilities.push({
                            capability_id: m.targetId,
                            name: m.targetName,
                            category: window.SolutionFormState.currentCapabilityCategory,
                            description: m.description || ''
                        });
                    }
                });
                // Force Alpine reactivity
                self.selectedCapabilities = [].concat(self.selectedCapabilities);
            }
        },

        // Handle ArchiMate elements selected from unified modal event
        handleArchiMateSelected(detail) {
            if (detail && detail.mappings) {
                let self = this;
                detail.mappings.forEach(function(m) {
                    let layerKey = m.archimateLayer || self.activeLayer;
                    if (!self.selectedArchiMateElements[layerKey]) {
                        self.selectedArchiMateElements[layerKey] = [];
                    }
                    let existing = self.selectedArchiMateElements[layerKey].find(
                        function(e) { return e.element_id === m.targetId; }
                    );
                    if (!existing) {
                        self.selectedArchiMateElements[layerKey].push({
                            element_id: m.targetId,
                            element_table: m.elementTable || 'archimate_elements',
                            element_type: m.elementType || 'Element',
                            name: m.targetName,
                            color: self.layers.find(function(l) { return l.id === layerKey; })?.color || '#CCCCCC'
                        });
                    }
                });
                // Force Alpine reactivity
                self.selectedArchiMateElements = Object.assign({}, self.selectedArchiMateElements);
            }
        },

        // Open ArchiMate element modal using unified modal
        openArchiMateModal(layer) {
            let self = this;
            let targetLayer = layer || this.activeLayer;
            openUnifiedMappingModalDiscovery({
                context: 'archimate',
                onSaveCallback: function(mappings) {
                    // Add selected elements to the appropriate layer
                    mappings.forEach(function(m) {
                        let layerKey = m.archimateLayer || targetLayer;
                        if (!self.selectedArchiMateElements[layerKey]) {
                            self.selectedArchiMateElements[layerKey] = [];
                        }
                        let existing = self.selectedArchiMateElements[layerKey].find(
                            function(e) { return e.element_id === m.targetId; }
                        );
                        if (!existing) {
                            self.selectedArchiMateElements[layerKey].push({
                                element_id: m.targetId,
                                element_table: m.elementTable || 'archimate_elements',
                                element_type: m.elementType || 'Element',
                                name: m.targetName,
                                color: self.layers.find(function(l) { return l.id === layerKey; })?.color || '#CCCCCC'
                            });
                        }
                    });
                    // Force Alpine reactivity
                    self.selectedArchiMateElements = Object.assign({}, self.selectedArchiMateElements);
                }
            });
        },

        // Methods
        removeCapability(index) {
            this.selectedCapabilities.splice(index, 1);
            this.selectedCapabilities = [].concat(this.selectedCapabilities);
        },

        removeArchiMateElement(layerId, element) {
            let idx = this.selectedArchiMateElements[layerId].findIndex(function(e) {
                return e.element_id === element.element_id;
            });
            if (idx >= 0) {
                this.selectedArchiMateElements[layerId].splice(idx, 1);
                this.selectedArchiMateElements = Object.assign({}, this.selectedArchiMateElements);
            }
        },

        setCapabilityCategory(category) {
            this.currentCapabilityCategory = category;
            window.SolutionFormState.currentCapabilityCategory = category;
        },

        // Remove a requirement
        removeRequirement(index) {
            this.requirements.splice(index, 1);
            this.requirements = [].concat(this.requirements);
        },

        // Remove a roadmap item
        removeRoadmapItem(index) {
            this.roadmapItems.splice(index, 1);
            this.roadmapItems = [].concat(this.roadmapItems);
        },

        // Generate requirements using AI
        async generateRequirements() {
            if (!this.formData.description) {
                Platform.toast.warning('Please enter a description first');
                return;
            }

            this.isGeneratingRequirements = true;

            try {
                let response = await fetch('/solutions/ai-generate-requirements', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: this.formData.description,
                        solution_type: this.formData.solution_type,
                        business_domain: this.formData.business_domain,
                        capabilities: this.selectedCapabilities
                    })
                });

                let data = await response.json();
                if (data.success && data.requirements) {
                    this.requirements = data.requirements;
                } else {
                    Platform.toast.error('Failed to generate requirements: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error generating requirements:', error);
                Platform.toast.error('Failed to generate requirements. Please try again.');
            } finally {
                this.isGeneratingRequirements = false;
            }
        },

        // Generate roadmap using AI
        async generateRoadmap() {
            if (!this.formData.description) {
                Platform.toast.warning('Please enter a description first');
                return;
            }

            this.isGeneratingRoadmap = true;

            try {
                let response = await fetch('/solutions/ai-generate-roadmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: this.formData.description,
                        solution_type: this.formData.solution_type,
                        capabilities: this.selectedCapabilities,
                        archimate_elements: this.selectedArchiMateElements
                    })
                });

                let data = await response.json();
                if (data.success && data.roadmap_items) {
                    this.roadmapItems = data.roadmap_items;
                } else {
                    Platform.toast.error('Failed to generate roadmap: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error generating roadmap:', error);
                Platform.toast.error('Failed to generate roadmap. Please try again.');
            } finally {
                this.isGeneratingRoadmap = false;
            }
        },

        async aiPopulate() {
            if (!this.formData.description) {
                Platform.toast.warning('Please enter a description first');
                return;
            }

            this.isAIPopulating = true;

            try {
                // Suggest capabilities via AI
                let capResponse = await fetch('/solutions/ai-suggest-capabilities', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: this.formData.description,
                        solution_type: this.formData.solution_type,
                        business_domain: this.formData.business_domain
                    })
                });

                let capData = await capResponse.json();
                if (capData.success && capData.capabilities) {
                    this.selectedCapabilities = capData.capabilities.map(function(c) {
                        return {
                            capability_id: null,
                            name: c.name,
                            category: c.category || 'required',
                            rationale: c.rationale
                        };
                    });
                }

                // Add sample ArchiMate elements
                this.addSampleArchiMateElements();

                // Generate requirements using AI
                let reqResponse = await fetch('/solutions/ai-generate-requirements', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: this.formData.description,
                        solution_type: this.formData.solution_type,
                        business_domain: this.formData.business_domain,
                        capabilities: this.selectedCapabilities
                    })
                });
                let reqData = await reqResponse.json();
                if (reqData.success && reqData.requirements) {
                    this.requirements = reqData.requirements;
                }

                // Generate roadmap using AI
                let roadmapResponse = await fetch('/solutions/ai-generate-roadmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        description: this.formData.description,
                        solution_type: this.formData.solution_type,
                        capabilities: this.selectedCapabilities,
                        archimate_elements: this.selectedArchiMateElements
                    })
                });
                let roadmapData = await roadmapResponse.json();
                if (roadmapData.success && roadmapData.roadmap_items) {
                    this.roadmapItems = roadmapData.roadmap_items;
                }

            } catch (error) {
                console.error('Error in AI population:', error);
                Platform.toast.error('Failed to get AI suggestions. Please try again.');
            } finally {
                this.isAIPopulating = false;
            }
        },

        addSampleArchiMateElements() {
            this.selectedArchiMateElements = {
                motivation: [
                    { element_id: 'ai-1', element_table: 'stakeholders', element_type: 'Stakeholder', name: 'Solution Owner', color: '#B3A2C7' },
                    { element_id: 'ai-2', element_table: 'goals', element_type: 'Goal', name: 'Business Value Delivery', color: '#B3A2C7' }
                ],
                strategy: [
                    { element_id: 'ai-3', element_table: 'capabilities', element_type: 'Capability', name: 'Core Capability', color: '#F5D742' }
                ],
                business: [
                    { element_id: 'ai-4', element_table: 'business_processes', element_type: 'BusinessProcess', name: 'Main Process', color: '#FFFFB5' }
                ],
                application: [
                    { element_id: 'ai-5', element_table: 'application_components', element_type: 'ApplicationComponent', name: 'Main Application', color: '#B5E3FF' }
                ],
                technology: [
                    { element_id: 'ai-6', element_table: 'technology_nodes', element_type: 'Node', name: 'Infrastructure', color: '#C9E6B5' }
                ],
                implementation: [
                    { element_id: 'ai-7', element_table: 'work_packages', element_type: 'WorkPackage', name: 'Implementation Phase 1', color: '#FFB5B5' }
                ]
            };
        },

        async submitForm() {
            this.isSubmitting = true;

            try {
                let formData = Object.assign({}, this.formData, {
                    target_outcomes: this.formData.target_outcomes.split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s; }),
                    success_metrics: this.formData.success_metrics.split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s; }),
                    capabilities: this.selectedCapabilities,
                    archimate_elements: this.selectedArchiMateElements,
                    requirements: this.requirements,
                    roadmap_items: this.roadmapItems
                });

                let response = await fetch(APP_CONFIG.createSolutionUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                let result = await response.json();

                if (result.success) {
                    this.clearSessionStorage();
                    window.location.href = result.redirect_url || APP_CONFIG.listSolutionsUrl;
                } else {
                    Platform.toast.error('Error: ' + (result.error || 'Failed to create solution'));
                }
            } catch (error) {
                console.error('Error submitting form:', error);
                Platform.toast.error('Failed to create solution. Please try again.');
            } finally {
                this.isSubmitting = false;
            }
        },

        // sessionStorage key for wizard data persistence
        _storageKey: 'solution_create_wizard_data',

        // Save current form state to sessionStorage
        saveToSessionStorage() {
            try {
                let state = {
                    formData: this.formData,
                    selectedCapabilities: this.selectedCapabilities,
                    selectedArchiMateElements: this.selectedArchiMateElements,
                    requirements: this.requirements,
                    roadmapItems: this.roadmapItems,
                    activeLayer: this.activeLayer,
                    strategyCapabilityType: this.strategyCapabilityType,
                    strategyCapabilityLevel: this.strategyCapabilityLevel,
                    strategyCapabilityCategory: this.strategyCapabilityCategory
                };
                sessionStorage.setItem(this._storageKey, JSON.stringify(state));
            } catch (e) {
                console.warn('Failed to save wizard state to sessionStorage:', e);
            }
        },

        // Restore form state from sessionStorage
        restoreFromSessionStorage() {
            try {
                let saved = sessionStorage.getItem(this._storageKey);
                if (!saved) return false;

                let state = JSON.parse(saved);
                if (state.formData) {
                    Object.assign(this.formData, state.formData);
                }
                if (state.selectedCapabilities) {
                    window.SolutionFormState.selectedCapabilities = state.selectedCapabilities;
                }
                if (state.selectedArchiMateElements) {
                    window.SolutionFormState.selectedArchiMateElements = state.selectedArchiMateElements;
                }
                if (state.requirements) {
                    this.requirements = state.requirements;
                }
                if (state.roadmapItems) {
                    this.roadmapItems = state.roadmapItems;
                }
                if (state.activeLayer) {
                    this.activeLayer = state.activeLayer;
                }
                if (state.strategyCapabilityType) {
                    this.strategyCapabilityType = state.strategyCapabilityType;
                }
                if (state.strategyCapabilityLevel !== undefined) {
                    this.strategyCapabilityLevel = state.strategyCapabilityLevel;
                }
                if (state.strategyCapabilityCategory) {
                    this.strategyCapabilityCategory = state.strategyCapabilityCategory;
                }
                return true;
            } catch (e) {
                console.warn('Failed to restore wizard state from sessionStorage:', e);
                return false;
            }
        },

        // Clear sessionStorage after successful submission
        clearSessionStorage() {
            try {
                sessionStorage.removeItem(this._storageKey);
            } catch (e) {
                // Ignore
            }
        },

        init() {
            // Restore saved wizard state on page load
            let restored = this.restoreFromSessionStorage();
            if (restored) {
            }

            // Watch for form data changes and persist to sessionStorage
            this.$watch('formData', function() { this.saveToSessionStorage(); }.bind(this), { deep: true });
            this.$watch('requirements', function() { this.saveToSessionStorage(); }.bind(this));
            this.$watch('roadmapItems', function() { this.saveToSessionStorage(); }.bind(this));
            this.$watch('activeLayer', function() { this.saveToSessionStorage(); }.bind(this));

            // Periodically save complex state (capabilities, archimate elements)
            let self = this;
            setInterval(function() { self.saveToSessionStorage(); }, 5000);

            if (typeof lucide !== 'undefined') {
                this.$nextTick(function() { lucide.createIcons(); });
            }
        }
    }; });
});
