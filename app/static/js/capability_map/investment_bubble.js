/**
 * Investment Bubble — 2x2 TIME quadrant chart for enterprise/investment_matrix.html
 * (Business Architect visual 3).
 *
 * Data: window.__investmentBubbleData, embedded by investment_matrix.html from the
 * SAME `capabilities` context variable the existing table already renders (no new
 * endpoint/route). Fields per capability: name, strategic_importance, maturity_gap,
 * business_value (1-10, used as an investment-size proxy — this capability model has
 * no annual_cost field), roi_score.
 *
 * Axes:
 *   x = strategic_importance (low=1 .. critical=4)
 *   y = maturity_gap (target_maturity_level - current_maturity_level)
 *   r (bubble size) = business_value
 *
 * Quadrants follow the TIME model (Tolerate / Invest / Migrate / Eliminate), matching
 * the same quadrant naming + color convention already used by the Chart.js TIME
 * quadrant in applications/rationalization/dashboard.js.
 *
 * Uses Chart.js (type: 'bubble') — same CDN/version already used elsewhere in the app.
 * No new external charting library is introduced.
 */
(function () {
    'use strict';

    var IMPORTANCE_ORDER = { low: 1, medium: 2, high: 3, critical: 4 };
    var IMPORTANCE_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical' };
    var X_MID = 2.5;   // boundary between "medium" and "high" strategic importance
    var Y_MID = 1.5;   // boundary between a minor and a major maturity gap

    var QUADRANT_COLORS = {
        INVEST: 'rgba(16, 185, 129, 0.75)',   // emerald — high value, small gap
        MIGRATE: 'rgba(245, 158, 11, 0.75)',  // amber — high value, large gap
        TOLERATE: 'rgba(59, 130, 246, 0.75)', // primary blue — low value, small gap
        ELIMINATE: 'rgba(239, 68, 68, 0.75)'  // destructive red — low value, large gap
    };

    function cssHSL(varName, alpha) {
        var raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
        if (!raw) return null;
        return alpha !== undefined ? 'hsl(' + raw + ' / ' + alpha + ')' : 'hsl(' + raw + ')';
    }

    function classifyQuadrant(x, y) {
        if (x >= X_MID && y < Y_MID) return 'INVEST';
        if (x >= X_MID && y >= Y_MID) return 'MIGRATE';
        if (x < X_MID && y < Y_MID) return 'TOLERATE';
        return 'ELIMINATE';
    }

    function radiusFor(businessValue) {
        var v = businessValue || 5;
        return Math.max(6, Math.min(26, 6 + v * 2));
    }

    function initInvestmentBubbleChart() {
        var canvas = document.getElementById('investment-bubble-chart');
        var container = document.getElementById('investment-bubble-container');
        var emptyState = document.getElementById('investment-bubble-empty');
        if (!canvas || typeof Chart === 'undefined') return;

        var data = window.__investmentBubbleData || [];
        if (!data.length) {
            if (container) container.classList.add('hidden');
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        }

        var grouped = { INVEST: [], MIGRATE: [], TOLERATE: [], ELIMINATE: [] };

        data.forEach(function (cap) {
            var x = IMPORTANCE_ORDER[cap.strategic_importance] || 2;
            var y = Math.max(0, cap.maturity_gap || 0);
            var quadrant = classifyQuadrant(x, y);
            grouped[quadrant].push({
                x: x,
                y: y,
                r: radiusFor(cap.business_value),
                name: cap.name,
                strategic_importance: cap.strategic_importance,
                roi_score: cap.roi_score
            });
        });

        var datasets = Object.keys(grouped)
            .filter(function (q) { return grouped[q].length > 0; })
            .map(function (q) {
                return {
                    label: q.charAt(0) + q.slice(1).toLowerCase(),
                    data: grouped[q],
                    backgroundColor: QUADRANT_COLORS[q],
                    borderColor: 'transparent'
                };
            });

        new Chart(canvas, {
            type: 'bubble',
            data: { datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        min: 0.5,
                        max: 4.5,
                        title: { display: true, text: 'Strategic Importance' },
                        ticks: {
                            stepSize: 1,
                            callback: function (value) { return IMPORTANCE_LABELS[value] || ''; }
                        }
                    },
                    y: {
                        min: 0,
                        title: { display: true, text: 'Maturity Gap (Target − Current)' },
                        ticks: { stepSize: 1 }
                    }
                },
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var d = ctx.raw;
                                var roi = (d.roi_score !== null && d.roi_score !== undefined) ? ', ROI score ' + d.roi_score : '';
                                return d.name + ' — ' + (d.strategic_importance || 'medium') + ' importance, gap ' + d.y + roi;
                            }
                        }
                    }
                }
            },
            plugins: [{
                id: 'timeQuadrantLines',
                beforeDraw: function (chart) {
                    var c = chart.ctx;
                    var area = chart.chartArea;
                    var xScale = chart.scales.x;
                    var yScale = chart.scales.y;
                    var xMidPx = xScale.getPixelForValue(X_MID);
                    var yMidPx = yScale.getPixelForValue(Y_MID);
                    var gridColor = cssHSL('--border', 0.8) || 'rgba(128, 128, 128, 0.4)';
                    var labelColor = cssHSL('--muted-foreground') || 'rgba(128, 128, 128, 0.8)';

                    c.save();
                    c.setLineDash([5, 5]);
                    c.strokeStyle = gridColor;
                    c.lineWidth = 1;
                    c.beginPath(); c.moveTo(xMidPx, area.top); c.lineTo(xMidPx, area.bottom); c.stroke();
                    c.beginPath(); c.moveTo(area.left, yMidPx); c.lineTo(area.right, yMidPx); c.stroke();
                    c.restore();

                    // Chart.js plots larger y (bigger maturity gap) toward the TOP of the
                    // chart area, so the "high importance" (right) + "large gap" (top)
                    // quadrant is MIGRATE, and "high importance" + "small gap" (bottom) is
                    // INVEST — matching classifyQuadrant() above.
                    c.font = '11px system-ui';
                    c.fillStyle = labelColor;
                    c.fillText('ELIMINATE', area.left + 8, area.top + 14);
                    c.fillText('MIGRATE', area.right - 60, area.top + 14);
                    c.fillText('TOLERATE', area.left + 8, area.bottom - 8);
                    c.fillText('INVEST', area.right - 52, area.bottom - 8);
                }
            }]
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initInvestmentBubbleChart);
    } else {
        initInvestmentBubbleChart();
    }

    window.initInvestmentBubbleChart = initInvestmentBubbleChart;
})();
