/**
 * Process Suggestion Modal - External JavaScript
 * Extracted from app/templates/components/process_suggestion_modal.html
 * Uses window.__APP_CONFIG__ bridge for server-side values (none needed currently)
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

let currentApplicationId = null;
let currentSuggestions = [];

function openProcessSuggestionModal(appId, appName, appDescription) {
  currentApplicationId = appId;

  // Set application info
  document.getElementById('modal-app-name').textContent = appName;
  document.getElementById('modal-app-description').textContent = appDescription || 'No description available';

  // Show modal via shared component
  openModal('process-suggestion');

  // Load suggestions
  loadProcessSuggestions(appId);
}

function closeProcessSuggestionModal() {
  closeModal('process-suggestion');
  currentApplicationId = null;
  currentSuggestions = [];

  // Reset form
  hideManualProcessMapping();
  let searchEl = document.getElementById('process-search');
  if (searchEl) searchEl.value = '';
  let notesEl = document.getElementById('mapping-notes');
  if (notesEl) notesEl.value = '';
}

function loadProcessSuggestions(appId) {
  // Show loading
  document.getElementById('suggestions-loading').classList.remove('hidden');
  document.getElementById('suggestions-list').classList.add('hidden');
  document.getElementById('no-suggestions').classList.add('hidden');

  return fetch('/api/applications/' + appId + '/process-suggestions')
    .then(function(response) {
      return response.json();
    })
    .then(function(data) {
      if (data.suggestions && data.suggestions.length > 0) {
        currentSuggestions = data.suggestions;
        displaySuggestions(data.suggestions);
      } else {
        showNoSuggestions();
      }
    })
    .catch(function(error) {
      console.error('Error loading suggestions:', error);
      showError('Failed to load process suggestions');
    })
    .finally(function() {
      document.getElementById('suggestions-loading').classList.add('hidden');
    });
}

function displaySuggestions(suggestions) {
  let container = document.getElementById('suggestions-list');
  safeHTML(container, '');

  suggestions.forEach(function(suggestion, index) {
    let suggestionEl = createSuggestionElement(suggestion, index);
    container.appendChild(suggestionEl);
  });

  // Update summary
  document.getElementById('suggestions-summary').textContent =
    suggestions.length + ' suggestion' + (suggestions.length !== 1 ? 's' : '') + ' found';

  // Show suggestions list
  container.classList.remove('hidden');
  document.getElementById('no-suggestions').classList.add('hidden');
}

function createSuggestionElement(suggestion, index) {
  let div = document.createElement('div');
  div.className = 'border border-border rounded-lg p-4 space-y-3';
  div.id = 'suggestion-' + index;

  let confidenceColor = getConfidenceColor(suggestion.confidence);
  let confidenceLabel = getConfidenceLabel(suggestion.confidence);

  let processCodeHtml = '';
  if (suggestion.process_code) {
    processCodeHtml = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground">' +
      suggestion.process_code +
    '</span>';
  }

  let matchReasonHtml = '';
  if (suggestion.match_reason) {
    matchReasonHtml = '<div class="text-sm text-muted-foreground mb-2">' +
      '<strong>Match Reason:</strong> ' + suggestion.match_reason +
    '</div>';
  }

  let processTypeHtml = '';
  if (suggestion.process_type) {
    processTypeHtml = '<div class="flex items-center gap-1">' +
      '<i data-lucide="layers" class="w-4 h-4"></i>' +
      '<span>' + suggestion.process_type + '</span>' +
    '</div>';
  }

  safeHTML(div, '<div class="flex items-start justify-between">' +
    '<div class="flex-1">' +
      '<div class="flex items-center gap-3 mb-2">' +
        '<h4 class="text-lg font-medium text-foreground">' + suggestion.process_name + '</h4>' +
        '<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium ' + confidenceColor + '">' +
          confidenceLabel +
        '</span>' +
        processCodeHtml +
      '</div>' +
      matchReasonHtml +
      '<div class="flex items-center gap-4 text-sm text-muted-foreground">' +
        '<div class="flex items-center gap-1">' +
          '<i data-lucide="target" class="w-4 h-4"></i>' +
          '<span>Confidence: ' + Math.round(suggestion.confidence * 100) + '%</span>' +
        '</div>' +
        processTypeHtml +
      '</div>' +
    '</div>' +
    '<div class="flex items-center gap-2 ml-4">' +
      '<button data-action="acceptSuggestion" data-id="' + index + '"' +
        ' class="inline-flex items-center px-3 py-2 bg-emerald-600 text-primary-foreground rounded-md hover:bg-green-700 text-sm">' +
        '<i data-lucide="check" class="w-4 h-4 mr-1"></i>' +
        'Accept' +
      '</button>' +
      '<button data-action="rejectSuggestion" data-id="' + index + '"' +
        ' class="inline-flex items-center px-3 py-2 bg-destructive text-primary-foreground rounded-md hover:bg-red-700 text-sm">' +
        '<i data-lucide="x" class="w-4 h-4 mr-1"></i>' +
        'Reject' +
      '</button>' +
    '</div>' +
  '</div>');

  return div;
}

function getConfidenceColor(confidence) {
  if (confidence >= 0.8) return 'bg-green-500/10 text-emerald-600 border border-green-500/30';
  if (confidence >= 0.6) return 'bg-yellow-500/10 text-amber-600 border border-yellow-500/30';
  return 'bg-red-500/10 text-destructive border border-red-500/30';
}

function getConfidenceLabel(confidence) {
  if (confidence >= 0.8) return 'High Confidence';
  if (confidence >= 0.6) return 'Medium Confidence';
  return 'Low Confidence';
}

function acceptSuggestion(index) {
  let suggestion = currentSuggestions[index];

  return fetch('/api/applications/' + currentApplicationId + '/process-links', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      process_id: suggestion.process_id,
      confidence: suggestion.confidence,
      auto_generated: true,
      notes: 'Auto-mapped with ' + Math.round(suggestion.confidence * 100) + '% confidence: ' + suggestion.match_reason
    })
  })
  .then(function(response) {
    if (response.ok) {
      let suggestionEl = document.getElementById('suggestion-' + index);
      if (suggestionEl) suggestionEl.remove();

      let remainingSuggestions = document.querySelectorAll('#suggestions-list > div').length;
      document.getElementById('suggestions-summary').textContent =
        remainingSuggestions + ' suggestion' + (remainingSuggestions !== 1 ? 's' : '') + ' remaining';

      showSuccess('Process mapping accepted successfully');

      if (remainingSuggestions === 0) {
        showNoSuggestions();
      }
    } else {
      throw new Error('Failed to accept suggestion');
    }
  })
  .catch(function(error) {
    console.error('Error accepting suggestion:', error);
    showError('Failed to accept process mapping');
  });
}

function rejectSuggestion(index) {
  let suggestionEl = document.getElementById('suggestion-' + index);
  if (suggestionEl) suggestionEl.remove();

  let remainingSuggestions = document.querySelectorAll('#suggestions-list > div').length;
  document.getElementById('suggestions-summary').textContent =
    remainingSuggestions + ' suggestion' + (remainingSuggestions !== 1 ? 's' : '') + ' remaining';

  if (remainingSuggestions === 0) {
    showNoSuggestions();
  }
}

function showNoSuggestions() {
  document.getElementById('suggestions-list').classList.add('hidden');
  document.getElementById('no-suggestions').classList.remove('hidden');
  document.getElementById('suggestions-summary').textContent = 'No suggestions found';
}

function showManualProcessMapping() {
  document.getElementById('manual-mapping-form').classList.remove('hidden');
  document.getElementById('process-search').focus();
}

function hideManualProcessMapping() {
  document.getElementById('manual-mapping-form').classList.add('hidden');
  let resultsEl = document.getElementById('process-search-results');
  if (resultsEl) resultsEl.classList.add('hidden');
}

// Process search functionality
(function() {
  let searchEl = document.getElementById('process-search');
  if (searchEl) {
    searchEl.addEventListener('input', function(e) {
      let query = e.target.value.trim();

      if (query.length < 2) {
        document.getElementById('process-search-results').classList.add('hidden');
        return;
      }

      fetch('/api/applications/processes/search?q=' + encodeURIComponent(query))
        .then(function(response) {
          return response.json();
        })
        .then(function(processes) {
          displayProcessSearchResults(processes);
        })
        .catch(function(error) {
          console.error('Error searching processes:', error);
        });
    });
  }
})();

function displayProcessSearchResults(processes) {
  let resultsContainer = document.getElementById('process-search-results');

  if (processes.length === 0) {
    safeHTML(resultsContainer, '<div class="p-3 text-muted-foreground">No processes found</div>');
  } else {
    safeHTML(resultsContainer, processes.map(function(process) {
      let processCodeHtml = process.process_code ? '<div class="text-sm text-muted-foreground">' + process.process_code + '</div>' : '';
      return '<div class="p-3 hover:bg-muted/50 cursor-pointer border-b border-border last:border-b-0"' +
        ' data-action="selectProcess" data-params=\'[' + process.id + ', "' + process.name.replace(/"/g, '&quot;') + '", "' + (process.process_code || '') + '"]\'>' +
        '<div class="font-medium text-foreground">' + process.name + '</div>' +
        processCodeHtml +
      '</div>';
    }).join(''));
  }

  resultsContainer.classList.remove('hidden');
}

let selectedProcess = null;

function selectProcess(processId, processName, processCode) {
  selectedProcess = { id: processId, name: processName, code: processCode };
  document.getElementById('process-search').value = processName;
  document.getElementById('process-search-results').classList.add('hidden');
}

function addManualProcessMapping() {
  if (!selectedProcess) {
    showError('Please select a process');
    return;
  }

  let notes = document.getElementById('mapping-notes').value.trim();

  return fetch('/api/applications/' + currentApplicationId + '/process-links', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      process_id: selectedProcess.id,
      auto_generated: false,
      notes: notes || 'Manual mapping'
    })
  })
  .then(function(response) {
    if (response.ok) {
      showSuccess('Manual process mapping added successfully');
      hideManualProcessMapping();
      loadProcessSuggestions(currentApplicationId);
    } else {
      throw new Error('Failed to add manual mapping');
    }
  })
  .catch(function(error) {
    console.error('Error adding manual mapping:', error);
    showError('Failed to add manual process mapping');
  });
}

function refreshSuggestions() {
  if (currentApplicationId) {
    return loadProcessSuggestions(currentApplicationId);
  }
}

// Utility functions
function showSuccess(message) {
  let notification = document.createElement('div');
  notification.className = 'fixed top-4 right-4 z-[60] p-4 rounded-lg shadow-lg max-w-md bg-green-500/10 text-emerald-600 border border-green-500/30';
  safeHTML(notification, '<div class="flex items-center">' +
    '<i data-lucide="check-circle" class="w-5 h-5 mr-2"></i>' +
    '<span>' + message + '</span>' +
  '</div>');
  document.body.appendChild(notification);
  setTimeout(function() { notification.remove(); }, 3000);
}

function showError(message) {
  let notification = document.createElement('div');
  notification.className = 'fixed top-4 right-4 z-[60] p-4 rounded-lg shadow-lg max-w-md bg-red-500/10 text-destructive border border-red-500/30';
  safeHTML(notification, '<div class="flex items-center">' +
    '<i data-lucide="alert-circle" class="w-5 h-5 mr-2"></i>' +
    '<span>' + message + '</span>' +
  '</div>');
  document.body.appendChild(notification);
  setTimeout(function() { notification.remove(); }, 3000);
}

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
  lucide.createIcons();
}
