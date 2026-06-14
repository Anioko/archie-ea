let APP_CONFIG = window.__APP_CONFIG__ || {};

document.addEventListener('DOMContentLoaded', function() {
    let mode = document.getElementById('currentMode').value;
    let contextId = document.getElementById('contextId').value;

    // Initialize dashboard
    initializeCodeGeneration(mode, contextId);

    // Mode switching
    document.getElementById('enhancementModeBtn').addEventListener('click', function() {
        window.location.href = '/code-generation/dashboard?mode=enhancement';
    });

    document.getElementById('architectureModeBtn').addEventListener('click', function() {
        window.location.href = '/code-generation/dashboard?mode=architecture';
    });
});

function initializeCodeGeneration(mode, contextId) {
    // Load context if available
    if (contextId) {
        loadContext(mode, contextId);
    }

    // Load available templates
    loadTemplates();
}

function loadContext(mode, contextId) {
    let endpoint = mode === 'enhancement'
        ? '/code-generation/api/context/application/' + contextId
        : '/code-generation/api/context/architecture/' + contextId;

    fetch(endpoint)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                displayContext(data, mode);
            }
        })
        .catch(function(error) {
            console.error('Failed to load context:', error);
        });
}

function loadTemplates() {
    fetch('/code-generation/api/templates')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                displayTemplates(data.templates);
            }
        })
        .catch(function(error) {
            console.error('Failed to load templates:', error);
        });
}

function displayContext(data, mode) {
    let contextContainer = document.getElementById('contextContainer');
    if (!contextContainer) return;

    let html = '';

    if (mode === 'enhancement' && data.application) {
        html = '<div class="mb-4">' +
                '<h4 class="font-semibold text-foreground">' + data.application.name + '</h4>' +
                '<p class="text-sm text-muted-foreground">' + (data.application.description || 'No description') + '</p>' +
            '</div>' +
            '<div class="mb-4">' +
                '<h5 class="text-sm font-medium text-foreground mb-2">Components (' + data.application.components.length + ')</h5>' +
                '<ul class="text-sm text-muted-foreground space-y-1">' +
                    data.application.components.slice(0, 5).map(function(comp) {
                        return '<li>&bull; ' + comp.name + '</li>';
                    }).join('') +
                    (data.application.components.length > 5 ? '<li class="text-muted-foreground">... and more</li>' : '') +
                '</ul>' +
            '</div>';
    } else if (mode === 'architecture' && data.view) {
        html = '<div class="mb-4">' +
                '<h4 class="font-semibold text-foreground">' + data.view.name + '</h4>' +
                '<p class="text-sm text-muted-foreground">' + (data.view.description || 'No description') + '</p>' +
            '</div>' +
            '<div class="mb-4">' +
                '<h5 class="text-sm font-medium text-foreground mb-2">Viewpoint</h5>' +
                '<p class="text-sm text-muted-foreground">' + data.view.viewpoint + '</p>' +
            '</div>';
    }

    safeHTML(contextContainer, html);
}

function displayTemplates(templates) {
    let templateContainer = document.getElementById('templateList');
    if (!templateContainer) return;

    let html = '';

    let entries = Object.entries(templates);
    for (let i = 0; i < entries.length; i++) {
        let language = entries[i][0];
        let files = entries[i][1];
        html += '<div class="mb-4">' +
                '<h5 class="text-sm font-medium text-foreground mb-2 capitalize">' + language + '</h5>' +
                '<ul class="text-sm text-muted-foreground space-y-1">' +
                    files.map(function(file) { return '<li>&bull; ' + file + '</li>'; }).join('') +
                '</ul>' +
            '</div>';
    }

    safeHTML(templateContainer, html);
}

function generateCode() {
    let language = document.getElementById('languageSelect').value;
    let framework = document.getElementById('frameworkSelect').value;
    let database = document.getElementById('databaseSelect').value;
    let mode = document.getElementById('currentMode').value;
    let contextId = document.getElementById('contextId').value;

    if (!language) {
        showNotification('Please select a programming language', 'error');
        return;
    }

    // Show loading state
    let generateBtn = document.getElementById('generateBtn');
    let originalText = generateBtn.textContent;
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';

    // Prepare request data
    let requestData = {
        mode: mode,
        context_id: contextId,
        technology_stack: {
            primary_language: language,
            framework: framework,
            primary_database: database
        },
        elements: [] // Will be populated from context
    };

    // Generate code
    fetch('/code-generation/api/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            displayResults(data.artifacts);
            showNotification('Generated ' + data.artifacts.length + ' code artifacts', 'success');
        } else {
            showNotification(data.error || 'Generation failed', 'error');
        }
    })
    .catch(function(error) {
        console.error('Generation failed:', error);
        showNotification('Generation failed: ' + error.message, 'error');
    })
    .finally(function() {
        generateBtn.disabled = false;
        generateBtn.textContent = originalText;
    });
}

function displayResults(artifacts) {
    let resultsContainer = document.getElementById('resultsContainer');
    if (!resultsContainer) return;

    let html = '<div class="space-y-4">';

    artifacts.forEach(function(artifact, index) {
        html += '<div class="border border-border rounded-lg overflow-hidden">' +
                '<div class="bg-muted/30 px-4 py-3 flex justify-between items-center">' +
                    '<div>' +
                        '<h5 class="font-medium text-foreground">' + artifact.name + '</h5>' +
                        '<p class="text-sm text-muted-foreground">' + artifact.language + ' &bull; ' + artifact.type + '</p>' +
                    '</div>' +
                    '<div class="flex space-x-2">' +
                        '<button data-action="copyCode" data-id="' + index + '" class="px-3 py-1 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90">' +
                            'Copy' +
                        '</button>' +
                        '<button data-action="downloadCode" data-id="' + index + '" class="px-3 py-1 text-sm bg-muted-foreground/20 text-primary-foreground rounded hover:bg-muted-foreground/30">' +
                            'Download' +
                        '</button>' +
                    '</div>' +
                '</div>' +
                '<div class="bg-background p-4 overflow-x-auto">' +
                    '<pre class="text-sm text-foreground/90"><code id="code-' + index + '">' + escapeHtml(artifact.content) + '</code></pre>' +
                '</div>' +
            '</div>';
    });

    html += '</div>';
    safeHTML(resultsContainer, html);

    // Store artifacts for copy/download
    window.codeArtifacts = artifacts;
}

function copyCode(index) {
    let artifact = window.codeArtifacts[index];
    navigator.clipboard.writeText(artifact.content)
        .then(function() { showNotification('Code copied to clipboard', 'success'); })
        .catch(function() { showNotification('Failed to copy code', 'error'); });
}

function downloadCode(index) {
    let artifact = window.codeArtifacts[index];
    let blob = new Blob([artifact.content], { type: 'text/plain' });
    let url = URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = artifact.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showNotification('Code downloaded', 'success');
}

function showNotification(message, type) {
    let notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 ' +
        (type === 'success' ? 'bg-emerald-500' : 'bg-destructive') +
        ' text-primary-foreground';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(function() {
        notification.remove();
    }, 3000);
}
