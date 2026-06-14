let APP_CONFIG = window.__APP_CONFIG__ || {};

document.addEventListener('DOMContentLoaded', function() {
    let currentModel = null;
    let currentLayer = 'business';

    // Initialize Lucide icons
    lucide.createIcons();

    // Load model from URL parameter or generate new one
    let urlParams = new URLSearchParams(window.location.search);
    let modelId = urlParams.get('model_id');

    if (modelId) {
        loadExistingModel(modelId);
    } else {
        // Generate model from architecture assistant data
        generateModelFromAssistant();
    }

    // Layer navigation
    document.querySelectorAll('.layer-nav-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.layer-nav-btn').forEach(function(b) { b.classList.remove('active', 'bg-primary/10', 'text-primary/90', 'border-primary/20'); });
            document.querySelectorAll('.layer-nav-btn').forEach(function(b) { b.classList.add('bg-muted', 'text-foreground', 'border-border'); });

            this.classList.add('active', 'bg-primary/10', 'text-primary/90', 'border-primary/20');
            this.classList.remove('bg-muted', 'text-foreground', 'border-border');

            currentLayer = this.dataset.layer;
            renderElements();
        });
    });

    // Show all elements
    document.getElementById('btn-show-all').addEventListener('click', function() {
        renderElements();
    });

    // Show connected elements only
    document.getElementById('btn-show-connected').addEventListener('click', function() {
        renderElements(true);
    });

    // Export XML
    document.getElementById('btn-export-xml').addEventListener('click', function() {
        if (currentModel) {
            exportModelAsXML();
        }
    });

    // Open in Composer
    document.getElementById('btn-open-composer').addEventListener('click', function() {
        if (currentModel) {
            openInComposer();
        }
    });

    // Close modal
    document.getElementById('btn-close-modal').addEventListener('click', function() {
        Platform.modal.close('element-modal');
    });

    async function generateModelFromAssistant() {
        try {
            // Get data from architecture assistant (this would be passed from the assistant)
            let assistantData = JSON.parse(localStorage.getItem('architecture_assistant_data') || '{}');

            if (!assistantData.capability_id || !assistantData.solution_options) {
                showError('No architecture assistant data found. Please run the assistant first.');
                return;
            }

            let response = await fetch('/api/architecture-assistant/generate-archimate-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    capability_id: assistantData.capability_id,
                    solution_options: assistantData.solution_options,
                    gap_analysis: assistantData.gap_analysis || {}
                })
            });

            let result = await response.json();

            if (result.success) {
                currentModel = result.model;
                renderModel();
            } else {
                showError(result.error || 'Failed to generate model');
            }
        } catch (error) {
            console.error('Error generating model:', error);
            showError('Failed to generate ArchiMate model');
        }
    }

    async function loadExistingModel(modelId) {
        // Placeholder for loading existing models
        showError('Loading existing models not yet implemented');
    }

    function renderModel() {
        if (!currentModel) return;

        // Update header
        document.getElementById('model-title').textContent = currentModel.name || 'ArchiMate Model';
        document.getElementById('model-description').textContent = currentModel.description || 'Generated architecture model';

        // Update statistics
        document.getElementById('elements-count').textContent = currentModel.elements ? currentModel.elements.length : 0;
        document.getElementById('relationships-count').textContent = currentModel.relationships ? currentModel.relationships.length : 0;
        document.getElementById('viewpoints-count').textContent = currentModel.viewpoints ? currentModel.viewpoints.length : 0;

        // Render elements
        renderElements();

        // Render viewpoints
        renderViewpoints();

        // Render relationships
        renderRelationships();
    }

    function renderElements(showConnectedOnly) {
        let container = document.getElementById('elements-container');
        if (!currentModel || !currentModel.elements) {
            safeHTML(container, '<p class="text-muted-foreground">No elements found</p>');
            return;
        }

        let elements = currentModel.elements.filter(function(el) { return el.layer === currentLayer; });

        if (showConnectedOnly) {
            let connectedIds = {};
            if (currentModel.relationships) {
                currentModel.relationships.forEach(function(rel) {
                    connectedIds[rel.source] = true;
                    connectedIds[rel.target] = true;
                });
            }
            elements = elements.filter(function(el) { return connectedIds[el.id]; });
        }

        if (elements.length === 0) {
            safeHTML(container, '<p class="text-muted-foreground">No ' + currentLayer + ' layer elements found</p>');
            return;
        }

        safeHTML(container, elements.map(function(element) {
            return '<div class="model-element layer-' + element.layer + ' bg-card border border-border rounded-lg p-3" data-action="showElementDetails" data-id="' + element.id + '">' +
                '<div class="flex justify-between items-start">' +
                    '<div>' +
                        '<h4 class="font-medium text-sm">' + element.name + '</h4>' +
                        '<p class="text-xs text-muted-foreground mt-1">' + element.type + '</p>' +
                    '</div>' +
                    '<span class="text-xs bg-secondary text-secondary-foreground px-2 py-1 rounded">' + element.layer + '</span>' +
                '</div>' +
                (element.description ? '<p class="text-xs text-muted-foreground mt-2">' + element.description + '</p>' : '') +
            '</div>';
        }).join(''));
    }

    function renderViewpoints() {
        let container = document.getElementById('viewpoints-container');
        if (!currentModel || !currentModel.viewpoints || currentModel.viewpoints.length === 0) {
            safeHTML(container, '<p class="text-muted-foreground">No viewpoints generated</p>');
            return;
        }

        safeHTML(container, currentModel.viewpoints.map(function(viewpoint) {
            return '<div class="viewpoint-card rounded-lg p-3">' +
                '<h4 class="font-medium text-sm mb-2">' + viewpoint.name + '</h4>' +
                '<p class="text-xs text-muted-foreground mb-2">' + viewpoint.description + '</p>' +
                '<div class="flex justify-between text-xs">' +
                    '<span>' + (viewpoint.elements ? viewpoint.elements.length : 0) + ' elements</span>' +
                    '<span>' + (viewpoint.relationships ? viewpoint.relationships.length : 0) + ' relationships</span>' +
                '</div>' +
            '</div>';
        }).join(''));
    }

    function renderRelationships() {
        let container = document.getElementById('relationships-container');
        if (!currentModel || !currentModel.relationships || currentModel.relationships.length === 0) {
            safeHTML(container, '<p class="text-muted-foreground">No relationships found</p>');
            return;
        }

        safeHTML(container, currentModel.relationships.slice(0, 10).map(function(rel) {
            return '<div class="text-xs border border-border rounded p-2">' +
                '<div class="font-medium">' + rel.type + '</div>' +
                '<div class="text-muted-foreground">' + getElementName(rel.source) + ' \u2192 ' + getElementName(rel.target) + '</div>' +
            '</div>';
        }).join(''));

        if (currentModel.relationships.length > 10) {
            let moreEl = document.createElement('p');
            moreEl.className = 'text-xs text-muted-foreground mt-2';
            moreEl.textContent = '... and ' + (currentModel.relationships.length - 10) + ' more';
            container.appendChild(moreEl);
        }
    }

    function getElementName(elementId) {
        if (!currentModel || !currentModel.elements) return elementId;
        let element = currentModel.elements.find(function(el) { return el.id === elementId; });
        return element ? element.name : elementId;
    }

    function showElementDetails(elementId) {
        if (!currentModel || !currentModel.elements) return;
        let element = currentModel.elements.find(function(el) { return el.id === elementId; });
        if (!element) return;

        document.getElementById('modal-element-name').textContent = element.name;

        let detailsContainer = document.getElementById('modal-element-details');
        let html = '<div class="space-y-2">' +
                '<div><strong>Type:</strong> ' + element.type + '</div>' +
                '<div><strong>Layer:</strong> ' + element.layer + '</div>' +
                (element.description ? '<div><strong>Description:</strong> ' + element.description + '</div>' : '');

        if (element.properties) {
            Object.entries(element.properties).forEach(function(entry) {
                html += '<div><strong>' + entry[0] + ':</strong> ' + entry[1] + '</div>';
            });
        }

        html += '</div>';
        safeHTML(detailsContainer, html);

        Platform.modal.open('element-modal');
    }

    async function exportModelAsXML() {
        try {
            let response = await fetch('/api/architecture-assistant/export-archimate-model/' + currentModel.id);
            if (response.ok) {
                let xml = await response.text();
                let blob = new Blob([xml], { type: 'application/xml' });
                let url = URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = (currentModel.name || 'archimate-model') + '.xml';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } else {
                showError('Failed to export model');
            }
        } catch (error) {
            console.error('Error exporting model:', error);
            showError('Failed to export model');
        }
    }

    function openInComposer() {
        // Placeholder for opening in Solution Composer
        showError('Opening in Solution Composer not yet implemented');
    }

    function showError(message) {
        // Simple error display - in production, use a proper toast system
        Platform.toast.error(message);
    }

    // Make showElementDetails globally available
    window.showElementDetails = showElementDetails;
});
