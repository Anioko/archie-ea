/**
 * ArchiMate 3.2 Implementation & Migration Roadmap
 * Extracted from archimate_roadmap/archimate_roadmap.html
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

function archimateRoadmapManager() {
    return {
        selectedLayer: '',
        selectedType: '',
        showAddModal: false,
        editingWorkPackage: null,
        workPackages: [],
        filteredWorkPackages: [],
        timelineDisplay: 'months', // New property for timeline display
        timelinePeriods: [], // New property for calculated periods
        formData: {
            name: '',
            description: '',
            archimate_element: '',
            archimate_layer: 'Business',
            work_package_type: 'strategic',
            assigned_to: '',
            status: 'planned',
            start_date: '',
            target_date: '',
            progress_percentage: 0,
            estimated_effort_hours: 0
        },

        // Generate roadmap state
        showGenerateModal: false,
        availableGaps: [],
        selectedGapIds: [],
        generatePreviewMode: true,
        generatePriorityFilter: '',
        generateTimelineMonths: '18',
        generateIncludePlateaus: true,
        generatePreviewResult: null,
        generateStatus: null,

        async initializeRoadmap() {
            // Get timeline dates from data attributes with fallback
            let startDate = this.$el.dataset.startDate || '2024-01-01';
            let endDate = this.$el.dataset.endDate || '2028-12-31';

            // Store in component for later use
            this.timelineStart = new Date(startDate);
            this.timelineEnd = new Date(endDate);

            // Calculate timeline periods based on display mode
            this.updateTimelineDisplay();

            await this.loadWorkPackages();
            await this.loadAvailableGaps();
            this.filterWorkPackages();
        },

        // Load available gaps for roadmap generation
        async loadAvailableGaps() {
            try {
                let response = await fetch('/capability-map/api/roadmap/archimate-gaps');
                if (response.ok) {
                    let data = await response.json();
                    this.availableGaps = data.gaps || [];
                } else {
                    console.error('Failed to load gaps');
                    this.availableGaps = [];
                }
            } catch (error) {
                console.error('Error loading gaps:', error);
                this.availableGaps = [];
            }
        },

        // Select all gaps
        selectAllGaps() {
            this.selectedGapIds = this.availableGaps.map(function(g) { return g.id; });
        },

        // Preview roadmap without creating
        async previewRoadmap() {
            this.generateStatus = { type: 'info', message: 'Generating preview...' };
            this.generatePreviewResult = null;

            try {
                let response = await fetch('/api/roadmap/archimate/preview-roadmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        gap_ids: this.selectedGapIds.length > 0 ? this.selectedGapIds : null
                    })
                });

                let data = await response.json();

                if (response.ok && data.success) {
                    this.generatePreviewResult = data.preview;
                    this.generateStatus = { type: 'success', message: 'Preview generated successfully' };

                    // Refresh Lucide icons
                    if (typeof lucide !== 'undefined') {
                        this.$nextTick(function() { lucide.createIcons(); });
                    }
                } else {
                    this.generateStatus = { type: 'error', message: data.error || 'Failed to generate preview' };
                }
            } catch (error) {
                console.error('Preview error:', error);
                this.generateStatus = { type: 'error', message: 'Error generating preview: ' + error.message };
            }
        },

        // Generate actual roadmap
        async generateRoadmap() {
            this.generateStatus = { type: 'info', message: 'Generating roadmap... This may take a moment.' };

            try {
                let response = await fetch('/api/roadmap/archimate/generate-roadmap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        gap_ids: this.selectedGapIds.length > 0 ? this.selectedGapIds : null,
                        priority_filter: this.generatePriorityFilter || null,
                        include_plateaus: this.generateIncludePlateaus,
                        timeline_months: parseInt(this.generateTimelineMonths)
                    })
                });

                let data = await response.json();

                if (response.ok && data.success) {
                    let roadmap = data.roadmap;
                    let stats = roadmap.statistics;

                    this.generateStatus = {
                        type: 'success',
                        message: 'Roadmap generated! Created ' + stats.total_work_packages + ' work packages from ' + stats.total_gaps + ' gaps.'
                    };

                    // Refresh work packages
                    await this.loadWorkPackages();
                    this.filterWorkPackages();

                    // Refresh Lucide icons
                    if (typeof lucide !== 'undefined') {
                        this.$nextTick(function() { lucide.createIcons(); });
                    }

                    // Close modal after delay
                    let self = this;
                    setTimeout(function() {
                        self.showGenerateModal = false;
                        self.generateStatus = null;
                        self.generatePreviewResult = null;
                        self.selectedGapIds = [];
                    }, 3000);
                } else {
                    this.generateStatus = { type: 'error', message: data.error || 'Failed to generate roadmap' };
                }
            } catch (error) {
                console.error('Generate roadmap error:', error);
                this.generateStatus = { type: 'error', message: 'Error generating roadmap: ' + error.message };
            }
        },

        updateTimelineDisplay() {
            let start = new Date(this.timelineStart);
            let end = new Date(this.timelineEnd);
            this.timelinePeriods = [];



            if (this.timelineDisplay === 'months') {
                let current = new Date(start);
                while (current <= end) {
                    this.timelinePeriods.push({
                        label: current.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
                        start: new Date(current),
                        end: new Date(current.getFullYear(), current.getMonth() + 1, 0)
                    });
                    current.setMonth(current.getMonth() + 1);
                }
            } else if (this.timelineDisplay === 'quarters') {
                let current = new Date(start);
                current.setDate(1);
                current.setMonth(Math.floor(current.getMonth() / 3) * 3);

                while (current <= end) {
                    let quarterStart = new Date(current);
                    let quarterEnd = new Date(current.getFullYear(), current.getMonth() + 3, 0);

                    this.timelinePeriods.push({
                        label: 'Q' + (Math.floor(current.getMonth() / 3) + 1) + ' ' + current.getFullYear(),
                        start: quarterStart,
                        end: quarterEnd
                    });

                    current.setMonth(current.getMonth() + 3);
                }
            } else if (this.timelineDisplay === 'years') {
                let current = new Date(start);
                current.setMonth(0, 1);

                while (current <= end) {
                    this.timelinePeriods.push({
                        label: current.getFullYear().toString(),
                        start: new Date(current),
                        end: new Date(current.getFullYear(), 11, 31)
                    });
                    current.setFullYear(current.getFullYear() + 1);
                }
            }



            // Force DOM updates after timeline periods are calculated
            this.$nextTick(function() {

                this.updateTimelineHeader();
                this.updateTimelineGrid();
                // Re-calculate work package positions for new timeline
                this.$nextTick(function() {
                    this.updateWorkPackagePositions();
                }.bind(this));
            }.bind(this));
        },

        updateTimelineHeader() {
            let headerElement = document.getElementById('archimate-timeline-header');


            if (headerElement && this.timelinePeriods.length > 0) {
                let headerHTML = this.timelinePeriods.map(function(period) {
                    return '<div class="flex-1 p-2 text-center text-xs border-r border-border bg-muted">' + period.label + '</div>';
                }).join('');


                safeHTML(headerElement, headerHTML);
            } else {

            }
        },

        updateTimelineGrid() {
            // Update all timeline grid instances with unique IDs
            this.filteredWorkPackages.forEach(function(workPackage) {
                let gridElement = document.getElementById('archimate-timeline-grid-' + workPackage.id);
                if (gridElement && this.timelinePeriods.length > 0) {
                    let gridHTML = this.timelinePeriods.map(function() {
                        return '<div class="flex-1 border-r border-border/20 flex-shrink-0" style="min-width: 100px;"></div>';
                    }).join('');
                    safeHTML(gridElement, gridHTML);
                }
            }.bind(this));
        },

        updateWorkPackagePositions() {
            // Force Alpine.js to recalculate work package positions
            this.filteredWorkPackages = [].concat(this.filteredWorkPackages);
        },

        async loadWorkPackages() {
            try {
                let response = await fetch('/api/archimate-work-packages');
                let data = await response.json();
                this.workPackages = data.work_packages || [];
                this.filteredWorkPackages = [].concat(this.workPackages);
            } catch (error) {
                console.error('Error loading work packages:', error);
                this.workPackages = APP_CONFIG.archimateWorkPackages || [];
                this.filteredWorkPackages = [].concat(this.workPackages);
            }
        },

        filterWorkPackages() {
            this.filteredWorkPackages = this.workPackages.filter(function(wp) {
                let matchesLayer = !this.selectedLayer || wp.archimate_layer === this.selectedLayer;
                let matchesType = !this.selectedType || wp.work_package_type === this.selectedType;
                return matchesLayer && matchesType;
            }.bind(this));
        },

        getLayerColor(layer) {
            let colors = {
                'Business': 'bg-primary',
                'Application': 'bg-emerald-500',
                'Technology': 'bg-orange-500',
                'Implementation': 'bg-violet-500'
            };
            return colors[layer] || 'bg-muted/50';
        },

        getDeliverableStatusColor(status) {
            let colors = {
                'planned': 'bg-muted/70',
                'in_progress': 'bg-amber-400',
                'completed': 'bg-emerald-400',
                'cancelled': 'bg-destructive/60'
            };
            return colors[status] || 'bg-muted/70';
        },

        getGapPriorityColor(priority) {
            let colors = {
                'critical': 'bg-destructive',
                'high': 'bg-orange-500',
                'medium': 'bg-amber-500',
                'low': 'bg-emerald-500'
            };
            return colors[priority] || 'bg-muted/50';
        },

        getBarStyle(workPackage) {
            // Ensure dates are properly parsed
            let startDate = new Date(workPackage.start_date);
            let endDate = new Date(workPackage.target_date);

            // Validate dates
            if (isNaN(startDate.getTime()) || isNaN(endDate.getTime()) || this.timelinePeriods.length === 0) {
                return {
                    left: '0px',
                    width: '0px',
                    top: '50%',
                    transform: 'translateY(-50%)'
                };
            }

            // Calculate position based on timeline periods
            let totalPeriods = this.timelinePeriods.length;
            let periodWidth = 100 / totalPeriods; // Each period gets equal width percentage

            // Find which period the work package starts in
            let startPeriodIndex = 0;
            let endPeriodIndex = totalPeriods - 1;

            for (let i = 0; i < this.timelinePeriods.length; i++) {
                let period = this.timelinePeriods[i];
                if (startDate >= period.start && startDate <= period.end) {
                    startPeriodIndex = i;
                }
                if (endDate >= period.start && endDate <= period.end) {
                    endPeriodIndex = i;
                    break;
                }
            }

            // Calculate position and width in percentages
            let leftPercent = startPeriodIndex * periodWidth;
            let widthPercent = (endPeriodIndex - startPeriodIndex + 1) * periodWidth;

            return {
                left: leftPercent + '%',
                width: widthPercent + '%',
                top: '50%',
                transform: 'translateY(-50%)',
                minWidth: '20px' // Ensure minimum visibility
            };
        },

        getProgressStyle(workPackage) {
            return {
                width: workPackage.progress_percentage + '%'
            };
        },

        getDurationText(workPackage) {
            let startDate = new Date(workPackage.start_date);
            let endDate = new Date(workPackage.target_date);
            let duration = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));

            if (duration <= 0) {
                return 'Invalid';
            } else if (duration === 1) {
                return '1 day';
            } else if (duration < 30) {
                return duration + ' days';
            } else if (duration < 365) {
                let months = Math.floor(duration / 30);
                let days = duration % 30;
                if (days === 0) {
                    return months + ' month' + (months > 1 ? 's' : '');
                } else {
                    return months + 'm ' + days + 'd';
                }
            } else {
                let years = Math.floor(duration / 365);
                let months = Math.floor((duration % 365) / 30);
                if (months === 0) {
                    return years + ' year' + (years > 1 ? 's' : '');
                } else {
                    return years + 'y ' + months + 'm';
                }
            }
        },

        getMilestoneStyle(deliverable, workPackage) {
            // Position milestone at 80% of work package duration
            let startDate = new Date(workPackage.start_date);
            let endDate = new Date(workPackage.target_date);
            let timelineStart = this.timelineStart;
            let totalDays = (this.timelineEnd - timelineStart) / (1000 * 60 * 60 * 24);
            let startOffset = (startDate - timelineStart) / (1000 * 60 * 60 * 24);
            let duration = (endDate - startDate) / (1000 * 60 * 60 * 24);

            // Prevent division by zero
            if (totalDays <= 0 || duration <= 0 || isNaN(totalDays) || isNaN(duration) || !isFinite(totalDays) || !isFinite(duration)) {
                return {
                    left: '0%',
                    top: '50%',
                    transform: 'translate(-50%, -50%)'
                };
            }

            let milestoneOffset = startOffset + (duration * 0.8);
            let leftPercent = 0;

            // Additional protection against division by zero
            if (totalDays > 0 && !isNaN(totalDays) && isFinite(totalDays) && !isNaN(milestoneOffset) && isFinite(milestoneOffset)) {
                leftPercent = Math.max(0, (milestoneOffset / totalDays) * 100);
            }

            return {
                left: leftPercent + '%',
                top: '50%',
                transform: 'translate(-50%, -50%)'
            };
        },

        async saveWorkPackage() {
            try {
                let url = this.editingWorkPackage ?
                    '/api/archimate-work-packages/' + this.editingWorkPackage.id :
                    '/api/archimate-work-packages';
                let method = this.editingWorkPackage ? 'PUT' : 'POST';

                let response = await fetch(url, {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(this.formData)
                });

                let result = await response.json();

                if (result.success) {
                    if (this.editingWorkPackage) {
                        let index = this.filteredWorkPackages.findIndex(function(wp) { return wp.id === this.editingWorkPackage.id; }.bind(this));
                        if (index !== -1) {
                            this.filteredWorkPackages[index] = result.work_package;
                        }
                    } else {
                        this.filteredWorkPackages.push(result.work_package);
                    }

                    this.showAddModal = false;
                    this.editingWorkPackage = null;
                    this.resetForm();
                } else {
                    Platform.toast.error('Error saving work package: ' + result.error);
                }
            } catch (error) {
                console.error('Error saving work package:', error);
                Platform.toast.error('Error saving work package');
            }
        },

        editWorkPackage(workPackage) {
            this.editingWorkPackage = workPackage;
            this.formData = {
                name: workPackage.name,
                description: workPackage.description,
                archimate_element: workPackage.archimate_element,
                archimate_layer: workPackage.archimate_layer,
                work_package_type: workPackage.work_package_type,
                assigned_to: workPackage.assigned_to || '',
                status: workPackage.status,
                start_date: workPackage.start_date,
                target_date: workPackage.target_date,
                progress_percentage: workPackage.progress_percentage,
                estimated_effort_hours: workPackage.estimated_effort_hours
            };
            this.showAddModal = true;
        },

        async deleteWorkPackage(workPackage) {
            if (confirm('Are you sure you want to delete "' + workPackage.name + '"?')) {
                try {
                    let response = await fetch('/api/archimate-work-packages/' + workPackage.id, {
                        method: 'DELETE'
                    });

                    let result = await response.json();

                    if (result.success) {
                        // Remove from local array
                        let index = this.filteredWorkPackages.findIndex(function(wp) { return wp.id === workPackage.id; });
                        if (index !== -1) {
                            this.filteredWorkPackages.splice(index, 1);
                        }
                    } else {
                        Platform.toast.error('Error deleting work package: ' + result.error);
                    }
                } catch (error) {
                    console.error('Error deleting work package:', error);
                    Platform.toast.error('Error deleting work package');
                }
            }
        },

        resetForm() {
            this.formData = {
                name: '',
                description: '',
                archimate_element: '',
                archimate_layer: 'Business',
                work_package_type: 'strategic',
                assigned_to: '',
                status: 'planned',
                start_date: '',
                target_date: '',
                progress_percentage: 0,
                estimated_effort_hours: 0
            };
        },

        exportToCSV() {
            let headers = ['Name', 'ArchiMate Element', 'Layer', 'Type', 'Status', 'Assigned To', 'Start Date', 'Target Date', 'Progress', 'Effort Hours', 'Deliverables', 'Gaps'];
            let rows = this.filteredWorkPackages.map(function(wp) {
                return [
                    wp.name,
                    wp.archimate_element,
                    wp.archimate_layer,
                    wp.work_package_type,
                    wp.status,
                    wp.assigned_to || 'Unassigned',
                    wp.start_date,
                    wp.target_date,
                    wp.progress_percentage + '%',
                    wp.estimated_effort_hours,
                    wp.deliverables.map(function(d) { return d.name; }).join('; '),
                    wp.gaps.map(function(g) { return g.name; }).join('; ')
                ];
            });

            let csvContent = [headers].concat(rows)
                .map(function(row) { return row.map(function(cell) { return '"' + cell + '"'; }).join(','); })
                .join('\n');

            let blob = new Blob([csvContent], { type: 'text/csv' });
            let url = window.URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = url;
            a.download = 'archimate-roadmap-' + new Date().toISOString().split('T')[0] + '.csv';
            a.click();
            window.URL.revokeObjectURL(url);
        },

        exportToPNG() {
            let ganttElement = document.querySelector('.bg-card');
            html2canvas(ganttElement, {
                backgroundColor: '#ffffff',
                scale: 3, // Higher scale for better text clarity
                logging: false,
                useCORS: true,
                allowTaint: true
            }).then(function(canvas) {
                let link = document.createElement('a');
                link.download = 'archimate-roadmap-' + new Date().toISOString().split('T')[0] + '.png';
                link.href = canvas.toDataURL('image/png', 1.0);
                link.click();
            }).catch(function(error) {
                console.error('Error generating PNG:', error);
                Platform.toast.error('Error generating PNG export');
            });
        },

        exportToJPG() {
            let ganttElement = document.querySelector('.bg-card');
            html2canvas(ganttElement, {
                backgroundColor: '#ffffff',
                scale: 3, // Higher scale for better text clarity
                logging: false,
                useCORS: true,
                allowTaint: true
            }).then(function(canvas) {
                let link = document.createElement('a');
                link.download = 'archimate-roadmap-' + new Date().toISOString().split('T')[0] + '.jpg';
                link.href = canvas.toDataURL('image/jpeg', 0.95);
                link.click();
            }).catch(function(error) {
                console.error('Error generating JPG:', error);
                Platform.toast.error('Error generating JPG export');
            });
        },

        // Event handling functions
        getEventStyle(event, workPackage) {
            let start = new Date(this.timelineStart);
            let eventDate = new Date(event.event_date);
            let daysFromStart = Math.floor((eventDate - start) / (1000 * 60 * 60 * 24));

            // Calculate position based on timeline periods
            let periodWidth = 100; // min-width from CSS
            let leftPosition = daysFromStart * periodWidth;

            return {
                left: leftPosition + 'px',
                top: '50%',
                transform: 'translate(-50%, -50%)'
            };
        },

        editImplementationEvent(event) {
            // Edit modal not yet wired for implementation events

            Platform.toast.info('Edit Implementation Event: ' + event.name);
        },

        editBusinessEvent(event) {
            // Edit modal not yet wired for business events

            Platform.toast.info('Edit Business Event: ' + event.name);
        }
    };
}
