/**
 * Roadmap Widget Component - External JavaScript
 * Extracted from app/templates/components/roadmap_widget.html
 *
 * Expects window.__ROADMAP_WIDGET_CONFIG__ to be set per-instance with:
 *   { containerId: string, endpoint: string }
 */
function initRoadmapWidgetInstance(containerId, endpoint) {
    // Initialize roadmap data for this widget instance
    window['roadmapData_' + containerId] = {
        items: [],
        filteredItems: [],
        timelinePeriods: [],
        displayMode: 'month',
        viewMode: 'auto',
        initialized: false
    };

    // Initialize widget
    function initRoadmapWidget(cid, ep) {
        fetch(ep)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    window['roadmapData_' + cid].items = data.items || [];
                    window['roadmapData_' + cid].filteredItems = data.items || [];
                    renderRoadmapTimeline(cid);
                    updateStats(cid);
                }
            })
            .catch(function(err) { console.error('Failed to load roadmap:', err); });
    }

    // View toggle
    window['setRoadmapView' + containerId] = function(mode) {
        window['roadmapData_' + containerId].viewMode = mode;
        let btnAuto = document.getElementById('roadmap-view-auto-' + containerId);
        let btnSaved = document.getElementById('roadmap-view-saved-' + containerId);
        if (btnAuto && btnSaved) {
            if (mode === 'auto') {
                btnAuto.className = 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all';
                btnSaved.className = 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
            } else {
                btnAuto.className = 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
                btnSaved.className = 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all';
            }
        }
        initRoadmapWidget(containerId, endpoint);
    };

    // Expand/Collapse all
    window['expandAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(function(row) {
            row.classList.remove('collapsed');
        });
        showToast('All items expanded', 'success');
    };

    window['collapseAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(function(row) {
            row.classList.add('collapsed');
        });
        showToast('All items collapsed', 'success');
    };

    // Jump to today
    window['jumpToToday' + containerId] = function() {
        let container = document.getElementById('roadmap-timeline-container-' + containerId);
        if (container) {
            let todayCol = container.querySelector('.timeline-today');
            if (todayCol) {
                todayCol.scrollIntoView({ behavior: 'smooth', inline: 'center' });
            }
        }
    };

    // Quick add modal
    window['openQuickAddModal' + containerId] = function() {
        Platform.toast.info('Add Capability feature - to be implemented');
    };

    // Export menu
    window['toggleRoadmapExportMenu' + containerId] = function() {
        let menu = document.getElementById('roadmap-export-menu-' + containerId);
        if (menu) menu.classList.toggle('hidden');
    };

    // Export
    window['exportRoadmap' + containerId] = function(format) {
        showToast('Exporting as ' + format + '...', 'success');
        let menu = document.getElementById('roadmap-export-menu-' + containerId);
        if (menu) menu.classList.add('hidden');
    };

    // Timeline zoom
    window['setTimelineZoom' + containerId] = function(zoom) {
        window['roadmapData_' + containerId].displayMode = zoom;
        ['day', 'week', 'month', 'quarter'].forEach(function(z) {
            let btn = document.getElementById('zoom-' + z + '-' + containerId);
            if (btn) {
                btn.className = z === zoom
                    ? 'px-2 py-1 text-xs rounded bg-card shadow-sm font-medium text-muted-foreground transition-all'
                    : 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });
        renderRoadmapTimeline(containerId);
    };

    // Gap type filter
    window['setGapTypeFilter' + containerId] = function(type) {
        let filter = document.getElementById('roadmap-gap-type-filter-' + containerId);
        if (filter) filter.value = type;
        filterRoadmapItems(containerId);
    };

    // Toggle filter panel
    window['toggleFilterPanel' + containerId] = function() {
        let panel = document.getElementById('filter-panel-content-' + containerId);
        if (panel) panel.classList.toggle('hidden');
    };

    // Clear all filters
    window['clearAllFilters' + containerId] = function() {
        let ids = ['roadmap-gap-type-filter-', 'roadmap-priority-filter-', 'roadmap-status-filter-', 'roadmap-domain-filter-', 'roadmap-search-'];
        ids.forEach(function(id) {
            let el = document.getElementById(id + containerId);
            if (el) el.value = '';
        });
        filterRoadmapItems(containerId);
    };

    // Filter items
    window['filterRoadmapItems' + containerId] = function() {
        applyRoadmapFilters(containerId);
    };

    // Apply filters
    window['applyRoadmapFilters' + containerId] = function() {
        applyRoadmapFilters(containerId);
    };

    function applyRoadmapFilters(cid) {
        let gapTypeEl = document.getElementById('roadmap-gap-type-filter-' + cid);
        let priorityEl = document.getElementById('roadmap-priority-filter-' + cid);
        let statusEl = document.getElementById('roadmap-status-filter-' + cid);
        let searchEl = document.getElementById('roadmap-search-' + cid);

        let gapType = gapTypeEl ? gapTypeEl.value : '';
        let priority = priorityEl ? priorityEl.value : '';
        let status = statusEl ? statusEl.value : '';
        let search = searchEl ? searchEl.value.toLowerCase() : '';

        let data = window['roadmapData_' + cid];
        data.filteredItems = data.items.filter(function(item) {
            let matchType = !gapType || (item.gap_types && item.gap_types.includes(gapType));
            let matchPriority = !priority || item.priority === priority;
            let matchStatus = !status || item.status === status;
            let matchSearch = !search || (item.name && item.name.toLowerCase().includes(search));
            return matchType && matchPriority && matchStatus && matchSearch;
        });

        renderRoadmapTimeline(cid);
        updateStats(cid);

        let visibleCount = document.getElementById('roadmap-visible-count-' + cid);
        if (visibleCount) visibleCount.textContent = data.filteredItems.length;
    }

    function filterRoadmapItems(cid) {
        applyRoadmapFilters(cid);
    }

    // Update statistics
    function updateStats(cid) {
        let data = window['roadmapData_' + cid];
        let items = data.filteredItems || [];

        let coverage = items.filter(function(i) { return i.gap_types && i.gap_types.includes('coverage'); }).length;
        let quality = items.filter(function(i) { return i.gap_types && i.gap_types.includes('quality'); }).length;
        let retirement = items.filter(function(i) { return i.gap_types && i.gap_types.includes('retirement'); }).length;
        let modernization = items.filter(function(i) { return i.gap_types && i.gap_types.includes('modernization'); }).length;
        let critical = items.filter(function(i) { return i.priority === 'critical'; }).length;

        let idMap = {};
        idMap['roadmap-coverage-count-'] = coverage;
        idMap['roadmap-quality-count-'] = quality;
        idMap['roadmap-retirement-count-'] = retirement;
        idMap['roadmap-modernization-count-'] = modernization;
        idMap['roadmap-gap-count-'] = items.length;
        idMap['roadmap-critical-count-'] = critical;
        idMap['roadmap-high-count-'] = items.filter(function(i) { return i.priority === 'high'; }).length;
        idMap['roadmap-total-count-'] = data.items.length;
        idMap['roadmap-visible-count-'] = items.length;

        Object.keys(idMap).forEach(function(id) {
            let el = document.getElementById(id + cid);
            if (el) el.textContent = idMap[id];
        });
    }

    // Render timeline (simplified)
    function renderRoadmapTimeline(cid) {
        let container = document.getElementById('roadmap-timeline-' + cid);
        if (!container) return;

        let data = window['roadmapData_' + cid];
        let items = data.filteredItems || [];

        if (items.length === 0) {
            safeHTML(container, '<div class="p-8 text-center text-muted-foreground">No items to display</div>');
            return;
        }

        safeHTML(container, items.map(function(item) {
            return '<div class="roadmap-row p-4 border-b border-border hover:bg-muted/50">' +
                '<div class="flex items-center justify-between">' +
                    '<div>' +
                        '<h4 class="font-medium text-foreground">' + (item.name || 'Untitled') + '</h4>' +
                        '<p class="text-sm text-muted-foreground">' + (item.domain_name || 'Unknown domain') + ' &bull; ' + (item.priority || 'No priority') + '</p>' +
                    '</div>' +
                    '<span class="px-2 py-1 text-xs rounded-full ' + getPriorityClass(item.priority) + '">' + (item.priority || 'N/A') + '</span>' +
                '</div>' +
            '</div>';
        }).join(''));

        let visibleCountEl = document.getElementById('roadmap-visible-count-' + cid);
        if (visibleCountEl) visibleCountEl.textContent = items.length;
    }

    function getPriorityClass(priority) {
        let classes = {
            critical: 'bg-destructive/10 text-destructive',
            high: 'bg-orange-100 text-orange-800',
            medium: 'bg-amber-500/10 text-amber-800',
            low: 'bg-emerald-500/10 text-emerald-800'
        };
        return classes[priority] || 'bg-muted text-foreground';
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initRoadmapWidget(containerId, endpoint);
        });
    } else {
        initRoadmapWidget(containerId, endpoint);
    }
}

// Auto-initialize from config if present
(function() {
    let configs = window.__ROADMAP_WIDGET_CONFIGS__ || [];
    configs.forEach(function(cfg) {
        initRoadmapWidgetInstance(cfg.containerId, cfg.endpoint);
    });
})();
