/**
 * ui/gantt.js — Gantt timeline low-level module (v2)
 *
 * Per-day precision positioning, split-panel scroll sync,
 * configurable stats, enhanced dependency/milestone rendering.
 *
 * Requires: core/00-namespace.js through core/05-error.js
 * Provides: Platform.gantt.alpineMixin(options)
 *
 * NOTE: Task bar colors use inline styles from config.statusColors (data-driven).
 * This is a deliberate exception to token migration rules — see design doc Section 13.
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform.gantt] core/00-namespace.js must be loaded before ui/gantt.js');
    }

    let log   = global.Platform.log   ? global.Platform.log.child('gantt')   : { debug: function(){}, warn: function(){}, error: function(){} };
    let error = global.Platform.error || { handle: function(e){ console.error(e); } };

    // ── Constants ────────────────────────────────────────────────────────────
    let ROW_HEIGHT          = 40;
    let GROUP_HEIGHT        = 34;
    let LABEL_WIDTH         = 260;
    let DETAIL_PANEL_WIDTH  = 320;
    let HEADER_HEIGHT       = 44;
    let MIN_BAR_WIDTH       = 24;
    let BAR_LABEL_THRESHOLD = 100;
    let DAY_MS              = 86400000;

    /** Day-width in pixels per zoom level */
    let ZOOM_DAY_WIDTHS = {
        weeks:    28,
        months:   5,
        quarters: 2,
        years:    0.8
    };

    // ── Helpers ──────────────────────────────────────────────────────────────

    function _fetch(url, opts) {
        if (global.Platform.fetch) return global.Platform.fetch(url, opts);
        if (global.apiFetch)       return global.apiFetch(url, opts);
        return global.fetch(url, opts).then(function (r) { return r.json(); });
    }

    function _resolveField(obj, dotPath) {
        if (!obj || !dotPath) return undefined;
        let parts = dotPath.split('.');
        let current = obj;
        for (let i = 0; i < parts.length; i++) {
            if (current == null) return undefined;
            current = current[parts[i]];
        }
        return current;
    }

    function _buildUrl(base, params) {
        if (!params || Object.keys(params).length === 0) return base;
        let sep = base.indexOf('?') === -1 ? '?' : '&';
        let qs = new URLSearchParams();
        Object.keys(params).forEach(function (k) {
            let v = params[k];
            if (v !== '' && v !== null && v !== undefined) qs.set(k, v);
        });
        let str = qs.toString();
        return str ? base + sep + str : base;
    }

    function _daysBetween(a, b) {
        return Math.ceil((b - a) / DAY_MS);
    }

    function _toDate(v) {
        if (!v) return null;
        if (v instanceof Date) return v;
        let d = new Date(v);
        return isNaN(d.getTime()) ? null : d;
    }

    // ── Alpine mixin factory ─────────────────────────────────────────────────

    function alpineMixin(options) {
        options = options || {};
        let _endpoint    = options.endpoint    || '';
        let _containerId = options.containerId || 'gantt-timeline';

        return {
            // ── Data (from API or inline) ─────────────────────────────────
            groups:       [],
            tasks:        [],
            milestones:   [],
            _depPairs:    [],   // [[sourceId, targetId], ...]
            config:       {},
            stats:        [],

            // ── UI state ──────────────────────────────────────────────────
            zoom:              'months',
            collapsedGroupIds: [],
            selectedTaskId:    null,
            hoveredTaskId:     null,
            tooltipPos:        { x: 0, y: 0 },
            loading:           true,
            error:             null,
            filterText:        '',
            filterStatus:      '',
            showFilters:       false,
            allCollapsed:      false,
            _focusedRowIndex:  -1,
            ariaAnnouncement:  '',

            // ── Computed timeline ─────────────────────────────────────────
            timelineStart:      null,
            timelineEnd:        null,
            dayWidth:           5,
            timelineWidth:      0,
            periodLabels:       [],
            gridLines:          [],
            todayX:             -1,
            milestonePositions: [],
            dependencyPaths:    [],
            canvasHeight:       0,
            visibleRows:        [],

            // ── Internal ──────────────────────────────────────────────────
            _rowYPositions:       [],
            _endpoint:            _endpoint,
            _containerId:         _containerId,
            _onTaskClick:         options.onTaskClick         || null,
            _storageKey:          options.storageKey           || _containerId,
            _metadataFields:      options.metadataFields       || null,
            _detailPanelActions:  options.detailPanelActions   || null,
            _scrollTicking:       false,
            _abortController:     null,

            // ── CRUD state ────────────────────────────────────────────────
            _crudEndpoint:          options.crudEndpoint          || '',
            _secondaryCrudEndpoint: options.secondaryCrudEndpoint || '',
            _secondaryCrudLabel:    options.secondaryCrudLabel    || 'Add Child',
            crudFormOpen:           false,
            crudEditingId:          null,
            crudIsSecondary:        false,
            crudParentId:           null,
            crudSubmitting:         false,
            crudError:              '',
            crudForm:               { name: '', status: 'identified', priority: 'medium', start_date: '', end_date: '', description: '' },

            // ── Constants (exposed for template) ──────────────────────────
            ROW_HEIGHT:         ROW_HEIGHT,
            GROUP_HEIGHT:       GROUP_HEIGHT,
            LABEL_WIDTH:        LABEL_WIDTH,
            DETAIL_PANEL_WIDTH: DETAIL_PANEL_WIDTH,
            HEADER_HEIGHT:      HEADER_HEIGHT,
            MIN_BAR_WIDTH:      MIN_BAR_WIDTH,

            // ═══════════════════════════════════════════════════════════════
            // INIT
            // ═══════════════════════════════════════════════════════════════

            _ganttInit: function () {
                this._restoreZoom();
                if (this._endpoint) {
                    this._fetchData();
                } else if (options.data) {
                    this._loadInlineData(options.data);
                }
            },

            _loadInlineData: function (data) {
                this.groups     = data.groups     || [];
                this.tasks      = data.tasks      || [];
                this.milestones = data.milestones  || [];
                this.config     = data.config      || {};
                this.stats      = data.stats       || [];

                // Extract dependencies
                this._extractDependencies(data.dependencies);

                this._recompute();
                this.loading = false;

                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._scrollToToday(); });
                }
            },

            // ── Data fetching ─────────────────────────────────────────────

            reload: function (params) {
                this._fetchData(params);
            },

            _fetchData: function (params) {
                let self = this;
                self.loading = true;
                self.error   = null;

                if (self._abortController) {
                    try { self._abortController.abort(); } catch (e) { /* ignore */ }
                }
                self._abortController = typeof AbortController !== 'undefined' ? new AbortController() : null;

                let url = _buildUrl(self._endpoint, params);
                log.debug('Fetching gantt data', url);

                _fetch(url, self._abortController ? { signal: self._abortController.signal } : {})
                    .then(function (data) {
                        if (!data || !data.success) {
                            self.error   = (data && data.error) || 'Failed to load timeline data';
                            self.loading = false;
                            return;
                        }

                        let gantt = data.gantt || {};
                        self.groups     = gantt.groups     || [];
                        self.tasks      = gantt.tasks      || [];
                        self.milestones = gantt.milestones  || [];
                        self.config     = data.config       || {};
                        self.stats      = data.stats        || [];

                        // Extract dependencies from task objects (API format)
                        self._extractDependenciesFromTasks();

                        self._recompute();
                        self.loading = false;

                        if (typeof self.$nextTick === 'function') {
                            self.$nextTick(function () { self._scrollToToday(); });
                        } else {
                            requestAnimationFrame(function () { self._scrollToToday(); });
                        }
                    })
                    .catch(function (err) {
                        if (err && err.name === 'AbortError') return;
                        self.error   = (err && err.message) || 'Network error loading timeline';
                        self.loading = false;
                        log.error('Gantt fetch failed', err);
                    });
            },

            /**
             * Extract dependency pairs from task objects.
             * API format: each task has dependencies: [depId, ...] (tasks it depends ON).
             * Converts to _depPairs: [[sourceId, targetId], ...] where source blocks target.
             */
            _extractDependenciesFromTasks: function () {
                let pairs = [];
                this.tasks.forEach(function (t) {
                    if (t.dependencies && t.dependencies.length) {
                        t.dependencies.forEach(function (depId) {
                            pairs.push([depId, t.id]);
                        });
                    }
                });
                this._depPairs = pairs;
            },

            /**
             * Accept dependencies in the inline format: [[sourceId, targetId], ...]
             * or from task.dependencies.
             */
            _extractDependencies: function (deps) {
                if (Array.isArray(deps) && deps.length > 0) {
                    this._depPairs = deps;
                } else {
                    this._extractDependenciesFromTasks();
                }
            },

            // ═══════════════════════════════════════════════════════════════
            // RECOMPUTE
            // ═══════════════════════════════════════════════════════════════

            _recompute: function () {
                this._computeTimelineRange();
                this._computeDayWidth();
                this._computeTimelineWidth();
                this._computePeriodLabels();
                this._computeGridLines();
                this._computeTodayX();
                this._markOverlappingLabels();
                this._computeMilestonePositions();
                this._computeVisibleRows();
                this._computeCanvasHeight();
                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._computeDependencyPaths(); });
                } else {
                    requestAnimationFrame(function () { self._computeDependencyPaths(); });
                }
            },

            // ── Timeline range ────────────────────────────────────────────

            _computeTimelineRange: function () {
                let allDates = [];
                this.tasks.forEach(function (t) {
                    let s = _toDate(t.start_date);
                    let e = _toDate(t.end_date);
                    if (s) allDates.push(s);
                    if (e) allDates.push(e);
                });
                this.milestones.forEach(function (m) {
                    let d = _toDate(m.date);
                    if (d) allDates.push(d);
                });
                allDates.push(new Date());

                if (allDates.length === 0) {
                    this.timelineStart = new Date();
                    this.timelineEnd   = new Date();
                    return;
                }

                let min = new Date(Math.min.apply(null, allDates));
                let max = new Date(Math.max.apply(null, allDates));

                // Pad: 1 month before and after
                this.timelineStart = new Date(min.getFullYear(), min.getMonth() - 1, 1);
                this.timelineEnd   = new Date(max.getFullYear(), max.getMonth() + 2, 0);
            },

            _computeDayWidth: function () {
                this.dayWidth = ZOOM_DAY_WIDTHS[this.zoom] || 5;
            },

            _computeTimelineWidth: function () {
                let days = _daysBetween(this.timelineStart, this.timelineEnd);
                this.timelineWidth = Math.max(Math.ceil(days * this.dayWidth), 600);
            },

            // ── Per-day positioning ───────────────────────────────────────

            dateToX: function (date) {
                if (!this.timelineStart) return 0;
                let d = _toDate(date);
                if (!d) return 0;
                let days = (d - this.timelineStart) / DAY_MS;
                return Math.round(days * this.dayWidth);
            },

            getBarLeft: function (task) {
                return this.dateToX(task.start_date);
            },

            getBarWidth: function (task) {
                let left  = this.dateToX(task.start_date);
                let right = this.dateToX(task.end_date);
                return Math.max(right - left, MIN_BAR_WIDTH);
            },

            isBarLabelVisible: function (task) {
                return this.getBarWidth(task) > BAR_LABEL_THRESHOLD;
            },

            /**
             * Get the task bar position as inline style values.
             */
            getTaskPosition: function (task) {
                return {
                    left:  this.getBarLeft(task),
                    width: this.getBarWidth(task)
                };
            },

            // ── Period labels ─────────────────────────────────────────────

            _computePeriodLabels: function () {
                let labels = [];
                let end    = this.timelineEnd;
                let self   = this;
                let cursor;

                if (this.zoom === 'weeks') {
                    // Show month labels
                    cursor = new Date(this.timelineStart.getFullYear(), this.timelineStart.getMonth(), 1);
                    while (cursor <= end) {
                        labels.push({
                            x:      self.dateToX(cursor) + 4,
                            label:  cursor.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }),
                            hidden: false
                        });
                        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
                    }
                } else if (this.zoom === 'months') {
                    cursor = new Date(this.timelineStart.getFullYear(), this.timelineStart.getMonth(), 1);
                    while (cursor <= end) {
                        labels.push({
                            x:      self.dateToX(cursor) + 4,
                            label:  cursor.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }),
                            hidden: false
                        });
                        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
                    }
                } else if (this.zoom === 'quarters') {
                    cursor = new Date(this.timelineStart.getFullYear(), Math.floor(this.timelineStart.getMonth() / 3) * 3, 1);
                    while (cursor <= end) {
                        let q = Math.floor(cursor.getMonth() / 3) + 1;
                        labels.push({
                            x:      self.dateToX(cursor) + 4,
                            label:  'Q' + q + ' ' + cursor.getFullYear(),
                            hidden: false
                        });
                        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 3, 1);
                    }
                } else {
                    cursor = new Date(this.timelineStart.getFullYear(), 0, 1);
                    while (cursor <= end) {
                        labels.push({
                            x:      self.dateToX(cursor) + 4,
                            label:  String(cursor.getFullYear()),
                            hidden: false
                        });
                        cursor = new Date(cursor.getFullYear() + 1, 0, 1);
                    }
                }

                this.periodLabels = labels;
            },

            // ── Grid lines ────────────────────────────────────────────────

            _computeGridLines: function () {
                let lines  = [];
                let end    = this.timelineEnd;
                let self   = this;
                let cursor;

                if (this.zoom === 'weeks') {
                    // Grid line per week (Monday)
                    cursor = new Date(this.timelineStart);
                    let dow = cursor.getDay();
                    let offset = dow === 0 ? 1 : (dow === 1 ? 0 : 8 - dow);
                    cursor.setDate(cursor.getDate() + offset);
                    while (cursor <= end) {
                        lines.push(self.dateToX(cursor));
                        cursor = new Date(cursor.getTime() + 7 * DAY_MS);
                    }
                } else if (this.zoom === 'months') {
                    cursor = new Date(this.timelineStart.getFullYear(), this.timelineStart.getMonth(), 1);
                    while (cursor <= end) {
                        lines.push(self.dateToX(cursor));
                        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
                    }
                } else if (this.zoom === 'quarters') {
                    cursor = new Date(this.timelineStart.getFullYear(), Math.floor(this.timelineStart.getMonth() / 3) * 3, 1);
                    while (cursor <= end) {
                        lines.push(self.dateToX(cursor));
                        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 3, 1);
                    }
                } else {
                    cursor = new Date(this.timelineStart.getFullYear(), 0, 1);
                    while (cursor <= end) {
                        lines.push(self.dateToX(cursor));
                        cursor = new Date(cursor.getFullYear() + 1, 0, 1);
                    }
                }

                this.gridLines = lines;
            },

            // ── Today marker ──────────────────────────────────────────────

            _computeTodayX: function () {
                let today = new Date();
                if (today >= this.timelineStart && today <= this.timelineEnd) {
                    this.todayX = this.dateToX(today);
                } else {
                    this.todayX = -1;
                }
            },

            // ── Hide period labels that overlap Today badge ──────────────

            _markOverlappingLabels: function () {
                let tx = this.todayX;
                for (let i = 0; i < this.periodLabels.length; i++) {
                    this.periodLabels[i].hidden = (tx >= 0 && Math.abs(this.periodLabels[i].x - tx) < 50);
                }
            },

            // ── Milestone positions ───────────────────────────────────────

            _computeMilestonePositions: function () {
                let self = this;
                this.milestonePositions = this.milestones.map(function (m) {
                    let x = self.dateToX(m.date);
                    return {
                        id:    m.id,
                        x:     x,
                        label: m.label,
                        date:  m.date,
                        group: m.group || null
                    };
                }).filter(function (m) {
                    return m.x >= 0;
                });
            },

            // ── Visible rows ──────────────────────────────────────────────

            _computeVisibleRows: function () {
                let self = this;
                let rows = [];
                let filterText   = (self.filterText || '').toLowerCase();
                let filterStatus = self.filterStatus || '';

                // Filter tasks
                let filtered = self.tasks;
                if (filterText || filterStatus) {
                    filtered = self.tasks.filter(function (t) {
                        if (filterText && (t.name || '').toLowerCase().indexOf(filterText) === -1) return false;
                        if (filterStatus && t.status !== filterStatus) return false;
                        return true;
                    });
                }

                // Build group-to-tasks map
                let tasksByGroup = {};
                let ungrouped    = [];
                filtered.forEach(function (t) {
                    let gid = t.group;
                    if (gid) {
                        if (!tasksByGroup[gid]) tasksByGroup[gid] = [];
                        tasksByGroup[gid].push(t);
                    } else {
                        ungrouped.push(t);
                    }
                });

                // Emit groups in order, then their tasks
                self.groups.forEach(function (group) {
                    let isCollapsed = self.collapsedGroupIds.indexOf(group.id) > -1;
                    let groupTasks  = tasksByGroup[group.id] || [];

                    // Hide empty groups when filtering
                    if ((filterText || filterStatus) && groupTasks.length === 0) return;

                    rows.push({
                        type:      'group',
                        id:        group.id,
                        label:     group.label,
                        collapsed: isCollapsed,
                        taskCount: groupTasks.length
                    });
                    if (!isCollapsed) {
                        groupTasks.forEach(function (t) {
                            rows.push({ type: 'task', id: t.id, data: t });
                        });
                    }
                });

                // Ungrouped tasks at end
                ungrouped.forEach(function (t) {
                    rows.push({ type: 'task', id: t.id, data: t });
                });

                self.visibleRows = rows;
            },

            // ── Canvas height + row positions (precomputed O(n)) ──────────

            _computeCanvasHeight: function () {
                let rows = this.visibleRows;
                let positions = new Array(rows.length);
                let y = 0;
                for (let i = 0; i < rows.length; i++) {
                    positions[i] = y;
                    y += (rows[i].type === 'group') ? GROUP_HEIGHT : ROW_HEIGHT;
                }
                this._rowYPositions = positions;
                this.canvasHeight = Math.max(y, 200);
            },

            // ── Row Y position (O(1) lookup) ─────────────────────────────

            getRowY: function (index) {
                return this._rowYPositions[index] || 0;
            },

            /** Get Y center of a task row by task ID (for dependency arrows) */
            getTaskCenterY: function (taskId) {
                let rows = this.visibleRows;
                for (let i = 0; i < rows.length; i++) {
                    if (rows[i].type === 'task' && rows[i].id === taskId) {
                        return this._rowYPositions[i] + ROW_HEIGHT / 2;
                    }
                }
                return -1;
            },

            // ── Dependency paths ──────────────────────────────────────────

            _computeDependencyPaths: function () {
                let self = this;
                let feats = self.config.features;
                // Support both config.features.dependencies flag and inline deps
                if (feats && feats.dependencies === false && self._depPairs.length === 0) {
                    self.dependencyPaths = [];
                    return;
                }

                let paths = [];
                let taskMap = {};
                self.tasks.forEach(function (t) { taskMap[t.id] = t; });

                self._depPairs.forEach(function (pair) {
                    let srcId = pair[0];
                    let tgtId = pair[1];
                    let src   = taskMap[srcId];
                    let tgt   = taskMap[tgtId];
                    if (!src || !tgt) return;

                    let srcY = self.getTaskCenterY(srcId);
                    let tgtY = self.getTaskCenterY(tgtId);
                    if (srcY < 0 || tgtY < 0) return; // hidden (collapsed group)

                    let x1 = self.dateToX(src.end_date);
                    let x2 = self.dateToX(tgt.start_date);

                    // Bezier curve
                    let midX = x1 + (x2 - x1) / 2;
                    let d = 'M ' + x1 + ' ' + srcY +
                            ' C ' + midX + ' ' + srcY +
                            ', ' + midX + ' ' + tgtY +
                            ', ' + x2 + ' ' + tgtY;

                    // Arrowhead points
                    let arrow = x2 + ',' + (tgtY - 4) + ' ' +
                                (x2 + 7) + ',' + tgtY + ' ' +
                                x2 + ',' + (tgtY + 4);

                    paths.push({
                        id:    srcId + '-' + tgtId,
                        d:     d,
                        arrow: arrow
                    });
                });

                self.dependencyPaths = paths;
            },

            // ═══════════════════════════════════════════════════════════════
            // GROUP OPERATIONS
            // ═══════════════════════════════════════════════════════════════

            toggleGroup: function (groupId) {
                let idx = this.collapsedGroupIds.indexOf(groupId);
                if (idx > -1) {
                    this.collapsedGroupIds.splice(idx, 1);
                } else {
                    this.collapsedGroupIds.push(groupId);
                }
                this.allCollapsed = this.collapsedGroupIds.length === this.groups.length;
                this._computeVisibleRows();
                this._computeCanvasHeight();
                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._computeDependencyPaths(); });
                }
            },

            collapseAll: function () {
                this.collapsedGroupIds = this.groups.map(function (g) { return g.id; });
                this.allCollapsed = true;
                this._computeVisibleRows();
                this._computeCanvasHeight();
                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._computeDependencyPaths(); });
                }
            },

            expandAll: function () {
                this.collapsedGroupIds = [];
                this.allCollapsed = false;
                this._computeVisibleRows();
                this._computeCanvasHeight();
                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._computeDependencyPaths(); });
                }
            },

            toggleAllGroups: function () {
                if (this.allCollapsed) {
                    this.expandAll();
                } else {
                    this.collapseAll();
                }
            },

            // ═══════════════════════════════════════════════════════════════
            // TASK SELECTION
            // ═══════════════════════════════════════════════════════════════

            selectTask: function (taskId) {
                if (this.selectedTaskId === taskId) {
                    this.selectedTaskId = null;
                } else {
                    this.selectedTaskId = taskId;
                    this.hideTooltip();
                    if (typeof this._onTaskClick === 'function') {
                        let task = this.getTaskById(taskId);
                        if (task) this._onTaskClick(task);
                    }
                }
            },

            selectTaskById: function (id) {
                this.selectedTaskId = id;
                this.hideTooltip();
            },

            closeDetailPanel: function () {
                this.selectedTaskId = null;
            },

            getSelectedTask: function () {
                return this.getTaskById(this.selectedTaskId);
            },

            getTaskById: function (id) {
                if (!id) return null;
                for (let i = 0; i < this.tasks.length; i++) {
                    if (this.tasks[i].id === id) return this.tasks[i];
                }
                return null;
            },

            // ═══════════════════════════════════════════════════════════════
            // ZOOM
            // ═══════════════════════════════════════════════════════════════

            setZoom: function (level) {
                this.zoom = level;
                this._recompute();
                try {
                    localStorage.setItem('archie_gantt_zoom_' + this._storageKey, level);
                } catch (e) { /* quota or private browsing */ }
                let self = this;
                if (typeof self.$nextTick === 'function') {
                    self.$nextTick(function () { self._scrollToToday(); });
                }
            },

            _restoreZoom: function () {
                try {
                    let saved = localStorage.getItem('archie_gantt_zoom_' + this._storageKey);
                    if (saved && ['weeks', 'months', 'quarters', 'years'].indexOf(saved) > -1) {
                        this.zoom = saved;
                    }
                } catch (e) { /* ignore */ }
            },

            // ═══════════════════════════════════════════════════════════════
            // SCROLL
            // ═══════════════════════════════════════════════════════════════

            syncScroll: function (source) {
                let labelEl    = this.$refs.labelScroll;
                let timelineEl = this.$refs.timelineScroll;
                let headerEl   = this.$refs.timelineHeader;

                if (!labelEl || !timelineEl) return;

                if (source === 'label') {
                    timelineEl.scrollTop = labelEl.scrollTop;
                } else {
                    labelEl.scrollTop = timelineEl.scrollTop;
                    if (headerEl) headerEl.scrollLeft = timelineEl.scrollLeft;
                }
            },

            _scrollToToday: function () {
                if (this.todayX < 0) return;
                let self = this;
                requestAnimationFrame(function () { self.jumpToToday(); });
            },

            jumpToToday: function () {
                if (this.todayX < 0) return;
                let el = this.$refs.timelineScroll;
                if (!el) return;
                el.scrollLeft = Math.max(0, this.todayX - el.clientWidth / 3);
                if (this.$refs.timelineHeader) {
                    this.$refs.timelineHeader.scrollLeft = el.scrollLeft;
                }
            },

            // ═══════════════════════════════════════════════════════════════
            // TOOLTIP
            // ═══════════════════════════════════════════════════════════════

            showTooltip: function (taskId, event) {
                if (this.selectedTaskId === taskId) return;
                this.hoveredTaskId = taskId;
                if (event) {
                    this.tooltipPos = {
                        x: Math.min(event.clientX + 12, window.innerWidth - 300),
                        y: Math.min(event.clientY - 10, window.innerHeight - 200)
                    };
                }
            },

            moveTooltip: function (event) {
                if (!this.hoveredTaskId) return;
                this.tooltipPos = {
                    x: Math.min(event.clientX + 12, window.innerWidth - 300),
                    y: Math.min(event.clientY - 10, window.innerHeight - 200)
                };
            },

            hideTooltip: function () {
                this.hoveredTaskId = null;
            },

            getTooltipTask: function () {
                return this.getTaskById(this.hoveredTaskId);
            },

            // ═══════════════════════════════════════════════════════════════
            // FILTERING
            // ═══════════════════════════════════════════════════════════════

            setFilterText: function (text) {
                this.filterText = text;
                this._recompute();
            },

            setFilterStatus: function (status) {
                this.filterStatus = status;
                this._recompute();
            },

            clearFilters: function () {
                this.filterText   = '';
                this.filterStatus = '';
                this._recompute();
            },

            // ═══════════════════════════════════════════════════════════════
            // CSV EXPORT
            // ═══════════════════════════════════════════════════════════════

            exportCSV: function () {
                let self = this;
                let headers = ['Name', 'Group', 'Status', 'Start Date', 'End Date', 'Progress (%)'];
                let metaKeys  = [];
                let metaLabels = [];

                // Add metadata columns from config
                let fields = self._metadataFields || (self.config && self.config.detailFields) || [];
                fields.forEach(function (f) {
                    metaKeys.push(f.key);
                    metaLabels.push(f.label || f.key);
                });

                let allHeaders = headers.concat(metaLabels);

                // Get group label lookup
                let groupMap = {};
                self.groups.forEach(function (g) { groupMap[g.id] = g.label; });

                let rows = self.tasks.map(function (t) {
                    let base = [
                        t.name || '',
                        groupMap[t.group] || t.group || '',
                        (t.status || '').replace(/_/g, ' '),
                        t.start_date || '',
                        t.end_date || '',
                        t.progress != null ? String(t.progress) : ''
                    ];
                    let meta = metaKeys.map(function (k) {
                        let val = _resolveField(t, k);
                        return val != null ? String(val) : '';
                    });
                    return base.concat(meta);
                });

                let csv = [
                    allHeaders.map(function (h) { return '"' + h.replace(/"/g, '""') + '"'; }).join(',')
                ].concat(rows.map(function (r) {
                    return r.map(function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
                })).join('\n');

                let blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                let url = URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = 'gantt-export-' + new Date().toISOString().split('T')[0] + '.csv';
                a.click();
                URL.revokeObjectURL(url);
            },

            // ═══════════════════════════════════════════════════════════════
            // KEYBOARD NAVIGATION
            // ═══════════════════════════════════════════════════════════════

            _handleKeyDown: function (event) {
                let key = event.key;
                let rows = this.visibleRows;
                if (!rows.length) return;

                if (key === 'ArrowDown' || key === 'ArrowUp') {
                    event.preventDefault();
                    let dir = key === 'ArrowDown' ? 1 : -1;
                    let next = this._focusedRowIndex + dir;
                    if (next < 0) next = 0;
                    if (next >= rows.length) next = rows.length - 1;
                    this._focusedRowIndex = next;
                    let row = rows[next];
                    this.ariaAnnouncement = row.type === 'group'
                        ? row.label + ', group, ' + row.taskCount + ' items' + (row.collapsed ? ', collapsed' : ', expanded')
                        : (row.data ? row.data.name : '');
                    return;
                }

                if (key === 'Enter' || key === ' ') {
                    event.preventDefault();
                    let idx = this._focusedRowIndex;
                    if (idx < 0 || idx >= rows.length) return;
                    let focused = rows[idx];
                    if (focused.type === 'group') {
                        this.toggleGroup(focused.id);
                    } else if (focused.type === 'task') {
                        this.selectTask(focused.id);
                    }
                    return;
                }

                if (key === 'Escape') {
                    if (this.crudFormOpen) {
                        event.preventDefault();
                        this.closeCrudForm();
                    } else if (this.selectedTaskId) {
                        event.preventDefault();
                        this.closeDetailPanel();
                    }
                    return;
                }
            },

            getFocusedRowIndex: function () {
                return this._focusedRowIndex;
            },

            setFocusedRowIndex: function (i) {
                this._focusedRowIndex = i;
            },

            // ═══════════════════════════════════════════════════════════════
            // FIELD RESOLVER
            // ═══════════════════════════════════════════════════════════════

            resolveField: function (task, dotPath) {
                return _resolveField(task, dotPath);
            },

            // ═══════════════════════════════════════════════════════════════
            // CRUD METHODS (kept from v1 for backward compat)
            // ═══════════════════════════════════════════════════════════════

            hasCrud: function () { return !!this._crudEndpoint; },
            hasSecondaryCrud: function () { return !!this._secondaryCrudEndpoint; },
            getSecondaryCrudLabel: function () { return this._secondaryCrudLabel; },

            getAvailableStatuses: function () {
                if (this.config && this.config.statusColors) {
                    return Object.keys(this.config.statusColors);
                }
                return ['identified', 'planned', 'in_progress', 'completed'];
            },

            openCreateForm: function () {
                this.crudEditingId = null;
                this.crudIsSecondary = false;
                this.crudParentId = null;
                this.crudForm = { name: '', status: 'identified', priority: 'medium', start_date: '', end_date: '', description: '' };
                this.crudError = '';
                this.crudFormOpen = true;
            },

            openEditForm: function (task) {
                if (!task) return;
                this.crudEditingId = task.id;
                this.crudIsSecondary = false;
                this.crudParentId = null;
                this.crudForm = {
                    name:       task.name || '',
                    status:     task.status || 'identified',
                    priority:   (task.meta && task.meta.priority) || 'medium',
                    start_date: task.start_date ? task.start_date.substring(0, 10) : '',
                    end_date:   task.end_date ? task.end_date.substring(0, 10) : '',
                    description: (task.meta && task.meta.description) || ''
                };
                this.crudError = '';
                this.crudFormOpen = true;
            },

            openSecondaryCreateForm: function (parentTask) {
                if (!parentTask) return;
                this.crudEditingId = null;
                this.crudIsSecondary = true;
                this.crudParentId = parentTask.id;
                this.crudForm = {
                    name: '', status: 'planned', priority: 'medium',
                    start_date: parentTask.start_date ? parentTask.start_date.substring(0, 10) : '',
                    end_date:   parentTask.end_date ? parentTask.end_date.substring(0, 10) : '',
                    description: ''
                };
                this.crudError = '';
                this.crudFormOpen = true;
            },

            closeCrudForm: function () {
                this.crudFormOpen = false;
                this.crudEditingId = null;
                this.crudIsSecondary = false;
                this.crudParentId = null;
                this.crudError = '';
            },

            confirmDelete: function (task) {
                if (!task || !confirm('Delete "' + task.name + '"? This cannot be undone.')) return;
                let self = this;
                _fetch(self._crudEndpoint + '/' + task.id, { method: 'DELETE' })
                    .then(function (data) {
                        if (data && data.success) {
                            self.selectedTaskId = null;
                            self.reload();
                        } else {
                            Platform.toast.error('Delete failed: ' + ((data && data.error) || 'Unknown error'));
                        }
                    }).catch(function (err) {
                        let msg = (err && err.data && err.data.error) || (err && err.message) || 'Network error';
                        Platform.toast.error('Delete failed: ' + msg);
                    });
            },

            submitCrudForm: function () {
                let self = this;
                if (!self.crudForm.name.trim()) return;
                self.crudSubmitting = true;
                self.crudError = '';

                let url, method;
                if (self.crudIsSecondary && self.crudParentId) {
                    url = self._secondaryCrudEndpoint.replace('{id}', self.crudParentId);
                    method = 'POST';
                } else if (self.crudEditingId) {
                    url = self._crudEndpoint + '/' + self.crudEditingId;
                    method = 'PUT';
                } else {
                    url = self._crudEndpoint;
                    method = 'POST';
                }

                _fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(self.crudForm)
                }).then(function (data) {
                    self.crudSubmitting = false;
                    if (data && data.success) {
                        self.closeCrudForm();
                        self.reload();
                    } else {
                        self.crudError = (data && data.error) || 'Failed to save';
                    }
                }).catch(function (err) {
                    self.crudSubmitting = false;
                    self.crudError = (err && err.data && err.data.error) || (err && err.message) || 'Network error';
                });
            }
        };
    }

    // ── Public API ────────────────────────────────────────────────────────────
    let ganttModule = {
        alpineMixin:        alpineMixin,
        ROW_HEIGHT:         ROW_HEIGHT,
        GROUP_HEIGHT:       GROUP_HEIGHT,
        LABEL_WIDTH:        LABEL_WIDTH,
        DETAIL_PANEL_WIDTH: DETAIL_PANEL_WIDTH,
        HEADER_HEIGHT:      HEADER_HEIGHT
    };

    global.Platform.register('gantt', ganttModule);

}(window));
