/**
 * AI Chat Module — A.R.C.H.I.E. Enterprise Architecture AI Assistant
 *
 * Requires window.domainConfig, window.promptTemplates,
 * window.personaConfig, window.csrfToken, and window.userDisplayName
 * to be set by the template before this script loads.
 */

// ==========================================================================
// Quick-query catalog (A95-001)
// ==========================================================================

const QUICK_QUERIES = [
  { label: 'Apps without owner',        query: 'Show all applications without an assigned owner',                           domain: 'applications' },
  { label: 'Low maturity caps',         query: 'List capabilities with maturity below 3',                                   domain: 'capabilities' },
  { label: 'Expiring vendors',          query: 'Show vendors with contracts expiring in the next 90 days',                  domain: 'vendors' },
  { label: 'High-risk apps',            query: 'List applications with risk score above 70',                                 domain: 'applications' },
  { label: 'Unmapped APQC caps',        query: 'Show capabilities not mapped to any APQC process framework entry',          domain: 'capabilities' },
  { label: 'Duplicate applications',    query: 'Identify applications that appear to be duplicates of each other',          domain: 'applications' },
  { label: 'Rationalization candidates',query: 'List applications that are candidates for rationalization or decommission',  domain: 'applications' },
  { label: 'Vendor risk overview',      query: 'Show vendors with high risk scores or critical compliance gaps',             domain: 'vendors' },
  { label: 'ArchiMate health',          query: 'List ArchiMate elements that have no relationships defined',                 domain: 'architecture' },
  { label: 'Stale solutions',           query: 'List solutions with no activity in the last 180 days',                      domain: 'solutions' },
  { label: 'Apps by status',            query: 'Count applications grouped by lifecycle status',                             domain: 'applications' },
  { label: 'Orphaned vendors',          query: 'Show vendors not associated with any solution or application',               domain: 'vendors' },
];
window.QUICK_QUERIES = QUICK_QUERIES;

// A95-006: Capability mapping entries
QUICK_QUERIES.push(
  { label: 'Create capability',  query: '/create-capability', isSlash: true },
  { label: 'Map APQC framework', query: '/map-apqc',          isSlash: true }
);

// A95-002: Structured API routes for known quick queries
const QUICK_QUERY_ROUTES = {
  'Show all applications without an assigned owner': '/api/v1/applications?filter=no_owner&format=table',
  'List capabilities with maturity below 3':         '/api/v1/capabilities?filter=low_maturity&format=table',
  'Show vendors with contracts expiring in the next 90 days': '/api/v1/vendors?filter=expiring_soon&format=table',
  'List applications with risk score above 70':       '/api/v1/applications?filter=high_risk&format=table',
  'Show capabilities not mapped to any APQC process framework entry':  '/api/v1/capabilities?filter=unmapped&format=table',
  'List solutions with no activity in the last 180 days': '/api/v1/solutions?filter=stale&format=table',
  'Count applications grouped by lifecycle status':   '/api/v1/applications/stats?group_by=status&format=table',
  'Show vendors not associated with any solution or application': '/api/v1/vendors?filter=orphaned&format=table',
};
window.QUICK_QUERY_ROUTES = QUICK_QUERY_ROUTES;

// A95-003: Dashboard navigation routes for known quick queries
const DASHBOARD_ROUTES = {
  'Show all applications without an assigned owner': '/applications?filter=no_owner',
  'List capabilities with maturity below 3':         '/capabilities?filter=low_maturity',
  'Show vendors with contracts expiring in the next 90 days': '/vendors?filter=expiring_soon',
  'List applications with risk score above 70':       '/applications?filter=high_risk',
  'Show capabilities not mapped to any APQC process framework entry':  '/capabilities?filter=unmapped',
  'List solutions with no activity in the last 180 days': '/solutions?filter=stale',
  'Count applications grouped by lifecycle status':   '/applications',
  'Show vendors not associated with any solution or application': '/vendors?filter=orphaned',
};
window.DASHBOARD_ROUTES = DASHBOARD_ROUTES;

// A95-003: Append a contextual "View in dashboard" link for NL responses
function appendDashboardCTA(responseText) {
  if (!responseText) return '';
  if (/application/i.test(responseText)) return '<div class="mt-1"><a href="/applications" class="text-xs text-primary underline" aria-label="View applications dashboard">View applications →</a></div>';
  if (/vendor/i.test(responseText)) return '<div class="mt-1"><a href="/vendors" class="text-xs text-primary underline" aria-label="View vendors dashboard">View vendors →</a></div>';
  if (/capabilit/i.test(responseText)) return '<div class="mt-1"><a href="/capabilities" class="text-xs text-primary underline" aria-label="View capabilities dashboard">View capabilities →</a></div>';
  if (/solution/i.test(responseText)) return '<div class="mt-1"><a href="/solutions" class="text-xs text-primary underline" aria-label="View solutions dashboard">View solutions →</a></div>';
  return '';
}
window.appendDashboardCTA = appendDashboardCTA;

// A95-001: Render quick-query chips from QUICK_QUERIES config into #quick-query-chips
function renderQuickQueryChips() {
    const container = document.getElementById('quick-query-chips');
    if (!container) return;
    container.innerHTML = '';
    const queries = window.QUICK_QUERIES || [];
    queries.forEach(function(q) {
        if (q.isSlash) return; // slash commands rendered separately
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'quick-query-btn inline-flex items-center gap-1 rounded-md border border-input bg-background px-3 py-1 text-xs hover:bg-accent';
        btn.setAttribute('aria-label', 'Quick query: ' + q.label);
        btn.setAttribute('data-query', q.query);
        btn.textContent = q.label;
        btn.addEventListener('click', function() {
            if (typeof runQuickQuery === 'function') {
                runQuickQuery(q.query);
            }
        });
        container.appendChild(btn);
    });
}
window.renderQuickQueryChips = renderQuickQueryChips;

// ==========================================================================
// DOM References
// ==========================================================================

const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const domainSelector = document.getElementById('domain-selector');
const templateSelector = document.getElementById('template-selector');
const personaSelector = document.getElementById('persona-selector');
const modelSelector = document.getElementById('model-selector');
const selectedElementIdInput = document.getElementById('selected-element-id');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const commandHints = document.getElementById('command-hints');

// ==========================================================================
// State
// ==========================================================================

let domainConfig = window.domainConfig || {};
let promptTemplates = window.promptTemplates || [];
let personaConfig = window.personaConfig || {};
let currentDomain = sessionStorage.getItem('ai_chat_domain') || 'general';
let currentPersona = sessionStorage.getItem('ai_chat_persona') || 'enterprise_architect';
let chatHistory = [];
let contextElement = null;
let isSending = false;
let hasConversationStarted = false;
let _activeAbortController = null;
let _activeAbortTimer = null; // auto-abort on timeout

// ENT-085: Vision/multimodal — attached image state
let _attachedImageData = null;   // base64 string (no data: prefix)
let _attachedImageType = null;   // e.g. "image/png"
let _attachedImageName = null;   // filename for display

function _initImageAttachment() {
    let attachBtn = document.getElementById('image-attach-btn');
    let fileInput = document.getElementById('image-upload-input');
    let removeBtn = document.getElementById('image-remove-btn');
    if (!attachBtn || !fileInput) return;

    attachBtn.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        let file = this.files && this.files[0];
        if (!file) return;
        // Validate size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            Platform.toast.warning('Image too large. Maximum size is 10 MB.');
            this.value = '';
            return;
        }
        // Validate type
        let allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
        if (allowed.indexOf(file.type) === -1) {
            Platform.toast.warning('Unsupported image type. Please use PNG, JPG, GIF, or WebP.');
            this.value = '';
            return;
        }
        let reader = new FileReader();
        reader.onload = function(e) {
            // e.target.result is "data:<type>;base64,<data>"
            let dataUrl = e.target.result;
            let commaIdx = dataUrl.indexOf(',');
            _attachedImageData = dataUrl.substring(commaIdx + 1);
            _attachedImageType = file.type;
            _attachedImageName = file.name;
            _showImagePreview(dataUrl, file.name);
        };
        reader.readAsDataURL(file);
    });

    if (removeBtn) {
        removeBtn.addEventListener('click', _clearAttachedImage);
    }
}

function _showImagePreview(dataUrl, fileName) {
    let bar = document.getElementById('image-preview-bar');
    let thumb = document.getElementById('image-preview-thumb');
    let nameEl = document.getElementById('image-preview-name');
    if (!bar) return;
    thumb.src = dataUrl;
    nameEl.textContent = fileName;
    bar.classList.remove('hidden');
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function _clearAttachedImage() {
    _attachedImageData = null;
    _attachedImageType = null;
    _attachedImageName = null;
    let bar = document.getElementById('image-preview-bar');
    let fileInput = document.getElementById('image-upload-input');
    if (bar) bar.classList.add('hidden');
    if (fileInput) fileInput.value = '';
}

function _setSendingUI(sending) {
    if (sendBtn) { sendBtn.disabled = sending; sendBtn.classList.toggle('hidden', sending); }
    if (stopBtn) { stopBtn.classList.toggle('hidden', !sending); }
}

if (stopBtn) {
    stopBtn.addEventListener('click', function() {
        if (_activeAbortTimer) { clearTimeout(_activeAbortTimer); _activeAbortTimer = null; }
        if (_activeAbortController) {
            _activeAbortController.abort();
            _activeAbortController = null;
        }
        isSending = false;
        _setSendingUI(false);
        let loading = document.querySelector('.loading-message');
        if (loading) {
            let bubble = loading.closest('.flex.gap-4');
            if (bubble) bubble.remove();
        }
    });
}

// Rate limit tracking (30 req/hour) — AIC-RATELIMIT
let rateLimitCount = parseInt(sessionStorage.getItem('ai_chat_rate_count') || '0');
let rateLimitResetAt = parseInt(sessionStorage.getItem('ai_chat_rate_reset') || '0');
let RATE_LIMIT_MAX = 30;

function getRateLimitRemaining() {
    let now = Date.now();
    if (now > rateLimitResetAt) {
        rateLimitCount = 0;
        rateLimitResetAt = now + 3600000; // 1 hour
        sessionStorage.setItem('ai_chat_rate_count', '0');
        sessionStorage.setItem('ai_chat_rate_reset', rateLimitResetAt.toString());
    }
    return RATE_LIMIT_MAX - rateLimitCount;
}

function incrementRateLimit() {
    rateLimitCount++;
    sessionStorage.setItem('ai_chat_rate_count', rateLimitCount.toString());
    updateRateLimitUI();
}

function updateRateLimitUI() {
    let badge = document.getElementById('rate-limit-badge');
    if (!badge) return;
    let remaining = getRateLimitRemaining();
    badge.textContent = remaining + '/' + RATE_LIMIT_MAX;
    if (remaining <= 5) {
        badge.className = 'text-xs px-2 py-0.5 rounded-full bg-destructive/10 text-destructive font-medium border border-destructive/20';
    } else if (remaining <= 10) {
        badge.className = 'text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium border border-amber-200';
    } else {
        badge.className = 'text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium';
    }
    badge.title = remaining + ' AI requests remaining this hour';
}

// ==========================================================================
// CSRF helper — all POST requests must include this
// ==========================================================================

function csrfHeaders(extra) {
    let headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.csrfToken || ''
    };
    if (extra) {
        for (let k in extra) { headers[k] = extra[k]; }
    }
    return headers;
}

// ==========================================================================
// Model Loading
// ==========================================================================

async function loadAvailableModels() {
    try {
        let response = await fetch('/ai-chat/models');
        let data = await response.json();
        if (data.success) {
            safeHTML(modelSelector, '<option value="">Auto-Select Model</option>');
            data.models.forEach(function(model) {
                let option = document.createElement('option');
                option.value = model.model;
                option.textContent = model.display_name;
                if (model.recommended_for && model.recommended_for.length > 0) {
                    option.textContent += ' (' + model.recommended_for[0] + ')';
                }
                modelSelector.appendChild(option);
            });
        }
    } catch (error) {
        console.warn('Could not load models:', error);
    }
}

// ==========================================================================
// Color Class Mappings
// ==========================================================================

let colorClasses = {
    'blue': { bg: 'bg-blue-500', gradient: 'bg-blue-500', text: 'text-blue-700', badge: 'bg-blue-500/10 text-blue-700', light: 'bg-blue-50 border-blue-200', iconBg: 'bg-blue-500/10', iconText: 'text-blue-600' }, // token-migration-ok
    'green': { bg: 'bg-green-500', gradient: 'bg-green-500', text: 'text-green-700', badge: 'bg-green-500/10 text-green-700', light: 'bg-green-50 border-green-200', iconBg: 'bg-green-500/10', iconText: 'text-green-600' }, // token-migration-ok
    'purple': { bg: 'bg-purple-500', gradient: 'bg-purple-500', text: 'text-purple-700', badge: 'bg-purple-500/10 text-purple-700', light: 'bg-purple-50 border-purple-200', iconBg: 'bg-purple-500/10', iconText: 'text-purple-600' }, // token-migration-ok
    'orange': { bg: 'bg-orange-500', gradient: 'bg-orange-500', text: 'text-orange-700', badge: 'bg-orange-500/10 text-orange-700', light: 'bg-orange-50 border-orange-200', iconBg: 'bg-orange-500/10', iconText: 'text-orange-600' },
    'indigo': { bg: 'bg-indigo-500', gradient: 'bg-indigo-500', text: 'text-indigo-700', badge: 'bg-indigo-500/10 text-indigo-700', light: 'bg-indigo-50 border-indigo-200', iconBg: 'bg-indigo-500/10', iconText: 'text-indigo-600' }, // token-migration-ok
    'teal': { bg: 'bg-teal-500', gradient: 'bg-teal-500', text: 'text-teal-700', badge: 'bg-teal-500/10 text-teal-700', light: 'bg-teal-50 border-teal-200', iconBg: 'bg-teal-500/10', iconText: 'text-teal-600' },
    'primary': { bg: 'bg-primary', gradient: 'bg-primary', text: 'text-primary', badge: 'bg-primary/10 text-primary', light: 'bg-primary/5 border-primary/20', iconBg: 'bg-primary/10', iconText: 'text-primary' },
    'amber': { bg: 'bg-amber-500', gradient: 'bg-amber-500', text: 'text-amber-700', badge: 'bg-amber-500/10 text-amber-700', light: 'bg-amber-50 border-amber-200', iconBg: 'bg-amber-500/10', iconText: 'text-amber-600' },
    'cyan': { bg: 'bg-cyan-500', gradient: 'bg-cyan-500', text: 'text-cyan-700', badge: 'bg-cyan-500/10 text-cyan-700', light: 'bg-cyan-50 border-cyan-200', iconBg: 'bg-cyan-500/10', iconText: 'text-cyan-600' },
    'red': { bg: 'bg-red-500', gradient: 'bg-red-500', text: 'text-red-700', badge: 'bg-red-500/10 text-red-700', light: 'bg-red-50 border-red-200', iconBg: 'bg-red-500/10', iconText: 'text-red-600' } // token-migration-ok
};

function getColorClass(colorName, type) {
    type = type || 'bg';
    let colors = colorClasses[colorName] || colorClasses['primary'];
    return colors[type] || colors.bg;
}

// ==========================================================================
// Domain & Persona Management
// ==========================================================================

domainSelector.addEventListener('change', function(e) {
    currentDomain = e.target.value;
    sessionStorage.setItem('ai_chat_domain', currentDomain);
    updateDomainUI(currentDomain);
    loadDomainContext(currentDomain);
    updateTemplateOptions(currentDomain);
});

personaSelector.addEventListener('change', function(e) {
    currentPersona = e.target.value;
    sessionStorage.setItem('ai_chat_persona', currentPersona);
    updatePersonaUI(currentPersona);
    if (currentPersona && personaConfig[currentPersona]) {
        let defaultDomain = personaConfig[currentPersona].default_domain;
        if (defaultDomain && defaultDomain !== currentDomain) {
            domainSelector.value = defaultDomain;
            currentDomain = defaultDomain;
            sessionStorage.setItem('ai_chat_domain', currentDomain);
            updateDomainUI(currentDomain);
            loadDomainContext(currentDomain);
        }
        if (!hasConversationStarted) {
            renderWelcomeScreen();
        }
    }
});

function updatePersonaUI(persona) {
    if (!persona || !personaConfig[persona]) {
        document.getElementById('domain-description').textContent = 'Enterprise Architecture Intelligence';
        return;
    }
    let config = personaConfig[persona];
    document.getElementById('domain-description').textContent = config.description || config.name;
}

function updateSamplePrompts(persona) {
    if (!persona || !personaConfig[persona]) return;
    let config = personaConfig[persona];
    let prompts = config.sample_prompts || [];
    if (prompts.length > 0) {
        let contextDiv = document.getElementById('domain-context');
        safeHTML(contextDiv, DOMPurify.sanitize(
            '<h3 class="font-medium text-sm mb-3">Sample Prompts for ' + DOMPurify.sanitize(config.name) + '</h3>' +
            '<div class="space-y-2" id="sample-prompts-container"></div>' +
            '<div class="mt-4 p-3 bg-muted/50 rounded-lg">' +
            '<h4 class="font-medium text-xs mb-2">Expertise Areas</h4>' +
            '<div class="flex flex-wrap gap-1">' +
            (config.expertise || []).map(function(e) {
                return '<span class="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full">' + DOMPurify.sanitize(e) + '</span>';
            }).join('') +
            '</div></div>'
        ));
        let promptsContainer = document.getElementById('sample-prompts-container');
        prompts.forEach(function(p) {
            let btn = document.createElement('button');
            btn.className = 'text-left p-2 rounded-lg border hover:bg-accent text-xs truncate w-full transition-colors';
            btn.textContent = p;
            btn.addEventListener('click', function() { usePrompt(p); });
            promptsContainer.appendChild(btn);
        });
    }
}

function usePrompt(prompt) {
    userInput.value = prompt;
    userInput.focus();
    autoResizeTextarea();
}

function updateDomainUI(domain) {
    let config = domainConfig[domain];
    if (!config) return;

    document.getElementById('domain-title').textContent = config.name;
    document.getElementById('domain-description').textContent = config.description;

    let iconElement = document.getElementById('domain-icon');
    safeHTML(iconElement, DOMPurify.sanitize('<i data-lucide="' + (config.icon || 'bot') + '" class="h-5 w-5"></i>'));

    let bgClass = getColorClass(config.color || 'primary', 'bg');
    iconElement.className = 'flex h-10 w-10 items-center justify-center rounded-xl ' + bgClass + ' text-primary-foreground transition-all duration-300 shadow-sm';

    lucide.createIcons();
}

function updateTemplateOptions(domain) {
    let config = domainConfig[domain];
    if (!config || !config.templates) return;

    safeHTML(templateSelector, '');
    config.templates.forEach(function(template) {
        let option = document.createElement('option');
        option.value = template;
        option.textContent = template;
        templateSelector.appendChild(option);
    });
    promptTemplates.forEach(function(template) {
        let customOption = document.createElement('option');
        customOption.value = template.name;
        customOption.textContent = template.name;
        templateSelector.appendChild(customOption);
    });
}

// ==========================================================================
// Domain Context Loading
// ==========================================================================

async function loadDomainContext(domain) {
    try {
        let response = await fetch(`/ai-chat/context/${domain}`);
        let data = await response.json();
        let contextContainer = document.getElementById('domain-context');
        safeHTML(contextContainer, '');

        if (domain === 'architecture' && data.elements) {
            safeHTML(contextContainer, DOMPurify.sanitize(
                '<h3 class="font-medium text-sm mb-3">ArchiMate Elements</h3>' +
                '<div class="space-y-2">' +
                data.elements.map(function(el) {
                    return '<div class="rounded-lg border bg-card p-3 shadow-sm cursor-pointer hover:bg-accent transition-colors js-ctx-element" ' +
                        'data-element-id="' + parseInt(el.id) + '" data-context-type="archimate_element">' +
                        '<div class="flex items-center gap-2 mb-1">' +
                        '<span class="bg-primary/10 text-primary text-[10px] px-1.5 py-0.5 rounded font-medium">' + DOMPurify.sanitize(el.type) + '</span>' +
                        '<span class="font-medium text-sm">' + DOMPurify.sanitize(el.name) + '</span>' +
                        '</div></div>';
                }).join('') +
                '</div>'
            ));
            contextContainer.querySelectorAll('.js-ctx-element').forEach(function(el) {
                el.addEventListener('click', function() {
                    selectContext(parseInt(this.dataset.elementId), this.dataset.contextType);
                });
            });
        } else if (domain === 'technology' && data.applications) {
            safeHTML(contextContainer, DOMPurify.sanitize(
                '<h3 class="font-medium text-sm mb-3">Applications</h3>' +
                '<div class="space-y-2">' +
                data.applications.map(function(app) {
                    return '<div class="rounded-lg border bg-card p-3 shadow-sm cursor-pointer hover:bg-accent transition-colors js-ctx-element" ' +
                        'data-element-id="' + parseInt(app.id) + '" data-context-type="application">' +
                        '<div class="flex items-center gap-2 mb-1">' +
                        '<span class="bg-emerald-500/10 text-emerald-700 text-[10px] px-1.5 py-0.5 rounded font-medium">Application</span>' +
                        '<span class="font-medium text-sm">' + DOMPurify.sanitize(app.name) + '</span>' +
                        '</div>' +
                        '<p class="text-xs text-muted-foreground">' + DOMPurify.sanitize(app.technology || 'No technology info') + '</p>' +
                        '</div>';
                }).join('') +
                '</div>'
            ));
            contextContainer.querySelectorAll('.js-ctx-element').forEach(function(el) {
                el.addEventListener('click', function() {
                    selectContext(parseInt(this.dataset.elementId), this.dataset.contextType);
                });
            });
        } else {
            if (currentPersona && personaConfig[currentPersona]) {
                updateSamplePrompts(currentPersona);
            } else {
                safeHTML(contextContainer, DOMPurify.sanitize(
                    '<div class="text-center py-8 text-muted-foreground">' +
                    '<i data-lucide="inbox" class="h-8 w-8 mx-auto mb-2 opacity-50"></i>' +
                    '<p class="text-sm">No specific context available for ' + DOMPurify.sanitize(domain) + '</p>' +
                    '</div>'
                ));
            }
        }
        lucide.createIcons();
    } catch (error) {
        console.error('Error loading domain context:', error);
    }
}

function selectContext(elementId, contextType) {
    selectedElementIdInput.value = elementId;
    contextElement = { id: elementId, type: contextType };
    appendSystemMessage('Context set: ' + contextType + ' #' + elementId, 'info');
}

// ==========================================================================
// Auto-resize textarea & Command Hints
// ==========================================================================

function autoResizeTextarea() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
}

let _slashCommands = [
    { cmd: '/rationalize', desc: 'Analyze application portfolio for rationalization opportunities' },
    { cmd: '/gap-analysis', desc: 'Run capability, vendor, or process gap analysis' },
    { cmd: '/generate-archimate', desc: 'Generate ArchiMate 3.2 elements for an application' },
    { cmd: '/discover-vendors', desc: 'Find vendors for a specific capability' },
    { cmd: '/map-apqc', desc: 'Map APQC PCF processes to an application' },
    { cmd: '/help', desc: 'Show all available commands' }
];

function handleInputChange() {
    autoResizeTextarea();
    let val = userInput.value;
    if (val.startsWith('/') && !val.includes(' ') && val.length < 25) {
        if (commandHints) {
            let matches = _slashCommands.filter(function(c) { return c.cmd.startsWith(val); });
            if (matches.length > 0) {
                let html = matches.map(function(c) {
                    return '<button type="button" class="flex w-full items-start gap-2 px-2 py-1 rounded text-xs hover:bg-accent text-left" onclick="userInput.value=\'' + c.cmd + '\'; handleInputChange();">' +
                        '<span class="font-mono font-semibold text-primary shrink-0">' + c.cmd + '</span>' +
                        '<span class="text-muted-foreground">' + c.desc + '</span></button>';
                }).join('');
                safeHTML(commandHints, '<div class="border rounded-md bg-popover shadow-md p-1 mb-2">' + html + '</div>');
                commandHints.classList.remove('hidden');
            } else {
                commandHints.classList.add('hidden');
            }
        }
    } else {
        if (commandHints) commandHints.classList.add('hidden');
    }
}

// ==========================================================================
// Keyboard Handling
// ==========================================================================

function handleEnter(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
}

// ==========================================================================
// Command Handler
// ==========================================================================

async function handleChatCommand(message) {
    let parts = message.trim().split(/\s+/);
    let command = parts[0].toLowerCase();
    let args = parts.slice(1).join(' ');

    let commands = {
        '/generate-archimate': handleGenerateArchimate,
        '/map-apqc': handleMapApqc,
        '/save-insights': handleSaveInsights,
        '/bulk-process': handleBulkProcess,
        '/gap-analysis': handleGapAnalysis,
        '/discover-vendors': handleDiscoverVendors,
        '/rationalize': handleRationalize,
        '/help': showCommandHelp
    };

    if (commands[command]) {
        await commands[command](args);
        return true;
    }
    return false;
}

// ==========================================================================
// Actionable Workflow Functions
// ==========================================================================

async function handleGenerateArchimate(args) {
    let appId = args.trim() || (contextElement && contextElement.id);
    if (!appId) {
        appendMessage('ai', '**Generate ArchiMate Elements**\n\nTo generate ArchiMate 3.2 elements for an application:\n\n1. Select an application from the **Context Panel** (left sidebar)\n2. Or provide an ID: `/generate-archimate 42`\n\nI will analyze the application and suggest Business, Application, and Technology layer elements with confidence scores.', { domain: 'architecture' });
        return;
    }
    appendSystemMessage('Generating ArchiMate elements for application ' + appId + '...', 'info');
    try {
        let response = await fetch('/ai-chat/chat/generate-archimate', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ application_id: parseInt(appId), preview_only: true })
        });
        let data = await response.json();
        if (data.success) {
            let elementsHtml = data.elements.map(function(e) {
                return '- **' + e.type + '**: ' + e.name + ' (' + Math.round(e.confidence * 100) + '% confidence)';
            }).join('\n');
            let capSuggestions = '';
            if (data.capability_suggestions && data.capability_suggestions.length > 0) {
                capSuggestions = '\n### Capability Suggestions\n' + data.capability_suggestions.slice(0, 3).map(function(c) { return '- ' + c.capability_name; }).join('\n');
            }
            let procSuggestions = '';
            if (data.process_suggestions && data.process_suggestions.length > 0) {
                procSuggestions = '\n### APQC Process Suggestions\n' + data.process_suggestions.slice(0, 3).map(function(p) { return '- ' + p.process_code + ': ' + p.process_name; }).join('\n');
            }
            appendMessage('ai', '## ArchiMate Elements for ' + DOMPurify.sanitize(data.application_name) + '\n\n' +
                (data.elements.length > 0 ? elementsHtml : 'No elements suggested.') + capSuggestions + procSuggestions,
                { domain: 'architecture' });

            /* ENT-121: Store elements for Composer prefill and show Open in Composer button */
            if (data.elements && data.elements.length > 0) {
                try {
                    sessionStorage.setItem('composer_prefill', JSON.stringify({
                        elements: data.elements,
                        relationships: data.relationships || [],
                        app_name: data.application_name,
                        timestamp: Date.now(),
                    }));
                } catch (_) { /* storage full / private browsing — skip silently */ }

                let btnDiv = document.createElement('div');
                btnDiv.className = 'flex justify-end mt-2 ml-12';
                let btn = document.createElement('a');
                btn.href = '/archimate/composer?prefill=1';
                btn.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors';
                btn.setAttribute('data-ent121-composer-link', '');
                let relCount = (data.relationships || []).length;
                let hint = data.elements.length + ' element' + (data.elements.length !== 1 ? 's' : '');
                if (relCount > 0) hint += ', ' + relCount + ' relationship' + (relCount !== 1 ? 's' : '');
                safeHTML(btn, '<i data-lucide="layout-template" class="h-3 w-3"></i> Open in Composer (' + hint + ')');
                btnDiv.appendChild(btn);
                messagesContainer.appendChild(btnDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                lucide.createIcons();
            }
        } else {
            appendMessage('ai', '**Error:** ' + data.error, { domain: 'architecture' });
        }
    } catch (error) {
        appendMessage('ai', '**Error:** ' + error.message, { domain: 'architecture' });
    }
}

async function applyArchimateElements(appId) {
    try {
        let response = await fetch('/ai-chat/chat/generate-archimate', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ application_id: parseInt(appId), preview_only: false })
        });
        let data = await response.json();
        if (data.success) {
            appendSystemMessage('Created ' + data.elements_created + ' ArchiMate elements', 'info');
        } else {
            appendSystemMessage(data.error, 'error');
        }
    } catch (error) {
        appendSystemMessage(error.message, 'error');
    }
}
window.applyArchimateElements = applyArchimateElements;

async function handleMapApqc(args) {
    let appId = args.trim() || (contextElement && contextElement.id);
    if (!appId) {
        appendMessage('ai', '**Map APQC Processes**\n\nTo map APQC PCF processes for an application:\n\n1. Select an application from the **Context Panel**\n2. Or provide an ID: `/map-apqc 42`\n\nI will analyze the application and suggest process mappings with confidence levels.', { domain: 'business_capability' });
        return;
    }
    appendSystemMessage('Mapping APQC processes for application ' + appId + '...', 'info');
    try {
        let response = await fetch('/ai-chat/chat/map-apqc', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ application_id: parseInt(appId), preview_only: true })
        });
        let data = await response.json();
        if (data.success) {
            let highConf = data.mappings.filter(function(m) { return m.confidence >= 0.85; });
            let medConf = data.mappings.filter(function(m) { return m.confidence >= 0.7 && m.confidence < 0.85; });
            let lowConf = data.mappings.filter(function(m) { return m.confidence < 0.7; });
            appendMessage('ai',
                '## APQC Process Mappings for ' + DOMPurify.sanitize(data.application_name) + '\n\n' +
                '**High Confidence (>=85%):**\n' +
                (highConf.length > 0 ? highConf.map(function(m) { return '- ' + m.process_code + ': ' + m.process_name + ' (' + Math.round(m.confidence * 100) + '%)'; }).join('\n') : 'None') +
                '\n\n**Medium Confidence (70-85%):**\n' +
                (medConf.length > 0 ? medConf.map(function(m) { return '- ' + m.process_code + ': ' + m.process_name + ' (' + Math.round(m.confidence * 100) + '%)'; }).join('\n') : 'None') +
                '\n\n**Low Confidence (<70%):**\n' +
                (lowConf.length > 0 ? lowConf.map(function(m) { return '- ' + m.process_code + ': ' + m.process_name + ' (' + Math.round(m.confidence * 100) + '%)'; }).join('\n') : 'None'),
                { domain: 'business_capability' });
        } else {
            appendMessage('ai', '**Error:** ' + data.error, { domain: 'business_capability' });
        }
    } catch (error) {
        appendMessage('ai', '**Error:** ' + error.message, { domain: 'business_capability' });
    }
}

async function applyApqcMappings(appId, highConfOnly) {
    try {
        let response = await fetch('/ai-chat/chat/map-apqc', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ application_id: parseInt(appId), preview_only: false, apply_high_confidence: highConfOnly })
        });
        let data = await response.json();
        if (data.success) {
            appendSystemMessage('Applied ' + data.mappings_applied + ' APQC mappings', 'info');
        } else {
            appendSystemMessage(data.error, 'error');
        }
    } catch (error) {
        appendSystemMessage(error.message, 'error');
    }
}
window.applyApqcMappings = applyApqcMappings;

async function handleSaveInsights(args) {
    appendMessage('ai', '**Save Insights**\n\nTo save insights from our conversation to an application, use:\n`/save-insights [application_id]`\n\nOr select an application from context and describe what insights to save.', { domain: 'general' });
}

async function handleBulkProcess(args) {
    let maxApps = parseInt(args) || 10;
    appendSystemMessage('Starting bulk processing for up to ' + maxApps + ' applications...', 'info');
    try {
        let response = await fetch('/ai-chat/chat/bulk-process', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ max_applications: maxApps, map_capabilities: true, map_processes: true, generate_archimate: false, auto_create: false })
        });
        let data = await response.json();
        if (data.success) {
            let appLines = '';
            if (data.applications) {
                appLines = data.applications.slice(0, 5).map(function(app) {
                    return '- ' + app.application_name + ': ' + (app.capabilities ? app.capabilities.length : 0) + ' caps, ' + (app.processes ? app.processes.length : 0) + ' procs';
                }).join('\n');
            }
            appendMessage('ai',
                '## Bulk Processing Results\n\n' +
                '**Applications Processed:** ' + data.total_processed + '\n' +
                '**Capability Mappings Created:** ' + data.capability_mappings_created + '\n' +
                '**Process Mappings Created:** ' + data.process_mappings_created + '\n' +
                '**ArchiMate Elements Created:** ' + data.archimate_elements_created + '\n\n' +
                appLines + '\n\nUse `/bulk-process [number]` to process more applications.',
                { domain: 'general' });
        } else {
            appendMessage('ai', '**Error:** ' + data.error, { domain: 'general' });
        }
    } catch (error) {
        appendMessage('ai', '**Error:** ' + error.message, { domain: 'general' });
    }
}

async function handleGapAnalysis(args) {
    let analysisType = args.trim() || 'capability';
    appendSystemMessage('Running ' + analysisType + ' gap analysis...', 'info');
    try {
        let response = await fetch('/ai-chat/chat/gap-analysis', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ analysis_type: analysisType })
        });
        let data = await response.json();
        if (data.success) {
            appendMessage('ai',
                '## Gap Analysis: ' + DOMPurify.sanitize(data.analysis_type) + '\n\n' +
                '**Total Gaps Found:** ' + data.total_gaps + '\n' +
                '**Critical/High Priority:** ' + data.critical_gaps + '\n\n### Top Gaps:\n' +
                data.gaps.slice(0, 10).map(function(g) {
                    let icon = g.severity === 'high' ? '**[HIGH]' : '**[MED]';
                    return '- ' + icon + ' ' + DOMPurify.sanitize(g.name) + '**\n  ' + DOMPurify.sanitize(g.description) + '\n  *Recommendation:* ' + DOMPurify.sanitize(g.recommendation);
                }).join('\n'),
                { domain: 'gap_analysis' });
        } else {
            appendMessage('ai', '**Error:** ' + data.error, { domain: 'gap_analysis' });
        }
    } catch (error) {
        appendMessage('ai', '**Error:** ' + error.message, { domain: 'gap_analysis' });
    }
}
window.handleGapAnalysis = handleGapAnalysis;

async function handleDiscoverVendors(args) {
    let capabilityName = args.trim();
    if (!capabilityName) {
        appendMessage('ai', '**Discover Vendors**\n\nFind vendors that support a specific capability:\n\n`/discover-vendors Customer Relationship Management`\n\nI will search the vendor catalog and provide capability fit scores and TCO estimates.', { domain: 'vendor_intelligence' });
        return;
    }
    appendSystemMessage('Discovering vendors for "' + capabilityName + '"...', 'info');
    try {
        let response = await fetch('/ai-chat/chat/discover-vendors', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ capability_name: capabilityName, calculate_tco: true })
        });
        let data = await response.json();
        if (data.success) {
            appendMessage('ai',
                '## Vendor Discovery: ' + DOMPurify.sanitize(data.capability_searched) + '\n\n' +
                '**Vendors Found:** ' + data.vendors_found + '\n\n' +
                data.vendors.map(function(v, i) {
                    let tcoLine = v.tco_estimate ? '\n**3-Year TCO:** $' + v.tco_estimate.three_year.toLocaleString() : '';
                    return '### ' + (i + 1) + '. ' + DOMPurify.sanitize(v.vendor_name) + ' (' + Math.round(v.capability_fit * 100) + '% fit)\n' +
                        '**Products:** ' + v.products.map(function(p) { return DOMPurify.sanitize(p.product_name); }).join(', ') + tcoLine;
                }).join('\n\n'),
                { domain: 'vendor_intelligence' });
        // Inject "Apply to solution" buttons into each vendor heading
        let lastMsgEl = messagesContainer.lastElementChild;
        if (lastMsgEl) {
            let contentDiv = lastMsgEl.querySelector('.message-content');
            if (contentDiv) {
                let solutionId = contextElement && contextElement.type === 'solution' ? contextElement.id : '';
                data.vendors.forEach(function(v) {
                    contentDiv.querySelectorAll('h3').forEach(function(h3) {
                        if (h3.textContent.includes(v.vendor_name) && !h3.dataset.vendorName) {
                            h3.dataset.vendorName = v.vendor_name;
                        }
                    });
                });
                injectVendorApplyButtons(contentDiv, solutionId);
            }
        }
        } else {
            appendMessage('ai', '**Error:** ' + data.error, { domain: 'vendor_intelligence' });
        }
    } catch (error) {
        appendMessage('ai', '**Error:** ' + error.message, { domain: 'vendor_intelligence' });
    }
}

function showCommandHelp() {
    appendMessage('ai',
        '## Available Commands\n\n' +
        '| Command | Description |\n' +
        '|---------|-------------|\n' +
        '| `/generate-archimate [app_id]` | Generate ArchiMate 3.2 elements for an application |\n' +
        '| `/map-apqc [app_id]` | Map APQC PCF processes to an application |\n' +
        '| `/gap-analysis [type]` | Run gap analysis (capability, vendor, or process) |\n' +
        '| `/discover-vendors [capability]` | Find vendors for a specific capability |\n' +
        '| `/bulk-process [count]` | Bulk process applications (default: 10) |\n' +
        '| `/save-insights [app_id]` | Save chat insights to an application |\n' +
        '| `/rationalize` | Analyze application portfolio for rationalization opportunities |\n' +
        '| `/help` | Show this help message |\n\n' +
        '**Tip:** Select an application from the Context panel first, then commands will use it automatically.',
        { domain: 'general' });
}

async function handleRationalize() {
    let prompt = 'Analyze our application portfolio for rationalization opportunities. Identify:\n\n' +
        '1. **Retirement candidates** — redundant, low-use, or end-of-life applications\n' +
        '2. **Consolidation candidates** — overlapping applications serving the same business capability\n' +
        '3. **Modernization candidates** — critical applications with high technical debt\n\n' +
        'Return a prioritized list with business justification for each recommendation, ' +
        'referencing capability alignment and estimated cost impact where possible.';
    userInput.value = prompt;
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
    chatForm.dispatchEvent(new Event('submit'));
}

// ==========================================================================
// Action Card Rendering
// ==========================================================================

function renderActionCard(type, data) {
    let div = document.createElement('div');
    div.className = 'flex gap-4';

    let avatarIcon = type === 'archimate' ? 'layers' : 'list-tree';
    let avatar = '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-lg">' +
         '<i data-lucide="' + avatarIcon + '" class="h-5 w-5"></i></div>';

    let contentHtml = '';
    let title = '';
    let appId = data.application_id;

    if (type === 'archimate') {
        title = 'Generated ArchiMate Elements for ' + DOMPurify.sanitize(data.application_name);
        contentHtml = data.elements.map(function(el, index) {
            let confidenceClass = el.confidence > 80 ? 'confidence-high' : (el.confidence > 50 ? 'confidence-medium' : 'confidence-low');
            let confidenceLabel = el.confidence > 80 ? 'High' : (el.confidence > 50 ? 'Medium' : 'Low');
            return '<div class="element-item">' +
                '<input type="checkbox" class="element-checkbox" id="elem-' + index + '" checked data-element=\'' + JSON.stringify(el).replace(/'/g, '&#39;') + '\' aria-label="Select ' + DOMPurify.sanitize(el.name) + '">' +
                '<div class="element-icon"><i data-lucide="box" class="h-4 w-4"></i></div>' +
                '<div class="flex-1 min-w-0">' +
                '<div class="flex items-center gap-2 mb-1">' +
                '<span class="font-medium text-sm truncate">' + DOMPurify.sanitize(el.name) + '</span>' +
                '<span class="text-xs text-muted-foreground">(' + DOMPurify.sanitize(el.type) + ')</span>' +
                '<span class="confidence-badge ' + confidenceClass + '">' + parseInt(el.confidence) + '% ' + confidenceLabel + '</span>' +
                '</div>' +
                '<p class="text-xs text-muted-foreground line-clamp-2">' + DOMPurify.sanitize(el.description || 'No description') + '</p>' +
                (el.reasoning ? '<p class="text-[10px] text-primary dark:text-primary/80 mt-1"><i data-lucide="info" class="h-3 w-3 inline mr-0.5"></i> ' + DOMPurify.sanitize(el.reasoning) + '</p>' : '') +
                '</div></div>';
        }).join('');
    } else if (type === 'apqc') {
        title = 'APQC Process Mappings for ' + DOMPurify.sanitize(data.application_name);
        contentHtml = data.suggestions.map(function(item, index) {
            let confidenceClass = item.confidence > 80 ? 'confidence-high' : (item.confidence > 50 ? 'confidence-medium' : 'confidence-low');
            return '<div class="element-item">' +
                '<input type="checkbox" class="element-checkbox" id="map-' + index + '" ' + (item.selected ? 'checked' : '') + ' data-mapping=\'' + JSON.stringify(item).replace(/'/g, '&#39;') + '\' aria-label="Select ' + DOMPurify.sanitize(item.name) + '">' +
                '<div class="element-icon"><i data-lucide="git-branch" class="h-4 w-4"></i></div>' +
                '<div class="flex-1 min-w-0">' +
                '<div class="flex items-center gap-2 mb-1">' +
                '<span class="font-medium text-sm text-primary">' + DOMPurify.sanitize(item.code) + '</span>' +
                '<span class="font-medium text-sm truncate">' + DOMPurify.sanitize(item.name) + '</span>' +
                '<span class="confidence-badge ' + confidenceClass + '">' + parseInt(item.confidence) + '%</span>' +
                '</div>' +
                '<p class="text-xs text-muted-foreground">' + DOMPurify.sanitize(item.hierarchy) + '</p>' +
                '</div></div>';
        }).join('');
    }

    let bubble = '<div class="rounded-xl bg-muted/50 p-4 text-sm w-full max-w-3xl">' +
        '<div class="action-card bg-background border shadow-sm">' +
        '<div class="action-card-header p-3">' +
        '<div class="action-card-title">' +
        '<i data-lucide="sparkles" class="h-4 w-4 text-primary"></i> ' + title +
        '</div></div>' +
        '<div class="p-3 max-h-96 overflow-y-auto custom-scrollbar">' + contentHtml + '</div>' +
        '<div class="action-buttons p-3 bg-muted/20 rounded-b-lg">' +
        '<button class="js-apply-action inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2" data-action-type="' + type + '" data-app-id="' + parseInt(appId) + '">' +
        '<i data-lucide="check" class="mr-2 h-4 w-4"></i> Apply Selected</button>' +
        '<button class="js-cancel-action inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2 ml-2">Cancel</button>' +
        '</div></div></div>';

    safeHTML(div, avatar + bubble);
    let applyBtn = div.querySelector('.js-apply-action');
    if (applyBtn) {
        applyBtn.addEventListener('click', function() {
            applyAction(this.dataset.actionType, parseInt(this.dataset.appId), this);
        });
    }
    let cancelBtn = div.querySelector('.js-cancel-action');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            this.closest('.action-card').remove();
        });
    }
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    lucide.createIcons();
}

// ==========================================================================
// Apply Action
// ==========================================================================

async function applyAction(type, appId, btn) {
    let card = btn.closest('.action-card');
    let checkboxes = card.querySelectorAll('input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        appendSystemMessage('Please select at least one item to apply.', 'error');
        return;
    }
    let originalText = btn.innerHTML; // SAFE: read-only, no assignment
    btn.disabled = true;
    safeHTML(btn, '<i data-lucide="loader-2" class="mr-2 h-4 w-4 animate-spin"></i> Applying...');
    lucide.createIcons();
    try {
        let endpoint = '';
        let payload = { application_id: appId };
        if (type === 'archimate') {
            endpoint = '/ai-chat/apply-archimate';
            payload.elements = Array.from(checkboxes).map(function(cb) { return JSON.parse(cb.dataset.element); });
        } else if (type === 'apqc') {
            endpoint = '/ai-chat/apply-apqc';
            payload.mappings = Array.from(checkboxes).map(function(cb) { return JSON.parse(cb.dataset.mapping); });
        }
        let response = await fetch(endpoint, {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify(payload)
        });
        let result = await response.json();
        if (result.success) {
            let parent = card.parentElement;
            safeHTML(parent, DOMPurify.sanitize(
                '<div class="p-4 bg-emerald-500/5 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-800 rounded-lg text-emerald-800 dark:text-emerald-300">' +
                '<div class="flex items-center gap-2 font-semibold">' +
                '<i data-lucide="check-circle" class="h-5 w-5"></i> Success</div>' +
                '<p class="mt-1 text-sm">' + DOMPurify.sanitize(result.message) + '</p></div>'
            ));
            lucide.createIcons();
        } else {
            appendSystemMessage('Error: ' + result.error, 'error');
            btn.disabled = false;
            safeHTML(btn, originalText);
        }
    } catch (error) {
        appendSystemMessage('Failed to apply changes: ' + error.message, 'error');
        btn.disabled = false;
        safeHTML(btn, originalText);
    }
}
window.applyAction = applyAction;

// ==========================================================================
// Message Rendering
// ==========================================================================

function appendLoadingMessage() {
    let id = 'loading-' + Date.now();
    let div = document.createElement('div');
    div.id = id;
    div.className = 'flex gap-4';
    let domainColor = (domainConfig[currentDomain] && domainConfig[currentDomain].color) || 'primary';
    let loadingGradient = getColorClass(domainColor, 'gradient');
    let loadingIcon = (domainConfig[currentDomain] && domainConfig[currentDomain].icon) || 'bot';
    let domainName = (domainConfig[currentDomain] && domainConfig[currentDomain].name) || 'AI';
    safeHTML(div,
        '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ' + loadingGradient + ' text-primary-foreground shadow-lg">' +
        '<i data-lucide="' + loadingIcon + '" class="h-5 w-5 animate-pulse"></i></div>' +
        '<div class="rounded-xl bg-muted/50 p-4 text-sm">' +
        '<div class="flex items-center gap-3">' +
        '<div class="flex space-x-1">' +
        '<div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 0ms"></div>' +
        '<div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 150ms"></div>' +
        '<div class="w-2 h-2 bg-primary rounded-full animate-bounce" style="animation-delay: 300ms"></div>' +
        '</div>' +
        '<span class="text-muted-foreground text-sm">' + DOMPurify.sanitize(domainName) + ' is analyzing...</span>' +
        '</div></div>');
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    lucide.createIcons();
    return id;
}

function removeLoadingMessage(id) {
    let el = document.getElementById(id);
    if (el) el.remove();
}

/**
 * A95-019: Render structured TOGAF ADM phase cards for architect analysis responses.
 *
 * Displays 7 expandable cards (scope, capabilities, gaps, options, roadmap,
 * arb_draft, archimate). Each card has Approve/Edit buttons. Card 7 shows
 * "Open in Composer" only after all prior cards are approved.
 */
function renderArchitectPhaseCards(container, phases, solutionId, reasoningTrail) {
    if (!phases || typeof phases !== 'object') return;

    let phaseOrder = [
        { key: 'scope', label: 'Phase A: Architecture Vision', icon: 'target' },
        { key: 'capabilities', label: 'Phase B: Business Architecture', icon: 'layers' },
        { key: 'gaps', label: 'Phase C: Gap Analysis', icon: 'git-compare' },
        { key: 'options', label: 'Phase D: Options Assessment', icon: 'list-checks' },
        { key: 'roadmap', label: 'Phase E: Implementation Roadmap', icon: 'calendar' },
        { key: 'arb_draft', label: 'Phase F: ARB Submission Draft', icon: 'shield-check' },
        { key: 'archimate', label: 'Phase G: ArchiMate Model', icon: 'network' },
    ];

    let cardsWrapper = document.createElement('div');
    cardsWrapper.className = 'architect-phase-cards space-y-3 mt-4';
    cardsWrapper.setAttribute('data-solution-id', solutionId || '');

    let approvedStates = {};
    phaseOrder.forEach(function(p) { approvedStates[p.key] = false; });

    phaseOrder.forEach(function(phaseDef, idx) {
        let phaseData = phases[phaseDef.key];
        if (!phaseData) return;

        let card = document.createElement('div');
        card.className = 'phase-card border border-border rounded-lg overflow-hidden';
        card.setAttribute('data-phase', phaseDef.key);

        let contentText = '';
        if (typeof phaseData === 'string') {
            contentText = phaseData;
        } else if (phaseData.summary) {
            contentText = phaseData.summary;
        } else if (phaseData.element_count !== undefined) {
            contentText = 'Generated ' + phaseData.element_count + ' ArchiMate elements across ' +
                (phaseData.layer_count || 'multiple') + ' layers.';
        } else {
            contentText = JSON.stringify(phaseData, null, 2);
        }

        let headerHtml =
            '<div class="phase-card-header flex items-center justify-between px-4 py-3 bg-muted/30 cursor-pointer select-none" data-phase-toggle="' + phaseDef.key + '">' +
                '<div class="flex items-center gap-2">' +
                    '<i data-lucide="' + phaseDef.icon + '" class="h-4 w-4 text-primary"></i>' +
                    '<span class="text-sm font-semibold">' + DOMPurify.sanitize(phaseDef.label) + '</span>' +
                    '<span class="phase-status-badge px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground" data-phase-badge="' + phaseDef.key + '">Pending</span>' +
                '</div>' +
                '<i data-lucide="chevron-down" class="h-4 w-4 text-muted-foreground phase-chevron transition-transform"></i>' +
            '</div>';

        let bodyHtml =
            '<div class="phase-card-body px-4 py-3 text-sm prose dark:prose-invert max-w-none" data-phase-body="' + phaseDef.key + '" style="display:none;">' +
                DOMPurify.sanitize(marked.parse(contentText)) +
                '<div class="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">' +
                    '<button class="js-approve-phase inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors" data-phase="' + phaseDef.key + '">' +
                        '<i data-lucide="check" class="h-3 w-3"></i> Approve</button>' +
                    '<button class="js-edit-phase inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-accent transition-colors" data-phase="' + phaseDef.key + '">' +
                        '<i data-lucide="pencil" class="h-3 w-3"></i> Edit</button>' +
                    (idx === phaseOrder.length - 1 ?
                        '<a class="js-open-composer inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-accent text-accent-foreground hover:bg-accent/80 transition-colors ml-auto" href="/archimate/composer?solution_id=' + (solutionId || '') + '" style="display:none;" data-composer-link>' +
                            '<i data-lucide="layout-template" class="h-3 w-3"></i> Open in Composer</a>'
                    : '') +
                '</div>' +
            '</div>';

        safeHTML(card, headerHtml + bodyHtml);
        cardsWrapper.appendChild(card);
    });

    container.appendChild(cardsWrapper);

    // Wire up expand/collapse toggles
    cardsWrapper.querySelectorAll('[data-phase-toggle]').forEach(function(header) {
        header.addEventListener('click', function() {
            let phaseKey = header.getAttribute('data-phase-toggle');
            let body = cardsWrapper.querySelector('[data-phase-body="' + phaseKey + '"]');
            let chevron = header.querySelector('.phase-chevron');
            if (body) {
                let isVisible = body.style.display !== 'none';
                body.style.display = isVisible ? 'none' : 'block';
                if (chevron) chevron.style.transform = isVisible ? '' : 'rotate(180deg)';
            }
        });
    });

    // Wire approve buttons
    cardsWrapper.querySelectorAll('.js-approve-phase').forEach(function(btn) {
        btn.addEventListener('click', function() {
            let phaseKey = btn.getAttribute('data-phase');
            let solId = cardsWrapper.getAttribute('data-solution-id');
            btn.disabled = true;
            safeHTML(btn, '<i data-lucide="loader-2" class="h-3 w-3 animate-spin"></i> Approving...');

            fetch('/ai-chat/architect/approve-phase', {
                method: 'POST',
                headers: csrfHeaders(),
                body: JSON.stringify({ solution_id: parseInt(solId) || 0, phase_name: phaseKey }),
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    approvedStates[phaseKey] = true;
                    btn.className = btn.className.replace('bg-primary', 'bg-emerald-600').replace('hover:bg-primary/90', '');
                    safeHTML(btn, '<i data-lucide="check-circle" class="h-3 w-3"></i> Approved');
                    btn.disabled = true;
                    let badge = cardsWrapper.querySelector('[data-phase-badge="' + phaseKey + '"]');
                    if (badge) {
                        badge.textContent = 'Approved';
                        badge.className = badge.className.replace('bg-muted text-muted-foreground', 'bg-emerald-500/10 text-emerald-600');
                    }
                    lucide.createIcons();

                    // Check if all phases before archimate are approved
                    let allPriorApproved = ['scope', 'capabilities', 'gaps', 'options', 'roadmap', 'arb_draft']
                        .every(function(k) { return approvedStates[k]; });
                    if (allPriorApproved) {
                        let composerLink = cardsWrapper.querySelector('[data-composer-link]');
                        if (composerLink) composerLink.style.display = '';
                        // Show export row when all phases approved
                        let exportRow = container.querySelector('[data-export-row]');
                        if (exportRow) exportRow.style.display = '';
                    }
                } else {
                    btn.disabled = false;
                    safeHTML(btn, '<i data-lucide="check" class="h-3 w-3"></i> Approve');
                }
                lucide.createIcons();
            })
            .catch(function() {
                btn.disabled = false;
                safeHTML(btn, '<i data-lucide="check" class="h-3 w-3"></i> Approve');
                lucide.createIcons();
            });
        });
    });

    // Wire edit buttons — toggle inline edit mode
    cardsWrapper.querySelectorAll('.js-edit-phase').forEach(function(btn) {
        btn.addEventListener('click', function() {
            let phaseKey = btn.getAttribute('data-phase');
            let body = cardsWrapper.querySelector('[data-phase-body="' + phaseKey + '"]');
            if (!body) return;
            let contentEl = body.querySelector('.prose');
            if (!contentEl) contentEl = body;
            let existing = body.querySelector('.phase-edit-textarea');
            if (existing) {
                existing.remove();
                safeHTML(btn, '<i data-lucide="pencil" class="h-3 w-3"></i> Edit');
                lucide.createIcons();
                return;
            }
            let textarea = document.createElement('textarea');
            textarea.className = 'phase-edit-textarea w-full mt-2 p-2 rounded-md border border-input bg-background text-sm resize-y min-h-[80px]';
            textarea.value = contentEl.textContent;
            contentEl.after(textarea);
            textarea.focus();
            safeHTML(btn, '<i data-lucide="x" class="h-3 w-3"></i> Cancel');
            lucide.createIcons();
        });
    });

    // Auto-expand the first card
    let firstHeader = cardsWrapper.querySelector('[data-phase-toggle]');
    if (firstHeader) firstHeader.click();

    // Render reasoning trail (collapsible block below phase cards)
    if (reasoningTrail && Array.isArray(reasoningTrail) && reasoningTrail.length > 0) {
        let trailWrapper = document.createElement('div');
        trailWrapper.className = 'reasoning-trail mt-4';

        let stepsHtml = reasoningTrail.map(function(step) {
            let score = parseFloat(step.confidence) || 0;
            let label, badgeClass;
            if (score >= 0.8) {
                label = 'High';
                badgeClass = 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30';
            } else if (score >= 0.6) {
                label = 'Medium';
                badgeClass = 'bg-amber-500/10 text-amber-600 border-amber-500/30';
            } else {
                label = 'Low';
                badgeClass = 'bg-destructive/10 text-destructive border-destructive/30';
            }
            return '<div class="reasoning-step flex items-start gap-2 py-2 border-b border-border/30 last:border-0">' +
                '<span class="text-xs font-semibold text-primary whitespace-nowrap mt-0.5">' + DOMPurify.sanitize(step.phase || '') + '</span>' +
                '<span class="text-xs text-muted-foreground flex-1">' + DOMPurify.sanitize(step.summary || '') + '</span>' +
                '<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium border ' + badgeClass + ' whitespace-nowrap">' + label + '</span>' +
            '</div>';
        }).join('');

        let trailHtml =
            '<div class="reasoning-trail-toggle flex items-center gap-2 cursor-pointer select-none py-2" data-reasoning-toggle>' +
                '<i data-lucide="chevron-right" class="h-3.5 w-3.5 text-muted-foreground reasoning-chevron transition-transform"></i>' +
                '<span class="text-xs font-medium text-muted-foreground">Reasoning (' + reasoningTrail.length + ' steps)</span>' +
            '</div>' +
            '<div class="reasoning-trail-body hidden pl-5" data-reasoning-body>' +
                stepsHtml +
            '</div>';

        safeHTML(trailWrapper, trailHtml);
        container.appendChild(trailWrapper);

        // Wire toggle
        let toggleEl = trailWrapper.querySelector('[data-reasoning-toggle]');
        let bodyEl = trailWrapper.querySelector('[data-reasoning-body]');
        let chevronEl = trailWrapper.querySelector('.reasoning-chevron');
        if (toggleEl && bodyEl) {
            toggleEl.addEventListener('click', function() {
                let isHidden = bodyEl.classList.contains('hidden');
                if (isHidden) {
                    bodyEl.classList.remove('hidden');
                    if (chevronEl) chevronEl.style.transform = 'rotate(90deg)';
                } else {
                    bodyEl.classList.add('hidden');
                    if (chevronEl) chevronEl.style.transform = '';
                }
            });
        }
    }

    // Export row (hidden until all phases approved)
    let exportRow = document.createElement('div');
    exportRow.className = 'architect-export-row flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-border/50';
    exportRow.setAttribute('data-export-row', '');
    exportRow.style.display = 'none';

    let briefBtnHtml =
        '<button class="js-export-brief inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">' +
            '<i data-lucide="file-text" class="h-3 w-3"></i> Architecture Brief (PDF)</button>';
    let arbBtnHtml =
        '<button class="js-export-arb inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-accent transition-colors">' +
            '<i data-lucide="shield" class="h-3 w-3"></i> ARB Submission (PDF)</button>';
    let diagramLinkHtml =
        '<a class="js-export-diagram inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-input bg-background hover:bg-accent transition-colors" ' +
            'href="/archimate/composer/export?solution_id=' + (solutionId || '') + '&format=png" target="_blank">' +
            '<i data-lucide="image" class="h-3 w-3"></i> ArchiMate Diagram (PNG)</a>';

    safeHTML(exportRow, briefBtnHtml + arbBtnHtml + diagramLinkHtml);
    container.appendChild(exportRow);

    // Wire export-brief button
    let briefBtn = exportRow.querySelector('.js-export-brief');
    if (briefBtn) {
        briefBtn.addEventListener('click', function() {
            let solId = cardsWrapper.getAttribute('data-solution-id');
            briefBtn.disabled = true;
            safeHTML(briefBtn, '<i data-lucide="loader-2" class="h-3 w-3 animate-spin"></i> Generating...');
            fetch('/ai-chat/architect/export-brief', {
                method: 'POST',
                headers: csrfHeaders(),
                body: JSON.stringify({ solution_id: parseInt(solId) || 0, format: 'pdf' }),
            })
            .then(function(r) {
                if (r.ok) return r.blob();
                throw new Error('Export failed');
            })
            .then(function(blob) {
                let url = URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = 'architecture_brief_' + (solId || 'draft') + '.pdf';
                a.click();
                URL.revokeObjectURL(url);
                briefBtn.disabled = false;
                safeHTML(briefBtn, '<i data-lucide="file-text" class="h-3 w-3"></i> Architecture Brief (PDF)');
                lucide.createIcons();
            })
            .catch(function() {
                briefBtn.disabled = false;
                safeHTML(briefBtn, '<i data-lucide="file-text" class="h-3 w-3"></i> Architecture Brief (PDF)');
                lucide.createIcons();
            });
        });
    }

    // Wire ARB export button
    let arbBtn = exportRow.querySelector('.js-export-arb');
    if (arbBtn) {
        arbBtn.addEventListener('click', function() {
            let solId = cardsWrapper.getAttribute('data-solution-id');
            arbBtn.disabled = true;
            safeHTML(arbBtn, '<i data-lucide="loader-2" class="h-3 w-3 animate-spin"></i> Generating...');
            fetch('/ai-chat/architect/export-brief', {
                method: 'POST',
                headers: csrfHeaders(),
                body: JSON.stringify({ solution_id: parseInt(solId) || 0, format: 'arb' }),
            })
            .then(function(r) {
                if (r.ok) return r.blob();
                throw new Error('Export failed');
            })
            .then(function(blob) {
                let url = URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = 'arb_submission_' + (solId || 'draft') + '.pdf';
                a.click();
                URL.revokeObjectURL(url);
                arbBtn.disabled = false;
                safeHTML(arbBtn, '<i data-lucide="shield" class="h-3 w-3"></i> ARB Submission (PDF)');
                lucide.createIcons();
            })
            .catch(function() {
                arbBtn.disabled = false;
                safeHTML(arbBtn, '<i data-lucide="shield" class="h-3 w-3"></i> ARB Submission (PDF)');
                lucide.createIcons();
            });
        });
    }

    lucide.createIcons();
}

/**
 * Render ArchiMate element preview cards in chat messages.
 * Called when AI response contains archimate_elements array.
 */
function renderArchimatePreviewCards(container, elements, solutionId) {
    if (!elements || elements.length === 0) return;

    let wrapper = document.createElement('div');
    wrapper.className = 'mt-3 space-y-2';

    let byLayer = {};
    elements.forEach(function(el) {
        let layer = (el.layer || 'unknown').toLowerCase();
        if (!byLayer[layer]) byLayer[layer] = [];
        byLayer[layer].push(el);
    });

    let LAYER_LABELS = {
        business: 'Business', application: 'Application', technology: 'Technology',
        motivation: 'Motivation', strategy: 'Strategy', implementation: 'Implementation'
    };
    let LAYER_ACCENTS = {
        business: '#eab308', application: '#0284c7', technology: '#16a34a',
        motivation: '#7c3aed', strategy: '#db2777', implementation: '#ea580c'
    };

    Object.keys(byLayer).forEach(function(layer) {
        let section = document.createElement('div');
        section.className = 'flex flex-wrap gap-1.5 items-center';

        let layerBadge = document.createElement('span');
        layerBadge.className = 'text-[10px] font-semibold px-1.5 py-0.5 rounded-full text-primary-foreground';
        layerBadge.style.background = LAYER_ACCENTS[layer] || '#94a3b8';
        layerBadge.textContent = LAYER_LABELS[layer] || layer;
        section.appendChild(layerBadge);

        byLayer[layer].forEach(function(el) {
            let badge = document.createElement('span');
            badge.className = 'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border border-border bg-muted/50 text-foreground';
            badge.textContent = el.name + ' (' + (el.type || 'Unknown') + ')';
            section.appendChild(badge);
        });

        wrapper.appendChild(section);
    });

    if (solutionId) {
        let link = document.createElement('a');
        link.href = '/archimate/composer?solution_id=' + solutionId;
        link.className = 'inline-flex items-center gap-1.5 mt-2 text-xs text-primary hover:underline';
        link.target = '_blank';
        link.textContent = 'Open in Composer';
        let icon = document.createElement('i');
        icon.setAttribute('data-lucide', 'external-link');
        icon.className = 'w-3 h-3';
        link.prepend(icon);
        wrapper.appendChild(link);
    }

    container.appendChild(wrapper);
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function appendMessage(role, text, metadata) {
    hasConversationStarted = true;
    text = (text != null) ? String(text) : '';
    metadata = metadata || {};
    let isAi = role === 'ai';
    let div = document.createElement('div');
    div.className = 'flex gap-4 ' + (isAi ? '' : 'flex-row-reverse');

    let domainColor = (domainConfig[currentDomain] && domainConfig[currentDomain].color) || 'primary';
    let avatarGradient = getColorClass(domainColor, 'gradient');
    let domainIcon = (domainConfig[currentDomain] && domainConfig[currentDomain].icon) || 'bot';
    let avatar = isAi
        ? '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ' + avatarGradient + ' text-primary-foreground shadow-lg">' +
          '<i data-lucide="' + domainIcon + '" class="h-5 w-5"></i></div>'
        : '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">' +
          '<i data-lucide="user" class="h-5 w-5"></i></div>';

    let metadataDomainColor = metadata.domain ? ((domainConfig[metadata.domain] && domainConfig[metadata.domain].color) || 'blue') : 'blue';
    let badgeClass = getColorClass(metadataDomainColor, 'badge');
    let bubble;
    if (isAi) {
        let metaHtml = '';
        if (metadata.domain) {
            let domainName = (domainConfig[metadata.domain] && domainConfig[metadata.domain].name) || 'AI';
            metaHtml = '<div class="mb-2"><span class="px-2 py-1 ' + badgeClass + ' text-xs rounded-full font-medium">' +
                DOMPurify.sanitize(domainName) + '</span>';
            if (metadata.processing_time) {
                metaHtml += '<span class="ml-2 text-xs text-muted-foreground">' + parseInt(metadata.processing_time) + 'ms</span>';
            }
            metaHtml += '</div>';
        }
        // Build confidence badge if confidence > 0
        let confHtml = '';
        if (metadata.confidence && metadata.confidence > 0) {
            let confPct = Math.round(metadata.confidence * 100);
            let confClass = confPct >= 75 ? 'confidence-high' : confPct >= 50 ? 'confidence-medium' : 'confidence-low';
            let confTitle = confPct >= 75 ? 'High confidence' : confPct >= 50 ? 'Medium confidence' : 'Low confidence — verify this response';
            confHtml = '<span class="confidence-badge ' + confClass + '" title="' + confTitle + '">' +
                '<i data-lucide="bar-chart-2" class="conf-icon"></i>' +
                confPct + '%</span>';
        }
        if (metaHtml) {
            // Inject confidence badge into existing metaHtml div
            metaHtml = metaHtml.replace('</div>', confHtml + '</div>');
        } else if (confHtml) {
            metaHtml = '<div class="mb-2">' + confHtml + '</div>';
        }

        // Build action bar (copy + feedback)
        let msgId = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
        let actionBar = '<div class="msg-action-bar flex items-center gap-1 mt-2 pt-2 border-t border-border/40 opacity-0 group-hover:opacity-100 transition-opacity" data-msg-id="' + msgId + '">' +
            '<button class="js-copy-msg inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors" title="Copy message" aria-label="Copy message">' +
            '<i data-lucide="copy" class="h-3 w-3"></i></button>' +
            '<button class="js-feedback-up inline-flex h-6 px-2 items-center justify-center rounded text-muted-foreground hover:text-emerald-600 hover:bg-emerald-50 transition-colors text-xs gap-1" title="Helpful" aria-label="Helpful">' +
            '<i data-lucide="thumbs-up" class="h-3 w-3"></i></button>' +
            '<button class="js-feedback-down inline-flex h-6 px-2 items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors text-xs gap-1" title="Not helpful" aria-label="Not helpful">' +
            '<i data-lucide="thumbs-down" class="h-3 w-3"></i></button>' +
            '</div>';

        bubble = '<div class="rounded-xl bg-muted/50 p-4 text-sm prose dark:prose-invert max-w-3xl group">' +
            metaHtml +
            '<div class="message-content" data-raw-text="' + text.replace(/"/g, '&quot;') + '">' + DOMPurify.sanitize(marked.parse(text)) + '</div>' +
            actionBar +
            '</div>';
    } else {
        bubble = '<div class="rounded-xl bg-primary text-primary-foreground p-4 text-sm max-w-3xl">' +
            '<div class="message-content">' + DOMPurify.sanitize(text) + '</div></div>';
    }

    safeHTML(div, avatar + bubble);
    // Wire copy button
    let copyBtn = div.querySelector('.js-copy-msg');
    if (copyBtn) {
        let rawText = text;
        copyBtn.addEventListener('click', function() { copyMessageText(rawText, this); });
    }
    // Wire feedback buttons
    let feedbackDomain = metadata.domain || currentDomain;
    let feedbackPersona = currentPersona;
    let upBtn = div.querySelector('.js-feedback-up');
    let downBtn = div.querySelector('.js-feedback-down');
    if (upBtn) upBtn.addEventListener('click', function() { submitFeedback('up', feedbackDomain, feedbackPersona, text, this, downBtn); });
    if (downBtn) downBtn.addEventListener('click', function() { submitFeedback('down', feedbackDomain, feedbackPersona, text, this, upBtn); });
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    lucide.createIcons();
    // A95-019: Render structured phase cards for architect analysis responses
    if (isAi && metadata.phases && typeof metadata.phases === 'object') {
        let contentDiv = div.querySelector('.message-content');
        if (contentDiv) {
            renderArchitectPhaseCards(contentDiv, metadata.phases, metadata.solution_id, metadata.reasoning_trail);
        }
    }
    // Render ArchiMate preview cards if response contains elements (COMP-004)
    if (isAi && metadata.archimate_elements && metadata.archimate_elements.length > 0) {
        let contentDiv = div.querySelector('.message-content');
        if (contentDiv) {
            let solutionId = metadata.solution_id || (contextElement && contextElement.type === 'solution' ? contextElement.id : null);
            renderArchimatePreviewCards(contentDiv, metadata.archimate_elements, solutionId);
        }
        /* ENT-121: any AI response with architecture elements gets an Open in Composer button */
        let elements = metadata.archimate_elements;
        let relationships = metadata.archimate_relationships || [];
        try {
            sessionStorage.setItem('composer_prefill', JSON.stringify({
                elements: elements,
                relationships: relationships,
                app_name: metadata.app_name || metadata.application_name || null,
                timestamp: Date.now(),
            }));
        } catch (_) {}
        let btnDiv = document.createElement('div');
        btnDiv.className = 'flex justify-end mt-2 ml-12';
        let btn = document.createElement('a');
        btn.href = '/archimate/composer?prefill=1';
        btn.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors';
        btn.setAttribute('data-ent121-composer-link', '');
        let hint = elements.length + ' element' + (elements.length !== 1 ? 's' : '');
        if (relationships.length > 0) hint += ', ' + relationships.length + ' relationship' + (relationships.length !== 1 ? 's' : '');
        safeHTML(btn, '<i data-lucide="layout-template" class="h-3 w-3"></i> Open in Composer (' + hint + ')');
        btnDiv.appendChild(btn);
        messagesContainer.appendChild(btnDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (window.lucide) lucide.createIcons();
    }
    // Render follow-up question chips (AIC-FOLLOWUP)
    if (isAi && metadata.follow_up_questions && metadata.follow_up_questions.length > 0) {
        let chipsDiv = document.createElement('div');
        chipsDiv.className = 'flex flex-wrap gap-2 px-4 pb-2 ml-12';
        metadata.follow_up_questions.forEach(function(q) {
            let chip = document.createElement('button');
            chip.className = 'follow-up-chip text-xs px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 hover:bg-primary/15 text-primary transition-colors text-left leading-snug';
            chip.textContent = q;
            chip.addEventListener('click', function() {
                userInput.value = q;
                userInput.focus();
                autoResizeTextarea();
            });
            chipsDiv.appendChild(chip);
        });
        messagesContainer.appendChild(chipsDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function appendSystemMessage(text, type) {
    type = type || 'info';
    let div = document.createElement('div');
    div.className = 'flex justify-center my-3';

    let bgColor = type === 'info' ? 'bg-primary/5 text-primary border-primary/20 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800' :
                  type === 'error' ? 'bg-destructive/5 text-destructive border-destructive/20 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800' :
                  'bg-muted/50 text-muted-foreground border-border';

    let icon = type === 'info' ? 'info' : type === 'error' ? 'alert-circle' : 'check';

    safeHTML(div, '<div class="px-3 py-2 rounded-lg text-xs ' + bgColor + ' border flex items-center gap-2 max-w-md">' +
        '<i data-lucide="' + icon + '" class="h-3 w-3 shrink-0"></i> ' +
        DOMPurify.sanitize(text) + '</div>');

    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    lucide.createIcons();
}

// ==========================================================================
// Message Actions: Copy & Feedback (AIC-COPY, AIC-FEEDBACK)
// ==========================================================================

function copyMessageText(text, btn) {
    navigator.clipboard.writeText(text).then(function() {
        let icon = btn.querySelector('i');
        if (icon) { icon.setAttribute('data-lucide', 'check'); lucide.createIcons(); }
        setTimeout(function() {
            if (icon) { icon.setAttribute('data-lucide', 'copy'); lucide.createIcons(); }
        }, 2000);
    }).catch(function() {
        // Fallback for non-HTTPS
        let ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    });
}

async function submitFeedback(rating, domain, persona, messageText, clickedBtn, otherBtn) {
    // Visual state immediately
    clickedBtn.classList.add(rating === 'up' ? 'text-emerald-600' : 'text-destructive');
    clickedBtn.classList.remove('text-muted-foreground');
    if (otherBtn) { otherBtn.disabled = true; otherBtn.classList.add('opacity-40'); }
    clickedBtn.disabled = true;

    try {
        await fetch('/ai-chat/feedback', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({
                rating: rating,
                domain: domain,
                persona: persona,
                message_text: messageText.substring(0, 500)
            })
        });
    } catch (e) { /* non-critical */ }
}

// ==========================================================================
// Form Submission
// ==========================================================================

chatForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    let message = userInput.value.trim();
    if (!message) return;
    if (isSending) return;
    if (commandHints) commandHints.classList.add('hidden');
    if (detectCreateSolutionIntent(message)) {
        openCreateSolutionModalWithMessage(message);
        userInput.value = '';
        return;
    }
    // ENT-122: ArchiMate freeform NL intent — route to dedicated generation endpoint
    if (detectArchimateFreeformIntent(message)) {
        await handleArchimateFreeform(message);
        return;
    }
    // A95-013: diagram creation intent — if a solution is in context, create diagram immediately
    if (detectDiagramIntent(message)) {
        let solId = (contextElement && contextElement.type === 'solution') ? contextElement.id : null;
        let solName = (contextElement && contextElement.type === 'solution') ? contextElement.name : null;
        if (solId) {
            userInput.value = '';
            appendMessage('user', message);
            createSolutionDiagramFromChat(solId, solName);
            return;
        }
        // No solution in context — fall through to normal NL handling
    }
    if (getRateLimitRemaining() <= 0) {
        let minsLeft = Math.max(1, Math.ceil((rateLimitResetAt - Date.now()) / 60000));
        appendMessage('ai', '**Rate limit reached** \u2014 30 AI requests per hour. Please wait approximately ' + minsLeft + ' minute' + (minsLeft !== 1 ? 's' : '') + ' before sending another message.', { domain: currentDomain });
        return;
    }
    isSending = true;
    _setSendingUI(true);
    incrementRateLimit();
    userInput.value = '';
    userInput.style.height = 'auto';
    _clearAttachedImage(); // ENT-085: clear attached image after sending

    let timestamp = new Date().toISOString();
    chatHistory.push({ role: 'user', content: message, timestamp: timestamp });
    appendMessage('user', message);

    if (message.startsWith('/')) {
        let handled = await handleChatCommand(message);
        if (handled) {
            isSending = false;
            _setSendingUI(false);
            return;
        }
    }

    let loadingId = appendLoadingMessage();
    let startTime = performance.now();

    // Use streaming if supported (AIC-STREAM)
    let useStreaming = true;

    if (useStreaming) {
        try {
            await sendMessageStreaming(message, loadingId, startTime);
        } catch (streamErr) {
            // Clean up original loading indicator (streaming may have already removed it)
            // then add a fresh one so the user has visual feedback during the fallback call.
            removeLoadingMessage(loadingId);
            let fallbackLoadingId = appendLoadingMessage();
            try {
                await sendMessageFallback(message, fallbackLoadingId, startTime);
            } catch (e2) {
                removeLoadingMessage(fallbackLoadingId);
                appendMessage('ai', '**Network Error**\n\nCould not reach the server. Please check your connection and try again.\n\n`' + e2.message + '`', { domain: currentDomain });
            }
        }
        isSending = false;
        _setSendingUI(false);
        return;
    }

    try {
        let legacyPayload = {
            message: message,
            domain: currentDomain,
            template_name: templateSelector.value || 'General Inquiry',
            element_id: selectedElementIdInput.value ? parseInt(selectedElementIdInput.value) : null,
            context_type: contextElement ? contextElement.type : null,
            persona: currentPersona || null,
            model: modelSelector ? modelSelector.value : null
        };
        // ENT-085: attach image data for vision analysis
        if (_attachedImageData) {
            legacyPayload.image_data = _attachedImageData;
            legacyPayload.image_media_type = _attachedImageType || 'image/png';
        }
        let response = await fetch('/ai-chat/message', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify(legacyPayload)
        });

        // Guard against HTML error pages (login redirect, CSRF failure, 500)
        let contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            removeLoadingMessage(loadingId);
            if (response.status === 401 || response.status === 400) {
                appendMessage('ai', '**Session Expired**\n\nYour session has expired. Please [refresh the page](javascript:location.reload()) to log in again.', { domain: currentDomain });
            } else {
                appendMessage('ai', '**Server Error**\n\nThe server returned an unexpected response (HTTP ' + response.status + '). Please try again or contact your administrator.', { domain: currentDomain });
            }
            isSending = false;
            _setSendingUI(false);
            return;
        }
        let data = await response.json();
        let endTime = performance.now();
        let processingTime = Math.round(endTime - startTime);

        removeLoadingMessage(loadingId);

        if (data.error) {
            let errorTitle = 'Error';
            if (data.error_type === 'auth') errorTitle = 'Authentication Error';
            else if (data.error_type === 'connection') errorTitle = 'Connection Error';
            else if (data.error_type === 'timeout') errorTitle = 'Timeout Error';
            else if (data.error_type === 'rate_limit') errorTitle = 'Rate Limit Reached';
            else if (data.error_type === 'model_error') errorTitle = 'Model Error';

            appendMessage('ai', '**' + errorTitle + '**\n\n' + data.error + '\n\n*Try again or switch to a different model.*', { domain: currentDomain });
        } else {
            // Show actions taken by the agent (tool use results)
            if (data.actions_taken && data.actions_taken.length > 0) {
                const actionLines = data.actions_taken.map(function(a) {
                    return '✓ ' + (a.message || a.tool);
                }).join('\n');
                appendSystemMessage('**Actions completed:**\n' + actionLines, 'success');
            }

            // Show pending approvals (approve-tier tools waiting for confirmation)
            if (data.pending_approvals && data.pending_approvals.length > 0) {
                data.pending_approvals.forEach(function(pa) {
                    _renderApprovalPrompt(pa);
                });
            }

            chatHistory.push({
                role: 'ai',
                content: data.response,
                timestamp: timestamp,
                metadata: data.metadata
            });
            appendMessage('ai', data.response, {
                domain: data.domain,
                processing_time: (data.metadata && data.metadata.processing_time) || processingTime,
                confidence: data.confidence,
                follow_up_questions: data.follow_up_questions || [],
                archimate_elements: data.archimate_elements || (data.metadata && data.metadata.archimate_elements) || [],
                solution_id: data.solution_id || (data.metadata && data.metadata.solution_id) || null
            });
            // Auto-save every 5 AI responses (AIC-AUTOSAVE)
            let aiMsgCount = chatHistory.filter(function(m) { return m.role === 'ai' || m.role === 'assistant'; }).length;
            if (aiMsgCount > 0 && aiMsgCount % 5 === 0) {
                saveCurrentSession().catch(function() {});
            }
        }
    } catch (error) {
        removeLoadingMessage(loadingId);
        appendMessage('ai', '**Network Error**\n\nCould not reach the server. Please check your connection and try again.\n\n`' + error.message + '`', { domain: currentDomain });
    } finally {
        isSending = false;
        _setSendingUI(false);
    }
});

// ==========================================================================
// Agent Approval Prompts
// Rendered when the AI queues a destructive/significant action for confirmation.
// ==========================================================================

function _renderApprovalPrompt(pa) {
    const container = document.querySelector('#chat-messages');
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'approval-prompt border border-amber-400 rounded-lg p-4 my-3 bg-amber-50 dark:bg-amber-900/20';
    card.dataset.approvalId = pa.approval_id;
    card.innerHTML = `
        <div class="flex items-start gap-3">
            <span class="text-amber-500 text-lg">⚠️</span>
            <div class="flex-1">
                <p class="font-semibold text-amber-800 dark:text-amber-200 text-sm mb-1">Action requires your approval</p>
                <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">${DOMPurify.sanitize(pa.summary || pa.tool)}</p>
                <div class="flex gap-2">
                    <button class="btn-approve px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs rounded font-medium transition-colors">
                        Confirm
                    </button>
                    <button class="btn-reject px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs rounded font-medium transition-colors">
                        Cancel
                    </button>
                </div>
                <p class="approval-status text-xs mt-2 text-gray-500 hidden"></p>
            </div>
        </div>`;

    // Confirm handler
    card.querySelector('.btn-approve').addEventListener('click', async function() {
        this.disabled = true;
        card.querySelector('.btn-reject').disabled = true;
        const statusEl = card.querySelector('.approval-status');
        statusEl.textContent = 'Executing…';
        statusEl.classList.remove('hidden');
        try {
            const resp = await fetch('/ai-chat/tools/approve/' + pa.approval_id, {
                method: 'POST',
                headers: { 'X-CSRFToken': _getCsrfToken(), 'Content-Type': 'application/json' },
            });
            const result = await resp.json();
            if (result.success) {
                statusEl.textContent = '✓ ' + (result.message || 'Done');
                statusEl.className = 'approval-status text-xs mt-2 text-green-600 font-medium';
                card.className = card.className.replace('border-amber-400 bg-amber-50 dark:bg-amber-900/20', 'border-green-400 bg-green-50 dark:bg-green-900/20');
            } else {
                statusEl.textContent = '✗ ' + (result.error || 'Failed');
                statusEl.className = 'approval-status text-xs mt-2 text-red-600 font-medium';
            }
        } catch (e) {
            statusEl.textContent = 'Network error — please try again.';
            statusEl.classList.remove('hidden');
        }
    });

    // Cancel handler
    card.querySelector('.btn-reject').addEventListener('click', async function() {
        this.disabled = true;
        card.querySelector('.btn-approve').disabled = true;
        try {
            await fetch('/ai-chat/tools/reject/' + pa.approval_id, {
                method: 'POST',
                headers: { 'X-CSRFToken': _getCsrfToken() },
            });
        } catch (_) {}
        const statusEl = card.querySelector('.approval-status');
        statusEl.textContent = 'Cancelled.';
        statusEl.classList.remove('hidden');
        card.style.opacity = '0.5';
    });

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
}

function _getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// ==========================================================================
// Streaming Message Sender (AIC-STREAM)
// ==========================================================================

async function sendMessageStreaming(message, loadingId, startTime) {
    let payloadObj = {
        message: message,
        domain: currentDomain,
        template_name: templateSelector.value || 'General Inquiry',
        element_id: selectedElementIdInput.value ? parseInt(selectedElementIdInput.value) : null,
        context_type: contextElement ? contextElement.type : null,
        persona: currentPersona || null,
        model: modelSelector ? modelSelector.value : null
    };
    // ENT-085: attach image data for vision analysis
    if (_attachedImageData) {
        payloadObj.image_data = _attachedImageData;
        payloadObj.image_media_type = _attachedImageType || 'image/png';
    }
    let streamPayload = JSON.stringify(payloadObj);

    _activeAbortController = new AbortController();
    if (_activeAbortTimer) clearTimeout(_activeAbortTimer);
    _activeAbortTimer = setTimeout(function() { if (_activeAbortController) _activeAbortController.abort('timeout'); }, 45000);
    let response = await fetch('/ai-chat/message/stream', {
        method: 'POST',
        headers: csrfHeaders(),
        body: streamPayload,
        signal: _activeAbortController.signal
    });

    if (!response.ok) {
        throw new Error('Stream endpoint returned ' + response.status);
    }

    removeLoadingMessage(loadingId);

    // Create streaming message bubble
    let domainColor = (domainConfig[currentDomain] && domainConfig[currentDomain].color) || 'primary';
    let avatarGradient = getColorClass(domainColor, 'gradient');
    let domainIcon = (domainConfig[currentDomain] && domainConfig[currentDomain].icon) || 'bot';
    let streamDiv = document.createElement('div');
    streamDiv.className = 'flex gap-4';
    let streamMsgId = 'stream-' + Date.now();
    safeHTML(streamDiv,
        '<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ' + avatarGradient + ' text-primary-foreground shadow-lg">' +
        '<i data-lucide="' + domainIcon + '" class="h-5 w-5"></i></div>' +
        '<div class="rounded-xl bg-muted/50 p-4 text-sm prose dark:prose-invert max-w-3xl" id="' + streamMsgId + '">' +
        '<div class="stream-cursor">▍</div>' +
        '</div>');
    messagesContainer.appendChild(streamDiv);
    lucide.createIcons();

    let reader = response.body.getReader();
    let decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let metaData = { domain: currentDomain };
    let streamContainer = document.getElementById(streamMsgId);

    while (true) {
        let chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        let lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (!line) continue;
            if (line.startsWith('data: ')) {
                let data = line.slice(6);
                if (data === '[DONE]') continue;
                try {
                    let parsed = JSON.parse(data);
                    if (parsed.action === 'redirect' && parsed.url) {
                        // AIF-003: create_solution intent — redirect to solution detail
                        streamDiv.remove();
                        appendSystemMessage('Solution architecture created — redirecting...', 'info');
                        setTimeout(function() { window.location.href = parsed.url; }, 1200);
                        return;
                    } else if (parsed.token) {
                        fullText += parsed.token;
                        if (streamContainer) {
                            safeHTML(streamContainer, DOMPurify.sanitize(marked.parse(fullText)) + '<span class="stream-cursor animate-pulse">▍</span>');
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        }
                    } else if (parsed.done) {
                        metaData = {
                            domain: parsed.domain || currentDomain,
                            confidence: parsed.confidence,
                            follow_up_questions: parsed.follow_up_questions || [],
                            processing_time: Math.round(performance.now() - startTime),
                            phases: parsed.phases || null,
                            reasoning_trail: parsed.reasoning_trail || null,
                            solution_id: parsed.solution_id || null,
                            archimate_elements: parsed.archimate_elements || null
                        };
                        if (streamContainer) {
                            safeHTML(streamContainer, DOMPurify.sanitize(marked.parse(fullText)));
                        }
                    } else if (parsed.error) {
                        throw new Error(parsed.error);
                    }
                } catch (parseErr) {
                    // Re-throw intentional errors (e.g. parsed.error throw above).
                    // Swallow only JSON SyntaxErrors from malformed SSE lines.
                    if (!(parseErr instanceof SyntaxError)) {
                        throw parseErr;
                    }
                }
            }
        }
    }

    // Replace streaming bubble with proper appendMessage output
    streamDiv.remove();

    // If streaming produced no text, fall back to non-streaming endpoint
    if (!fullText || !fullText.trim()) {
        throw new Error('Streaming produced empty response — falling back to non-streaming');
    }

    hasConversationStarted = true;
    chatHistory.push({ role: 'ai', content: fullText, timestamp: new Date().toISOString(), metadata: metaData });
    appendMessage('ai', fullText, metaData);

    let aiMsgCount = chatHistory.filter(function(m) { return m.role === 'ai' || m.role === 'assistant'; }).length;
    if (aiMsgCount > 0 && aiMsgCount % 5 === 0) {
        saveCurrentSession().catch(function() {});
    }
}

async function sendMessageFallback(message, loadingId, startTime) {
    _activeAbortController = new AbortController();
    if (_activeAbortTimer) clearTimeout(_activeAbortTimer);
    _activeAbortTimer = setTimeout(function() { if (_activeAbortController) _activeAbortController.abort('timeout'); }, 30000);
    let fbPayload = {
        message: message,
        domain: currentDomain,
        template_name: templateSelector.value || 'General Inquiry',
        element_id: selectedElementIdInput.value ? parseInt(selectedElementIdInput.value) : null,
        context_type: contextElement ? contextElement.type : null,
        persona: currentPersona || null,
        model: modelSelector ? modelSelector.value : null
    };
    // ENT-085: attach image data for vision analysis
    if (_attachedImageData) {
        fbPayload.image_data = _attachedImageData;
        fbPayload.image_media_type = _attachedImageType || 'image/png';
    }
    let response = await fetch('/ai-chat/message', {
        method: 'POST',
        headers: csrfHeaders(),
        signal: _activeAbortController.signal,
        body: JSON.stringify(fbPayload)
    });
    // Guard against HTML error pages (login redirect, CSRF failure, 500)
    let fbContentType = response.headers.get('content-type') || '';
    if (!fbContentType.includes('application/json')) {
        if (response.status === 401 || response.status === 400) {
            throw new Error('Session expired. Please refresh the page to log in again.');
        }
        throw new Error('Server returned an unexpected response (HTTP ' + response.status + '). Please try again.');
    }
    let data = await response.json();
    let processingTime = Math.round(performance.now() - startTime);
    removeLoadingMessage(loadingId);
    if (data.error) {
        appendMessage('ai', '**Error**\n\n' + data.error, { domain: currentDomain });
    } else {
        chatHistory.push({ role: 'ai', content: data.response, timestamp: new Date().toISOString(), metadata: data.metadata });
        appendMessage('ai', data.response, {
            domain: data.domain,
            processing_time: (data.metadata && data.metadata.processing_time) || processingTime,
            confidence: data.confidence,
            follow_up_questions: data.follow_up_questions || [],
            archimate_elements: data.archimate_elements || (data.metadata && data.metadata.archimate_elements) || [],
            solution_id: data.solution_id || (data.metadata && data.metadata.solution_id) || null,
            phases: data.phases || (data.metadata && data.metadata.phases) || null,
            reasoning_trail: data.reasoning_trail || (data.metadata && data.metadata.reasoning_trail) || null
        });
    }
}

// ==========================================================================
// Document Upload Panel Toggle
// ==========================================================================

function toggleDocumentUploadPanel() {
    let panel = document.getElementById('document-upload-panel');
    if (panel) {
        panel.classList.toggle('hidden');
        if (!panel.classList.contains('hidden') && typeof lucide !== 'undefined') {
            setTimeout(function() { lucide.createIcons(); }, 100);
        }
    }
}

// ==========================================================================
// Mobile Sidebar Toggle
// ==========================================================================

function toggleSidebar() {
    let sidebar = document.getElementById('context-sidebar');
    let backdrop = document.getElementById('sidebar-backdrop');
    let isOpen = !sidebar.classList.contains('-translate-x-full');
    if (isOpen) {
        sidebar.classList.add('-translate-x-full');
        backdrop.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
    } else {
        sidebar.classList.remove('-translate-x-full');
        backdrop.classList.remove('hidden');
        document.body.classList.add('overflow-hidden');
        sidebar.style.height = '100%';
    }
    setTimeout(function() { lucide.createIcons(); }, 100);
}

// ==========================================================================
// Sidebar Tab Management
// ==========================================================================

function switchSidebarTab(tab) {
    ['context', 'query', 'alerts', 'history'].forEach(function(panelName) {
        let panel = document.getElementById('panel-' + panelName);
        if (panel) { panel.classList.add('hidden'); panel.style.display = ''; }
    });
    document.querySelectorAll('[id^="tab-"]').forEach(function(t) {
        t.classList.remove('border-b-2', 'border-primary', 'text-primary');
        t.classList.add('text-muted-foreground');
    });
    let selectedPanel = document.getElementById('panel-' + tab);
    let selectedTab = document.getElementById('tab-' + tab);
    if (selectedPanel) { selectedPanel.classList.remove('hidden'); selectedPanel.style.display = 'flex'; }
    if (selectedTab) {
        selectedTab.classList.add('border-b-2', 'border-primary', 'text-primary');
        selectedTab.classList.remove('text-muted-foreground');
    }
    if (tab === 'alerts') { loadRecommendations(); }
    if (tab === 'history') { loadSessionList(); }
    lucide.createIcons();
}

// AIC-110: Session history loading
async function loadSessionList() {
    let container = document.getElementById('session-list');
    if (!container) return;
    safeHTML(container, '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i></div>');
    lucide.createIcons();
    try {
        let resp = await fetch('/ai-chat/sessions', { headers: csrfHeaders() });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        let data = await resp.json();
        let sessions = data.sessions || [];
        if (sessions.length === 0) {
            safeHTML(container, '<p class="text-xs text-muted-foreground text-center py-8">No saved sessions yet. Sessions auto-save every 5 messages.</p>');
            return;
        }
        let html = '';
        sessions.forEach(function(s) {
            let name = s.name || s.session_name || 'Untitled session';
            let date = s.created_at || s.timestamp || '';
            if (date) { try { date = new Date(date).toLocaleDateString(); } catch(e) {} }
            let msgCount = (s.messages || s.history || []).length;
            html += '<button onclick="loadSession(\'' + (s.session_id || s.id || '') + '\')" class="w-full text-left p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors">'
                  + '<div class="font-medium text-xs truncate">' + DOMPurify.sanitize(name) + '</div>'
                  + '<div class="text-[10px] text-muted-foreground mt-1">' + DOMPurify.sanitize(date) + (msgCount ? ' · ' + msgCount + ' messages' : '') + '</div>'
                  + '</button>';
        });
        safeHTML(container, html);
    } catch (err) {
        safeHTML(container, '<p class="text-xs text-destructive text-center py-4">Failed to load sessions: ' + DOMPurify.sanitize(err.message) + '</p>');
    }
    lucide.createIcons();
}

async function loadSession(sessionId) {
    if (!sessionId) return;
    try {
        let resp = await fetch(`/ai-chat/session/${encodeURIComponent(sessionId)}`, { headers: csrfHeaders() });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        let data = await resp.json();
        if (data.success === false) { appendSystemMessage('Could not load session: ' + (data.error || 'Unknown error'), 'warning'); return; }
        // Restore chat history
        let messages = data.messages || data.history || [];
        if (messages.length === 0) { appendSystemMessage('Session is empty', 'info'); return; }
        chatHistory = messages;
        hasConversationStarted = true;
        // Re-render all messages
        let messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) safeHTML(messagesContainer, '');
        messages.forEach(function(msg) {
            let role = msg.role || 'user';
            let content = msg.content || msg.text || '';
            if (role === 'ai' || role === 'assistant') {
                appendMessage('ai', content, { domain: msg.domain || currentDomain });
            } else {
                appendMessage('user', content);
            }
        });
        appendSystemMessage('Session restored (' + messages.length + ' messages)', 'info');
        // Switch back to chat
        switchSidebarTab('context');
    } catch (err) {
        appendSystemMessage('Failed to load session: ' + err.message, 'warning');
    }
}

// ==========================================================================
// Natural Language Query Functions
// ==========================================================================

async function executeNLQuery() {
    let input = document.getElementById('nl-query-input');
    let query = input.value.trim();
    if (!query) return;
    let resultsDiv = document.getElementById('nl-query-results');
    let resultsList = document.getElementById('nl-results-list');
    let explanationDiv = document.getElementById('nl-query-explanation');
    let countSpan = document.getElementById('nl-result-count');
    resultsDiv.classList.remove('hidden');
    safeHTML(resultsList, '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i></div>');
    lucide.createIcons();
    try {
        let response = await fetch('/ai-chat/nl-query', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ query: query, persona: currentPersona })
        });
        let data = await response.json();
        if (data.success) {
            countSpan.textContent = data.result_count + ' found';
            explanationDiv.textContent = data.explanation || '';
            explanationDiv.classList.toggle('hidden', !data.explanation);
            if (data.results && data.results.length > 0) {
                safeHTML(resultsList, DOMPurify.sanitize(data.results.map(function(item) {
                    return '<div class="p-2 border rounded-lg hover:bg-accent/50 cursor-pointer js-entity-result" ' +
                        'data-entity-type="' + DOMPurify.sanitize(item.entity_type) + '" ' +
                        'data-entity-id="' + (parseInt(item.id) || 0) + '" ' +
                        'data-entity-name="' + DOMPurify.sanitize(item.name) + '">' +
                        '<div class="flex items-center justify-between mb-1">' +
                        '<span class="text-sm font-medium">' + DOMPurify.sanitize(item.name) + '</span>' +
                        '<span class="text-xs bg-muted px-1.5 py-0.5 rounded">' + DOMPurify.sanitize(item.entity_type) + '</span>' +
                        '</div>' +
                        '<p class="text-xs text-muted-foreground line-clamp-2">' + DOMPurify.sanitize(item.description || item.status || '') + '</p>' +
                        '</div>';
                }).join('')));
                resultsList.querySelectorAll('.js-entity-result').forEach(function(el) {
                    el.addEventListener('click', function() {
                        showEntityInChat(this.dataset.entityType, parseInt(this.dataset.entityId), this.dataset.entityName);
                    });
                });
            } else {
                safeHTML(resultsList, '<p class="text-sm text-muted-foreground text-center py-4">No results found</p>');
            }
        } else {
            safeHTML(resultsList, '');
            let errP = document.createElement('p');
            errP.className = 'text-sm text-destructive text-center py-4';
            errP.textContent = data.error || 'Query failed';
            resultsList.appendChild(errP);
        }
    } catch (error) {
        safeHTML(resultsList, '');
        let errP2 = document.createElement('p');
        errP2.className = 'text-sm text-destructive text-center py-4';
        errP2.textContent = 'Error: ' + error.message;
        resultsList.appendChild(errP2);
    }
    lucide.createIcons();
}

function runQuickQuery(query) {
    switchSidebarTab('query');
    document.getElementById('nl-query-input').value = query;
    const structuredRoute = QUICK_QUERY_ROUTES && QUICK_QUERY_ROUTES[query];
    if (structuredRoute) {
        fetchStructuredQueryResult(query, structuredRoute);
        return;
    }
    setTimeout(function() { executeNLQuery(); }, 150);
}

async function fetchStructuredQueryResult(label, apiUrl) {
    try {
        appendMessage('ai', '<em>Fetching structured results for: ' + DOMPurify.sanitize(label) + '…</em>');
        const resp = await fetch(apiUrl, { headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' } });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        const tableHtml = renderQueryResultTable(data, label);
        appendMessage('ai', tableHtml);
    } catch (err) {
        appendMessage('ai', '<em>Could not load structured results. Falling back to AI query.</em>');
        executeNLQuery(label);
    }
}

function renderQueryResultTable(data, queryLabel) {
    const items = Array.isArray(data) ? data : (data.items || data.results || data.data || []);
    if (!items.length) return '<em>No results found.</em>';
    const keys = Object.keys(items[0]);
    const headers = keys.map(function(k) {
        return '<th class="px-3 py-1 text-left text-xs font-medium text-muted-foreground">' + DOMPurify.sanitize(k) + '</th>';
    }).join('');
    const rows = items.slice(0, 50).map(function(row) {
        return '<tr>' + keys.map(function(k) {
            return '<td class="px-3 py-1 text-sm border-t">' + DOMPurify.sanitize(String(row[k] != null ? row[k] : '')) + '</td>';
        }).join('') + '</tr>';
    }).join('');
    const dashboardUrl = (queryLabel && DASHBOARD_ROUTES && DASHBOARD_ROUTES[queryLabel]) ? DASHBOARD_ROUTES[queryLabel] : null;
    const ctaHtml = dashboardUrl
        ? '<div class="mt-2 text-right"><a href="' + dashboardUrl + '" class="inline-flex items-center gap-1 text-xs text-primary underline hover:no-underline" aria-label="View full results in dashboard">View in dashboard →</a></div>'
        : '';
    return '<div class="overflow-x-auto rounded border"><table class="w-full text-sm"><thead><tr>' + headers + '</tr></thead><tbody>' + rows + '</tbody></table></div>' + ctaHtml;
}

// ==========================================================================
// Entity Interaction
// ==========================================================================

function showEntityInChat(entityType, entityId, entityName) {
    let safeEntityName = DOMPurify.sanitize(entityName);
    let safeEntityType = DOMPurify.sanitize(entityType);
    let modalEl = document.getElementById('entity-action-modal');
    if (!modalEl) return;

    let titleEl = document.getElementById('entity-action-title');
    let subtitleEl = document.getElementById('entity-action-subtitle');
    let viewDescEl = document.getElementById('entity-action-view-desc');
    if (titleEl) titleEl.textContent = safeEntityName;
    if (subtitleEl) subtitleEl.textContent = safeEntityType + ' \u2022 ID: ' + parseInt(entityId);
    if (viewDescEl) viewDescEl.textContent = 'Open the full ' + safeEntityType.toLowerCase() + ' page';

    // Clone buttons to remove stale event listeners from a previous call
    ['entity-action-view', 'entity-action-ask', 'entity-action-context'].forEach(function(btnId) {
        let btn = document.getElementById(btnId);
        if (btn) { let clone = btn.cloneNode(true); btn.parentNode.replaceChild(clone, btn); }
    });

    let viewBtn = document.getElementById('entity-action-view');
    let askBtn = document.getElementById('entity-action-ask');
    let contextBtn = document.getElementById('entity-action-context');
    if (viewBtn) viewBtn.addEventListener('click', function() { navigateToEntity(entityType, entityId); _closeEntityActionModal(); });
    if (askBtn) askBtn.addEventListener('click', function() { askAIAboutEntity(entityType, entityId, entityName); _closeEntityActionModal(); });
    if (contextBtn) contextBtn.addEventListener('click', function() { addToContext(entityType, entityId, entityName); _closeEntityActionModal(); });
    if (typeof lucide !== 'undefined') lucide.createIcons();

    modalEl.classList.remove('hidden');
    _entityModalEscapeHandler = function(e) { if (e.key === 'Escape') _closeEntityActionModal(); };
    document.addEventListener('keydown', _entityModalEscapeHandler);
}

let _entityModalEscapeHandler = null;

function _closeEntityActionModal() {
    let modalEl = document.getElementById('entity-action-modal');
    if (modalEl) modalEl.classList.add('hidden');
    if (_entityModalEscapeHandler) { document.removeEventListener('keydown', _entityModalEscapeHandler); _entityModalEscapeHandler = null; }
}

function navigateToEntity(entityType, entityId) {
    let urlMap = {
        'Application': '/applications/', 'application': '/applications/',
        'Capability': '/capabilities/', 'capability': '/capabilities/',
        'Vendor': '/vendors/', 'vendor': '/vendors/',
        'Process': '/processes/', 'process': '/processes/',
        'Technology': '/technologies/', 'technology': '/technologies/'
    };
    window.open((urlMap[entityType] || '/applications/') + entityId, '_blank');
}

function askAIAboutEntity(entityType, entityId, entityName) {
    usePrompt('Analyze "' + entityName + '" (' + entityType + ', ID: ' + entityId + ').\n\nPlease provide:\n1. Overview and current status\n2. Key relationships and dependencies\n3. Risk assessment\n4. Improvement recommendations');
    chatForm.dispatchEvent(new Event('submit'));
}

function addToContext(entityType, entityId, entityName) {
    selectedElementIdInput.value = entityId;
    contextElement = { id: entityId, type: entityType, name: entityName };
    appendSystemMessage('Context set: ' + entityName + ' (' + entityType + '). Try these commands:', 'info');
    // AIC-203: Show available commands as clickable chips
    let chipContainer = document.createElement('div');
    chipContainer.className = 'flex flex-wrap gap-1 mt-1 mb-2 ml-12';
    let commands = [
        { cmd: '/generate-archimate ' + entityId, label: 'Generate ArchiMate' },
        { cmd: '/map-apqc ' + entityId, label: 'Map APQC' },
        { cmd: 'Tell me about ' + entityName, label: 'Ask AI about this' },
    ];
    commands.forEach(function(c) {
        let chip = document.createElement('button');
        chip.className = 'text-[10px] px-2 py-1 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors';
        chip.textContent = c.label;
        chip.addEventListener('click', function() {
            let input = document.getElementById('chat-input') || document.querySelector('textarea[name="message"]');
            if (input) { input.value = c.cmd; input.focus(); }
        });
        chipContainer.appendChild(chip);
    });
    let messagesContainer = document.getElementById('chat-messages');
    if (messagesContainer) messagesContainer.appendChild(chipContainer);
}

// ==========================================================================
// Session Management
// ==========================================================================

function startNewChat() {
    chatHistory = [];
    hasConversationStarted = false;
    contextElement = null;
    selectedElementIdInput.value = '';
    try {
        fetch('/ai-chat/history/clear', { method: 'POST', headers: csrfHeaders() });
    } catch (e) { /* ignore */ }
    renderWelcomeScreen();
    appendSystemMessage('New conversation started', 'info');
}

async function saveCurrentSession() {
    if (chatHistory.length === 0) {
        appendSystemMessage('No conversation to save', 'info');
        return;
    }
    try {
        let response = await fetch('/ai-chat/session/save', {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify({ name: 'Session ' + new Date().toLocaleString(), history: chatHistory })
        });
        let data = await response.json();
        if (data.success) {
            appendSystemMessage('Session saved successfully', 'info');
        } else {
            appendSystemMessage('Could not save session: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        appendSystemMessage('Could not save session', 'error');
    }
}

// ==========================================================================
// Export Conversation (AIC-EXPORT)
// ==========================================================================

function exportConversation() {
    if (chatHistory.length === 0) {
        appendSystemMessage('No conversation to export', 'info');
        return;
    }
    let lines = [
        '# A.R.C.H.I.E. Architecture Chat Export',
        '**Exported:** ' + new Date().toLocaleString(),
        '**Domain:** ' + (domainConfig[currentDomain] && domainConfig[currentDomain].name || currentDomain),
        '**Persona:** ' + (personaConfig[currentPersona] && personaConfig[currentPersona].name || currentPersona || 'Not set'),
        '',
        '---',
        ''
    ];
    chatHistory.forEach(function(msg) {
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

function selectDomainAndPrompt(domain, samplePrompt) {
    domainSelector.value = domain;
    currentDomain = domain;
    sessionStorage.setItem('ai_chat_domain', currentDomain);
    updateDomainUI(domain);
    loadDomainContext(domain);
    updateTemplateOptions(domain);
    usePrompt(samplePrompt);
}

function askAboutRecommendation(title, description) {
    usePrompt('Help me implement this recommendation: "' + title + '"\n\nContext: ' + description + '\n\nPlease provide:\n1. Step-by-step implementation plan\n2. Key stakeholders to involve\n3. Potential challenges and mitigations\n4. Expected timeline and milestones');
    chatForm.dispatchEvent(new Event('submit'));
}

// ==========================================================================
// Recommendations and Alerts
// ==========================================================================

async function loadRecommendations(refresh) {
    refresh = refresh || false;
    let alertsList = document.getElementById('alerts-list');
    let recsContent = document.getElementById('recs-content');
    let healthScore = document.getElementById('health-score');
    let healthBar = document.getElementById('health-bar');
    let alertBadge = document.getElementById('alert-badge');

    safeHTML(alertsList, '<div class="text-center py-4"><i data-lucide="loader-2" class="h-5 w-5 animate-spin mx-auto"></i><p class="text-xs text-muted-foreground mt-2">Loading alerts...</p></div>');
    lucide.createIcons();

    let controller = new AbortController();
    let timeoutId = setTimeout(function() { controller.abort(); }, 15000);

    try {
        let response = await fetch(`/ai-chat/recommendations?persona=${currentPersona}&refresh=${refresh}`, { signal: controller.signal });
        clearTimeout(timeoutId);
        let data = await response.json();

        let score = data.health_score || 0;
        healthScore.textContent = score + '%';
        healthBar.style.width = score + '%';
        if (score >= 70) {
            healthScore.className = 'text-lg font-bold text-emerald-600';
            healthBar.className = 'bg-emerald-500 h-2 rounded-full transition-all';
        } else if (score >= 40) {
            healthScore.className = 'text-lg font-bold text-amber-600';
            healthBar.className = 'bg-amber-500 h-2 rounded-full transition-all';
        } else {
            healthScore.className = 'text-lg font-bold text-destructive';
            healthBar.className = 'bg-destructive h-2 rounded-full transition-all';
        }

        let criticalCount = ((data.summary && data.summary.critical_count) || 0) + ((data.summary && data.summary.high_count) || 0);
        if (criticalCount > 0) {
            alertBadge.textContent = criticalCount > 99 ? '99+' : criticalCount;
            alertBadge.classList.remove('hidden');
            alertBadge.style.display = 'flex';
        } else {
            alertBadge.classList.add('hidden');
            alertBadge.style.display = 'none';
        }

        if (data.alerts && data.alerts.length > 0) {
            safeHTML(alertsList, DOMPurify.sanitize(data.alerts.slice(0, 5).map(function(alert) {
                let actionLinks = '';
                if (alert.action_url) {
                    actionLinks += '<a href="' + DOMPurify.sanitize(alert.action_url) + '" class="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"><i data-lucide="external-link" class="h-3 w-3"></i>' + DOMPurify.sanitize(alert.action_label || 'Open') + '</a>';
                }
                if (alert.query) {
                    actionLinks += (actionLinks ? '<span class="text-muted-foreground mx-1">|</span>' : '') +
                        '<button class="text-xs text-primary hover:underline js-alert-query" data-query="' + DOMPurify.sanitize(alert.query) + '"><i data-lucide="search" class="h-3 w-3 inline"></i> Ask AI</button>';
                }
                if (alert.action && !alert.action_url) {
                    actionLinks += (actionLinks ? '<span class="text-muted-foreground mx-1">|</span>' : '') +
                        '<span class="text-xs text-muted-foreground italic">' + DOMPurify.sanitize(alert.action) + '</span>';
                }
                return '<div class="p-3 border rounded-lg mb-2 ' + getPriorityBorderClass(alert.priority) + '">' +
                    '<div class="flex items-start justify-between gap-2 mb-1">' +
                    '<span class="text-sm font-medium">' + DOMPurify.sanitize(alert.title) + '</span>' +
                    '<span class="text-xs px-1.5 py-0.5 rounded shrink-0 ' + getPriorityBadgeClass(alert.priority) + '">' + DOMPurify.sanitize(alert.priority) + '</span>' +
                    '</div>' +
                    '<p class="text-xs text-muted-foreground mb-2">' + DOMPurify.sanitize(alert.description) + '</p>' +
                    '<div class="flex items-center gap-1 flex-wrap">' + actionLinks + '</div>' +
                    '</div>';
            }).join('')));
            alertsList.querySelectorAll('.js-alert-query').forEach(function(btn) {
                btn.addEventListener('click', function() { runQuickQuery(this.dataset.query); });
            });
        } else {
            safeHTML(alertsList, '<div class="text-center py-4"><i data-lucide="check-circle" class="h-5 w-5 mx-auto mb-2 text-emerald-500"></i><p class="text-sm text-muted-foreground">No active alerts</p></div>');
        }

        if (data.recommendations && data.recommendations.length > 0) {
            safeHTML(recsContent, DOMPurify.sanitize(data.recommendations.slice(0, 3).map(function(rec, idx) {
                let detailsHtml = '';
                if (rec.steps && rec.steps.length > 0) {
                    detailsHtml += '<div class="mt-2 text-[11px] text-muted-foreground space-y-1">';
                    if (rec.timeline) detailsHtml += '<div><strong>Timeline:</strong> ' + DOMPurify.sanitize(rec.timeline) + ' · <strong>Effort:</strong> ' + DOMPurify.sanitize(rec.effort || 'TBD') + '</div>';
                    detailsHtml += '<div class="font-medium mt-1">Steps:</div><ol class="list-decimal pl-4 space-y-0.5">';
                    rec.steps.forEach(function(s) { detailsHtml += '<li>' + DOMPurify.sanitize(s) + '</li>'; });
                    detailsHtml += '</ol>';
                    if (rec.benefits && rec.benefits.length > 0) {
                        detailsHtml += '<div class="font-medium mt-1">Benefits:</div><ul class="list-disc pl-4">';
                        rec.benefits.forEach(function(b) { detailsHtml += '<li>' + DOMPurify.sanitize(b) + '</li>'; });
                        detailsHtml += '</ul>';
                    }
                    detailsHtml += '</div>';
                }
                return '<div class="p-2 border rounded-lg mb-2 bg-gradient-to-r from-primary/5 to-transparent">' +
                    '<div class="flex items-center justify-between mb-1">' +
                    '<span class="text-xs font-medium">' + DOMPurify.sanitize(rec.title) + '</span>' +
                    '<span class="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">' + (parseInt(rec.impact_score) || 0) + '%</span>' +
                    '</div>' +
                    '<p class="text-[11px] text-muted-foreground">' + DOMPurify.sanitize((rec.description || '').substring(0, 100)) + '</p>' +
                    detailsHtml +
                    '<div class="flex gap-2 mt-2">' +
                    '<button class="text-[10px] text-primary hover:underline js-rec-item" data-rec-title="' + DOMPurify.sanitize(rec.title) + '" data-rec-desc="' + DOMPurify.sanitize((rec.description || '').substring(0, 200)) + '"><i data-lucide="message-circle" class="h-3 w-3 inline"></i> Ask AI to help</button>' +
                    '</div></div>';
            }).join('')));
            recsContent.querySelectorAll('.js-rec-item').forEach(function(el) {
                el.addEventListener('click', function() {
                    askAboutRecommendation(this.dataset.recTitle, this.dataset.recDesc);
                });
            });
        } else {
            safeHTML(recsContent, '<p class="text-xs text-muted-foreground">No recommendations at this time.</p>');
        }
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            safeHTML(alertsList, '<div class="text-center py-4"><p class="text-sm text-muted-foreground">Loading timed out.</p><button class="js-retry-alerts text-xs text-primary hover:underline mt-1">Retry</button></div>');
        } else {
            safeHTML(alertsList, '<div class="text-center py-4"><p class="text-sm text-muted-foreground">Could not load alerts.</p><button class="js-retry-alerts text-xs text-primary hover:underline mt-1">Retry</button></div>');
        }
        healthScore.textContent = '--';
        healthBar.style.width = '0%';
        let retryBtn = alertsList.querySelector('.js-retry-alerts');
        if (retryBtn) retryBtn.addEventListener('click', function() { loadRecommendations(true); });
    }
    lucide.createIcons();
}

function refreshRecommendations() { loadRecommendations(true); }

function getPriorityBorderClass(priority) {
    return { 'critical': 'border-l-4 border-l-red-500', 'high': 'border-l-4 border-l-orange-500', 'medium': 'border-l-4 border-l-yellow-500', 'low': 'border-l-4 border-l-blue-500' }[priority] || '';
}

function getPriorityBadgeClass(priority) {
    return { 'critical': 'bg-destructive/10 text-destructive', 'high': 'bg-orange-100 text-orange-800', 'medium': 'bg-amber-500/10 text-amber-700', 'low': 'bg-primary/10 text-primary/90' }[priority] || 'bg-muted text-foreground'; // token-migration-ok
}

// ==========================================================================
// Document Upload Event Listeners
// ==========================================================================

window.addEventListener('add-document-analysis', function(e) {
    let detail = e.detail || {};
    appendMessage('ai',
        '**Document Analyzed: ' + (detail.filename || 'Unknown') + '**\n\n' +
        (detail.summary || 'Document has been analyzed.') + '\n\n' +
        '**Results:**\n' +
        '- Elements Found: ' + (detail.elementsFound || 0) + '\n' +
        '- Elements Created: ' + (detail.elementsCreated || 0) + '\n' +
        '- Confidence: ' + (detail.confidence || 'Medium'),
        { domain: currentDomain });
});

window.addEventListener('show-notification', function(e) {
    let detail = e.detail || {};
    appendSystemMessage(detail.message || 'Notification', detail.type || 'info');
});

window.addEventListener('ask-question', function(e) {
    let detail = e.detail || {};
    if (detail.question) {
        userInput.value = detail.question;
        if (detail.context) { userInput.value += '\n\n[Context: ' + detail.context + ']'; }
        chatForm.dispatchEvent(new Event('submit'));
    }
});

window.addEventListener('link-to-entity', function(e) {
    let detail = e.detail || {};
    appendSystemMessage('Linking document to ' + detail.entityType + ': ' + detail.entityName, 'info');
});

window.addEventListener('create-entity', function(e) {
    let detail = e.detail || {};
    appendSystemMessage('Creating new ' + detail.entityType + ': ' + ((detail.entityData && detail.entityData.name) || 'Unknown'), 'info');
});

// ==========================================================================
// Chat History Persistence
// ==========================================================================

async function loadChatHistory() {
    try {
        let response = await fetch('/ai-chat/history');
        if (!response.ok) return false;
        let data = await response.json();
        if (!data.success || !data.history || data.history.length === 0) return false;
        safeHTML(messagesContainer, '');
        data.history.forEach(function(msg) {
            let role = msg.role === 'assistant' ? 'ai' : msg.role;
            appendMessage(role, msg.content, { domain: msg.domain || currentDomain });
            chatHistory.push({ role: role, content: msg.content, timestamp: msg.timestamp, metadata: msg.metadata || {} });
        });
        hasConversationStarted = true;
        let separator = document.createElement('div');
        separator.className = 'flex items-center gap-3 my-4 px-4';
        safeHTML(separator,
            '<div class="flex-1 border-t border-border"></div>' +
            '<span class="text-xs text-muted-foreground">Previous conversation restored</span>' +
            '<div class="flex-1 border-t border-border"></div>');
        messagesContainer.appendChild(separator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return true;
    } catch (error) {
        console.warn('Could not load chat history:', error);
        return false;
    }
}

// ==========================================================================
// Welcome Screen
// ==========================================================================

function renderWelcomeScreen() {
    let userName = window.userDisplayName || '';
    let greeting = userName ? 'Welcome, ' + DOMPurify.sanitize(userName) : 'Welcome to A.R.C.H.I.E.';
    let personaName = '';
    let samplePrompts = [];
    if (currentPersona && personaConfig[currentPersona]) {
        personaName = personaConfig[currentPersona].name || '';
        samplePrompts = personaConfig[currentPersona].sample_prompts || [];
    }

    safeHTML(messagesContainer, '');

    // Hero section
    let heroDiv = document.createElement('div');
    heroDiv.className = 'max-w-3xl mx-auto w-full';
    safeHTML(heroDiv,
        '<div class="text-center mb-8 pt-4">' +
        '<div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground mx-auto mb-4 shadow-lg">' +
        '<i data-lucide="bot" class="h-8 w-8"></i></div>' +
        '<h2 class="text-xl font-semibold mb-1">' + greeting + '</h2>' +
        '<p class="text-sm text-muted-foreground">What architecture activity would you like to perform?</p>' +
        (personaName ? '<div class="mt-2 inline-flex items-center gap-1.5 px-3 py-1 bg-primary/10 text-primary rounded-full text-xs font-medium"><i data-lucide="user" class="h-3 w-3"></i>' + DOMPurify.sanitize(personaName) + '</div>' : '') +
        '</div>');
    messagesContainer.appendChild(heroDiv);

    // Quick Action Cards
    let actionsDiv = document.createElement('div');
    actionsDiv.className = 'max-w-3xl mx-auto w-full mb-6';
    safeHTML(actionsDiv,
        '<h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 px-1">Quick Actions</h3>' +
        '<div class="grid grid-cols-2 lg:grid-cols-3 gap-3" id="quick-actions-grid"></div>');
    messagesContainer.appendChild(actionsDiv);

    let quickActions = [
        { icon: 'layers', color: 'blue', label: 'Generate ArchiMate', desc: 'Create ArchiMate 3.2 elements from applications', action: 'archimate' },
        { icon: 'search', color: 'orange', label: 'Run Gap Analysis', desc: 'Identify gaps in your architecture landscape', action: 'gap' },
        { icon: 'building-2', color: 'purple', label: 'Map to APQC', desc: 'Map applications to APQC process framework', action: 'apqc' },
        { icon: 'briefcase', color: 'teal', label: 'Discover Vendors', desc: 'Find vendors for specific capabilities', action: 'vendors' },
        { icon: 'upload-cloud', color: 'indigo', label: 'Analyze Document', desc: 'Upload and extract architecture elements', action: 'upload' },
        { icon: 'database', color: 'green', label: 'Query Portfolio', desc: 'Ask questions about your data in plain English', action: 'query' }
    ];

    let grid = actionsDiv.querySelector('#quick-actions-grid');
    quickActions.forEach(function(qa) {
        let card = document.createElement('button');
        card.className = 'quick-action-card flex flex-col items-start gap-2 p-4 rounded-xl bg-card border hover:border-primary/30 text-left group';
        safeHTML(card,
            '<div class="h-10 w-10 rounded-lg ' + getColorClass(qa.color, 'iconBg') + ' flex items-center justify-center group-hover:scale-110 transition-transform">' +
            '<i data-lucide="' + qa.icon + '" class="h-5 w-5 ' + getColorClass(qa.color, 'iconText') + '"></i></div>' +
            '<div>' +
            '<span class="text-sm font-medium block leading-tight">' + qa.label + '</span>' +
            '<span class="text-xs text-muted-foreground leading-tight">' + qa.desc + '</span>' +
            '</div>');
        card.addEventListener('click', function() { handleQuickAction(qa.action); });
        grid.appendChild(card);
    });

    // Conversation Starters
    if (samplePrompts.length > 0) {
        let startersDiv = document.createElement('div');
        startersDiv.className = 'max-w-3xl mx-auto w-full mb-4';
        safeHTML(startersDiv,
            '<h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 px-1">Suggested for ' + DOMPurify.sanitize(personaName || 'you') + '</h3>' +
            '<div class="grid grid-cols-1 sm:grid-cols-2 gap-2" id="starter-prompts"></div>');
        messagesContainer.appendChild(startersDiv);

        let starterGrid = startersDiv.querySelector('#starter-prompts');
        samplePrompts.forEach(function(prompt) {
            let chip = document.createElement('button');
            chip.className = 'prompt-chip flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 hover:border-primary/20 text-left transition-all group';
            safeHTML(chip,
                '<i data-lucide="message-square" class="h-4 w-4 text-primary mt-0.5 shrink-0 group-hover:scale-110 transition-transform"></i>' +
                '<span class="text-sm text-foreground leading-snug">' + DOMPurify.sanitize(prompt) + '</span>');
            chip.addEventListener('click', function() {
                usePrompt(prompt);
                chatForm.dispatchEvent(new Event('submit'));
            });
            starterGrid.appendChild(chip);
        });
    }

    lucide.createIcons();
}

function handleQuickAction(action) {
    if (action === 'archimate') {
        selectDomainAndPrompt('architecture', '');
        handleGenerateArchimate('');
    } else if (action === 'gap') {
        selectDomainAndPrompt('gap_analysis', '');
        handleGapAnalysis('capability');
    } else if (action === 'apqc') {
        selectDomainAndPrompt('business_capability', '');
        handleMapApqc('');
    } else if (action === 'vendors') {
        selectDomainAndPrompt('vendor_intelligence', '');
        handleDiscoverVendors('');
    } else if (action === 'upload') {
        toggleDocumentUploadPanel();
    } else if (action === 'query') {
        switchSidebarTab('query');
        document.getElementById('nl-query-input').focus();
    }
}

// ==========================================================================
// Initialize
// ==========================================================================

document.addEventListener('DOMContentLoaded', function() {
    if (currentDomain && domainSelector) domainSelector.value = currentDomain;
    if (currentPersona && personaSelector) personaSelector.value = currentPersona;

    updateDomainUI(currentDomain);
    loadDomainContext(currentDomain);
    updateTemplateOptions(currentDomain);
    loadAvailableModels();

    // Populate persona selector dynamically from window.personaConfig (AIC-PERSONA-SYNC)
    if (personaSelector && Object.keys(personaConfig).length > 0) {
        let currentVal = personaSelector.value;
        safeHTML(personaSelector, '<option value="">Select Role</option>');
        Object.keys(personaConfig).forEach(function(key) {
            let cfg = personaConfig[key];
            let option = document.createElement('option');
            option.value = key;
            option.textContent = cfg.name || key;
            if (key === currentPersona || key === currentVal) option.selected = true;
            personaSelector.appendChild(option);
        });
    }

    if (currentPersona && personaConfig[currentPersona]) {
        updatePersonaUI(currentPersona);
    }

    loadRecommendations();
    updateRateLimitUI();
    _initImageAttachment(); // ENT-085: wire up image attach button
    renderQuickQueryChips(); // A95-001: populate quick-query chips from QUICK_QUERIES config

    // Keyboard handlers
    let nlQueryInput = document.getElementById('nl-query-input');
    if (nlQueryInput) {
        nlQueryInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') executeNLQuery();
        });
    }
    if (userInput) {
        userInput.addEventListener('keydown', handleEnter);
        userInput.addEventListener('input', handleInputChange);
    }

    // Command hint buttons
    document.querySelectorAll('.js-cmd-hint').forEach(function(btn) {
        btn.addEventListener('click', function() {
            userInput.value = this.dataset.cmd + ' ';
            userInput.focus();
            if (commandHints) commandHints.classList.add('hidden');
        });
    });

    // Create solution from brief — open modal and handle form
    let createSolBtn = document.getElementById('ai-chat-create-solution-btn');
    if (createSolBtn) createSolBtn.addEventListener('click', openCreateSolutionModal);
    let createSolCancel = document.getElementById('ai-chat-create-solution-cancel');
    if (createSolCancel) createSolCancel.addEventListener('click', closeCreateSolutionModal);
    let createSolForm = document.getElementById('ai-chat-create-solution-form');
    if (createSolForm) {
        createSolForm.addEventListener('submit', function(e) {
            e.preventDefault();
            let titleEl = document.getElementById('ai-chat-solution-title');
            let briefEl = document.getElementById('ai-chat-solution-brief');
            let statusEl = document.getElementById('ai-chat-create-solution-status');
            let submitBtn = document.getElementById('ai-chat-create-solution-submit');
            let title = (titleEl && titleEl.value) ? titleEl.value.trim() : '';
            let brief = (briefEl && briefEl.value) ? briefEl.value.trim() : '';
            if (!title || !brief) return;
            if (submitBtn) submitBtn.disabled = true;
            if (statusEl) { statusEl.classList.remove('hidden'); statusEl.textContent = 'Creating solution and generating draft…'; }
            fetch('/solutions/create-with-draft', {
                method: 'POST',
                headers: csrfHeaders(),
                body: JSON.stringify({ title: title, brief: brief })
            }).then(function(resp) { return resp.json().then(function(data) { return { ok: resp.ok, data: data }; }, function() { return { ok: false, data: {} }; }); })
              .then(function(r) {
                  if (submitBtn) submitBtn.disabled = false;
                  if (r.ok && r.data.redirect) {
                      window.location.href = r.data.redirect;
                      return;
                  }
                  if (statusEl) statusEl.textContent = 'Error: ' + (r.data.error || r.data.message || 'Unknown error');
              })
              .catch(function() {
                  if (submitBtn) submitBtn.disabled = false;
                  if (statusEl) statusEl.textContent = 'Request failed. Please try again.';
              });
        });
    }

    // Load history or show welcome
    loadChatHistory().then(function(hasHistory) {
        if (!hasHistory) {
            renderWelcomeScreen();
        }
        lucide.createIcons();

        // A95-013: Auto-load context from URL params (element_id + context_type)
        // Must run after history load to avoid being overwritten by session restore.
        let params = new URLSearchParams(window.location.search);
        let urlElementId = params.get('element_id');
        let urlContextType = params.get('context_type');
        // AIC-019: fallback to short-form 'id' and 'context' params when long-form are absent
        if (!urlElementId) {
            urlElementId = params.get('id');
        }
        if (!urlContextType) {
            urlContextType = params.get('context');
        }
        if (urlElementId && urlContextType) {
            contextElement = { id: parseInt(urlElementId, 10), type: urlContextType, name: null };
            if (selectedElementIdInput) selectedElementIdInput.value = urlElementId;
        }
    });
});

// ==========================================================================
// ENT-122: ArchiMate natural language intent detection and freeform handler
// ==========================================================================

const ARCHIMATE_NL_PATTERNS = [
  /\b(generate|create|draw|design|build|make)\s+(an?\s+)?archimate\b/i,
  /\barchimate\s+(diagram|model|view|for|of)\b/i,
  /\b(draw|design|create)\s+an?\s+architecture\s+diagram\s+(for|of|showing)\b/i,
  /\b(model|diagram)\s+(this|the)\s+(system|solution|application)\s+(in\s+)?archimate\b/i,
];

function detectArchimateFreeformIntent(text) {
  return ARCHIMATE_NL_PATTERNS.some(function(p) { return p.test(text); });
}
window.detectArchimateFreeformIntent = detectArchimateFreeformIntent;

async function handleArchimateFreeform(description) {
  isSending = true;
  _setSendingUI(true);
  incrementRateLimit();
  userInput.value = '';
  userInput.style.height = 'auto';
  _clearAttachedImage();

  chatHistory.push({ role: 'user', content: description, timestamp: new Date().toISOString() });
  appendMessage('user', description);
  let loadingId = appendLoadingMessage();

  try {
    let resp = await fetch('/ai-chat/chat/generate-archimate-description', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfHeaders()),
      body: JSON.stringify({ description: description }),
    });
    let data = await resp.json();
    removeLoadingMessage(loadingId);

    if (data.success && data.elements && data.elements.length > 0) {
      let summary = '## ArchiMate Diagram — ' + DOMPurify.sanitize(data.model_name || 'Generated Architecture') + '\n\n';
      summary += data.elements.map(function(e) {
        return '- **' + e.type + '**: ' + e.name + (e.description ? ' — ' + e.description : '');
      }).join('\n');
      if (data.relationships && data.relationships.length > 0) {
        summary += '\n\n**Relationships:** ' + data.relationships.length + ' wired';
      }
      appendMessage('ai', summary, {
        archimate_elements: data.elements,
        archimate_relationships: data.relationships || [],
      });
    } else {
      let errMsg = (data && data.error) ? data.error : 'No elements generated. Try a more detailed description.';
      appendMessage('ai', '\u26A0\uFE0F ' + errMsg);
    }
  } catch (err) {
    removeLoadingMessage(loadingId);
    console.error('ENT-122: handleArchimateFreeform error:', err);
    appendMessage('ai', 'ArchiMate generation failed. Please try again.');
  } finally {
    isSending = false;
    _setSendingUI(false);
  }
}

// ==========================================================================
// A95-013: Diagram creation intent detection and handler
// ==========================================================================

const DIAGRAM_INTENT_PATTERNS = [
  /\b(create|generate|make|draw|build|show(\s+me)?)\s+(a\s+)?(solution\s+)?(architecture\s+)?diagram\b/i,
  /\barchitecture\s+diagram\b/i,
  /\bvisualiz[ez]/i,
  /\bopen\s+(in\s+)?composer\b/i,
  /\bdiagram\s+(for|of|showing)\b/i,
];

function detectDiagramIntent(text) {
  return DIAGRAM_INTENT_PATTERNS.some(function(p) { return p.test(text); });
}
window.detectDiagramIntent = detectDiagramIntent;

async function createSolutionDiagramFromChat(solutionId, solutionName) {
  try {
    let loadingMsg = 'Creating architecture diagram for ' + (solutionName || 'solution') + '\u2026';
    appendMessage('ai', loadingMsg);

    let payload = { solution_id: solutionId };
    if (solutionName) payload.solution_name = solutionName;

    let resp = await fetch('/ai-chat/chat/create-solution-diagram', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfHeaders()),
      body: JSON.stringify(payload),
    });
    let data = await resp.json();
    if (data.success && data.redirect_url) {
      appendMessage('ai', '\u2705 ' + (data.message || 'Diagram created. Opening composer\u2026'));
      setTimeout(function() { window.location.href = data.redirect_url; }, 1200);
    } else {
      appendMessage('ai', 'Could not create diagram: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    console.error('createSolutionDiagramFromChat error:', err);
    appendMessage('ai', 'Diagram creation failed. Please try again.');
  }
}
window.createSolutionDiagramFromChat = createSolutionDiagramFromChat;

// ==========================================================================
// Expose functions for template event handlers
// ==========================================================================

window.toggleSidebar = toggleSidebar;
window.switchSidebarTab = switchSidebarTab;
window.executeNLQuery = executeNLQuery;
window.runQuickQuery = runQuickQuery;
window.fetchStructuredQueryResult = fetchStructuredQueryResult;
window.renderQueryResultTable = renderQueryResultTable;
window.refreshRecommendations = refreshRecommendations;
window.toggleDocumentUploadPanel = toggleDocumentUploadPanel;
window.selectDomainAndPrompt = selectDomainAndPrompt;
window.selectContext = selectContext;
window.handleEnter = handleEnter;
window.startNewChat = startNewChat;
window.saveCurrentSession = saveCurrentSession;

// ==========================================================================
// Create solution from brief — AI chat can create solutions (same backend as list)
// ==========================================================================

let _createSolutionModalEscapeHandler;
function openCreateSolutionModal() {
    openCreateSolutionModalWithMessage('');
}
/** Pre-fill the create-solution modal with a message (e.g. from natural language). */
function openCreateSolutionModalWithMessage(message) {
    let modal = document.getElementById('ai-chat-create-solution-modal');
    if (modal) modal.classList.remove('hidden');
    let titleEl = document.getElementById('ai-chat-solution-title');
    let briefEl = document.getElementById('ai-chat-solution-brief');
    let brief = (typeof message === 'string' && message.trim()) ? message.trim() : '';
    if (briefEl) briefEl.value = brief;
    let suggestedTitle = suggestTitleFromCreateSolutionMessage(brief);
    if (titleEl) titleEl.value = suggestedTitle;
    let status = document.getElementById('ai-chat-create-solution-status');
    if (status) { status.classList.add('hidden'); status.textContent = ''; }
    _createSolutionModalEscapeHandler = function(e) { if (e.key === 'Escape') closeCreateSolutionModal(); };
    document.addEventListener('keydown', _createSolutionModalEscapeHandler);
}
function suggestTitleFromCreateSolutionMessage(text) {
    if (!text || !text.length) return '';
    let lower = text.toLowerCase();
    let patterns = [
        /^(?:create|create a)\s+(?:a\s+)?solution\s+for\s+(.+)/i,
        /^new\s+solution\s*[:\-]?\s*(.+)/i,
        /^I\s+need\s+(?:a\s+)?(?:new\s+)?solution\s+(?:for|about)\s+(.+)/i,
        /^(?:I'd like to|I would like to)\s+create\s+(?:a\s+)?solution\s+(?:for\s+)?(.+)/i,
    ];
    for (let i = 0; i < patterns.length; i++) {
        let m = text.match(patterns[i]);
        if (m && m[1]) {
            let rest = m[1].trim();
            let firstLine = rest.split(/\r?\n/)[0].trim();
            return (firstLine.length > 80) ? firstLine.substring(0, 77) + '...' : firstLine;
        }
    }
    let firstLine = text.split(/\r?\n/)[0].trim();
    return (firstLine.length > 80) ? firstLine.substring(0, 77) + '...' : firstLine;
}
function detectCreateSolutionIntent(message) {
    if (!message || typeof message !== 'string') return false;
    let t = message.trim().toLowerCase();
    if (t.length < 10) return false;
    let patterns = [
        /create\s+(?:a\s+)?solution\s+for/i,
        /create\s+(?:a\s+)?solution\s+about/i,
        /new\s+solution\s*[:\-]?/i,
        /I\s+need\s+(?:a\s+)?(?:new\s+)?solution\s+(?:for|about)/i,
        /I\s+want\s+to\s+create\s+(?:a\s+)?solution/i,
        /I'd like to\s+create\s+(?:a\s+)?solution/i,
        /^\/create-?solution\b/i
    ];
    return patterns.some(function(p) { return p.test(t); });
}
function closeCreateSolutionModal() {
    let modal = document.getElementById('ai-chat-create-solution-modal');
    if (modal) modal.classList.add('hidden');
    if (_createSolutionModalEscapeHandler) document.removeEventListener('keydown', _createSolutionModalEscapeHandler);
}
window.openCreateSolutionModal = openCreateSolutionModal;
window.openCreateSolutionModalWithMessage = openCreateSolutionModalWithMessage;
window.closeCreateSolutionModal = closeCreateSolutionModal;
window.detectCreateSolutionIntent = detectCreateSolutionIntent;

// ==========================================================================
// A95-007: Vendor apply — one-click apply discover-vendors result
// ==========================================================================

function applyVendorResult(vendorName, solutionId) {
    let url = solutionId
        ? '/solutions/' + encodeURIComponent(solutionId) + '/vendors?suggest=' + encodeURIComponent(vendorName)
        : '/vendors?search=' + encodeURIComponent(vendorName);
    window.location.href = url;
}
window.applyVendorResult = applyVendorResult;

function injectVendorApplyButtons(containerEl, solutionId) {
    let vendorCards = containerEl.querySelectorAll('[data-vendor-name]');
    vendorCards.forEach(function(card) {
        let vName = card.dataset.vendorName;
        if (!card.querySelector('.apply-vendor-btn')) {
            let btn = document.createElement('button');
            btn.className = 'apply-vendor-btn inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 mt-1';
            btn.setAttribute('type', 'button');
            btn.setAttribute('aria-label', 'Apply ' + vName + ' to solution');
            btn.textContent = 'Apply to solution';
            btn.onclick = function() { applyVendorResult(vName, solutionId || ''); };
            card.appendChild(btn);
        }
    });
}
window.injectVendorApplyButtons = injectVendorApplyButtons;
