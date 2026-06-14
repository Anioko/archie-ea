/**
 * LLM Selector Dropdown - External JavaScript
 * Extracted from app/templates/components/llm_selector.html
 * Uses window.__APP_CONFIG__ bridge for server-side values
 *
 * Required APP_CONFIG keys:
 *   - selectorId: The selector element ID prefix (from Jinja2 {{ selector_id }})
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

(function() {
  // Mirror the guard used in sidebar.js — do not fire auth-required API calls when not authenticated
  if (window.__userAuthenticated === false) return;

  let selectorId = APP_CONFIG.selectorId || 'llm-selector';
  let container = document.getElementById(selectorId + '-container');
  let button = document.getElementById(selectorId + '-button');
  let dropdown = document.getElementById(selectorId + '-dropdown');
  let label = document.getElementById(selectorId + '-label');
  let optionsContainer = document.getElementById(selectorId + '-options');

  // Bail out if the selector widget is not present in this page's DOM
  if (!container || !button || !dropdown || !label || !optionsContainer) return;

  let availableLLMs = [];
  let currentPreference = null;

  // Toggle dropdown
  button.addEventListener('click', function(e) {
    e.stopPropagation();
    let isExpanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', !isExpanded);
    dropdown.classList.toggle('hidden');
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', function(e) {
    if (!container.contains(e.target)) {
      button.setAttribute('aria-expanded', 'false');
      dropdown.classList.add('hidden');
    }
  });

  // Fetch available LLMs
  function loadAvailableLLMs() {
    return fetch('/api/v1/llm/available', {
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json'
      }
    })
    .then(function(response) {
      if (!response.ok) {
        throw new Error('Failed to load LLMs');
      }
      return response.json();
    })
    .then(function(data) {
      if (data.success) {
        availableLLMs = data.llms || [];
        renderOptions();
      } else {
        showError(data.error || 'Failed to load LLMs');
      }
    })
    .catch(function(error) {
      console.error('Error loading LLMs:', error);
      showError('Unable to load LLM options');
    });
  }

  // Fetch user preference
  function loadUserPreference() {
    return fetch('/api/v1/llm/preference', {
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json'
      }
    })
    .then(function(response) {
      if (response.ok) {
        return response.json();
      }
      return null;
    })
    .then(function(data) {
      if (data && data.success && data.preference) {
        currentPreference = data.preference;
        updateLabel();
      }
    })
    .catch(function(error) {
      console.error('Error loading preference:', error);
    });
  }

  // Render dropdown options
  function renderOptions() {
    safeHTML(optionsContainer, '');

    availableLLMs.forEach(function(llm) {
      let option = document.createElement('div');
      option.className = 'px-4 py-2 text-sm hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center justify-between';
      option.setAttribute('role', 'menuitem');

      // Check if this is the currently selected option
      let isSelected = currentPreference && currentPreference.provider === llm.id;
      if (isSelected) {
        option.classList.add('bg-accent', 'text-accent-foreground');
      }

      // Status indicator
      let statusIndicator = '';
      if (llm.id === 'none') {
        statusIndicator = '<span class="text-muted-foreground text-xs">Manual mode</span>';
      } else if (llm.available) {
        statusIndicator = '<span class="text-emerald-600 text-xs flex items-center gap-1">' +
          '<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>' +
          llm.key_count + ' key(s)' +
        '</span>';
      } else {
        statusIndicator = '<span class="text-destructive text-xs flex items-center gap-1">' +
          '<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>' +
          'Not configured' +
        '</span>';
      }

      let modelsHtml = '';
      if (llm.models && llm.models.length > 0) {
        let modelsText = llm.models.slice(0, 2).join(', ');
        if (llm.models.length > 2) modelsText += '...';
        modelsHtml = '<span class="text-xs text-muted-foreground">' + modelsText + '</span>';
      }

      safeHTML(option, '<div class="flex flex-col">' +
        '<span class="font-medium">' + llm.name + '</span>' +
        modelsHtml +
      '</div>' +
      statusIndicator);

      // Only allow clicking if available or is "none"
      if (llm.available || llm.id === 'none') {
        (function(llmRef) {
          option.addEventListener('click', function() {
            selectLLM(llmRef.id, llmRef.models[0]);
          });
        })(llm);
      } else {
        option.classList.add('opacity-50', 'cursor-not-allowed');
        option.title = 'No API keys configured for this provider';
      }

      optionsContainer.appendChild(option);
    });

    updateLabel();
  }

  // Update the button label
  function updateLabel() {
    let selected = availableLLMs.find(function(llm) {
      return currentPreference && currentPreference.provider === llm.id;
    });

    if (selected) {
      label.textContent = selected.name;
    } else {
      // Default to first available or "No LLM"
      let defaultLLM = availableLLMs.find(function(llm) { return llm.id === 'none'; }) || availableLLMs[0];
      if (defaultLLM) {
        label.textContent = defaultLLM.name;
        // Auto-select if no preference set
        if (!currentPreference) {
          selectLLM(defaultLLM.id, defaultLLM.models[0], false);
        }
      } else {
        label.textContent = 'No LLMs available';
      }
    }
  }

  // Select an LLM
  function selectLLM(provider, model, save) {
    if (save === undefined) save = true;
    currentPreference = { provider: provider, model: model };
    updateLabel();
    renderOptions(); // Re-render to update selection highlight

    // Close dropdown
    button.setAttribute('aria-expanded', 'false');
    dropdown.classList.add('hidden');

    if (save) {
      let csrfToken = '';
      let csrfMeta = document.querySelector('meta[name="csrf-token"]');
      if (csrfMeta) csrfToken = csrfMeta.content;

      fetch('/api/v1/llm/preference', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ provider: provider, model: model })
      })
      .then(function(response) {
        return response.json();
      })
      .then(function(data) {
        if (data.success) {
          showNotification('LLM preference saved', 'success');
        } else {
          showNotification('Failed to save preference: ' + (data.error || 'Unknown error'), 'error');
        }
      })
      .catch(function(error) {
        console.error('Error saving preference:', error);
        showNotification('Failed to save preference', 'error');
      });
    }

    // Dispatch custom event for other components to listen to
    window.dispatchEvent(new CustomEvent('llmSelected', {
      detail: { provider: provider, model: model }
    }));
  }

  // Show error state
  function showError(message) {
    label.textContent = message;
    label.classList.add('text-destructive');
    safeHTML(optionsContainer, '<div class="px-4 py-2 text-sm text-destructive">' +
      message +
    '</div>');
  }

  // Show notification
  function showNotification(message, type) {
    if (!type) type = 'info';
    let colorClass = type === 'success' ? 'bg-emerald-500/10 text-green-800 border border-emerald-200' :
      type === 'error' ? 'bg-destructive/10 text-red-800 border border-destructive/20' :
      'bg-primary/10 text-primary/90 border border-primary/20';

    let notification = document.createElement('div');
    notification.className = 'fixed bottom-4 right-4 px-4 py-2 rounded-lg text-sm font-medium z-50 transition-opacity duration-300 ' + colorClass;
    notification.textContent = message;

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(function() {
      notification.classList.add('opacity-0');
      setTimeout(function() {
        notification.remove();
      }, 300);
    }, 3000);
  }

  // Initialize
  loadAvailableLLMs();
  loadUserPreference();
})();
