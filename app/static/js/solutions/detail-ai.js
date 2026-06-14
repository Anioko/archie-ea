/**
 * solutions/detail-ai.js
 * AI Insights panel fetch functions extracted from detail.js (Phase 1 decomposition).
 * Methods are merged into Alpine.data("solutionDetail") via window._detailAI.
 * Load this file BEFORE detail.js in the HTML template.
 */
(function () {
    "use strict";
    window._detailAI = {
            // SAD-08: Load all 5 suggestion endpoints in parallel
            async loadAIInsights() {
                if (this.aiInsightsLoaded || this.aiInsightsLoading) return;
                const sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                if (!sid) return;
                this.aiInsightsLoading = true;
                const base = '/api/solutions/' + sid + '/suggestions/';
                const endpoints = [
                    ['vendors', base + 'vendors'],
                    ['costs', base + 'costs'],
                    ['risks', base + 'risks'],
                    ['actions', base + 'next-actions'],
                    ['archimate', base + 'archimate']
                ];
                await Promise.allSettled(endpoints.map(async ([key, url]) => {
                    try {
                        const r = await fetch(url, { credentials: 'same-origin' });
                        if (r.ok) this.aiInsightsData[key] = await r.json();
                    } catch (e) {
                        console.warn('[SAD-08] Failed to load ' + key + ':', e);
                    }
                }));
                this.aiInsightsLoaded = true;
                this.aiInsightsLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            // SAD-11: Open explainability modal for any AI-computed value
            async openExplainability(reasoningId) {
                if (!reasoningId) return;
                const sid = (window.__SOLUTION_CONFIG__ || {}).solutionId;
                this.explainOpen = true;
                this.explainLoading = true;
                this.explainData = null;
                try {
                    const r = await fetch('/solutions/api/' + sid + '/reasoning/' + reasoningId, { credentials: 'same-origin' });
                    if (r.ok) this.explainData = await r.json();
                } catch (e) {
                    console.warn('[SAD-11] explainability fetch failed:', e);
                }
                this.explainLoading = false;
                if (typeof lucide !== 'undefined') this.$nextTick(() => lucide.createIcons());
            },

            // ENH-003: Show explainability modal from already-loaded suggestion data (no extra fetch)
            showExplainabilityForSection(sectionKey) {
                if (!this.aiInsightsData || !this.aiInsightsData[sectionKey]) return;
                const section = this.aiInsightsData[sectionKey];
                if (section.explainability || section.recommendation_reasoning || section.reasoning_chain) {
                    this.explainData = section;
                    this.explainOpen = true;
                }
            },
            hasAnyExplainability() {
                if (!this.aiInsightsData) return false;
                const keys = ['vendors', 'costs', 'risks'];
                return keys.some(function (k) {
                    const s = this.aiInsightsData[k];
                    return s && (s.explainability || s.recommendation_reasoning || s.reasoning_chain);
                }, this);
            },

            // Helper: badge CSS for confidence score (0-1)
            confidenceBadge(score) {
                if (score == null) return 'bg-zinc-500/10 text-zinc-600 border-zinc-500/30';
                if (score >= 0.75) return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30';
                if (score >= 0.50) return 'bg-amber-500/10 text-amber-600 border-amber-500/30';
                return 'bg-destructive/10 text-destructive border-destructive/30';
            },
            confidencePct(score) {
                if (score == null) return '—';
                const pct = Math.round(score * 100);
                if (pct <= 0) return 'Not calculated';
                return pct + '%';
            },
    };
})();
