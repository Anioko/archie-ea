/**
 * Session Detail Page - External JavaScript
 * Extracted from app/templates/solutions/session_detail.html
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

function sessionDetail() {
    return {
        activeTab: 'overview',
        analysisResults: [],
        analysisLoading: false,
        analysisLoaded: false,
        analysisError: null,
        hasProblemDefinition: APP_CONFIG.hasProblemDefinition || false,

        // AI Design state
        aiElements: {},
        aiElementsSource: '',
        aiRequirements: [],
        aiRequirementsSource: '',
        aiRoadmap: [],
        aiRoadmapSource: '',
        aiPatterns: [],
        aiPatternMatchCount: 0,
        aiLoading: { elements: false, requirements: false, roadmap: false, patterns: false },
        aiGenerated: { elements: false, requirements: false, roadmap: false, patterns: false },
        aiExpandedLayers: { motivation: true, strategy: true, business: true, application: true, technology: true, implementation: true },

        // Accept recommendation state
        acceptingRec: null,

        // Analyze problem state
        analyzingProblem: false,
        motivationResults: null,

        // Apply suggestion state
        applyingElements: false,
        applyingRequirements: false,
        applyingRoadmap: false,

        // Scenario what-if state
        scenarioWeights: { cost: 25, capability: 25, risk: 20, strategic_fit: 15, implementation: 15 },
        scenarioLoading: false,
        scenarioResults: [],

        get scenarioWeightSum() {
            return this.scenarioWeights.cost + this.scenarioWeights.capability +
                   this.scenarioWeights.risk + this.scenarioWeights.strategic_fit +
                   this.scenarioWeights.implementation;
        },

        resumeAnalysis() {
            window.location.href = '/solutions/architect/workspace?session_id=' + APP_CONFIG.sessionId;
        },

        exportSession() {
            window.location.href = '/solutions/architect/sessions/' + APP_CONFIG.sessionId + '/export/pdf';
        },

        async loadAnalysisResults() {
            if (this.analysisLoaded) return;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/analysis-results', {
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success && data.has_results) {
                    this.analysisResults = data.recommendations.map(function(rec) {
                        return Object.assign({}, rec, {
                            _showPros: false,
                            _showCons: false
                        });
                    });
                }
                this.analysisLoaded = true;
            } catch (err) {
                console.error('Failed to load analysis results:', err);
                this.analysisLoaded = true;
            }
        },

        async runOptionsAnalysis() {
            this.analysisLoading = true;
            this.analysisError = null;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/run-analysis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success) {
                    this.analysisResults = data.recommendations.map(function(rec, idx) {
                        return {
                            option_type: rec.option_type,
                            rank: idx + 1,
                            score: rec.score || 0,
                            confidence: rec.score ? Math.min(1.0, rec.score / 100.0) : 0,
                            estimated_cost_min: rec.estimated_cost ? rec.estimated_cost * 0.8 : null,
                            estimated_cost_max: rec.estimated_cost ? rec.estimated_cost * 1.2 : null,
                            timeline_months: rec.timeline_months,
                            pros: rec.pros || [],
                            cons: rec.cons || [],
                            justification: rec.description || '',
                            _showPros: false,
                            _showCons: false
                        };
                    });
                    this.analysisLoaded = true;
                } else {
                    this.analysisError = data.error || 'Analysis failed. Please try again.';
                }
            } catch (err) {
                this.analysisError = 'Network error. Please check your connection and try again.';
                console.error('Options analysis error:', err);
            } finally {
                this.analysisLoading = false;
            }
        },

        async generateAIElements() {
            this.aiLoading.elements = true;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/ai-elements', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success && data.suggestions) {
                    this.aiElements = data.suggestions;
                    this.aiElementsSource = data.source || 'unknown';
                    this.aiGenerated.elements = true;
                }
            } catch (err) {
                console.error('AI elements generation error:', err);
            } finally {
                this.aiLoading.elements = false;
            }
        },

        async detectAIPatterns() {
            this.aiLoading.patterns = true;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/ai-patterns', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success && data.patterns) {
                    this.aiPatterns = data.patterns;
                    this.aiPatternMatchCount = data.match_count || 0;
                    this.aiGenerated.patterns = true;
                }
            } catch (err) {
                console.error('Pattern detection error:', err);
            } finally {
                this.aiLoading.patterns = false;
            }
        },

        async generateAIRequirements() {
            this.aiLoading.requirements = true;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/ai-requirements', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success && data.requirements) {
                    this.aiRequirements = data.requirements;
                    this.aiRequirementsSource = data.source || 'unknown';
                    this.aiGenerated.requirements = true;
                }
            } catch (err) {
                console.error('AI requirements generation error:', err);
            } finally {
                this.aiLoading.requirements = false;
            }
        },

        async generateAIRoadmap() {
            this.aiLoading.roadmap = true;
            try {
                let response = await fetch('/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/ai-roadmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await response.json();
                if (data.success && data.roadmap_items) {
                    this.aiRoadmap = data.roadmap_items;
                    this.aiRoadmapSource = data.source || 'unknown';
                    this.aiGenerated.roadmap = true;
                }
            } catch (err) {
                console.error('AI roadmap generation error:', err);
            } finally {
                this.aiLoading.roadmap = false;
            }
        },

        async acceptRecommendation(recommendationId) {
            if (!confirm('Accept this recommendation and create a Solution?')) return;
            this.acceptingRec = recommendationId;
            try {
                let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                let headers = { 'Content-Type': 'application/json' };
                if (csrfMeta) {
                    headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
                }
                let resp = await fetch(
                    '/solutions/architect/api/sessions/' +
                    APP_CONFIG.sessionId + '/accept-recommendation',
                    {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ recommendation_id: recommendationId })
                    }
                );
                let data = await resp.json();
                if (data.success) {
                    window.location.href = '/solutions/' + data.solution_id;
                } else {
                    Platform.toast.error('Failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('[sessionDetail] accept error:', err);
                Platform.toast.error('Failed to accept recommendation');
            } finally {
                this.acceptingRec = null;
            }
        },

        async analyzeProblem() {
            if (this.analyzingProblem) return;
            this.analyzingProblem = true;
            try {
                let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                let headers = { 'Content-Type': 'application/json' };
                if (csrfMeta) {
                    headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
                }
                let resp = await fetch(
                    '/solutions/architect/api/sessions/' +
                    APP_CONFIG.sessionId + '/analyze-problem',
                    {
                        method: 'POST',
                        headers: headers
                    }
                );
                let data = await resp.json();
                if (data.success) {
                    this.motivationResults = data;
                    // Reload page to show newly created motivation elements
                    window.location.reload();
                } else {
                    Platform.toast.error('Analysis failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('[sessionDetail] analyze error:', err);
                Platform.toast.error('Failed to run analysis. Please try again.');
            } finally {
                this.analyzingProblem = false;
            }
        },

        async applyElements() {
            if (this.applyingElements || !APP_CONFIG.solutionId) return;
            this.applyingElements = true;
            try {
                let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                let headers = { 'Content-Type': 'application/json' };
                if (csrfMeta) { headers['X-CSRFToken'] = csrfMeta.getAttribute('content'); }

                // Flatten aiElements into a list
                let elements = [];
                let self = this;
                Object.keys(this.aiElements).forEach(function(layer) {
                    (self.aiElements[layer] || []).forEach(function(elem) {
                        elements.push({
                            layer: layer,
                            type: elem.element_type || elem.type || '',
                            name: elem.name,
                            description: elem.description || ''
                        });
                    });
                });

                let resp = await fetch(
                    '/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/apply-elements',
                    {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ solution_id: APP_CONFIG.solutionId, elements: elements })
                    }
                );
                let data = await resp.json();
                if (data.success) {
                    Platform.toast.success('Applied ' + data.created + ' elements to solution.');
                } else {
                    Platform.toast.error('Failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('[sessionDetail] apply elements error:', err);
                Platform.toast.error('Failed to apply elements');
            } finally {
                this.applyingElements = false;
            }
        },

        async applyRequirements() {
            if (this.applyingRequirements) return;
            this.applyingRequirements = true;
            try {
                let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                let headers = { 'Content-Type': 'application/json' };
                if (csrfMeta) { headers['X-CSRFToken'] = csrfMeta.getAttribute('content'); }

                let requirements = this.aiRequirements.map(function(r) {
                    return {
                        name: r.title || r.name,
                        description: r.description || '',
                        type: r.category === 'Functional' ? 'FUNCTIONAL' : r.category === 'Non-Functional' ? 'QUALITY' : 'CONSTRAINT',
                        priority: r.priority === 'critical' ? 5 : r.priority === 'high' ? 4 : r.priority === 'medium' ? 3 : 2,
                        mandatory: r.priority === 'critical' || r.priority === 'high',
                        confidence: 0.8
                    };
                });

                let resp = await fetch(
                    '/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/apply-requirements',
                    {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ requirements: requirements })
                    }
                );
                let data = await resp.json();
                if (data.success) {
                    Platform.toast.success('Applied ' + data.created + ' requirements.');
                    window.location.reload();
                } else {
                    Platform.toast.error('Failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('[sessionDetail] apply requirements error:', err);
                Platform.toast.error('Failed to apply requirements');
            } finally {
                this.applyingRequirements = false;
            }
        },

        async applyRoadmap() {
            if (this.applyingRoadmap || !APP_CONFIG.solutionId) return;
            this.applyingRoadmap = true;
            try {
                let csrfMeta = document.querySelector('meta[name="csrf-token"]');
                let headers = { 'Content-Type': 'application/json' };
                if (csrfMeta) { headers['X-CSRFToken'] = csrfMeta.getAttribute('content'); }

                let roadmap_items = this.aiRoadmap.map(function(item, idx) {
                    return {
                        name: item.title || item.name || ('Phase ' + (idx + 1)),
                        description: item.description || '',
                        target_date: item.target_date || null,
                        order: idx
                    };
                });

                let resp = await fetch(
                    '/solutions/architect/api/sessions/' + APP_CONFIG.sessionId + '/apply-roadmap',
                    {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ solution_id: APP_CONFIG.solutionId, roadmap_items: roadmap_items })
                    }
                );
                let data = await resp.json();
                if (data.success) {
                    Platform.toast.success('Applied ' + data.created + ' roadmap phases.');
                } else {
                    Platform.toast.error('Failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('[sessionDetail] apply roadmap error:', err);
                Platform.toast.error('Failed to apply roadmap');
            } finally {
                this.applyingRoadmap = false;
            }
        },

        async recalculateScenario() {
            if (this.scenarioWeightSum !== 100 || this.analysisResults.length === 0) return;
            this.scenarioLoading = true;
            try {
                // Client-side recalculation using the existing scores and new weights
                let weights = {
                    cost: this.scenarioWeights.cost / 100,
                    capability: this.scenarioWeights.capability / 100,
                    risk: this.scenarioWeights.risk / 100,
                    strategic_fit: this.scenarioWeights.strategic_fit / 100,
                    implementation: this.scenarioWeights.implementation / 100,
                };

                // Recalculate weighted scores for each option
                let recalculated = this.analysisResults.map(function(rec) {
                    // Map option scores to weight dimensions
                    let baseScore = rec.score || 0;
                    let costFactor = weights.cost / 0.25;
                    let capFactor = weights.capability / 0.25;
                    let riskFactor = weights.risk / 0.20;
                    let stratFactor = weights.strategic_fit / 0.15;
                    let implFactor = weights.implementation / 0.15;
                    let avgFactor = (costFactor + capFactor + riskFactor + stratFactor + implFactor) / 5;
                    let adjustedScore = Math.min(100, Math.max(0, baseScore * avgFactor));

                    return {
                        option_type: rec.option_type,
                        score: Math.round(adjustedScore * 10) / 10,
                    };
                });

                // Sort by score descending
                recalculated.sort(function(a, b) { return b.score - a.score; });
                this.scenarioResults = recalculated;
            } catch (err) {
                console.error('Scenario recalculation error:', err);
            } finally {
                this.scenarioLoading = false;
            }
        }
    };
}
