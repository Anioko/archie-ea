/* /ai-chat page wiring.
 *
 * What is left once transport, render, commands and panels have been pulled
 * out: the selectors, the submit path, the delegated data-action vocabulary,
 * the entity modal, the create-solution modal, the document panel and mobile
 * sidebar toggles, the deep-link handling, and the conversation history rail.
 *
 * Seams that are invisible from the markup and break silently — do not remove
 * without reading spec §12.3:
 *   - the five window CustomEvents (add-document-analysis, show-notification,
 *     ask-question, link-to-entity, create-entity) are the ONLY connection
 *     between document_upload.js and the transcript;
 *   - the approvals modal opens through data-modal-open / data-modal-close and
 *     the `hidden` ATTRIBUTE, served by ui/modal.js. It is not Alpine. Turning
 *     it into x-show silently breaks the badge button;
 *   - window.loadSessionList is called from the streaming path and the
 *     non-streaming path. Lose it and a new chat does not appear in the rail
 *     until the page is reloaded.
 */
(function (window, document) {
    'use strict';

    var ArchieChat = window.ArchieChat;

    // Enhanced JavaScript for multi-domain chat with persona support

    /* The CSRF-injecting fetch wrapper that used to shadow `fetch` for this
       whole block now lives in transport.js, so every module shares it. */
    const fetch = ArchieChat.transport.apiFetch;

    const messagesContainer = document.getElementById('messages-container');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const domainSelector = document.getElementById('domain-selector');
    const personaSelector = document.getElementById('persona-selector');
    const modelSelector = document.getElementById('model-selector');
    const selectedElementIdInput = document.getElementById('selected-element-id');

    // Get configurations from window object
    let domainConfig = window.domainConfig || {};
    let personaConfig = window.personaConfig || {};

    /* Conversation state and rendering now live in ai_chat/render.js, because
       more than one module reads them. `state` is the same object every module
       sees — assigning state.currentDomain here is visible to render.js. */
    const state = ArchieChat.state;
    const {
        getColorClass, appendMessage, appendSystemMessage, appendError,
        beginStreamedMessage, updateStreamedMessage, finaliseStreamedMessage
    } = ArchieChat.render;
    const {
        handle: handleChatCommand, detectArchimateFreeformIntent,
        handleArchimateFreeform, applyApqcMappings, handleGapAnalysis,
        handleDiscoverVendors, handleArchitectViewpoints, handleArbReady
    } = ArchieChat.commands;
    const {
        switchTab: switchSidebarTab, loadDomainContext, selectContext,
        updateSamplePrompts, runQuickQuery, loadRecommendations
    } = ArchieChat.panels;

    // Welcome UI helpers — hide suggestion chips on first user send
    function _hideWelcomeUI() {
        document.getElementById('suggestion-chips')?.classList.add('hidden');
        document.getElementById('domain-welcome-grid')?.classList.add('hidden');
    }

    function setSuggestion(text) {
        const ta = document.getElementById('user-input');
        if (ta) {
            ta.value = text;
            ta.focus();
        }
    }

    // Hide chips on first form submit
    document.getElementById('chat-form')?.addEventListener('submit', _hideWelcomeUI, { once: true });

    // Load available models
    async function loadAvailableModels() {
        try {
            const models = await ArchieChat.transport.loadModels();

            // Clear existing options
            modelSelector.innerHTML = '<option value="">Auto-Select Model</option>';

            // Add available models
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.model;
                option.textContent = model.display_name;

                // Add recommended for info
                if (model.recommended_for && model.recommended_for.length > 0) {
                    option.textContent += ` (${model.recommended_for[0]})`;
                }

                if (model.is_fallback) {
                    option.textContent += ` [Fallback ${model.fallback_order}]`;
                }

                if (model.test_status === 'failed') {
                    option.textContent += ' [Provider Warning]';
                }

                modelSelector.appendChild(option);
            });
        } catch (error) {
            modelSelector.innerHTML = '<option value="">Models unavailable</option>';
            console.error('Error loading models:', error);
        }
    }

    // Initialize domain selector
    domainSelector.addEventListener('change', (e) => {
        state.currentDomain = e.target.value;
        updateDomainUI(state.currentDomain);
        loadDomainContext(state.currentDomain);
    });

    // Initialize persona selector
    personaSelector.addEventListener('change', (e) => {
        state.currentPersona = e.target.value;
        updatePersonaUI(state.currentPersona);
        if (state.currentPersona && personaConfig[state.currentPersona]) {
            // Auto-switch to persona's default domain
            const defaultDomain = personaConfig[state.currentPersona].default_domain;
            if (defaultDomain && defaultDomain !== state.currentDomain) {
                domainSelector.value = defaultDomain;
                state.currentDomain = defaultDomain;
                updateDomainUI(state.currentDomain);
                loadDomainContext(state.currentDomain);
            }
            // Show sample prompts
            updateSamplePrompts(state.currentPersona);
        }
    });

    function updatePersonaUI(persona) {
        if (!persona || !personaConfig[persona]) {
            // Reset to default
            document.getElementById('domain-description').textContent = 'Select a domain for specialized assistance';
            return;
        }
        const config = personaConfig[persona];
        document.getElementById('domain-description').textContent = config.description || config.name;
        appendSystemMessage(`Persona switched to: ${config.name}`, 'info');
    }

    function usePrompt(prompt) {
        userInput.value = prompt;
        userInput.focus();
    }

    function updateDomainUI(domain) {
        const config = domainConfig[domain];
        if (!config) return;

        // Update header
        document.getElementById('domain-title').textContent = config.name;
        document.getElementById('domain-description').textContent = config.description;

        // Update icon
        const iconElement = document.getElementById('domain-icon');
        iconElement.innerHTML = `<i data-lucide="${config.icon}" class="h-5 w-5"></i>`;

        // Update colors using safe class mapping
        const bgClass = getColorClass(config.color || 'primary', 'bg');
        iconElement.className = `flex h-9 w-9 items-center justify-center rounded-lg ${bgClass} text-primary-foreground transition-all duration-300`; // token-migration-ok

        // Re-initialize lucide icons
        lucide.createIcons();
    }

    /* updateTemplateOptions() lived here. template_name was validated and
       HTML-sanitised by chat_core and then discarded — AgentRunner.run() has no
       such parameter and nothing read it after line 362 — so the dropdown it
       filled, and the AIPromptTemplate query behind it, affected no answer ever
       produced. Removed rather than left as decoration. */

    function handleEnter(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    }

    /* Enter sends; Shift+Enter newlines.
       handleEnter() (defined above) was written for this and never bound - there
       were zero keydown listeners in the file - so the composer was a plain
       3-row textarea where Enter inserted a newline and the ONLY way to send a
       message was clicking the button. That is the first thing a user tries, and
       it is also an accessibility defect: the chat could not be submitted from
       the keyboard at all. */
    userInput.addEventListener('keydown', handleEnter);

    /* Send and Stop swap places while a turn is in flight. Salvaged from
       ai_chat.js, the 169 KB file no template loads: #stop-btn has been in the
       markup all along with its handler in a file that never ran. */
    function _setSendingUI(sending) {
        const sendBtn = document.getElementById('send-btn');
        const stopBtn = document.getElementById('stop-btn');
        if (sendBtn) { sendBtn.disabled = sending; sendBtn.classList.toggle('hidden', sending); }
        if (stopBtn) { stopBtn.classList.toggle('hidden', !sending); }
    }

    document.getElementById('stop-btn')?.addEventListener('click', () => {
        ArchieChat.transport.abort();
        _setSendingUI(false);
    });

    // Enhanced form submission
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        _submitTurn().finally(() => _setSendingUI(false));
    });

    async function _submitTurn() {
        const message = userInput.value.trim();
        if (!message) return;
        _setSendingUI(true);

        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';

        // Add user message to history
        const timestamp = new Date().toISOString();
        state.chatHistory.push({ role: 'user', content: message, timestamp });
        appendMessage('user', message);

        // Check for client-side commands (actionable architect workflows)
        if (message.startsWith('/')) {
            const handled = await handleChatCommand(message);
            if (handled) return;
        }

        // ENT-122: intercept NL ArchiMate intent before regular chat
        if (detectArchimateFreeformIntent(message)) {
            await handleArchimateFreeform(message);
            return;
        }

        await _deliverTurn(message, timestamp);
    }

    /* The network half of a turn, separated from _submitTurn so the error
       card's Retry can run it again without echoing the user's message into
       the transcript a second time. */
    async function _deliverTurn(message, timestamp) {
        // Show loading indicator
        const loadingId = 'loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.className = 'flex gap-4';
        const loadingGradient = getColorClass(domainConfig[state.currentDomain]?.color || 'primary', 'gradient');
        loadingDiv.innerHTML = `
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${loadingGradient} text-primary-foreground shadow-lg"><!-- token-migration-ok -->
                <i data-lucide="${domainConfig[state.currentDomain]?.icon || 'bot'}" class="h-5 w-5 animate-pulse"></i>
            </div>
            <div class="rounded-xl bg-muted/50 p-4 text-sm flex items-center gap-3">
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                    <div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                    <div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                </div>
                <span class="text-muted-foreground">Thinking...</span>
            </div>
        `;
        messagesContainer.appendChild(loadingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        lucide.createIcons();

        const startTime = performance.now();
        // Shared payload. thread_id keeps multi-turn chats in one conversation.
        const _payload = JSON.stringify({
            message: message,
            domain: state.currentDomain,
            element_id: selectedElementIdInput.value || null,
            context_type: state.contextElement?.type || null,
            persona: state.currentPersona || null,
            model: document.getElementById('model-selector')?.value || null,
            thread_id: window.__threadId || null,
        });

        // Stream the reply token-by-token (like ChatGPT). If streaming can't be
        // established, fall through to the non-streaming request below.
        try { if (await streamAiReply(_payload, loadingId, startTime, timestamp)) return; }
        catch (_streamErr) {
            /* A user-initiated stop is not a transport failure: re-issuing the
               turn against the non-streaming endpoint would be the opposite of
               what Stop means. Everything else falls through. */
            if (_streamErr && _streamErr.name === 'AbortError') {
                /* Stop pressed before the first byte: onOpen never ran, so the
                   loading node it would have removed is still on screen and the
                   transcript reads "Thinking..." forever. That is the most
                   likely moment to press Stop, so it is the one that must be
                   cleaned up here. */
                const _l = document.getElementById(loadingId);
                if (_l) _l.remove();
                return;
            }
            /* fall through to non-streaming */
        }

        try {
            const response = await ArchieChat.transport.sendMessage(_payload);

            const data = await response.json();
            // Remember the conversation this turn was saved to, and refresh the
            // history rail so a brand-new chat appears immediately.
            if (data.thread_id) {
                const _wasNew = data.thread_id !== window.__threadId;
                window.__threadId = data.thread_id;
                if (_wasNew && window.loadSessionList) window.loadSessionList();
            }
            const endTime = performance.now();
            const processingTime = Math.round(endTime - startTime);

            // Remove loading (guard: may already be gone if streaming ran first)
            { const _l = document.getElementById(loadingId); if (_l) _l.remove(); }

            if (data.error) {
                /* A failure renders as a failure. It used to render as an AI
                   turn beginning "**⚠️ Error:**" — the assistant's avatar, the
                   assistant's bubble, and no way to try again. */
                let errorTitle = 'Error';
                if (data.error_type === 'auth') {
                    errorTitle = 'Authentication Error';
                } else if (data.error_type === 'connection') {
                    errorTitle = 'Connection Error';
                } else if (data.error_type === 'timeout') {
                    errorTitle = 'Timeout Error';
                } else if (data.error_type === 'rate_limit') {
                    errorTitle = 'Rate Limit';
                } else if (data.error_type === 'model_error') {
                    errorTitle = 'Model Error';
                }
                appendError(`${errorTitle}: ${data.error}`, () => _retryTurn(message, timestamp));
            } else {
                // Add AI response to history
                state.chatHistory.push({
                    role: 'ai',
                    content: data.response,
                    timestamp,
                    metadata: data.metadata
                });

                appendMessage('ai', data.response, {
                    domain: data.domain,
                    processing_time: data.metadata?.processing_time || processingTime,
                    sources: data.sources,
                    /* The fallback must show the same footer as the streamed
                       path. It carries no tool_start/tool_result events — there
                       is no stream to carry them — so the trail is empty and the
                       evidence strip reports "context only" rather than
                       inventing lookups it cannot see. actions_taken does come
                       back on this path, so receipts and next-artifact are the
                       same either way. */
                    trail: [],
                    contextUsed: true,
                    actions: data.actions_taken || [],
                    pendingApprovals: data.pending_approvals || []
                });

                // Genome extraction — fires after every AI response when ?mode=genome
                if (window._genomePanelInstance) {
                    await window._genomePanelInstance.extractAfterMessage(state.chatHistory);
                }
            }

        } catch (error) {
            { const _l = document.getElementById(loadingId); if (_l) _l.remove(); }
            appendError(`Network error: ${error.message}`, () => _retryTurn(message, timestamp));
        }
    }

    function _retryTurn(message, timestamp) {
        _setSendingUI(true);
        _deliverTurn(message, timestamp).finally(() => _setSendingUI(false));
    }

    // Stream an AI reply via SSE. Renders tokens live into a bubble; returns true
    // when it rendered a reply (caller then stops), throws/returns false to let
    // the caller fall back to the non-streaming endpoint.
    async function streamAiReply(payload, loadingId, startTime, timestamp) {
        let wrap = null;
        // One turn's tool calls, in execution order. Rebuilt per turn so an
        // answer can never inherit the previous answer's evidence.
        const _trail = [];
        // The bubble is only DROPPED when the answer never arrived. On success
        // it is finalised in place — removing and rebuilding it is what made
        // every answer flash and the transcript jump on completion.
        const dropBubble = () => { if (wrap) { wrap.remove(); wrap = null; } };

        try {
            return await ArchieChat.transport.streamMessage(payload, {
                onOpen: () => {
                    { const _l = document.getElementById(loadingId); if (_l) _l.remove(); }
                    wrap = beginStreamedMessage();
                },
                onThreadId: (id) => {
                    const wasNew = id !== window.__threadId;
                    window.__threadId = id;
                    if (wasNew && window.loadSessionList) window.loadSessionList();
                },
                /* The evidence trail. The server has always emitted these and
                   the client always discarded them; they are what lets the UI
                   state coverage structurally ("47 matched, showing 15") rather
                   than trusting the model to mention it. */
                onToolStart: (ev) => { _trail.push({ tool: ev.tool, args: ev.args, result: null }); },
                onToolResult: (ev) => {
                    for (let i = _trail.length - 1; i >= 0; i--) {
                        if (_trail[i].tool === ev.tool && _trail[i].result === null) {
                            _trail[i].result = ev.result;
                            return;
                        }
                    }
                    _trail.push({ tool: ev.tool, args: null, result: ev.result });
                },
                onToken: (_text, full) => {
                    updateStreamedMessage(wrap, full);
                },
                onDone: async (result) => {
                    const meta = {
                        domain: result.domain || state.currentDomain,
                        processing_time: Math.round(performance.now() - startTime),
                        sources: result.sources,
                        trail: _trail,
                        actions: result.actions || [],
                        pendingApprovals: result.pendingApprovals || [],
                        // No tool ran, but the domain snapshot was in the prompt:
                        // that is "context only", not "ungrounded".
                        contextUsed: _trail.length === 0
                    };
                    state.chatHistory.push({ role: 'ai', content: result.text, timestamp, metadata: meta });
                    finaliseStreamedMessage(wrap, result.text, meta);
                    wrap = null;   // finalised in place; nothing left to drop
                    // Genome panel extraction is an optional side-panel enrichment;
                    // the chat turn above already completed and must not be undone by this failing.
                    if (window._genomePanelInstance) { try { await window._genomePanelInstance.extractAfterMessage(state.chatHistory); } catch (_) { /* swallow-ok: optional side-panel enrichment run after the answer is already on screen; an error toast here would read as the answer having failed when it did not */ } }
                }
            });
        } finally {
            dropBubble();
        }
    }

    // ==========================================================================
    // Document Upload Panel Toggle
    // ==========================================================================

    // UIQA-004: /ai-chat/document-upload redirects here with ?panel=docs
    if (new URLSearchParams(window.location.search).get('panel') === 'docs') {
        document.addEventListener('DOMContentLoaded', function() {
            toggleDocumentUploadPanel();
        });
    }

    function toggleDocumentUploadPanel() {
        const panel = document.getElementById('document-upload-panel');
        if (panel) {
            panel.classList.toggle('hidden');
            // Reinitialize Lucide icons when panel opens
            if (!panel.classList.contains('hidden') && typeof lucide !== 'undefined') {
                setTimeout(() => lucide.createIcons(), 100);
            }
        }
    }

    // ==========================================================================
    // Mobile Sidebar Toggle
    // ==========================================================================

    function toggleSidebar() {
        const sidebar = document.getElementById('context-sidebar');
        const backdrop = document.getElementById('sidebar-backdrop');
        const isOpen = !sidebar.classList.contains('-translate-x-full');

        if (isOpen) {
            // Close sidebar
            sidebar.classList.add('-translate-x-full');
            backdrop.classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
        } else {
            // Open sidebar
            sidebar.classList.remove('-translate-x-full');
            backdrop.classList.remove('hidden');
            document.body.classList.add('overflow-hidden');
            // Ensure sidebar is visible on mobile
            sidebar.style.height = '100%';
        }
        setTimeout(() => lucide.createIcons(), 100);
    }

    // =========================================================================
    // CSP-safe event delegation — handles all dynamically-injected data-action buttons
    // =========================================================================
    document.addEventListener('click', (event) => {
        // --- quick-query (sidebar NL query suggestions) ---
        const quickQueryButton = event.target.closest('[data-quick-query]');
        if (quickQueryButton) {
            event.preventDefault();
            runQuickQuery(quickQueryButton.dataset.quickQuery);
            return;
        }

        const btn = event.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;

        // --- sample prompt ---
        if (action === 'use-prompt') {
            usePrompt(btn.dataset.prompt);
            return;
        }

        // --- select context item (architecture/technology panel) ---
        if (action === 'select-context') {
            selectContext(parseInt(btn.dataset.id), btn.dataset.type);
            return;
        }

        /* apply-ai-action and dismiss-action-card lived here. Their only
           producer was renderActionCard, on the dead handleCommand path, so
           neither branch could ever fire. Removed with it. */

        // --- apply APQC mappings ---
        if (action === 'apply-apqc') {
            applyApqcMappings(parseInt(btn.dataset.appId), btn.dataset.highConf === '1');
            return;
        }

        // --- gap analysis tab switch ---
        if (action === 'gap-analysis-tab') {
            handleGapAnalysis(btn.dataset.analysisType);
            return;
        }

        // --- rediscover vendors ---
        if (action === 'discover-vendors') {
            handleDiscoverVendors(btn.dataset.capability);
            return;
        }

        // --- generate architect viewpoints ---
        if (action === 'architect-viewpoints') {
            handleArchitectViewpoints(btn.dataset.solutionId);
            return;
        }

        // --- check ARB readiness ---
        if (action === 'arb-ready') {
            handleArbReady(btn.dataset.solutionId);
            return;
        }

        // --- show entity in chat (search sidebar results) ---
        if (action === 'show-entity') {
            showEntityInChat(btn.dataset.entityType, parseInt(btn.dataset.entityId), btn.dataset.entityName);
            return;
        }

        // --- entity action modal: close ---
        if (action === 'close-entity-modal') {
            const modal = document.getElementById('entity-action-modal');
            if (modal) modal.remove();
            return;
        }

        // --- entity action modal: navigate to entity page ---
        if (action === 'navigate-entity') {
            navigateToEntity(btn.dataset.entityType, parseInt(btn.dataset.entityId));
            const modal = document.getElementById('entity-action-modal');
            if (modal) modal.remove();
            return;
        }

        // --- entity action modal: ask AI about entity ---
        if (action === 'ask-ai-entity') {
            askAIAboutEntity(btn.dataset.entityType, parseInt(btn.dataset.entityId), btn.dataset.entityName);
            const modal = document.getElementById('entity-action-modal');
            if (modal) modal.remove();
            return;
        }

        // --- entity action modal: add entity to context ---
        if (action === 'add-context-entity') {
            addToContext(btn.dataset.entityType, parseInt(btn.dataset.entityId), btn.dataset.entityName);
            const modal = document.getElementById('entity-action-modal');
            if (modal) modal.remove();
            return;
        }
    });

    function showEntityInChat(entityType, entityId, entityName) {
        // Show options modal for what to do with this entity
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50';
        modal.id = 'entity-action-modal';
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

        modal.innerHTML = `
            <div class="bg-background rounded-lg border shadow-xl p-6 max-w-md w-full mx-4">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="font-semibold text-lg">${entityName}</h3>
                    <button aria-label="Close" type="button" data-action="close-entity-modal" class="text-muted-foreground hover:text-foreground">
                        <i data-lucide="x" class="h-5 w-5"></i>
                    </button>
                </div>
                <p class="text-sm text-muted-foreground mb-4">${entityType} • ID: ${entityId}</p>
                <div class="space-y-2">
                    <button type="button" data-action="navigate-entity" data-entity-type="${entityType}" data-entity-id="${entityId}"
                        class="w-full flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors text-left">
                        <div class="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center"><!-- token-migration-ok -->
                            <i data-lucide="external-link" class="h-5 w-5 text-primary"></i><!-- token-migration-ok -->
                        </div>
                        <div>
                            <div class="font-medium text-sm">View Details</div>
                            <div class="text-xs text-muted-foreground">Open the full ${entityType.toLowerCase()} page</div>
                        </div>
                    </button>
                    <button type="button" data-action="ask-ai-entity" data-entity-type="${entityType}" data-entity-id="${entityId}" data-entity-name="${entityName.replace(/"/g, '&quot;')}"
                        class="w-full flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors text-left">
                        <div class="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center"><!-- token-migration-ok -->
                            <i data-lucide="bot" class="h-5 w-5 text-primary"></i><!-- token-migration-ok -->
                        </div>
                        <div>
                            <div class="font-medium text-sm">Ask AI</div>
                            <div class="text-xs text-muted-foreground">Get AI analysis and insights</div>
                        </div>
                    </button>
                    <button type="button" data-action="add-context-entity" data-entity-type="${entityType}" data-entity-id="${entityId}" data-entity-name="${entityName.replace(/"/g, '&quot;')}"
                        class="w-full flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors text-left">
                        <div class="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center"><!-- token-migration-ok -->
                            <i data-lucide="plus-circle" class="h-5 w-5 text-emerald-600"></i><!-- token-migration-ok -->
                        </div>
                        <div>
                            <div class="font-medium text-sm">Add to Context</div>
                            <div class="text-xs text-muted-foreground">Use as context for AI queries</div>
                        </div>
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        lucide.createIcons();
    }

    function navigateToEntity(entityType, entityId) {
        // Map entity types to their detail URLs
        const urlMap = {
            'Application': `/applications/${entityId}`,
            'application': `/applications/${entityId}`,
            'Capability': `/capabilities/${entityId}`,
            'capability': `/capabilities/${entityId}`,
            'Vendor': `/vendors/${entityId}`,
            'vendor': `/vendors/${entityId}`,
            'Process': `/processes/${entityId}`,
            'process': `/processes/${entityId}`,
            'Technology': `/technologies/${entityId}`,
            'technology': `/technologies/${entityId}`
        };

        const url = urlMap[entityType] || `/applications/${entityId}`;
        window.open(url, '_blank');
    }

    function askAIAboutEntity(entityType, entityId, entityName) {
        const prompt = `Analyze "${entityName}" (${entityType}, ID: ${entityId}).\n\nPlease provide:\n1. Overview and current status\n2. Key relationships and dependencies\n3. Risk assessment\n4. Improvement recommendations`;

        userInput.value = prompt;
        chatForm.dispatchEvent(new Event('submit'));
    }

    function addToContext(entityType, entityId, entityName) {
        selectedElementIdInput.value = entityId;
        state.contextElement = { id: entityId, type: entityType, name: entityName };
        appendSystemMessage(`Context set: ${entityName} (${entityType})`, 'info');
    }

    function selectDomainAndPrompt(domain, samplePrompt) {
        // Switch the domain selector
        domainSelector.value = domain;
        state.currentDomain = domain;

        // Update UI
        updateDomainUI(domain);
        loadDomainContext(domain);
        // Set the sample prompt in the input field
        userInput.value = samplePrompt;
        userInput.focus();

        // Show a system message about the switch
        const domainName = domainConfig[domain]?.name || domain;
        appendSystemMessage(`Switched to ${domainName}. Press Enter or click Send to use the sample prompt, or type your own question.`, 'info');
    }

    // Wire domain cards via addEventListener (CSP blocks inline onclick)
    document.querySelectorAll('.domain-card[data-domain]').forEach(function(card) {
        card.addEventListener('click', function() {
            selectDomainAndPrompt(this.dataset.domain, this.dataset.prompt);
        });
    });

    // AI-1: wire the welcome-screen AI Architect persona cards. Setting the
    // (otherwise hidden) persona selector + dispatching 'change' runs the
    // existing handler, which sets state.currentPersona, the persona's default
    // domain, and the role's sample prompts.
    function selectArchitectPersona(persona, samplePrompt) {
        if (personaSelector) {
            personaSelector.value = persona;
            personaSelector.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            state.currentPersona = persona;
        }
        if (userInput && samplePrompt) {
            userInput.value = samplePrompt;
            userInput.focus();
        }
        const label = (personaConfig && personaConfig[persona] && personaConfig[persona].name) || persona;
        // Best-effort welcome banner; persona selection above already took effect either way.
        try { appendSystemMessage(`${label} engaged — grounded in live platform data. Press Enter to use the suggested prompt, or ask your own.`, 'info'); } catch (e) { /* swallow-ok: cosmetic welcome banner; the persona switch above already took effect, so failing to print the banner is not a failure the user needs to act on */ }
    }
    document.querySelectorAll('.architect-card[data-persona]').forEach(function(card) {
        card.addEventListener('click', function() {
            selectArchitectPersona(this.dataset.persona, this.dataset.prompt);
        });
    });

    // ==========================================================================
    // Create Solution from Brief — modal handler
    // ==========================================================================

    function openCreateSolutionModal() { openCreateSolutionModalWithMessage(''); }
    function openCreateSolutionModalWithMessage(message) {
        let modal = document.getElementById('ai-chat-create-solution-modal');
        if (modal) modal.classList.remove('hidden');
        const briefEl = document.getElementById('ai-chat-solution-brief');
        if (briefEl && typeof message === 'string' && message.trim()) briefEl.value = message.trim();
        const titleEl = document.getElementById('ai-chat-solution-title');
        if (titleEl) titleEl.focus();
    }
    function closeCreateSolutionModal() {
        let modal = document.getElementById('ai-chat-create-solution-modal');
        if (modal) modal.classList.add('hidden');
    }

    // Wire the button
    const createSolBtn = document.getElementById('ai-chat-create-solution-btn');
    if (createSolBtn) createSolBtn.addEventListener('click', openCreateSolutionModal);
    const createSolCancel = document.getElementById('ai-chat-create-solution-cancel');
    if (createSolCancel) createSolCancel.addEventListener('click', closeCreateSolutionModal);
    const createSolForm = document.getElementById('ai-chat-create-solution-form');
    if (createSolForm) {
        createSolForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const titleEl = document.getElementById('ai-chat-solution-title');
            const briefEl = document.getElementById('ai-chat-solution-brief');
            const statusEl = document.getElementById('ai-chat-create-solution-status');
            const submitBtn = createSolForm.querySelector('button[type="submit"]');
            let title = (titleEl && titleEl.value || '').trim();
            const brief = (briefEl && briefEl.value || '').trim();
            if (!title || !brief) return;
            if (submitBtn) submitBtn.disabled = true;
            if (statusEl) { statusEl.classList.remove('hidden'); statusEl.textContent = 'Creating solution and generating draft…'; }
            fetch('/solutions/create-with-draft', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : ''},
                body: JSON.stringify({ title: title, brief: brief })
            }).then(function(resp) { return resp.json().then(function(data) { return { ok: resp.ok, data: data }; }, function() { return { ok: false, data: {} }; }); })
              .then(function(r) {
                  if (submitBtn) submitBtn.disabled = false;
                  if (r.ok && r.data.redirect) {
                      closeCreateSolutionModal();
                      appendSystemMessage('Solution created — redirecting to detail page…', 'info');
                      setTimeout(function() { window.location.href = r.data.redirect; }, 800);
                  } else {
                      if (statusEl) statusEl.textContent = 'Error: ' + (r.data.error || 'Could not create solution');
                  }
              }).catch(function(err) {
                  if (submitBtn) submitBtn.disabled = false;
                  if (statusEl) statusEl.textContent = 'Network error: ' + err.message;
              });
        });
    }

    // ==========================================================================
    // Document Upload Event Listeners
    // ==========================================================================

    // Listen for document analysis results to add to chat
    window.addEventListener('add-document-analysis', (e) => {
        const { filename, summary, elementsFound, elementsCreated, confidence } = e.detail || {};
        const message = `**Document Analyzed: ${filename || 'Unknown'}**

${summary || 'Document has been analyzed.'}

**Results:**
- Elements Found: ${elementsFound || 0}
- Elements Created: ${elementsCreated || 0}
- Confidence: ${confidence || 'Medium'}

Would you like me to provide more details about the extracted elements or help you with follow-up questions?`;
        appendMessage('ai', message, { domain: state.currentDomain });
    });

    // Listen for notification events
    window.addEventListener('show-notification', (e) => {
        const { type, message } = e.detail || {};
        appendSystemMessage(message || 'Notification', type || 'info');
    });

    // Listen for questions from document panel
    window.addEventListener('ask-question', (e) => {
        const { question, context } = e.detail || {};
        if (question) {
            userInput.value = question;
            if (context) {
                userInput.value += `\n\n[Context: ${context}]`;
            }
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Listen for entity linking requests
    window.addEventListener('link-to-entity', (e) => {
        const { entityType, entityId, entityName, documentId } = e.detail || {};
        appendSystemMessage(`Linking document to ${entityType}: ${entityName} (ID: ${entityId})`, 'info');
    });

    // Listen for entity creation requests
    window.addEventListener('create-entity', (e) => {
        const { entityType, entityData } = e.detail || {};
        appendSystemMessage(`Creating new ${entityType}: ${entityData?.name || 'Unknown'}`, 'info');
    });

    // ==========================================================================
    // Initialize on Load
    // ==========================================================================

    // Initialize on load
    document.addEventListener('DOMContentLoaded', () => {
        updateDomainUI(state.currentDomain);
        loadDomainContext(state.currentDomain);
        loadAvailableModels(); // Load available models

        // Load initial alert count
        loadRecommendations();
        // The opening screen reads this tenant's portfolio rather than asking
        // the user to supply the agenda.
        ArchieChat.panels.loadPortfolioBriefing();

        /* The welcome grid used to be rebuilt here: messagesContainer.innerHTML
           overwrote the server-rendered grid with a second copy carrying
           different prompt strings, and both copies' cards were wired, so
           every card had two click handlers. The server-rendered one is the
           one that survives; the wiring above it runs once. */
        lucide.createIcons();

        // A95-005: Handle deep-link context params from entity detail pages.
        // Supports:
        //   ?context=application&id=<app_id>   (application detail page)
        //   ?element_id=<id>&context_type=vendor&domain=vendor_intelligence  (vendor detail "Ask AI")
        const urlParams = new URLSearchParams(window.location.search);
        const deepLinkContext = urlParams.get('context');
        const deepLinkId = urlParams.get('id');
        const elementId = urlParams.get('element_id');
        const contextType = urlParams.get('context_type');
        const deepLinkDomain = urlParams.get('domain');

        if (deepLinkContext === 'application' && deepLinkId && !isNaN(parseInt(deepLinkId))) {
            const appId = parseInt(deepLinkId);
            selectedElementIdInput.value = appId;
            state.contextElement = { id: appId, type: 'application' };
            if (domainSelector) {
                domainSelector.value = 'technology';
                state.currentDomain = 'technology';
                updateDomainUI('technology');
                loadDomainContext('technology');
            }
            if (userInput) {
                userInput.value = `/generate-archimate ${appId}`;
            }
            appendSystemMessage(`Application context loaded (ID: ${appId}). Ready to generate ArchiMate model.`, 'info');
        } else if (elementId && contextType && !isNaN(parseInt(elementId))) {
            // Generic entity deep-link: ?element_id=<id>&context_type=<type>&domain=<domain>
            const entityId = parseInt(elementId);
            selectedElementIdInput.value = entityId;
            state.contextElement = { id: entityId, type: contextType };
            const targetDomain = deepLinkDomain || 'general';
            if (domainSelector && domainConfig[targetDomain]) {
                domainSelector.value = targetDomain;
                state.currentDomain = targetDomain;
                updateDomainUI(targetDomain);
                loadDomainContext(targetDomain);
            }
            // Build a context-aware welcome message
            const entityLabel = contextType.charAt(0).toUpperCase() + contextType.slice(1).replace(/_/g, ' ');
            if (userInput && userInput.value === '') {
                if (contextType === 'vendor') {
                    userInput.value = `Analyze this vendor — what are the key risks, capability gaps, and strategic recommendations?`;
                }
            }
            appendSystemMessage(`${entityLabel} context loaded (ID: ${entityId}). Ask me anything about this ${contextType.replace(/_/g, ' ')}.`, 'info');
        }
    });

    // ==========================================================================
    // Export Conversation (AIC-EXPORT)
    // ==========================================================================

    /* The Export button in the header has been calling this since it was added.
       The implementation existed only in app/static/js/ai_chat.js, which no
       template ever loaded, so every click raised an Alpine expression error
       while the feature was listed as working. Ported from there unchanged. */
    function exportConversation() {
        if (state.chatHistory.length === 0) {
            appendSystemMessage('No conversation to export', 'info');
            return;
        }
        let lines = [
            '# A.R.C.H.I.E. Architecture Chat Export',
            '**Exported:** ' + new Date().toLocaleString(),
            '**Domain:** ' + (domainConfig[state.currentDomain] && domainConfig[state.currentDomain].name || state.currentDomain),
            '**Persona:** ' + (personaConfig[state.currentPersona] && personaConfig[state.currentPersona].name || state.currentPersona || 'Not set'),
            '',
            '---',
            ''
        ];
        state.chatHistory.forEach(function(msg) {
            if (msg.role === 'user') {
                lines.push('## 🧑 User');
                lines.push(msg.content);
                lines.push('');
            } else if (msg.role === 'ai' || msg.role === 'assistant') {
                lines.push('## 🤖 A.R.C.H.I.E.');
                lines.push(msg.content);
                lines.push('');
            }
        });
        lines.push('---');
        lines.push('*Generated by A.R.C.H.I.E. Enterprise Architecture AI Assistant*');

        let blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
        let url = URL.createObjectURL(blob);
        let a = document.createElement('a');
        a.href = url;
        a.download = 'archie-chat-' + new Date().toISOString().slice(0, 10) + '.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        appendSystemMessage('Conversation exported as Markdown', 'info');
    }

    /* Alpine expressions and the markup resolve these off window. */
    window.exportConversation = exportConversation;
    window.toggleSidebar = toggleSidebar;
    window.toggleDocumentUploadPanel = toggleDocumentUploadPanel;
    window.setSuggestion = setSuggestion;
    window.usePrompt = usePrompt;
})(window, document);

/* Conversation history rail — wired into the LIVE inline chat. Defines the
   functions the template buttons call (loadSessionList / startNewConversation),
   plus open/delete, and keeps window.__threadId in sync so multi-turn chats
   stay in one conversation. Backed by the /ai-chat/threads API. */
(function () {
  var transport = window.ArchieChat.transport;
  var render = window.ArchieChat.render;
  function esc(s) { var d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }

  window.loadSessionList = async function () {
    var c = document.getElementById('session-list');
    if (!c) return;
    c.innerHTML = '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i></div>';
    if (window.lucide) lucide.createIcons();
    try {
      var r = await transport.listThreads();
      var j = await r.json();
      var t = (j && j.threads) || [];
      if (!t.length) {
        c.innerHTML = '<p class="text-xs text-muted-foreground text-center py-8">No conversations yet. Ask anything below — your chats are saved here automatically.</p>';
        return;
      }
      c.innerHTML = t.map(function (x) {
        var active = (x.id === window.__threadId) ? ' bg-accent' : '';
        // An unparsable timestamp renders as an em dash, never as a blank that
        // would read as "this conversation has no date".
        var d = '—'; try { d = new Date(x.updated_at || x.created_at).toLocaleDateString(); } catch (e) { /* swallow-ok: date formatting of one row; the em dash above already tells the user the date is unknown */ }
        return '<div class="js-thr group relative flex items-center rounded-lg border border-border hover:bg-accent/50 transition-colors' + active + '" data-id="' + esc(x.id) + '">' +
          '<button type="button" class="js-thr-open flex-1 text-left p-3 min-w-0">' +
          '<div class="font-medium text-xs truncate">' + esc(x.title || 'New chat') + '</div>' +
          '<div class="text-[10px] text-muted-foreground mt-1">' + esc(d) + (x.message_count ? ' · ' + x.message_count + ' messages' : '') + '</div></button>' +
          '<button type="button" class="js-thr-del opacity-0 group-hover:opacity-100 shrink-0 p-2 text-muted-foreground hover:text-destructive" title="Delete conversation" aria-label="Delete conversation"><i data-lucide="trash-2" class="h-3.5 w-3.5"></i></button></div>';
      }).join('');
      c.querySelectorAll('.js-thr').forEach(function (row) {
        var id = row.getAttribute('data-id');
        var o = row.querySelector('.js-thr-open'); if (o) o.addEventListener('click', function () { window.loadSession(id); });
        var del = row.querySelector('.js-thr-del'); if (del) del.addEventListener('click', function (e) { e.stopPropagation(); window.deleteConversation(id); });
      });
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      c.innerHTML = '<p class="text-xs text-destructive text-center py-4">Couldn\'t load conversations.</p>';
    }
  };

  window.loadSession = async function (id) {
    if (!id) return;
    try {
      var r = await transport.loadThread(id);
      if (!r.ok) {
        if (window.Platform && window.Platform.toast) window.Platform.toast.error('Could not load that conversation.');
        return;
      }
      var j = await r.json();
      var msgs = (j && j.messages) || [];
      window.__threadId = id;
      var wg = document.getElementById('domain-welcome-grid'); if (wg) wg.classList.add('hidden');
      var mc = document.getElementById('messages-container'); if (mc) mc.innerHTML = '';
      /* Resolved through the module, and deliberately unguarded.
         appendMessage used to be a window global — the old template's classic
         <script> hoisted every top-level function onto window — so
         `typeof appendMessage === 'function'` was true. Inside an IIFE it is
         always false, so this loop silently rendered nothing: opening a past
         conversation cleared the pane and left it empty, while __threadId above
         had already switched, so the next message continued a thread the user
         could not see. A guard that can be false for a module this file depends
         on is not a safety net, it is the bug. */
      msgs.forEach(function (m) {
        render.appendMessage(
          m.role === 'assistant' ? 'ai' : m.role,
          m.content,
          { domain: window.ArchieChat.state.currentDomain || 'general' }
        );
      });
      window.loadSessionList();
      if (mc) mc.scrollTop = mc.scrollHeight;
    } catch (e) {
      if (window.Platform && window.Platform.toast) window.Platform.toast.error('Could not load that conversation.');
    }
  };

  window.deleteConversation = async function (id) {
    if (!id) return;
    try {
      await transport.deleteThread(id);
    } catch (e) {
      // The thread was NOT deleted server-side — do not proceed to
      // startNewConversation()/refresh below, or the user is left believing
      // the delete worked while the conversation is still there.
      if (window.Platform && window.Platform.toast) window.Platform.toast.error('Could not delete that conversation.');
      return;
    }
    if (id === window.__threadId) { window.startNewConversation(); return; }
    window.loadSessionList();
  };

  // "New chat" — a fresh page load is the most reliable reset for the inline
  // chat (welcome grid, in-page state, and __threadId all reset cleanly).
  window.startNewConversation = function () { window.__threadId = null; window.location.href = window.location.pathname; };

  // Auto-load the rail so past chats are visible without clicking Refresh; failure here
  // just means the sidebar list stays empty until the next successful call, non-fatal to boot.
  function boot() { try { window.loadSessionList(); } catch (e) { /* swallow-ok: loadSessionList renders its own "Couldn't load conversations" state; this guard only stops a throw at page load from aborting the rest of the script */ } }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
