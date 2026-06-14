/**
 * Agentic Gap Implementation
 * Extracted from main/agentic_gaps.html
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

let currentTab = 'overview';

function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(function(content) {
        content.classList.add('hidden');
    });

    // Remove active class from all tabs
    document.querySelectorAll('.tab-button').forEach(function(btn) {
        btn.classList.remove('active', 'border-primary', 'text-primary');
        btn.classList.add('border-transparent', 'text-muted-foreground');
    });

    // Show selected tab content
    document.getElementById('content-' + tabName).classList.remove('hidden');

    // Add active class to selected tab
    let activeTab = document.getElementById('tab-' + tabName);
    activeTab.classList.add('active', 'border-primary', 'text-primary');
    activeTab.classList.remove('border-transparent', 'text-muted-foreground');

    currentTab = tabName;
}

document.addEventListener('DOMContentLoaded', function() {
    let checkStatusBtn = document.getElementById('checkStatusBtn');
    let implementAllBtn = document.getElementById('implementAllBtn');
    let implementSingleBtn = document.getElementById('implementSingleBtn');
    let agentSelect = document.getElementById('agentSelect');
    let statusTableBody = document.getElementById('statusTableBody');
    let resultsDisplay = document.getElementById('resultsDisplay');
    let loadHistoryBtn = document.getElementById('loadHistoryBtn');
    let loadMetricsBtn = document.getElementById('loadMetricsBtn');
    let loadRecommendationsBtn = document.getElementById('loadRecommendationsBtn');
    let loadSchedulesBtn = document.getElementById('loadSchedulesBtn');
    let configAgentSelect = document.getElementById('configAgentSelect');
    let saveConfigBtn = document.getElementById('saveConfigBtn');

    // Get CSRF token from meta tag
    let getCSRFToken = function() {
        let metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : '';
    };

    // Enable single agent button when agent is selected
    agentSelect.addEventListener('change', function() {
        implementSingleBtn.disabled = !this.value;
    });

    // Check status — API not yet implemented
    checkStatusBtn.addEventListener('click', function() {
        safeHTML(statusTableBody, '<tr><td colspan="4" class="text-muted-foreground p-4">Agentic gaps API is not yet available.</td></tr>');
    });

    // Implement all gaps — API not yet implemented
    implementAllBtn.addEventListener('click', function() {
        resultsDisplay.className = 'bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-md';
        safeHTML(resultsDisplay, 'Agentic gaps API is not yet available.');
    });

    // Implement single agent — API not yet implemented
    implementSingleBtn.addEventListener('click', function() {
        resultsDisplay.className = 'bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-md';
        safeHTML(resultsDisplay, 'Agentic gaps API is not yet available.');
    });

    // All remaining handlers — APIs not yet implemented
    let notAvailableMsg = 'Agentic gaps API is not yet available.';

    loadHistoryBtn.addEventListener('click', function() {
        safeHTML(document.getElementById('historyTableBody'),
            '<tr><td colspan="6" class="text-center p-4 text-muted-foreground">' + notAvailableMsg + '</td></tr>');
    });

    loadMetricsBtn.addEventListener('click', function() {
        document.getElementById('metricsData').textContent = notAvailableMsg;
    });

    loadRecommendationsBtn.addEventListener('click', function() {
        safeHTML(document.getElementById('recommendationsDisplay'),
            '<p class="text-muted-foreground">' + notAvailableMsg + '</p>');
    });

    loadSchedulesBtn.addEventListener('click', function() {
        safeHTML(document.getElementById('schedulesDisplay'),
            '<p class="text-muted-foreground">' + notAvailableMsg + '</p>');
    });

    configAgentSelect.addEventListener('change', function() {
        document.getElementById('configForm').classList.add('hidden');
    });

    saveConfigBtn.addEventListener('click', function() {
        Platform.toast.info(notAvailableMsg);
    });

    document.getElementById('scheduleForm').addEventListener('submit', function(e) {
        e.preventDefault();
        Platform.toast.info(notAvailableMsg);
    });

    window.implementAgent = function() { Platform.toast.info(notAvailableMsg); };
    window.reviewExecution = function() { Platform.toast.info(notAvailableMsg); };
    window.rollbackExecution = function() { Platform.toast.info(notAvailableMsg); };
});
