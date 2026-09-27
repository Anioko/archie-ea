let APP_CONFIG = window.__APP_CONFIG__ || {};

function businessContextApp() {
    return {
        currentStep: 1,
        totalSteps: 6,
        context: {
            id: null,
            name: '',
            description: '',
            organization: '',
            industry: '',
            drivers: [],
            objectives: [],
            constraints: [],
            metrics: [],
            capabilities: []
        },
        form: {
            project_name: '',
            organization: '',
            industry: '',
            business_problem: '',
            strategic_objectives: '',
            stakeholders: '',
            constraints: ''
        },
        submitting: false,
        statusMsg: '',
        errorMsg: '',
        analysisResults: null,

        // Driver management
        addDriver() {
            this.context.drivers.push({
                id: Date.now().toString(),
                name: '',
                description: '',
                category: 'strategic',
                impact_level: 'medium',
                timeframe: 'medium_term',
                stakeholders: []
            });
        },

        removeDriver(index) {
            this.context.drivers.splice(index, 1);
        },

        // Objective management
        addObjective() {
            this.context.objectives.push({
                id: Date.now().toString(),
                name: '',
                description: '',
                priority: 'medium',
                timeframe: '',
                owner: '',
                kpis: [],
                dependencies: []
            });
        },

        removeObjective(index) {
            this.context.objectives.splice(index, 1);
        },

        // Constraint management
        addConstraint() {
            this.context.constraints.push({
                id: Date.now().toString(),
                name: '',
                description: '',
                type: 'technical',
                impact: 'moderate',
                mitigation_strategy: ''
            });
        },

        removeConstraint(index) {
            this.context.constraints.splice(index, 1);
        },

        // Metric management
        addMetric() {
            this.context.metrics.push({
                id: Date.now().toString(),
                name: '',
                description: '',
                metric_type: 'kpi',
                current_value: 0,
                target_value: 0,
                unit: '',
                measurement_frequency: 'monthly',
                owner: ''
            });
        },

        removeMetric(index) {
            this.context.metrics.splice(index, 1);
        },

        // Capability management
        addCapability() {
            this.context.capabilities.push({
                id: Date.now().toString(),
                name: '',
                description: '',
                domain: '',
                level: 2,
                maturity: 'initial',
                strategic_importance: 'medium',
                business_value: '',
                current_state: '',
                target_state: '',
                gaps: [],
                gaps_text: '',
                dependencies: []
            });
        },

        removeCapability(index) {
            this.context.capabilities.splice(index, 1);
        },

        updateGaps(index) {
            let capability = this.context.capabilities[index];
            capability.gaps = capability.gaps_text.split('\n').filter(function(gap) { return gap.trim(); });
        },

        // Returns headers dict with Content-Type + CSRF token
        _csrfHeaders() {
            let h = { 'Content-Type': 'application/json' };
            let token = document.querySelector('meta[name="csrf-token"]');
            if (token) { h['X-CSRFToken'] = token.getAttribute('content'); }
            return h;
        },

        // Save context
        async saveContext() {
            try {
                let result = await Platform.fetch.post('/api/architecture-assistant/business-context', {
                    name: this.context.name,
                    description: this.context.description,
                    organization: this.context.organization,
                    industry: this.context.industry
                });

                if (result.success) {
                    this.context.id = result.data.id;
                    Platform.toast.success('Business context saved successfully!');

                    // Save individual components
                    await this.saveDrivers();
                    await this.saveObjectives();
                    await this.saveConstraints();
                    await this.saveMetrics();
                    await this.saveCapabilities();
                } else {
                    Platform.toast.error('Error saving context: ' + result.error);
                }
            } catch (error) {
                Platform.toast.error('Error saving context');
            }
        },

        // Save drivers
        async saveDrivers() {
            let failed = 0;
            for (let i = 0; i < this.context.drivers.length; i++) {
                let driver = this.context.drivers[i];
                if (!driver.saved) {
                    try {
                        await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/drivers', {
                            name: driver.name,
                            description: driver.description,
                            category: driver.category,
                            impact_level: driver.impact_level,
                            timeframe: driver.timeframe,
                            stakeholders: driver.stakeholders
                        });
                        driver.saved = true;
                    } catch (error) {
                        failed++;
                    }
                }
            }
            if (failed > 0) {
                Platform.toast.error(failed + ' driver' + (failed > 1 ? 's' : '') + ' failed to save');
            }
        },

        // Save objectives
        async saveObjectives() {
            let failed = 0;
            for (let i = 0; i < this.context.objectives.length; i++) {
                let objective = this.context.objectives[i];
                if (!objective.saved) {
                    try {
                        await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/objectives', {
                            name: objective.name,
                            description: objective.description,
                            priority: objective.priority,
                            timeframe: objective.timeframe,
                            owner: objective.owner,
                            kpis: objective.kpis,
                            dependencies: objective.dependencies
                        });
                        objective.saved = true;
                    } catch (error) {
                        failed++;
                    }
                }
            }
            if (failed > 0) {
                Platform.toast.error(failed + ' objective' + (failed > 1 ? 's' : '') + ' failed to save');
            }
        },

        // Save constraints
        async saveConstraints() {
            let failed = 0;
            for (let i = 0; i < this.context.constraints.length; i++) {
                let constraint = this.context.constraints[i];
                if (!constraint.saved) {
                    try {
                        await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/constraints', {
                            name: constraint.name,
                            description: constraint.description,
                            type: constraint.type,
                            impact: constraint.impact,
                            mitigation_strategy: constraint.mitigation_strategy
                        });
                        constraint.saved = true;
                    } catch (error) {
                        failed++;
                    }
                }
            }
            if (failed > 0) {
                Platform.toast.error(failed + ' constraint' + (failed > 1 ? 's' : '') + ' failed to save');
            }
        },

        // Save metrics
        async saveMetrics() {
            let failed = 0;
            for (let i = 0; i < this.context.metrics.length; i++) {
                let metric = this.context.metrics[i];
                if (!metric.saved) {
                    try {
                        await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/metrics', {
                            name: metric.name,
                            description: metric.description,
                            metric_type: metric.metric_type,
                            current_value: metric.current_value,
                            target_value: metric.target_value,
                            unit: metric.unit,
                            measurement_frequency: metric.measurement_frequency,
                            owner: metric.owner
                        });
                        metric.saved = true;
                    } catch (error) {
                        failed++;
                    }
                }
            }
            if (failed > 0) {
                Platform.toast.error(failed + ' metric' + (failed > 1 ? 's' : '') + ' failed to save');
            }
        },

        // Save capabilities
        async saveCapabilities() {
            let failed = 0;
            for (let i = 0; i < this.context.capabilities.length; i++) {
                let capability = this.context.capabilities[i];
                if (!capability.saved) {
                    try {
                        await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/capabilities', {
                            name: capability.name,
                            description: capability.description,
                            domain: capability.domain,
                            level: capability.level,
                            maturity: capability.maturity,
                            strategic_importance: capability.strategic_importance,
                            business_value: capability.business_value,
                            current_state: capability.current_state,
                            target_state: capability.target_state,
                            gaps: capability.gaps,
                            dependencies: capability.dependencies
                        });
                        capability.saved = true;
                    } catch (error) {
                        failed++;
                    }
                }
            }
            if (failed > 0) {
                Platform.toast.error(failed + ' capabilit' + (failed > 1 ? 'ies' : 'y') + ' failed to save');
            }
        },

        // Generate analysis
        async generateAnalysis() {
            if (!this.context.id) {
                Platform.toast.warning('Please save the business context first');
                return;
            }

            try {
                // Generate heatmap
                /* Each response is checked: unguarded, a 500 parsed cleanly, `.success`
                   was undefined, and the results panel opened with a null heatmap and
                   the literal strings "Error generating problem statement"/"…scope
                   definition" sitting where the analysis should be — a failure
                   presented as an analysis result. */
                let heatmapResult = await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/heatmap');

                // Generate problem statement
                let problemResult = await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/problem-statement');

                // Generate scope definition
                let scopeResult = await Platform.fetch.post('/api/architecture-assistant/business-context/' + this.context.id + '/scope');

                this.analysisResults = {
                    capability_heatmap: heatmapResult.success ? heatmapResult.data : null,
                    problem_statement: problemResult.success ? problemResult.data.problem_statement : 'Error generating problem statement',
                    scope_definition: scopeResult.success ? scopeResult.data.scope_definition : 'Error generating scope definition'
                };

                // Scroll to results
                document.querySelector('[x-show="analysisResults"]').scrollIntoView({ behavior: 'smooth' });

            } catch (error) {
                // Leave analysisResults untouched — a half-built result is worse than none.
                Platform.toast.error('Could not generate the analysis — ' + ((error && error.message) || 'request failed') + '. Nothing was produced.');
            }
        },

        async submitPhaseA() {
            // FAR-017: Prevent double-click duplicates
            if (this.submitting) return;
            this.errorMsg = '';
            this.statusMsg = '';

            if (!this.form.project_name.trim()) {
                this.errorMsg = 'Project name is required.';
                return;
            }
            if (!this.form.organization.trim()) {
                this.errorMsg = 'Organisation is required.';
                return;
            }
            if (!this.form.industry.trim()) {
                this.errorMsg = 'Industry is required.';
                return;
            }

            this.submitting = true;
            try {
                let result = await Platform.fetch.post('/api/architecture-assistant/business-context', {
                    name: this.form.project_name.trim(),
                    organization: this.form.organization.trim(),
                    industry: this.form.industry.trim(),
                    description: this.form.business_problem.trim(),
                    strategic_objectives: this.form.strategic_objectives.trim(),
                    stakeholders: this.form.stakeholders.trim(),
                    constraints: this.form.constraints.trim()
                }, { silent: true });

                if (result.context_id) {
                    sessionStorage.setItem('architecture_assistant_context_id', result.context_id);
                    this.context.id = result.context_id;
                    this.statusMsg = 'Business context saved. Context ID: ' + result.context_id;
                } else {
                    this.errorMsg = result.error || 'Failed to save business context.';
                }
            } catch (err) {
                this.errorMsg = 'Network error. Please try again.';
            } finally {
                this.submitting = false;
            }
        }
    }
}
