let APP_CONFIG = window.__APP_CONFIG__ || {};

let currentData = {
    configurations: [],
    extensions: [],
    templates: [],
    instances: []
};

function loadData() {
    Promise.all([
        fetch('/framework-management/api/available-frameworks').then(function(r) { return r.json(); }),
        fetch('/framework-management/api/statistics').then(function(r) { return r.json(); }),
        fetch('/framework-management/api/active-framework').then(function(r) { return r.json().catch(function() { return null; }); })
    ]).then(function(results) {
        let frameworks = results[0];
        let stats = results[1];
        let activeFramework = results[2];
        currentData = frameworks;
        updateStatistics(stats);
        updateActiveFramework(activeFramework);
        renderConfigurations();
        renderExtensions();
        renderTemplates();
        renderInstances();
    }).catch(function(error) {
        console.error('Error loading data:', error);
        notifyFrameworkError('Failed to load framework data. Please retry.');
    });
}

function notifyFrameworkError(message) {
    let activeContainer = document.getElementById('active-framework-content');
    safeHTML(activeContainer,
        '<div class="rounded-md border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">' +
            '<p class="font-semibold">Unable to load framework dashboard data.</p>' +
            '<p class="mt-1">' + message + '</p>' +
            '<button onclick="loadData()" class="mt-3 rounded bg-destructive px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-red-700">Retry</button>' +
        '</div>');
    if (typeof window.showToast === 'function') {
        window.showToast(message, 'error');
    } else {
        Platform.toast.info(message);
    }
}

function updateStatistics(stats) {
    document.getElementById('total-configurations').textContent = stats.total_configurations;
    document.getElementById('active-configurations').textContent = stats.active_configurations;
    document.getElementById('total-extensions').textContent = stats.total_extensions;
    document.getElementById('active-instances').textContent = stats.active_instances;
}

function updateActiveFramework(activeFramework) {
    let container = document.getElementById('active-framework-content');
    if (activeFramework && activeFramework.configuration) {
        safeHTML(container, '<div class="flex justify-between items-start">' +
                '<div>' +
                    '<h4 class="font-semibold text-lg">' + activeFramework.configuration.configuration_name + '</h4>' +
                    '<p class="text-sm text-muted-foreground mt-1">' + activeFramework.configuration.configuration_description + '</p>' +
                    '<div class="flex gap-2 mt-2">' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-emerald-500 text-primary-foreground">Active</span>' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-primary text-primary-foreground">' + activeFramework.configuration.base_framework + '</span>' +
                    '</div>' +
                '</div>' +
                (activeFramework.instance ? '<div class="text-right">' +
                    '<p class="text-sm font-medium">' + activeFramework.instance.name + '</p>' +
                    '<p class="text-xs text-muted-foreground">' + activeFramework.instance.implementation_percentage + '% implemented</p>' +
                    '<div class="w-24 h-2 bg-muted rounded-full mt-1">' +
                        '<div class="h-2 bg-emerald-500 rounded-full" style="width: ' + activeFramework.instance.implementation_percentage + '%"></div>' +
                    '</div>' +
                '</div>' : '') +
            '</div>');
    } else {
        safeHTML(container, '<p class="text-muted-foreground">No active framework deployed</p>');
    }
}

function renderConfigurations() {
    let container = document.getElementById('configurations-container');
    let filter = document.getElementById('config-filter').value;

    let filtered = currentData.configurations.filter(function(config) {
        if (filter === 'all') return true;
        return config.status === filter;
    });

    if (filtered.length === 0) {
        safeHTML(container, '<p class="text-muted-foreground">No configurations found</p>');
        return;
    }

    safeHTML(container, filtered.map(function(config) {
        return '<div class="p-4 rounded-md border hover:bg-accent transition-colors">' +
            '<div class="flex justify-between items-start">' +
                '<div class="flex-1">' +
                    '<h5 class="font-semibold">' + config.configuration_name + '</h5>' +
                    '<p class="text-sm text-muted-foreground mt-1">' + config.configuration_description + '</p>' +
                    '<div class="flex gap-2 mt-2">' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ' + getStatusColor(config.status) + '">' + config.status + '</span>' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-muted text-foreground">' + config.base_framework + '</span>' +
                    '</div>' +
                '</div>' +
                (config.status === 'draft' ?
                '<button data-action="deployConfiguration" data-id="' + config.id + '" class="ml-4 px-3 py-1 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90">' +
                    'Deploy' +
                '</button>' : '') +
            '</div>' +
        '</div>';
    }).join(''));
}

function renderExtensions() {
    let container = document.getElementById('extensions-container');
    let filter = document.getElementById('extension-filter').value;

    let filtered = currentData.extensions.filter(function(ext) {
        if (filter === 'all') return true;
        return ext.type === filter;
    });

    if (filtered.length === 0) {
        safeHTML(container, '<p class="text-muted-foreground">No extensions found</p>');
        return;
    }

    safeHTML(container, filtered.map(function(ext) {
        return '<div class="p-4 rounded-md border hover:bg-accent transition-colors">' +
            '<div class="flex justify-between items-start">' +
                '<div class="flex-1">' +
                    '<h5 class="font-semibold">' + ext.name + '</h5>' +
                    '<p class="text-sm text-muted-foreground mt-1">' + ext.description + '</p>' +
                    '<div class="flex gap-2 mt-2">' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-primary text-primary-foreground">' + ext.type + '</span>' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-muted text-foreground">' + ext.category + '</span>' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-muted text-foreground">v' + ext.version + '</span>' +
                    '</div>' +
                '</div>' +
                '<button data-action="activateExtension" data-id="' + ext.id + '" class="ml-4 px-3 py-1 text-xs bg-emerald-500 text-primary-foreground rounded-md hover:bg-emerald-600">' +
                    'Activate' +
                '</button>' +
            '</div>' +
        '</div>';
    }).join(''));
}

function renderTemplates() {
    let container = document.getElementById('templates-container');

    if (currentData.templates.length === 0) {
        safeHTML(container, '<p class="text-muted-foreground">No templates available</p>');
        return;
    }

    safeHTML(container, currentData.templates.map(function(template) {
        return '<div class="p-4 rounded-md border hover:bg-accent transition-colors cursor-pointer" data-action="applyTemplate" data-id="' + template.id + '">' +
            '<h5 class="font-semibold">' + template.name + '</h5>' +
            '<p class="text-sm text-muted-foreground mt-1">' + template.description + '</p>' +
            '<div class="flex justify-between items-center mt-2">' +
                '<div class="flex gap-2">' +
                    '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-primary text-primary-foreground">' + template.type + '</span>' +
                    '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-muted text-foreground">' + template.organization_size + '</span>' +
                '</div>' +
                '<span class="text-xs text-muted-foreground">' + template.usage_count + ' uses</span>' +
            '</div>' +
        '</div>';
    }).join(''));
}

function renderInstances() {
    let container = document.getElementById('instances-container');

    if (currentData.instances.length === 0) {
        safeHTML(container, '<p class="text-muted-foreground">No deployed instances</p>');
        return;
    }

    safeHTML(container, currentData.instances.map(function(instance) {
        return '<div class="p-4 rounded-md border hover:bg-accent transition-colors">' +
            '<div class="flex justify-between items-start">' +
                '<div class="flex-1">' +
                    '<h5 class="font-semibold">' + instance.name + '</h5>' +
                    '<p class="text-sm text-muted-foreground mt-1">' + instance.description + '</p>' +
                    '<div class="flex gap-2 mt-2">' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ' + getStatusColor(instance.status) + '">' + instance.status + '</span>' +
                        '<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium bg-muted text-foreground">' + instance.organization_unit + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="text-right">' +
                    '<p class="text-sm font-medium">' + instance.implementation_percentage + '%</p>' +
                    '<div class="w-16 h-2 bg-muted rounded-full mt-1">' +
                        '<div class="h-2 bg-primary rounded-full" style="width: ' + instance.implementation_percentage + '%"></div>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</div>';
    }).join(''));
}

function getStatusColor(status) {
    let colors = {
        'active': 'bg-emerald-500 text-primary-foreground',
        'draft': 'bg-muted/50 text-primary-foreground',
        'deprecated': 'bg-destructive text-primary-foreground',
        'implementing': 'bg-primary text-primary-foreground',
        'operational': 'bg-emerald-500 text-primary-foreground',
        'optimizing': 'bg-primary text-primary-foreground',
        'archived': 'bg-muted/70 text-primary-foreground'
    };
    return colors[status] || 'bg-muted/50 text-primary-foreground';
}

function deployConfiguration(configId) {
    currentDeployConfigId = configId;
    Platform.modal.open('deployModal');
}

function closeDeployModal() {
    Platform.modal.close('deployModal');
    document.getElementById('deployForm').reset();
}

function activateExtension(extensionId) {
    fetch('/framework-management/api/activate-extension/' + extensionId, {
        method: 'POST'
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            Platform.toast.info(data.message);
            loadData();
        } else {
            Platform.toast.error('Failed to activate extension: ' + data.message);
        }
    })
    .catch(function(error) {
        console.error('Error activating extension:', error);
        Platform.toast.error('Error activating extension');
    });
}

function applyTemplate(templateId) {
    let name = prompt('Enter configuration name:');
    if (!name) return;

    fetch('/framework-management/api/apply-template', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            template_id: templateId,
            configuration_name: name
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            Platform.toast.info(data.message);
            loadData();
        } else {
            Platform.toast.error('Failed to apply template: ' + data.message);
        }
    })
    .catch(function(error) {
        console.error('Error applying template:', error);
        Platform.toast.error('Error applying template');
    });
}

// Handle deploy form submission
document.getElementById('deployForm').addEventListener('submit', function(e) {
    e.preventDefault();

    let data = {
        configuration_id: currentDeployConfigId,
        instance_name: document.getElementById('instance-name').value,
        description: document.getElementById('instance-description').value,
        organization_unit: document.getElementById('organization-unit').value,
        implementation_scope: document.getElementById('implementation-scope').value
    };

    fetch('/framework-management/api/deploy-configuration', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(function(response) { return response.json(); })
    .then(function(result) {
        if (result.success) {
            Platform.toast.info(result.message);
            closeDeployModal();
            loadData();
        } else {
            Platform.toast.error('Deployment failed: ' + result.message);
        }
    })
    .catch(function(error) {
        console.error('Error deploying configuration:', error);
        Platform.toast.error('Error deploying configuration');
    });
});

// Filter event listeners
document.getElementById('config-filter').addEventListener('change', renderConfigurations);
document.getElementById('extension-filter').addEventListener('change', renderExtensions);

// Initialize
let currentDeployConfigId = null;
document.addEventListener('DOMContentLoaded', function() {
    loadData();

    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});
