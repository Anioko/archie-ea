/**
 * Document Analyzer - External JavaScript
 * Extracted from app/templates/components/document_analyzer.html
 * Uses window.__APP_CONFIG__ bridge for server-side values (none needed currently)
 *
 * Alpine.js component: documentAnalyzer(entityType, entityId)
 * Called via x-data in the template with Jinja2-provided parameters.
 */
let APP_CONFIG = window.__APP_CONFIG__ || {};

function documentAnalyzer(entityType, entityId) {
    return {
        entityType: entityType,
        entityId: entityId,
        selectedFiles: [],
        dragover: false,
        uploading: false,
        uploadStatus: 'Uploading...',
        provider: 'claude',
        analysisResults: null,
        applying: false,
        editMode: false,
        filePreview: null,
        showDiffPreview: false,
        analysisHistory: [],
        analysisId: null,
        batchProgress: { current: 0, total: 0 },
        fileProgress: [],
        batchResults: [],

        handleDrop: function(event) {
            this.dragover = false;
            let files = Array.from(event.dataTransfer.files);
            this.addFiles(files);
        },

        handleFileSelect: function(event) {
            let files = Array.from(event.target.files);
            this.addFiles(files);
        },

        addFiles: function(files) {
            let MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
            let allowedExtensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.png', '.jpg', '.jpeg', '.gif', '.svg'];
            let self = this;

            files.forEach(function(file) {
                // Check file size
                if (file.size > MAX_FILE_SIZE) {
                    Platform.toast.warning('File "' + file.name + '" is too large. Maximum size is 50MB.');
                    return;
                }

                // Check file extension
                let ext = '.' + file.name.split('.').pop().toLowerCase();
                if (allowedExtensions.indexOf(ext) === -1) {
                    Platform.toast.warning('File "' + file.name + '" has unsupported format. Allowed: ' + allowedExtensions.join(', '));
                    return;
                }

                // Check if file already exists
                let exists = self.selectedFiles.find(function(f) {
                    return f.name === file.name && f.size === file.size;
                });
                if (!exists) {
                    self.selectedFiles.push(file);
                }
            });
        },

        removeFile: function(index) {
            this.selectedFiles.splice(index, 1);
        },

        clearFiles: function() {
            this.selectedFiles = [];
            let fileInput = document.getElementById('document-file-input');
            if (fileInput) fileInput.value = '';
        },

        formatFileSize: function(bytes) {
            if (bytes === 0) return '0 Bytes';
            let k = 1024;
            let sizes = ['Bytes', 'KB', 'MB', 'GB'];
            let i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        },

        analyzeDocument: function() {
            if (this.selectedFiles.length === 0) return;

            let self = this;
            self.uploading = true;
            self.batchProgress = { current: 0, total: self.selectedFiles.length };
            self.fileProgress = [];
            self.batchResults = [];

            // Initialize progress for all files
            self.selectedFiles.forEach(function(file, index) {
                self.fileProgress.push({
                    fileName: file.name,
                    status: 'pending',
                    percent: 0
                });
            });

            let url = self.entityType === 'application'
                ? '/api/applications/' + self.entityId + '/analyze-document'
                : '/api/vendors/' + self.entityId + '/analyze-document';

            // Process files sequentially using a promise chain
            let chain = Promise.resolve();
            self.selectedFiles.forEach(function(file, i) {
                chain = chain.then(function() {
                    self.batchProgress.current = i + 1;
                    self.uploadStatus = 'Processing ' + file.name + ' (' + (i + 1) + '/' + self.selectedFiles.length + ')...';

                    // Update file progress
                    self.fileProgress[i].status = 'processing';
                    self.fileProgress[i].percent = 10;

                    let formData = new FormData();
                    formData.append('file', file);
                    formData.append('provider', self.provider);

                    self.fileProgress[i].percent = 30;
                    self.fileProgress[i].status = 'uploading';

                    let csrfToken = '';
                    let csrfEl = document.querySelector('[name=csrf_token]');
                    if (csrfEl) csrfToken = csrfEl.value;

                    return fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': csrfToken
                        }
                    })
                    .then(function(response) {
                        self.fileProgress[i].percent = 60;
                        self.fileProgress[i].status = 'analyzing';

                        if (!response.ok) {
                            return response.json().then(function(errorData) {
                                throw new Error(errorData.error || 'Analysis failed');
                            });
                        }
                        return response.json();
                    })
                    .then(function(data) {
                        self.fileProgress[i].percent = 100;
                        self.fileProgress[i].status = 'completed';

                        // Store result
                        self.batchResults.push({
                            fileName: file.name,
                            analysis: data.analysis,
                            analysisId: data.analysis_id,
                            success: true
                        });

                        // If this is the first file, set it as the main result
                        if (i === 0) {
                            self.analysisResults = data.analysis;
                            self.analysisId = data.analysis_id;
                        }
                    })
                    .catch(function(error) {
                        self.fileProgress[i].status = 'error';
                        self.fileProgress[i].percent = 100;

                        // Better error handling
                        let errorMessage = error.message;
                        if (error.message.indexOf('timeout') !== -1 || error.message.indexOf('network') !== -1) {
                            errorMessage = 'Analysis timed out';
                        } else if (error.message.indexOf('file type') !== -1 || error.message.indexOf('not allowed') !== -1) {
                            errorMessage = 'Unsupported file type';
                        } else if (error.message.indexOf('size') !== -1 || error.message.indexOf('too large') !== -1) {
                            errorMessage = 'File too large (max 50MB)';
                        }

                        self.batchResults.push({
                            fileName: file.name,
                            error: errorMessage,
                            success: false
                        });
                    });
                });
            });

            chain.then(function() {
                // Show summary
                let successCount = self.batchResults.filter(function(r) { return r.success; }).length;
                let errorCount = self.batchResults.filter(function(r) { return !r.success; }).length;

                self.uploadStatus = 'Completed: ' + successCount + ' succeeded, ' + errorCount + ' failed';
                self.uploading = false;

                // Show summary notification
                if (errorCount > 0) {
                    let errorDiv = document.createElement('div');
                    errorDiv.className = 'fixed top-4 right-4 bg-amber-500 text-primary-foreground p-4 rounded-lg shadow-lg z-50 max-w-md';
                    safeHTML(errorDiv, '<div class="flex items-center gap-2 mb-2">' +
                        '<i data-lucide="alert-triangle" class="h-5 w-5"></i>' +
                        '<h4 class="font-semibold">Batch Analysis Complete</h4>' +
                    '</div>' +
                    '<p class="text-sm">' + successCount + ' file(s) analyzed successfully, ' + errorCount + ' file(s) failed.</p>' +
                    '<button onclick="this.parentElement.remove()" class="mt-2 text-xs underline">Dismiss</button>');
                    document.body.appendChild(errorDiv);
                    setTimeout(function() { errorDiv.remove(); }, 10000);
                }
            });
        },

        applyAnalysis: function() {
            if (!this.analysisResults) return;

            let self = this;
            self.applying = true;

            let url = self.entityType === 'application'
                ? '/api/applications/' + self.entityId + '/apply-analysis'
                : '/api/vendors/' + self.entityId + '/apply-analysis';

            let csrfToken = '';
            let csrfEl = document.querySelector('[name=csrf_token]');
            if (csrfEl) csrfToken = csrfEl.value;

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    analysis: self.analysisResults,
                    analysis_id: self.analysisId
                })
            })
            .then(function(response) {
                if (!response.ok) {
                    return response.json().then(function(errorData) {
                        throw new Error(errorData.error || 'Failed to apply analysis');
                    });
                }
                return response.json();
            })
            .then(function(data) {
                // Show success message with details
                let message = 'Analysis applied successfully!\n\n' +
                    '- ' + data.archimate_elements_created + ' ArchiMate elements created\n' +
                    '- Application/Vendor details updated';

                if (confirm(message + '\n\nReload page to see changes?')) {
                    window.location.reload();
                }
            })
            .catch(function(error) {
                self.applying = false;
                Platform.toast.error('Error applying analysis: ' + error.message);
            });
        },

        previewFile: function(file) {
            let fileToPreview = file || this.selectedFiles[0];
            if (!fileToPreview) return;
            let self = this;

            // For images, show preview
            if (fileToPreview.type.startsWith('image/')) {
                let reader = new FileReader();
                reader.onload = function(e) {
                    self.filePreview = '<img src="' + e.target.result + '" class="max-w-full h-auto rounded" alt="Preview">';
                };
                reader.readAsDataURL(fileToPreview);
            } else {
                // For text-based files, show first 1000 chars
                let reader = new FileReader();
                reader.onload = function(e) {
                    let text = e.target.result.substring(0, 1000);
                    self.filePreview = '<pre class="whitespace-pre-wrap text-xs">' + self.escapeHtml(text) + '</pre>';
                };
                reader.readAsText(fileToPreview);
            }
        },

        escapeHtml: function(text) {
            let div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        reanalyzeWithDifferentProvider: function() {
            if (this.selectedFiles.length === 0) return;

            // Cycle through providers
            let providers = ['claude', 'openai', 'gemini'];
            let currentIndex = providers.indexOf(this.provider);
            this.provider = providers[(currentIndex + 1) % providers.length];

            // Re-analyze
            this.analysisResults = null;
            this.batchResults = [];
            this.analyzeDocument();
        },

        addNewElement: function() {
            if (!this.analysisResults.archimate_elements) {
                this.analysisResults.archimate_elements = [];
            }
            this.analysisResults.archimate_elements.push({
                name: '',
                type: 'ApplicationComponent',
                layer: 'application',
                description: ''
            });
        },

        removeElement: function(index) {
            if (this.analysisResults.archimate_elements) {
                this.analysisResults.archimate_elements.splice(index, 1);
            }
        },

        resetAnalyzer: function() {
            this.selectedFiles = [];
            this.analysisResults = null;
            this.uploading = false;
            this.applying = false;
            this.editMode = false;
            this.filePreview = null;
            this.showDiffPreview = false;
            this.batchProgress = { current: 0, total: 0 };
            this.fileProgress = [];
            this.batchResults = [];
            let fileInput = document.getElementById('document-file-input');
            if (fileInput) fileInput.value = '';
        }
    };
}
