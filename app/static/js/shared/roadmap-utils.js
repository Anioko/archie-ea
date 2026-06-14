/**
 * Shared Roadmap Utilities
 *
 * Reusable functions for timeline rendering, bar positioning, and export functionality
 * Used by: capability-roadmap, archimate-roadmap, hybrid-roadmap, application roadmaps
 *
 * @version 1.0.0
 */

const RoadmapUtils = {
    /**
     * Get column width based on timeline display mode
     * @param {string} displayMode - 'weeks', 'months', 'quarters', or 'years'
     * @returns {number} Column width in pixels
     */
    getColumnWidth(displayMode) {
        switch (displayMode) {
            case 'weeks': return 45;     // Compact for many weeks
            case 'months': return 80;
            case 'quarters': return 120;
            case 'years': return 200;    // Wider for year view
            default: return 80;
        }
    },

    /**
     * Generate timeline periods based on start/end dates and display mode
     * @param {Date} startDate - Timeline start date
     * @param {Date} endDate - Timeline end date
     * @param {string} displayMode - 'weeks', 'months', 'quarters', or 'years'
     * @returns {Array} Array of period objects with {label, start, end}
     */
    generateTimelinePeriods(startDate, endDate, displayMode = 'months') {
        const periods = [];
        const start = new Date(startDate);
        const end = new Date(endDate);

        if (displayMode === 'months') {
            const current = new Date(start.getFullYear(), start.getMonth(), 1);
            while (current <= end) {
                periods.push({
                    label: current.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
                    start: new Date(current),
                    end: new Date(current.getFullYear(), current.getMonth() + 1, 0)
                });
                current.setMonth(current.getMonth() + 1);
            }
        } else if (displayMode === 'weeks') {
            let current = new Date(start);
            // Set to start of week (Monday)
            current.setDate(current.getDate() - ((current.getDay() + 6) % 7));
            while (current <= end) {
                let weekStart = new Date(current);
                let weekEnd = new Date(current);
                weekEnd.setDate(weekEnd.getDate() + 6);
                if (weekEnd > end) weekEnd = new Date(end);

                // Get ISO week number
                const tempDate = new Date(weekStart);
                tempDate.setHours(0, 0, 0, 0);
                tempDate.setDate(tempDate.getDate() + 3 - (tempDate.getDay() + 6) % 7);
                const week1 = new Date(tempDate.getFullYear(), 0, 4);
                const weekNum = 1 + Math.round(((tempDate - week1) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7);

                // Compact label: "W1 '26" or show month marker at start of each month
                const isFirstWeekOfMonth = weekStart.getDate() <= 7;
                const monthLabel = isFirstWeekOfMonth ? weekStart.toLocaleDateString('en-US', { month: 'short' }) + ' ' : '';
                const yearSuffix = weekNum === 1 ? ` '${weekStart.getFullYear().toString().slice(-2)}` : '';

                periods.push({
                    label: `${monthLabel}W${weekNum}${yearSuffix}`,
                    start: weekStart,
                    end: weekEnd
                });
                current.setDate(current.getDate() + 7);
            }
        } else if (displayMode === 'quarters') {
            const current = new Date(start);
            current.setDate(1);
            current.setMonth(Math.floor(current.getMonth() / 3) * 3);

            while (current <= end) {
                const quarterStart = new Date(current);
                const quarterEnd = new Date(current.getFullYear(), current.getMonth() + 3, 0);
                periods.push({
                    label: `Q${Math.floor(current.getMonth() / 3) + 1} ${current.getFullYear()}`,
                    start: quarterStart,
                    end: quarterEnd
                });
                current.setMonth(current.getMonth() + 3);
            }
        } else if (displayMode === 'years') {
            const current = new Date(start);
            current.setMonth(0, 1);

            while (current <= end) {
                periods.push({
                    label: current.getFullYear().toString(),
                    start: new Date(current),
                    end: new Date(current.getFullYear(), 11, 31)
                });
                current.setFullYear(current.getFullYear() + 1);
            }
        }

        return periods;
    },

    /**
     * Calculate bar position and width based on item dates and timeline periods
     * @param {Object} item - Item with start_date and end_date properties
     * @param {Array} timelinePeriods - Array of period objects
     * @param {string} displayMode - 'months', 'quarters', or 'years'
     * @returns {Object} CSS style object with left, width, top, transform
     */
    getBarStyle(item, timelinePeriods, displayMode = 'months') {
        const startDate = new Date(item.start_date);
        const endDate = new Date(item.end_date || item.target_date);

        // Validate dates
        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime()) || timelinePeriods.length === 0) {
            return {
                left: '0px',
                width: '100px',
                top: '50%',
                transform: 'translateY(-50%)'
            };
        }

        const columnWidth = this.getColumnWidth(displayMode);

        // Find which period the item starts and ends in
        let startPeriodIndex = 0;
        let endPeriodIndex = timelinePeriods.length - 1;

        for (let i = 0; i < timelinePeriods.length; i++) {
            const period = timelinePeriods[i];
            if (startDate >= period.start && startDate <= period.end) {
                startPeriodIndex = i;
            }
            if (endDate >= period.start && endDate <= period.end) {
                endPeriodIndex = i;
                break;
            }
        }

        // Calculate position and width
        const barLeft = startPeriodIndex * columnWidth;
        const barWidth = Math.max((endPeriodIndex - startPeriodIndex + 1) * columnWidth, columnWidth);

        return {
            left: `${barLeft}px`,
            width: `${barWidth}px`,
            top: '50%',
            transform: 'translateY(-50%)'
        };
    },

    /**
     * Get color based on priority/importance level
     * @param {string} priority - 'critical', 'high', 'medium', or 'low'
     * @returns {string} Tailwind CSS class or hex color
     */
    getPriorityColor(priority) {
        const colors = {
            critical: '#ef4444', // red
            high: '#f97316',     // orange
            medium: '#eab308',   // yellow
            low: '#22c55e'       // green
        };
        return colors[priority?.toLowerCase()] || '#6b7280';
    },

    /**
     * Get Tailwind CSS class for priority badge
     * @param {string} priority - Priority level
     * @returns {string} Tailwind CSS classes
     */
    getPriorityBadgeClass(priority) {
        const classes = {
            critical: 'bg-destructive/10 text-red-800',
            high: 'bg-orange-100 text-orange-800',
            medium: 'bg-amber-500/10 text-yellow-800',
            low: 'bg-emerald-500/10 text-green-800'
        };
        return classes[priority?.toLowerCase()] || 'bg-muted text-foreground';
    },

    /**
     * Generate timeline header HTML
     * @param {Array} timelinePeriods - Array of period objects
     * @param {string} displayMode - Display mode for column width
     * @returns {string} HTML string for timeline header
     */
    generateTimelineHeaderHTML(timelinePeriods, displayMode = 'months') {
        const columnWidth = this.getColumnWidth(displayMode);
        return timelinePeriods.map(period =>
            `<div style="width: ${columnWidth}px; min-width: ${columnWidth}px; text-align: center; padding: 8px 4px; font-size: 12px; font-weight: 500; color: #374151; border-right: 1px solid #e5e7eb; background: #f9fafb;">${period.label}</div>`
        ).join('');
    },

    /**
     * Generate grid columns HTML for timeline
     * @param {Array} timelinePeriods - Array of period objects
     * @param {string} displayMode - Display mode for column width
     * @returns {string} HTML string for grid columns
     */
    generateGridColumnsHTML(timelinePeriods, displayMode = 'months') {
        const columnWidth = this.getColumnWidth(displayMode);
        return timelinePeriods.map(() =>
            `<div style="width: ${columnWidth}px; min-width: ${columnWidth}px; border-right: 1px solid #f3f4f6;"></div>`
        ).join('');
    },

    /**
     * Export timeline to image (PNG or JPG)
     * @param {string} format - 'png' or 'jpg'
     * @param {Object} config - Export configuration
     * @param {Array} items - Items to export (work packages, capabilities, etc.)
     * @param {Array} timelinePeriods - Timeline periods
     * @param {string} displayMode - Display mode
     * @param {string} title - Export title
     * @param {Function} getItemColor - Function to get item color
     */
    async exportToImage(format, config = {}) {
        const {
            items = [],
            timelinePeriods = [],
            displayMode = 'months',
            title = 'Roadmap Export',
            subtitle = '',
            getItemColor = () => '#3b82f6',
            filename = 'roadmap-export'
        } = config;

        // Create export container
        const exportContainer = document.createElement('div');
        exportContainer.style.position = 'absolute';
        exportContainer.style.left = '-9999px';
        exportContainer.style.top = '0';
        document.body.appendChild(exportContainer);

        // Show loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999;';
        safeHTML(loadingDiv, '<div style="background: white; padding: 24px; border-radius: 8px; text-align: center;"><div style="border: 3px solid #e5e7eb; border-top: 3px solid #3b82f6; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 12px;"></div><p style="color: #374151; font-size: 14px;">Generating export...</p></div><style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>');
        document.body.appendChild(loadingDiv);

        try {
            const columnWidth = this.getColumnWidth(displayMode);
            const rowHeight = 60;
            const totalWidth = Math.max(timelinePeriods.length * columnWidth + 300, 1200);

            // Build export HTML
            const exportHTML = `
                <div style="width: ${totalWidth}px; background: white; padding: 30px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <!-- Title -->
                    <div style="margin-bottom: 24px; border-bottom: 2px solid #e5e7eb; padding-bottom: 16px;">
                        <h1 style="font-size: 24px; font-weight: 700; color: #111827; margin: 0 0 8px 0;">${title}</h1>
                        ${subtitle ? `<p style="font-size: 14px; color: #6b7280; margin: 0;">${subtitle}</p>` : ''}
                        <p style="font-size: 12px; color: #9ca3af; margin-top: 8px;">Generated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
                    </div>

                    <!-- Timeline -->
                    <div style="display: flex; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                        <!-- Labels Column -->
                        <div style="width: 280px; min-width: 280px; background: #f9fafb; border-right: 2px solid #e5e7eb;">
                            <div style="height: 44px; padding: 12px 16px; font-weight: 600; color: #374151; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center;">Item Name</div>
                            ${items.map(item => `
                                <div style="height: ${rowHeight}px; padding: 8px 16px; border-bottom: 1px solid #f3f4f6; display: flex; align-items: center;">
                                    <div>
                                        <div style="font-weight: 500; color: #111827; font-size: 13px; margin-bottom: 2px;">${item.name}</div>
                                        <div style="font-size: 11px; color: #6b7280;">${item.domain_name || item.capability_name || ''}</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>

                        <!-- Timeline Grid -->
                        <div style="flex: 1; overflow: hidden;">
                            <!-- Header -->
                            <div style="display: flex; border-bottom: 1px solid #e5e7eb; height: 44px;">
                                ${this.generateTimelineHeaderHTML(timelinePeriods, displayMode)}
                            </div>

                            <!-- Rows -->
                            ${items.map(item => {
                                const barStyle = this.getBarStyle(item, timelinePeriods, displayMode);
                                const barLeft = parseInt(barStyle.left);
                                const barWidth = parseInt(barStyle.width);
                                const itemColor = typeof getItemColor === 'function' ? getItemColor(item) : getItemColor;

                                return `
                                    <div style="height: ${rowHeight}px; display: flex; position: relative;">
                                        ${this.generateGridColumnsHTML(timelinePeriods, displayMode)}
                                        <!-- Bar -->
                                        <div style="position: absolute; left: ${barLeft}px; top: 50%; transform: translateY(-50%); width: ${barWidth}px; height: 44px; background: linear-gradient(135deg, ${itemColor} 0%, ${this.darkenColor(itemColor, 15)} 100%); border-radius: 6px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">
                                            <span style="color: white; font-size: 18px; font-weight: 700; padding: 0 12px; white-space: nowrap; text-shadow: 0 1px 3px rgba(0,0,0,0.3);">${item.name}</span>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>

                    <!-- Legend -->
                    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; display: flex; align-items: center; gap: 24px; flex-wrap: wrap;">
                        <span style="font-size: 12px; font-weight: 600; color: #374151;">Priority:</span>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: #ef4444;"></div>
                            <span style="font-size: 12px; color: #6b7280;">Critical</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: #f97316;"></div>
                            <span style="font-size: 12px; color: #6b7280;">High</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: #eab308;"></div>
                            <span style="font-size: 12px; color: #6b7280;">Medium</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: #22c55e;"></div>
                            <span style="font-size: 12px; color: #6b7280;">Low</span>
                        </div>
                    </div>
                </div>
            `;

            safeHTML(exportContainer, exportHTML);

            // Wait for render
            await new Promise(resolve => setTimeout(resolve, 100));

            // Capture with html2canvas
            const canvas = await html2canvas(exportContainer.firstElementChild, {
                backgroundColor: '#ffffff',
                scale: 2,
                useCORS: true,
                logging: false
            });

            // Cleanup
            document.body.removeChild(exportContainer);

            // Convert and download
            const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
            const quality = format === 'png' ? 1.0 : 0.92;
            const dataUrl = canvas.toDataURL(mimeType, quality);

            const link = document.createElement('a');
            link.download = `${filename}_${new Date().toISOString().split('T')[0]}.${format}`;
            link.href = dataUrl;
            link.click();

        } catch (error) {
            console.error('Export error:', error);
            toast.error('Export Failed', {
                description: 'Failed to export image. Please try again.',
                duration: 5000
            });
        } finally {
            document.body.removeChild(loadingDiv);
        }
    },

    /**
     * Export data to CSV
     * @param {Array} items - Items to export
     * @param {Array} columns - Column definitions [{key, label}]
     * @param {string} filename - Filename without extension
     */
    exportToCSV(items, columns, filename = 'export') {
        const headers = columns.map(col => col.label);
        const rows = items.map(item =>
            columns.map(col => {
                let value = item[col.key];
                if (value === null || value === undefined) value = '';
                if (typeof value === 'string' && value.includes(',')) {
                    value = `"${value.replace(/"/g, '""')}"`;
                }
                return value;
            })
        );

        const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        window.URL.revokeObjectURL(url);
    },

    /**
     * Darken a hex color by a percentage
     * @param {string} color - Hex color (e.g., '#3b82f6')
     * @param {number} percent - Percentage to darken (0-100)
     * @returns {string} Darkened hex color
     */
    darkenColor(color, percent) {
        const num = parseInt(color.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.max((num >> 16) - amt, 0);
        const G = Math.max((num >> 8 & 0x00FF) - amt, 0);
        const B = Math.max((num & 0x0000FF) - amt, 0);
        return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    },

    /**
     * Format date for display
     * @param {string|Date} date - Date to format
     * @param {string} format - 'short', 'medium', or 'long'
     * @returns {string} Formatted date string
     */
    formatDate(date, format = 'medium') {
        if (!date) return '';
        const d = new Date(date);
        if (isNaN(d.getTime())) return '';

        const options = {
            short: { month: 'short', year: '2-digit' },
            medium: { month: 'short', day: 'numeric', year: 'numeric' },
            long: { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' }
        };

        return d.toLocaleDateString('en-US', options[format] || options.medium);
    },

    /**
     * Calculate duration between two dates
     * @param {string|Date} startDate - Start date
     * @param {string|Date} endDate - End date
     * @returns {string} Human-readable duration
     */
    calculateDuration(startDate, endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));

        if (days <= 0) return 'Invalid';
        if (days === 1) return '1 day';
        if (days < 30) return `${days} days`;
        if (days < 365) {
            const months = Math.floor(days / 30);
            return months === 1 ? '1 month' : `${months} months`;
        }
        const years = Math.floor(days / 365);
        const remainingMonths = Math.floor((days % 365) / 30);
        if (remainingMonths === 0) {
            return years === 1 ? '1 year' : `${years} years`;
        }
        return `${years}y ${remainingMonths}m`;
    }
};

// Make available globally
if (typeof window !== 'undefined') {
    window.RoadmapUtils = RoadmapUtils;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RoadmapUtils;
}
