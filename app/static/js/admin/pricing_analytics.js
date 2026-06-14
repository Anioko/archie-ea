/**
 * pricing_analytics.js — Chart.js initialisation for the Pricing Analytics admin page.
 *
 * Colour palette matches rationalization_workbench.js conventions.
 */

const CONFIDENCE_COLORS = {
    api_synced:           { bg: 'rgba(59, 130, 246, 0.8)',  border: 'rgba(59, 130, 246, 1)' },
    contract_verified:    { bg: 'rgba(16, 185, 129, 0.8)', border: 'rgba(16, 185, 129, 1)' },
    architect_confirmed:  { bg: 'rgba(99, 102, 241, 0.8)', border: 'rgba(99, 102, 241, 1)' },
    seeded:               { bg: 'rgba(245, 158, 11, 0.8)', border: 'rgba(245, 158, 11, 1)' },
    llm_proposed:         { bg: 'rgba(156, 163, 175, 0.8)', border: 'rgba(156, 163, 175, 1)' },
};

const DEFAULT_COLOR = { bg: 'rgba(203, 213, 225, 0.8)', border: 'rgba(203, 213, 225, 1)' };

/**
 * Initialise the confidence distribution pie chart.
 *
 * @param {Object} dist  - {data_source_type: count, ...} from analytics.confidence_distribution
 */
function initConfidencePieChart(dist) {
    if (typeof Chart === 'undefined') { return; }

    const ctx = document.getElementById('confidencePieChart');
    if (!ctx) { return; }

    const labels = [];
    const counts = [];
    const backgrounds = [];
    const borders = [];

    Object.keys(dist).forEach(function(key) {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        labels.push(label);
        counts.push(dist[key]);
        const c = CONFIDENCE_COLORS[key] || DEFAULT_COLOR;
        backgrounds.push(c.bg);
        borders.push(c.border);
    });

    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: backgrounds,
                borderColor: borders,
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: { size: 11 },
                        padding: 12,
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce(function(a, b) { return a + b; }, 0);
                            const value = context.parsed;
                            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
                            return ' ' + context.label + ': ' + value + ' (' + pct + '%)';
                        },
                    },
                },
            },
        },
    });
}
