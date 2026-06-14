/** Architecture Assistant - External JavaScript
 * Extracted from app/templates/architecture_assistant/index.html
 * Uses window.__APP_CONFIG__ bridge for Jinja2 template values.
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

// AA-008: localStorage cache helpers with TTL (24h) and 2MB soft cap
let AA_CACHE_TTL_MS = 86400000; // 24 hours
let AA_CACHE_SIZE_CAP = 2 * 1024 * 1024; // 2MB

function saveCache(key, value) {
    let wrapper = { data: value, expires: Date.now() + AA_CACHE_TTL_MS };
    let serialized = JSON.stringify(wrapper);
    // Check total localStorage usage before writing
    try {
        let totalSize = 0;
        for (let i = 0; i < localStorage.length; i++) {
            let k = localStorage.key(i);
            totalSize += (localStorage.getItem(k) || '').length;
        }
        // If over cap, clear stale architecture_assistant entries first
        if (totalSize + serialized.length > AA_CACHE_SIZE_CAP) {
            let existing = localStorage.getItem(key);
            if (existing) {
                try {
                    let parsed = JSON.parse(existing);
                    if (parsed.expires && parsed.expires < Date.now()) {
                        localStorage.removeItem(key);
                    }
                } catch (e) {
                    localStorage.removeItem(key);
                }
            }
        }
        localStorage.setItem(key, serialized);
    } catch (e) {
        console.warn('[AA] localStorage write failed:', e.message);
        // Quota exceeded — clear expired entries and retry once
        try {
            localStorage.removeItem(key);
            localStorage.setItem(key, serialized);
        } catch (retryErr) {
            console.warn('[AA] localStorage retry failed:', retryErr.message);
        }
    }
}

function readCache(key) {
    try {
        let raw = localStorage.getItem(key);
        if (!raw) return null;
        let wrapper = JSON.parse(raw);
        if (!wrapper.expires || wrapper.expires < Date.now()) {
            localStorage.removeItem(key);
            return null;
        }
        return wrapper.data;
    } catch (e) {
        localStorage.removeItem(key);
        return null;
    }
}

// Architecture Assistant Application
let ArchAssistant = {
    currentStep: 1,
    selectedCapability: null,
    gapAnalysis: null,
    solutionOptions: [],
    selectedOption: null,
    arbDraft: null,
    selectedCapabilities: [],
    businessContextId: null,
    roadmapData: null,

    // Open unified mapping modal for capability selection
    openMappingModal: function() {
        if (typeof openUnifiedMappingModalDiscovery === 'function') {
            openUnifiedMappingModalDiscovery({
                context: 'capability',
                allowTargetSelectOnly: true,
                onTargetSelected: function(target) {
                    // target: {id, name}
                    ArchAssistant.addSelectedCapability(String(target.id), target.name);
                }
            });
        } else {
            alert('Unified mapping modal is not available');
        }
    },

    addSelectedCapability: function(id, name) {
        if (!this.selectedCapabilities.find(function(c) { return String(c.id) === String(id); })) {
            this.selectedCapabilities.push({ id: String(id), name: name || ('Capability ' + id) });
            // Set primary selectedCapability for backward compatibility
            if (!this.selectedCapability) this.selectedCapability = this.selectedCapabilities[0];
            this.renderSelectedCapabilities();
            document.getElementById('btn-step-2-next').disabled = false;
            this._persistToServer('capabilities', { capabilities: this.selectedCapabilities });
        }
    },

    renderSelectedCapabilities: function() {
        let el = document.getElementById('selected-capabilities');
        if (!el) return;
        if (this.selectedCapabilities.length === 0) {
            el.textContent = 'No capabilities selected';
        } else {
            el.textContent = this.selectedCapabilities.length + ' selected: ' + this.selectedCapabilities.map(function(c) { return c.name; }).join(', ');
        }
    },

    // AWIZ-014: ArchiMate viewpoint selector shown before Step 1
    showViewpointSelector: function() {
        let self = this;
        self._selectedViewpoint = self._selectedViewpoint || null;

        fetch('/api/architecture-assistant/viewpoints')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                let viewpoints = data.viewpoints || [];
                if (!viewpoints.length) { self.goToStep(1); return; }

                let cards = viewpoints.map(function(vp) {
                    let key = vp.key || vp.id || vp.name || '';
                    return '<div data-viewpoint-key="' + key + '" class="cursor-pointer p-4 border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors">' +
                        '<div class="font-medium text-sm mb-1">' + vp.name + '</div>' +
                        '<div class="text-xs text-muted-foreground mb-2">' + (vp.description || '') + '</div>' +
                        '<div class="flex flex-wrap gap-1">' +
                        (vp.layers || []).map(function(l) { return '<span class="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">' + l + '</span>'; }).join('') +
                        '</div></div>';
                }).join('');

                let modal = document.createElement('div');
                modal.id = 'viewpoint-selector-modal';
                modal.className = 'fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4';
                safeHTML(modal,
                    '<div class="bg-background rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto shadow-xl">' +
                    '<div class="p-6 border-b border-border">' +
                    '<h2 class="text-lg font-semibold">Select ArchiMate Viewpoint</h2>' +
                    '<p class="text-sm text-muted-foreground mt-1">Choose the architectural lens for this session. Filters which elements are shown across all wizard steps.</p>' +
                    '</div>' +
                    '<div class="p-6 grid grid-cols-1 sm:grid-cols-2 gap-3">' + cards + '</div>' +
                    '<div class="p-4 border-t border-border flex justify-end">' +
                    '<button id="viewpoint-skip-btn" class="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">Skip — use Layered (default)</button>' +
                    '</div></div>');
                document.body.appendChild(modal);

                // Card click
                modal.addEventListener('click', function(e) {
                    let card = e.target.closest('[data-viewpoint-key]');
                    if (card) {
                        self._selectedViewpoint = card.dataset.viewpointKey;
                        modal.remove();
                        self.goToStep(1);
                    }
                });
                // Skip button
                let skipBtn = document.getElementById('viewpoint-skip-btn');
                if (skipBtn) {
                    skipBtn.addEventListener('click', function() {
                        self._selectedViewpoint = 'layered';
                        modal.remove();
                        self.goToStep(1);
                    });
                }
            })
            .catch(function() { self.goToStep(1); });
    },

    init: function() {
        this.setupEventListeners();
        this.showViewpointSelector();
        lucide.createIcons();

        // Saved sets dropdown toggle
        let loadBtn = document.getElementById('btn-load-sets');
        let dropdown = document.getElementById('saved-sets-dropdown');
        loadBtn && loadBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
            if (!dropdown.classList.contains('hidden')) {
                loadSavedSets(window.CURRENT_USER_ID || 0);
            }
        });
        // Close when clicking outside
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target) && !loadBtn.contains(e.target)) dropdown.classList.add('hidden');
        });

        let clearBtn = document.getElementById('btn-clear-sets');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                safeHTML(document.getElementById('saved-sets'), '');
                dropdown.classList.add('hidden');
            });
        }
    },

    getPayload: function(response) {
        if (!response || response.success === false) {
            return null;
        }
        return response.data !== undefined ? response.data : response;
    },

    persistAssistantData: function(solutionOptions) {
        if (!this.selectedCapability) return;
        // AA-008: Use saveCache with TTL and size cap instead of raw localStorage
        saveCache('architecture_assistant_data', {
            capability_id: this.selectedCapability.id,
            business_context_id: this.businessContextId || null,
            scope: {
                problem: this._scopeProblem || '',
                definition: this._scopeDefinition || '',
                stakeholders: this._scopeStakeholders || '',
                constraints: this._scopeConstraints || '',
                principles: this._scopePrinciples || []
            },
            gap_analysis: this.gapAnalysis || {},
            solution_options: solutionOptions || this.solutionOptions || [],
            roadmap_data: this.roadmapData || null
        });
    },

    _persistToServer: function(step, data) {
        let csrfToken = document.querySelector('meta[name="csrf-token"]');
        let headers = { 'Content-Type': 'application/json' };
        if (csrfToken) { headers['X-CSRFToken'] = csrfToken.getAttribute('content'); }
        fetch('/api/architecture-assistant/session/' + step, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        }).then(function(resp) {
            if (!resp.ok) {
                console.warn('[AA] session persist got HTTP ' + resp.status + ' for step ' + step);
            }
        }).catch(function(err) {
            console.warn('[AA] session persist failed for step ' + step + ':', err);
        });
    },

    showSectionError: function(containerId, message) {
        let container = document.getElementById(containerId);
        safeHTML(container,
            '<div class="col-span-full text-center py-8 text-destructive">' +
            '<i data-lucide="alert-circle" class="h-8 w-8 mx-auto mb-2"></i>' +
            '<p>' + message + '</p>' +
            '</div>');
        lucide.createIcons();
    },

    setupEventListeners: function() {
        let self = this;
        // Step navigation (6 steps)
        // Step 1: Define Scope
        document.getElementById('btn-step-1-next').addEventListener('click', function() { self.goToStep(2); });
        let skipBtn = document.getElementById('btn-step-1-skip');
        if (skipBtn) skipBtn.addEventListener('click', function() { self.goToStep(2); });
        // Step 2: Assess Capabilities
        document.getElementById('btn-step-2-back').addEventListener('click', function() { self.goToStep(1); });
        document.getElementById('btn-step-2-next').addEventListener('click', function() { self.goToStep(3); });
        // Step 3: Analyze Gaps
        document.getElementById('btn-step-3-back').addEventListener('click', function() { self.goToStep(2); });
        document.getElementById('btn-step-3-next').addEventListener('click', function() { self.goToStep(4); });
        // Step 4: Solution Options
        document.getElementById('btn-step-4-back').addEventListener('click', function() { self.goToStep(3); });
        document.getElementById('btn-step-4-next').addEventListener('click', function() { self.goToStep(5); });
        // Step 5: Implementation Roadmap
        document.getElementById('btn-step-5-back').addEventListener('click', function() { self.goToStep(4); });
        document.getElementById('btn-step-5-next').addEventListener('click', function() { self.goToStep(6); });
        // Step 6: ARB Draft
        document.getElementById('btn-step-6-back').addEventListener('click', function() { self.goToStep(5); });

        // Actions
        document.getElementById('btn-new-session').addEventListener('click', function() { self.newSession(); });
        let saveSetBtn = document.getElementById('btn-save-set');
        if (saveSetBtn) {
            saveSetBtn.addEventListener('click', function() { self.saveCurrentSet(window.CURRENT_USER_ID || 0); });
        }
        document.getElementById('btn-download-draft').addEventListener('click', function() { self.downloadDraft(); });
        document.getElementById('btn-submit-arb').addEventListener('click', function() { self.submitToARB(); });

        // Search
        document.getElementById('capability-search').addEventListener('input', function(e) { self.filterCapabilities(e.target.value); });

        // Selected capabilities container click to clear
        let sel = document.getElementById('selected-capabilities');
        if (sel) {
            sel.addEventListener('click', function() {
                let modalId = window.modalManager.createModal({
                    title: 'Clear Selection',
                    content: '<p class="text-sm text-muted-foreground">Clear selected capabilities?</p>',
                    size: 'small',
                    buttons: [
                        { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                        { text: 'Clear', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'clear', handler: function() { self.clearSelectedCapabilities(); } }
                    ]
                });
                window.modalManager.open(modalId);
            });
        }
    },

    // Fetch saved capability sets and render into UI dropdown
    loadSavedSets: async function(userId) {
        try {
            let res = await fetch('/api/architecture-assistant/capability-sets?user_id=' + userId);
            let data = await res.json();
            if (!data.success) return;
            let container = document.getElementById('saved-sets');
            safeHTML(container, '');
            data.data.forEach(function(s) {
                let btn = document.createElement('button');
                btn.className = 'px-2 py-1 text-sm hover:bg-muted rounded w-full text-left';
                btn.textContent = s.name;
                btn.onclick = function() {
                    ArchAssistant.selectedCapabilities = s.capability_ids.map(function(id) { return {id: id, name: 'Capability ' + id}; });
                    ArchAssistant.renderSelectedCapabilities();
                    ArchAssistant.loadGapAnalysis();
                };
                container.appendChild(btn);
            });
        } catch (e) {
            console.error('Error loading saved sets', e);
        }
    },

    // Save current selection as set
    saveCurrentSet: async function(userId) {
        let name = prompt('Name for capability set:');
        if (!name) return;
        let payload = { name: name, capability_ids: this.selectedCapabilities.map(function(c) { return c.id; }), user_id: userId };
        try {
            let res = await fetch('/api/architecture-assistant/capability-sets', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
            let data = await res.json();
            if (data.success) {
                alert('Saved');
                let dropdown = document.getElementById('saved-sets-dropdown');
                dropdown.classList.add('hidden');
                this.loadSavedSets(window.CURRENT_USER_ID || 0);
            } else {
                alert('Save failed: ' + (data.error || 'unknown'));
            }
        } catch (e) {
            console.error('Save set failed', e);
            alert('Save failed');
        }
    },

    // AA-010: Pagination state for capability list
    _capCurrentPage: 1,
    _capPerPage: 50,
    _capTotalCount: 0,
    _capLoadingMore: false,

    loadCapabilities: async function(page) {
        let self = this;
        page = page || 1;
        self._capCurrentPage = page;
        try {
            // AA-010: Paginated flat list + hierarchy in parallel
            let flatPromise = fetch('/capability-map/api/unified-capabilities?page=' + page + '&per_page=' + self._capPerPage);
            let hierarchyPromise = (page === 1)
                ? fetch('/capability-map/api/acm/hierarchy')
                : Promise.resolve(null);

            let flatRes = await flatPromise;
            let flatData = await flatRes.json();
            let capabilities = Array.isArray(flatData.unified_capabilities)
                ? flatData.unified_capabilities
                : self.getPayload(flatData);

            // Track total for pagination
            if (flatData.total !== undefined) {
                self._capTotalCount = flatData.total;
            } else if (Array.isArray(capabilities)) {
                self._capTotalCount = capabilities.length;
            }

            if (Array.isArray(capabilities)) {
                if (page === 1) {
                    self.capabilities = capabilities;
                } else {
                    // Append to existing list
                    self.capabilities = (self.capabilities || []).concat(capabilities);
                }
                self.renderCapabilities(self.capabilities);
                self._renderLoadMoreButton();
            }

            // Load hierarchy tree for browse mode (only on first page)
            if (page === 1) {
                try {
                    let hierRes = await hierarchyPromise;
                    if (hierRes) {
                        let hierData = await hierRes.json();
                        if (hierData.hierarchy) {
                            self._capHierarchy = hierData.hierarchy;
                            self._renderHierarchyBrowser(hierData.hierarchy);
                        }
                    }
                } catch (hierErr) {
                    console.warn('Hierarchy view not available:', hierErr);
                }
            }

            if (!Array.isArray(capabilities)) {
                throw new Error((flatData && flatData.error) || 'Failed to load capabilities');
            }
        } catch (err) {
            console.error('Error loading capabilities:', err);
            if (page === 1) self.capabilities = [];
            self.showSectionError('capabilities-list', 'Error loading capabilities');
        } finally {
            self._capLoadingMore = false;
        }
    },

    // AA-010: Render "Load more" button when more pages exist
    _renderLoadMoreButton: function() {
        let self = this;
        let container = document.getElementById('capabilities-load-more');
        if (!container) {
            // Create container if not present
            let listEl = document.getElementById('capabilities-list');
            if (listEl) {
                let div = document.createElement('div');
                div.id = 'capabilities-load-more';
                div.className = 'flex justify-center py-4';
                listEl.parentNode.insertBefore(div, listEl.nextSibling);
                container = div;
            }
        }
        if (!container) return;
        let loaded = (self.capabilities || []).length;
        if (loaded < self._capTotalCount) {
            container.innerHTML = '<button type="button" onclick="ArchAssistant.loadMoreCapabilities()" class="inline-flex items-center gap-2 h-9 px-4 rounded-md text-sm font-medium border border-input bg-background hover:bg-accent">' +
                'Load more (' + loaded + ' of ' + self._capTotalCount + ')' +
                '</button>';
        } else {
            container.innerHTML = '';
        }
    },

    loadMoreCapabilities: function() {
        if (this._capLoadingMore) return;
        this._capLoadingMore = true;
        this.loadCapabilities(this._capCurrentPage + 1);
    },

    _renderHierarchyBrowser: function(hierarchy) {
        let container = document.getElementById('capability-hierarchy-tree');
        if (!container) return;
        if (!hierarchy || hierarchy.length === 0) {
            safeHTML(container, '<p class="text-sm text-muted-foreground py-4">No hierarchy data available</p>');
            return;
        }
        let self = this;
        let html = '<div class="space-y-1">';
        hierarchy.forEach(function(domain) {
            html += self._renderHierarchyNode(domain, 0);
        });
        html += '</div>';
        safeHTML(container, html);
        lucide.createIcons();
    },

    _renderHierarchyNode: function(node, depth) {
        let self = this;
        let hasChildren = node.children && node.children.length > 0;
        let indent = 'pl-' + (depth * 4);
        let isSelected = self.selectedCapabilities.some(function(c) { return String(c.id) === String(node.id); });
        let appCount = node.applications_count || 0;
        let levelBadge = node.level || ('L' + depth);

        let html = '<div class="' + indent + '">';
        html += '<div class="flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-muted/50 group ' + (isSelected ? 'bg-primary/5 border border-primary/20' : '') + '">';

        // Expand/collapse toggle for nodes with children
        if (hasChildren) {
            html += '<button class="shrink-0 p-0.5 rounded hover:bg-muted" onclick="ArchAssistant._toggleHierarchyNode(this)" aria-label="Toggle children">' +
                '<i data-lucide="chevron-right" class="h-3.5 w-3.5 text-muted-foreground transition-transform"></i></button>';
        } else {
            html += '<span class="w-5"></span>';
        }

        // Node content
        html += '<div class="flex-1 min-w-0">';
        html += '<span class="text-sm font-medium truncate">' + (node.name || 'Unnamed') + '</span>';
        if (node.code) html += ' <span class="text-xs text-muted-foreground">(' + node.code + ')</span>';
        html += '</div>';

        // Badges
        html += '<span class="text-xs px-1.5 py-0.5 bg-muted rounded shrink-0">' + levelBadge + '</span>';
        if (appCount > 0) html += '<span class="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded shrink-0">' + appCount + ' apps</span>';

        // Select button (only for leaf or L1+ nodes with real IDs)
        if (node.id && typeof node.id === 'number') {
            html += '<button class="opacity-0 group-hover:opacity-100 shrink-0 px-2 py-0.5 text-xs border border-primary text-primary rounded hover:bg-primary hover:text-primary-foreground transition-all" ' +
                'onclick="ArchAssistant.addSelectedCapability(\'' + node.id + '\', \'' + (node.name || '').replace(/'/g, "\\'") + '\')">' +
                (isSelected ? 'Selected' : 'Select') + '</button>';
        }

        html += '</div>';

        // Children (hidden by default)
        if (hasChildren) {
            html += '<div class="hierarchy-children hidden">';
            node.children.forEach(function(child) {
                html += self._renderHierarchyNode(child, depth + 1);
            });
            html += '</div>';
        }

        html += '</div>';
        return html;
    },

    _toggleHierarchyNode: function(btn) {
        let parent = btn.closest('div').parentElement;
        let children = parent.querySelector('.hierarchy-children');
        if (!children) return;
        children.classList.toggle('hidden');
        let icon = btn.querySelector('i, svg');
        if (icon) {
            icon.style.transform = children.classList.contains('hidden') ? '' : 'rotate(90deg)';
        }
    },

    renderCapabilities: function(capabilities) {
        let self = this;
        let container = document.getElementById('capabilities-list');
        // AWIZ-009: layer badge colours
        let layerColours = { strategy: 'bg-primary/10 text-primary', business: 'bg-primary/10 text-primary', application: 'bg-primary/10 text-primary', technology: 'bg-emerald-500/10 text-emerald-700' };
        let cards = capabilities.map(function(cap) {
            let isSelected = self.selectedCapabilities.some(function(c) { return String(c.id) === String(cap.id); });
            let layer = (cap.archimate_layer || 'strategy').toLowerCase();
            let layerCls = layerColours[layer] || 'bg-muted text-muted-foreground';
            return '<div class="option-card p-4 border border-border rounded-lg ' + (isSelected ? 'selected' : '') + '"' +
                ' data-id="' + cap.id + '">' +
                '<div class="flex items-center gap-2">' +
                '<span class="font-medium">' + cap.name + '</span>' +
                '<span class="text-xs px-2 py-0.5 rounded-full ' + layerCls + '">' + (cap.archimate_layer || 'Strategy') + '</span>' +
                '</div>' +
                '<div class="flex items-center gap-2 mt-2">' +
                '<span class="text-xs px-2 py-1 bg-muted rounded">Level ' + (cap.level || 2) + '</span>' +
                (cap.has_gap ? '<span class="text-xs px-2 py-1 bg-amber-500/10 text-amber-700 rounded">Has Gap</span>' : '') +
                '</div>' +
                '</div>';
        }).join('');

        // AWIZ-009: append CapabilityMap viewpoint panel below the card list
        let viewpointPanel = '<details class="mt-4 border border-border rounded-lg p-3" id="capability-map-details">' +
            '<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">CapabilityMap Viewpoint</summary>' +
            '<div id="capability-map-panel" class="mt-2 text-sm text-muted-foreground">Loading viewpoint...</div>' +
            '</details>';

        safeHTML(container, cards + viewpointPanel);

        // Lazy-load viewpoint on expand
        let details = document.getElementById('capability-map-details');
        if (details) {
            details.addEventListener('toggle', function() {
                if (!details.open) return;
                let panel = document.getElementById('capability-map-panel');
                if (panel && panel.dataset.loaded) return;
                fetch('/api/architecture-assistant/viewpoints')
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        let vps = data.viewpoints || [];
                        let cm = vps.find(function(v) { return (v.key || v.id || v.name || '').toLowerCase().includes('capability'); }) || vps[0];
                        if (cm && panel) {
                            safeHTML(panel, '<div class="font-medium text-foreground mb-1">' + cm.name + '</div>' +
                                '<p class="text-xs mb-2">' + (cm.description || '') + '</p>' +
                                '<div class="flex flex-wrap gap-1">' +
                                (cm.layers || []).map(function(l) { return '<span class="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded">' + l + '</span>'; }).join('') +
                                '</div>');
                            panel.dataset.loaded = '1';
                        }
                    }).catch(function() { if (panel) panel.textContent = 'Viewpoint unavailable'; });
            });
        }
    },

    filterCapabilities: function(query) {
        let self = this;
        let filtered = self.capabilities.filter(function(cap) {
            return cap.name.toLowerCase().includes(query.toLowerCase());
        });
        self.renderCapabilities(filtered);
        clearTimeout(self._capSearchTimer);
        if (query.length >= 2) {
            self._capSearchTimer = setTimeout(function() {
                fetch('/api/architecture-assistant/capabilities?page=1&per_page=50&search=' + encodeURIComponent(query))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.success && data.capabilities) {
                            let seen = {};
                            self.capabilities.forEach(function(c) { seen[c.id] = true; });
                            let merged = self.capabilities.slice();
                            data.capabilities.forEach(function(c) {
                                if (!seen[c.id]) { merged.push(c); seen[c.id] = true; }
                            });
                            self.capabilities = merged;
                            let refiltered = merged.filter(function(cap) {
                                return cap.name.toLowerCase().includes(query.toLowerCase());
                            });
                            self.renderCapabilities(refiltered);
                        }
                    })
                    .catch(function() {});
            }, 300);
        }
    },

    selectCapability: function(id) {
        let self = ArchAssistant;
        // Maintain single-select legacy behavior while supporting multi-select
        self.selectedCapability = self.capabilities.find(function(c) { return String(c.id) === String(id); });
        if (!self.selectedCapability) return;
        if (!self.selectedCapabilities.find(function(c) { return String(c.id) === String(id); })) {
            self.selectedCapabilities.push(self.selectedCapability);
        }
        self.renderCapabilities(self.capabilities);
        self.renderSelectedCapabilities();
        document.getElementById('btn-step-2-next').disabled = false;
    },

    clearSelectedCapabilities: function() {
        this.selectedCapabilities = [];
        this.selectedCapability = null;
        this.renderSelectedCapabilities();
        this.renderCapabilities(this.capabilities);
        document.getElementById('btn-step-2-next').disabled = true;
    },

    goToStep: function(step) {
        // Save state from current step before navigating away
        if (this.currentStep === 1) this._saveScopeState();

        // Update wizard indicators
        document.querySelectorAll('.wizard-indicator').forEach(function(ind) {
            let s = parseInt(ind.dataset.step);
            if (s < step) {
                ind.classList.remove('opacity-50');
                ind.querySelector('div').className = 'w-8 h-8 rounded-full bg-emerald-500 text-primary-foreground flex items-center justify-center text-sm font-medium shrink-0';
            } else if (s === step) {
                ind.classList.remove('opacity-50');
                ind.querySelector('div').className = 'w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-medium shrink-0';
            } else {
                ind.classList.add('opacity-50');
                ind.querySelector('div').className = 'w-8 h-8 rounded-full bg-muted text-muted-foreground flex items-center justify-center text-sm font-medium shrink-0';
            }
        });

        // Update step visibility
        document.querySelectorAll('.wizard-step').forEach(function(s) { s.classList.remove('active'); });
        let activePanel = document.getElementById('step-' + step);
        activePanel.classList.add('active');

        this.currentStep = step;

        // Scroll wizard content into view
        activePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });

        // Load step content
        if (step === 1) this.loadBusinessContext();
        if (step === 2) this.loadCapabilities();
        if (step === 3) this.loadGapAnalysis();
        if (step === 4) this.loadSolutionOptions();
        if (step === 5) this.loadRoadmap();
        if (step === 6) this.generateARBDraft();

        lucide.createIcons();
    },

    loadGapAnalysis: async function() {
        let self = this;
        let container = document.getElementById('gap-analysis-content');

        if (!self.selectedCapability && (!self.selectedCapabilities || self.selectedCapabilities.length === 0)) {
            self.showSectionError('gap-analysis-content', 'Please select at least one capability in Step 2 first.');
            return;
        }

        let capName = self.selectedCapability ? self.selectedCapability.name : self.selectedCapabilities[0].name;
        let capCount = self.selectedCapabilities ? self.selectedCapabilities.length : 1;
        let label = capCount > 1 ? (capCount + ' capabilities') : capName;

        safeHTML(container,
            '<div class="text-center py-8 text-muted-foreground">' +
            '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
            '<p>Analyzing gaps for ' + label + '...</p>' +
            '</div>');
        lucide.createIcons();

        try {
            let scopeData = { problem: self._scopeProblem || '', definition: self._scopeDefinition || '', stakeholders: self._scopeStakeholders || '', constraints: self._scopeConstraints || '' };
            let payload = self.selectedCapabilities && self.selectedCapabilities.length > 0
                ? { capability_id: self.selectedCapabilities.map(function(c) { return c.id; }), scope: scopeData }
                : { capability_id: self.selectedCapability ? self.selectedCapability.id : null, scope: scopeData };

            let res = await fetch('/api/architecture-assistant/analyze-gap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            let data = await res.json();
            let gapData = self.getPayload(data);
            if (gapData && gapData.gap_analysis) {
                gapData = gapData.gap_analysis;
            }

            if (data.success && gapData) {
                self.gapAnalysis = gapData;
                self.persistAssistantData();
                self.renderGapAnalysis(gapData);
                return;
            }

            throw new Error(data.error || 'Gap analysis failed');
        } catch (err) {
            console.error('Error analyzing gap:', err);
            self.showSectionError('gap-analysis-content', 'Error analyzing capability gap');
        }
    },

    renderGapAnalysis: function(data) {
        let container = document.getElementById('gap-analysis-content');
        let severityClass = data.gap_severity === 'high' ? 'text-destructive' :
                           data.gap_severity === 'medium' ? 'text-amber-600' : 'text-emerald-600';

        // Portfolio insights section
        let portfolioInsightsHtml = data.portfolio_insights ? '<div class="p-4 bg-gradient-to-r from-primary/5 to-primary/10 border border-primary/20 rounded-lg mb-6"><div class="flex items-center justify-between mb-3"><h3 class="font-semibold text-foreground flex items-center gap-2"><i data-lucide="activity" class="h-5 w-5"></i>Portfolio Health Context</h3><div class="text-3xl font-bold ' + (data.portfolio_insights.health_score >= 80 ? 'text-emerald-600' : data.portfolio_insights.health_score >= 60 ? 'text-amber-600' : 'text-destructive') + '">' + data.portfolio_insights.health_score + '</div></div>' +
            (data.portfolio_insights.relevant_alerts && data.portfolio_insights.relevant_alerts.length > 0 ? '<div class="mb-3"><h4 class="text-sm font-medium text-muted-foreground mb-2">Related Alerts</h4><div class="space-y-1">' + data.portfolio_insights.relevant_alerts.slice(0, 3).map(function(alert) { return '<div class="text-xs p-2 bg-background rounded border border-border"><span class="font-medium ' + (alert.priority === 'critical' ? 'text-destructive' : alert.priority === 'high' ? 'text-amber-600' : 'text-amber-600') + '">' + alert.priority.toUpperCase() + '</span>: ' + alert.title + '</div>'; }).join('') + '</div></div>' : '') +
            (data.portfolio_insights.relevant_recommendations && data.portfolio_insights.relevant_recommendations.length > 0 ? '<div><h4 class="text-sm font-medium text-muted-foreground mb-2">Recommended Actions</h4><div class="space-y-1">' + data.portfolio_insights.relevant_recommendations.slice(0, 2).map(function(rec) { return '<div class="text-xs p-2 bg-background rounded border border-border"><i data-lucide="lightbulb" class="h-3 w-3 inline mr-1"></i>' + rec.title + '</div>'; }).join('') + '</div></div>' : '') +
            '</div>' : '';

        safeHTML(container, portfolioInsightsHtml +
            '<div class="grid grid-cols-1 md:grid-cols-2 gap-6">' +
            '<div class="p-4 bg-muted/50 rounded-lg"><h3 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="circle" class="h-4 w-4 text-destructive"></i>Current State</h3><p class="text-sm text-muted-foreground">' + (data.current_state || 'Not assessed') + '</p></div>' +
            '<div class="p-4 bg-muted/50 rounded-lg"><h3 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="target" class="h-4 w-4 text-emerald-500"></i>Target State</h3><p class="text-sm text-muted-foreground">' + (data.target_state || 'Not defined') + '</p></div>' +
            '</div>' +
            '<div class="grid grid-cols-1 md:grid-cols-3 gap-4">' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Gap Severity</div><div class="text-2xl font-bold ' + severityClass + ' capitalize">' + (data.gap_severity || 'Unknown') + '</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Estimated Effort</div><div class="text-2xl font-bold">' + (data.estimated_effort || 'TBD') + '</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Impact Areas</div><div class="text-2xl font-bold">' + (data.impact_areas || []).length + '</div></div>' +
            '</div>' +
            (data.recommendations ? '<div class="p-4 bg-primary/5 border border-primary/20 rounded-lg"><h3 class="font-medium mb-3 text-primary/90">AI Recommendations</h3><ul class="space-y-2">' + data.recommendations.map(function(rec) { return '<li class="flex items-start gap-2 text-sm text-primary"><i data-lucide="check" class="h-4 w-4 mt-0.5 flex-shrink-0"></i>' + rec + '</li>'; }).join('') + '</ul></div>' : '') +
            // AWIZ-010: ArchiMate Plateaus section
            (data.gap_elements && data.gap_elements.length ?
                '<details class="mt-4 border border-border rounded-lg p-3"><summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">ArchiMate Plateaus (' + data.gap_elements.length + ')</summary>' +
                '<div class="mt-2 space-y-1">' +
                data.gap_elements.map(function(g) { return '<div class="text-xs p-2 bg-muted rounded flex items-center gap-2"><span class="font-medium">' + g.name + '</span><span class="text-muted-foreground">Baseline → Target (IDs: ' + g.from_plateau_id + ' → ' + g.to_plateau_id + ')</span></div>'; }).join('') +
                '</div></details>' : ''));
        lucide.createIcons();
    },

    loadSolutionOptions: async function() {
        let self = this;
        let container = document.getElementById('solution-options');
        safeHTML(container,
            '<div class="text-center py-8 text-muted-foreground">' +
            '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
            '<p>Generating solution options...</p>' +
            '</div>');
        lucide.createIcons();

        try {
            let requestPayload = {
                capability_id: self.selectedCapability.id,
                gap_analysis: self.gapAnalysis
            };
            let res = await fetch('/api/architecture-assistant/generate-options', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestPayload)
            });
            let data = await res.json();
            let optionsData = self.getPayload(data);
            let options = optionsData && optionsData.options ? optionsData.options : data.options;

            if (data.success && Array.isArray(options) && options.length === 0) {
                let fallbackRes = await fetch('/api/architecture-assistant/design-solution', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestPayload)
                });
                let fallbackData = await fallbackRes.json();
                let fallbackPayload = self.getPayload(fallbackData);
                options = fallbackPayload && fallbackPayload.options ? fallbackPayload.options : fallbackData.options;
                data = fallbackData;
            }

            if (data.success && Array.isArray(options)) {
                self.solutionOptions = options;
                self.persistAssistantData();
                self.renderSolutionOptions(options);
                if (options.length > 0 && !self.selectedOption) { self.selectOption(String(options[0].id)); }
                return;
            }

            throw new Error(data.error || 'Option generation failed');
        } catch (err) {
            console.error('Error generating options:', err);
            self.showSectionError('solution-options', 'Error generating solution options');
        }
    },

    renderSolutionOptions: function(options) {
        let self = this;
        let container = document.getElementById('solution-options');
        safeHTML(container, options.map(function(opt, idx) {
            let isSelected = self.selectedOption && String(self.selectedOption.id) === String(opt.id);
            let recommendedBadge = idx === 0 ? '<span class="px-2 py-1 text-xs bg-emerald-500/10 text-emerald-700 rounded">Recommended</span>' : '';
            let vendor = opt.vendor || opt.vendor_name || '';
            let score = opt.score || opt.total_score || opt.totalScore || 0;
            let fit = opt.fit_score || opt.capability_coverage || opt.strategic_fit_score || 0;
            let cost = opt.cost_estimate || opt.cost || '';
            let implementation = opt.implementation_time || (opt.implementation_weeks ? opt.implementation_weeks + ' weeks' : opt.implementation || '');
            let archi = opt.archimate_suggestions || {};
            let archiHtml = Object.keys(archi).length ? '<div class="mt-3 p-3 bg-muted/30 rounded"><div class="text-xs text-muted-foreground mb-2">ArchiMate Suggestions</div>' + Object.keys(archi).map(function(layer) { return '<div class="text-xs"><strong>' + layer + '</strong>: ' + (archi[layer]||[]).map(function(e) { return e.name || e.element_type || e.title || ''; }).join(', ') + '</div>'; }).join('') + '</div>' : '';
            let checklist = opt.governance_checklist || [];
            let checklistHtml = checklist.length ? '<div class="mt-3 text-xs text-muted-foreground">' + checklist.map(function(c) { return '<div>' + c.check + ': ' + (c.pass !== undefined ? c.pass : (c.value !== undefined ? c.value : '')) + '</div>'; }).join('') + '</div>' : '';

            return '<div class="option-card p-6 border border-border rounded-lg ' + (isSelected ? 'selected' : '') + '" data-option-id="' + opt.id + '" data-action="ArchAssistant.selectOption" data-id="' + opt.id + '">' +
                '<div class="flex justify-between items-start mb-4"><div><div class="flex items-center gap-2">' + recommendedBadge + '<span class="text-lg font-semibold">' + opt.name + '</span></div><div class="text-sm text-muted-foreground">' + vendor + '</div></div><div class="text-right"><div class="text-2xl font-bold text-primary">' + score + '</div><div class="text-xs text-muted-foreground">Overall Score</div></div></div>' +
                '<div class="grid grid-cols-3 gap-4 mb-4"><div><div class="text-xs text-muted-foreground mb-1">Fit Score</div><div class="score-bar"><div class="score-fill bg-primary" style="width: ' + fit + '%"></div></div></div><div><div class="text-xs text-muted-foreground">Cost Estimate</div><div class="text-sm font-medium">' + cost + '</div></div><div><div class="text-xs text-muted-foreground">Implementation</div><div class="text-sm font-medium">' + implementation + '</div></div></div>' +
                '<div class="grid grid-cols-2 gap-4"><div><div class="text-xs text-muted-foreground mb-2">Pros</div><div class="space-y-1">' + (opt.pros || []).map(function(p) { return '<div class="pros-cons-item pro-item"><i data-lucide="plus" class="h-3 w-3 inline mr-1"></i>' + p + '</div>'; }).join('') + '</div></div><div><div class="text-xs text-muted-foreground mb-2">Cons</div><div class="space-y-1">' + (opt.cons || []).map(function(c) { return '<div class="pros-cons-item con-item"><i data-lucide="minus" class="h-3 w-3 inline mr-1"></i>' + c + '</div>'; }).join('') + '</div></div></div>' +
                '<div class="mt-3 pt-3 border-t border-border flex gap-2"><button class="px-3 py-1.5 text-xs border border-primary text-primary rounded hover:bg-primary hover:text-primary-foreground transition-colors" data-action="ArchAssistant.launchSolutionComposer" data-id="' + opt.id + '"><i data-lucide="layers" class="h-3 w-3 inline mr-1"></i>Open Model Viewer</button><button class="px-3 py-1.5 text-xs border border-border rounded hover:bg-accent transition-colors" data-action="ArchAssistant.viewArchiMateDetails" data-id="' + opt.id + '"><i data-lucide="list-tree" class="h-3 w-3 inline mr-1"></i>View ArchiMate Details</button></div>' +
                archiHtml + checklistHtml +
                '</div>';
        }).join(''));

        lucide.createIcons();
    },

    selectOption: function(id) {
        let self = ArchAssistant;
        self.selectedOption = self.solutionOptions.find(function(o) { return String(o.id) === String(id); });
        self.renderSolutionOptions(self.solutionOptions);
        document.getElementById('btn-step-4-next').disabled = false;
    },

    generateARBDraft: async function() {
        let self = this;
        let container = document.getElementById('arb-draft-content');
        safeHTML(container,
            '<div class="text-center py-8 text-muted-foreground">' +
            '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
            '<p>Generating ARB submission draft...</p>' +
            '</div>');
        lucide.createIcons();

        try {
            // First, attempt an in-depth option analysis to enrich the selected option
            try {
                let analysisRes = await fetch('/api/architecture-assistant/analyze-options', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ options_data: [self.selectedOption], capability_id: self.selectedCapability?.id })
                });
                let analysis = await analysisRes.json();
                if (analysis.success && analysis.options && analysis.options.length > 0) {
                    let enriched = analysis.options[0];
                    self.selectedOption = enriched;
                    self.decisionRationale = analysis.decision_rationale || null;
                }
            } catch (e) {
                console.warn('Option analysis failed, proceeding with original selection', e);
            }

            let res = await fetch('/api/architecture-assistant/draft-arb', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    capability_id: self.selectedCapability.id,
                    recommended_option: self.selectedOption,
                    gap_analysis: self.gapAnalysis
                })
            });
            let data = await res.json();

            if (data.success && data.draft) {
                self.arbDraft = data.draft;
                self.renderARBDraft(self.arbDraft);
            } else if (data.success && data.data) {
                self.arbDraft = data.data;
                self.renderARBDraft(self.arbDraft);
            } else {
                throw new Error(data.error || 'ARB draft generation failed');
            }
        } catch (err) {
            console.error('Error generating ARB draft:', err);
            self.showSectionError('arb-draft-content', 'Error generating ARB draft');
        }
    },

    renderARBDraft: function(draft) {
        let self = ArchAssistant;
        let container = document.getElementById('arb-draft-content');
        self.arbDraft = draft;

        // AWIZ-013: ArchiMate model summary table
        let archimateSection = '';
        if (draft.archimate_viewpoints && draft.archimate_viewpoints.elements && draft.archimate_viewpoints.elements.length) {
            let elements = draft.archimate_viewpoints.elements;
            let layers = ['motivation', 'strategy', 'business', 'application', 'technology'];
            let tableRows = layers.map(function(l) {
                let count = elements.filter(function(e) { return (e.layer || '').toLowerCase() === l; }).length;
                return count ? '<tr><td class="px-3 py-1 capitalize text-sm">' + l + '</td><td class="px-3 py-1 text-sm font-medium">' + count + '</td></tr>' : '';
            }).join('');
            archimateSection = '<div class="border border-border rounded-lg p-4">' +
                '<div class="flex items-center justify-between mb-3">' +
                '<h4 class="font-medium flex items-center gap-2"><i data-lucide="layers" class="h-4 w-4 text-primary"></i>Generated ArchiMate Model</h4>' +
                '<button data-action="ArchAssistant.exportArchiMateOEF" class="px-3 py-1 text-xs border border-primary text-primary rounded hover:bg-primary hover:text-primary-foreground transition-colors">' +
                '<i data-lucide="download" class="h-3 w-3 inline mr-1"></i>Export ArchiMate XML (OEF)</button>' +
                '</div>' +
                '<table class="w-full text-sm"><thead><tr><th class="px-3 py-1 text-left font-medium text-muted-foreground">Layer</th><th class="px-3 py-1 text-left font-medium text-muted-foreground">Elements</th></tr></thead>' +
                '<tbody>' + tableRows + '</tbody></table>' +
                '</div>';
        }

        safeHTML(container,
            '<div class="p-4 bg-muted/50 rounded-lg mb-4"><h3 class="font-semibold text-lg mb-2">' + draft.title + '</h3><div class="flex gap-4 text-sm text-muted-foreground"><span>Cost: ' + (draft.cost_summary || 'To be determined') + '</span><span>Timeline: ' + (draft.timeline || 'To be determined') + '</span></div></div>' +
            '<div class="space-y-4">' +
            '<div class="border border-border rounded-lg p-4"><h4 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="briefcase" class="h-4 w-4 text-primary"></i>Business Justification</h4><textarea class="w-full px-3 py-2 border border-border rounded-md min-h-[100px]" id="draft-business">' + draft.business_justification + '</textarea></div>' +
            '<div class="border border-border rounded-lg p-4"><h4 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="cpu" class="h-4 w-4 text-primary"></i>Technical Assessment</h4><textarea class="w-full px-3 py-2 border border-border rounded-md min-h-[100px]" id="draft-technical">' + draft.technical_assessment + '</textarea></div>' +
            '<div class="border border-border rounded-lg p-4"><h4 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="shield-alert" class="h-4 w-4 text-primary"></i>Risk Analysis</h4><textarea class="w-full px-3 py-2 border border-border rounded-md min-h-[100px]" id="draft-risk">' + draft.risk_analysis + '</textarea></div>' +
            '<div class="border border-border rounded-lg p-4"><h4 class="font-medium mb-2 flex items-center gap-2"><i data-lucide="route" class="h-4 w-4 text-primary"></i>Implementation Approach</h4><textarea class="w-full px-3 py-2 border border-border rounded-md min-h-[100px]" id="draft-implementation">' + draft.implementation_approach + '</textarea></div>' +
            archimateSection +
            '</div>');
        lucide.createIcons();
    },

    // AWIZ-013: export ArchiMate model as OEF XML download
    exportArchiMateOEF: function() {
        let self = ArchAssistant;
        let model = (self.arbDraft && self.arbDraft.archimate_viewpoints) ? self.arbDraft.archimate_viewpoints : {};
        fetch('/api/architecture-assistant/export-archimate-oef', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: model })
        }).then(function(r) { return r.blob(); }).then(function(blob) {
            let url = URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = url;
            a.download = 'archimate_model.xml';
            document.body.appendChild(a);
            a.click();
            setTimeout(function() { a.remove(); URL.revokeObjectURL(url); }, 1000);
        }).catch(function(err) {
            console.error('OEF export error:', err);
            ArchAssistant.showToast('Export failed', 'error');
        });
    },

    // Run the full orchestration pipeline in one server call
    runFullPipeline: async function() {
        let self = this;

        // Require at least capabilities selected
        if (!self.selectedCapabilities || self.selectedCapabilities.length === 0) {
            self.showToast('Select at least one capability first (Step 2)', 'info');
            return;
        }

        // Save current scope state
        self._saveScopeState();

        let container = document.getElementById('arb-draft-content');
        if (container) {
            safeHTML(container,
                '<div class="text-center py-8 text-muted-foreground">' +
                '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
                '<p class="font-medium">Running full architecture pipeline...</p>' +
                '<p class="text-sm mt-1">Scope → Gap Analysis → Solutions → Roadmap → ARB Draft</p>' +
                '<div id="pipeline-progress" class="mt-4 space-y-1"></div>' +
                '</div>');
            lucide.createIcons();
        }

        // Jump to ARB step to show progress
        self.goToStep(6);

        try {
            let payload = {
                capability_ids: self.selectedCapabilities.map(function(c) { return parseInt(c.id); }),
                scope: {
                    problem: self._scopeProblem || '',
                    definition: self._scopeDefinition || '',
                    stakeholders: self._scopeStakeholders || '',
                    constraints: self._scopeConstraints || '',
                    principles: self._scopePrinciples || []
                },
                target_coverage: 100,
                include_roadmap: true
            };

            let res = await fetch('/api/architecture-assistant/orchestrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            let data = await res.json();

            if (!data.success) {
                throw new Error(data.error || 'Pipeline failed');
            }

            let r = data.results || {};

            // Populate wizard state from pipeline results
            if (r.gap_analysis) {
                self.gapAnalysis = r.gap_analysis;
            }
            if (r.solution_options && r.solution_options.options) {
                self.solutionOptions = r.solution_options.options;
                self.selectedOption = self.solutionOptions[0] || null;
                self.decisionRationale = r.solution_options.decision_rationale || null;
            }
            if (r.roadmap) {
                self.roadmapData = r.roadmap;
            }
            if (r.arb_draft) {
                let draft = r.arb_draft.draft || r.arb_draft;
                self.arbDraft = draft;
                self.renderARBDraft(draft);
            } else {
                // If ARB draft wasn't generated, show summary of what completed
                let phases = data.completed_phases || [];
                let summaryHtml = '<div class="space-y-4">' +
                    '<div class="p-4 bg-muted/50 border border-border rounded-lg">' +
                    '<h3 class="font-medium mb-2">Pipeline Complete</h3>' +
                    '<p class="text-sm text-muted-foreground mb-3">' + phases.length + ' of ' + data.total_phases + ' phases completed</p>' +
                    '<div class="flex flex-wrap gap-2">' +
                    phases.map(function(p) {
                        return '<span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-700 border border-emerald-500/30">' +
                            '<i data-lucide="check" class="h-3 w-3 mr-1"></i>' + p.replace(/_/g, ' ') + '</span>';
                    }).join('') + '</div></div>';

                if (r.errors && r.errors.length > 0) {
                    summaryHtml += '<div class="p-4 bg-destructive/5 border border-destructive/20 rounded-lg">' +
                        '<h4 class="font-medium text-sm text-destructive mb-2">Errors</h4>' +
                        r.errors.map(function(e) {
                            return '<p class="text-xs text-muted-foreground"><strong>' + e.phase + ':</strong> ' + e.error + '</p>';
                        }).join('') + '</div>';
                }

                summaryHtml += '</div>';
                if (container) safeHTML(container, summaryHtml);
                lucide.createIcons();
            }

            self.persistAssistantData();
            self.showToast('Pipeline completed: ' + (data.completed_phases || []).length + '/' + data.total_phases + ' phases', 'success');
        } catch (err) {
            console.error('Pipeline error:', err);
            self.showSectionError('arb-draft-content', 'Pipeline failed: ' + err.message);
        }
    },

    newSession: function() {
        this.selectedCapability = null;
        this.gapAnalysis = null;
        this.solutionOptions = [];
        this.selectedOption = null;
        this.arbDraft = null;
        this.businessContextId = null;
        this.roadmapData = null;
        this._scopeProblem = '';
        this._scopeDefinition = '';
        this._scopeStakeholders = '';
        this._scopeConstraints = '';
        this._scopePrinciples = [];
        this._capHierarchy = null;
        this.goToStep(1);
        document.getElementById('btn-step-2-next').disabled = true;
    },

    downloadDraft: function() {
        // AA-009: Use arbDraft directly — Alpine x-model binds edits in real-time
        let draft = Object.assign({}, this.arbDraft);

        let blob = new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' });
        let url = URL.createObjectURL(blob);
        let a = document.createElement('a');
        a.href = url;
        a.download = 'arb-draft-' + Date.now() + '.json';
        a.click();
        URL.revokeObjectURL(url);
    },

    submitToARB: async function() {
        let self = this;
        try {
            // AA-009: Use arbDraft directly — Alpine x-model binds edits in real-time
            let updatedDraft = Object.assign({}, self.arbDraft);

            let capNames = self.selectedCapabilities.map(function(c) { return c.name; }).join(', ');
            let arbPayload = {
                title: updatedDraft.title || 'Architecture Review: ' + (self.selectedCapability?.name || 'Solution Implementation'),
                review_type: 'capability_implementation',
                decision_sought: 'Approve ' + (self.selectedOption?.name || 'proposed solution') + ' for ' + capNames,
                description: updatedDraft.business_justification || 'Architecture review submission from Architecture Assistant',
                priority: self.gapAnalysis?.gap_severity === 'critical' ? 'critical' :
                         self.gapAnalysis?.gap_severity === 'high' ? 'high' : 'medium',
                business_impact: self.gapAnalysis?.gap_severity || 'medium',
                estimated_effort: 'xl',
                togaf_phase: 'Phase E - Technology Architecture',
                business_justification: updatedDraft.business_justification,
                technical_assessment: updatedDraft.technical_assessment,
                risk_analysis: updatedDraft.risk_analysis,
                implementation_notes: updatedDraft.implementation_approach,
                capability_ids: self.selectedCapabilities.map(function(c) { return parseInt(c.id); }),
                capability_impacts: self.selectedCapabilities.map(function(c) {
                    return { capability_id: parseInt(c.id), impact_type: 'modifies', impact_level: 'high' };
                }),
                linked_capabilities: self.selectedCapabilities.map(function(c) { return { id: c.id, name: c.name }; }),
                metadata: {
                    source: 'architecture_assistant',
                    recommended_solution: self.selectedOption?.name,
                    cost_estimate: self.selectedOption?.cost_estimate || updatedDraft.cost_summary,
                    timeline: self.selectedOption?.implementation_time || updatedDraft.timeline,
                    gap_analysis: self.gapAnalysis,
                    decision_rationale: self.decisionRationale
                }
            };

            let res = await fetch('/arb/api/reviews', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(arbPayload)
            });

            let data = await res.json();

            let reviewId = data.review_id || (data.data && data.data.id);
            let redirectUrl = data.redirect_url || (reviewId ? '/arb/reviews/' + reviewId : null);

            if (data.success && redirectUrl) {
                self.showToast('Successfully submitted to ARB! Review: ' + (data.review_number || ''), 'success');

                // Non-blocking: create a Solution record linked to the wizard data
                try {
                    let capNames = self.selectedCapabilities.map(function(c) { return c.name; }).join(', ');
                    let wizardPayload = {
                        title: self.arbDraft ? self.arbDraft.title : ('Solution for ' + capNames),
                        scope: {
                            problem: self._scopeProblem || '',
                            definition: self._scopeDefinition || '',
                            stakeholders: self._scopeStakeholders || '',
                            constraints: self._scopeConstraints || '',
                            principles: self._scopePrinciples || []
                        },
                        capabilities: self.selectedCapabilities.map(function(c) {
                            return { id: c.id, name: c.name };
                        }),
                        gap_analysis: self.gapAnalysis || {},
                        selected_option: self.selectedOption || {},
                        solution_type: 'Platform',
                        arb_review_id: reviewId
                    };

                    let solResp = await fetch('/solutions/create-from-wizard', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(wizardPayload)
                    });
                    let solData = await solResp.json();
                    if (solData.success && solData.redirect_url) {
                        redirectUrl = solData.redirect_url;
                    }
                } catch (solErr) {
                    console.warn('Solution creation failed (non-blocking):', solErr);
                }

                setTimeout(function() {
                    window.location.href = redirectUrl;
                }, 1500);
            } else {
                throw new Error(data.error || data.errors ? JSON.stringify(data.errors) : 'ARB submission failed');
            }

        } catch (err) {
            console.error('Error submitting to ARB:', err);
            self.showToast('ARB submission failed: ' + err.message, 'error');
        }
    },

    quickAction: function(action) {
        let self = this;
        if (action === 'status') {
            fetch('/api/architecture-assistant/status')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.success) {
                        let statusData = self.getPayload(data) || {};
                        self.showToast('Service is ' + (statusData.status || 'unknown'), 'success');
                    }
                })
                .catch(function(err) { console.error('[ArchAssistant] status fetch error:', err); });
        } else {
            self.showToast(action + ' feature - select a capability first', 'info');
        }
    },

    launchSolutionComposer: async function(optionId) {
        let self = ArchAssistant;
        let option = self.solutionOptions.find(function(o) { return String(o.id) === String(optionId); });
        if (!option) {
            self.showToast('Option not found', 'error');
            return;
        }

        try {
            self.persistAssistantData([option]);
            window.open('/architecture-assistant/model-viewer', '_blank');
            self.showToast('Opened ArchiMate model viewer', 'success');
        } catch (err) {
            console.error('Error opening model viewer:', err);
            self.showToast('Could not open model viewer: ' + err.message, 'error');
        }
    },

    // AWIZ-011: render full ArchiMate 5-layer tree in a slide-over panel
    viewArchiMateDetails: function(optionId) {
        let self = ArchAssistant;
        let capId = self.selectedCapabilityId || (self.selectedCapability && self.selectedCapability.id);

        // Remove any existing panel
        let existing = document.getElementById('archimate-detail-panel');
        if (existing) existing.remove();

        let panel = document.createElement('div');
        panel.id = 'archimate-detail-panel';
        panel.className = 'fixed inset-y-0 right-0 w-96 bg-background border-l border-border shadow-xl z-50 overflow-y-auto p-4';
        safeHTML(panel,
            '<div class="flex items-center justify-between mb-4">' +
            '<h3 class="font-semibold">ArchiMate Model</h3>' +
            '<button id="archimate-panel-close" class="p-1 rounded hover:bg-muted"><i data-lucide="x" class="h-5 w-5"></i></button>' +
            '</div>' +
            '<div id="archimate-layer-content"><div class="text-center py-8 text-muted-foreground"><i data-lucide="loader" class="h-6 w-6 mx-auto mb-2 animate-spin"></i><p class="text-sm">Loading model...</p></div></div>');
        document.body.appendChild(panel);
        lucide.createIcons();

        document.getElementById('archimate-panel-close').addEventListener('click', function() { panel.remove(); });

        let layerLabels = ['motivation', 'strategy', 'business', 'application', 'technology'];
        let layerColours = { motivation: 'bg-amber-500/5 border-border', strategy: 'bg-primary/5 border-primary/20', business: 'bg-primary/5 border-primary/20', application: 'bg-primary/5 border-border', technology: 'bg-emerald-500/5 border-emerald-200' };

        if (!capId) {
            safeHTML(document.getElementById('archimate-layer-content'), '<p class="text-sm text-muted-foreground">Select a capability first to load its ArchiMate model.</p>');
            return;
        }

        fetch('/api/architecture-assistant/archimate-model?capability_id=' + capId)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                let elements = data.elements || [];
                let byLayer = {};
                elements.forEach(function(el) { (byLayer[el.layer] = byLayer[el.layer] || []).push(el); });

                let html = '';
                layerLabels.forEach(function(layer) {
                    let els = byLayer[layer] || [];
                    if (!els.length) return;
                    let cls = layerColours[layer] || 'bg-muted border-border';
                    html += '<details open class="mb-3 border ' + cls + ' rounded-lg p-3">' +
                        '<summary class="cursor-pointer text-sm font-medium capitalize select-none">' + layer + ' Layer (' + els.length + ')</summary>' +
                        '<div class="mt-2 space-y-1">' +
                        els.map(function(el) {
                            return '<div class="flex justify-between text-xs py-1 border-b border-border/50 last:border-0">' +
                                '<span class="font-medium">' + (el.name || '') + '</span>' +
                                '<span class="text-muted-foreground">' + (el.type || el.element_type || '') + '</span>' +
                                '</div>';
                        }).join('') +
                        '</div></details>';
                });

                if (!html) html = '<p class="text-sm text-muted-foreground">No ArchiMate elements generated for this capability yet.</p>';

                let rels = data.relationships || [];
                if (rels.length) {
                    html += '<details class="mb-3 border border-border rounded-lg p-3"><summary class="cursor-pointer text-sm font-medium select-none">Relationships (' + rels.length + ')</summary>' +
                        '<div class="mt-2 space-y-1">' +
                        rels.slice(0, 20).map(function(r) { return '<div class="text-xs py-1">' + (r.type || '') + ': ' + r.source_id + ' → ' + r.target_id + '</div>'; }).join('') +
                        '</div></details>';
                }

                safeHTML(document.getElementById('archimate-layer-content'), html);
                lucide.createIcons();
            })
            .catch(function(err) {
                console.error('ArchiMate model load error:', err);
                safeHTML(document.getElementById('archimate-layer-content'), '<p class="text-sm text-destructive">Could not load ArchiMate model.</p>');
            });
    },

    // Step 1: Load business context form (Phase A — Scope & Vision)
    loadBusinessContext: function() {
        let self = this;
        let container = document.getElementById('scope-content');
        if (!container) return;

        // Render the inline business context form with ArchiMate Motivation element pickers
        safeHTML(container,
            '<div class="space-y-2">' +
            '<div class="p-3 bg-primary/5 border border-primary/20 rounded-lg text-xs text-primary mb-4">' +
            '<strong>ArchiMate Motivation Layer</strong> — Type to search existing elements or create new ones. All entries are persisted as traceable ArchiMate records.' +
            '</div>' +
            self._renderMotivationCombobox('scope-problem', 'Driver', 'Problem Statement / Driver', 'Search existing drivers or type a new one...', self._scopeProblem || '') +
            '<button class="mb-4 px-3 py-1.5 text-xs border border-primary text-primary rounded-md hover:bg-primary hover:text-primary-foreground transition-colors" data-action="ArchAssistant.generateProblemStatement"><i data-lucide="sparkles" class="h-3 w-3 inline mr-1"></i>AI Generate from Portfolio Data</button>' +
            self._renderMotivationCombobox('scope-definition', 'Goal', 'Scope Definition / Goal', 'Search existing goals or type a new one...', self._scopeDefinition || '') +
            self._renderMotivationCombobox('scope-stakeholders', 'Stakeholder', 'Stakeholder Concerns', 'Search stakeholders (CIO, CFO, ...) or type a new one...', self._scopeStakeholders || '') +
            self._renderMotivationCombobox('scope-constraints', 'Constraint', 'Constraints &amp; Assumptions', 'Search existing constraints or type a new one...', self._scopeConstraints || '') +
            // Architecture Principles
            '<div>' +
            '<label class="block text-sm font-medium mb-2">Architecture Principles</label>' +
            '<div id="scope-principles" class="grid grid-cols-1 md:grid-cols-2 gap-2">' +
            self._renderPrincipleCheckboxes() +
            '</div>' +
            '</div>' +
            // Info card
            '<div class="p-4 bg-muted/50 border border-border rounded-lg">' +
            '<div class="flex items-start gap-3">' +
            '<i data-lucide="info" class="h-5 w-5 text-muted-foreground shrink-0 mt-0.5"></i>' +
            '<div class="text-sm text-muted-foreground">' +
            '<p class="font-medium text-foreground mb-1">TOGAF Phase A: Architecture Vision</p>' +
            '<p>Captures drivers, scope, stakeholder concerns, and constraints that frame this architecture engagement. This context flows into gap analysis, solution evaluation, and the final ARB submission.</p>' +
            '</div></div></div>' +
            '</div>');
        lucide.createIcons();

        // AWIZ-015: bind ArchiMate combobox typeahead to the scope content container
        self._bindMotivationComboboxes(container);

        // Bind principle checkbox change events via delegation
        let principlesContainer = document.getElementById('scope-principles');
        if (principlesContainer) {
            principlesContainer.addEventListener('change', function() { self._onPrincipleChange(); });
        }
    },

    // Default architecture principles (TOGAF standard)
    _architecturePrinciples: [
        { id: 'reuse', label: 'Maximize Reuse', desc: 'Prefer existing components over new builds' },
        { id: 'cloud-first', label: 'Cloud-First', desc: 'Default to cloud-hosted solutions' },
        { id: 'api-driven', label: 'API-Driven Integration', desc: 'Loosely coupled via well-defined APIs' },
        { id: 'data-owner', label: 'Single Data Owner', desc: 'Each data entity has one authoritative source' },
        { id: 'security-by-design', label: 'Security by Design', desc: 'Security built in, not bolted on' },
        { id: 'vendor-neutral', label: 'Vendor Neutral', desc: 'Avoid vendor lock-in where possible' }
    ],

    // AWIZ-015: render a combobox input backed by /motivation-elements typeahead
    _renderMotivationCombobox: function(fieldId, elementType, label, placeholder, currentValue) {
        return '<div class="relative mb-4">' +
            '<label for="' + fieldId + '" class="block text-sm font-medium mb-2">' + label +
            ' <span class="ml-1 text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary font-normal">ArchiMate</span></label>' +
            '<input type="text" id="' + fieldId + '" data-element-type="' + elementType +
            '" autocomplete="off" class="w-full px-3 py-2 border border-border rounded-md text-sm" placeholder="' +
            placeholder + '" value="' + (currentValue || '') + '">' +
            '<input type="hidden" id="' + fieldId + '-id">' +
            '<ul id="' + fieldId + '-dropdown" class="hidden absolute z-10 w-full bg-background border border-border rounded-md shadow-md max-h-48 overflow-y-auto mt-1"></ul>' +
            '</div>';
    },

    // AWIZ-015: attach typeahead listeners to all motivation comboboxes in a container
    _bindMotivationComboboxes: function(container) {
        let self = this;
        let debounceTimers = {};
        container.addEventListener('input', function(e) {
            let el = e.target;
            if (!el.dataset.elementType) return;
            let fieldId = el.id;
            clearTimeout(debounceTimers[fieldId]);
            debounceTimers[fieldId] = setTimeout(function() {
                let q = el.value.trim();
                let type = el.dataset.elementType;
                fetch('/api/architecture-assistant/motivation-elements?type=' + encodeURIComponent(type) + '&q=' + encodeURIComponent(q))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        let dropdown = document.getElementById(fieldId + '-dropdown');
                        if (!dropdown) return;
                        let results = data.results || [];
                        let html = results.map(function(r) {
                            return '<li data-id="' + r.id + '" data-name="' + r.name.replace(/"/g, '&quot;') + '" class="px-3 py-2 cursor-pointer hover:bg-muted text-sm">' + r.name + '</li>';
                        }).join('');
                        if (q.trim()) {
                            html += '<li data-create="true" class="px-3 py-2 cursor-pointer hover:bg-muted text-sm border-t border-border text-muted-foreground">+ Create: ' + q + '</li>';
                        }
                        safeHTML(dropdown, html);
                        if (html) dropdown.classList.remove('hidden');
                        else dropdown.classList.add('hidden');
                    }).catch(function() {});
            }, 300);
        });
        container.addEventListener('click', function(e) {
            let li = e.target.closest('li');
            if (!li) return;
            let dropdown = li.closest('ul');
            if (!dropdown) return;
            let fieldId = dropdown.id.replace('-dropdown', '');
            let input = document.getElementById(fieldId);
            let hiddenInput = document.getElementById(fieldId + '-id');
            if (li.dataset.create) {
                // Persist to backend via scope-archimate upsert
                let type = input ? input.dataset.elementType : '';
                let val = input ? input.value.trim() : li.textContent.replace('+ Create: ', '').trim();
                let payload = {};
                if (type === 'Driver') payload.problem_statement = val;
                else if (type === 'Stakeholder') payload.stakeholders = val;
                else if (type === 'Constraint') payload.constraints = val;
                else payload.problem_statement = val;
                fetch('/api/architecture-assistant/scope-archimate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).then(function(r) { return r.json(); }).then(function(data) {
                    if (data.success && hiddenInput) {
                        let ids = data.archimate_ids || {};
                        let id = ids.assessment || (ids.stakeholders || [])[0] || (ids.constraints || [])[0];
                        if (id) hiddenInput.value = id;
                    }
                }).catch(function() {});
            } else {
                if (input) input.value = li.dataset.name || li.textContent;
                if (hiddenInput) hiddenInput.value = li.dataset.id || '';
            }
            dropdown.classList.add('hidden');
        });
        // Close dropdowns on outside click
        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) {
                container.querySelectorAll('[id$="-dropdown"]').forEach(function(d) { d.classList.add('hidden'); });
            }
        });
    },

    _renderPrincipleCheckboxes: function() {
        let self = this;
        let selected = self._scopePrinciples || [];
        return self._architecturePrinciples.map(function(p) {
            let checked = selected.indexOf(p.id) !== -1 ? 'checked' : '';
            return '<label class="flex items-start gap-2 p-2 border border-border rounded-md hover:bg-muted/50 cursor-pointer text-sm">' +
                '<input type="checkbox" class="mt-0.5 rounded scope-principle-cb" value="' + p.id + '" ' + checked + '>' +
                '<div><span class="font-medium">' + p.label + '</span><br><span class="text-xs text-muted-foreground">' + p.desc + '</span></div>' +
                '</label>';
        }).join('');
    },

    _onPrincipleChange: function() {
        let checkboxes = document.querySelectorAll('#scope-principles input[type="checkbox"]');
        this._scopePrinciples = [];
        let self = this;
        checkboxes.forEach(function(cb) { if (cb.checked) self._scopePrinciples.push(cb.value); });
    },

    // AI-generate problem statement from portfolio health data
    generateProblemStatement: async function() {
        let self = ArchAssistant;
        if (!window.__APP_CONFIG__.llm_available) {
            let ta = document.getElementById('scope-problem');
            if (ta) ta.setAttribute('placeholder', 'AI features require LLM configuration in Settings');
            let btn = document.querySelector('[data-action="ArchAssistant.generateProblemStatement"]');
            if (btn) { btn.disabled = true; btn.setAttribute('title', 'Requires LLM configuration'); }
            return;
        }
        let textarea = document.getElementById('scope-problem');
        if (!textarea) return;
        textarea.value = 'Generating from portfolio data...';
        try {
            // Create a business context record if we don't have one
            if (!self.businessContextId) {
                let createRes = await fetch('/api/architecture-assistant/business-context', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Architecture Assistant Session ' + Date.now() })
                });
                let createData = await createRes.json();
                if (createData.success && createData.data) {
                    self.businessContextId = createData.data.id || createData.data.context_id;
                }
            }
            if (self.businessContextId) {
                let res = await fetch('/api/architecture-assistant/business-context/' + self.businessContextId + '/problem-statement', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                let data = await res.json();
                if (data.success && data.data && data.data.problem_statement) {
                    textarea.value = data.data.problem_statement;
                    self._scopeProblem = data.data.problem_statement;
                    return;
                }
            }
            textarea.value = '';
            self.showToast('Could not generate problem statement', 'info');
        } catch (err) {
            console.error('Error generating problem statement:', err);
            textarea.value = '';
            self.showToast('Error generating problem statement', 'error');
        }
    },

    // Save scope fields to local state before navigating away
    _saveScopeState: function() {
        this._scopeProblem = (document.getElementById('scope-problem') || {}).value || '';
        this._scopeDefinition = (document.getElementById('scope-definition') || {}).value || '';
        this._scopeStakeholders = (document.getElementById('scope-stakeholders') || {}).value || '';
        this._scopeConstraints = (document.getElementById('scope-constraints') || {}).value || '';
        // AWIZ-015: capture linked ArchiMate element IDs from hidden inputs
        this._scopeDriverId = (document.getElementById('scope-problem-id') || {}).value || null;
        this._scopeGoalId = (document.getElementById('scope-definition-id') || {}).value || null;
        this._scopeStakeholderId = (document.getElementById('scope-stakeholders-id') || {}).value || null;
        this._scopeConstraintId = (document.getElementById('scope-constraints-id') || {}).value || null;
        this._onPrincipleChange();
    },

    // Step 5: Load implementation roadmap (Phase F)
    loadRoadmap: async function() {
        let self = this;
        let container = document.getElementById('roadmap-content');
        if (!container) return;

        safeHTML(container,
            '<div class="text-center py-8 text-muted-foreground">' +
            '<i data-lucide="loader" class="h-8 w-8 mx-auto mb-2 animate-spin"></i>' +
            '<p>Generating implementation roadmap from gap analysis...</p>' +
            '</div>');
        lucide.createIcons();

        try {
            // Step 1: Convert gaps to persisted roadmap items with auto work packages
            if (self.gapAnalysis && self.selectedCapabilities.length > 0) {
                let gapPayload = {
                    gaps: self.selectedCapabilities.map(function(c) {
                        return {
                            capability_id: parseInt(c.id),
                            capability_type: 'business',
                            name: c.name,
                            gap_types: [self.gapAnalysis.gap_severity === 'high' ? 'coverage' : 'quality'],
                            priority: self.gapAnalysis.gap_severity || 'medium',
                            level: 2
                        };
                    }),
                    create_work_packages: true,
                    work_package_template: 'auto'
                };
                try {
                    await fetch('/api/roadmap/gaps/convert', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(gapPayload)
                    });
                } catch (convertErr) {
                    console.warn('Gap conversion failed (non-blocking):', convertErr);
                }
            }

            // Step 2: Fetch roadmap summary, work packages, and critical path in parallel
            let summaryRes = fetch('/api/roadmap-builder/summary');
            let wpRes = fetch('/api/roadmap-builder/work-packages?limit=20');
            let timelineRes = fetch('/api/roadmap-builder/timeline?group_by=priority');
            let critPathRes = fetch('/api/roadmap-builder/critical-path');

            let results = await Promise.allSettled([summaryRes, wpRes, timelineRes, critPathRes]);

            let summaryData = results[0].status === 'fulfilled' ? await results[0].value.json() : {};
            let wpData = results[1].status === 'fulfilled' ? await results[1].value.json() : {};
            let timelineData = results[2].status === 'fulfilled' ? await results[2].value.json() : {};
            let critPathData = results[3].status === 'fulfilled' ? await results[3].value.json() : {};

            let summary = (summaryData.success && summaryData.data) ? summaryData.data : {};
            let workPackages = (wpData.success && wpData.data && wpData.data.work_packages) ? wpData.data.work_packages : [];
            let timeline = (timelineData.success && timelineData.data && timelineData.data.groups) ? timelineData.data.groups : [];
            let critPath = (critPathData.success && critPathData.data) ? critPathData.data : {};

            self.roadmapData = { summary: summary, work_packages: workPackages, timeline: timeline, critical_path: critPath };
            self.persistAssistantData();
            self.renderRoadmap(self.roadmapData);
        } catch (err) {
            console.error('Error generating roadmap (trying ArchiMate elements):', err);
            // AWIZ-012: persist ArchiMate WorkPackage/Deliverable/Plateau chain as fallback
            let capId = self.selectedCapabilityId || (self.selectedCapability && self.selectedCapability.id);
            fetch('/api/architecture-assistant/roadmap-elements', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    capability_id: capId,
                    gap_elements: (self.gapAnalysis && self.gapAnalysis.gap_elements) ? self.gapAnalysis.gap_elements : [],
                    solution_option: self.selectedOption || null
                })
            }).then(function(r) { return r.json(); }).then(function(data) {
                if (data.work_packages && data.work_packages.length) {
                    let wpsHtml = '<div class="space-y-3">' +
                        '<div class="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-700">ArchiMate WorkPackage elements persisted. <a href="/roadmap-builder/" class="underline">View in Roadmap Builder</a></div>' +
                        data.work_packages.map(function(wp) {
                            return '<div class="flex gap-3 p-4 border border-border rounded-lg">' +
                                '<div class="flex-none text-xs text-muted-foreground w-20 text-right">Wks ' + wp.start_week + '–' + wp.end_week + '</div>' +
                                '<div class="font-medium text-sm">' + wp.name + '</div>' +
                                '</div>';
                        }).join('') + '</div>';
                    safeHTML(container, wpsHtml);
                } else {
                    self._renderFallbackRoadmap(container);
                }
            }).catch(function() { self._renderFallbackRoadmap(container); });
        }
    },

    _renderFallbackRoadmap: function(container) {
        let self = ArchAssistant;
        let wks = (self.selectedOption && self.selectedOption.implementation_weeks) ? self.selectedOption.implementation_weeks : 24;
        let phases = [
            ['Discovery & Design', 'Weeks 1–4', 'Requirements gathering, architecture blueprint, stakeholder alignment'],
            ['Build & Integrate', 'Weeks 5–' + (wks - 2), 'Implement, test, data migration, integration validation'],
            ['Go-Live', 'Final ' + Math.max(2, Math.round(wks * 0.15)) + ' weeks', 'Deploy, hypercare, stabilisation, lessons learned']
        ];
        let html = '<div class="space-y-4">' +
            '<div class="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">Showing estimated roadmap based on selected option. <a href="/roadmap-builder/" class="underline font-medium">Open Roadmap Builder</a> for full planning.</div>';
        phases.forEach(function(p, i) {
            html += '<div class="flex gap-4 p-4 border border-border rounded-lg">' +
                '<div class="flex-none w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">' + (i + 1) + '</div>' +
                '<div><div class="font-medium">' + p[0] + '</div><div class="text-xs text-muted-foreground mb-1">' + p[1] + '</div><div class="text-sm">' + p[2] + '</div></div>' +
                '</div>';
        });
        html += '</div>';
        safeHTML(container, html);
    },

    renderRoadmap: function(data) {
        let container = document.getElementById('roadmap-content');
        let summary = data.summary || {};
        let workPackages = data.work_packages || [];
        let timeline = data.timeline || [];
        let critPath = data.critical_path || {};

        // Summary cards
        let totalWP = summary.total_work_packages || workPackages.length;
        let completedWP = summary.completed_count || 0;
        let completionRate = summary.completion_rate || 0;
        let overdueCount = summary.overdue_count || 0;
        let totalCost = summary.total_estimated_cost || 0;

        let summaryHtml = '<div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Work Packages</div><div class="text-2xl font-bold">' + totalWP + '</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Completed</div><div class="text-2xl font-bold text-emerald-600">' + completedWP + '</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Completion</div><div class="text-2xl font-bold">' + Math.round(completionRate) + '%</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Overdue</div><div class="text-2xl font-bold ' + (overdueCount > 0 ? 'text-destructive' : '') + '">' + overdueCount + '</div></div>' +
            '<div class="p-4 border border-border rounded-lg text-center"><div class="text-sm text-muted-foreground mb-1">Est. Cost</div><div class="text-2xl font-bold">' + (totalCost > 0 ? '$' + (totalCost / 1000).toFixed(0) + 'K' : 'TBD') + '</div></div>' +
            '</div>';

        // Critical path info
        let critHtml = '';
        if (critPath.critical_path && critPath.critical_path.length > 0) {
            critHtml = '<div class="p-4 bg-muted/50 border border-border rounded-lg mb-6">' +
                '<h3 class="font-medium text-sm mb-3 flex items-center gap-2">' +
                '<i data-lucide="route" class="h-4 w-4 text-primary"></i>Critical Path (' + critPath.critical_path_length + ' items, ' + (critPath.total_duration || 0) + ' days)</h3>' +
                '<div class="flex flex-wrap gap-2">' +
                critPath.critical_path.map(function(cp) {
                    let statusClass = cp.status === 'completed' ? 'bg-emerald-500/10 text-emerald-700 border-emerald-500/30' :
                        cp.status === 'in_progress' ? 'bg-primary/10 text-primary border-primary/30' :
                        'bg-muted text-muted-foreground border-border';
                    return '<span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border ' + statusClass + '">' +
                        cp.name + ' <span class="ml-1 opacity-60">(' + (cp.duration || 0) + 'd)</span></span>';
                }).join('<i data-lucide="arrow-right" class="h-3 w-3 text-muted-foreground shrink-0"></i>') +
                '</div></div>';
        }

        // Work packages by priority (timeline groups)
        let wpHtml = '';
        if (timeline.length > 0) {
            wpHtml = '<div class="space-y-4">';
            timeline.forEach(function(group) {
                let priorityLabel = (group.name || 'Other').charAt(0).toUpperCase() + (group.name || 'other').slice(1);
                let priorityColor = group.name === 'high' ? 'text-destructive' : group.name === 'medium' ? 'text-amber-600' : 'text-emerald-600';
                wpHtml += '<div>' +
                    '<h3 class="font-medium text-sm mb-2 flex items-center gap-2 ' + priorityColor + '">' +
                    '<i data-lucide="flag" class="h-4 w-4"></i>' + priorityLabel + ' Priority (' + (group.items || []).length + ')</h3>' +
                    '<div class="space-y-2">';
                (group.items || []).forEach(function(wp) {
                    let statusBadge = wp.status === 'completed' ? 'bg-emerald-500/10 text-emerald-700' :
                        wp.status === 'in_progress' ? 'bg-primary/10 text-primary' :
                        wp.status === 'blocked' ? 'bg-destructive/10 text-destructive' :
                        'bg-muted text-muted-foreground';
                    let pct = wp.percent_complete || 0;
                    wpHtml += '<div class="p-3 border border-border rounded-lg flex items-center gap-4">' +
                        '<div class="flex-1 min-w-0">' +
                        '<div class="font-medium text-sm truncate">' + (wp.name || 'Untitled') + '</div>' +
                        '<div class="text-xs text-muted-foreground mt-0.5">' +
                        (wp.start_date ? wp.start_date : '') +
                        (wp.start_date && wp.end_date ? ' → ' : '') +
                        (wp.end_date ? wp.end_date : '') +
                        '</div></div>' +
                        '<div class="w-24 shrink-0">' +
                        '<div class="h-2 bg-muted rounded-full overflow-hidden"><div class="h-full bg-primary rounded-full" style="width:' + pct + '%"></div></div>' + /* ratchet-ok: dynamic progress width */
                        '<div class="text-xs text-muted-foreground text-center mt-0.5">' + pct + '%</div></div>' +
                        '<span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ' + statusBadge + ' shrink-0">' + (wp.status || 'planned') + '</span>' +
                        '</div>';
                });
                wpHtml += '</div></div>';
            });
            wpHtml += '</div>';
        } else if (workPackages.length > 0) {
            // Fallback: flat list if no timeline groups
            wpHtml = '<div class="space-y-3">' +
                '<h3 class="font-medium text-sm text-muted-foreground uppercase tracking-wider">Work Packages</h3>' +
                workPackages.map(function(wp) {
                    let statusBadge = wp.status === 'completed' ? 'bg-emerald-500/10 text-emerald-700' :
                        wp.status === 'in_progress' ? 'bg-primary/10 text-primary' :
                        'bg-muted text-muted-foreground';
                    return '<div class="p-3 border border-border rounded-lg flex items-center justify-between">' +
                        '<div><div class="font-medium text-sm">' + (wp.name || 'Untitled') + '</div>' +
                        '<div class="text-xs text-muted-foreground mt-1">' + (wp.description || '') + '</div></div>' +
                        '<span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ' + statusBadge + ' shrink-0">' + (wp.status || 'planned') + '</span>' +
                        '</div>';
                }).join('') +
                '</div>';
        } else {
            wpHtml = '<div class="text-center py-6 text-muted-foreground">' +
                '<i data-lucide="package" class="h-6 w-6 mx-auto mb-2"></i>' +
                '<p class="text-sm">No work packages generated yet. Use the Roadmap Builder to create them.</p>' +
                '</div>';
        }

        safeHTML(container, summaryHtml + critHtml + wpHtml);
        lucide.createIcons();
    },

    showToast: function(message, type) {
        type = type || 'info';
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            alert(message);
        }
    }
};

// Attach analyzeOptions method to ArchAssistant
ArchAssistant.analyzeOptions = async function() {
    let self = this;
    if (!self.solutionOptions || self.solutionOptions.length === 0) {
        self.showToast('No options available to analyze', 'info');
        return;
    }
    let container = document.getElementById('analysis-summary');
    if (container) safeHTML(container, '<div class="text-center py-4 text-muted-foreground"><i data-lucide="loader" class="h-6 w-6 inline animate-spin mr-2"></i>Analyzing options...</div>');
    let payloadOptions = self.solutionOptions.map(function(opt) {
        return {
            id: opt.id,
            name: opt.name,
            vendor_name: opt.vendor || opt.vendor_name,
            description: opt.description || '',
            cost_estimate: opt.cost_estimate || opt.cost,
            capability_coverage: opt.capability_coverage || opt.fit_score || opt.score || 0,
            pros: opt.pros || [],
            cons: opt.cons || []
        };
    });
    try {
        let res = await fetch('/api/architecture-assistant/analyze-options', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ options_data: payloadOptions, capability_id: self.selectedCapability?.id })
        });
        let data = await res.json();
        if (data.success && data.options) {
            self.solutionOptions = data.options;
            self.persistAssistantData();
            self.renderSolutionOptions(self.solutionOptions);
            if (container) {
                safeHTML(container, data.decision_rationale ? '<div class="p-4 bg-primary/5 border border-primary/20 rounded-lg"><h4 class="font-medium mb-2">Decision Rationale</h4><p class="text-sm text-primary/90">' + data.decision_rationale + '</p></div>' : '<div class="p-2 text-sm text-muted-foreground">Analysis complete</div>');
            }
            document.getElementById('btn-step-4-next').disabled = false;
        } else {
            if (container) safeHTML(container, '');
            self.showToast('Option analysis failed', 'error');
        }
    } catch (e) {
        console.error('Error analyzing options:', e);
        if (container) safeHTML(container, '');
        self.showToast('Option analysis error', 'error');
    }
};

// Initialize when DOM ready and bind analyze button
document.addEventListener('DOMContentLoaded', function() {
    ArchAssistant.init();
    let analyzeBtn = document.getElementById('btn-analyze-options');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', function() { ArchAssistant.analyzeOptions(); });
    }

    // Select Capabilities button
    let selectCapBtn = document.getElementById('btn-select-capabilities');
    if (selectCapBtn) {
        selectCapBtn.addEventListener('click', function() { ArchAssistant.openMappingModal(); });
    }

    // Capability grid card click delegation — must be set up after init
    // Uses event delegation so it survives safeHTML re-renders
    let capList = document.getElementById('capabilities-list');
    if (capList) {
        capList.addEventListener('click', function(e) {
            let card = e.target.closest('.option-card[data-id]');
            if (card) {
                ArchAssistant.selectCapability(card.getAttribute('data-id'));
            }
        });
    }

    // Quick action cards — wired via data-action attributes
    document.querySelectorAll('[data-action]').forEach(function(card) {
        card.addEventListener('click', function() {
            let action = this.getAttribute('data-action');
            if (action === 'pipeline') {
                ArchAssistant.runFullPipeline();
            } else {
                ArchAssistant.quickAction(action);
            }
        });
    });
});
