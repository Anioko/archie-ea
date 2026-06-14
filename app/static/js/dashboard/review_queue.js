/**
 * Review Queue - External JavaScript
 * Extracted from app/templates/dashboard/review_queue.html
 * Uses window.__APP_CONFIG__ bridge for server-side values
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

let reviewItems = [];
let selectedItems = new Set();
let currentReviewItem = null;

// Load review queue on page load
document.addEventListener('DOMContentLoaded', function() {
    loadReviewQueue();
});

function loadReviewQueue() {
    fetch('/api/review-queue')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                reviewItems = data.items;
                displayReviewItems();
                updatePendingCount(data.total_items);
            } else {
                console.error('Failed to load review queue:', data.error);
            }
        })
        .catch(function(error) {
            console.error('Error loading review queue:', error);
        })
        .finally(function() {
            document.getElementById('loading').classList.add('hidden');
        });
}

function displayReviewItems() {
    let container = document.getElementById('review-items');
    let emptyState = document.getElementById('empty-state');

    if (reviewItems.length === 0) {
        safeHTML(container, '');
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    safeHTML(container, reviewItems.map(function(item) {
        let confidenceLevel = getConfidenceLevel(item.confidence_score);
        let confidencePercent = Math.round(item.confidence_score * 100);
        let rationale = (item.confidence_factors && item.confidence_factors.rationale) ? item.confidence_factors.rationale : 'No rationale provided';
        let itemType = item.item_type.replace('_', ' ').toUpperCase();

        let alternativesHtml = '';
        if (item.confidence_factors && item.confidence_factors.alternatives) {
            let altItems = item.confidence_factors.alternatives.map(function(alt) {
                return '<li>' + alt.name + ' (' + Math.round(alt.confidence * 100) + '%)</li>';
            }).join('');
            alternativesHtml = '<div class="text-sm text-muted-foreground mb-2">' +
                '<strong>Alternatives:</strong>' +
                '<ul class="list-disc list-inside mt-1">' + altItems + '</ul>' +
                '</div>';
        }

        return '<div class="review-item bg-background" data-item-id="' + item.id + '">' +
            '<div class="flex items-start justify-between">' +
                '<div class="flex items-start space-x-3 flex-1">' +
                    '<input type="checkbox" class="item-checkbox mt-1" data-item-id="' + item.id + '"' +
                           ' onchange="toggleItemSelection(' + item.id + ')"' +
                           ' class="w-4 h-4 text-primary rounded focus:ring-primary">' +
                    '<div class="flex-1">' +
                        '<div class="flex items-center space-x-2 mb-2">' +
                            '<h2 class="text-lg font-semibold text-foreground">' + item.item_name + '</h2>' +
                            '<span class="confidence-' + confidenceLevel + ' px-2 py-1 rounded text-xs font-medium">' +
                                confidencePercent + '% confidence' +
                            '</span>' +
                            '<span class="bg-muted text-foreground px-2 py-1 rounded text-xs font-medium">' +
                                itemType +
                            '</span>' +
                        '</div>' +
                        '<div class="text-sm text-muted-foreground mb-2">' +
                            '<strong>AI Rationale:</strong> ' + rationale +
                        '</div>' +
                        alternativesHtml +
                        '<div class="flex items-center space-x-4 text-sm text-muted-foreground">' +
                            '<span><i class="fas fa-robot mr-1"></i>' + item.ai_model_used + '</span>' +
                            '<span><i class="fas fa-clock mr-1"></i>' + formatDate(item.created_at) + '</span>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="flex space-x-2 ml-4">' +
                    '<button data-action="openReviewModal" data-id="' + item.id + '"' +
                            ' class="bg-primary text-primary-foreground px-3 py-1 rounded text-sm hover:bg-primary/90 transition-colors">' +
                        '<i class="fas fa-eye mr-1"></i>Review' +
                    '</button>' +
                    '<button data-action="quickApprove" data-id="' + item.id + '"' +
                            ' class="bg-emerald-600 text-primary-foreground px-3 py-1 rounded text-sm hover:bg-green-700 transition-colors">' +
                        '<i class="fas fa-check mr-1"></i>Approve' +
                    '</button>' +
                    '<button data-action="quickReject" data-id="' + item.id + '"' +
                            ' class="bg-destructive text-primary-foreground px-3 py-1 rounded text-sm hover:bg-red-700 transition-colors">' +
                        '<i class="fas fa-times mr-1"></i>Reject' +
                    '</button>' +
                '</div>' +
            '</div>' +
        '</div>';
    }).join(''));
}

function getConfidenceLevel(score) {
    if (score >= 0.8) return 'high';
    if (score >= 0.5) return 'medium';
    return 'low';
}

function formatDate(dateString) {
    let date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function toggleItemSelection(itemId) {
    if (selectedItems.has(itemId)) {
        selectedItems.delete(itemId);
    } else {
        selectedItems.add(itemId);
    }
    updateSelectAllCheckbox();
}

function toggleSelectAll() {
    let selectAll = document.getElementById('select-all');
    let checkboxes = document.querySelectorAll('.item-checkbox');

    checkboxes.forEach(function(checkbox) {
        checkbox.checked = selectAll.checked;
        let itemId = parseInt(checkbox.dataset.itemId);
        if (selectAll.checked) {
            selectedItems.add(itemId);
        } else {
            selectedItems.delete(itemId);
        }
    });
}

function updateSelectAllCheckbox() {
    let selectAll = document.getElementById('select-all');
    let checkboxes = document.querySelectorAll('.item-checkbox');
    let checkedCount = document.querySelectorAll('.item-checkbox:checked').length;

    selectAll.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
}

function bulkApprove() {
    if (selectedItems.size === 0) {
        Platform.toast.warning('Please select items to approve');
        return;
    }

    let itemIds = Array.from(selectedItems);
    let count = selectedItems.size;
    let modalId = window.modalManager.createModal({
        title: 'Approve Items',
        content: '<p class="text-sm text-muted-foreground">Approve ' + count + ' selected items?</p>',
        size: 'small',
        buttons: [
            { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
            { text: 'Approve', class: 'px-4 py-2 text-sm font-medium text-primary-foreground bg-emerald-600 border border-transparent rounded-md hover:bg-emerald-700', action: 'approve', handler: function() {
                fetch('/api/review-queue/bulk-approve', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        item_ids: itemIds,
                        decision_reason: 'Bulk approved',
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
                })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.success) {
                        selectedItems.clear();
                        loadReviewQueue();
                        Platform.toast.success('Bulk approval completed: ' + data.successful_count + ' approved, ' + data.failed_count + ' failed');
                    } else {
                        Platform.toast.error('Bulk approval failed: ' + data.error);
                    }
                })
                .catch(function(error) {
                    console.error('Error in bulk approve:', error);
                    Platform.toast.error('Error in bulk approve');
                });
            } }
        ]
    });
    window.modalManager.open(modalId);
}

function bulkReject() {
    if (selectedItems.size === 0) {
        Platform.toast.warning('Please select items to reject');
        return;
    }

    let itemIds = Array.from(selectedItems);
    let count = selectedItems.size;
    let modalId = window.modalManager.createModal({
        title: 'Reject Items',
        content: '<p class="text-sm text-muted-foreground">Reject ' + count + ' selected items?</p>',
        size: 'small',
        buttons: [
            { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
            { text: 'Reject', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'reject', handler: function() {
                fetch('/api/review-queue/bulk-reject', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        item_ids: itemIds,
                        decision_reason: 'Bulk rejected',
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
                })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.success) {
                        selectedItems.clear();
                        loadReviewQueue();
                        Platform.toast.success('Bulk rejection completed: ' + data.successful_count + ' rejected, ' + data.failed_count + ' failed');
                    } else {
                        Platform.toast.error('Bulk rejection failed: ' + data.error);
                    }
                })
                .catch(function(error) {
                    console.error('Error in bulk reject:', error);
                    Platform.toast.error('Error in bulk reject');
                });
            } }
        ]
    });
    window.modalManager.open(modalId);
}

function quickApprove(itemId) {
    submitReviewDecision(itemId, 'approve');
}

function quickReject(itemId) {
    submitReviewDecision(itemId, 'reject');
}

function openReviewModal(itemId) {
    currentReviewItem = reviewItems.find(function(item) { return item.id === itemId; });
    if (!currentReviewItem) return;

    let modal = document.getElementById('review-modal');
    let content = document.getElementById('modal-content');

    let confidenceLevel = getConfidenceLevel(currentReviewItem.confidence_score);
    let confidencePercent = currentReviewItem.confidence_score * 100;
    let confidenceColor = confidenceLevel === 'high' ? 'green' : (confidenceLevel === 'medium' ? 'yellow' : 'red');
    let rationale = (currentReviewItem.confidence_factors && currentReviewItem.confidence_factors.rationale) ? currentReviewItem.confidence_factors.rationale : 'No rationale provided';

    let alternativesHtml = '';
    if (currentReviewItem.confidence_factors && currentReviewItem.confidence_factors.alternatives) {
        let altItems = currentReviewItem.confidence_factors.alternatives.map(function(alt) {
            return '<li>' + alt.name + ' (' + Math.round(alt.confidence * 100) + '%)</li>';
        }).join('');
        alternativesHtml = '<div>' +
            '<label class="block text-sm font-medium text-foreground mb-1">Alternative Suggestions</label>' +
            '<ul class="list-disc list-inside text-sm text-muted-foreground">' + altItems + '</ul>' +
            '</div>';
    }

    safeHTML(content, '<div class="space-y-4">' +
        '<div>' +
            '<h3 class="font-semibold text-foreground">' + currentReviewItem.item_name + '</h3>' +
            '<p class="text-sm text-muted-foreground">' + currentReviewItem.item_type.replace('_', ' ').toUpperCase() + '</p>' +
        '</div>' +
        '<div>' +
            '<label class="block text-sm font-medium text-foreground mb-1">Confidence Score</label>' +
            '<div class="flex items-center space-x-2">' +
                '<div class="flex-1 bg-muted rounded-full h-2">' +
                    '<div class="bg-' + confidenceColor + '-500 h-2 rounded-full"' +
                         ' style="width: ' + confidencePercent + '%"></div>' +
                '</div>' +
                '<span class="text-sm font-medium">' + Math.round(confidencePercent) + '%</span>' +
            '</div>' +
        '</div>' +
        '<div>' +
            '<label class="block text-sm font-medium text-foreground mb-1">AI Rationale</label>' +
            '<p class="text-sm text-muted-foreground">' + rationale + '</p>' +
        '</div>' +
        alternativesHtml +
        '<div>' +
            '<label class="block text-sm font-medium text-foreground mb-1">Review Notes</label>' +
            '<textarea id="review-notes" rows="3" class="w-full border border-border rounded-lg px-3 py-2 focus:ring-primary focus:border-primary"' +
                      ' placeholder="Add your review notes..."></textarea>' +
        '</div>' +
    '</div>');

    Platform.modal.open('review-modal');
}

function closeReviewModal() {
    Platform.modal.close('review-modal');
    currentReviewItem = null;
}

function submitReview(decision) {
    if (!currentReviewItem) return;

    let notes = document.getElementById('review-notes').value;
    submitReviewDecision(currentReviewItem.id, decision, notes);
    closeReviewModal();
}

function submitReviewDecision(itemId, decision, notes) {
    notes = notes || '';
    let endpoint = decision === 'approve' ? '/api/review-queue/' + itemId + '/approve' : '/api/review-queue/' + itemId + '/reject';

    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            decision_type: decision,
            decision_reason: notes || (decision + ' by reviewer'),
            reviewer_id: 1,
            reviewer_role: 'architect',
            reviewer_experience_level: 'senior',
            quality_assessment: {
                accuracy: { score: decision === 'approve' ? 0.9 : 0.3, weight: 0.4 },
                completeness: { score: 0.8, weight: 0.3 },
                relevance: { score: 0.7, weight: 0.3 }
            },
            identified_issues: [],
            suggested_improvements: [],
            human_confidence_estimate: decision === 'approve' ? 0.9 : 0.3,
            ai_accuracy_assessment: decision === 'approve' ? 4 : 2,
            correction_made: false,
            corrected_data: {},
            review_duration_seconds: 30
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            loadReviewQueue();
        } else {
            Platform.toast.error('Failed to submit review: ' + data.error);
        }
    })
    .catch(function(error) {
        console.error('Error submitting review:', error);
        Platform.toast.error('Error submitting review');
    });
}

function updateThreshold(type, value) {
    document.getElementById(type + '-value').textContent = value + '%';
}

function saveThresholds() {
    let autoAccept = document.getElementById('auto-accept-threshold').value;

    fetch('/api/review-queue/thresholds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            threshold_name: 'User Configured Thresholds',
            threshold_type: 'global',
            minimum_confidence: (autoAccept - 30) / 100,
            auto_approval_threshold: autoAccept / 100,
            rejection_threshold: 0.3,
            requires_human_review: true,
            user_id: 1
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            Platform.toast.success('Thresholds saved successfully');
        } else {
            Platform.toast.error('Failed to save thresholds: ' + data.error);
        }
    })
    .catch(function(error) {
        console.error('Error saving thresholds:', error);
        Platform.toast.error('Error saving thresholds');
    });
}

function refreshQueue() {
    loadReviewQueue();
}

function updatePendingCount(count) {
    let badge = document.querySelector('.bg-primary\\/10'); // token-migration-ok
    if (badge) {
        badge.textContent = count + ' pending';
    }
}
