/**
 * Import History Manager - Frontend JavaScript Integration
 * Handles import history display, progress tracking, and batch job management
 */

class ImportHistoryManager {
    constructor() {
        this.importHistory = [];
        this.currentImport = null;
        this.progressInterval = null;
        this.filters = {
            status: '',
            dateFrom: '',
            dateTo: ''
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadImportHistory();
        this.initializeDatePicker();
    }

    bindEvents() {
        // Filters
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filters.status = e.target.value;
                this.applyFilters();
            });
        }

        const dateFromFilter = document.getElementById('date-from');
        if (dateFromFilter) {
            dateFromFilter.addEventListener('change', (e) => {
                this.filters.dateFrom = e.target.value;
                this.applyFilters();
            });
        }

        const dateToFilter = document.getElementById('date-to');
        if (dateToFilter) {
            dateToFilter.addEventListener('change', (e) => {
                this.filters.dateTo = e.target.value;
                this.applyFilters();
            });
        }

        // Clear filters
        const clearFilters = document.getElementById('clear-filters');
        if (clearFilters) {
            clearFilters.addEventListener('click', () => {
                this.clearFilters();
            });
        }

        // Refresh
        const refresh = document.getElementById('refresh');
        if (refresh) {
            refresh.addEventListener('click', () => {
                this.loadImportHistory();
            });
        }
    }

    initializeDatePicker() {
        // Initialize date pickers if needed
        const dateFrom = document.getElementById('date-from');
        const dateTo = document.getElementById('date-to');

        if (dateFrom) {
            // Set default to 30 days ago
            const thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
            dateFrom.value = thirtyDaysAgo.toISOString().split('T')[0];
        }

        if (dateTo) {
            // Set default to today
            dateTo.value = new Date().toISOString().split('T')[0];
        }
    }

    async loadImportHistory() {
        // API /api/import-history not yet implemented — show empty state
        this.showLoading(false);
        this.importHistory = [];
        this.displayImportHistory();
        this.updateStatistics();
    }

    displayImportHistory() {
        const container = document.getElementById('import-history');
        if (!container) return;

        if (this.importHistory.length === 0) {
            safeHTML(container, `
                <div class="text-center py-8 text-muted-foreground">
                    <i class="fas fa-history text-4xl mb-4"></i>
                    <p>No import history found</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.importHistory.map(item => `
            <div class="import-item border rounded-lg p-4 mb-4" data-job-id="${escapeHtml(item.id)}">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <h4 class="font-semibold text-lg">${escapeHtml(item.file_name || 'Unknown File')}</h4>
                        <div class="flex items-center space-x-2 mt-1">
                            <span class="status-badge status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
                            <span class="text-sm text-muted-foreground">Job ID: ${escapeHtml(item.id)}</span>
                            <span class="text-sm text-muted-foreground">Created: ${escapeHtml(new Date(item.created_at).toLocaleString())}</span>
                        </div>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="importHistoryManager.viewDetails(${parseInt(item.id, 10) || 0})"
                                class="px-3 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary">
                            <i class="fas fa-eye"></i> Details
                        </button>
                        ${item.status === 'completed' ? `
                        <button onclick="importHistoryManager.exportData(${parseInt(item.id, 10) || 0})"
                                class="px-3 py-1 text-sm bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600">
                            <i class="fas fa-download"></i> Export
                        </button>
                        ` : ''}
                        ${item.status === 'completed' && this.canRollback(item) ? `
                        <button onclick="importHistoryManager.confirmRollback(${parseInt(item.id, 10) || 0})"
                                class="px-3 py-1 text-sm bg-orange-500 text-primary-foreground rounded hover:bg-orange-600">
                            <i class="fas fa-undo"></i> Rollback
                        </button>
                        ` : ''}
                        ${item.status === 'failed' ? `
                        <button onclick="importHistoryManager.retryFailed(${parseInt(item.id, 10) || 0})"
                                class="px-3 py-1 text-sm bg-amber-500 text-primary-foreground rounded hover:bg-yellow-600">
                            <i class="fas fa-redo"></i> Retry
                        </button>
                        ` : ''}
                    </div>
                </div>

                <div class="import-stats grid grid-cols-5 gap-3">
                    <div class="text-center bg-emerald-500/5 p-3 rounded">
                        <div class="text-lg font-bold text-emerald-600">${parseInt(item.processed_items, 10) || 0}</div>
                        <div class="text-xs text-muted-foreground">Processed</div>
                    </div>
                    <div class="text-center bg-primary/5 p-3 rounded">
                        <div class="text-lg font-bold text-primary">${parseInt(item.total_items, 10) || 0}</div>
                        <div class="text-xs text-muted-foreground">Total</div>
                    </div>
                    <div class="text-center bg-destructive/5 p-3 rounded">
                        <div class="text-lg font-bold text-destructive">${parseInt(item.failed_items, 10) || 0}</div>
                        <div class="text-xs text-muted-foreground">Failed</div>
                    </div>
                    <div class="text-center bg-purple-50 p-3 rounded">
                        <div class="text-lg font-bold text-primary">${parseInt(item.progress, 10) || 0}%</div>
                        <div class="text-xs text-muted-foreground">Progress</div>
                    </div>
                    <div class="text-center bg-muted/30 p-3 rounded">
                        <div class="text-lg font-bold text-muted-foreground">${escapeHtml(this.calculateDuration(item))}</div>
                        <div class="text-xs text-muted-foreground">Duration</div>
                    </div>
                </div>

                ${item.status === 'running' ? `
                <div class="progress-bar mt-3">
                    <div class="w-full bg-muted rounded-full h-2">
                        <div class="bg-primary h-2 rounded-full transition-all duration-300"
                             style="width: ${parseInt(item.progress, 10) || 0}%"></div>
                    </div>
                    <div class="text-xs text-muted-foreground mt-1">
                        ${escapeHtml(item.status_details?.current_item || 'Processing...')}
                    </div>
                </div>
                ` : ''}

                ${item.import_history ? `
                <div class="import-details mt-3 p-3 bg-muted/30 rounded">
                    <div class="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <strong>Duplicate Mode:</strong> ${escapeHtml(item.import_history.duplicate_mode || 'N/A')}
                        </div>
                        <div>
                            <strong>Generate ArchiMate:</strong> ${item.import_history.generate_archimate ? 'Yes' : 'No'}
                        </div>
                        <div>
                            <strong>Import Source:</strong> ${escapeHtml(item.import_history.import_source || 'N/A')}
                        </div>
                    </div>
                </div>
                ` : ''}
            </div>
        `).join(''));

        // Start progress monitoring for running jobs
        this.startProgressMonitoring();
    }

    calculateDuration(item) {
        if (!item.started_at) return 'N/A';

        const started = new Date(item.started_at);
        const completed = item.completed_at ? new Date(item.completed_at) : new Date();
        const duration = Math.floor((completed - started) / 1000); // seconds

        if (duration < 60) return `${duration}s`;
        if (duration < 3600) return `${Math.floor(duration / 60)}m`;
        return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
    }

    canRollback(item) {
        if (!item.completed_at) return false;

        const completed = new Date(item.completed_at);
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

        return completed > sevenDaysAgo;
    }

    async viewDetails() {
        // API /api/import-history/{id} not yet implemented
        this.showError('Import history API is not yet available.');
    }

    showJobDetails(job) {
        // Use modal manager to create a standardized modal
        const modalId = modalManager.createModal({
            title: 'Import Job Details',
            content: `
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <strong>Job ID:</strong> ${escapeHtml(job.id)}
                        </div>
                        <div>
                            <strong>Status:</strong> <span class="status-badge status-${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
                        </div>
                        <div>
                            <strong>File Name:</strong> ${escapeHtml(job.config_data?.file_name || 'N/A')}
                        </div>
                        <div>
                            <strong>Created:</strong> ${escapeHtml(new Date(job.created_at).toLocaleString())}
                        </div>
                        <div>
                            <strong>Started:</strong> ${job.started_at ? escapeHtml(new Date(job.started_at).toLocaleString()) : 'N/A'}
                        </div>
                        <div>
                            <strong>Completed:</strong> ${job.completed_at ? escapeHtml(new Date(job.completed_at).toLocaleString()) : 'N/A'}
                        </div>
                    </div>

                    <div class="grid grid-cols-4 gap-4">
                        <div class="text-center bg-emerald-500/5 p-3 rounded">
                            <div class="text-lg font-bold text-emerald-600">${parseInt(job.processed_items, 10) || 0}</div>
                            <div class="text-sm text-muted-foreground">Processed</div>
                        </div>
                        <div class="text-center bg-primary/5 p-3 rounded">
                            <div class="text-lg font-bold text-primary">${parseInt(job.total_items, 10) || 0}</div>
                            <div class="text-sm text-muted-foreground">Total</div>
                        </div>
                        <div class="text-center bg-destructive/5 p-3 rounded">
                            <div class="text-lg font-bold text-destructive">${parseInt(job.failed_items, 10) || 0}</div>
                            <div class="text-sm text-muted-foreground">Failed</div>
                        </div>
                        <div class="text-center bg-purple-50 p-3 rounded">
                            <div class="text-lg font-bold text-primary">${parseInt(job.progress, 10) || 0}%</div>
                            <div class="text-sm text-muted-foreground">Progress</div>
                        </div>
                    </div>

                    ${job.items && job.items.length > 0 ? `
                    <div>
                        <h4 class="font-semibold mb-2">Job Items</h4>
                        <div class="max-h-60 overflow-y-auto">
                            <table class="min-w-full divide-y divide-border">
                                <thead class="bg-muted/30">
                                    <tr>
                                        <th class="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">ID</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">Type</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">Status</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">Created</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">Duration</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-background divide-y divide-border">
                                    ${job.items.map(item => `
                                        <tr>
                                            <td class="px-4 py-2 text-sm">${escapeHtml(item.id)}</td>
                                            <td class="px-4 py-2 text-sm">${escapeHtml(item.item_type)}</td>
                                            <td class="px-4 py-2 text-sm">
                                                <span class="status-badge status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
                                            </td>
                                            <td class="px-4 py-2 text-sm">${escapeHtml(new Date(item.created_at).toLocaleString())}</td>
                                            <td class="px-4 py-2 text-sm">${escapeHtml(item.processing_time_seconds || 'N/A')}s</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    ` : ''}

                    ${job.error_message ? `
                    <div class="bg-destructive/5 p-3 rounded">
                        <h4 class="font-semibold text-red-800 mb-1">Error Message</h4>
                        <p class="text-destructive">${escapeHtml(job.error_message)}</p>
                    </div>
                    ` : ''}
                </div>
            `,
            size: 'xlarge',
            buttons: [
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

    async exportData() {
        // API /api/import-history/{id}/export not yet implemented
        this.showError('Import history API is not yet available.');
    }

    confirmRollback(jobId) {
        // Use modal manager to create a standardized confirmation modal
        const modalId = modalManager.createModal({
            title: 'Confirm Rollback',
            content: `
                <div class="space-y-4">
                    <p class="text-foreground">
                        Are you sure you want to rollback this import? This will:
                    </p>
                    <ul class="list-disc list-inside text-foreground">
                        <li>Delete all applications created by this import</li>
                        <li>Remove all APQC mappings</li>
                        <li>Delete ArchiMate elements</li>
                        <li>This action cannot be undone</li>
                    </ul>
                    <p class="text-sm text-muted-foreground">
                        Rollback is only available within 7 days of import.
                    </p>
                </div>
            `,
            size: 'small',
            buttons: [
                {
                    text: '<i class="fas fa-undo"></i> Rollback',
                    class: 'px-4 py-2 bg-destructive text-primary-foreground rounded hover:bg-destructive',
                    action: 'rollback',
                    handler: () => this.rollback(jobId)
                },
                {
                    text: 'Cancel',
                    class: 'px-4 py-2 bg-muted text-foreground rounded hover:bg-muted/70',
                    action: 'cancel',
                    closeOnClick: true
                }
            ]
        });

        // Open the modal
        modalManager.open(modalId);
    }

    async rollback() {
        // API /api/import-history/{id}/rollback not yet implemented
        this.showError('Import history API is not yet available.');
    }

    async retryFailed() {
        // API /api/import-history/{id}/retry-failed not yet implemented
        this.showError('Import history API is not yet available.');
    }

    startProgressMonitoring() {
        // Clear existing interval
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }

        // Check if there are any running jobs
        const runningJobs = this.importHistory.filter(job => job.status === 'running');

        if (runningJobs.length > 0) {
            // Update progress every 5 seconds for running jobs
            this.progressInterval = setInterval(() => {
                this.updateRunningJobsProgress();
            }, 5000);
        }
    }

    async updateRunningJobsProgress() {
        // API /api/import-history/{id}/progress not yet implemented — no-op
    }

    applyFilters() {
        this.loadImportHistory();
    }

    clearFilters() {
        this.filters = {
            status: '',
            dateFrom: '',
            dateTo: ''
        };

        // Reset filter inputs
        const statusFilter = document.getElementById('status-filter');
        const dateFromFilter = document.getElementById('date-from');
        const dateToFilter = document.getElementById('date-to');

        if (statusFilter) statusFilter.value = '';
        if (dateFromFilter) dateFromFilter.value = '';
        if (dateToFilter) dateToFilter.value = '';

        this.loadImportHistory();
    }

    updateStatistics() {
        const statsContainer = document.getElementById('statistics');
        if (!statsContainer) return;

        const total = this.importHistory.length;
        const completed = this.importHistory.filter(job => job.status === 'completed').length;
        const failed = this.importHistory.filter(job => job.status === 'failed').length;
        const running = this.importHistory.filter(job => job.status === 'running').length;

        safeHTML(statsContainer, `
            <div class="grid grid-cols-4 gap-4">
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${total}</div>
                    <div class="text-sm text-muted-foreground">Total Imports</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-emerald-600">${completed}</div>
                    <div class="text-sm text-muted-foreground">Completed</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-destructive">${failed}</div>
                    <div class="text-sm text-muted-foreground">Failed</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${running}</div>
                    <div class="text-sm text-muted-foreground">Running</div>
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
    window.importHistoryManager = new ImportHistoryManager();
});
