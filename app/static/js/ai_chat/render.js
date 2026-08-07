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
                renderSources(metadata.sources) +
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
        var sources = renderSources(meta.sources);
        if (sources) bubble.insertAdjacentHTML('beforeend', sources);
        if (window.lucide) lucide.createIcons();
        return el;
    }

    ArchieChat.render = {
        colorClasses: colorClasses,
        getColorClass: getColorClass,
        escapeForHtml: escapeForHtml,
        renderMarkdown: renderMarkdown,
        renderSources: renderSources,
        appendMessage: appendMessage,
        appendSystemMessage: appendSystemMessage,
        appendError: appendError,
        beginStreamedMessage: beginStreamedMessage,
        updateStreamedMessage: updateStreamedMessage,
        finaliseStreamedMessage: finaliseStreamedMessage,
        scrollToBottom: scrollToBottom,
        messagesContainer: messages
    };
})(window, document);
