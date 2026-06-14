/**
 * Extension Dashboard - External JavaScript
 * Extracted from app/templates/framework_management/extension_dashboard.html
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

// Extension Dashboard JavaScript
let extensionName = APP_CONFIG.extensionName || '';

document.addEventListener('DOMContentLoaded', function() {
    loadExtensionData();
    loadActivityLog();
});

function loadExtensionData() {
    // Simulate loading extension data
    let extensionData = getExtensionData(extensionName);

    document.getElementById('extensionType').textContent = extensionData.type;
    document.getElementById('extensionVersion').textContent = extensionData.version;
    document.getElementById('extensionProvider').textContent = extensionData.provider;
    document.getElementById('downloadCount').textContent = extensionData.downloadCount;
    document.getElementById('activeInstallations').textContent = extensionData.activeInstallations;
    document.getElementById('ratingValue').textContent = extensionData.rating;
    document.getElementById('targetFramework').textContent = extensionData.targetFramework;
    document.getElementById('minVersion').textContent = extensionData.minVersion;
    document.getElementById('dependencies').textContent = extensionData.dependencies;
    document.getElementById('extensionSize').textContent = extensionData.size;
    document.getElementById('lastUpdated').textContent = extensionData.lastUpdated;

    // Render rating stars
    renderRatingStars(extensionData.rating);

    // Render features
    renderFeatures(extensionData.features);
}

function getExtensionData(name) {
    let extensions = {
        'manufacturing-basic': {
            type: 'Industry',
            version: '2.1.0',
            provider: 'System',
            downloadCount: 1250,
            activeInstallations: 89,
            rating: 4.2,
            targetFramework: 'Unified_Manufacturing_Excellence',
            minVersion: '1.5.0',
            dependencies: 'Core Framework v1.5+',
            size: '15.2 MB',
            lastUpdated: '2024-01-10',
            features: [
                { name: 'Basic Process Templates', description: 'Pre-built manufacturing process templates', icon: 'fa-file-alt' },
                { name: 'Quality Control', description: 'Basic quality management tools', icon: 'fa-check-circle' },
                { name: 'Inventory Tracking', description: 'Simple inventory management', icon: 'fa-boxes' },
                { name: 'Production Scheduling', description: 'Basic production planning', icon: 'fa-calendar-alt' },
                { name: 'Reporting Dashboard', description: 'Essential manufacturing reports', icon: 'fa-chart-bar' },
                { name: 'User Management', description: 'Basic user role management', icon: 'fa-users' }
            ]
        },
        'manufacturing-advanced': {
            type: 'Industry',
            version: '3.4.1',
            provider: 'System',
            downloadCount: 856,
            activeInstallations: 42,
            rating: 4.7,
            targetFramework: 'Unified_Manufacturing_Excellence',
            minVersion: '2.0.0',
            dependencies: 'Core Framework v2.0+, Manufacturing Basic',
            size: '28.7 MB',
            lastUpdated: '2024-01-08',
            features: [
                { name: 'Advanced Analytics', description: 'Predictive analytics and insights', icon: 'fa-chart-line' },
                { name: 'AI Integration', description: 'Machine learning capabilities', icon: 'fa-brain' },
                { name: 'IoT Connectivity', description: 'Industrial IoT integration', icon: 'fa-network-wired' },
                { name: 'Digital Twin', description: 'Virtual factory modeling', icon: 'fa-cube' },
                { name: 'Automated Quality', description: 'AI-powered quality control', icon: 'fa-robot' },
                { name: 'Supply Chain Optimization', description: 'Advanced supply chain management', icon: 'fa-truck' }
            ]
        },
        'digital-transformation': {
            type: 'Technology',
            version: '1.8.2',
            provider: 'System',
            downloadCount: 623,
            activeInstallations: 31,
            rating: 4.5,
            targetFramework: 'Unified_Manufacturing_Excellence',
            minVersion: '1.8.0',
            dependencies: 'Core Framework v1.8+',
            size: '22.1 MB',
            lastUpdated: '2024-01-12',
            features: [
                { name: 'Cloud Integration', description: 'Cloud services connectivity', icon: 'fa-cloud' },
                { name: 'Mobile Access', description: 'Mobile device support', icon: 'fa-mobile-alt' },
                { name: 'API Gateway', description: 'RESTful API management', icon: 'fa-plug' },
                { name: 'Data Analytics', description: 'Big data processing', icon: 'fa-database' },
                { name: 'Security Suite', description: 'Advanced security features', icon: 'fa-shield-alt' },
                { name: 'Collaboration Tools', description: 'Team collaboration platform', icon: 'fa-comments' }
            ]
        }
    };

    return extensions[name.replace('-', '-')] || extensions['manufacturing-basic'];
}

function renderRatingStars(rating) {
    let ratingContainer = document.getElementById('userRating');
    let fullStars = Math.floor(rating);
    let hasHalfStar = rating % 1 !== 0;

    let starsHTML = '';
    for (let i = 0; i < fullStars; i++) {
        starsHTML += '<i class="fas fa-star"></i>';
    }
    if (hasHalfStar) {
        starsHTML += '<i class="fas fa-star-half-alt"></i>';
    }
    let emptyStars = 5 - Math.ceil(rating);
    for (let j = 0; j < emptyStars; j++) {
        starsHTML += '<i class="far fa-star"></i>';
    }

    safeHTML(ratingContainer, starsHTML);
}

function renderFeatures(features) {
    let featuresContainer = document.getElementById('extensionFeatures');
    safeHTML(featuresContainer, '');

    features.forEach(function(feature) {
        let featureDiv = document.createElement('div');
        featureDiv.className = 'bg-muted rounded-lg p-4';
        safeHTML(featureDiv,
            '<div class="flex items-center space-x-3">' +
                '<div class="bg-primary/10 p-2 rounded-full">' +
                    '<i class="fas ' + feature.icon + ' text-primary"></i>' +
                '</div>' +
                '<div>' +
                    '<h4 class="font-medium text-foreground">' + feature.name + '</h4>' +
                    '<p class="text-sm text-muted-foreground">' + feature.description + '</p>' +
                '</div>' +
            '</div>');
        featuresContainer.appendChild(featureDiv);
    });
}

function loadActivityLog() {
    let activities = [
        { action: 'Extension downloaded', timestamp: '2024-01-13 10:30', user: 'System' },
        { action: 'Configuration updated', timestamp: '2024-01-12 15:45', user: 'Admin' },
        { action: 'Extension activated', timestamp: '2024-01-11 09:20', user: 'System' },
        { action: 'Version checked', timestamp: '2024-01-10 14:15', user: 'System' }
    ];

    let logContainer = document.getElementById('activityLog');
    safeHTML(logContainer, '');

    activities.forEach(function(activity) {
        let activityDiv = document.createElement('div');
        activityDiv.className = 'flex items-center justify-between p-3 bg-muted rounded-md';
        safeHTML(activityDiv,
            '<div class="flex items-center space-x-3">' +
                '<div class="bg-primary/10 p-2 rounded-full">' +
                    '<i class="fas fa-info text-primary text-sm"></i>' +
                '</div>' +
                '<div>' +
                    '<p class="font-medium text-foreground">' + activity.action + '</p>' +
                    '<p class="text-sm text-muted-foreground">' + activity.user + '</p>' +
                '</div>' +
            '</div>' +
            '<span class="text-sm text-muted-foreground">' + activity.timestamp + '</span>');
        logContainer.appendChild(activityDiv);
    });
}

function activateExtension() {
    // API call to activate extension
    let statusEl = document.getElementById('extensionStatus');
    let previousStatus = statusEl ? statusEl.textContent : '';
    if (statusEl) {
        statusEl.textContent = 'Activating...';
        statusEl.className = 'px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-800';
    }

    fetch('/framework-management/api/activate-extension', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            extension_name: extensionName
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.success) {
            document.getElementById('extensionStatus').textContent = 'Active';
            document.getElementById('extensionStatus').className = 'px-2 py-1 text-xs rounded-full bg-emerald-500/10 text-green-800';
            loadActivityLog();
            if (typeof window.showToast === 'function') {
                window.showToast('Extension activated successfully.', 'success');
            }
        } else {
            if (statusEl) {
                statusEl.textContent = previousStatus || 'Inactive';
                statusEl.className = 'px-2 py-1 text-xs rounded-full bg-destructive/10 text-red-800';
            }
            showExtensionError('Failed to activate extension: ' + (data.message || 'unknown error'));
        }
    })
    .catch(function(error) {
        console.error('Error activating extension:', error);
        if (statusEl) {
            statusEl.textContent = previousStatus || 'Inactive';
            statusEl.className = 'px-2 py-1 text-xs rounded-full bg-destructive/10 text-red-800';
        }
        showExtensionError('Error activating extension. Please retry.');
    });
}

function showExtensionError(message) {
    if (typeof window.showToast === 'function') {
        window.showToast(message, 'error');
    } else {
        Platform.toast.error(message);
    }
}

function configureExtension() {
    // Open configuration modal or navigate to config page
}

function saveConfiguration() {
    // Save configuration settings
}

function resetConfiguration() {
    if (confirm('Are you sure you want to reset to default configuration?')) {
        // Reset configuration to defaults
    }
}
