/**
 * Abacus Settings Page - External JavaScript
 * Extracted from app/templates/admin/abacus_settings.html
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

function addCountry(country) {
    let input = document.getElementById('filter_countries');
    let current = input.value.trim();
    if (current === 'all') { input.value = country; return; }
    let countries = current ? current.split(',').map(function(c) { return c.trim(); }) : [];
    if (countries.indexOf(country) === -1) {
        countries.push(country);
        input.value = countries.join(',');
    }
}

// Initialize Lucide Icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

// Sync status polling
let statusPollInterval;
let currentJobId = null;

function updateSyncStatus() {
    fetch(APP_CONFIG.syncStatusUrl, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        },
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        let statusIndicator = document.getElementById('status-indicator');
        let statusText = document.getElementById('status-text');
        let statusDetails = document.getElementById('status-details');
        let syncButton = document.getElementById('sync-button');
        let cancelBtn = document.getElementById('cancel-job-btn');

        // Store current job ID
        currentJobId = data.job_id;

        if (data.status === 'no_jobs') {
            statusIndicator.className = 'h-3 w-3 rounded-full bg-muted/70';
            statusText.textContent = 'No sync jobs';
            statusText.className = 'font-medium text-foreground';
            statusDetails.textContent = 'No sync jobs have been run yet.';
            if (syncButton) syncButton.disabled = false;
            if (cancelBtn) cancelBtn.classList.add('hidden');
            return;
        }

        // Update status indicator
        switch (data.status) {
            case 'pending':
                statusIndicator.className = 'h-3 w-3 rounded-full bg-yellow-400';
                statusText.textContent = 'Queued';
                statusText.className = 'font-medium text-amber-700';
                if (syncButton) syncButton.disabled = true;
                if (cancelBtn) cancelBtn.classList.remove('hidden');
                break;
            case 'in_progress':
                statusIndicator.className = 'h-3 w-3 rounded-full bg-primary animate-pulse';
                statusText.textContent = 'Running';
                statusText.className = 'font-medium text-primary';
                if (syncButton) syncButton.disabled = true;
                if (cancelBtn) cancelBtn.classList.remove('hidden');
                break;
            case 'completed':
                statusIndicator.className = 'h-3 w-3 rounded-full bg-emerald-500';
                statusText.textContent = 'Completed';
                statusText.className = 'font-medium text-emerald-700';
                if (syncButton) syncButton.disabled = false;
                if (cancelBtn) cancelBtn.classList.add('hidden');
                break;
            case 'failed':
                statusIndicator.className = 'h-3 w-3 rounded-full bg-destructive';
                statusText.textContent = 'Failed';
                statusText.className = 'font-medium text-destructive';
                if (syncButton) syncButton.disabled = false;
                if (cancelBtn) cancelBtn.classList.add('hidden');
                break;
            case 'cancelled':
                statusIndicator.className = 'h-3 w-3 rounded-full bg-orange-500';
                statusText.textContent = 'Cancelled';
                statusText.className = 'font-medium text-orange-700';
                if (syncButton) syncButton.disabled = false;
                if (cancelBtn) cancelBtn.classList.add('hidden');
                break;
            default:
                statusIndicator.className = 'h-3 w-3 rounded-full bg-muted/70';
                statusText.textContent = data.status || 'Unknown';
                statusText.className = 'font-medium text-foreground';
                if (syncButton) syncButton.disabled = false;
                if (cancelBtn) cancelBtn.classList.add('hidden');
        }

        // Update details
        let details = 'Job ID: ' + data.job_id;
        if (data.created_at) {
            details += ' | Created: ' + new Date(data.created_at).toLocaleString();
        }
        if (data.started_at) {
            details += ' | Started: ' + new Date(data.started_at).toLocaleString();
        }
        if (data.finished_at) {
            details += ' | Finished: ' + new Date(data.finished_at).toLocaleString();
        }

        if (data.result && data.result.records_fetched) {
            let records = data.result.records_fetched;
            details += ' | Fetched: ' + (records.applications || 0) + ' apps, ' + (records.capabilities || 0) + ' caps, ' + (records.relationships || 0) + ' rels';
        }

        if (data.error) {
            details += ' | Error: ' + data.error;
        }

        statusDetails.textContent = details;
    })
    .catch(function(error) {
        console.error('Error fetching sync status:', error);
        document.getElementById('status-text').textContent = 'Error loading status';
        document.getElementById('status-details').textContent = 'Failed to check sync status.';
    });
}

function cancelCurrentJob() {
    if (!currentJobId) {
        Platform.toast.warning('No job to cancel');
        return;
    }

    let jobId = currentJobId;
    let modalId = window.modalManager.createModal({
        title: 'Cancel Sync Job',
        content: '<p class="text-sm text-muted-foreground">Are you sure you want to cancel job #' + jobId + '? This will stop the sync immediately.</p>',
        size: 'small',
        buttons: [
            { text: 'Keep Running', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
            { text: 'Cancel Job', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'stop', handler: function() {
                let cancelUrl = '/admin/abacus-settings/cancel-job/' + jobId;

                fetch(cancelUrl, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                })
                .then(function(response) {
                    if (!response.ok) {
                        return response.text().then(function(text) {
                            throw new Error('HTTP ' + response.status + ': ' + text);
                        });
                    }
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        Platform.toast.success('Job cancelled successfully');
                        updateSyncStatus(); // Refresh status immediately
                    } else {
                        Platform.toast.error('Failed to cancel job: ' + data.message);
                    }
                })
                .catch(function(error) {
                    console.error('Error cancelling job:', error);
                    Platform.toast.error('Error cancelling job: ' + error.message);
                });
            } }
        ]
    });
    window.modalManager.open(modalId);
}

// Update imported data counts
function updateImportedDataCounts() {
    fetch('/admin/abacus-settings/stats', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        },
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            // Update applications count
            let appsCount = data.applications || 0;
            let appsCountEl = document.getElementById('imported-apps-count');
            let appsProgressEl = document.getElementById('apps-progress');
            if (appsCountEl) {
                appsCountEl.textContent = appsCount;
                if (appsProgressEl) {
                    let percentage = Math.min(100, Math.max(1, (appsCount / 100) * 100));
                    appsProgressEl.style.width = percentage + '%';
                }
            }

            // Update capabilities count
            let capsCount = data.capabilities || 0;
            let capsCountEl = document.getElementById('imported-caps-count');
            let capsProgressEl = document.getElementById('caps-progress');
            if (capsCountEl) {
                capsCountEl.textContent = capsCount;
                if (capsProgressEl) {
                    let capPercentage = Math.min(100, Math.max(1, (capsCount / 50) * 100));
                    capsProgressEl.style.width = capPercentage + '%';
                }
            }
        }
    })
    .catch(function(error) {
        console.error('Error fetching Abacus stats:', error);
    });
}

// Start polling when page loads
document.addEventListener('DOMContentLoaded', function() {
    updateSyncStatus(); // Initial check
    statusPollInterval = setInterval(updateSyncStatus, 2000); // Poll every 2 seconds
    updateImportedDataCounts(); // Load imported data stats
    setInterval(updateImportedDataCounts, 10000); // Refresh every 10 seconds
});

// Clean up polling when page unloads
window.addEventListener('beforeunload', function() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
});
