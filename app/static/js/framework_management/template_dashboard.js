let APP_CONFIG = window.__APP_CONFIG__ || {};

// Template Dashboard JavaScript
let templateName = APP_CONFIG.templateName || '';
let templateNameTitle = APP_CONFIG.templateNameTitle || '';

document.addEventListener('DOMContentLoaded', function() {
    loadTemplateData();
    loadRecentDeployments();
});

function loadTemplateData() {
    // Simulate loading template data
    let templateData = getTemplateData(templateName);

    document.getElementById('templateCategory').textContent = templateData.category;
    document.getElementById('templateType').textContent = templateData.type;
    document.getElementById('orgSize').textContent = templateData.organizationSize;
    document.getElementById('complexity').textContent = templateData.complexity;
    document.getElementById('usageCount').textContent = templateData.usageCount;
    document.getElementById('successRate').textContent = templateData.successRate + '%';
    document.getElementById('qualityValue').textContent = templateData.qualityScore;
    document.getElementById('avgImplementation').textContent = templateData.avgImplementation;
    document.getElementById('provider').textContent = templateData.provider;
    document.getElementById('lastUpdated').textContent = templateData.lastUpdated;
    document.getElementById('templateDescription').textContent = templateData.description;

    // Render quality score stars
    renderQualityStars(templateData.qualityScore);

    // Render target industries
    renderTargetIndustries(templateData.targetIndustries);

    // Render capabilities and extensions
    renderCapabilities(templateData.capabilities);
    renderExtensions(templateData.extensions);

    // Render implementation steps
    renderImplementationSteps(templateData.implementationSteps);
}

function getTemplateData(name) {
    let templates = {
        'small-enterprise': {
            category: 'Manufacturing',
            type: 'Business Framework',
            organizationSize: 'Small (1-50 employees)',
            complexity: 'Beginner',
            usageCount: 234,
            successRate: 94.2,
            qualityScore: 4.3,
            avgImplementation: '2-3 weeks',
            provider: 'System',
            lastUpdated: '2024-01-05',
            targetIndustries: ['Manufacturing', 'Retail', 'Services'],
            description: 'A streamlined framework template designed specifically for small enterprises. Provides essential manufacturing capabilities with simplified implementation and minimal overhead.',
            capabilities: [
                'Basic Production Planning',
                'Quality Control Essentials',
                'Inventory Management',
                'Order Processing',
                'Basic Reporting'
            ],
            extensions: [
                'Manufacturing Basic Extension',
                'Quality Management Tools'
            ],
            implementationSteps: [
                'Initial assessment and planning',
                'Core capability setup',
                'Basic process configuration',
                'User training and onboarding',
                'Go-live and support'
            ]
        },
        'large-enterprise': {
            category: 'Manufacturing',
            type: 'Enterprise Framework',
            organizationSize: 'Large (500+ employees)',
            complexity: 'Advanced',
            usageCount: 156,
            successRate: 91.8,
            qualityScore: 4.6,
            avgImplementation: '8-12 weeks',
            provider: 'System',
            lastUpdated: '2024-01-08',
            targetIndustries: ['Manufacturing', 'Automotive', 'Aerospace', 'Pharmaceuticals'],
            description: 'Comprehensive enterprise-grade framework template for large manufacturing organizations. Includes advanced capabilities, multi-site support, and enterprise integrations.',
            capabilities: [
                'Advanced Production Planning',
                'Enterprise Quality Management',
                'Multi-site Inventory Management',
                'Supply Chain Integration',
                'Advanced Analytics',
                'Compliance Management',
                'Digital Twin Support',
                'IoT Integration'
            ],
            extensions: [
                'Manufacturing Advanced Extension',
                'Digital Transformation Extension',
                'AI Analytics Extension'
            ],
            implementationSteps: [
                'Enterprise assessment and roadmap',
                'Infrastructure preparation',
                'Core framework deployment',
                'Advanced capability configuration',
                'Integration setup',
                'Multi-site rollout',
                'Enterprise training',
                'Go-live and optimization'
            ]
        },
        'generic-business': {
            category: 'General',
            type: 'Business Framework',
            organizationSize: 'Any size',
            complexity: 'Intermediate',
            usageCount: 412,
            successRate: 89.5,
            qualityScore: 4.1,
            avgImplementation: '4-6 weeks',
            provider: 'System',
            lastUpdated: '2024-01-10',
            targetIndustries: ['All Industries'],
            description: 'A versatile business framework template suitable for organizations across various industries. Provides a solid foundation for business capability management with flexible customization options.',
            capabilities: [
                'Business Process Management',
                'Quality Management',
                'Resource Management',
                'Performance Monitoring',
                'Risk Management',
                'Continuous Improvement'
            ],
            extensions: [
                'Digital Transformation Extension',
                'Analytics Extension'
            ],
            implementationSteps: [
                'Business analysis and requirements gathering',
                'Framework customization',
                'Process configuration',
                'User training',
                'Pilot implementation',
                'Full deployment',
                'Continuous optimization'
            ]
        }
    };

    return templates[name.replace('-', '-')] || templates['generic-business'];
}

function renderQualityStars(score) {
    let scoreContainer = document.getElementById('qualityScore');
    let fullStars = Math.floor(score);
    let hasHalfStar = score % 1 !== 0;

    let starsHTML = '';
    for (let i = 0; i < fullStars; i++) {
        starsHTML += '<i class="fas fa-star"></i>';
    }
    if (hasHalfStar) {
        starsHTML += '<i class="fas fa-star-half-alt"></i>';
    }
    let emptyStars = 5 - Math.ceil(score);
    for (let i = 0; i < emptyStars; i++) {
        starsHTML += '<i class="far fa-star"></i>';
    }

    safeHTML(scoreContainer, starsHTML);
}

function renderTargetIndustries(industries) {
    let container = document.getElementById('targetIndustries');
    safeHTML(container, '');

    industries.forEach(function(industry) {
        let badge = document.createElement('span');
        badge.className = 'px-2 py-1 text-xs rounded-full bg-primary/10 text-primary/90 mr-2 mb-2';
        badge.textContent = industry;
        container.appendChild(badge);
    });
}

function renderCapabilities(capabilities) {
    let container = document.getElementById('includedCapabilities');
    safeHTML(container, '');

    capabilities.forEach(function(capability) {
        let div = document.createElement('div');
        div.className = 'flex items-center space-x-2 p-2 bg-muted rounded';
        let icon = document.createElement('i');
        icon.className = 'fas fa-check-circle text-emerald-500';
        let span = document.createElement('span');
        span.className = 'text-foreground';
        span.textContent = capability;
        div.appendChild(icon);
        div.appendChild(span);
        container.appendChild(div);
    });
}

function renderExtensions(extensions) {
    let container = document.getElementById('preconfiguredExtensions');
    safeHTML(container, '');

    extensions.forEach(function(extension) {
        let div = document.createElement('div');
        div.className = 'flex items-center space-x-2 p-2 bg-muted rounded';
        let icon = document.createElement('i');
        icon.className = 'fas fa-puzzle text-primary';
        let span = document.createElement('span');
        span.className = 'text-foreground';
        span.textContent = extension;
        div.appendChild(icon);
        div.appendChild(span);
        container.appendChild(div);
    });
}

function renderImplementationSteps(steps) {
    let container = document.getElementById('implementationSteps');
    safeHTML(container, '');

    steps.forEach(function(step, index) {
        let stepDiv = document.createElement('div');
        stepDiv.className = 'flex items-start space-x-3';
        let numDiv = document.createElement('div');
        numDiv.className = 'bg-primary text-primary-foreground w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0';
        numDiv.textContent = String(index + 1);
        let textDiv = document.createElement('div');
        textDiv.className = 'flex-1';
        let p = document.createElement('p');
        p.className = 'text-foreground';
        p.textContent = step;
        textDiv.appendChild(p);
        stepDiv.appendChild(numDiv);
        stepDiv.appendChild(textDiv);
        container.appendChild(stepDiv);
    });
}

function loadRecentDeployments() {
    let deployments = [
        { organization: 'Acme Manufacturing', date: '2024-01-12', status: 'Completed', progress: 100 },
        { organization: 'Global Industries', date: '2024-01-10', status: 'In Progress', progress: 65 },
        { organization: 'Tech Solutions Inc', date: '2024-01-08', status: 'Completed', progress: 100 },
        { organization: 'Precision Engineering', date: '2024-01-05', status: 'Planning', progress: 15 }
    ];

    let container = document.getElementById('recentDeployments');
    safeHTML(container, '');

    deployments.forEach(function(deployment) {
        let deploymentDiv = document.createElement('div');
        deploymentDiv.className = 'flex items-center justify-between p-3 bg-muted rounded-md';

        // Left: icon + org + date
        let leftDiv = document.createElement('div');
        leftDiv.className = 'flex items-center space-x-3';
        let iconWrap = document.createElement('div');
        iconWrap.className = 'bg-primary/10 p-2 rounded-full';
        let icon = document.createElement('i');
        icon.className = 'fas fa-building text-primary text-sm';
        iconWrap.appendChild(icon);
        let infoDiv = document.createElement('div');
        let orgP = document.createElement('p');
        orgP.className = 'font-medium text-foreground';
        orgP.textContent = deployment.organization;
        let dateP = document.createElement('p');
        dateP.className = 'text-sm text-muted-foreground';
        dateP.textContent = deployment.date;
        infoDiv.appendChild(orgP);
        infoDiv.appendChild(dateP);
        leftDiv.appendChild(iconWrap);
        leftDiv.appendChild(infoDiv);

        // Right: progress bar + status badge
        let rightDiv = document.createElement('div');
        rightDiv.className = 'flex items-center space-x-3';
        let barWrap = document.createElement('div');
        barWrap.className = 'flex-1 w-24';
        let barBg = document.createElement('div');
        barBg.className = 'bg-background rounded-full h-2';
        let barFill = document.createElement('div');
        barFill.className = 'bg-primary h-2 rounded-full';
        barFill.style.width = Math.min(100, Math.max(0, Number(deployment.progress) || 0)) + '%';
        barBg.appendChild(barFill);
        barWrap.appendChild(barBg);
        let statusSpan = document.createElement('span');
        statusSpan.className = 'px-2 py-1 text-xs rounded-full ' + getStatusColor(deployment.status);
        statusSpan.textContent = deployment.status;
        rightDiv.appendChild(barWrap);
        rightDiv.appendChild(statusSpan);

        deploymentDiv.appendChild(leftDiv);
        deploymentDiv.appendChild(rightDiv);
        container.appendChild(deploymentDiv);
    });
}

function getStatusColor(status) {
    let colors = {
        'Completed': 'bg-emerald-500/10 text-green-800',
        'In Progress': 'bg-amber-500/10 text-yellow-800',
        'Planning': 'bg-primary/10 text-primary/90',
        'Delayed': 'bg-destructive/10 text-red-800'
    };
    return colors[status] || 'bg-muted text-foreground';
}

function customizeTemplate() {
    // Navigate to customization page or open modal
}
