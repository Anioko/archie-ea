/**
 * solutions/detail-phase-e.js
 * Phase E options analysis, MCDA, vendor products — extracted from detail.js (Phase 1 decomposition).
 * Methods are merged into Alpine.data("solutionDetail") via window._detailPhaseE.
 * Load this file BEFORE detail.js in the HTML template.
 */
(function () {
    "use strict";
    window._detailPhaseE = {
            // SAD-04: Solution Options (MCDA)
            async loadSolutionOptions() {
                if (this.solutionOptionsLoaded || this.solutionOptionsLoading) return;
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                if (!sid) { this.solutionOptionsLoaded = true; return; }
                this.solutionOptionsLoading = true;
                try {
                    let r = await fetch('/solutions/' + sid + '/options', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
                    if (r.ok) {
                        let d = await r.json();
                        this.solutionOptions = (d.data || d.options || d || []);
                        if (!Array.isArray(this.solutionOptions)) this.solutionOptions = [];
                    }
                } catch (e) { console.warn('[SAD-04] solution options fetch failed:', e); }
                this.solutionOptionsLoaded = true;
                this.solutionOptionsLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            // --- AI element suggestions (SDX-005) ---
            _phaseToLayers(phase) {
                let map = {
                    'A': ['motivation', 'strategy'],
                    'B': ['business'],
                    'C': ['application'],
                    'D': ['technology'],
                    'E': ['implementation'],
                    'BCD': ['business', 'application', 'technology'],
                };
                return map[phase] || ['motivation', 'strategy', 'business', 'application', 'technology', 'implementation'];
            },

            async aiSuggestElements(phase) {
                if (this.suggestingElements) return;
                this.suggestingElements = true;
                this.aiSuggestPhase = phase;
                this.aiSuggestions = [];
                try {
                    // BPP-014: Use the context-aware suggestion pipeline
                    let resp = await fetch(this.apiBase + '/api/suggest-elements', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({ phases: [phase] })
                    });
                    let data = await resp.json();
                    if (data.suggestions && data.suggestions[phase]) {
                        let phaseSuggestions = data.suggestions[phase];
                        let all = [];
                        // Existing elements from enterprise catalog
                        const existing = phaseSuggestions.existing_elements || [];
                        for (let i = 0; i < existing.length; i++) {
                            all.push({
                                name: existing[i].name,
                                element_type: existing[i].type,
                                layer: existing[i].layer,
                                description: existing[i].reason || '',
                                confidence: existing[i].confidence,
                                element_id: existing[i].element_id,
                                relationship_type: existing[i].relationship_type,
                                is_existing: true
                            });
                        }
                        // New proposed elements
                        const newEls = phaseSuggestions.new_elements || [];
                        for (let j = 0; j < newEls.length; j++) {
                            all.push({
                                name: newEls[j].name,
                                element_type: newEls[j].type,
                                layer: newEls[j].layer,
                                description: newEls[j].reason || '',
                                confidence: newEls[j].confidence,
                                is_new: true
                            });
                        }
                        this.aiSuggestions = all;
                    } else if (data.error) {
                        // Fallback to legacy /ai-populate if new endpoint returns error
                        console.warn('[BPP-014] Suggest endpoint error, falling back:', data.error);
                        let fallback = await fetch(this.apiBase + '/ai-populate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
                            body: JSON.stringify({ phase: phase })
                        });
                        let fbData = await fallback.json();
                        if (fbData.success && fbData.suggestions) {
                            let layers = this._phaseToLayers(phase);
                            let all = [];
                            for (let k = 0; k < layers.length; k++) {
                                const layerItems = fbData.suggestions[layers[k]] || [];
                                for (let m = 0; m < layerItems.length; m++) {
                                    layerItems[m].layer = layers[k];
                                    all.push(layerItems[m]);
                                }
                            }
                            this.aiSuggestions = all;
                            this.aiReasoningStateId = fbData.reasoning_state_id || null;
                        }
                    }
                } catch (err) {
                    console.error('[solutionDetail] AI suggest error:', err);
                    Platform.toast.error('AI suggestion failed. Check console for details.');
                }
                this.suggestingElements = false;
            },

            async acceptSuggestion(idx) {
                let s = this.aiSuggestions[idx];
                if (!s) return;
                try {
                    let resp = await fetch(this.apiBase + '/archimate-elements', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({
                            elements: [{
                                element_id: 0,
                                element_table: 'ai_suggested',
                                layer_type: s.layer,
                                element_name: s.name,
                                relationship_type: s.element_type,
                                notes: s.description || ''
                            }]
                        })
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.aiSuggestions.splice(idx, 1);
                        this._recordAiFeedback(this.aiReasoningStateId, 'accept', s.layer + '-' + idx, 'archimate_element');
                        // KAN-003: Show chain completion result if inference engine ran
                        if (data.chain_result) {
                            let cr = data.chain_result;
                            let msg = 'Element accepted. Engine inferred ' + cr.nodes_created + ' element' + (cr.nodes_created !== 1 ? 's' : '') + ' and ' + cr.relationships_created + ' relationship' + (cr.relationships_created !== 1 ? 's' : '') + '.';
                            if (typeof this.showNotification === 'function') {
                                this.showNotification(msg, 'success');
                            } else {
                            }
                        }
                    }
                } catch (err) {
                    console.error('[solutionDetail] accept suggestion error:', err);
                }
            },

            dismissSuggestion(idx) {
                let s = this.aiSuggestions[idx];
                this._recordAiFeedback(this.aiReasoningStateId, 'reject', (s && s.layer ? s.layer : 'unknown') + '-' + idx, 'archimate_element');
                this.aiSuggestions.splice(idx, 1);
            },

            // KAN-003: Fetch inference preview for an element type (cached)
            async fetchInferencePreview(elementType) {
                if (this._inferencePreviewCache && this._inferencePreviewCache[elementType]) {
                    return this._inferencePreviewCache[elementType];
                }
                try {
                    let resp = await fetch(this.apiBase + '/ai/inference-preview?element_type=' + encodeURIComponent(elementType), {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (!resp.ok) return null;
                    let json = await resp.json();
                    let data = (json.success && json.data) ? json.data : json;
                    if (!this._inferencePreviewCache) this._inferencePreviewCache = {};
                    this._inferencePreviewCache[elementType] = data;
                    return data;
                } catch (e) {
                    console.warn('[KAN-003] Inference preview fetch failed:', e);
                    return null;
                }
            },

            // KAN-003: Toggle inference preview for a suggestion card
            async toggleInferencePreview(idx) {
                let s = this.aiSuggestions[idx];
                if (!s) return;
                // Toggle off if already showing
                if (s._previewExpanded) {
                    this.aiSuggestions[idx] = Object.assign({}, s, { _previewExpanded: false });
                    return;
                }
                // Fetch and attach preview data
                let preview = await this.fetchInferencePreview(s.element_type);
                this.aiSuggestions[idx] = Object.assign({}, s, {
                    _previewExpanded: true,
                    _previewData: preview
                });
            },

            // KAN-003: Clear inference preview cache (call after bulk operations)
            clearInferencePreviewCache() {
                this._inferencePreviewCache = {};
            },

            async runOptionsAnalysis() {
                this.analyzingOptions = true;
                try {
                    let resp = await fetch(this.apiBase + '/options/ai-analyze', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({})
                    });
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    let json = await resp.json();
                    if (json.success && json.data) {
                        this.recommendations = json.data;
                        this.refreshArchitectureVariantsFromRecommendations();
                    }
                } catch (err) {
                    console.error('[solutionDetail] options analysis error:', err);
                    Platform.toast.error('Options analysis failed. Check console for details.');
                }
                this.analyzingOptions = false;
            },

            refreshArchitectureVariantsFromRecommendations() {
                let variants = [];
                for (let i = 0; i < (this.recommendations || []).length; i++) {
                    let r = this.recommendations[i];
                    if (r.data_sources && r.data_sources.variant_type) {
                        variants.push({
                            id: r.id,
                            variant_type: r.data_sources.variant_type,
                            name: r.data_sources.name || r.data_sources.variant_type,
                            description: r.justification,
                            cost_estimate: r.data_sources.cost_estimate,
                            timeline_months: r.timeline_months || r.data_sources.timeline_months,
                            risk_profile: r.data_sources.risk_profile,
                            trade_offs: r.data_sources.trade_offs || []
                        });
                    }
                }
                this.architectureVariants = variants;
            },

            async loadArchitectureVariants() {
                this.generatingVariants = true;
                this.architectureVariants = [];
                try {
                    let resp = await fetch(this.apiBase + '/generate-variants', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify(this.draftBrief && this.draftBrief.problem_statement ? this.draftBrief : { problem_statement: this.solutionName || 'Generate architecture variants' })
                    });
                    let json = await resp.json().catch(function() { return {}; });
                    if (json.success && json.variants) {
                        this.architectureVariants = json.variants;
                        await this.refreshEntityData('option');
                    }
                } catch (err) {
                    console.error('[solutionDetail] generate variants error:', err);
                    Platform.toast.error('Generate variants failed. Check console for details.');
                }
                this.generatingVariants = false;
            },

            async applyVariant(recommendationId) {
                this.applyingVariantId = recommendationId;
                try {
                    let resp = await fetch(this.apiBase + '/apply-variant/' + recommendationId, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({})
                    });
                    let json = await resp.json().catch(function() { return {}; });
                    if (json.success) {
                        await this.refreshEntityData();
                        this.architectureVariants = [];
                    } else {
                        Platform.toast.error(json.error || 'Failed to apply variant.');
                    }
                } catch (err) {
                    console.error('[solutionDetail] apply variant error:', err);
                    Platform.toast.error('Apply variant failed.');
                }
                this.applyingVariantId = null;
            },

            // ── ENT-058: Options Analysis (TCO aggregation + MCDA scoring) ──

            async loadOptionsAnalysis() {
                if (this.optionsAnalysisLoading) return;
                this.optionsAnalysisLoading = true;
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                if (!sid) { this.optionsAnalysisLoading = false; return; }
                try {
                    let resp = await fetch('/solutions/' + sid + '/options-analysis', {
                        credentials: 'same-origin',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (resp.ok) {
                        let json = await resp.json();
                        if (json.success) {
                            this.optionsAnalysisData = json;
                            // Initialise MCDA criteria from response
                            if (json.mcda && json.mcda.criteria) {
                                this.mcdaCriteria = json.mcda.criteria.map(function(c) {
                                    return { name: c.name, weight: c.weight, description: c.description || '' };
                                });
                            }
                        }
                    }
                } catch (err) {
                    console.error('[ENT-058] options analysis fetch error:', err);
                }
                this.optionsAnalysisLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(function() { lucide.createIcons(); });
            },

            updateCriterionWeight(idx, value) {
                if (this.mcdaCriteria[idx]) {
                    this.mcdaCriteria[idx].weight = parseInt(value, 10) / 100;
                }
            },

            mcdaCriteriaTotal() {
                let total = 0;
                for (let i = 0; i < this.mcdaCriteria.length; i++) {
                    total += Math.round(this.mcdaCriteria[i].weight * 100);
                }
                return total;
            },

            async saveMcdaCriteria() {
                this.savingCriteria = true;
                let sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                try {
                    let resp = await fetch('/solutions/' + sid + '/options-analysis/criteria', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({ criteria: this.mcdaCriteria })
                    });
                    let json = await resp.json();
                    if (json.success) {
                        this.editingMcdaCriteria = false;
                    } else {
                        Platform.toast.error(json.error || 'Failed to save criteria.');
                    }
                } catch (err) {
                    console.error('[ENT-058] save MCDA criteria error:', err);
                    Platform.toast.error('Failed to save criteria weights.');
                }
                this.savingCriteria = false;
            },

            computeMcdaScore(criterion, option) {
                // Map criterion name to option data for scoring
                let name = (criterion.name || '').toLowerCase();
                if (name === 'cost' && option.estimated_cost_min !== null) {
                    // Invert: lower cost = higher score. Normalise against max cost across options.
                    let options = this.optionsAnalysisData.mcda.options;
                    let maxCost = 0;
                    for (let i = 0; i < options.length; i++) {
                        let c = options[i].estimated_cost_min || 0;
                        if (c > maxCost) maxCost = c;
                    }
                    if (maxCost === 0) return null;
                    return Math.round((1 - (option.estimated_cost_min / maxCost)) * 100);
                }
                if (name === 'time to value' && option.timeline_months) {
                    let opts = this.optionsAnalysisData.mcda.options;
                    let maxTime = 0;
                    for (let j = 0; j < opts.length; j++) {
                        let t = opts[j].timeline_months || 0;
                        if (t > maxTime) maxTime = t;
                    }
                    if (maxTime === 0) return null;
                    return Math.round((1 - (option.timeline_months / maxTime)) * 100);
                }
                if (name === 'risk' && this.optionsAnalysisData.risks) {
                    // Use option score as risk proxy (higher score = lower risk)
                    return option.score !== null ? Math.round(option.score * 100) : null;
                }
                if ((name === 'capability fit' || name === 'strategic alignment') && option.score !== null) {
                    return Math.round(option.score * 100);
                }
                // Fallback: use option score
                return option.score !== null ? Math.round(option.score * 100) : null;
            },

            computeWeightedTotal(option) {
                let total = 0;
                let hasAny = false;
                for (let i = 0; i < this.mcdaCriteria.length; i++) {
                    let score = this.computeMcdaScore(this.mcdaCriteria[i], option);
                    if (score !== null) {
                        total += score * this.mcdaCriteria[i].weight;
                        hasAny = true;
                    }
                }
                return hasAny ? Math.round(total) : null;
            },

            bestWeightedTotal() {
                if (!this.optionsAnalysisData || !this.optionsAnalysisData.mcda) return null;
                let best = -1;
                let options = this.optionsAnalysisData.mcda.options || [];
                for (let i = 0; i < options.length; i++) {
                    let wt = this.computeWeightedTotal(options[i]);
                    if (wt !== null && wt > best) best = wt;
                }
                return best > -1 ? best : null;
            },

            costBarWidth(option) {
                if (!option.estimated_cost_min) return 0;
                let options = this.optionsAnalysisData.mcda.options || [];
                let maxCost = 0;
                for (let i = 0; i < options.length; i++) {
                    let c = options[i].estimated_cost_max || options[i].estimated_cost_min || 0;
                    if (c > maxCost) maxCost = c;
                }
                if (maxCost === 0) return 0;
                return Math.round((option.estimated_cost_min / maxCost) * 100);
            },

            formatCurrency(value) {
                if (value === null || value === undefined) return '—';
                let config = window.__SOLUTION_CONFIG__ || {};
                let symbol = config.currencySymbol || '£';
                let num = parseFloat(value);
                if (isNaN(num)) return '—';
                if (num >= 1000000) return symbol + (num / 1000000).toFixed(1) + 'M';
                if (num >= 1000) return symbol + (num / 1000).toFixed(1) + 'K';
                return symbol + num.toFixed(0);
            },
    };
})();
