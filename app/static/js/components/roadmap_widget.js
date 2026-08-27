/* Extracted from components/roadmap_widget.html (ARCH-064): ~31KB of JS kept
   out of every server-rendered page load and cached instead. The widget is
   single-instance per page; containerId/endpoint are read from the
   .roadmap-widget root element rather than baked in by Jinja. All ~200
   dynamically-named window['fn'+containerId] globals still match the
   Jinja-rendered call sites in the markup, which is unchanged. */
// Roadmap Widget JavaScript (containerId resolved at runtime from .roadmap-widget)
(function() {
    const _rw = document.querySelector('.roadmap-widget');
    const containerId = _rw ? _rw.id : '';
    const endpoint = _rw ? (_rw.dataset.endpoint || '') : '';
    
    // Initialize roadmap data for this widget instance
    window['roadmapData_' + containerId] = {
        items: [],
        filteredItems: [],
        timelinePeriods: [],
        displayMode: 'month',
        viewMode: 'auto',
        initialized: false,
        timelineYears: 4,
        timelineCustomStart: null,
        timelineCustomEnd: null,
        timelineStart: null,
        timelineEnd: null
    };

    function isWidgetVisible() {
        const root = document.getElementById(containerId);
        return !!(root && root.offsetParent !== null);
    }

    function initializeWhenVisible() {
        if (window['roadmapData_' + containerId].initialized) {
            return;
        }

        if (isWidgetVisible()) {
            window['roadmapData_' + containerId].initialized = true;
            window['initRoadmapWidget' + containerId](containerId, endpoint);
            return;
        }

        const pollId = window.setInterval(function() {
            if (!isWidgetVisible()) {
                return;
            }

            window.clearInterval(pollId);
            if (!window['roadmapData_' + containerId].initialized) {
                window['roadmapData_' + containerId].initialized = true;
                window['initRoadmapWidget' + containerId](containerId, endpoint);
            }
        }, 250);
    }

    // Define all functions on window immediately
    window['initRoadmapWidget' + containerId] = function(cid, ep) {
        fetch(ep)
            .then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    const items = data.items || data.gaps || [];
                    const wdata = window['roadmapData_' + cid];
                    wdata.items = items;
                    wdata.filteredItems = items;

                    // Calculate timeline range
                    const now = new Date();
                    const years = wdata.timelineYears || 4;
                    if (wdata.timelineCustomStart && wdata.timelineCustomEnd) {
                        wdata.timelineStart = new Date(wdata.timelineCustomStart);
                        wdata.timelineEnd = new Date(wdata.timelineCustomEnd);
                    } else {
                        wdata.timelineStart = new Date(now.getFullYear(), 0, 1);
                        wdata.timelineEnd = new Date(now.getFullYear() + years, 0, 1);
                    }

                    window['renderRoadmapTimeline' + cid](cid);
                    window['updateStats' + cid](cid);
                } else {
                    throw new Error(data.error || 'The roadmap data could not be loaded.');
                }
            })
            .catch(err => {
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Failed to load the roadmap: ' + (err.message || 'unknown error'));
                }
            });
    };
    
    window['setRoadmapView' + containerId] = function(mode) {
        window['roadmapData_' + containerId].viewMode = mode;
        const btnAuto = document.getElementById('roadmap-view-auto-' + containerId);
        const btnSaved = document.getElementById('roadmap-view-saved-' + containerId);
        if (btnAuto && btnSaved) {
            if (mode === 'auto') {
                btnAuto.className = 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all';
                btnSaved.className = 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
            } else {
                btnAuto.className = 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
                btnSaved.className = 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all';
            }
        }
        window['initRoadmapWidget' + containerId](containerId, endpoint);
    };
    
    window['expandAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(row => {
            row.classList.remove('collapsed');
        });
        window['showToast' + containerId]('All items expanded', 'success');
    };
    
    window['collapseAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(row => {
            row.classList.add('collapsed');
        });
        window['showToast' + containerId]('All items collapsed', 'success');
    };
    
    window['jumpToToday' + containerId] = function() {
        const container = document.getElementById('roadmap-timeline-container-' + containerId);
        if (container) {
            const todayCol = container.querySelector('.timeline-today');
            if (todayCol) {
                todayCol.scrollIntoView({ behavior: 'smooth', inline: 'center' });
            }
        }
    };
    
    window['openQuickAddModal' + containerId] = function() {
        Platform.toast.info('Add Capability feature - to be implemented');
    };
    
    window['toggleRoadmapExportMenu' + containerId] = function() {
        const menu = document.getElementById('roadmap-export-menu-' + containerId);
        if (menu) menu.classList.toggle('hidden');
    };
    
    window['exportRoadmap' + containerId] = function(format) {
        window['showToast' + containerId]('Exporting as ' + format + '...', 'success');
        const menu = document.getElementById('roadmap-export-menu-' + containerId);
        if (menu) menu.classList.add('hidden');
    };
    
    window['setTimelineZoom' + containerId] = function(zoom) {
        window['roadmapData_' + containerId].displayMode = zoom;
        ['day', 'week', 'month', 'quarter'].forEach(z => {
            const btn = document.getElementById('zoom-' + z + '-' + containerId);
            if (btn) {
                btn.className = z === zoom
                    ? 'px-2 py-1 text-xs rounded bg-card shadow-sm font-medium text-muted-foreground transition-all'
                    : 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });
        window['renderRoadmapTimeline' + containerId](containerId);
    };

    window['setTimelineRangeWidget' + containerId] = function(years) {
        const data = window['roadmapData_' + containerId];
        data.timelineYears = years;
        data.timelineCustomStart = null;
        data.timelineCustomEnd = null;

        [1, 2, 4, 6, 10].forEach(y => {
            const btn = document.querySelector('[data-timeline-range-' + containerId + '="' + y + '"]');
            if (btn) {
                btn.className = y === years
                    ? 'px-2 py-1 text-xs rounded bg-card shadow-sm font-medium text-muted-foreground transition-all'
                    : 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });

        const startInput = document.getElementById('timeline-custom-start-' + containerId);
        const endInput = document.getElementById('timeline-custom-end-' + containerId);
        if (startInput) startInput.value = '';
        if (endInput) endInput.value = '';

        const now = new Date();
        data.timelineStart = new Date(now.getFullYear(), 0, 1);
        data.timelineEnd = new Date(now.getFullYear() + years, 0, 1);

        window['renderRoadmapTimeline' + containerId](containerId);
        window['updateStats' + containerId](containerId);
        window['showToast' + containerId]('Timeline range: ' + years + ' year' + (years > 1 ? 's' : ''), 'success');
    };

    window['applyCustomTimelineRange' + containerId] = function() {
        const startInput = document.getElementById('timeline-custom-start-' + containerId);
        const endInput = document.getElementById('timeline-custom-end-' + containerId);

        if (!startInput || !endInput || !startInput.value || !endInput.value) {
            window['showToast' + containerId]('Please set both start and end dates', 'warning');
            return;
        }

        const startDate = new Date(startInput.value);
        const endDate = new Date(endInput.value);

        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
            window['showToast' + containerId]('Invalid date format', 'error');
            return;
        }

        if (endDate <= startDate) {
            window['showToast' + containerId]('End date must be after start date', 'warning');
            return;
        }

        const data = window['roadmapData_' + containerId];
        data.timelineCustomStart = startDate;
        data.timelineCustomEnd = endDate;
        data.timelineStart = startDate;
        data.timelineEnd = endDate;

        [1, 2, 4, 6, 10].forEach(y => {
            const btn = document.querySelector('[data-timeline-range-' + containerId + '="' + y + '"]');
            if (btn) {
                btn.className = 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });

        window['renderRoadmapTimeline' + containerId](containerId);
        window['updateStats' + containerId](containerId);

        const startStr = startDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        const endStr = endDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        window['showToast' + containerId]('Custom range: ' + startStr + ' - ' + endStr, 'success');
    };

    window['setGapTypeFilter' + containerId] = function(type) {
        const filter = document.getElementById('roadmap-gap-type-filter-' + containerId);
        if (filter) filter.value = type;
        window['filterRoadmapItems' + containerId]();
    };
    
    window['toggleFilterPanel' + containerId] = function() {
        const panel = document.getElementById('filter-panel-content-' + containerId);
        if (panel) panel.classList.toggle('hidden');
    };
    
    window['clearAllFilters' + containerId] = function() {
        const ids = ['roadmap-gap-type-filter-', 'roadmap-priority-filter-', 'roadmap-status-filter-', 'roadmap-domain-filter-', 'roadmap-search-'];
        ids.forEach(id => {
            const el = document.getElementById(id + containerId);
            if (el) el.value = '';
        });
        window['filterRoadmapItems' + containerId]();
    };
    
    window['filterRoadmapItems' + containerId] = function() {
        window['applyRoadmapFilters' + containerId]();
    };
    
    window['applyRoadmapFilters' + containerId] = function() {
        const gapType = document.getElementById('roadmap-gap-type-filter-' + containerId)?.value || '';
        const priority = document.getElementById('roadmap-priority-filter-' + containerId)?.value || '';
        const status = document.getElementById('roadmap-status-filter-' + containerId)?.value || '';
        const search = (document.getElementById('roadmap-search-' + containerId)?.value || '').toLowerCase();
        
        const data = window['roadmapData_' + containerId];
        data.filteredItems = data.items.filter(item => {
            const matchType = !gapType || (item.gap_types && item.gap_types.includes(gapType));
            const matchPriority = !priority || item.priority === priority;
            const matchStatus = !status || item.status === status;
            const matchSearch = !search || (item.name && item.name.toLowerCase().includes(search));
            return matchType && matchPriority && matchStatus && matchSearch;
        });
        
        window['renderRoadmapTimeline' + containerId](containerId);
        window['updateStats' + containerId](containerId);
        
        const visibleCount = document.getElementById('roadmap-visible-count-' + containerId);
        if (visibleCount) visibleCount.textContent = data.filteredItems.length;
    };
    
    window['updateStats' + containerId] = function(cid) {
        const data = window['roadmapData_' + cid];
        const items = data.filteredItems || [];
        
        const counts = {
            coverage: items.filter(i => i.gap_types && i.gap_types.includes('coverage')).length,
            quality: items.filter(i => i.gap_types && i.gap_types.includes('quality')).length,
            retirement: items.filter(i => i.gap_types && i.gap_types.includes('retirement')).length,
            modernization: items.filter(i => i.gap_types && i.gap_types.includes('modernization')).length,
            critical: items.filter(i => i.priority === 'critical').length,
            high: items.filter(i => i.priority === 'high').length,
            total: items.length,
            all: data.items.length
        };
        
        const ids = {
            'roadmap-coverage-count-': counts.coverage,
            'roadmap-quality-count-': counts.quality,
            'roadmap-retirement-count-': counts.retirement,
            'roadmap-modernization-count-': counts.modernization,
            'roadmap-gap-count-': counts.total,
            'roadmap-critical-count-': counts.critical,
            'roadmap-high-count-': counts.high,
            'roadmap-total-count-': counts.all,
            'roadmap-visible-count-': counts.total
        };
        
        Object.keys(ids).forEach(id => {
            const el = document.getElementById(id + cid);
            if (el) el.textContent = ids[id];
        });
    };
    
    window['renderRoadmapTimeline' + containerId] = function(cid) {
        const container = document.getElementById('roadmap-timeline-' + cid);
        if (!container) return;
        
        const data = window['roadmapData_' + cid];
        const items = data.filteredItems || [];
        
        if (items.length === 0) {
            container.innerHTML = '<div class="p-8 text-center text-muted-foreground">No items to display</div>';
            return;
        }
        
        const getPriorityClassForRender = function(priority) {
            const classes = {
                critical: 'bg-destructive/10 text-destructive',
                high: 'bg-warning/10 text-warning',
                medium: 'bg-warning/10 text-warning',
                low: 'bg-success/10 text-success'
            };
            return classes[priority] || 'bg-muted text-foreground';
        };
        
        container.innerHTML = items.map(item => `
            <div class="roadmap-row p-4 border-b border-border hover:bg-muted/50">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-medium text-foreground">${escapeHtml(item.name || 'Untitled')}</h4>
                        <p class="text-sm text-muted-foreground">${escapeHtml(item.domain_name || 'Unknown domain')} • ${escapeHtml(item.priority || 'No priority')}</p>
                    </div>
                    <span class="px-2 py-1 text-xs rounded-full ${getPriorityClassForRender(item.priority)}">${escapeHtml(item.priority || 'N/A')}</span>
                </div>
            </div>
        `).join('');
    };
    
    window['showToast' + containerId] = function(message, type) {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${type === 'success' ? 'bg-success' : 'bg-primary'} text-primary-foreground`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    };
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeWhenVisible();
        });
    } else {
        initializeWhenVisible();
    }
})();
(function() {
    const _rw = document.querySelector('.roadmap-widget');
    const containerId = _rw ? _rw.id : '';
    const endpoint = _rw ? (_rw.dataset.endpoint || '') : '';
    
    // Initialize roadmap data for this widget instance
    window['roadmapData_' + containerId] = {
        items: [],
        filteredItems: [],
        timelinePeriods: [],
        displayMode: 'month',
        viewMode: 'auto',
        initialized: false,
        timelineYears: 4,
        timelineCustomStart: null,
        timelineCustomEnd: null,
        timelineStart: null,
        timelineEnd: null
    };

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        initRoadmapWidget(containerId, endpoint);
    });
    
    // Initialize widget
    function initRoadmapWidget(cid, ep) {
        fetch(ep)
            .then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    let wdata = window['roadmapData_' + cid];
                    wdata.items = data.items || [];
                    wdata.filteredItems = data.items || [];

                    // Calculate timeline range from configured years
                    let now = new Date();
                    let years = wdata.timelineYears || 4;
                    if (wdata.timelineCustomStart && wdata.timelineCustomEnd) {
                        wdata.timelineStart = new Date(wdata.timelineCustomStart);
                        wdata.timelineEnd = new Date(wdata.timelineCustomEnd);
                    } else {
                        wdata.timelineStart = new Date(now.getFullYear(), 0, 1);
                        wdata.timelineEnd = new Date(now.getFullYear() + years, 0, 1);
                    }

                    renderRoadmapTimeline(cid);
                    updateStats(cid);

                    // Update timeline range display
                    const rangeEl = document.getElementById('roadmap-timeline-range-' + cid);
                    if (rangeEl && wdata.timelineStart && wdata.timelineEnd) {
                        let startStr = wdata.timelineStart.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
                        let endStr = wdata.timelineEnd.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
                        rangeEl.textContent = startStr + ' - ' + endStr;
                    }
                } else {
                    throw new Error(data.error || 'The roadmap data could not be loaded.');
                }
            })
            .catch(err => {
                if (window.Platform && Platform.toast) {
                    Platform.toast.error('Failed to load the roadmap: ' + (err.message || 'unknown error'));
                }
            });
    }
    
    // View toggle
    window['setRoadmapView' + containerId] = function(mode) {
        window['roadmapData_' + containerId].viewMode = mode;
        document.getElementById('roadmap-view-auto-' + containerId).className = 
            mode === 'auto' ? 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all' 
                           : 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
        document.getElementById('roadmap-view-saved-' + containerId).className = 
            mode === 'saved' ? 'px-3 py-1.5 text-sm rounded-md bg-card shadow-sm font-medium text-muted-foreground transition-all' 
                            : 'px-3 py-1.5 text-sm rounded-md font-medium text-muted-foreground hover:text-foreground transition-all';
        initRoadmapWidget(containerId, endpoint);
    };
    
    // Expand/Collapse all
    window['expandAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(row => {
            row.classList.remove('collapsed');
        });
        showToast('All items expanded', 'success');
    };
    
    window['collapseAllRoadmapRows' + containerId] = function() {
        document.querySelectorAll('#roadmap-timeline-' + containerId + ' .roadmap-row').forEach(row => {
            row.classList.add('collapsed');
        });
        showToast('All items collapsed', 'success');
    };
    
    // Jump to today
    window['jumpToToday' + containerId] = function() {
        const container = document.getElementById('roadmap-timeline-container-' + containerId);
        const todayCol = container.querySelector('.timeline-today');
        if (todayCol) {
            todayCol.scrollIntoView({ behavior: 'smooth', inline: 'center' });
        }
    };
    
    // Quick add modal
    window['openQuickAddModal' + containerId] = function() {
        Platform.toast.info('Add Capability feature - to be implemented');
    };
    
    // Export menu
    window['toggleRoadmapExportMenu' + containerId] = function() {
        const menu = document.getElementById('roadmap-export-menu-' + containerId);
        menu.classList.toggle('hidden');
    };
    
    // Export
    window['exportRoadmap' + containerId] = function(format) {
        showToast('Exporting as ' + format + '...', 'success');
        document.getElementById('roadmap-export-menu-' + containerId).classList.add('hidden');
    };
    
    // Timeline zoom
    window['setTimelineZoom' + containerId] = function(zoom) {
        window['roadmapData_' + containerId].displayMode = zoom;
        ['day', 'week', 'month', 'quarter'].forEach(z => {
            const btn = document.getElementById('zoom-' + z + '-' + containerId);
            if (btn) {
                btn.className = z === zoom
                    ? 'px-2 py-1 text-xs rounded bg-card shadow-sm font-medium text-muted-foreground transition-all'
                    : 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });
        renderRoadmapTimeline(containerId);
    };

    // Timeline range (preset years)
    window['setTimelineRangeWidget' + containerId] = function(years) {
        let data = window['roadmapData_' + containerId];
        data.timelineYears = years;
        data.timelineCustomStart = null;
        data.timelineCustomEnd = null;

        // Update range button states
        [1, 2, 4, 6, 10].forEach(function(y) {
            let btn = document.querySelector('[data-timeline-range-' + containerId + '="' + y + '"]');
            if (btn) {
                btn.className = y === years
                    ? 'px-2 py-1 text-xs rounded bg-card shadow-sm font-medium text-muted-foreground transition-all'
                    : 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });

        // Clear custom date inputs
        let startInput = document.getElementById('timeline-custom-start-' + containerId);
        let endInput = document.getElementById('timeline-custom-end-' + containerId);
        if (startInput) startInput.value = '';
        if (endInput) endInput.value = '';

        // Recalculate timeline with the new range
        let now = new Date();
        data.timelineStart = new Date(now.getFullYear(), 0, 1);
        data.timelineEnd = new Date(now.getFullYear() + years, 0, 1);

        renderRoadmapTimeline(containerId);
        updateStats(containerId);

        // Update timeline range display
        const rangeEl = document.getElementById('roadmap-timeline-range-' + containerId);
        if (rangeEl) {
            let startStr = data.timelineStart.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
            let endStr = data.timelineEnd.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
            rangeEl.textContent = startStr + ' - ' + endStr;
        }

        showToast('Timeline range: ' + years + ' year' + (years > 1 ? 's' : ''), 'success');
    };

    // Custom date range
    window['applyCustomTimelineRange' + containerId] = function() {
        let startInput = document.getElementById('timeline-custom-start-' + containerId);
        let endInput = document.getElementById('timeline-custom-end-' + containerId);

        if (!startInput || !endInput || !startInput.value || !endInput.value) {
            showToast('Please set both start and end dates', 'warning');
            return;
        }

        let startDate = new Date(startInput.value);
        let endDate = new Date(endInput.value);

        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
            showToast('Invalid date format', 'error');
            return;
        }

        if (endDate <= startDate) {
            showToast('End date must be after start date', 'warning');
            return;
        }

        let data = window['roadmapData_' + containerId];
        data.timelineCustomStart = startDate;
        data.timelineCustomEnd = endDate;
        data.timelineStart = startDate;
        data.timelineEnd = endDate;

        // Deselect all preset range buttons
        [1, 2, 4, 6, 10].forEach(function(y) {
            let btn = document.querySelector('[data-timeline-range-' + containerId + '="' + y + '"]');
            if (btn) {
                btn.className = 'px-2 py-1 text-xs rounded font-medium text-muted-foreground hover:bg-card hover:shadow-sm transition-all';
            }
        });

        renderRoadmapTimeline(containerId);
        updateStats(containerId);

        // Update timeline range display
        const rangeEl = document.getElementById('roadmap-timeline-range-' + containerId);
        if (rangeEl) {
            let startStr = startDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
            let endStr = endDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
            rangeEl.textContent = startStr + ' - ' + endStr;
        }

        showToast('Custom range: ' + startDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) + ' - ' + endDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }), 'success');
    };
    
    // Gap type filter
    window['setGapTypeFilter' + containerId] = function(type) {
        document.getElementById('roadmap-gap-type-filter-' + containerId).value = type;
        filterRoadmapItems(containerId);
    };
    
    // Toggle filter panel
    window['toggleFilterPanel' + containerId] = function() {
        const panel = document.getElementById('filter-panel-content-' + containerId);
        panel.classList.toggle('hidden');
    };
    
    // Clear all filters
    window['clearAllFilters' + containerId] = function() {
        document.getElementById('roadmap-gap-type-filter-' + containerId).value = '';
        document.getElementById('roadmap-priority-filter-' + containerId).value = '';
        document.getElementById('roadmap-status-filter-' + containerId).value = '';
        document.getElementById('roadmap-domain-filter-' + containerId).value = '';
        document.getElementById('roadmap-search-' + containerId).value = '';
        filterRoadmapItems(containerId);
    };
    
    // Filter items
    window['filterRoadmapItems' + containerId] = function() {
        applyRoadmapFilters(containerId);
    };
    
    // Apply filters
    window['applyRoadmapFilters' + containerId] = function() {
        const gapType = document.getElementById('roadmap-gap-type-filter-' + containerId).value;
        const priority = document.getElementById('roadmap-priority-filter-' + containerId).value;
        const status = document.getElementById('roadmap-status-filter-' + containerId).value;
        const search = document.getElementById('roadmap-search-' + containerId).value.toLowerCase();
        
        const data = window['roadmapData_' + containerId];
        data.filteredItems = data.items.filter(item => {
            const matchType = !gapType || (item.gap_types && item.gap_types.includes(gapType));
            const matchPriority = !priority || item.priority === priority;
            const matchStatus = !status || item.status === status;
            const matchSearch = !search || (item.name && item.name.toLowerCase().includes(search));
            return matchType && matchPriority && matchStatus && matchSearch;
        });
        
        renderRoadmapTimeline(containerId);
        updateStats(containerId);
        
        document.getElementById('roadmap-visible-count-' + containerId).textContent = data.filteredItems.length;
    };
    
    // Update statistics
    function updateStats(cid) {
        const data = window['roadmapData_' + cid];
        const items = data.filteredItems || [];
        
        const coverage = items.filter(i => i.gap_types && i.gap_types.includes('coverage')).length;
        const quality = items.filter(i => i.gap_types && i.gap_types.includes('quality')).length;
        const retirement = items.filter(i => i.gap_types && i.gap_types.includes('retirement')).length;
        const modernization = items.filter(i => i.gap_types && i.gap_types.includes('modernization')).length;
        const critical = items.filter(i => i.priority === 'critical').length;
        
        document.getElementById('roadmap-coverage-count-' + cid).textContent = coverage;
        document.getElementById('roadmap-quality-count-' + cid).textContent = quality;
        document.getElementById('roadmap-retirement-count-' + cid).textContent = retirement;
        document.getElementById('roadmap-modernization-count-' + cid).textContent = modernization;
        document.getElementById('roadmap-gap-count-' + cid).textContent = items.length;
        document.getElementById('roadmap-critical-count-' + cid).textContent = critical;
        document.getElementById('roadmap-high-count-' + cid).textContent = items.filter(i => i.priority === 'high').length;
        document.getElementById('roadmap-total-count-' + cid).textContent = data.items.length;
    }
    
    // Render timeline (simplified)
    function renderRoadmapTimeline(cid) {
        const container = document.getElementById('roadmap-timeline-' + cid);
        const data = window['roadmapData_' + cid];
        const items = data.filteredItems || [];
        
        if (items.length === 0) {
            container.innerHTML = '<div class="p-8 text-center text-muted-foreground">No items to display</div>';
            return;
        }
        
        // Simple list view for now
        container.innerHTML = items.map(item => `
            <div class="roadmap-row p-4 border-b border-border hover:bg-muted/50">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-medium text-foreground">${escapeHtml(item.name || 'Untitled')}</h4>
                        <p class="text-sm text-muted-foreground">${escapeHtml(item.domain_name || 'Unknown domain')} • ${escapeHtml(item.priority || 'No priority')}</p>
                    </div>
                    <span class="px-2 py-1 text-xs rounded-full ${getPriorityClass(item.priority)}">${escapeHtml(item.priority || 'N/A')}</span>
                </div>
            </div>
        `).join('');
        
        document.getElementById('roadmap-visible-count-' + cid).textContent = items.length;
    }
    
    function getPriorityClass(priority) {
        const classes = {
            critical: 'bg-destructive/10 text-destructive',
            high: 'bg-warning/10 text-warning',
            medium: 'bg-warning/10 text-warning',
            low: 'bg-success/10 text-success'
        };
        return classes[priority] || 'bg-muted text-foreground';
    }
    
    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${type === 'success' ? 'bg-success' : 'bg-primary'} text-primary-foreground`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
})();
