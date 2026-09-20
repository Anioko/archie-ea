/**
 * Shared helper for resolving a shadcn/ui CSS custom property (e.g. `--warning`)
 * to a real, Chart.js-parseable colour string at runtime.
 *
 * `hsl(var(--warning))` is valid CSS but NOT a valid JavaScript colour literal:
 * `var(...)` only resolves inside an actual CSS property value, so handing it
 * to a JS charting library (Chart.js -> @kurkle/color) fails to parse silently
 * and the library falls back to its default fill (black). This resolves the
 * custom property via `getComputedStyle` first, so the string handed to the
 * chart is a real `H S% L%` triplet.
 *
 * Single source of truth — previously duplicated in
 * capability_map/maturity_radar.js and capability_map/investment_bubble.js,
 * and diverged into a broken inline copy in arb/dashboard.html (2026-09-17).
 */
(function () {
    'use strict';

    function cssHSL(varName, alpha) {
        var raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
        if (!raw) return null;
        return alpha !== undefined ? 'hsl(' + raw + ' / ' + alpha + ')' : 'hsl(' + raw + ')';
    }

    window.ArchieColorTokens = window.ArchieColorTokens || {};
    window.ArchieColorTokens.cssHSL = cssHSL;
})();
