/**
 * Capability Model — nested-box BIZBOK capability map (Business Architect visual 1).
 *
 * Renders Level 1 capabilities as containers with their Level 2 / Level 3 capabilities
 * nested inside, grouped by Business Domain (L0), heat-shaded by maturity gap.
 *
 * Data source: GET /capability-map/api/unified-capabilities — the SAME endpoint the
 * existing "Heat Map" tab already uses (see loadHeatMap() in capability_map/index.js).
 * No new backend route is introduced.
 *
 * KNOWN DATA LIMITATION (documented fallback):
 * The unified-capabilities endpoint returns `level` (1/2/3) and `domain.name` per
 * capability, but it does NOT return `parent_capability_id` — so a true parent → child
 * tree (this exact L2 belongs under that exact L1 box) cannot be reconstructed from
 * this endpoint alone. As a faithful fallback we nest by BusinessDomain (outer
 * container) → capability level (L1 shown as a header tier, L2/L3 nested as smaller
 * boxes in tiers below), which still satisfies "L1 containers with L2/L3 nested inside"
 * using only fields the endpoint actually exposes.
 *
 * Click behaviour: reuses the EXISTING capability drill-down used by the Heat Map tab
 * (window.showHeatmapDetail, defined in capability_map/index.js) by switching to that
 * tab and invoking it — no duplicate detail UI is built.
 */
(function () {
    'use strict';

    var _loaded = false;
    var _delegated = false;

    var LEVEL_LABELS = { 1: 'Level 1 — Strategic', 2: 'Level 2 — Business', 3: 'Level 3 — Operational' };

    function gapOf(cap) {
        // Mirrors the exact computation used by the existing Heat Map detail panel
        // (showHeatmapDetail in capability_map/index.js) so the two views agree.
        var current = cap.current_maturity || 1;
        var target = cap.target_maturity || 3;
        return target - current;
    }

    function gapBucketClasses(gap) {
        if (gap >= 2) {
            return { box: 'bg-destructive/15 border-destructive/40 hover:bg-destructive/25', dot: 'bg-destructive', text: 'text-destructive' };
        }
        if (gap === 1) {
            return { box: 'bg-amber-500/15 border-amber-500/40 hover:bg-amber-500/25', dot: 'bg-amber-500', text: 'text-amber-600' };
        }
        return { box: 'bg-emerald-500/15 border-emerald-500/40 hover:bg-emerald-500/25', dot: 'bg-emerald-500', text: 'text-emerald-600' };
    }

    function loadCapabilityModelTab() {
        if (_loaded) return;
        var loading = document.getElementById('capmodel-loading');
        var empty = document.getElementById('capmodel-empty');
        var container = document.getElementById('capmodel-container');
        if (!loading || !container) return;

        fetch('/capability-map/api/unified-capabilities')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var caps = data.unified_capabilities || data.capabilities || [];
                loading.classList.add('hidden');
                if (!caps.length) {
                    if (empty) empty.classList.remove('hidden');
                    return;
                }
                renderNestedCapabilityMap(caps, container);
                container.classList.remove('hidden');
                _loaded = true;
                if (typeof lucide !== 'undefined') lucide.createIcons();
            })
            .catch(function (e) {
                loading.classList.add('hidden');
                var msg = '<p class="text-sm text-destructive">Failed to load capability model: ' + escapeHtml(e.message) + '</p>';
                safeHTML(container, msg);
                container.classList.remove('hidden');
            });
    }

    function renderNestedCapabilityMap(caps, container) {
        // Group: domain name -> level -> [caps]
        var domains = {};
        caps.forEach(function (c) {
            var domainName = (c.domain && c.domain.name) || 'Unknown';
            var level = c.level || 1;
            if (level < 1 || level > 3) level = 3;
            if (!domains[domainName]) domains[domainName] = { 1: [], 2: [], 3: [] };
            domains[domainName][level].push(c);
        });

        var sortedDomainNames = Object.keys(domains).sort();
        var html = '<div class="space-y-6">';

        sortedDomainNames.forEach(function (domainName) {
            var tiers = domains[domainName];
            var totalInDomain = tiers[1].length + tiers[2].length + tiers[3].length;

            html += '<div class="rounded-lg border-2 border-border bg-card p-4">';
            html += '<div class="flex items-center justify-between mb-3 flex-wrap gap-2">';
            html += '<h3 class="text-sm font-bold text-foreground flex items-center gap-2">';
            html += '<i data-lucide="folder-tree" class="w-4 h-4 text-primary" aria-hidden="true"></i>';
            html += escapeHtml(domainName) + '</h3>';
            html += '<span class="text-[10px] text-muted-foreground">' + totalInDomain + ' capabilities</span>';
            html += '</div>';

            [1, 2, 3].forEach(function (level) {
                var capsAtLevel = tiers[level];
                if (!capsAtLevel.length) return;
                capsAtLevel.sort(function (a, b) { return (a.name || '').localeCompare(b.name || ''); });

                var sizeClasses = level === 1
                    ? 'px-4 py-3 text-sm font-semibold min-w-[160px]'
                    : level === 2
                        ? 'px-3 py-2 text-xs font-medium min-w-[130px]'
                        : 'px-2 py-1.5 text-[11px] font-medium min-w-[100px]';

                html += '<div class="mb-3 last:mb-0' + (level > 1 ? ' pl-4 border-l-2 border-border/60' : '') + '">';
                html += '<p class="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1.5">' + LEVEL_LABELS[level] + '</p>';
                html += '<div class="flex flex-wrap gap-2">';
                capsAtLevel.forEach(function (cap) {
                    var gap = gapOf(cap);
                    var colors = gapBucketClasses(gap);
                    var capJson = escapeHtml(JSON.stringify(cap));
                    html += '<button type="button" class="nm-cap-box text-left rounded-md border transition-colors cursor-pointer ' + sizeClasses + ' ' + colors.box + '"';
                    html += ' data-cap="' + capJson + '"';
                    html += ' title="' + escapeHtml(cap.name) + ' — maturity ' + (cap.current_maturity || 1) + '/' + (cap.target_maturity || 3) + '">';
                    html += '<span class="flex items-center gap-1.5">';
                    html += '<span class="w-2 h-2 rounded-full shrink-0 ' + colors.dot + '"></span>';
                    html += '<span class="truncate max-w-[220px] text-foreground">' + escapeHtml(cap.name) + '</span>';
                    html += '</span>';
                    html += '<span class="block mt-0.5 text-[10px] ' + colors.text + '">' + (cap.current_maturity || 1) + '/' + (cap.target_maturity || 3) + ' maturity · ' + (cap.mapping_count || 0) + ' app(s)</span>';
                    html += '</button>';
                });
                html += '</div></div>';
            });

            html += '</div>';
        });

        html += '</div>';
        safeHTML(container, html);

        if (!_delegated) {
            container.addEventListener('click', function (e) {
                var btn = e.target.closest('.nm-cap-box');
                if (!btn) return;
                var raw = btn.getAttribute('data-cap');
                var cap;
                try { cap = JSON.parse(raw); } catch (err) { return; }

                // Reuse the EXISTING Heat Map drill-down instead of building a new one:
                // switch to the Heat Map tab (its own @click loads/marks it active),
                // then invoke the same detail renderer the Heat Map tab uses.
                var heatmapTabBtn = document.getElementById('tab-heatmap');
                if (heatmapTabBtn) heatmapTabBtn.click();
                if (typeof window.showHeatmapDetail === 'function') {
                    window.showHeatmapDetail(cap);
                }
                if (window.Platform && Platform.toast && typeof Platform.toast.info === 'function') {
                    Platform.toast.info('Opened "' + cap.name + '" in the Heat Map detail panel.');
                }
            });
            _delegated = true;
        }
    }

    window.loadCapabilityModelTab = loadCapabilityModelTab;
})();
