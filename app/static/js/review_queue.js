/**
 * Review Queue Manager - Frontend JavaScript Integration
 * Handles all review queue interactions and API communication
 */

class ReviewQueueManager {
    constructor() {
        this.selectedItems = new Set();
        this.reviewItems = [];
        this.statistics = {};
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadReviewQueue();
        this.startRealTimeUpdates();
    }

    bindEvents() {
        // Select all checkbox
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                this.selectAll(e.target.checked);
            });
        }

        // Bulk action buttons
        const bulkApprove = document.getElementById('bulk-approve');
        if (bulkApprove) {
            bulkApprove.addEventListener('click', () => {
                this.bulkApprove();
            });
        }

        const bulkReject = document.getElementById('bulk-reject');
        if (bulkReject) {
            bulkReject.addEventListener('click', () => {
                this.bulkReject();
            });
        }

        // Threshold controls
        const autoAcceptThreshold = document.getElementById('auto-accept-threshold');
        if (autoAcceptThreshold) {
            autoAcceptThreshold.addEventListener('input', (e) => {
                this.updateThreshold('auto-accept', e.target.value);
            });
        }

        const rejectionThreshold = document.getElementById('rejection-threshold');
        if (rejectionThreshold) {
            rejectionThreshold.addEventListener('input', (e) => {
                this.updateThreshold('rejection', e.target.value);
            });
        }

        // Save thresholds button
        const saveThresholds = document.getElementById('save-thresholds');
        if (saveThresholds) {
            saveThresholds.addEventListener('click', () => {
                this.saveThresholds();
            });
        }

        // Search/filter
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterItems(e.target.value);
            });
        }

        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filterByStatus(e.target.value);
            });
        }
    }

    async loadReviewQueue() {
        try {
            this.showLoading(true);
            const response = await fetch('/api/review-queue');
            const data = await response.json();

            if (data.success) {
                this.reviewItems = data.items;
                this.statistics = data.statistics;
                this.renderReviewQueue();
                this.updateStatistics();
            } else {
                this.showError('Failed to load review queue: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to load review queue:', error);
            this.showError('Error loading review queue');
        } finally {
            this.showLoading(false);
        }
    }

    renderReviewQueue() {
        const container = document.getElementById('review-items');
        if (!container) return;

        if (this.reviewItems.length === 0) {
            safeHTML(container, `
                <div class="text-center py-8 text-muted-foreground">
                    <i class="fas fa-check-circle text-4xl mb-4"></i>
                    <p>No items pending review</p>
                </div>
            `);
            return;
        }

        safeHTML(container, this.reviewItems.map(item => `
            <div class="review-item border rounded-lg p-4 mb-4 ${item.status === 'pending' ? 'border-yellow-300' : 'border-border'}" data-item-id="${item.id}">
                <div class="flex items-start justify-between">
                    <div class="flex items-start space-x-3 flex-1">
                        <input type="checkbox" class="item-checkbox mt-1" value="${item.id}"
                               onchange="reviewQueueManager.toggleItem(${item.id})">
                        <div class="flex-1">
                            <div class="flex items-center space-x-2 mb-2">
                                <span class="confidence-badge ${this.getConfidenceClass(item.confidence_score)}">
                                    ${(item.confidence_score * 100).toFixed(1)}%
                                </span>
                                <span class="mapping-type">${item.mapping_type}</span>
                                <span class="status-${item.status}">${item.status}</span>
                            </div>
                            <h4 class="font-semibold mb-1">${item.application_name}</h4>
                            <p class="text-sm text-muted-foreground mb-2">${item.mapping_data?.description || 'No description'}</p>
                            <div class="text-xs text-muted-foreground">
                                <span class="mr-3">AI: ${item.ai_model_used}</span>
                                <span class="mr-3">Threshold: ${item.threshold_name}</span>
                                <span>Created: ${new Date(item.created_at).toLocaleString()}</span>
                            </div>
                            ${item.rationale ? `<div class="mt-2 p-2 bg-primary/5 rounded text-sm"><strong>AI Rationale:</strong> ${item.rationale}</div>` : ''}
                        </div>
                    </div>
                    <div class="flex space-x-2">
                        <button onclick="reviewQueueManager.viewDetails(${item.id})"
                                class="px-3 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary">
                            <i class="fas fa-eye"></i> Details
                        </button>
                        <button onclick="reviewQueueManager.quickApprove(${item.id})"
                                class="px-3 py-1 text-sm bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600">
                            <i class="fas fa-check"></i> Approve
                        </button>
                        <button onclick="reviewQueueManager.quickReject(${item.id})"
                                class="px-3 py-1 text-sm bg-destructive text-primary-foreground rounded hover:bg-destructive">
                            <i class="fas fa-times"></i> Reject
                        </button>
                    </div>
                </div>
            </div>
        `).join(''));
    }

    getConfidenceClass(score) {
        if (score >= 0.8) return 'high-confidence';
        if (score >= 0.6) return 'medium-confidence';
        return 'low-confidence';
    }

    toggleItem(itemId) {
        if (this.selectedItems.has(itemId)) {
            this.selectedItems.delete(itemId);
        } else {
            this.selectedItems.add(itemId);
        }
        this.updateSelectAllState();
    }

    selectAll(checked) {
        const checkboxes = document.querySelectorAll('.item-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            const itemId = parseInt(checkbox.value);
            if (checked) {
                this.selectedItems.add(itemId);
            } else {
                this.selectedItems.delete(itemId);
            }
        });
    }

    updateSelectAllState() {
        const selectAll = document.getElementById('select-all');
        const checkboxes = document.querySelectorAll('.item-checkbox');
        const checkedCount = document.querySelectorAll('.item-checkbox:checked').length;

        if (selectAll) {
            selectAll.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
        }
    }

    async approveItem(itemId, reason = '') {
        try {
            const response = await fetch(`/api/review-queue/${itemId}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    decision_reason: reason || 'Approved by user',
                    reviewer_role: 'architect',
                    reviewer_experience_level: 'senior',
                    quality_assessment: {
                        accuracy: { score: 0.9, weight: 0.4 },
                        completeness: { score: 0.8, weight: 0.3 },
                        relevance: { score: 0.7, weight: 0.3 }
                    },
                    identified_issues: [],
                    suggested_improvements: [],
                    human_confidence_estimate: 0.9,
                    ai_accuracy_assessment: 4,
                    correction_made: false,
                    corrected_data: {},
                    review_duration_seconds: 30
                })
            });

            const result = await response.json();
            if (result.success) {
                this.removeItem(itemId);
                this.showSuccess(`Item ${itemId} approved successfully`);
                await this.loadReviewQueue(); // Refresh
            } else {
                this.showError('Failed to approve item: ' + result.error);
            }
        } catch (error) {
            console.error('Failed to approve item:', error);
            this.showError('Error approving item');
        }
    }

    async rejectItem(itemId, reason = '') {
        try {
            const response = await fetch(`/api/review-queue/${itemId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    decision_reason: reason || 'Rejected by user',
                    reviewer_role: 'architect',
                    reviewer_experience_level: 'senior',
                    quality_assessment: {
                        accuracy: { score: 0.3, weight: 0.4 },
                        completeness: { score: 0.5, weight: 0.3 },
                        relevance: { score: 0.4, weight: 0.3 }
                    },
                    identified_issues: [],
                    suggested_improvements: [],
                    human_confidence_estimate: 0.3,
                    ai_accuracy_assessment: 2,
                    correction_made: false,
                    corrected_data: {},
                    review_duration_seconds: 30
                })
            });

            const result = await response.json();
            if (result.success) {
                this.removeItem(itemId);
                this.showSuccess(`Item ${itemId} rejected successfully`);
                await this.loadReviewQueue(); // Refresh
            } else {
                this.showError('Failed to reject item: ' + result.error);
            }
        } catch (error) {
            console.error('Failed to reject item:', error);
            this.showError('Error rejecting item');
        }
    }

    async bulkApprove() {
        const itemIds = Array.from(this.selectedItems);
        if (itemIds.length === 0) {
            this.showError('No items selected for approval');
            return;
        }

        const self = this;
        const count = itemIds.length;
        const modalId = window.modalManager.createModal({
            title: 'Approve Items',
            content: '<p class="text-sm text-muted-foreground">Approve ' + count + ' selected items?</p>',
            size: 'small',
            buttons: [
                { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                { text: 'Approve', class: 'px-4 py-2 text-sm font-medium text-primary-foreground bg-emerald-600 border border-transparent rounded-md hover:bg-emerald-700', action: 'approve', handler: async function() {
                    self._doBulkApprove(itemIds);
                } }
            ]
        });
        window.modalManager.open(modalId);
    }

    async _doBulkApprove(itemIds) {
        try {
            const response = await fetch('/api/review-queue/bulk-approve', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_ids: itemIds,
                    decision_reason: 'Bulk approved by user',
                    reviewer_role: 'architect',
                    reviewer_experience_level: 'senior',
                    quality_assessment: {
                        accuracy: { score: 0.9, weight: 0.4 },
                        completeness: { score: 0.8, weight: 0.3 },
                        relevance: { score: 0.7, weight: 0.3 }
                    },
                    identified_issues: [],
                    suggested_improvements: [],
                    human_confidence_estimate: 0.9,
                    ai_accuracy_assessment: 4,
                    correction_made: false,
                    corrected_data: {},
                    review_duration_seconds: 30
                })
            });

            const result = await response.json();
            if (result.success) {
                this.selectedItems.clear();
                this.showSuccess(`Bulk approval completed: ${result.successful_count} approved, ${result.failed_count} failed`);
                await this.loadReviewQueue(); // Refresh
            } else {
                this.showError('Bulk approval failed: ' + result.error);
            }
        } catch (error) {
            console.error('Failed to bulk approve:', error);
            this.showError('Error in bulk approval');
        }
    }

    async bulkReject() {
        const itemIds = Array.from(this.selectedItems);
        if (itemIds.length === 0) {
            this.showError('No items selected for rejection');
            return;
        }

        const self = this;
        const count = itemIds.length;
        const modalId = window.modalManager.createModal({
            title: 'Reject Items',
            content: '<p class="text-sm text-muted-foreground">Reject ' + count + ' selected items?</p>',
            size: 'small',
            buttons: [
                { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                { text: 'Reject', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'reject', handler: async function() {
                    self._doBulkReject(itemIds);
                } }
            ]
        });
        window.modalManager.open(modalId);
    }

    async _doBulkReject(itemIds) {
        try {
            const response = await fetch('/api/review-queue/bulk-reject', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_ids: itemIds,
                    decision_reason: 'Bulk rejected by user',
                    reviewer_role: 'architect',
                    reviewer_experience_level: 'senior',
                    quality_assessment: {
                        accuracy: { score: 0.3, weight: 0.4 },
                        completeness: { score: 0.5, weight: 0.3 },
                        relevance: { score: 0.4, weight: 0.3 }
                    },
                    identified_issues: [],
                    suggested_improvements: [],
                    human_confidence_estimate: 0.3,
                    ai_accuracy_assessment: 2,
                    correction_made: false,
                    corrected_data: {},
                    review_duration_seconds: 30
                })
            });

            const result = await response.json();
            if (result.success) {
                this.selectedItems.clear();
                this.showSuccess(`Bulk rejection completed: ${result.successful_count} rejected, ${result.failed_count} failed`);
                await this.loadReviewQueue(); // Refresh
            } else {
                this.showError('Bulk rejection failed: ' + result.error);
            }
        } catch (error) {
            console.error('Failed to bulk reject:', error);
            this.showError('Error in bulk rejection');
        }
    }

    removeItem(itemId) {
        this.reviewItems = this.reviewItems.filter(item => item.id !== itemId);
        this.selectedItems.delete(itemId);
        this.renderReviewQueue();
        this.updateStatistics();
    }

    viewDetails(itemId) {
        const item = this.reviewItems.find(item => item.id === itemId);
        if (!item) return;

        // Create modal with detailed information
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-foreground bg-opacity-50 flex items-center justify-center z-50';
        safeHTML(modal, `
            <div class="bg-background rounded-lg p-6 max-w-2xl max-h-screen overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold">Review Item Details</h3>
                    <button onclick="this.closest('.fixed').remove()" class="text-muted-foreground hover:text-foreground">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="space-y-4">
                    <div>
                        <strong>Application:</strong> ${item.application_name}
                    </div>
                    <div>
                        <strong>Mapping Type:</strong> ${item.mapping_type}
                    </div>
                    <div>
                        <strong>Confidence Score:</strong> ${(item.confidence_score * 100).toFixed(1)}%
                    </div>
                    <div>
                        <strong>AI Model:</strong> ${item.ai_model_used}
                    </div>
                    <div>
                        <strong>Threshold:</strong> ${item.threshold_name}
                    </div>
                    <div>
                        <strong>Status:</strong> ${item.status}
                    </div>
                    <div>
                        <strong>Created:</strong> ${new Date(item.created_at).toLocaleString()}
                    </div>
                    ${item.rationale ? `
                    <div>
                        <strong>AI Rationale:</strong>
                        <div class="p-3 bg-primary/5 rounded mt-1">${item.rationale}</div>
                    </div>
                    ` : ''}
                    ${item.mapping_data ? `
                    <div>
                        <strong>Mapping Data:</strong>
                        <pre class="p-3 bg-muted/30 rounded mt-1 text-sm">${JSON.stringify(item.mapping_data, null, 2)}</pre>
                    </div>
                    ` : ''}
                    ${item.alternatives && item.alternatives.length > 0 ? `
                    <div>
                        <strong>Alternatives:</strong>
                        <ul class="list-disc list-inside mt-1">
                            ${item.alternatives.map(alt => `<li>${alt.name || alt.description}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}
                </div>
                <div class="flex space-x-3 mt-6">
                    <button onclick="reviewQueueManager.approveItem(${item.id}); this.closest('.fixed').remove();"
                            class="px-4 py-2 bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600">
                        <i class="fas fa-check"></i> Approve
                    </button>
                    <button onclick="reviewQueueManager.rejectItem(${item.id}); this.closest('.fixed').remove();"
                            class="px-4 py-2 bg-destructive text-primary-foreground rounded hover:bg-destructive">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `);
        document.body.appendChild(modal);
    }

    quickApprove(itemId) {
        const self = this;
        const modalId = window.modalManager.createModal({
            title: 'Approve Item',
            content: '<p class="text-sm text-muted-foreground">Approve this item?</p>',
            size: 'small',
            buttons: [
                { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                { text: 'Approve', class: 'px-4 py-2 text-sm font-medium text-primary-foreground bg-emerald-600 border border-transparent rounded-md hover:bg-emerald-700', action: 'approve', handler: function() { self.approveItem(itemId); } }
            ]
        });
        window.modalManager.open(modalId);
    }

    quickReject(itemId) {
        const self = this;
        const modalId = window.modalManager.createModal({
            title: 'Reject Item',
            content: '<p class="text-sm text-muted-foreground">Reject this item?</p>',
            size: 'small',
            buttons: [
                { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
                { text: 'Reject', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'reject', handler: function() { self.rejectItem(itemId); } }
            ]
        });
        window.modalManager.open(modalId);
    }

    updateStatistics() {
        const statsContainer = document.getElementById('statistics');
        if (!statsContainer || !this.statistics) return;

        safeHTML(statsContainer, `
            <div class="grid grid-cols-4 gap-4">
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${this.statistics.pending_count || 0}</div>
                    <div class="text-sm text-muted-foreground">Pending</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-emerald-600">${this.statistics.approved_count || 0}</div>
                    <div class="text-sm text-muted-foreground">Approved</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-destructive">${this.statistics.rejected_count || 0}</div>
                    <div class="text-sm text-muted-foreground">Rejected</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl font-bold text-primary">${this.statistics.total_count || 0}</div>
                    <div class="text-sm text-muted-foreground">Total</div>
                </div>
            </div>
        `);
    }

    updateThreshold(type, value) {
        const valueDisplay = document.getElementById(`${type}-value`);
        if (valueDisplay) {
            valueDisplay.textContent = value + '%';
        }
    }

    async saveThresholds() {
        const autoAccept = document.getElementById('auto-accept-threshold').value;
        const rejection = document.getElementById('rejection-threshold').value;

        try {
            const response = await fetch('/api/review-queue/thresholds', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    threshold_name: 'User Configured Thresholds',
                    threshold_type: 'global',
                    minimum_confidence: (autoAccept - 30) / 100,
                    auto_approval_threshold: autoAccept / 100,
                    rejection_threshold: rejection / 100,
                    requires_human_review: true,
                    user_id: 1 // This should come from session
                })
            });

            const result = await response.json();
            if (result.success) {
                this.showSuccess('Thresholds saved successfully');
            } else {
                this.showError('Failed to save thresholds: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving thresholds:', error);
            this.showError('Error saving thresholds');
        }
    }

    filterItems(searchTerm) {
        const filtered = this.reviewItems.filter(item => {
            const searchLower = searchTerm.toLowerCase();
            return item.application_name?.toLowerCase().includes(searchLower) ||
                   item.mapping_type?.toLowerCase().includes(searchLower) ||
                   item.rationale?.toLowerCase().includes(searchLower);
        });
        this.renderFilteredItems(filtered);
    }

    filterByStatus(status) {
        const filtered = status === 'all' ? this.reviewItems :
                       this.reviewItems.filter(item => item.status === status);
        this.renderFilteredItems(filtered);
    }

    renderFilteredItems(items) {
        const originalItems = this.reviewItems;
        this.reviewItems = items;
        this.renderReviewQueue();
        this.reviewItems = originalItems;
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

    startRealTimeUpdates() {
        // Update queue every 30 seconds
        this._pollIntervalId = setInterval(() => {
            this.loadReviewQueue();
        }, 30000);
    }

    stopRealTimeUpdates() {
        if (this._pollIntervalId) {
            clearInterval(this._pollIntervalId);
            this._pollIntervalId = null;
        }
    }

    destroy() {
        this.stopRealTimeUpdates();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reviewQueueManager = new ReviewQueueManager();
});

// Clean up polling on page unload and logout (ISS-018)
window.addEventListener('beforeunload', () => {
    if (window.reviewQueueManager) {
        window.reviewQueueManager.stopRealTimeUpdates();
    }
});
document.addEventListener('user:logout', () => {
    if (window.reviewQueueManager) {
        window.reviewQueueManager.stopRealTimeUpdates();
    }
});
