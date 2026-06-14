/**
 * Vendor Catalog Manager - Frontend JavaScript Integration
 * Handles vendor product catalog browsing, search, and AI extraction testing
 */

class VendorCatalogManager {
    constructor() {
        this.vendors = [];
        this.productFamilies = [];
        this.products = [];
        this.selectedVendor = null;
        this.selectedFamily = null;
        this.filters = {
            search: '',
            tier: '',
            category: ''
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadVendorCatalog();
        this.loadCategories();
        this.loadTiers();
    }

    bindEvents() {
        // Search
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }

        // Filters
        const tierFilter = document.getElementById('tier-filter');
        if (tierFilter) {
            tierFilter.addEventListener('change', (e) => {
                this.filters.tier = e.target.value;
                this.applyFilters();
            });
        }

        const categoryFilter = document.getElementById('category-filter');
        if (categoryFilter) {
            categoryFilter.addEventListener('change', (e) => {
                this.filters.category = e.target.value;
                this.applyFilters();
            });
        }

        // Clear search
        const clearSearch = document.getElementById('clear-search');
        if (clearSearch) {
            clearSearch.addEventListener('click', () => {
                this.clearSearch();
            });
        }

        // AI Extraction
        const runExtraction = document.getElementById('run-extraction');
        if (runExtraction) {
            runExtraction.addEventListener('click', () => {
                this.runAIExtraction();
            });
        }

        const clearExtraction = document.getElementById('clear-extraction');
        if (clearExtraction) {
            clearExtraction.addEventListener('click', () => {
                this.clearExtraction();
            });
        }
    }

    async loadVendorCatalog() {
        try {
            this.showLoading(true);
            const params = new URLSearchParams();

            if (this.filters.search) params.append('search', this.filters.search);
            if (this.filters.tier) params.append('tier', this.filters.tier);
            if (this.filters.category) params.append('category', this.filters.category);

            const response = await fetch(`/api/vendors?${params}`);
            const data = await response.json();

            if (data.success) {
                this.vendors = data.vendors || [];
                this.productFamilies = data.product_families || [];
                this.products = data.products || [];
                this.displayCatalog();
                this.updateStatistics(data.total || 0);
            } else {
                this.showError('Failed to load vendor catalog: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading vendor catalog:', error);
            this.showError('Error loading vendor catalog');
        } finally {
            this.showLoading(false);
        }
    }

    async loadCategories() {
        try {
            const response = await fetch('/api/vendors/categories');
            const data = await response.json();

            if (data.success) {
                this.populateCategoryFilter(data.categories || []);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    }

    async loadTiers() {
        try {
            const response = await fetch('/api/vendors/tiers');
            const data = await response.json();

            if (data.success) {
                this.populateTierFilter(data.tiers || []);
            }
        } catch (error) {
            console.error('Error loading tiers:', error);
        }
    }

    populateCategoryFilter(categories) {
        const categoryFilter = document.getElementById('category-filter');
        if (!categoryFilter) return;

        const currentValue = categoryFilter.value;

        // Clear existing options except the first one
        while (categoryFilter.children.length > 1) {
            categoryFilter.removeChild(categoryFilter.lastChild);
        }

        // Add categories
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categoryFilter.appendChild(option);
        });

        // Restore previous selection
        if (currentValue) {
            categoryFilter.value = currentValue;
        }
    }

    populateTierFilter(tiers) {
        const tierFilter = document.getElementById('tier-filter');
        if (!tierFilter) return;

        const currentValue = tierFilter.value;

        // Clear existing options except the first one
        while (tierFilter.children.length > 1) {
            tierFilter.removeChild(tierFilter.lastChild);
        }

        // Add tiers
        tiers.forEach(tier => {
            const option = document.createElement('option');
            option.value = tier;
            option.textContent = tier;
            tierFilter.appendChild(option);
        });

        // Restore previous selection
        if (currentValue) {
            tierFilter.value = currentValue;
        }
    }

    displayCatalog() {
        this.displayVendors();
        this.displayProductFamilies();
        this.displayProducts();
        this.updateCounts();
    }

    displayVendors() {
        const container = document.getElementById('vendors');
        if (!container) return;

        if (this.vendors.length === 0) {
            safeHTML(container, `
                <div class="text-center py-4 text-muted-foreground">
                    <i class="fas fa-building text-2xl mb-2"></i>
                    <p>No vendors found</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.vendors.map(vendor => `
            <div class="vendor-item ${this.selectedVendor?.id === vendor.id ? 'selected' : ''}"
                 onclick="vendorCatalogManager.selectVendor(${vendor.id})">
                <div class="vendor-header">
                    <h4>${escapeHtml(vendor.name)}</h4>
                    <span class="tier-badge tier-${escapeHtml(vendor.tier)}">${escapeHtml(vendor.tier)}</span>
                </div>
                <div class="vendor-stats">
                    <span class="stat">
                        <i class="fas fa-box"></i> ${vendor.product_count || 0} products
                    </span>
                    <span class="stat">
                        <i class="fas fa-layer-group"></i> ${vendor.family_count || 0} families
                    </span>
                </div>
                ${vendor.description ? `
                <div class="vendor-description">
                    ${escapeHtml(vendor.description.substring(0, 100))}${vendor.description.length > 100 ? '...' : ''}
                </div>
                ` : ''}
            </div>
        `).join(''));
    }

    displayProductFamilies() {
        const container = document.getElementById('product-families');
        if (!container) return;

        if (!this.selectedVendor || this.productFamilies.length === 0) {
            safeHTML(container, `
                <div class="text-center py-4 text-muted-foreground">
                    <i class="fas fa-layer-group text-2xl mb-2"></i>
                    <p>${this.selectedVendor ? 'No product families found' : 'Select a vendor to view families'}</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.productFamilies.map(family => `
            <div class="family-item ${this.selectedFamily?.id === family.id ? 'selected' : ''}"
                 onclick="vendorCatalogManager.selectFamily(${family.id})">
                <div class="family-header">
                    <h4>${escapeHtml(family.name)}</h4>
                    <span class="product-count">${family.product_count || 0} products</span>
                </div>
                ${family.description ? `
                <div class="family-description">
                    ${escapeHtml(family.description.substring(0, 80))}${family.description.length > 80 ? '...' : ''}
                </div>
                ` : ''}
            </div>
        `).join(''));
    }

    displayProducts() {
        const container = document.getElementById('products');
        if (!container) return;

        if (!this.selectedFamily || this.products.length === 0) {
            safeHTML(container, `
                <div class="text-center py-4 text-muted-foreground">
                    <i class="fas fa-cube text-2xl mb-2"></i>
                    <p>${this.selectedFamily ? 'No products found' : 'Select a product family to view products'}</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.products.map(product => `
            <div class="product-item" onclick="vendorCatalogManager.viewProductDetails(${product.id})">
                <div class="product-header">
                    <h4>${escapeHtml(product.name)}</h4>
                    <span class="version">${escapeHtml(product.version) || 'N/A'}</span>
                </div>
                <div class="product-details">
                    <div class="detail-row">
                        <span class="label">Category:</span>
                        <span class="value">${escapeHtml(product.category) || 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Deployment:</span>
                        <span class="value">${escapeHtml(product.deployment_type) || 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Applications:</span>
                        <span class="value">${product.application_count || 0}</span>
                    </div>
                </div>
                ${product.description ? `
                <div class="product-description">
                    ${escapeHtml(product.description.substring(0, 100))}${product.description.length > 100 ? '...' : ''}
                </div>
                ` : ''}
            </div>
        `).join(''));
    }

    async selectVendor(vendorId) {
        this.selectedVendor = this.vendors.find(v => v.id === vendorId);
        this.selectedFamily = null;

        // Load vendor hierarchy
        try {
            this.showLoading(true);
            const response = await fetch(`/api/vendors/${vendorId}/hierarchy`);
            const data = await response.json();

            if (data.success) {
                this.productFamilies = data.hierarchy?.product_families || [];
                this.products = [];
                this.displayCatalog();
            } else {
                this.showError('Failed to load vendor hierarchy: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading vendor hierarchy:', error);
            this.showError('Error loading vendor hierarchy');
        } finally {
            this.showLoading(false);
        }
    }

    async selectFamily(familyId) {
        this.selectedFamily = this.productFamilies.find(f => f.id === familyId);

        // Load family products
        try {
            this.showLoading(true);
            const response = await fetch(`/api/vendors/families/${familyId}/products`);
            const data = await response.json();

            if (data.success) {
                this.products = data.products || [];
                this.displayProducts();
            } else {
                this.showError('Failed to load family products: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading family products:', error);
            this.showError('Error loading family products');
        } finally {
            this.showLoading(false);
        }
    }

    async viewProductDetails(productId) {
        try {
            this.showLoading(true);
            const response = await fetch(`/api/vendors/products/${productId}`);
            const data = await response.json();

            if (data.success) {
                this.showProductDetailsModal(data.product, data.applications);
            } else {
                this.showError('Failed to load product details: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading product details:', error);
            this.showError('Error loading product details');
        } finally {
            this.showLoading(false);
        }
    }

    showProductDetailsModal(product, applications) {
        // Use modal manager to create a standardized modal
        const modalId = modalManager.createModal({
            title: 'Product Details',
            content: `
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <strong>Product Name:</strong> ${escapeHtml(product.name)}
                        </div>
                        <div>
                            <strong>Version:</strong> ${escapeHtml(product.version) || 'N/A'}
                        </div>
                        <div>
                            <strong>Category:</strong> ${escapeHtml(product.category) || 'N/A'}
                        </div>
                        <div>
                            <strong>Deployment Type:</strong> ${escapeHtml(product.deployment_type) || 'N/A'}
                        </div>
                        <div>
                            <strong>License:</strong> ${escapeHtml(product.license_type) || 'N/A'}
                        </div>
                        <div>
                            <strong>Support Level:</strong> ${escapeHtml(product.support_level) || 'N/A'}
                        </div>
                    </div>

                    ${product.description ? `
                    <div>
                        <strong>Description:</strong>
                        <p class="mt-1">${escapeHtml(product.description)}</p>
                    </div>
                    ` : ''}

                    ${product.specifications ? `
                    <div>
                        <strong>Specifications:</strong>
                        <pre class="mt-1 p-3 bg-muted/30 rounded text-sm">${escapeHtml(JSON.stringify(product.specifications, null, 2))}</pre>
                    </div>
                    ` : ''}

                    ${applications && applications.length > 0 ? `
                    <div>
                        <h4 class="font-semibold mb-2">Applications Using This Product</h4>
                        <div class="max-h-40 overflow-y-auto">
                            <ul class="list-disc list-inside">
                                ${applications.map(app => `<li>${escapeHtml(app.name)}</li>`).join('')}
                            </ul>
                        </div>
                    </div>
                    ` : ''}
                </div>
            `,
            size: 'large',
            buttons: [
                {
                    text: '<i class="fas fa-check"></i> Use in Mapping',
                    class: 'px-4 py-2 bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600',
                    action: 'use-mapping',
                    handler: () => this.useProductInMapping(product.id)
                },
                {
                    text: '<i class="fas fa-robot"></i> Test AI Extraction',
                    class: 'px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary',
                    action: 'test-extraction',
                    handler: () => this.testAIExtraction(product.name)
                },
                {
                    text: 'Close',
                    class: 'px-4 py-2 border border-border rounded text-foreground hover:bg-muted/30',
                    action: 'close',
                    closeOnClick: true
                }
            ]
        });

        // Open the modal
        modalManager.open(modalId);
    }

    async handleSearch(query) {
        this.filters.search = query;

        if (query.trim() === '') {
            this.loadVendorCatalog();
            return;
        }

        try {
            this.showLoading(true);
            const params = new URLSearchParams();
            params.append('q', query);
            if (this.filters.tier) params.append('tier', this.filters.tier);
            if (this.filters.category) params.append('category', this.filters.category);

            const response = await fetch(`/api/vendors/search?${params}`);
            const data = await response.json();

            if (data.success) {
                this.displaySearchResults(data.results || []);
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

    displaySearchResults(results) {
        const vendorsContainer = document.getElementById('vendors');
        const familiesContainer = document.getElementById('product-families');
        const productsContainer = document.getElementById('products');

        if (!vendorsContainer || !familiesContainer || !productsContainer) return;

        // Group results by type
        const vendors = results.filter(r => r.type === 'vendor');
        const families = results.filter(r => r.type === 'family');
        const products = results.filter(r => r.type === 'product');

        safeHTML(vendorsContainer, vendors.map(vendor => `
            <div class="vendor-item search-result" onclick="vendorCatalogManager.selectVendor(${vendor.id})">
                <div class="vendor-header">
                    <h4>${escapeHtml(vendor.name)}</h4>
                    <span class="tier-badge tier-${escapeHtml(vendor.tier)}">${escapeHtml(vendor.tier)}</span>
                </div>
                <div class="search-score">${(vendor.score * 100).toFixed(1)}% match</div>
            </div>
        `).join('') || '<div class="text-center py-4 text-muted-foreground">No vendors found</div>');

        safeHTML(familiesContainer, families.map(family => `
            <div class="family-item search-result" onclick="vendorCatalogManager.selectFamily(${family.id})">
                <div class="family-header">
                    <h4>${escapeHtml(family.name)}</h4>
                    <span class="product-count">${family.product_count || 0} products</span>
                </div>
                <div class="search-score">${(family.score * 100).toFixed(1)}% match</div>
            </div>
        `).join('') || '<div class="text-center py-4 text-muted-foreground">No families found</div>');

        safeHTML(productsContainer, products.map(product => `
            <div class="product-item search-result" onclick="vendorCatalogManager.viewProductDetails(${product.id})">
                <div class="product-header">
                    <h4>${escapeHtml(product.name)}</h4>
                    <span class="version">${escapeHtml(product.version) || 'N/A'}</span>
                </div>
                <div class="search-score">${(product.score * 100).toFixed(1)}% match</div>
            </div>
        `).join('') || '<div class="text-center py-4 text-muted-foreground">No products found</div>');
    }

    async runAIExtraction() {
        const input = document.getElementById('extraction-input');
        if (!input || !input.value.trim()) {
            this.showError('Please enter an application description');
            return;
        }

        try {
            this.showLoading(true);
            const response = await fetch('/api/vendors/extract', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    application_description: input.value.trim()
                })
            });

            const data = await response.json();
            if (data.success) {
                this.displayExtractionResults(data.extraction_result, data.alternatives, data.confidence);
            } else {
                this.showError('Extraction failed: ' + data.error);
            }
        } catch (error) {
            console.error('Error running AI extraction:', error);
            this.showError('Error running AI extraction');
        } finally {
            this.showLoading(false);
        }
    }

    displayExtractionResults(result, alternatives, confidence) {
        const resultsContainer = document.getElementById('extraction-results');
        if (!resultsContainer) return;

        safeHTML(resultsContainer, `
            <div class="extraction-results">
                <div class="results-header">
                    <h4>Extraction Results</h4>
                    <div class="confidence-score">
                        <span class="confidence-label">Confidence:</span>
                        <span class="confidence-value">${(confidence * 100).toFixed(1)}%</span>
                    </div>
                </div>

                ${result ? `
                <div class="primary-result">
                    <div class="result-item">
                        <span class="label">Vendor:</span>
                        <span class="value">${escapeHtml(result.vendor) || 'Not identified'}</span>
                    </div>
                    <div class="result-item">
                        <span class="label">Product:</span>
                        <span class="value">${escapeHtml(result.product) || 'Not identified'}</span>
                    </div>
                    <div class="result-item">
                        <span class="label">Version:</span>
                        <span class="value">${escapeHtml(result.version) || 'N/A'}</span>
                    </div>
                    <div class="result-item">
                        <span class="label">Category:</span>
                        <span class="value">${escapeHtml(result.category) || 'N/A'}</span>
                    </div>
                </div>
                ` : '<p class="text-muted-foreground">No extraction results available</p>'}

                ${alternatives && alternatives.length > 0 ? `
                <div class="alternatives">
                    <h5>Alternative Matches</h5>
                    <div class="alternatives-list">
                        ${alternatives.map((alt, index) => `
                            <div class="alternative-item">
                                <div class="alternative-header">
                                    <span class="rank">#${index + 1}</span>
                                    <span class="confidence">${(alt.confidence * 100).toFixed(1)}%</span>
                                </div>
                                <div class="alternative-details">
                                    <div class="detail-row">
                                        <span class="label">Vendor:</span>
                                        <span class="value">${escapeHtml(alt.vendor) || 'N/A'}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span class="label">Product:</span>
                                        <span class="value">${escapeHtml(alt.product) || 'N/A'}</span>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `);

        resultsContainer.classList.remove('hidden');
    }

    clearExtraction() {
        const input = document.getElementById('extraction-input');
        const results = document.getElementById('extraction-results');

        if (input) input.value = '';
        if (results) results.classList.add('hidden');
    }

    clearSearch() {
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = '';

        this.filters.search = '';
        this.loadVendorCatalog();
    }

    applyFilters() {
        this.loadVendorCatalog();
    }

    updateCounts() {
        const vendorCount = document.getElementById('vendor-count');
        const familyCount = document.getElementById('family-count');
        const productCount = document.getElementById('product-count');

        if (vendorCount) vendorCount.textContent = this.vendors.length;
        if (familyCount) familyCount.textContent = this.productFamilies.length;
        if (productCount) productCount.textContent = this.products.length;
    }

    updateStatistics(total) {
        const statsContainer = document.getElementById('statistics');
        if (!statsContainer) return;

        safeHTML(statsContainer, `
            <div class="grid grid-cols-3 gap-4">
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${this.vendors.length}</div>
                    <div class="text-sm text-muted-foreground">Vendors</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-emerald-600">${this.productFamilies.length}</div>
                    <div class="text-sm text-muted-foreground">Families</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${this.products.length}</div>
                    <div class="text-sm text-muted-foreground">Products</div>
                </div>
            </div>
        `);
    }

    useProductInMapping(productId) {
        // This would integrate with the import mapping workflow
        this.showSuccess(`Product ${productId} selected for mapping`);

        // Could also store in a global variable or send to parent window
        if (window.parent && window.parent.selectVendorProduct) {
            window.parent.selectVendorProduct(productId);
        }
    }

    testAIExtraction(productName) {
        const input = document.getElementById('extraction-input');
        if (input) {
            input.value = `We are using ${productName} for our business processes.`;
            this.runAIExtraction();
        }
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
                <span>${escapeHtml(message)}</span>
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
    window.vendorCatalogManager = new VendorCatalogManager();
});
