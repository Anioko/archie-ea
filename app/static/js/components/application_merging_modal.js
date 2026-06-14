/**
 * Application Merging Modal - JavaScript
 * Extracted from components/application_merging_modal.html inline script
 * Handles merge candidate discovery, preview, execution, and batch operations
 */

// Application Merging JavaScript
let mergeCandidatesData = [];
let currentMergePage = 1;
let mergeItemsPerPage = 10;
let currentMergeFilter = 'all';
let currentMergeSearch = '';

// XSS prevention utility
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  let div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

// Toast notification for merge operations (avoids dependency on parent page)
function showMergeToast(message, type) {
  type = type || 'info';
  // Use parent showToast if available (direct API)
  if (typeof showToast === 'function') {
    showToast(message, type);
    return;
  }
  // Try event-based toast system (CustomEvent API)
  try {
    if (typeof CustomEvent !== 'undefined') {
      window.dispatchEvent(new CustomEvent('toast', { detail: { message: message, type: type } }));
      return;
    }
  } catch (e) { /* fall through to inline toast */ }
  let colors = {
    success: 'bg-emerald-500/10 border-emerald-200 text-green-800',
    error: 'bg-destructive/10 border-destructive/20 text-red-800',
    warning: 'bg-amber-100 border-amber-200 text-amber-800',
    info: 'bg-primary/10 border-primary/20 text-primary/90'
  };
  let toast = document.createElement('div');
  let existingToasts = document.querySelectorAll('[data-toast]');
  let topOffset = 16 + (existingToasts.length * 64);
  toast.className = 'fixed right-4 z-[10001] p-4 rounded-lg border shadow-lg max-w-sm ' + (colors[type] || colors.info);
  toast.style.top = topOffset + 'px';
  toast.setAttribute('data-toast', '1');
  toast.setAttribute('role', 'alert');
  safeHTML(toast, '<div class="flex items-start gap-3"><p class="text-sm font-medium">' +
    escapeHtml(String(message)) + '</p>' +
    '<button onclick="this.closest(\'[role=alert]\').remove()" class="ml-auto flex-shrink-0 text-current opacity-70 hover:opacity-100">&times;</button></div>');
  document.body.appendChild(toast);
  setTimeout(function() {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(function() { toast.remove(); }, 300);
  }, type === 'error' ? 6000 : 4000);
}

// CSRF token helper with meta tag fallback
function getMergeCSRFToken() {
  let formInput = document.querySelector('[name=csrf_token]');
  let formToken = formInput ? formInput.value : null;
  if (formToken) return formToken;
  let metaTag = document.querySelector('meta[name="csrf-token"]');
  let metaToken = metaTag ? metaTag.content : null;
  if (metaToken) return metaToken;
  console.warn('getMergeCSRFToken: No CSRF token found in form input or meta tag');
  return '';
}

// Default merge strategy (avoids 4 duplicated 7-line objects)
let DEFAULT_MERGE_STRATEGY = {
  description: 'primary',
  business_owner: 'primary',
  cost_center: 'primary',
  criticality: 'primary',
  merge_capabilities: true,
  merge_technologies: true
};

// Initialize merging functionality
function initializeApplicationMerging() {
  // Event listeners
  let thresholdEl = document.getElementById('similarity-threshold');
  if (thresholdEl) thresholdEl.addEventListener('input', updateThresholdDisplay);
  let findBtn = document.getElementById('find-candidates-btn');
  if (findBtn) findBtn.addEventListener('click', findMergeCandidates);
  let searchEl = document.getElementById('merge-search');
  if (searchEl) searchEl.addEventListener('input', filterMergeCandidates);
  let filterEl = document.getElementById('candidate-filter');
  if (filterEl) filterEl.addEventListener('change', filterMergeCandidates);
  let executeBtn = document.getElementById('execute-merge-btn');
  if (executeBtn) executeBtn.addEventListener('click', executeMerge);

  // Pagination buttons
  let prevBtn = document.getElementById('merge-prev-btn');
  if (prevBtn) prevBtn.addEventListener('click', function() {
    if (currentMergePage > 1) {
      currentMergePage--;
      displayMergeCandidatesList();
    }
  });
  let nextBtn = document.getElementById('merge-next-btn');
  if (nextBtn) nextBtn.addEventListener('click', function() {
    let filtered = filterCandidatesData();
    let totalPages = Math.ceil(filtered.length / mergeItemsPerPage);
    if (currentMergePage < totalPages) {
      currentMergePage++;
      displayMergeCandidatesList();
    }
  });

  // Modal close buttons
  document.querySelectorAll('[data-action="close-merge-modal"]').forEach(function(btn) {
    btn.addEventListener('click', closeMergeModal);
  });
  document.querySelectorAll('[data-action="close-preview-modal"]').forEach(function(btn) {
    btn.addEventListener('click', closePreviewModal);
  });

  // Escape key is handled by Platform.modal — no bespoke listener needed
}

function updateThresholdDisplay() {
  let threshold = document.getElementById('similarity-threshold').value;
  document.getElementById('threshold-value').textContent = threshold;
}

let _mergeModalTrigger = null;  // Track which element opened the modal for focus return

function openMergeModal() {
  _mergeModalTrigger = document.activeElement;
  Platform.modal.open('application-merging-modal');
  // Focus the first interactive element inside the modal
  let firstFocusable = document.querySelector('#application-merging-modal button, #application-merging-modal input, #application-merging-modal select');
  if (firstFocusable) firstFocusable.focus();
}

function closeMergeModal() {
  Platform.modal.close('application-merging-modal');
  // Reset all state (including search/filter that persisted across sessions)
  mergeCandidatesData = [];
  currentMergePage = 1;
  currentMergeSearch = '';
  currentMergeFilter = 'all';
  // Reset UI
  document.getElementById('merge-results').classList.add('hidden');
  document.getElementById('merge-config-section').classList.remove('hidden');
  document.getElementById('merge-empty').classList.add('hidden');
  // Clear input values
  let searchInput = document.getElementById('merge-search');
  if (searchInput) searchInput.value = '';
  let filterSelect = document.getElementById('candidate-filter');
  if (filterSelect) filterSelect.value = 'all';
  let thresholdInput = document.getElementById('similarity-threshold');
  if (thresholdInput) {
    thresholdInput.value = '0.7';
    let thresholdDisplay = document.getElementById('threshold-value');
    if (thresholdDisplay) thresholdDisplay.textContent = '0.7';
  }
  // Return focus to the element that triggered the modal
  if (_mergeModalTrigger && typeof _mergeModalTrigger.focus === 'function') {
    _mergeModalTrigger.focus();
    _mergeModalTrigger = null;
  }
}

function closePreviewModal() {
  Platform.modal.close('merge-preview-modal');
}

async function findMergeCandidates() {
  let threshold = parseFloat(document.getElementById('similarity-threshold').value);
  let maxCandidates = parseInt(document.getElementById('max-candidates').value);

  // Show loading
  document.getElementById('merge-config-section').classList.add('hidden');
  document.getElementById('merge-loading').classList.remove('hidden');
  document.getElementById('merge-results').classList.add('hidden');
  document.getElementById('merge-empty').classList.add('hidden');

  try {
    let mergeMode = document.getElementById('merge-mode').value;
    let response = await fetch('/dashboard/api/applications/merging/candidates?threshold=' + threshold + '&limit=' + maxCandidates + '&mode=' + mergeMode, {
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('Server error (' + response.status + '): ' + response.statusText);
    }

    let data = await response.json();

    if (data.status === 'success') {
      mergeCandidatesData = data.candidates;
      currentMergePage = 1;
      displayMergeResults(data);
    } else {
      throw new Error(data.message || 'Failed to get candidates');
    }
  } catch (error) {
    console.error('Error finding merge candidates:', error);
    document.getElementById('merge-loading').classList.add('hidden');
    document.getElementById('merge-empty').classList.remove('hidden');
    let errorMsg = document.getElementById('merge-empty').querySelector('p');
    if (errorMsg) errorMsg.textContent = 'Error: ' + error.message;
  }
}

function displayMergeResults(data) {
  document.getElementById('merge-loading').classList.add('hidden');

  if (data.candidates.length === 0) {
    document.getElementById('merge-empty').classList.remove('hidden');
    return;
  }

  // Display summary
  displayMergeSummary(data);

  // Display candidates
  displayMergeCandidatesList();

  // Show results
  document.getElementById('merge-results').classList.remove('hidden');
}

function displayMergeSummary(data) {
  let summaryHtml =
    '<div class="p-4 rounded bg-card border border-border">' +
      '<div class="text-2xl font-semibold text-primary">' + data.total_candidates + '</div>' +
      '<div class="text-muted-foreground text-sm">Merge Candidates</div>' +
    '</div>' +
    '<div class="p-4 rounded bg-card border border-border">' +
      '<div class="text-2xl font-semibold text-emerald-600">' + data.total_analyzed + '</div>' +
      '<div class="text-muted-foreground text-sm">Applications Analyzed</div>' +
    '</div>' +
    '<div class="p-4 rounded bg-card border border-border">' +
      '<div class="text-2xl font-semibold text-amber-600">' + (data.threshold_used * 100).toFixed(0) + '%</div>' +
      '<div class="text-muted-foreground text-sm">Similarity Threshold</div>' +
    '</div>' +
    '<div class="p-4 rounded bg-card border border-border">' +
      '<button type="button" data-action="batchMergeHighSimilarity" class="w-full px-4 py-2 text-sm bg-emerald-500 text-primary-foreground rounded hover:bg-emerald-600">' +
        'Batch Merge High Similarity' +
      '</button>' +
      '<div class="text-muted-foreground text-xs mt-2">Auto-merge candidates &gt;90% similarity</div>' +
    '</div>';
  safeHTML(document.getElementById('merge-summary'), summaryHtml);
}

function displayMergeCandidatesList() {
  let filteredCandidates = filterCandidatesData();
  let totalPages = Math.ceil(filteredCandidates.length / mergeItemsPerPage);
  let startIndex = (currentMergePage - 1) * mergeItemsPerPage;
  let endIndex = startIndex + mergeItemsPerPage;
  let pageCandidates = filteredCandidates.slice(startIndex, endIndex);

  let candidatesHtml = pageCandidates.map(function(candidate) {
    let similarityClass = candidate.similarity_score > 0.8 ? 'bg-emerald-500/10 text-green-800' :
      candidate.similarity_score > 0.7 ? 'bg-amber-500/10 text-yellow-800' :
      'bg-muted text-foreground';

    let matchReasonsHtml = '';
    if (candidate.match_reasons.length > 0) {
      matchReasonsHtml =
        '<div class="mb-3">' +
          '<h6 class="m-0 font-medium text-emerald-700 mb-1">Match Reasons:</h6>' +
          '<ul class="text-sm text-muted-foreground list-disc list-inside">' +
            candidate.match_reasons.map(function(reason) { return '<li>' + escapeHtml(reason) + '</li>'; }).join('') +
          '</ul>' +
        '</div>';
    }

    let conflictsHtml = '';
    if (candidate.conflicts.length > 0) {
      conflictsHtml =
        '<div class="mb-3">' +
          '<h6 class="m-0 font-medium text-destructive mb-1">Potential Conflicts:</h6>' +
          '<ul class="text-sm text-muted-foreground list-disc list-inside">' +
            candidate.conflicts.map(function(conflict) { return '<li>' + escapeHtml(conflict) + '</li>'; }).join('') +
          '</ul>' +
        '</div>';
    }

    return '<div class="border border-border rounded-lg p-4 hover:shadow-md transition-shadow">' +
      '<div class="flex justify-between items-start mb-4">' +
        '<div class="flex-1">' +
          '<div class="flex items-center gap-4 mb-2">' +
            '<h5 class="m-0 font-semibold text-lg">' + escapeHtml(candidate.primary_app.name) + '</h5>' +
            '<span class="px-2 py-1 text-xs bg-primary/10 text-primary/90 rounded">Primary</span>' +
            '<span class="px-3 py-1 text-xs font-medium rounded-full ' + similarityClass + '">' + (candidate.similarity_score * 100).toFixed(0) + '% Similar</span>' +
          '</div>' +
          '<p class="text-muted-foreground text-sm mb-2">' + escapeHtml(candidate.primary_app.description || 'No description') + '</p>' +
          '<div class="flex gap-4 text-sm text-muted-foreground">' +
            '<span>Owner: ' + escapeHtml(candidate.primary_app.business_owner || 'N/A') + '</span>' +
            '<span>Users: ' + (candidate.primary_app.user_count || 0) + '</span>' +
            '<span>Criticality: ' + escapeHtml(candidate.primary_app.criticality || 'N/A') + '</span>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="border-t border-border pt-4">' +
        '<div class="flex items-center gap-4 mb-2">' +
          '<h6 class="m-0 font-medium">Duplicate Application:</h6>' +
          '<span class="font-semibold">' + escapeHtml(candidate.duplicate_app.name) + '</span>' +
        '</div>' +
        '<p class="text-muted-foreground text-sm mb-2">' + escapeHtml(candidate.duplicate_app.description || 'No description') + '</p>' +
        '<div class="flex gap-4 text-sm text-muted-foreground mb-3">' +
          '<span>Owner: ' + escapeHtml(candidate.duplicate_app.business_owner || 'N/A') + '</span>' +
          '<span>Users: ' + (candidate.duplicate_app.user_count || 0) + '</span>' +
          '<span>Criticality: ' + escapeHtml(candidate.duplicate_app.criticality || 'N/A') + '</span>' +
        '</div>' +
        matchReasonsHtml +
        conflictsHtml +
        '<div class="flex gap-2 mt-4">' +
          '<button type="button" data-action="previewMerge" data-params=\'[' + candidate.primary_app.id + ', ' + candidate.duplicate_app.id + ']\'' +
                  ' class="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary">' +
            'Preview Merge' +
          '</button>' +
          '<button type="button" data-action="quickMerge" data-params=\'[' + candidate.primary_app.id + ', ' + candidate.duplicate_app.id + ']\'' +
                  ' class="px-3 py-1.5 text-sm bg-destructive text-primary-foreground rounded hover:bg-red-700">' +
            'Quick Merge' +
          '</button>' +
          '<button type="button" data-action="ignoreCandidate" data-params=\'[' + candidate.primary_app.id + ', ' + candidate.duplicate_app.id + ']\'' +
                  ' class="px-3 py-1.5 text-sm border border-input rounded hover:bg-muted/50">' +
            'Ignore' +
          '</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');

  safeHTML(document.getElementById('merge-candidates-list'), candidatesHtml || '<p class="text-center text-muted-foreground">No candidates match your search criteria.</p>');

  // Update pagination
  updateMergePagination(filteredCandidates.length, totalPages);
}

function filterCandidatesData() {
  let filtered = mergeCandidatesData;

  // Apply similarity filter
  if (currentMergeFilter === 'high') {
    filtered = filtered.filter(function(c) { return c.similarity_score > 0.8; });
  } else if (currentMergeFilter === 'medium') {
    filtered = filtered.filter(function(c) { return c.similarity_score >= 0.7 && c.similarity_score <= 0.8; });
  } else if (currentMergeFilter === 'conflicts') {
    filtered = filtered.filter(function(c) { return c.conflicts.length > 0; });
  }

  // Apply search filter
  if (currentMergeSearch) {
    let searchLower = currentMergeSearch.toLowerCase();
    filtered = filtered.filter(function(c) {
      return c.primary_app.name.toLowerCase().includes(searchLower) ||
        c.duplicate_app.name.toLowerCase().includes(searchLower) ||
        (c.primary_app.description && c.primary_app.description.toLowerCase().includes(searchLower)) ||
        (c.duplicate_app.description && c.duplicate_app.description.toLowerCase().includes(searchLower));
    });
  }

  return filtered;
}

function filterMergeCandidates() {
  currentMergeSearch = document.getElementById('merge-search').value;
  currentMergeFilter = document.getElementById('candidate-filter').value;
  currentMergePage = 1;
  displayMergeCandidatesList();
}

function updateMergePagination(totalItems, totalPages) {
  let start = totalItems === 0 ? 0 : (currentMergePage - 1) * mergeItemsPerPage + 1;
  let end = Math.min(currentMergePage * mergeItemsPerPage, totalItems);

  document.getElementById('merge-pagination-info').textContent = 'Showing ' + start + '-' + end + ' of ' + totalItems + ' candidates';

  let prevBtn = document.getElementById('merge-prev-btn');
  let nextBtn = document.getElementById('merge-next-btn');
  let pagesContainer = document.getElementById('merge-pages');

  prevBtn.disabled = currentMergePage === 1;
  nextBtn.disabled = currentMergePage >= totalPages;

  // Generate page numbers
  let pagesHtml = '';
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentMergePage - 2 && i <= currentMergePage + 2)) {
      pagesHtml += '<button type="button" data-action="goToMergePage" data-id="' + i + '" class="px-3 py-1.5 text-sm border rounded ' +
        (i === currentMergePage ? 'bg-primary text-primary-foreground border-primary' : 'border-input hover:bg-muted/50') +
        '">' + i + '</button>';
    } else if (i === currentMergePage - 3 || i === currentMergePage + 3) {
      pagesHtml += '<span class="px-2 text-muted-foreground">...</span>';
    }
  }
  safeHTML(pagesContainer, pagesHtml);
}

function goToMergePage(page) {
  currentMergePage = page;
  displayMergeCandidatesList();
  // Scroll candidates list to top on page change
  let listEl = document.getElementById('merge-candidates-list');
  if (listEl) listEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function previewMerge(primaryId, duplicateId) {
  try {
    let response = await fetch('/dashboard/api/applications/merging/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getMergeCSRFToken()
      },
      body: JSON.stringify({
        primary_app_id: primaryId,
        duplicate_app_id: duplicateId,
        merge_strategy: DEFAULT_MERGE_STRATEGY
      }),
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('Server error (' + response.status + '): ' + response.statusText);
    }

    let data = await response.json();

    if (data.status === 'success') {
      displayMergePreview(data.preview, primaryId, duplicateId);
      Platform.modal.open('merge-preview-modal');
    } else {
      throw new Error(data.message || 'Failed to preview merge');
    }
  } catch (error) {
    console.error('Error previewing merge:', error);
    showMergeToast('Error previewing merge: ' + error.message, 'error');
  }
}

function displayMergePreview(preview, primaryId, duplicateId) {
  let mergedResultHtml = '';
  let mergedKeys = Object.keys(preview.merged_result);
  for (let k = 0; k < mergedKeys.length; k++) {
    let field = mergedKeys[k];
    let value = preview.merged_result[field];
    let displayValue = Array.isArray(value) ? value.map(function(v) { return escapeHtml(v); }).join(', ') : escapeHtml(value);
    mergedResultHtml += '<div><strong>' + escapeHtml(field) + ':</strong> ' + displayValue + '</div>';
  }

  let changesHtml = '';
  if (preview.changes_detected.length > 0) {
    changesHtml =
      '<div class="mb-6">' +
        '<h4 class="font-semibold mb-3 text-amber-700">Changes Detected</h4>' +
        '<div class="p-4 border border-yellow-200 rounded bg-amber-500/5">' +
          '<ul class="text-sm list-disc list-inside">' +
            preview.changes_detected.map(function(change) { return '<li>' + escapeHtml(change) + ' will be updated</li>'; }).join('') +
          '</ul>' +
        '</div>' +
      '</div>';
  }

  let previewHtml =
    '<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">' +
      '<div>' +
        '<h4 class="font-semibold mb-3 text-emerald-700">Primary Application (Will be kept)</h4>' +
        '<div class="p-4 border border-emerald-200 rounded bg-emerald-500/5">' +
          '<h5 class="font-medium">' + escapeHtml(preview.primary_app.name) + '</h5>' +
          '<p class="text-sm text-muted-foreground mt-1">' + escapeHtml(preview.primary_app.description || 'No description') + '</p>' +
          '<div class="mt-2 text-sm">' +
            '<div>Owner: ' + escapeHtml(preview.primary_app.business_owner || 'N/A') + '</div>' +
            '<div>Criticality: ' + escapeHtml(preview.primary_app.criticality || 'N/A') + '</div>' +
            '<div>Users: ' + (preview.primary_app.user_count || 0) + '</div>' +
            '<div>Capabilities: ' + ((preview.primary_app.capabilities && preview.primary_app.capabilities.length) || 0) + '</div>' +
            '<div>Technologies: ' + ((preview.primary_app.technologies && preview.primary_app.technologies.length) || 0) + '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div>' +
        '<h4 class="font-semibold mb-3 text-destructive">Duplicate Application (Will be merged)</h4>' +
        '<div class="p-4 border border-destructive/20 rounded bg-destructive/5">' +
          '<h5 class="font-medium">' + escapeHtml(preview.duplicate_app.name) + '</h5>' +
          '<p class="text-sm text-muted-foreground mt-1">' + escapeHtml(preview.duplicate_app.description || 'No description') + '</p>' +
          '<div class="mt-2 text-sm">' +
            '<div>Owner: ' + escapeHtml(preview.duplicate_app.business_owner || 'N/A') + '</div>' +
            '<div>Criticality: ' + escapeHtml(preview.duplicate_app.criticality || 'N/A') + '</div>' +
            '<div>Users: ' + (preview.duplicate_app.user_count || 0) + '</div>' +
            '<div>Capabilities: ' + ((preview.duplicate_app.capabilities && preview.duplicate_app.capabilities.length) || 0) + '</div>' +
            '<div>Technologies: ' + ((preview.duplicate_app.technologies && preview.duplicate_app.technologies.length) || 0) + '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div class="mb-6">' +
      '<h4 class="font-semibold mb-3 text-primary">Merge Result Preview</h4>' +
      '<div class="p-4 border border-primary/20 rounded bg-primary/5">' +
        '<div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">' +
          mergedResultHtml +
        '</div>' +
      '</div>' +
    '</div>' +
    changesHtml +
    '<div class="p-4 bg-muted rounded">' +
      '<p class="text-sm text-foreground">' +
        '<strong>Important:</strong> This merge will combine the two applications. The duplicate application will be marked as merged and will no longer appear in the active application list. This action cannot be undone.' +
      '</p>' +
    '</div>';

  safeHTML(document.getElementById('merge-preview-content'), previewHtml);

  // Store merge data for execution
  document.getElementById('execute-merge-btn').dataset.primaryId = primaryId;
  document.getElementById('execute-merge-btn').dataset.duplicateId = duplicateId;
}

async function executeMerge() {
  let mergeBtn = document.getElementById('execute-merge-btn');
  let primaryId = parseInt(mergeBtn.dataset.primaryId);
  let duplicateId = parseInt(mergeBtn.dataset.duplicateId);

  let modalId = window.modalManager.createModal({
      title: 'Execute Merge',
      content: '<p class="text-sm text-muted-foreground">Are you sure you want to execute this merge? This action cannot be undone.</p>',
      size: 'small',
      buttons: [
          { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
          { text: 'Execute Merge', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'merge', handler: function() { _doExecuteMerge(primaryId, duplicateId); } }
      ]
  });
  window.modalManager.open(modalId);
}

async function _doExecuteMerge(primaryId, duplicateId) {
  let mergeBtn = document.getElementById('execute-merge-btn');
  mergeBtn.disabled = true;
  mergeBtn._origText = mergeBtn.textContent;
  mergeBtn.textContent = 'Merging...';

  try {
    let response = await fetch('/dashboard/api/applications/merging/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getMergeCSRFToken()
      },
      body: JSON.stringify({
        primary_app_id: primaryId,
        duplicate_app_id: duplicateId,
        merge_strategy: DEFAULT_MERGE_STRATEGY
      }),
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('Server error (' + response.status + '): ' + response.statusText);
    }

    let data = await response.json();

    if (data.status === 'success') {
      showMergeToast('Merge completed successfully!', 'success');
      closePreviewModal();
      closeMergeModal();
      // Refresh the application list
      if (typeof loadTableData === 'function') {
        loadTableData(1, '', '', '');
      }
    } else {
      throw new Error(data.message || 'Merge failed');
    }
  } catch (error) {
    console.error('Error executing merge:', error);
    showMergeToast('Error executing merge: ' + error.message, 'error');
  } finally {
    mergeBtn.disabled = false;
    if (mergeBtn._origText) {
      mergeBtn.textContent = mergeBtn._origText;
      delete mergeBtn._origText;
    }
  }
}

async function quickMerge(primaryId, duplicateId, triggerBtn) {
  let modalId = window.modalManager.createModal({
      title: 'Quick Merge',
      content: '<p class="text-sm text-muted-foreground">Are you sure you want to quickly merge these applications? This will use the default merge strategy.</p>',
      size: 'small',
      buttons: [
          { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
          { text: 'Quick Merge', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'merge', handler: function() { _doQuickMerge(primaryId, duplicateId, triggerBtn); } }
      ]
  });
  window.modalManager.open(modalId);
}

async function _doQuickMerge(primaryId, duplicateId, triggerBtn) {
  // Disable the quick merge button that was clicked
  let clickedBtn = triggerBtn || null;
  if (clickedBtn) {
    clickedBtn.disabled = true;
    clickedBtn._origText = clickedBtn.textContent;
    clickedBtn.textContent = 'Merging...';
  }

  try {
    let response = await fetch('/dashboard/api/applications/merging/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getMergeCSRFToken()
      },
      body: JSON.stringify({
        primary_app_id: primaryId,
        duplicate_app_id: duplicateId,
        merge_strategy: DEFAULT_MERGE_STRATEGY
      }),
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('Server error (' + response.status + '): ' + response.statusText);
    }

    let data = await response.json();

    if (data.status === 'success') {
      showMergeToast('Quick merge completed successfully!', 'success');
      // Refresh the candidates list
      findMergeCandidates();
      // Refresh the application list
      if (typeof loadTableData === 'function') {
        loadTableData(1, '', '', '');
      }
    } else {
      throw new Error(data.message || 'Quick merge failed');
    }
  } catch (error) {
    console.error('Error executing quick merge:', error);
    showMergeToast('Error executing quick merge: ' + error.message, 'error');
  } finally {
    if (clickedBtn) {
      clickedBtn.disabled = false;
      if (clickedBtn._origText) {
        clickedBtn.textContent = clickedBtn._origText;
        delete clickedBtn._origText;
      }
    }
  }
}

async function ignoreCandidate(primaryId, duplicateId) {
  try {
    // Persist ignore decision server-side
    let response = await fetch('/applications/rationalization/api/ignore-merge-candidate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getMergeCSRFToken()
      },
      body: JSON.stringify({ primary_id: primaryId, duplicate_id: duplicateId }),
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('Server error (' + response.status + '): ' + response.statusText);
    }

    // Only remove from UI after server confirms
    mergeCandidatesData = mergeCandidatesData.filter(function(c) {
      return !(c.primary_app.id === primaryId && c.duplicate_app.id === duplicateId);
    });
    displayMergeCandidatesList();
  } catch (err) {
    console.error('Failed to persist ignore decision:', err);
    showMergeToast('Failed to ignore candidate: ' + err.message, 'error');
  }
}

async function batchMergeHighSimilarity() {
  // Use configured threshold + 0.1 as the "high similarity" bar (minimum 0.85)
  let thresholdEl = document.getElementById('similarity-threshold');
  let configuredThreshold = parseFloat(thresholdEl ? thresholdEl.value : '0.7');
  let batchThreshold = Math.max(0.85, Math.min(configuredThreshold + 0.1, 0.98));
  let highSimilarityCandidates = mergeCandidatesData.filter(function(c) { return c.similarity_score > batchThreshold; });

  if (highSimilarityCandidates.length === 0) {
    showMergeToast('No candidates with >' + Math.round(batchThreshold * 100) + '% similarity found.', 'warning');
    return;
  }

  let candidateCount = highSimilarityCandidates.length;
  let thresholdPct = Math.round(batchThreshold * 100);
  let modalId = window.modalManager.createModal({
      title: 'Batch Merge High-Similarity Duplicates',
      content: '<p class="text-sm text-muted-foreground">Found ' + candidateCount + ' candidate(s) with &gt;' + thresholdPct + '% similarity. This will merge each duplicate into its primary application using the default strategy.</p><p class="text-sm text-muted-foreground mt-2">Proceed with batch merge?</p>',
      size: 'small',
      buttons: [
          { text: 'Cancel', class: 'px-4 py-2 text-sm font-medium text-foreground bg-background border border-border rounded-md hover:bg-muted', action: 'cancel', handler: function() {} },
          { text: 'Batch Merge', class: 'px-4 py-2 text-sm font-medium text-destructive-foreground bg-destructive border border-transparent rounded-md hover:bg-destructive/90', action: 'merge', handler: function() { _doBatchMerge(highSimilarityCandidates); } }
      ]
  });
  window.modalManager.open(modalId);
}

async function _doBatchMerge(highSimilarityCandidates) {
  // Disable individual merge buttons to prevent race conditions
  document.querySelectorAll('.merge-action-btn').forEach(function(btn) { btn.disabled = true; });

  let csrfToken = getMergeCSRFToken();
  let succeeded = 0;
  let failed = 0;
  let errors = [];
  let total = highSimilarityCandidates.length;

  // Show progress indicator in the batch merge button area
  let summaryEl = document.getElementById('merge-summary');
  let progressHtml =
    '<div id="batch-merge-progress" class="col-span-4 p-4 rounded bg-primary/5 border border-primary/20">' +
      '<div class="flex items-center gap-3 mb-2">' +
        '<div class="inline-block w-5 h-5 border-2 border-primary/20 border-t-blue-500 rounded-full animate-spin"></div>' +
        '<span class="text-sm font-medium text-primary/90">Batch merging in progress...</span>' +
      '</div>' +
      '<div class="w-full bg-primary/20 rounded-full h-2 mb-1">' +
        '<div id="batch-merge-bar" class="bg-primary h-2 rounded-full transition-all duration-300" style="width: 0%"></div>' +
      '</div>' +
      '<p id="batch-merge-status" class="text-xs text-primary mt-1">Processing 0 of ' + total + '...</p>' +
    '</div>';
  summaryEl.insertAdjacentHTML('beforeend', progressHtml);

  for (let i = 0; i < highSimilarityCandidates.length; i++) {
    let candidate = highSimilarityCandidates[i];
    let pct = Math.round(((i + 1) / total) * 100);

    // Update progress
    let bar = document.getElementById('batch-merge-bar');
    let status = document.getElementById('batch-merge-status');
    if (bar) bar.style.width = pct + '%';
    if (status) status.textContent = 'Processing ' + (i + 1) + ' of ' + total + '... (' + succeeded + ' merged, ' + failed + ' failed)';

    try {
      let response = await fetch('/dashboard/api/applications/merging/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          primary_app_id: candidate.primary_app.id,
          duplicate_app_id: candidate.duplicate_app.id,
          merge_strategy: DEFAULT_MERGE_STRATEGY
        }),
        credentials: 'include'
      });

      if (!response.ok) {
        failed++;
        errors.push(candidate.primary_app.name + ' + ' + candidate.duplicate_app.name + ': Server error (' + response.status + ')');
        continue;
      }

      let data = await response.json();
      if (data.status === 'success') {
        succeeded++;
      } else {
        failed++;
        errors.push(candidate.primary_app.name + ' + ' + candidate.duplicate_app.name + ': ' + (data.message || 'Unknown error'));
      }
    } catch (error) {
      failed++;
      errors.push(candidate.primary_app.name + ' + ' + candidate.duplicate_app.name + ': ' + error.message);
    }
  }

  // Remove progress indicator
  let progressEl = document.getElementById('batch-merge-progress');
  if (progressEl) progressEl.remove();

  if (failed === 0) {
    showMergeToast('Batch merge complete: ' + succeeded + ' merged successfully.', 'success');
  } else {
    showMergeToast('Batch merge: ' + succeeded + ' succeeded, ' + failed + ' failed. Check console for details.', failed > succeeded ? 'error' : 'warning');
    if (errors.length > 0) {
      console.warn('Batch merge errors:', errors);
    }
  }

  // Re-enable individual merge buttons
  document.querySelectorAll('.merge-action-btn').forEach(function(btn) { btn.disabled = false; });

  // Refresh candidates list and application table
  findMergeCandidates();
  if (typeof loadTableData === 'function') {
    loadTableData(1, '', '', '');
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeApplicationMerging);
