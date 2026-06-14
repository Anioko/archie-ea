/**
 * APQC Browser Manager - Frontend JavaScript Integration
 * Handles APQC hierarchy tree navigation and search functionality
 */

class APQCBrowserManager {
    constructor() {
        this.apqcData = [];
        this.selectedProcess = null;
        this.expandedNodes = new Set();
        this.searchResults = [];
        this.currentFilters = {
            level: '',
            industry: '',
            search: ''
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAPQCData();
        this.loadIndustryVariants();
    }

    bindEvents() {
        // Search functionality
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }

        // Filters
        const levelFilter = document.getElementById('level-filter');
        if (levelFilter) {
            levelFilter.addEventListener('change', (e) => {
                this.currentFilters.level = e.target.value;
                this.applyFilters();
            });
        }

        const industryFilter = document.getElementById('industry-filter');
        if (industryFilter) {
            industryFilter.addEventListener('change', (e) => {
                this.currentFilters.industry = e.target.value;
                this.applyFilters();
            });
        }

        // Expand/Collapse all
        const expandAll = document.getElementById('expand-all');
        if (expandAll) {
            expandAll.addEventListener('click', () => {
                this.expandAll();
            });
        }

        const collapseAll = document.getElementById('collapse-all');
        if (collapseAll) {
            collapseAll.addEventListener('click', () => {
                this.collapseAll();
            });
        }

        // Clear search
        const clearSearch = document.getElementById('clear-search');
        if (clearSearch) {
            clearSearch.addEventListener('click', () => {
                this.clearSearch();
            });
        }
    }

    async loadAPQCData() {
        try {
            this.showLoading(true);
            const response = await fetch('/api/apqc/tree');
            const data = await response.json();

            if (data.success) {
                this.apqcData = data.tree || [];
                this.displayTree();
                this.updateStatistics(data.total_processes || 0);
            } else {
                this.showError('Failed to load APQC data: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading APQC data:', error);
            this.showError('Error loading APQC data');
        } finally {
            this.showLoading(false);
        }
    }

    async loadIndustryVariants() {
        try {
            const response = await fetch('/api/apqc/variants');
            const data = await response.json();

            if (data.success) {
                this.populateIndustryFilter(data.variants || []);
            }
        } catch (error) {
            console.error('Error loading industry variants:', error);
        }
    }

    populateIndustryFilter(variants) {
        const industryFilter = document.getElementById('industry-filter');
        if (!industryFilter) return;

        const currentValue = industryFilter.value;

        // Clear existing options except the first one
        while (industryFilter.children.length > 1) {
            industryFilter.removeChild(industryFilter.lastChild);
        }

        // Add variants
        variants.forEach(variant => {
            const option = document.createElement('option');
            option.value = variant;
            option.textContent = variant;
            industryFilter.appendChild(option);
        });

        // Restore previous selection
        if (currentValue) {
            industryFilter.value = currentValue;
        }
    }

    displayTree() {
        const container = document.getElementById('apqc-tree');
        if (!container) return;

        if (this.apqcData.length === 0) {
            safeHTML(container, `
                <div class="text-center py-8 text-muted-foreground">
                    <i class="fas fa-sitemap text-4xl mb-4"></i>
                    <p>No APQC data available</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.renderTreeNodes(this.apqcData, 0));
    }

    renderTreeNodes(nodes, level = 0) {
        return nodes.map(node => `
            <div class="tree-node" data-level="${level}" data-id="${node.id}" data-code="${node.code}">
                <div class="tree-node-content" style="padding-left: ${level * 20}px">
                    <i class="fas fa-chevron-right tree-toggle ${this.expandedNodes.has(node.id) ? 'expanded' : ''}"
                       onclick="apqcBrowser.toggleNode(${node.id})"></i>
                    <i class="fas fa-${node.children && node.children.length > 0 ? 'folder' : 'file'} tree-icon"></i>
                    <span class="tree-label" onclick="apqcBrowser.selectNode(${node.id}); return false;">${node.code} ${node.name}</span>
                    <span class="tree-level">Level ${node.level || level + 1}</span>
                </div>
                <div class="tree-children ${this.expandedNodes.has(node.id) ? 'expanded' : 'hidden'}" id="children-${node.id}">
                    ${node.children ? this.renderTreeNodes(node.children, level + 1) : ''}
                </div>
            </div>
        `).join('');
    }

    toggleNode(nodeId) {
        if (this.expandedNodes.has(nodeId)) {
            this.expandedNodes.delete(nodeId);
        } else {
            this.expandedNodes.add(nodeId);
        }

        const childrenContainer = document.getElementById(`children-${nodeId}`);
        const toggle = document.querySelector(`[onclick="apqcBrowser.toggleNode(${nodeId})"]`);

        if (childrenContainer) {
            childrenContainer.classList.toggle('hidden');
            childrenContainer.classList.toggle('expanded');
        }

        if (toggle) {
            toggle.classList.toggle('expanded');
        }
    }

    async selectNode(nodeId) {
        try {
            this.showLoading(true);
            const response = await fetch(`/api/apqc/process/${nodeId}`);
            const data = await response.json();

            if (data.success) {
                this.selectedProcess = data.process;
                this.displayProcessDetails(data.process, data.hierarchy_path, data.auto_link_parents, data.child_processes);
            } else {
                this.showError('Failed to load process details: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading process details:', error);
            this.showError('Error loading process details');
        } finally {
            this.showLoading(false);
        }
    }

    displayProcessDetails(process, hierarchyPath, autoLinkParents, childProcesses) {
        const detailsContainer = document.getElementById('process-details');
        if (!detailsContainer) return;

        safeHTML(detailsContainer, `
            <div class="process-details">
                <div class="process-header">
                    <h3>${process.code} ${process.name}</h3>
                    <span class="level-badge level-${process.level}">Level ${process.level}</span>
                </div>

                <div class="process-description">
                    <p>${process.description || 'No description available'}</p>
                </div>

                ${hierarchyPath && hierarchyPath.length > 0 ? `
                <div class="hierarchy-path">
                    <h4>Hierarchy Path</h4>
                    <div class="breadcrumb">
                        ${hierarchyPath.map((item, index) => `
                            <span class="breadcrumb-item">
                                ${index > 0 ? '<i class="fas fa-chevron-right mx-2"></i>' : ''}
                                <a href="javascript:void(0)" onclick="apqcBrowser.selectNode(${item.id})">${item.code} ${item.name}</a>
                            </span>
                        `).join('')}
                    </div>
                </div>
                ` : ''}

                ${autoLinkParents && autoLinkParents.length > 0 ? `
                <div class="auto-link-parents">
                    <h4>Auto-Link Parent Processes</h4>
                    <div class="parent-list">
                        ${autoLinkParents.map(parent => `
                            <div class="parent-item">
                                <span class="parent-code">${parent.code}</span>
                                <span class="parent-name">${parent.name}</span>
                                <button onclick="apqcBrowser.autoLinkProcess(${parent.id})"
                                        class="px-2 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary">
                                    <i class="fas fa-link"></i> Link
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}

                ${childProcesses && childProcesses.length > 0 ? `
                <div class="child-processes">
                    <h4>Child Processes</h4>
                    <div class="child-list">
                        ${childProcesses.map(child => `
                            <div class="child-item">
                                <span class="child-code">${child.code}</span>
                                <span class="child-name">${child.name}</span>
                                <button onclick="apqcBrowser.selectNode(${child.id}); return false;"
                                        class="px-2 py-1 text-sm bg-muted/50 text-primary-foreground rounded hover:bg-muted-foreground/20">
                                    <i class="fas fa-arrow-right"></i> View
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}

                <div class="process-actions">
                    <button onclick="apqcBrowser.useProcessInMapping(${process.id})"
                            class="px-4 py-2 bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600">
                        <i class="fas fa-check"></i> Use in Mapping
                    </button>
                    <button onclick="apqcBrowser.viewProcessDetails(${process.id})"
                            class="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary">
                        <i class="fas fa-info-circle"></i> Full Details
                    </button>
                </div>
            </div>
        `);
    }

    async handleSearch(query) {
        this.currentFilters.search = query;

        if (query.trim() === '') {
            this.closeSearchResults();
            return;
        }

        try {
            this.showLoading(true);
            const response = await fetch(`/api/apqc/search?q=${encodeURIComponent(query)}&level=${this.currentFilters.level}&industry=${this.currentFilters.industry}&limit=20`);
            const data = await response.json();

            if (data.success) {
                this.searchResults = data.matches || [];
                this.displaySearchResults();
            } else {
                this.showError('Search failed: ' + data.error);
            }
        } catch (error) {
            console.error('Error searching:', error);
            this.showError('Error searching');
        } finally {
            this.showLoading(false);
        }
    }

    displaySearchResults() {
        const resultsContainer = document.getElementById('search-results');
        const treeContainer = document.getElementById('apqc-tree');

        if (!resultsContainer || !treeContainer) return;

        if (this.searchResults.length === 0) {
            safeHTML(resultsContainer, `
                <div class="text-center py-4 text-muted-foreground">
                    <i class="fas fa-search text-2xl mb-2"></i>
                    <p>No results found</p>
                </div>
            `);
            resultsContainer.classList.remove('hidden');
            return;
        }

        safeHTML(resultsContainer, `
            <div class="search-results-header">
                <h4>Search Results (${this.searchResults.length})</h4>
                <button onclick="apqcBrowser.closeSearchResults()" class="text-muted-foreground hover:text-foreground">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="search-results-list">
                ${this.searchResults.map(result => `
                    <div class="search-result-item" onclick="apqcBrowser.selectNode(${result.id}); return false;">
                        <div class="result-header">
                            <span class="result-code">${result.code}</span>
                            <span class="result-name">${result.name}</span>
                            <span class="result-level">Level ${result.level}</span>
                        </div>
                        <div class="result-description">
                            ${result.description ? result.description.substring(0, 150) + '...' : 'No description'}
                        </div>
                        <div class="result-score">
                            <span class="confidence-score">${(result.similarity_score * 100).toFixed(1)}% match</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `);

        resultsContainer.classList.remove('hidden');
        treeContainer.classList.add('hidden');
    }

    closeSearchResults() {
        const resultsContainer = document.getElementById('search-results');
        const treeContainer = document.getElementById('apqc-tree');
        const searchInput = document.getElementById('search-input');

        if (resultsContainer) {
            resultsContainer.classList.add('hidden');
        }
        if (treeContainer) {
            treeContainer.classList.remove('hidden');
        }
        if (searchInput) {
            searchInput.value = '';
        }

        this.currentFilters.search = '';
        this.searchResults = [];
    }

    applyFilters() {
        if (this.currentFilters.search) {
            this.handleSearch(this.currentFilters.search);
        } else {
            this.loadAPQCData();
        }
    }

    expandAll() {
        const allNodeIds = this.getAllNodeIds(this.apqcData);
        allNodeIds.forEach(nodeId => this.expandedNodes.add(nodeId));
        this.displayTree();
    }

    collapseAll() {
        this.expandedNodes.clear();
        this.displayTree();
    }

    getAllNodeIds(nodes) {
        let ids = [];
        nodes.forEach(node => {
            ids.push(node.id);
            if (node.children) {
                ids = ids.concat(this.getAllNodeIds(node.children));
            }
        });
        return ids;
    }

    async autoLinkProcess(parentId) {
        try {
            const response = await fetch('/api/apqc/auto-link', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    process_id: parentId
                })
            });

            const data = await response.json();
            if (data.success) {
                this.showSuccess(`Auto-linked ${data.auto_link_parents.length} parent processes`);
            } else {
                this.showError('Auto-link failed: ' + data.error);
            }
        } catch (error) {
            console.error('Error auto-linking:', error);
            this.showError('Error auto-linking processes');
        }
    }

    useProcessInMapping(processId) {
        // This would integrate with the import mapping workflow
        // For now, just show a success message
        this.showSuccess(`Process ${processId} selected for mapping`);

        // Could also store in a global variable or send to parent window
        if (window.parent && window.parent.selectAPQCProcess) {
            window.parent.selectAPQCProcess(processId);
        }
    }

    viewProcessDetails(processId) {
        // This could open a more detailed view or navigate to a details page
        window.open(`/dashboard/apqc-browser?process=${processId}`, '_blank');
    }

    updateStatistics(totalProcesses) {
        const statsContainer = document.getElementById('statistics');
        if (!statsContainer) return;

        safeHTML(statsContainer, `
            <div class="grid grid-cols-3 gap-4">
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${totalProcesses}</div>
                    <div class="text-sm text-muted-foreground">Total Processes</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-emerald-600">${this.expandedNodes.size}</div>
                    <div class="text-sm text-muted-foreground">Expanded Nodes</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${this.searchResults.length}</div>
                    <div class="text-sm text-muted-foreground">Search Results</div>
                </div>
            </div>
        `);
    }

    showLoading(show) {
        const loading = document.getElementById('loading');
        if (loading) {
            loading.classList.toggle('hidden', !show);
        }
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg z-50 ${
            type === 'success' ? 'bg-emerald-500 text-primary-foreground' : 'bg-destructive text-primary-foreground'
        }`;
        safeHTML(notification, `
            <div class="flex items-center space-x-2">
                <i class="fas fa-${type === 'success' ? 'check' : 'exclamation-triangle'}"></i>
                <span>${message}</span>
            </div>
        `);
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.apqcBrowser = new APQCBrowserManager();
});
