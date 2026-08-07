/* /ai-chat side panels: context, natural-language query, alerts and
 * recommendations, and the genome extraction rail.
 *
 * Ported verbatim from the inline script in
 * app/templates/ai_chat/index.html. The pieces that are easy to lose while
 * moving and are therefore called out here:
 *
 *   - /ai-chat/context/<domain> returns `elements` for architecture and
 *     `applications` for technology, and nothing recognisable otherwise. Each
 *     row is a data-action="select-context" target: the only click-path to
 *     element context.
 *   - switchTab's panel list must contain all four names. 'history' was
 *     missing, so choosing another tab never hid the Chats panel.
 *   - executeNLQuery hands advisory questions to the chat instead of the
 *     entity-lookup endpoint (ArchieChat.commands.isAdvisoryQuery).
 *   - genomePanel() is an Alpine component reached through
 *     window._genomePanelInstance after every answer when ?mode=genome, so it
 *     has to stay a global function.
 */
(function (window, document) {
    'use strict';

    var ArchieChat = (window.ArchieChat = window.ArchieChat || {});
    var state = ArchieChat.state;
    var render = ArchieChat.render;
    var appendSystemMessage = render.appendSystemMessage;
    /* The template used to shadow `fetch` with a CSRF-injecting wrapper for
       its whole inline block. Outside that block the wrapper has to be named. */
    var fetch = ArchieChat.transport.apiFetch;

    function personaConfig() { return window.personaConfig || {}; }
    function userInput() { return document.getElementById('user-input'); }
    function chatForm() { return document.getElementById('chat-form'); }
    function selectedElementIdInput() { return document.getElementById('selected-element-id'); }
    function isAdvisoryQuery(q) { return ArchieChat.commands.isAdvisoryQuery(q); }

    function updateSamplePrompts(persona) {
        if (!persona || !personaConfig()[persona]) return;
        const config = personaConfig()[persona];
        const prompts = config.sample_prompts || [];
        if (prompts.length > 0) {
            const promptsHtml = prompts.map(p => `<button type="button" data-action="use-prompt" data-prompt="${p.replace(/"/g, '&quot;')}" class="text-left p-2 rounded-lg border hover:bg-accent text-xs truncate">${p}</button>`).join('');
            const contextDiv = document.getElementById('domain-context');
            contextDiv.innerHTML = `
                <h3 class="font-medium text-sm mb-3">Sample Prompts for ${config.name}</h3>
                <div class="space-y-2">${promptsHtml}</div>
                <div class="mt-4 p-3 bg-muted/50 rounded-lg">
                    <h4 class="font-medium text-xs mb-2">Expertise Areas</h4>
                    <div class="flex flex-wrap gap-1">
                        ${(config.expertise || []).map(e => `<span class="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full">${e}</span>`).join('')}
                    </div>
                </div>
            `;
        }
    }

    async function loadDomainContext(domain) {
        try {
            const response = await fetch(`/ai-chat/context/${domain}`);
            const data = await response.json();

            const contextContainer = document.getElementById('domain-context');
            contextContainer.innerHTML = '';

            if (domain === 'architecture' && data.elements) {
                contextContainer.innerHTML = `
                    <h3 class="font-medium text-sm mb-3">ArchiMate Elements</h3>
                    <div class="space-y-2">
                        ${data.elements.map(el => `
                            <div class="rounded-lg border bg-card p-3 shadow-sm cursor-pointer hover:bg-accent transition-colors"
                                 data-action="select-context" data-id="${el.id}" data-type="archimate_element">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="bg-primary/10 text-primary text-[10px] px-1.5 py-0.5 rounded font-medium">${el.type}</span><!-- token-migration-ok -->
                                    <span class="font-medium text-sm">${el.name}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else if (domain === 'technology' && data.applications) {
                contextContainer.innerHTML = `
                    <h3 class="font-medium text-sm mb-3">Applications</h3>
                    <div class="space-y-2">
                        ${data.applications.map(app => `
                            <div class="rounded-lg border bg-card p-3 shadow-sm cursor-pointer hover:bg-accent transition-colors"
                                 data-action="select-context" data-id="${app.id}" data-type="application">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="bg-emerald-500/10 text-emerald-700 text-[10px] px-1.5 py-0.5 rounded font-medium">Application</span><!-- token-migration-ok -->
                                    <span class="font-medium text-sm">${app.name}</span>
                                </div>
                                <p class="text-xs text-muted-foreground">${app.technology || 'No technology info'}</p>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else {
                contextContainer.innerHTML = `
                    <div class="text-center py-8 text-muted-foreground">
                        <i data-lucide="inbox" class="h-8 w-8 mx-auto mb-2 opacity-50"></i>
                        <p class="text-sm">No specific context available for ${domain}</p>
                    </div>
                `;
            }

            // Re-initialize lucide icons
            lucide.createIcons();

        } catch (error) {
            console.error('Error loading domain context:', error);
        }
    }

    function selectContext(elementId, contextType) {
        selectedElementIdInput().value = elementId;
        state.contextElement = { id: elementId, type: contextType };

        // Visual feedback
        appendSystemMessage(`Context set: ${contextType} #${elementId}`, 'info');
    }

    // ==========================================================================
    // Sidebar Tab Management
    // ==========================================================================

    function switchSidebarTab(tab) {
        // 'history' was missing, so choosing another tab never hid the Chats
        // panel. The [id^="tab-"] reset below already covered all four.
        const panels = ['context', 'query', 'alerts', 'history'];

        // Hide all panels
        panels.forEach(panelName => {
            const panel = document.getElementById('panel-' + panelName);
            if (panel) {
                panel.classList.add('hidden');
                panel.style.display = '';
            }
        });

        // Reset all tab styles — remove active state including white background
        document.querySelectorAll('[id^="tab-"]').forEach(t => {
            t.classList.remove('border-b-2', 'border-primary', 'text-primary', 'bg-background');
            t.classList.add('text-muted-foreground');
        });

        // Show selected panel and style active tab
        const selectedPanel = document.getElementById('panel-' + tab);
        const selectedTab = document.getElementById('tab-' + tab);

        if (selectedPanel) {
            selectedPanel.classList.remove('hidden');
            selectedPanel.style.display = 'flex';
        }

        if (selectedTab) {
            selectedTab.classList.add('border-b-2', 'border-primary', 'text-primary', 'bg-background');
            selectedTab.classList.remove('text-muted-foreground');
        }

        // Load data for specific tabs
        if (tab === 'alerts') {
            loadRecommendations();
        }

        lucide.createIcons();
    }

    // ==========================================================================
    // Natural Language Query Functions
    // ==========================================================================

    async function executeNLQuery() {
        const input = document.getElementById('nl-query-input');
        const query = input.value.trim();
        if (!query) return;

        const resultsDiv = document.getElementById('nl-query-results');
        const resultsList = document.getElementById('nl-results-list');
        const explanationDiv = document.getElementById('nl-query-explanation');
        const countSpan = document.getElementById('nl-result-count');

        resultsDiv.classList.remove('hidden');

        // Advisory question -> hand off to the chat conversation pipeline.
        if (isAdvisoryQuery(query)) {
            input.value = '';
            if (explanationDiv) explanationDiv.classList.add('hidden');
            if (countSpan) countSpan.textContent = '';
            resultsList.innerHTML = '<div class="p-3 text-sm text-muted-foreground flex items-start gap-2">'
                + '<i data-lucide="messages-square" class="h-4 w-4 mt-0.5 shrink-0"></i>'
                + '<span>That\'s an advisory question — sent to the AI chat for a full answer. See the conversation →</span></div>';
            lucide.createIcons();
            userInput().value = query;
            if (chatForm().requestSubmit) { chatForm().requestSubmit(); }
            else { chatForm().dispatchEvent(new Event('submit', { cancelable: true, bubbles: true })); }
            const mc = document.getElementById('messages-container');
            if (mc) mc.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        resultsList.innerHTML = '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i></div>';
        lucide.createIcons();

        try {
            const response = await fetch('/ai-chat/nl-query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    persona: state.currentPersona
                })
            });

            const data = await response.json();

            if (data.success) {
                countSpan.textContent = data.result_count + ' found';
                explanationDiv.textContent = data.explanation || '';
                explanationDiv.classList.toggle('hidden', !data.explanation);

                if (data.results && data.results.length > 0) {
                    resultsList.innerHTML = data.results.map(item => `
                        <div class="p-2 border rounded-lg hover:bg-accent/50 cursor-pointer" data-action="show-entity" data-entity-type="${item.entity_type}" data-entity-id="${item.id}" data-entity-name="${item.name.replace(/"/g, '&quot;')}">
                            <div class="flex items-center justify-between mb-1">
                                <span class="text-sm font-medium">${item.name}</span>
                                <span class="text-xs bg-muted px-1.5 py-0.5 rounded">${item.entity_type}</span>
                            </div>
                            <p class="text-xs text-muted-foreground line-clamp-2">${item.description || item.status || item.business_owner || ''}</p>
                        </div>
                    `).join('');
                } else {
                    resultsList.innerHTML = '<p class="text-sm text-muted-foreground text-center py-4">No results found</p>';
                }

                // Show follow-up suggestions
                if (data.suggestions && data.suggestions.length > 0) {
                    resultsList.innerHTML += `
                        <div class="pt-3 border-t mt-3">
                            <p class="text-xs font-medium text-muted-foreground mb-2">Related queries:</p>
                            ${data.suggestions.map(s => `
                                <button type="button" data-quick-query="${s.replace(/"/g, '&quot;')}" class="block text-xs text-primary hover:underline mb-1">→ ${s}</button>
                            `).join('')}
                        </div>
                    `;
                }
            } else {
                resultsList.innerHTML = `
                    <div class="text-center py-4">
                        <p class="text-sm text-destructive mb-2">${data.error || 'Query failed'}</p>
                        ${data.suggestions ? data.suggestions.map(s => `<p class="text-xs text-muted-foreground">${s}</p>`).join('') : ''}
                    </div>
                `;
            }
        } catch (error) {
            resultsList.innerHTML = `<p class="text-sm text-destructive text-center py-4">Error: ${error.message}</p>`;
        }

        lucide.createIcons();
    }

    function runQuickQuery(query) {
        /* Every [data-quick-query] click funnels through here into
           /ai-chat/nl-query. A button carrying a slash command therefore posted
           the literal string to the natural-language query endpoint instead of
           running the command — including "/map-apqc", which IS a registered
           command, so it looked correct and quietly did the wrong thing.
           handleChatCommand is only reachable from the chat-form submit. */
        if (query.startsWith('/')) {
            userInput().value = query;
            chatForm().requestSubmit();
            return;
        }
        // Switch to Query tab first
        switchSidebarTab('query');
        // Set the query in the input
        document.getElementById('nl-query-input').value = query;
        // Execute the query after a small delay to ensure tab is visible
        setTimeout(() => executeNLQuery(), 150);
    }

    function askAboutRecommendation(title, description) {
        // Create a prompt asking the AI for help with this recommendation
        const prompt = `Help me implement this recommendation: "${title}"\n\nContext: ${description}\n\nPlease provide:\n1. Step-by-step implementation plan\n2. Key stakeholders to involve\n3. Potential challenges and mitigations\n4. Expected timeline and milestones`;

        // Set the prompt in the input field
        userInput().value = prompt;

        // Submit the form
        chatForm().dispatchEvent(new Event('submit'));
    }

    // ==========================================================================
    // Recommendations and Alerts Functions
    // ==========================================================================

    function exportContextLog() {
        const contextEl = document.getElementById('domain-context');
        const descEl = document.getElementById('context-description');
        const lines = [
            'A.R.C.H.I.E. Context Log',
            'Exported: ' + new Date().toISOString(),
            '---',
            'Domain: ' + (document.getElementById('domain-selector')?.value || 'global'),
            'Context: ' + (descEl?.textContent?.trim() || 'Global'),
            '---',
            contextEl?.innerText?.trim() || 'No context items selected.',
        ];
        const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'archie-context-' + Date.now() + '.txt';
        a.click();
        URL.revokeObjectURL(url);
    }

    async function loadRecommendations(refresh = false) {
        const alertsList = document.getElementById('alerts-list');
        const recsContent = document.getElementById('recs-content');
        const healthScore = document.getElementById('health-score');
        const healthBar = document.getElementById('health-bar');
        const alertBadge = document.getElementById('alert-badge');

        alertsList.innerHTML = '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i></div>';
        lucide.createIcons();

        try {
            const response = await fetch(`/ai-chat/recommendations?persona=${state.currentPersona}&refresh=${refresh}`);
            const data = await response.json();

            // Update health score
            const score = data.health_score || 0;
            healthScore.textContent = score + '%';
            healthBar.style.width = score + '%';

            // Color based on score
            if (score >= 70) { // token-migration-ok — health score status colors
                healthScore.className = 'text-lg font-bold text-emerald-600'; // token-migration-ok
                healthBar.className = 'bg-emerald-500 h-2 rounded-full transition-all'; // token-migration-ok
            } else if (score >= 40) {
                healthScore.className = 'text-lg font-bold text-amber-600'; // token-migration-ok
                healthBar.className = 'bg-amber-500 h-2 rounded-full transition-all'; // token-migration-ok
            } else {
                healthScore.className = 'text-lg font-bold text-destructive'; // token-migration-ok
                healthBar.className = 'bg-destructive h-2 rounded-full transition-all'; // token-migration-ok
            }

            // Update alert badge
            const criticalCount = (data.summary?.critical_count || 0) + (data.summary?.high_count || 0);
            if (criticalCount > 0) {
                alertBadge.textContent = criticalCount > 99 ? '99+' : criticalCount;
                alertBadge.classList.remove('hidden');
                alertBadge.style.display = 'flex';
            } else {
                alertBadge.classList.add('hidden');
                alertBadge.style.display = 'none';
            }

            // Render alerts with action links (no inline onclick — use addEventListener)
            if (data.alerts && data.alerts.length > 0) {
                let alertHtml = '';
                data.alerts.slice(0, 5).forEach(function(alert) {
                    let actions = '';
                    if (alert.action_url) {
                        actions += '<a href="' + alert.action_url + '" class="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"><i data-lucide="external-link" class="h-3 w-3"></i>' + (alert.action_label || 'Open') + '</a>';
                    }
                    if (alert.query) {
                        actions += (actions ? '<span class="text-muted-foreground mx-1">|</span>' : '');
                        actions += '<button type="button" class="text-xs text-primary hover:underline js-alert-query" data-query="' + alert.query.replace(/"/g, '&quot;') + '"><i data-lucide="search" class="h-3 w-3 inline"></i> Ask AI</button>';
                    }
                    alertHtml += '<div class="p-3 border rounded-lg mb-2 ' + getPriorityBorderClass(alert.priority) + '">' +
                        '<div class="flex items-start justify-between gap-2 mb-1">' +
                        '<span class="text-sm font-medium">' + alert.title + '</span>' +
                        '<span class="text-xs px-1.5 py-0.5 rounded shrink-0 ' + getPriorityBadgeClass(alert.priority) + '">' + alert.priority + '</span>' +
                        '</div>' +
                        '<p class="text-xs text-muted-foreground mb-2">' + alert.description + '</p>' +
                        '<div class="flex items-center gap-1 flex-wrap">' + actions + '</div></div>';
                });
                alertsList.innerHTML = alertHtml;
                alertsList.querySelectorAll('.js-alert-query').forEach(function(btn) {
                    btn.addEventListener('click', function() { runQuickQuery(this.dataset.query); });
                });
            } else {
                alertsList.innerHTML = '<p class="text-sm text-center text-muted-foreground py-4"><i data-lucide="check-circle" class="h-5 w-5 mx-auto mb-2 text-emerald-500"></i>No active alerts</p>'; // token-migration-ok
            }

            // Render recommendations with details (steps, benefits, timeline)
            if (data.recommendations && data.recommendations.length > 0) {
                let recHtml = '';
                data.recommendations.slice(0, 3).forEach(function(rec) {
                    let details = '';
                    if (rec.steps && rec.steps.length > 0) {
                        details += '<div class="mt-2 text-[11px] text-muted-foreground space-y-1">';
                        if (rec.timeline) details += '<div><strong>Timeline:</strong> ' + rec.timeline + ' · <strong>Effort:</strong> ' + (rec.effort || 'TBD') + '</div>';
                        details += '<div class="font-medium mt-1">Steps:</div><ol class="list-decimal pl-4 space-y-0.5">';
                        rec.steps.forEach(function(s) { details += '<li>' + s + '</li>'; });
                        details += '</ol>';
                        if (rec.benefits && rec.benefits.length > 0) {
                            details += '<div class="font-medium mt-1">Benefits:</div><ul class="list-disc pl-4">';
                            rec.benefits.forEach(function(b) { details += '<li>' + b + '</li>'; });
                            details += '</ul>';
                        }
                        details += '</div>';
                    }
                    recHtml += '<div class="p-2 border rounded-lg mb-2 bg-gradient-to-r from-primary/5 to-transparent">' +
                        '<div class="flex items-center justify-between mb-1">' +
                        '<span class="text-xs font-medium">' + rec.title + '</span>' +
                        '<span class="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">' + (rec.impact_score || 0) + '%</span>' +
                        '</div>' +
                        '<p class="text-[11px] text-muted-foreground">' + (rec.description || '').substring(0, 100) + '</p>' +
                        details +
                        '<div class="flex gap-2 mt-2">' +
                        '<button type="button" class="text-[10px] text-primary hover:underline js-rec-item" data-title="' + (rec.title || '').replace(/"/g, '&quot;') + '" data-desc="' + (rec.description || '').substring(0, 200).replace(/"/g, '&quot;') + '"><i data-lucide="message-circle" class="h-3 w-3 inline"></i> Ask AI to help</button>' +
                        '</div></div>';
                });
                recsContent.innerHTML = recHtml;
                recsContent.querySelectorAll('.js-rec-item').forEach(function(el) {
                    el.addEventListener('click', function() {
                        askAboutRecommendation(this.dataset.title, this.dataset.desc);
                    });
                });
            } else {
                recsContent.innerHTML = '<p class="text-xs text-muted-foreground">No recommendations at this time.</p>';
            }

        } catch (error) {
            alertsList.innerHTML = `<p class="text-sm text-destructive text-center py-4">Error loading data</p>`;
        }

        lucide.createIcons();
    }

    function refreshRecommendations() {
        loadRecommendations(true);
    }

    /* Four distinct levels from the semantic palette. Amber has no semantic
       token of its own (DESIGN.md), so high and medium are separated by
       weight — solid warning vs a muted warning — rather than by hue. */
    function getPriorityBorderClass(priority) {
        const classes = {
            'critical': 'border-l-4 border-l-destructive',
            'high': 'border-l-4 border-l-warning',
            'medium': 'border-l-4 border-l-warning/50',
            'low': 'border-l-4 border-l-info'
        };
        return classes[priority] || '';
    }

    /* Coloured text on its own tint needs the -emphasis variant, not the base
       token. The previous raw-scale values scored 2.35, 2.60 and 3.85 against
       their own tints — all far under the AA 4.5 required for normal text. */
    function getPriorityBadgeClass(priority) {
        const classes = {
            'critical': 'bg-destructive/10 text-destructive-emphasis',
            'high': 'bg-warning/10 text-warning-emphasis',
            'medium': 'bg-muted text-muted-foreground',
            'low': 'bg-info/10 text-info-emphasis'
        };
        return classes[priority] || 'bg-muted text-foreground';
    }

    /* Genome extraction rail — an Alpine component, so it must remain a
       global function for x-data="genomePanel()" to resolve it, and the
       instance is published on window._genomePanelInstance by x-init because
       the chat pipeline calls extractAfterMessage() after every answer. */
    function genomePanel() {
        return {
            isGenomeMode: new URLSearchParams(window.location.search).get('mode') === 'genome',
            genome: {},
            completeness: 0,
            readyToGenerate: false,
            genomeItems: [],

            async extractAfterMessage(conversation) {
                if (!this.isGenomeMode) return;
                try {
                    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
                    const resp = await fetch('/api/codegen/genome/extract', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrf,
                        },
                        body: JSON.stringify({ conversation, current_genome: this.genome })
                    });
                    if (!resp.ok) return;
                    const data = await resp.json();
                    if (!data.success) return;

                    this.genome = data.genome_partial;
                    this.completeness = data.completeness_pct;
                    this.readyToGenerate = data.ready_to_generate;
                    this._refreshItems();
                } catch (e) {
                    console.warn('Genome extraction failed:', e);
                }
            },

            _refreshItems() {
                const g = this.genome;
                const allItems = [
                    {
                        key: 'problem',
                        label: 'Problem',
                        value: g.problem?.statement ? g.problem.statement.slice(0, 100) : '',
                        status: g.problem?.statement ? 'confirmed' : 'pending'
                    },
                    {
                        key: 'entities',
                        label: 'Entities',
                        value: Object.keys(g.modules || {})
                            .flatMap(m => Object.keys((g.modules[m]?.entities) || {}))
                            .join(', '),
                        status: Object.keys(g.modules || {}).length > 0 ? 'confirmed' : 'pending'
                    },
                    {
                        key: 'auth',
                        label: 'Authentication',
                        value: g.infrastructure?.auth?.provider || '',
                        status: g.infrastructure?.auth?.provider ? 'confirmed' : 'pending'
                    },
                    {
                        key: 'tenancy',
                        label: 'Multi-tenancy',
                        value: g.security?.multi_tenancy?.enabled != null
                            ? (g.security.multi_tenancy.enabled ? 'Yes — isolated per org' : 'Single shared system')
                            : '',
                        status: g.security?.multi_tenancy?.enabled != null ? 'confirmed' : 'pending'
                    },
                    {
                        key: 'notifications',
                        label: 'Notifications',
                        value: (g.notifications?.channels || []).join(', '),
                        status: g.notifications?.channels?.length > 0 ? 'confirmed' : 'pending'
                    },
                    {
                        key: 'payments',
                        label: 'Payments',
                        value: g.payments?.provider && g.payments.provider !== 'none' ? g.payments.provider : '',
                        status: g.payments?.provider && g.payments.provider !== 'none' ? 'confirmed' : 'pending'
                    },
                ];
                // Show confirmed items + first pending item
                const confirmed = allItems.filter(i => i.status === 'confirmed');
                const firstPending = allItems.find(i => i.status === 'pending');
                this.genomeItems = firstPending ? [...confirmed, firstPending] : confirmed;
            },

            generate() {
                if (!this.readyToGenerate) return;
                // The old /codegen/workbench destination never existed (404 dead-end).
                // The Architecture Journey wizard is the canonical idea-to-code flow;
                // the genome draft is kept in sessionStorage for future prefill work.
                sessionStorage.setItem('genome_draft', JSON.stringify(this.genome));
                window.location.href = '/architecture-journey/';
            }
        };
    }

    ArchieChat.panels = {
        switchTab: switchSidebarTab,
        loadDomainContext: loadDomainContext,
        selectContext: selectContext,
        updateSamplePrompts: updateSamplePrompts,
        executeNLQuery: executeNLQuery,
        runQuickQuery: runQuickQuery,
        loadRecommendations: loadRecommendations,
        refreshRecommendations: refreshRecommendations,
        exportContextLog: exportContextLog,
        genomePanel: genomePanel
    };

    /* Alpine expressions and the markup resolve these off window. */
    window.switchSidebarTab = switchSidebarTab;
    window.executeNLQuery = executeNLQuery;
    window.runQuickQuery = runQuickQuery;
    window.refreshRecommendations = refreshRecommendations;
    window.exportContextLog = exportContextLog;
    window.genomePanel = genomePanel;
})(window, document);
