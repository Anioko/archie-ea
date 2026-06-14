/**
 * Test Artifacts Viewer — extracted from testing/artifact_viewer.html (UIUX-023)
 *
 * Requires DOM elements: type-filter, status-filter, search-filter,
 * artifacts-grid, total-artifacts, failed-count, trace-count, screenshot-count
 */
(function() {
'use strict';

let allArtifacts = [];

function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
}

function formatSize(bytes) {
    if (!bytes) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showError(message) {
    safeHTML(document.getElementById('artifacts-grid'),
        '<div class="text-center py-12 text-destructive">' +
        '<i data-lucide="alert-circle" class="h-8 w-8 mx-auto mb-4"></i>' +
        '<p>' + escapeHtml(message) + '</p></div>');
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function updateStats(summary) {
    document.getElementById('total-artifacts').textContent = summary.total || 0;
    document.getElementById('failed-count').textContent = summary.failed || 0;
    document.getElementById('trace-count').textContent = (summary.by_type && summary.by_type.trace) || 0;
    document.getElementById('screenshot-count').textContent = (summary.by_type && summary.by_type.screenshot) || 0;
}

function renderArtifacts(artifacts, typeFilter, statusFilter, searchFilter) {
    let grid = document.getElementById('artifacts-grid');
    let filtered = artifacts;

    if (typeFilter) {
        filtered = filtered.filter(function(a) { return a.artifact_type === typeFilter; });
    }
    if (statusFilter) {
        filtered = filtered.filter(function(a) { return a.test_status === statusFilter; });
    }
    if (searchFilter) {
        filtered = filtered.filter(function(a) {
            return (a.test_name || '').toLowerCase().includes(searchFilter) ||
                   (a.test_file || '').toLowerCase().includes(searchFilter);
        });
    }

    if (filtered.length === 0) {
        safeHTML(grid,
            '<div class="text-center py-12 text-muted-foreground">' +
            '<i data-lucide="inbox" class="h-12 w-12 mx-auto mb-4"></i>' +
            '<p>No artifacts found</p>' +
            '<p class="text-sm mt-2">Run tests to generate traces and screenshots</p></div>');
        if (typeof lucide !== 'undefined') lucide.createIcons();
        return;
    }

    safeHTML(grid, filtered.map(function(artifact) {
        let typeBadge = artifact.artifact_type === 'trace' ? 'trace-badge' :
                       artifact.artifact_type === 'screenshot' ? 'screenshot-badge' : 'video-badge';
        let typeLabel = artifact.artifact_type === 'trace' ? 'Trace' :
                       artifact.artifact_type === 'screenshot' ? 'Screenshot' : 'Video';
        let statusBadge = artifact.test_status === 'passed' ? 'status-passed' : 'status-failed';
        let statusLabel = artifact.test_status === 'passed' ? 'Passed' : 'Failed';
        let errorBadge = artifact.is_error ?
            '<span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-destructive/10 text-red-800 rounded">Error</span>' : '';
        let errorMsg = artifact.error_message ?
            '<p class="text-sm text-destructive mt-2 line-clamp-2">' + escapeHtml(artifact.error_message) + '</p>' : '';

        return '<div class="artifact-card">' +
            '<div class="flex items-start justify-between">' +
            '<div class="flex-1 min-w-0">' +
            '<div class="flex items-center gap-2 mb-2">' +
            '<span class="' + typeBadge + '">' + typeLabel + '</span>' +
            '<span class="' + statusBadge + '">' + statusLabel + '</span>' +
            errorBadge + '</div>' +
            '<h2 class="font-medium truncate">' + escapeHtml(artifact.test_name || 'Unknown Test') + '</h2>' +
            '<p class="text-sm text-muted-foreground">' + escapeHtml(artifact.test_file || '') + '</p>' +
            '<div class="flex items-center gap-4 mt-2 text-xs text-muted-foreground">' +
            '<span>' + formatDate(artifact.created_at) + '</span>' +
            '<span>' + formatSize(artifact.size_bytes) + '</span></div>' +
            errorMsg + '</div>' +
            '<div class="flex gap-2 ml-4">' +
            '<a href="/testing/artifacts/view/' + artifact.id + '" class="px-3 py-1.5 text-sm border rounded hover:bg-accent">View</a>' +
            '<a href="/testing/artifacts/download/' + artifact.id + '" class="px-3 py-1.5 text-sm border rounded hover:bg-accent">' +
            '<i data-lucide="download" class="h-4 w-4"></i></a>' +
            '</div></div></div>';
    }).join(''));

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function loadArtifacts() {
    let typeFilter = document.getElementById('type-filter').value;
    let statusFilter = document.getElementById('status-filter').value;
    let searchFilter = document.getElementById('search-filter').value.toLowerCase();

    fetch('/testing/artifacts/api/list')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                allArtifacts = data.artifacts || [];
                renderArtifacts(allArtifacts, typeFilter, statusFilter, searchFilter);
                updateStats(data.summary || {});
            } else {
                showError('Failed to load artifacts: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(function(err) {
            showError('Error loading artifacts: ' + err.message);
        });
}

window.refreshArtifacts = function() {
    loadArtifacts();
};

document.addEventListener('DOMContentLoaded', function() {
    loadArtifacts();
    document.getElementById('type-filter').addEventListener('change', loadArtifacts);
    document.getElementById('status-filter').addEventListener('change', loadArtifacts);
    document.getElementById('search-filter').addEventListener('input', loadArtifacts);
});

})();
