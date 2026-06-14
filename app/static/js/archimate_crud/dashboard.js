let APP_CONFIG = window.__APP_CONFIG__ || {};

document.addEventListener('alpine:init', function() {
    Alpine.data('archDashboard', function() {
        return {
            activeTab: 'motivation',
            elements: [],
            pagination: { page: 1, pages: 0, per_page: 25, total: 0, has_next: false, has_prev: false },
            loading: false,
            searchQuery: '',
            typeFilter: '',
            perPage: 25,
            currentPage: 1,
            sortBy: 'name',
            sortOrder: 'asc',
            totalCount: 0,
            layerCounts: {},
            layerConfig: APP_CONFIG.layerConfig || {},

            // Card filter and grouping
            cardFilter: '',
            groupByType: false,
            collapsedTypes: {},
            sourceFilter: '',

            bulkMode: false,
            selectedIds: [],
            selectAll: false,

            editingElement: null,
            formData: { element_type: '', name: '', description: '' },
            formError: '',
            saving: false,

            showDeleteConfirm: false,
            deletingElement: null,
            deleting: false,

            // ARCH-016: validation state
            validating: false,
            showValidationPanel: false,
            validationResults: null,

            // ARCH-016: viewpoint filter
            viewpointKey: 'basic',
            availableViewpoints: {},
            viewpointTypeFilter: [],

            // Layer-specific view modes (swimlane, cards, lifecycle, table)
            layerViewMode: JSON.parse(localStorage.getItem('archLayerViewMode') || '{}'),
            layerAltViews: {
                motivation: 'swimlane',
                strategy: 'cards',
                technology: 'lifecycle'
            },

            get currentViewMode() {
                let saved = this.layerViewMode[this.activeTab];
                if (saved) return saved;
                return this.layerAltViews[this.activeTab] || 'table';
            },

            get hasAltView() {
                return !!this.layerAltViews[this.activeTab];
            },

            toggleViewMode() {
                let current = this.currentViewMode;
                let alt = this.layerAltViews[this.activeTab];
                this.layerViewMode[this.activeTab] = current === 'table' ? (alt || 'table') : 'table';
                localStorage.setItem('archLayerViewMode', JSON.stringify(this.layerViewMode));
            },

            // Health panel state
            showHealthPanel: false,

            // ARC-004: advanced filter panel
            showAdvanced: false,
            filterScope: '',
            filterBuildingBlock: '',
            filterPlateau: '',
            filterHasRels: '',
            filterHasSolutions: '',

            // ARC-006: element detail slide-out panel
            showDetailPanel: false,
            detailElement: null,
            detailData: null,
            detailLoading: false,
            detailEditing: false,
            detailForm: { name: '', layer: '', element_type: '', description: '' },
            detailSaving: false,
            detailSaved: false,

            get typeCounts() {
                const counts = {};
                for (let i = 0; i < this.elements.length; i++) {
                    let t = this.elements[i].element_type || this.elements[i].type || 'Unknown';
                    counts[t] = (counts[t] || 0) + 1;
                }
                return counts;
            },

            get currentLayerTypes() {
                let cfg = this.layerConfig[this.activeTab];
                return cfg ? cfg.elements : [];
            },

            get elementGroups() {
                let filtered = this.elements;
                if (this.cardFilter === 'orphaned') {
                    filtered = filtered.filter(function(el) { return !el.rel_count || el.rel_count === 0; });
                } else if (this.cardFilter === 'undocumented') {
                    filtered = filtered.filter(function(el) { return !el.description || el.description.trim() === ''; });
                }
                let groups = {};
                for (let i = 0; i < filtered.length; i++) {
                    let el = filtered[i];
                    let t = el.element_type;
                    if (!groups[t]) groups[t] = { type: t, elements: [], count: 0 };
                    groups[t].elements.push(el);
                    groups[t].count++;
                }
                return Object.values(groups);
            },

            get sourceCounts() {
                let portfolio = 0, architecture = 0;
                for (let i = 0; i < this.elements.length; i++) {
                    let el = this.elements[i];
                    if (el.source === 'portfolio') portfolio++;
                    else architecture++;
                }
                return { portfolio: portfolio, architecture: architecture };
            },

            get healthStats() {
                let connected = 0, orphaned = 0, missing_desc = 0;
                for (let i = 0; i < this.elements.length; i++) {
                    let el = this.elements[i];
                    if (el.rel_count && el.rel_count > 0) connected++;
                    else orphaned++;
                    if (!el.description || el.description.trim() === '') missing_desc++;
                }
                return { total_relationships: connected, connected: connected, orphaned: orphaned, missing_description: missing_desc };
            },

            get layerTotal() {
                return this.pagination ? (this.pagination.total || 0) : 0;
            },

            toggleTypeGroup(type) {
                this.collapsedTypes[type] = !this.collapsedTypes[type];
            },

            toggleCardFilter(filter) {
                this.cardFilter = this.cardFilter === filter ? '' : filter;
            },

            get activeLayerLabel() {
                let cfg = this.layerConfig[this.activeTab];
                return cfg ? cfg.name : this.activeTab;
            },

            clearAllFilters() {
                this.searchQuery = '';
                this.typeFilter = '';
                this.sourceFilter = '';
                this.filterScope = '';
                this.filterBuildingBlock = '';
                this.filterPlateau = '';
                this.filterHasRels = '';
                this.filterHasSolutions = '';
                this.currentPage = 1;
                this.loadElements();
            },

            get detailFormLayerTypes() {
                return (this.layerConfig[this.detailForm.layer] || {}).elements || [];
            },

            init() {
                let urlLayer = new URLSearchParams(window.location.search).get('layer');
                if (urlLayer && this.layerConfig[urlLayer]) {
                    this.activeTab = urlLayer;
                }
                let urlPanel = new URLSearchParams(window.location.search).get('panel');
                if (urlPanel === 'health') {
                    this.showHealthPanel = true;
                }
                this.loadElements();
                this.loadAllLayerCounts();
                this.loadViewpoints();
            },

            switchTab(layerKey) {
                if (this.activeTab === layerKey) return;
                this.activeTab = layerKey;
                this.searchQuery = '';
                this.typeFilter = '';
                this.currentPage = 1;
                this.selectedIds = [];
                this.selectAll = false;
                history.replaceState(null, '', '?layer=' + layerKey);
                this.loadElements();
            },

            async loadElements() {
                this.loading = true;
                try {
                    let params = new URLSearchParams({
                        page: this.currentPage,
                        per_page: this.perPage,
                        sort_by: this.sortBy,
                        sort_order: this.sortOrder,
                    });
                    if (this.searchQuery) params.set('search', this.searchQuery);
                    if (this.sourceFilter) params.set('source', this.sourceFilter);
                    // Viewpoint type filter takes precedence over manual type filter
                    if (this.viewpointTypeFilter.length > 0 && !this.typeFilter) {
                        params.set('element_type', this.viewpointTypeFilter.join(','));
                    } else if (this.typeFilter) {
                        params.set('element_type', this.typeFilter);
                    }

                    let resp = await fetch(
                        '/architecture/api/layer/' + this.activeTab + '/elements?' + params,
                        { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
                    );
                    let data = await resp.json();
                    this.elements = data.elements;
                    this.pagination = data.pagination;
                    this.layerCounts[this.activeTab] = data.pagination.total;
                } catch (err) {
                    console.error('Failed to load elements:', err);
                } finally {
                    this.loading = false;
                    this.$nextTick(function() { if (typeof lucide !== 'undefined') lucide.createIcons(); });
                }
            },

            async loadAllLayerCounts() {
                let self = this;
                let layerKeys = Object.keys(this.layerConfig);
                // Use the fast /count endpoint to avoid loading all rows into Python.
                // Falls back to the elements endpoint if count endpoint is unavailable.
                for (let i = 0; i < layerKeys.length; i++) {
                    let layerKey = layerKeys[i];
                    try {
                        let resp = await fetch(
                            '/architecture/api/layer/' + layerKey + '/count',
                            { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
                        );
                        if (resp.ok) {
                            let data = await resp.json();
                            self.layerCounts[layerKey] = data.total || 0;
                        } else {
                            // Fallback: elements endpoint
                            let r2 = await fetch(
                                '/architecture/api/layer/' + layerKey + '/elements?per_page=1',
                                { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
                            );
                            let d2 = await r2.json();
                            self.layerCounts[layerKey] = (d2.pagination && d2.pagination.total) || 0;
                        }
                        self.totalCount = Object.values(self.layerCounts).reduce(function(a, b) { return a + b; }, 0);
                    } catch (e) {
                        console.warn('Layer count failed for', layerKey, e);
                        self.layerCounts[layerKey] = 0;
                    }
                }
            },

            async loadViewpoints() {
                try {
                    let resp = await fetch('/api/archimate/viewpoints', { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    this.availableViewpoints = await resp.json();
                } catch (e) { console.warn('Could not load viewpoints', e); }
            },

            applyViewpoint() {
                let vp = this.availableViewpoints[this.viewpointKey];
                this.viewpointTypeFilter = (vp && vp.element_types && vp.element_types.length) ? vp.element_types : [];
                this.typeFilter = '';
                this.currentPage = 1;
                this.loadElements();
            },

            toggleSort(column) {
                if (this.sortBy === column) {
                    this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortBy = column;
                    this.sortOrder = 'asc';
                }
                this.currentPage = 1;
                this.loadElements();
            },

            goToPage(page) {
                this.currentPage = page;
                this.loadElements();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            },

            toggleSelectAll() {
                if (this.selectAll) {
                    this.selectedIds = this.elements.map(function(el) { return el.id + ':' + el.element_type; });
                } else {
                    this.selectedIds = [];
                }
            },

            detailUrl(el) {
                return '/architecture/' + this.activeTab + '/' + el.element_type + '/' + el.id;
            },
            editPageUrl(el) {
                if (!el) return '#';
                return '/architecture/' + this.activeTab + '/' + el.element_type + '/' + el.id + '/edit';
            },

            formatTypeName(type) {
                if (!type) return '';
                return type.replace(/([A-Z])/g, ' $1').trim();
            },
            truncate(text, len) {
                if (!text) return '';
                return text.length > len ? text.substring(0, len) + '...' : text;
            },

            getLifecyclePhase(el) {
                if (!el.properties) return 'unset';
                let props = el.properties;
                if (typeof props === 'string') {
                    try { props = JSON.parse(props); } catch(e) { return 'unset'; }
                }
                let phase = props.lifecycle || 'unset';
                let valid = ['current', 'transitional', 'target', 'retire', 'unset'];
                return valid.indexOf(phase) >= 0 ? phase : 'unset';
            },

            groupElementsBy(keyFn) {
                let groups = {};
                let filtered = this.elements.filter(el => {
                    if (!this.searchQuery) return true;
                    return el.name.toLowerCase().indexOf(this.searchQuery.toLowerCase()) >= 0;
                });
                for (let i = 0; i < filtered.length; i++) {
                    let key = keyFn(filtered[i]);
                    if (!groups[key]) groups[key] = [];
                    groups[key].push(filtered[i]);
                }
                return groups;
            },

            // ARCH-016: run full model validation
            async runValidation() {
                this.validating = true;
                try {
                    const r = await fetch('/architecture/api/archimate/validate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{}',
                    });
                    this.validationResults = await r.json();
                    this.showValidationPanel = true;
                } catch (e) {
                    this.validationResults = { element_errors: 0, element_warnings: 0,
                        relationship_errors: 0, relationship_warnings: 0,
                        element_issues: [{ element: { id: 0, name: 'Error', layer: '' },
                            issues: [{ severity: 'error', message: e.message }] }],
                        relationship_issues: [] };
                    this.showValidationPanel = true;
                }
                this.validating = false;
            },

            openCreateModal() {
                this.editingElement = null;
                this.formData = { element_type: '', name: '', description: '' };
                this.formError = '';
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('archimate-form-modal');
                }
            },
            openEditModal(el) {
                this.editingElement = el;
                this.formData = {
                    element_type: el.element_type,
                    name: el.name,
                    description: el.description || '',
                };
                this.formError = '';
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('archimate-form-modal');
                }
            },
            async submitForm() {
                this.formError = '';
                if (!this.formData.name.trim()) {
                    this.formError = 'Name is required';
                    return;
                }
                if (!this.editingElement && !this.formData.element_type) {
                    this.formError = 'Please select an element type';
                    return;
                }
                this.saving = true;
                try {
                    let url;
                    if (this.editingElement) {
                        url = '/architecture/' + this.activeTab + '/' + this.editingElement.element_type + '/' + this.editingElement.id + '/edit';
                    } else {
                        url = '/architecture/' + this.activeTab + '/' + this.formData.element_type + '/new';
                    }
                    let resp = await fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: this.formData.name,
                            description: this.formData.description,
                        }),
                    });
                    let data = await resp.json();
                    if (data.success) {
                        if (window.Platform && window.Platform.modal) {
                            window.Platform.modal.close('archimate-form-modal');
                        }
                        this.loadElements();
                        this.loadAllLayerCounts();
                    } else {
                        this.formError = data.error || 'Operation failed';
                    }
                } catch (err) {
                    this.formError = 'Error: ' + err.message;
                } finally {
                    this.saving = false;
                }
            },

            confirmDelete(el) {
                this.deletingElement = el;
                this.showDeleteConfirm = true;
            },
            async executeDelete() {
                if (!this.deletingElement) return;
                this.deleting = true;
                try {
                    let el = this.deletingElement;
                    let resp = await fetch(
                        '/architecture/' + this.activeTab + '/' + el.element_type + '/' + el.id + '/delete',
                        { method: 'POST', headers: { 'Content-Type': 'application/json' } }
                    );
                    let data = await resp.json();
                    if (data.success) {
                        this.showDeleteConfirm = false;
                        this.deletingElement = null;
                        this.loadElements();
                        this.loadAllLayerCounts();
                    } else {
                        Platform.toast.error(data.error || 'Delete failed');
                    }
                } catch (err) {
                    Platform.toast.error('Error: ' + err.message);
                } finally {
                    this.deleting = false;
                }
            },

            async bulkDeleteSelected() {
                if (this.selectedIds.length === 0) return;
                let grouped = {};
                for (let i = 0; i < this.selectedIds.length; i++) {
                    let key = this.selectedIds[i];
                    let parts = key.split(':');
                    let id = parts[0];
                    let type = parts[1];
                    if (!grouped[type]) grouped[type] = [];
                    grouped[type].push(parseInt(id));
                }
                let self = this;
                let modalId = window.modalManager.createModal({
                    title: 'Delete Elements',
                    content: '<p class="text-sm text-muted-foreground">Delete ' + this.selectedIds.length + ' element(s)? This cannot be undone.</p>',
                    size: 'small',
                    buttons: [
                        { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                        { text: 'Delete', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'delete', handler: async function() {
                            try {
                                let entries = Object.entries(grouped);
                                for (let j = 0; j < entries.length; j++) {
                                    let type = entries[j][0];
                                    let ids = entries[j][1];
                                    await fetch('/architecture/' + self.activeTab + '/' + type + '/bulk-delete', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ ids: ids }),
                                    });
                                }
                                self.selectedIds = [];
                                self.selectAll = false;
                                self.loadElements();
                                self.loadAllLayerCounts();
                            } catch (err) {
                                Platform.toast.error('Error during bulk delete');
                            }
                        } }
                    ]
                });
                window.modalManager.open(modalId);
            },
            // ARC-006: detail panel methods
            async openDetailPanel(el) {
                this.showDetailPanel = true;
                this.detailEditing = false;
                this.detailSaved = false;
                this.detailElement = el;
                this.detailData = null;
                this.detailLoading = true;
                try {
                    let resp = await fetch('/architecture/api/elements/' + el.id + '/detail', {
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    this.detailData = await resp.json();
                } catch (e) {
                    this.detailData = { error: e.message };
                } finally {
                    this.detailLoading = false;
                    this.$nextTick(function() { if (typeof lucide !== 'undefined') lucide.createIcons(); });
                }
            },

            closeDetailPanel() {
                this.showDetailPanel = false;
                this.detailElement = null;
                this.detailData = null;
                this.detailEditing = false;
            },

            startDetailEdit() {
                if (!this.detailElement) return;
                let data = this.detailData || {};
                this.detailForm = {
                    name: data.name || this.detailElement.name || '',
                    layer: data.layer || this.activeTab,
                    element_type: data.type || this.detailElement.element_type || '',
                    description: data.description || '',
                };
                this.detailEditing = true;
            },

            onDetailLayerChange() {
                let layerTypes = (this.layerConfig[this.detailForm.layer] || {}).elements || [];
                if (!layerTypes.includes(this.detailForm.element_type)) {
                    this.detailForm.element_type = layerTypes[0] || '';
                }
            },

            async saveDetailEdit() {
                if (!this.detailElement) return;
                this.detailSaving = true;
                this.detailSaved = false;
                try {
                    let resp = await fetch('/architecture/api/elements/' + this.detailElement.id, {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: JSON.stringify(this.detailForm),
                    });
                    let data = await resp.json();
                    if (data.success) {
                        this.detailSaved = true;
                        this.detailEditing = false;
                        this.detailData = Object.assign({}, this.detailData, this.detailForm, { type: this.detailForm.element_type });
                        this.loadElements();
                        let self = this;
                        setTimeout(function() { self.detailSaved = false; }, 3000);
                    } else {
                        Platform.toast.error(data.error || 'Save failed');
                    }
                } catch (e) {
                    Platform.toast.error('Error: ' + e.message);
                } finally {
                    this.detailSaving = false;
                }
            },

            bulkExportSelected() {
                let grouped = {};
                for (let i = 0; i < this.selectedIds.length; i++) {
                    let key = this.selectedIds[i];
                    let parts = key.split(':');
                    let id = parts[0];
                    let type = parts[1];
                    if (!grouped[type]) grouped[type] = [];
                    grouped[type].push(id);
                }
                let entries = Object.entries(grouped);
                for (let j = 0; j < entries.length; j++) {
                    let type = entries[j][0];
                    let ids = entries[j][1];
                    let idParams = ids.map(function(id) { return 'ids=' + id; }).join('&');
                    window.open('/architecture/' + this.activeTab + '/' + type + '/export?format=json&' + idParams, '_blank');
                }
            },
        };
    });
});

document.addEventListener('DOMContentLoaded', function() {
    if (typeof lucide !== 'undefined') lucide.createIcons();
});
