/* /ai-chat transcript rendering.
 *
 * Everything that puts something in #messages-container: markdown +
 * sanitisation, message bubbles, system notices, sources, and the streaming
 * bubble. Extracted from the inline script in
 * app/templates/ai_chat/index.html.
 *
 * Two deliberate changes, both recorded in the commit that landed this file:
 *   - the streamed bubble is finalised IN PLACE instead of being removed and
 *     rebuilt, which used to flash and jump the transcript at the end of
 *     every answer;
 *   - failures render as an error card with Retry instead of an AI turn
 *     beginning "**⚠️ Error:**", which dressed a failure as an answer.
 */
(function (window, document) {
    'use strict';

    var ArchieChat = (window.ArchieChat = window.ArchieChat || {});

    /* Conversation state, shared by every chat module. It lives here rather
       than in the template because render, commands and panels all read it,
       and a per-block `let` is what made replayed history always render as
       domain "general" (it read window.currentDomain, which nothing set). */
    var state = (ArchieChat.state = ArchieChat.state || {
        currentDomain: 'general',
        currentPersona: '',
        chatHistory: [],
        contextElement: null
    });

    function messages() { return document.getElementById('messages-container'); }
    function domains() { return window.domainConfig || {}; }

    function scrollToBottom() {
        var c = messages();
        if (c) c.scrollTop = c.scrollHeight;
    }

    // Tailwind-safe color class mappings (explicit classes for build-time purging)
    // token-migration-ok — domain-specific color palette for visual differentiation
    var colorClasses = {
        'blue': { bg: 'bg-primary', gradient: 'from-info to-primary', text: 'text-primary', badge: 'bg-primary/10 text-primary' },
        'green': { bg: 'bg-emerald-500', gradient: 'from-green-500 to-green-600', text: 'text-emerald-700', badge: 'bg-emerald-500/10 text-emerald-700' }, // token-migration-ok
        'purple': { bg: 'bg-primary', gradient: 'from-purple-500 to-purple-600', text: 'text-purple-700', badge: 'bg-purple-100 text-purple-700' }, // token-migration-ok
        'orange': { bg: 'bg-orange-500', gradient: 'from-orange-500 to-orange-600', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-700' },
        'indigo': { bg: 'bg-primary', gradient: 'from-indigo-500 to-indigo-600', text: 'text-indigo-700', badge: 'bg-indigo-100 text-indigo-700' }, // token-migration-ok
        'teal': { bg: 'bg-teal-500', gradient: 'from-teal-500 to-teal-600', text: 'text-teal-700', badge: 'bg-teal-100 text-teal-700' },
        'slate': { bg: 'bg-muted-foreground', gradient: 'from-muted-foreground to-foreground', text: 'text-foreground', badge: 'bg-muted text-foreground' },
        'primary': { bg: 'bg-primary', gradient: 'from-primary to-primary/80', text: 'text-primary', badge: 'bg-primary/10 text-primary' },
        'amber': { bg: 'bg-amber-500', gradient: 'from-amber-500 to-amber-600', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700' },
        'cyan': { bg: 'bg-cyan-500', gradient: 'from-cyan-500 to-cyan-600', text: 'text-cyan-700', badge: 'bg-cyan-100 text-cyan-700' },
        'pink': { bg: 'bg-pink-500', gradient: 'from-pink-500 to-pink-600', text: 'text-pink-700', badge: 'bg-pink-100 text-pink-700' },
        'violet': { bg: 'bg-violet-500', gradient: 'from-violet-500 to-violet-600', text: 'text-violet-700', badge: 'bg-violet-100 text-violet-700' },
        'red': { bg: 'bg-destructive', gradient: 'from-destructive to-destructive-emphasis', text: 'text-destructive-emphasis', badge: 'bg-destructive/10 text-destructive-emphasis' }
    };

    function getColorClass(colorName, type) {
        var colors = colorClasses[colorName] || colorClasses['primary'];
        return colors[type || 'bg'] || colors.bg;
    }

    /* Escape a value that is interpolated into an innerHTML template as text.
       The user's own message was echoed raw, so any markup a user typed became
       live DOM in their transcript. */
    function escapeForHtml(value) {
        var div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }

    /* Render markdown, then sanitise, before it reaches innerHTML.
       The streaming path already did this (see the DOMPurify call further down),
       but this function is what renders every COMPLETED message and every message
       replayed from thread history - and it called marked.parse() straight into
       innerHTML. Because the stream re-renders through appendMessage when it
       finishes, the sanitised streaming output was immediately replaced by an
       unsanitised copy of the same text: a stored-XSS path through chat history,
       where the payload is model output or extracted document content.
       Falls back to escaped plain text if DOMPurify is unavailable - degraded
       formatting is an acceptable outcome; unsanitised HTML is not. */
    function renderMarkdown(text) {
        if (window.DOMPurify && window.marked) {
            return DOMPurify.sanitize(marked.parse(text == null ? '' : String(text)));
        }
        return escapeForHtml(text);
    }

    /* Records the answer was actually built from.
       These come from the tool results server-side, not from the model - a
       citation the model writes is another claim, and the claim is the thing
       being checked. `url` may be null when the owning blueprint is not
       registered; the name and id still make the record findable. */
    function renderSources(sources) {
        if (!Array.isArray(sources) || sources.length === 0) return '';
        var items = sources.map(function (s) {
            var label = escapeForHtml(s.name);
            var kind = escapeForHtml(String(s.type || '').replace(/_/g, ' '));
            var body = s.url
                ? '<a href="' + escapeForHtml(s.url) + '" class="underline hover:no-underline">' + label + '</a>'
                : label;
            return '<li class="inline-flex items-center gap-1.5 mr-3">' +
                     '<i data-lucide="link" class="h-3 w-3 text-muted-foreground" aria-hidden="true"></i>' +
                     '<span>' + body + '</span>' +
                     '<span class="text-muted-foreground">(' + kind + ' #' + escapeForHtml(s.id) + ')</span>' +
                   '</li>';
        }).join('');
        return '<div class="mt-3 pt-2 border-t border-border text-xs text-muted-foreground">' +
                 '<div class="mb-1 font-medium">Based on ' + sources.length + ' record' + (sources.length === 1 ? '' : 's') + ':</div>' +
                 '<ul class="list-none p-0 m-0">' + items + '</ul>' +
               '</div>';
    }


    /* ── Evidence trail ──────────────────────────────────────────────────────
       What the answer was actually built from, in execution order.

       This replaces a proposed "grounded / not grounded" binary keyed on
       sources.length. That binary was unshippable: citations cover 7 of the 37
       tools, so an answer built by propose_rationalization or simulate_impact
       against real tenant rows produced no sources and would have rendered
       "not checked against your portfolio" — a false provenance claim on
       exactly the highest-stakes answers, pointing in the direction the
       fabricated-data gate cannot see.

       Three states, each true by construction:

         Retrieved     tools ran; here is each call and what came back
         Context only  no tool ran, but the domain snapshot was in the prompt
         Unretrieved   neither

       Coverage is structural, not prose. When a tool returned 15 of 47 the row
       says so, from the result payload — the model is asked to report N of M
       (_AGENT_PREFIX rule 9) but may not, and an architect's real question is
       never "is this grounded" but "did it look at everything, or the first
       page?"                                                                */

    var TOOL_LABELS = {
        find_applications: 'Searched applications',
        find_applications_by_capability: 'Searched applications by capability',
        find_technical_capabilities: 'Searched technical capabilities',
        query_capability_gaps: 'Queried capability gaps',
        search_capabilities_by_problem: 'Searched capabilities',
        search_archimate_elements: 'Searched ArchiMate elements',
        get_solution_summary: 'Read solution summary',
        get_completeness_score: 'Scored solution completeness',
        propose_rationalization: 'Proposed rationalization',
        simulate_impact: 'Simulated impact',
        explain_element: 'Explained element',
        diagnose_chain: 'Diagnosed chain',
        validate_sap_clean_core: 'Validated SAP clean core',
        verify_codegen: 'Verified generated code'
    };

    function _toolLabel(name) {
        if (TOOL_LABELS[name]) return TOOL_LABELS[name];
        return String(name || 'tool').replace(/_/g, ' ').replace(/^./, function (c) {
            return c.toUpperCase();
        });
    }

    /* "47 matched, showing 15" — only when the tool actually reported both.
       Never inferred from the row count, because the number of rows shown is
       precisely what must not be presented as the number that exists. */
    function _coverage(result) {
        if (!result || typeof result !== 'object') return '';
        var shown = Array.isArray(result.result) ? result.result.length
                  : (result.result && typeof result.result === 'object' ? 1 : null);
        var total = result.total_matched != null ? result.total_matched
                  : (result.total != null ? result.total : null);
        if (total != null && shown != null && total > shown) {
            return escapeForHtml(String(total)) + ' matched, showing ' + escapeForHtml(String(shown));
        }
        if (shown != null) {
            return escapeForHtml(String(shown)) + (shown === 1 ? ' record' : ' records');
        }
        return '';
    }

    function _argSummary(args) {
        if (!args || typeof args !== 'object') return '';
        var parts = [];
        Object.keys(args).slice(0, 3).forEach(function (k) {
            var v = args[k];
            if (v === null || v === undefined || v === '') return;
            if (typeof v === 'object') return;
            parts.push(escapeForHtml(k) + ' = ' + escapeForHtml(String(v).slice(0, 40)));
        });
        return parts.join(' · ');
    }

    /* trail: [{tool, args, result}] in execution order, collected from the
       tool_start / tool_result stream events the server has always emitted. */
    function renderEvidence(trail, sources, opts) {
        var o = opts || {};
        var ran = Array.isArray(trail) && trail.length > 0;
        var cited = Array.isArray(sources) && sources.length > 0;

        var state, summary;
        if (ran) {
            state = 'retrieved';
            summary = trail.length + (trail.length === 1 ? ' lookup' : ' lookups')
                    + (cited ? ', ' + sources.length + ' record' + (sources.length === 1 ? '' : 's') + ' cited' : '');
        } else if (o.contextUsed) {
            state = 'context';
            summary = 'No lookup ran. Answered from the ' +
                      escapeForHtml(o.domainLabel || 'portfolio') + ' snapshot in context.';
        } else {
            state = 'unretrieved';
            summary = 'No portfolio data was read for this answer.';
        }

        var id = 'evidence-' + (_evidenceSeq += 1);
        var rows = ran ? trail.map(function (step) {
            var cov = _coverage(step.result);
            var args = _argSummary(step.args);
            var failed = step.result && step.result.success === false;
            return '<li class="flex items-start gap-2 py-1">' +
                     '<i data-lucide="' + (failed ? 'x-circle' : 'search') + '" class="h-3 w-3 mt-0.5 shrink-0 ' +
                        (failed ? 'text-destructive-emphasis' : 'text-muted-foreground') + '" aria-hidden="true"></i>' +
                     '<span>' +
                       '<span class="text-foreground">' + escapeForHtml(_toolLabel(step.tool)) + '</span>' +
                       (args ? '<span class="text-muted-foreground"> · ' + args + '</span>' : '') +
                       (cov ? '<span class="font-medium text-foreground"> · ' + cov + '</span>' : '') +
                       (failed ? '<span class="text-destructive-emphasis"> · failed</span>' : '') +
                     '</span>' +
                   '</li>';
        }).join('') : '';

        /* The accessible name is the whole sentence: the Context-only and
           Unretrieved states have to reach a screen-reader user with the same
           prominence as Retrieved, because those are the ones that change
           whether an answer can be taken to an ARB. */
        var icon = state === 'retrieved' ? 'database' : (state === 'context' ? 'layers' : 'help-circle');
        return '<div class="mt-3 pt-2 border-t border-border text-xs">' +
                 '<button type="button" class="js-evidence-toggle inline-flex items-center gap-1.5 ' +
                    'text-muted-foreground hover:text-foreground transition-colors" ' +
                    'aria-expanded="false" aria-controls="' + id + '" ' +
                    'aria-label="' + escapeForHtml(summary) + '. Show what this answer was built from">' +
                   '<i data-lucide="' + icon + '" class="h-3 w-3" aria-hidden="true"></i>' +
                   '<span>' + escapeForHtml(summary) + '</span>' +
                   '<i data-lucide="chevron-down" class="h-3 w-3 transition-transform" aria-hidden="true"></i>' +
                 '</button>' +
                 '<div id="' + id + '" hidden class="mt-2 space-y-2">' +
                   (rows ? '<ul class="list-none p-0 m-0 text-muted-foreground">' + rows + '</ul>' : '') +
                   renderSources(sources) +
                 '</div>' +
               '</div>';
    }

    var _evidenceSeq = 0;

    /* The domain pill above an answer. Shared by the completed-message path
       and the streamed-message path so the two cannot drift apart. */
    function renderMetaBadge(metadata) {
        var meta = metadata || {};
        if (!meta.domain) return '';
        var cfg = domains();
        var badgeClass = getColorClass((cfg[meta.domain] || {}).color || 'blue', 'badge');
        return '<div class="mb-2">' +
                 '<span class="px-2 py-1 ' + badgeClass + ' text-xs rounded-full font-medium">' +
                   escapeForHtml((cfg[meta.domain] || {}).name || 'AI') +
                 '</span>' +
                 (meta.processing_time ? '<span class="ml-2 text-xs text-muted-foreground">' + escapeForHtml(meta.processing_time) + 'ms</span>' : '') +
               '</div>';
    }

    function avatarHtml() {
        var cfg = domains();
        var domainColor = (cfg[state.currentDomain] || {}).color || 'primary';
        var avatarGradient = getColorClass(domainColor, 'gradient');
        return '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ' + avatarGradient + ' text-primary-foreground shadow-lg">' + // token-migration-ok
                 '<i data-lucide="' + ((cfg[state.currentDomain] || {}).icon || 'bot') + '" class="h-5 w-5"></i>' +
               '</div>';
    }

    function appendMessage(role, text, metadata) {
        metadata = metadata || {};
        var isAi = role === 'ai';
        var container = messages();
        var div = document.createElement('div');
        div.className = 'flex gap-4 ' + (isAi ? '' : 'flex-row-reverse');

        // Enhanced avatar with domain styling using safe color classes
        var avatar = isAi
            ? avatarHtml()
            : '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">' +
                '<i data-lucide="user" class="h-5 w-5"></i>' +
              '</div>';

        // Enhanced message bubble with metadata using safe color classes
        var bubble = isAi
            ? '<div class="rounded-xl bg-muted/50 p-4 text-sm prose max-w-3xl">' +
                renderMetaBadge(metadata) +
                '<div class="message-content">' + renderMarkdown(text) + '</div>' +
                renderEvidence(metadata.trail, metadata.sources, {
                    contextUsed: metadata.contextUsed,
                    domainLabel: metadata.domain
                }) +
              '</div>'
            : '<div class="rounded-xl bg-primary text-primary-foreground p-4 text-sm max-w-3xl">' +
                '<div class="message-content">' + escapeForHtml(text) + '</div>' +
              '</div>';

        div.innerHTML = avatar + bubble;
        if (container) container.appendChild(div);

        // ENT-122: inject "Open in Composer" button for ArchiMate responses
        if (isAi && metadata.archimate_elements && metadata.archimate_elements.length > 0) {
            /* Key, param and timestamp all have to match what the composer
               reads (archimate/composer.js:2407 and :2495), or the handoff
               silently drops the payload and opens an empty canvas:
                 - the key is 'composer_prefill', not 'archimate_prefill'
                 - the link must carry ?prefill=1, or the reader returns early
                 - a payload older than 5 minutes is discarded, so send a
                   timestamp rather than relying on the absent-field branch */
            var prefillData = {
                elements: metadata.archimate_elements,
                relationships: metadata.archimate_relationships || [],
                model_name: metadata.archimate_model_name || 'AI Generated Architecture',
                source: 'ai_chat',
                timestamp: Date.now()
            };
            sessionStorage.setItem('composer_prefill', JSON.stringify(prefillData));
            var composerBtn = document.createElement('div');
            composerBtn.className = 'mt-3 ml-12';
            var elemCount = metadata.archimate_elements.length;
            var relCount = (metadata.archimate_relationships || []).length;
            composerBtn.innerHTML =
                '<a href="/archimate/composer?prefill=1" data-ent121-composer-link' +
                '   class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm">' +
                  '<i data-lucide="layout-dashboard" class="h-4 w-4"></i>' +
                  ' Open in Composer — ' + elemCount + ' elements, ' + relCount + ' relationships' +
                '</a>';
            if (container) container.appendChild(composerBtn);
        }

        scrollToBottom();

        // Re-initialize lucide icons for new elements
        if (window.lucide) lucide.createIcons();
        return div;
    }

    function appendSystemMessage(text, type) {
        type = type || 'info';
        var div = document.createElement('div');
        div.className = 'flex justify-center my-4';

        var bgColor = type === 'info' ? 'bg-primary/5 text-primary border-primary/20' : // token-migration-ok
                      type === 'error' ? 'bg-destructive/5 text-destructive border-destructive/20' : // token-migration-ok
                      'bg-muted/50 text-muted-foreground border-border';

        div.innerHTML =
            '<div class="px-3 py-2 rounded-lg text-xs ' + bgColor + ' border flex items-center gap-2">' +
              '<i data-lucide="' + (type === 'info' ? 'info' : type === 'error' ? 'alert-circle' : 'check') + '" class="h-3 w-3"></i>' +
              text +
            '</div>';

        var container = messages();
        if (container) container.appendChild(div);
        scrollToBottom();
        if (window.lucide) lucide.createIcons();
        return div;
    }

    /* A failure is not an answer. This used to render as appendMessage('ai',
       '**⚠️ Error:** …'), which put the failure in the transcript wearing the
       assistant's avatar and offered no way to try again.
       text-destructive-emphasis, not text-destructive: the base token scores
       3.30 on its own tint (DESIGN.md). */
    function appendError(message, onRetry) {
        var div = document.createElement('div');
        div.className = 'mx-auto max-w-3xl rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-emphasis';
        div.setAttribute('role', 'alert');
        div.innerHTML =
            '<div class="flex items-start gap-2">' +
              '<i data-lucide="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true"></i>' +
              '<div class="flex-1"><p>' + escapeForHtml(message) + '</p></div>' +
              (onRetry ? '<button type="button" class="js-retry inline-flex items-center rounded-md border border-input bg-background px-3 py-1 text-xs font-medium hover:bg-accent">Retry</button>' : '') +
            '</div>';
        if (onRetry) {
            div.querySelector('.js-retry').addEventListener('click', function () {
                div.remove();
                onRetry();
            });
        }
        var container = messages();
        if (container) container.appendChild(div);
        scrollToBottom();
        if (window.lucide) lucide.createIcons();
        return div;
    }

    // ------------------------------------------------------- streamed answer

    /* The bubble tokens stream into. The caret is a SIBLING of the prose
       container, not a child: inside it, it inherits paragraph spacing. */
    function beginStreamedMessage() {
        var wrap = document.createElement('div');
        wrap.className = 'flex gap-4';
        wrap.setAttribute('aria-busy', 'true');
        wrap.innerHTML = avatarHtml() +
            '<div class="rounded-xl bg-muted/50 p-4 text-sm max-w-3xl">' +
              '<div class="message-content prose max-w-none"></div>' +
              '<span class="stream-caret animate-pulse" aria-hidden="true">▍</span>' +
            '</div>';
        var container = messages();
        if (container) container.appendChild(wrap);
        if (window.lucide) lucide.createIcons();
        return wrap;
    }

    function updateStreamedMessage(el, text) {
        if (!el) return;
        var body = el.querySelector('.message-content');
        if (body) body.innerHTML = renderMarkdown(text);
        scrollToBottom();
    }

    /* Finish the answer where it already is. The previous version removed the
       whole element and re-appended a fresh one through appendMessage, so the
       transcript flashed and jumped on every completion — at the exact moment
       the reader had started reading. */
    function finaliseStreamedMessage(el, text, meta) {
        if (!el) return null;
        meta = meta || {};
        var body = el.querySelector('.message-content');
        if (body) body.innerHTML = renderMarkdown(text);
        var caret = el.querySelector('.stream-caret');
        if (caret) caret.remove();
        el.removeAttribute('aria-busy');
        var bubble = body ? body.parentElement : el;
        var badge = renderMetaBadge(meta);
        if (badge) bubble.insertAdjacentHTML('afterbegin', badge);
        var sources = renderEvidence(meta.trail, meta.sources, {
            contextUsed: meta.contextUsed,
            domainLabel: meta.domain
        });
        if (sources) bubble.insertAdjacentHTML('beforeend', sources);
        if (window.lucide) lucide.createIcons();
        return el;
    }


    /* One delegated listener rather than a handler per message: evidence
       strips are injected into the transcript continuously, and re-binding on
       each would leak listeners for the life of the conversation. */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest && e.target.closest('.js-evidence-toggle');
        if (!btn) return;
        var panel = document.getElementById(btn.getAttribute('aria-controls'));
        if (!panel) return;
        var open = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', open ? 'false' : 'true');
        panel.hidden = open;
        var chev = btn.querySelector('[data-lucide="chevron-down"]');
        if (chev) chev.classList.toggle('rotate-180', !open);
        if (!open && window.lucide) lucide.createIcons();
    });

    ArchieChat.render = {
        colorClasses: colorClasses,
        getColorClass: getColorClass,
        escapeForHtml: escapeForHtml,
        renderMarkdown: renderMarkdown,
        renderSources: renderSources,
        appendMessage: appendMessage,
        renderEvidence: renderEvidence,
        appendSystemMessage: appendSystemMessage,
        appendError: appendError,
        beginStreamedMessage: beginStreamedMessage,
        updateStreamedMessage: updateStreamedMessage,
        finaliseStreamedMessage: finaliseStreamedMessage,
        scrollToBottom: scrollToBottom,
        messagesContainer: messages
    };
})(window, document);
