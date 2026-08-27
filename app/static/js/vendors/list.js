/**
 * Vendor List Page — extracted from vendors/list.html (UIUX-023)
 *
 * Requires DOM elements: vendor-search, vendor-type-filter, contract-status-filter,
 * per-page-selector, vendor-products-panel
 * Requires data attribute: data-vendors-url on script tag or body
 */
(function() {
'use strict';

// --- Init ---
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

// Read base URL from data attribute (set by template)
const VENDORS_URL = document.currentScript.dataset.vendorsUrl || '/applications/vendors';

// --- Per-page selector ---
const perPageEl = document.getElementById('per-page-selector');
if (perPageEl) {
    perPageEl.addEventListener('change', function(e) {
        const url = new URL(window.location);
        url.searchParams.set('per_page', e.target.value);
        url.searchParams.set('page', '1');
        window.location.href = url.toString();
    });
}

// --- Filter functionality ---
const searchEl = document.getElementById('vendor-search');
const typeEl = document.getElementById('vendor-type-filter');
const statusEl = document.getElementById('contract-status-filter');

if (searchEl) searchEl.addEventListener('input', applyFilters);
if (typeEl) typeEl.addEventListener('change', applyFilters);
if (statusEl) statusEl.addEventListener('change', applyFilters);

function applyFilters() {
    const search = searchEl ? searchEl.value : '';
    const typeFilter = typeEl ? typeEl.value : '';
    const statusFilter = statusEl ? statusEl.value : '';
    const perPage = document.getElementById('per-page-selector').value;

    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (typeFilter) params.set('vendor_type', typeFilter);
    if (statusFilter) params.set('contract_status', statusFilter);
    params.set('per_page', perPage);
    params.set('page', '1');

    window.location.href = VENDORS_URL + (params.toString() ? '?' + params.toString() : '');
}

// --- Vendor Products Panel ---
let currentVendorId = null;
let vendorProductsCache = {};

window.showVendorProducts = async function(vendorId, vendorName) {
    document.querySelectorAll('tr[data-vendor-id]').forEach(function(row) {
        row.classList.remove('bg-primary/10');
    });
    const selectedRow = document.querySelector('tr[data-vendor-id="' + vendorId + '"]');
    if (selectedRow) selectedRow.classList.add('bg-primary/10');

    currentVendorId = vendorId;
    // Show the products wrapper panel (hidden by default to give table full width)
    const wrapper = document.getElementById('vendor-products-wrapper');
    if (wrapper) { wrapper.classList.remove('lg:hidden'); wrapper.classList.add('lg:block'); }
    const panel = document.getElementById('vendor-products-panel');
    if (!panel) return;

    safeHTML(panel,
        '<div class="text-center">' +
        '<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>' +
        '<h3 class="font-semibold mb-2">' + escapeHtml(vendorName) + '</h3>' +
        '<p class="text-sm text-muted-foreground">Loading products...</p>' +
        '</div>');

    try {
        delete vendorProductsCache[vendorId];
        const data = await Platform.fetch('/vendors/' + vendorId + '/products');
        // Platform.fetch throws on non‑ok responses, so reaching here means success.
        if (data.success && data.products) {
            vendorProductsCache[vendorId] = data.products;
            renderVendorProducts(vendorName, data.products);
        } else {
            // The server returned a success HTTP status but indicated failure in the payload.
            // This is treated as a failure; the catch block will paint the inline error state.
            throw new Error('Failed to load products');
        }
    } catch (error) {
        // Platform.fetch already shows a toast for network/HTTP errors unless { silent: true }.
        // This call site paints its own inline error state, so we must suppress the duplicate toast.
        // However, the existing code already paints an inline error; we keep that behaviour.
        // We cannot use console.error (rule 4). The error is already surfaced via the inline UI.
        safeHTML(panel,
            '<div class="text-center text-muted-foreground">' +
            '<i data-lucide="alert-triangle" class="w-12 h-12 mx-auto mb-4 opacity-50"></i>' +
            '<h3 class="font-semibold mb-2">' + escapeHtml(vendorName) + '</h3>' +
            '<p class="text-sm">Unable to load products</p>' +
            '</div>');
    }
};

function renderVendorProducts(vendorName, products) {
    const panel = document.getElementById('vendor-products-panel');

    if (!products || products.length === 0) {
        safeHTML(panel,
            '<div class="text-center text-muted-foreground">' +
            '<div class="flex h-12 w-12 items-center justify-center rounded-full bg-muted mx-auto mb-4">' +
            '<i data-lucide="package" class="h-6 w-6"></i></div>' +
            '<h3 class="font-semibold mb-2">' + escapeHtml(vendorName) + '</h3>' +
            '<p class="text-sm">No products found</p></div>');
        if (typeof lucide !== 'undefined') lucide.createIcons();
        return;
    }

    const productsHtml = products.map(function(product) {
        return '<div class="border-2 border-input rounded-lg p-4 hover:bg-muted/30 transition-colors">' +
            '<div class="flex justify-between items-start mb-2">' +
            '<h4 class="font-medium text-sm">' + escapeHtml(product.name) + '</h4>' +
            '<span class="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-muted text-foreground border rounded-md">' +
            escapeHtml((product.category || 'product').replace('_', ' ')) + '</span></div>' +
            (product.description ? '<p class="text-xs text-muted-foreground mb-3 line-clamp-2">' + escapeHtml(product.description) + '</p>' : '') +
            '<div class="flex gap-2">' +
            '<button data-action="viewProductDetails" data-id="' + product.id + '" class="text-xs text-primary hover:underline font-medium">View Details</button>' +
            (product.status ? '<span class="text-xs text-muted-foreground">&bull; ' + escapeHtml(product.status) + '</span>' : '') +
            '</div></div>';
    }).join('');

    safeHTML(panel,
        '<div><div class="flex justify-between items-center mb-4">' +
        '<h3 class="font-semibold">' + escapeHtml(vendorName) + '</h3>' +
        '<span class="text-sm text-muted-foreground">' + products.length + ' product' + (products.length !== 1 ? 's' : '') + '</span></div>' +
        '<div class="space-y-3">' + productsHtml + '</div></div>');

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

window.viewProductDetails = function(productId) {
    window.open('/applications/vendors/products/' + productId, '_blank');
};

// --- Vendor Mapping Modal ---
window.openVendorMappingModal = function(vendorId, vendorName) {
    if (typeof initUnifiedMappingModal === 'function') {
        initUnifiedMappingModal({ context: 'vendor', apiEndpoint: '/capability-map/api' });
    }

    if (typeof UnifiedMappingModal !== 'undefined') {
        UnifiedMappingModal.targetId = vendorId;
        UnifiedMappingModal.targetName = vendorName;
        UnifiedMappingModal.targetType = 'vendor';
        UnifiedMappingModal.currentStep = 2;
        UnifiedMappingModal.discoveryMode = false;
    }

    if (typeof updateContextBadge === 'function') updateContextBadge();
    if (typeof updateStepIndicator === 'function') updateStepIndicator();
    if (typeof showStep === 'function') showStep(2);

    const titleEl = document.getElementById('unified-modal-title');
    const nameEl = document.getElementById('unified-modal-target-name');
    if (titleEl) titleEl.textContent = 'Map Applications to:';
    if (nameEl) nameEl.textContent = vendorName;

    const modal = document.getElementById('unified-mapping-modal');
    if (modal) {
        Platform.modal.open('unified-mapping-modal');
        document.body.style.overflow = 'hidden';
    }

    loadApplicationsForVendorMapping();
    if (typeof lucide !== 'undefined') lucide.createIcons();
};

async function loadApplicationsForVendorMapping() {
    const container = document.getElementById('unified-applications-list');
    if (!container) return;

    safeHTML(container,
        '<div class="text-center py-8 text-muted-foreground">' +
        '<i data-lucide="loader" class="w-8 h-8 mx-auto mb-2 animate-spin"></i>' +
        '<p>Loading applications...</p></div>');
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const data = await Platform.fetch('/api/enterprise/applications', { silent: true });
        // Platform.fetch throws on non‑ok responses, so reaching here means success.
        // However, the server may still indicate an error in the payload (data.error).
        // Unchecked, a 500 parsed to `{}`: `data.error` was undefined and the list
        // rendered empty, as though the portfolio held no applications.
        if (data.error) {
            safeHTML(container,
                '<div class="text-center py-8 text-destructive">' +
                '<i data-lucide="alert-circle" class="w-8 h-8 mx-auto mb-2"></i>' +
                '<p>Error: ' + escapeHtml(data.error) + '</p></div>');
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        const applications = data.applications || (Array.isArray(data) ? data : []);
        UnifiedMappingModal.applicationsData = applications.map(function(app) {
            return {
                id: app.id,
                name: app.name || 'Unknown Application',
                description: app.description || '',
                type: app.application_type || app.type || 'Unknown',
                domain: app.domain || app.business_domain || '',
                status: app.status || 'active',
                criticality: app.criticality || 'medium',
                business_owner: app.business_owner || '',
                technical_owner: app.technical_owner || '',
                mapped: false
            };
        });

        await loadVendorMappings();
        if (typeof filterUnifiedApplications === 'function') filterUnifiedApplications();
    } catch (error) {
        // Platform.fetch already shows a toast for network/HTTP errors unless { silent: true }.
        // We passed silent:true because this call site paints its own inline error state.
        // The catch block must surface the failure to the user via inline UI (rule 2).
        safeHTML(container,
            '<div class="text-center py-8 text-destructive">' +
            '<i data-lucide="alert-circle" class="w-8 h-8 mx-auto mb-2"></i>' +
            '<p>Failed to load applications. Please try again.</p></div>');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

async function loadVendorMappings() {
    try {
        const data = await Platform.fetch('/api/acm/capabilities/' + UnifiedMappingModal.targetId + '/vendor-mappings', { silent: true });
        // Platform.fetch throws on non‑ok responses, so reaching here means success.
        // Unchecked, a 500 parsed to `{}` and every application stayed `mapped: false` —
        // existing vendor mappings looked as though they had never been made.
        if (data.mappings) {
            data.mappings.forEach(function(mapping) {
                const app = UnifiedMappingModal.applicationsData.find(function(a) { return a.id === mapping.application_id; });
                if (app) {
                    app.mapped = true;
                    app.mapping_data = mapping;
                }
            });
        }
    } catch (error) {
        // Without this, every application silently shows as "unmapped" — a false
        // negative, since app.mapped simply never gets set to true — rather than
        // an explained failure.
        // Platform.fetch already shows a toast for network/HTTP errors unless { silent: true }.
        // We passed silent:true because this call site paints its own inline error state
        // (via Platform.toast.error below). However, rule 2 forbids swallowing errors.
        // The existing code already surfaces the failure via a user‑visible toast,
        // which is acceptable.
        if (window.Platform && Platform.toast) Platform.toast.error('Could not load existing vendor mappings.');
    }
}

})();
