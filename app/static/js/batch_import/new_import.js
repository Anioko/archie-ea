let APP_CONFIG = window.__APP_CONFIG__ || {};

function newImportForm() {
    return {
        form: {
            name: '',
            archimate_mode: 'standard',
            source_type: null, // 'file', 'paste', 'existing'
            file: null,
            paste_data: '',
            selected_applications: [],
            batch_size: 10,
            budget_limit: null,
            ai_generation: true,
            auto_commit: false
        },
        dragOver: false,
        previewData: [],
        availableApplications: [],
        loadingApplications: false,
        appSearchQuery: '',
        submitting: false,

        archimateModesOptions: [
            {
                value: 'quick',
                label: 'Quick',
                description: 'Application Component + Application Service (ArchiMate 3.2 Application Layer basics)',
                speed: 'Fast',
                speedClass: 'bg-emerald-500/10 text-emerald-700',
                cost: 'Low cost',
                costClass: 'bg-emerald-500/10 text-emerald-700'
            },
            {
                value: 'standard',
                label: 'Standard',
                description: 'Application Component, Service, Interface + Business Service, Process (Application & Business Layers)',
                speed: 'Medium',
                speedClass: 'bg-amber-100 text-amber-700',
                cost: 'Medium cost',
                costClass: 'bg-amber-100 text-amber-700'
            },
            {
                value: 'comprehensive',
                label: 'Comprehensive',
                description: 'Full ArchiMate 3.2: Application, Business, Technology & Implementation layers with relationships',
                speed: 'Slower',
                speedClass: 'bg-destructive/10 text-destructive',
                cost: 'Higher cost',
                costClass: 'bg-destructive/10 text-destructive'
            }
        ],

        init() {
            this.loadAvailableApplications();
        },

        get totalApplications() {
            if (this.form.source_type === 'existing') {
                return this.form.selected_applications.length;
            }
            return this.previewData.length;
        },

        get estimatedBatches() {
            return Math.ceil(this.totalApplications / this.form.batch_size);
        },

        get estimatedLLMCalls() {
            let callsPerApp = {
                'quick': 1,
                'standard': 2,
                'comprehensive': 4
            };
            return this.totalApplications * (callsPerApp[this.form.archimate_mode] || 2);
        },

        get estimatedTokens() {
            let tokensPerCall = {
                'quick': 500,
                'standard': 1000,
                'comprehensive': 2000
            };
            return this.estimatedLLMCalls * (tokensPerCall[this.form.archimate_mode] || 1000);
        },

        get estimatedCost() {
            // Approximate cost: $0.002 per 1000 tokens
            return (this.estimatedTokens / 1000) * 0.002;
        },

        get canSubmit() {
            if (!this.form.name.trim()) return false;
            if (this.totalApplications === 0) return false;
            return true;
        },

        formatFileSize(bytes) {
            if (!bytes) return '';
            let units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while (bytes >= 1024 && i < units.length - 1) {
                bytes /= 1024;
                i++;
            }
            return bytes.toFixed(1) + ' ' + units[i];
        },

        handleFileDrop(event) {
            this.dragOver = false;
            let file = event.dataTransfer.files[0];
            if (file) {
                this.processFile(file);
            }
        },

        handleFileSelect(event) {
            let file = event.target.files[0];
            if (file) {
                this.processFile(file);
            }
        },

        async processFile(file) {
            let validTypes = [
                'text/csv',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ];

            let ext = file.name.split('.').pop().toLowerCase();
            let validExtensions = ['csv', 'xls', 'xlsx'];

            if (!validExtensions.includes(ext)) {
                this.showToast('Please upload a CSV or Excel file', 'error');
                return;
            }

            if (file.size > 10 * 1024 * 1024) {
                this.showToast('File size must be less than 10MB', 'error');
                return;
            }

            this.form.file = file;
            this.form.source_type = 'file';

            // Parse CSV for preview
            if (ext === 'csv') {
                let text = await file.text();
                this.parseCSV(text);
            } else {
                // For Excel files, we'd need a library like SheetJS
                // For now, show placeholder
                this.previewData = [{ name: 'Excel file detected', description: 'Preview will be available after upload' }];
            }
        },

        parseCSV(text) {
            let lines = text.trim().split('\n');
            if (lines.length < 2) {
                this.previewData = [];
                return;
            }

            let headers = lines[0].split(',').map(function(h) { return h.trim().replace(/^["']|["']$/g, ''); });

            let self = this;
            this.previewData = lines.slice(1).map(function(line) {
                let values = self.parseCSVLine(line);
                let row = {};
                headers.forEach(function(header, i) {
                    row[header] = values[i] || '';
                });
                return row;
            }).filter(function(row) { return Object.values(row).some(function(v) { return v.trim(); }); });
        },

        parseCSVLine(line) {
            let result = [];
            let current = '';
            let inQuotes = false;

            for (let i = 0; i < line.length; i++) {
                let char = line[i];

                if (char === '"') {
                    inQuotes = !inQuotes;
                } else if (char === ',' && !inQuotes) {
                    result.push(current.trim());
                    current = '';
                } else {
                    current += char;
                }
            }

            result.push(current.trim());
            return result;
        },

        parsePasteData() {
            if (this.form.paste_data.trim()) {
                this.parseCSV(this.form.paste_data);
            } else {
                this.previewData = [];
            }
        },

        async loadAvailableApplications() {
            // API /capability-map/api/applications not yet implemented
            this.availableApplications = [];
            this.loadingApplications = false;
        },

        searchApplications() {
            // Filter is done client-side for simplicity
            // In production, this would be a server-side search
        },

        toggleApplication(appId) {
            let idx = this.form.selected_applications.indexOf(appId);
            if (idx > -1) {
                this.form.selected_applications.splice(idx, 1);
            } else {
                this.form.selected_applications.push(appId);
            }
            this.form.source_type = 'existing';
        },

        selectAllApplications() {
            let self = this;
            let filteredIds = this.availableApplications
                .filter(function(app) {
                    if (!self.appSearchQuery) return true;
                    let query = self.appSearchQuery.toLowerCase();
                    return app.name.toLowerCase().includes(query) ||
                           (app.description && app.description.toLowerCase().includes(query));
                })
                .map(function(app) { return app.id; });

            this.form.selected_applications = filteredIds;
            this.form.source_type = 'existing';
        },

        async submitForm() {
            // FAR-017: Prevent double-click duplicates
            if (this.submitting) return;
            if (!this.canSubmit) return;

            this.submitting = true;

            try {
                let formData = new FormData();
                formData.append('name', this.form.name);
                formData.append('archimate_mode', this.form.archimate_mode);
                formData.append('batch_size', this.form.batch_size);
                formData.append('ai_generation', this.form.ai_generation);
                formData.append('auto_commit', this.form.auto_commit);

                if (this.form.budget_limit) {
                    formData.append('budget_limit', this.form.budget_limit);
                }

                if (this.form.source_type === 'file' && this.form.file) {
                    formData.append('file', this.form.file);
                    formData.append('source_type', 'file');
                } else if (this.form.source_type === 'paste') {
                    formData.append('paste_data', this.form.paste_data);
                    formData.append('source_type', 'paste');
                } else if (this.form.source_type === 'existing') {
                    formData.append('application_ids', JSON.stringify(this.form.selected_applications));
                    formData.append('source_type', 'existing');
                }

                let response = await fetch('/api/batch-import/jobs', {
                    method: 'POST',
                    body: formData
                });

                let data = await response.json();

                if (data.success) {
                    this.showToast('Import job created successfully', 'success');
                    window.location.href = '/batch-import/jobs/' + data.job_id;
                } else {
                    this.showToast(data.message || 'Failed to create import job', 'error');
                }
            } catch (error) {
                console.error('Failed to create import job:', error);
                this.showToast('Failed to create import job', 'error');
            } finally {
                this.submitting = false;
            }
        },

        showToast(message, type) {
            if (window.showToast) {
                window.showToast(message, type);
            } else {

            }
        }
    };
}
