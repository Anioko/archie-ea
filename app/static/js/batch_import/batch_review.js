/**
 * Batch Review - External JavaScript
 * Extracted from app/templates/batch_import/batch_review.html
 * Uses window.__APP_CONFIG__ bridge for server-side values
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

function batchReview(jobId, batchId) {
    return {
        jobId: jobId,
        batchId: batchId,
        job: null,
        batch: null,
        elements: [],
        loading: true,
        refreshing: false,
        selectedElements: [],
        searchQuery: '',
        filterLayer: '',
        filterStatus: '',
        sortKey: 'name',
        sortOrder: 'asc',
        currentPage: 1,
        perPage: 20,
        showDetailModal: false,
        showEditModal: false,
        showCommitModal: false,
        selectedElement: null,
        editingElement: {},

        layerOptions: ['Business', 'Application', 'Technology', 'Motivation', 'Strategy', 'Implementation'],

        get summary() {
            return {
                total: this.elements.length,
                approved: this.elements.filter(function(e) { return e.approval_status === 'Approved'; }).length,
                pending: this.elements.filter(function(e) { return e.approval_status === 'Pending'; }).length,
                rejected: this.elements.filter(function(e) { return e.approval_status === 'Rejected'; }).length
            };
        },

        get layers() {
            let layerCounts = {};
            this.elements.forEach(function(e) {
                layerCounts[e.layer] = (layerCounts[e.layer] || 0) + 1;
            });

            let layerConfig = {
                'Business': { bgClass: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200', textClass: 'text-amber-600' },
                'Application': { bgClass: 'bg-primary/5 dark:bg-blue-900/20 border-primary/20', textClass: 'text-primary' },
                'Technology': { bgClass: 'bg-emerald-500/5 dark:bg-green-900/20 border-emerald-200', textClass: 'text-emerald-600' },
                'Motivation': { bgClass: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200', textClass: 'text-primary' },
                'Strategy': { bgClass: 'bg-destructive/5 dark:bg-red-900/20 border-destructive/20', textClass: 'text-destructive' },
                'Implementation': { bgClass: 'bg-cyan-50 dark:bg-cyan-900/20 border-cyan-200', textClass: 'text-cyan-600' }
            };

            return Object.entries(layerCounts).map(function(entry) {
                let name = entry[0];
                let count = entry[1];
                let config = layerConfig[name] || { bgClass: 'bg-muted/50 border-border', textClass: 'text-muted-foreground' };
                return {
                    name: name,
                    count: count,
                    bgClass: config.bgClass,
                    textClass: config.textClass
                };
            });
        },

        get canCommit() {
            return this.summary.approved > 0 && this.batch?.status !== 'Committed';
        },

        get filteredElements() {
            let filtered = this.elements;
            let self = this;

            if (this.searchQuery) {
                let query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(function(e) {
                    return e.name.toLowerCase().includes(query) ||
                        e.element_type.toLowerCase().includes(query) ||
                        (e.description && e.description.toLowerCase().includes(query));
                });
            }

            if (this.filterLayer) {
                let layer = this.filterLayer;
                filtered = filtered.filter(function(e) { return e.layer === layer; });
            }

            if (this.filterStatus) {
                let status = this.filterStatus;
                filtered = filtered.filter(function(e) { return e.approval_status === status; });
            }

            // Sort
            let sortKey = this.sortKey;
            let sortOrder = this.sortOrder;
            filtered = [].concat(filtered).sort(function(a, b) {
                let aVal = a[sortKey];
                let bVal = b[sortKey];

                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (sortOrder === 'asc') {
                    return aVal > bVal ? 1 : -1;
                }
                return aVal < bVal ? 1 : -1;
            });

            return filtered;
        },

        get totalPages() {
            return Math.ceil(this.filteredElements.length / this.perPage);
        },

        get startIndex() {
            return (this.currentPage - 1) * this.perPage;
        },

        get endIndex() {
            return this.startIndex + this.perPage;
        },

        get paginatedElements() {
            return this.filteredElements.slice(this.startIndex, this.endIndex);
        },

        get allSelected() {
            let self = this;
            return this.paginatedElements.length > 0 &&
                   this.paginatedElements.every(function(e) { return self.selectedElements.includes(e.id); });
        },

        init: function() {
            this.loadData();
        },

        loadData: function() {
            let self = this;
            self.loading = true;
            return Promise.all([
                fetch('/api/batch-import/jobs/' + self.jobId),
                fetch('/api/batch-import/jobs/' + self.jobId + '/batches/' + self.batchId),
                fetch('/api/batch-import/jobs/' + self.jobId + '/batches/' + self.batchId + '/elements')
            ]).then(function(responses) {
                return Promise.all(responses.map(function(r) { return r.json(); }));
            }).then(function(results) {
                let jobData = results[0];
                let batchData = results[1];
                let elementsData = results[2];

                if (jobData.success) self.job = jobData.job;
                if (batchData.success) self.batch = batchData.batch;
                if (elementsData.success) self.elements = elementsData.elements;

                self.$nextTick(function() {
                    if (typeof lucide !== 'undefined') {
                        lucide.createIcons();
                    }
                });
            }).catch(function(error) {
                console.error('Failed to load data:', error);
                self.showToast('Failed to load batch data', 'error');
            }).finally(function() {
                self.loading = false;
            });
        },

        refreshElements: function() {
            let self = this;
            self.refreshing = true;
            self.loadData().finally(function() {
                self.refreshing = false;
            });
        },

        sortBy: function(key) {
            if (this.sortKey === key) {
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortKey = key;
                this.sortOrder = 'asc';
            }
        },

        isSelected: function(id) {
            return this.selectedElements.includes(id);
        },

        toggleSelect: function(id) {
            let idx = this.selectedElements.indexOf(id);
            if (idx > -1) {
                this.selectedElements.splice(idx, 1);
            } else {
                this.selectedElements.push(id);
            }
        },

        toggleSelectAll: function(event) {
            if (event.target.checked) {
                this.selectedElements = Array.from(new Set(
                    this.selectedElements.concat(
                        this.paginatedElements.map(function(e) { return e.id; })
                    )
                ));
            } else {
                let pageIds = this.paginatedElements.map(function(e) { return e.id; });
                this.selectedElements = this.selectedElements.filter(function(id) { return !pageIds.includes(id); });
            }
        },

        getStatusBadgeClass: function(status) {
            let classes = {
                'Pending': 'border-transparent bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
                'Processing': 'border-transparent bg-primary/10 text-primary dark:bg-blue-900/30 dark:text-blue-400',
                'Processed': 'border-transparent bg-purple-100 text-primary dark:bg-purple-900/30 dark:text-purple-400',
                'Reviewing': 'border-transparent bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
                'Committed': 'border-transparent bg-emerald-500/10 text-emerald-600 dark:bg-green-900/30 dark:text-green-400'
            };
            return classes[status] || classes['Pending'];
        },

        getLayerBadgeClass: function(layer) {
            let classes = {
                'Business': 'border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
                'Application': 'border-transparent bg-primary/10 text-primary dark:bg-blue-900/30 dark:text-blue-400',
                'Technology': 'border-transparent bg-emerald-500/10 text-emerald-700 dark:bg-green-900/30 dark:text-green-400',
                'Motivation': 'border-transparent bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
                'Strategy': 'border-transparent bg-destructive/10 text-destructive dark:bg-red-900/30 dark:text-red-400',
                'Implementation': 'border-transparent bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400'
            };
            return classes[layer] || 'border-transparent bg-muted text-muted-foreground';
        },

        getLayerIconBackground: function(layer) {
            let backgrounds = {
                'Business': 'bg-amber-500',
                'Application': 'bg-primary',
                'Technology': 'bg-emerald-500',
                'Motivation': 'bg-primary',
                'Strategy': 'bg-destructive',
                'Implementation': 'bg-cyan-500'
            };
            return backgrounds[layer] || 'bg-muted-foreground';
        },

        getApprovalStatusBadgeClass: function(status) {
            let classes = {
                'Pending': 'border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
                'Approved': 'border-transparent bg-emerald-500/10 text-emerald-700 dark:bg-green-900/30 dark:text-green-400',
                'Rejected': 'border-transparent bg-destructive/10 text-destructive dark:bg-red-900/30 dark:text-red-400'
            };
            return classes[status] || classes['Pending'];
        },

        getConfidenceBarClass: function(confidence) {
            if (confidence >= 80) return 'bg-emerald-500';
            if (confidence >= 60) return 'bg-amber-500';
            return 'bg-destructive';
        },

        getConfidenceTextClass: function(confidence) {
            if (confidence >= 80) return 'text-emerald-600';
            if (confidence >= 60) return 'text-amber-600';
            return 'text-destructive';
        },

        showElementDetail: function(element) {
            this.selectedElement = element;
            this.showDetailModal = true;
            this.$nextTick(function() {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });
        },

        editElement: function(element) {
            this.editingElement = Object.assign({}, element);
            this.showEditModal = true;
        },

        saveElement: function() {
            let self = this;
            return fetch(
                '/api/batch-import/jobs/' + self.jobId + '/batches/' + self.batchId + '/elements/' + self.editingElement.id,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(self.editingElement)
                }
            ).then(function(response) {
                return response.json();
            }).then(function(data) {
                if (data.success) {
                    let idx = self.elements.findIndex(function(e) { return e.id === self.editingElement.id; });
                    if (idx > -1) {
                        self.elements[idx] = Object.assign({}, self.elements[idx], self.editingElement);
                    }
                    self.showToast('Element updated', 'success');
                    self.showEditModal = false;
                } else {
                    self.showToast(data.message || 'Failed to update element', 'error');
                }
            }).catch(function(error) {
                console.error('Failed to save element:', error);
                self.showToast('Failed to save element', 'error');
            });
        },

        approveElement: function(elementId) {
            return this.updateElementStatus(elementId, 'Approved');
        },

        rejectElement: function(elementId) {
            return this.updateElementStatus(elementId, 'Rejected');
        },

        updateElementStatus: function(elementId, status) {
            let self = this;
            return fetch(
                '/api/batch-import/jobs/' + self.jobId + '/batches/' + self.batchId + '/elements/' + elementId + '/status',
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                }
            ).then(function(response) {
                return response.json();
            }).then(function(data) {
                if (data.success) {
                    let idx = self.elements.findIndex(function(e) { return e.id === elementId; });
                    if (idx > -1) {
                        self.elements[idx].approval_status = status;
                    }
                    self.showToast('Element ' + status.toLowerCase(), 'success');
                } else {
                    self.showToast(data.message || 'Failed to update status', 'error');
                }
            }).catch(function(error) {
                console.error('Failed to update element status:', error);
                self.showToast('Failed to update status', 'error');
            });
        },

        bulkApprove: function() {
            let self = this;
            let chain = Promise.resolve();
            self.selectedElements.forEach(function(id) {
                chain = chain.then(function() {
                    return self.updateElementStatus(id, 'Approved');
                });
            });
            return chain.then(function() {
                self.selectedElements = [];
            });
        },

        bulkReject: function() {
            let self = this;
            let chain = Promise.resolve();
            self.selectedElements.forEach(function(id) {
                chain = chain.then(function() {
                    return self.updateElementStatus(id, 'Rejected');
                });
            });
            return chain.then(function() {
                self.selectedElements = [];
            });
        },

        autoApproveHighConfidence: function() {
            let self = this;
            let highConfidenceIds = self.elements
                .filter(function(e) { return e.approval_status === 'Pending' && e.confidence >= 80; })
                .map(function(e) { return e.id; });

            if (highConfidenceIds.length === 0) {
                self.showToast('No high-confidence pending elements found', 'info');
                return Promise.resolve();
            }

            let chain = Promise.resolve();
            highConfidenceIds.forEach(function(id) {
                chain = chain.then(function() {
                    return self.updateElementStatus(id, 'Approved');
                });
            });

            return chain.then(function() {
                self.showToast('Auto-approved ' + highConfidenceIds.length + ' elements', 'success');
            });
        },

        commitBatch: function() {
            this.showCommitModal = true;
        },

        confirmCommit: function() {
            let self = this;
            return fetch(
                '/api/batch-import/jobs/' + self.jobId + '/batches/' + self.batchId + '/commit',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                }
            ).then(function(response) {
                return response.json();
            }).then(function(data) {
                if (data.success) {
                    self.showToast('Committed ' + data.committed_count + ' elements to repository', 'success');
                    self.batch.status = 'Committed';
                    self.showCommitModal = false;
                } else {
                    self.showToast(data.message || 'Failed to commit batch', 'error');
                }
            }).catch(function(error) {
                console.error('Failed to commit batch:', error);
                self.showToast('Failed to commit batch', 'error');
            });
        },

        showToast: function(message, type) {
            type = type || 'info';
            if (window.showToast) {
                window.showToast(message, type);
            } else {
                console.log('[' + type + '] ' + message);
            }
        }
    };
}

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}
