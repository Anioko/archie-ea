let APP_CONFIG = window.__APP_CONFIG__ || {};

// Market Intelligence Application
//
// NOTE: This dashboard has no backend. Every data source it once called
// (/api/market-intelligence/quadrant, /risk-alerts, /trends, /sync,
// /alternatives/<id>) 404s — no blueprint anywhere in the app serves that
// prefix (verified against app.url_map). Rather than fetch and silently
// swallow the failure into a misleading "0 vendors tracked" state, this file
// renders an explicit "not available" state and does not call the network.
// See the dead-fetch audit that found this (nine 404ing front-end calls).
let MarketIntel = {
    currentTab: 'quadrant',

    init: function() {
        this.setupEventListeners();
        this.renderUnavailable();
        lucide.createIcons();
    },

    setupEventListeners: function() {
        let self = this;
        // Tab navigation — purely client-side, kept functional.
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) { self.switchTab(e.target.dataset.tab); });
        });

        document.getElementById('btn-sync-data').addEventListener('click', function() { self.syncData(); });
        document.getElementById('close-vendor-detail').addEventListener('click', function() { self.hideDialog('vendor-detail-dialog'); });
    },

    // No vendor/risk/trend data source exists, so every panel shows the same
    // explicit unavailable notice instead of a fabricated empty/zero state.
    renderUnavailable: function() {
        document.getElementById('total-vendors').textContent = '—';
        document.getElementById('risk-alerts').textContent = '—';
        document.getElementById('market-trends').textContent = '—';
        document.getElementById('leaders-count').textContent = '—';

        let notice = '<div class="p-8 text-center text-muted-foreground">' +
            '<i data-lucide="server-off" class="h-8 w-8 mx-auto mb-2"></i>' +
            '<p>Market intelligence data is not available.</p>' +
            '</div>';

        safeHTML(document.getElementById('vendor-list'), notice);
        safeHTML(document.getElementById('risk-alerts-list'), notice);
        safeHTML(document.getElementById('trends-grid'), notice);
        safeHTML(document.getElementById('alternatives-results'), notice);

        let select = document.getElementById('current-vendor-select');
        safeHTML(select, '<option value="">No vendors available</option>');
        select.disabled = true;

        lucide.createIcons();
    },

    syncData: function() {
        this.showToast('Market data sync is not available.', 'error');
    },

    switchTab: function(tab) {
        this.currentTab = tab;
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            btn.classList.remove('border-b-2', 'border-primary', 'text-primary');
            btn.classList.add('text-muted-foreground');
        });
        let activeBtn = document.querySelector('.tab-btn[data-tab="' + tab + '"]');
        if (!activeBtn) return;
        activeBtn.classList.remove('text-muted-foreground');
        activeBtn.classList.add('border-b-2', 'border-primary', 'text-primary');

        document.querySelectorAll('.tab-panel').forEach(function(panel) { panel.classList.add('hidden'); });
        document.getElementById(tab + '-tab').classList.remove('hidden');
    },

    hideDialog: function(id) {
        document.getElementById(id).classList.add('hidden');
        document.getElementById(id).classList.remove('flex');
    },

    showToast: function(message, type) {
        type = type || 'info';
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else if (Platform.toast[type]) {
            Platform.toast[type](message);
        } else {
            Platform.toast.info(message);
        }
    }
};

document.addEventListener('DOMContentLoaded', function() {
    MarketIntel.init();
});
