/**
 * ArchiMate Viewer — Alpine.js component for read-only diagram display
 * Used on Solution Detail page inside the ArchiMate Footprint panel.
 *
 * Wraps ComposerRenderer in view-only mode with viewpoint switching.
 */
function archimateViewer() {
    return {
        renderer: null,
        viewerVisible: false,
        activeViewpoint: 'auto',
        availableViewpoints: [
            { id: 'auto', label: 'Auto (dominant layer)' },
            { id: 'application_cooperation', label: 'Application Cooperation' },
            { id: 'technology', label: 'Technology' },
            { id: 'motivation', label: 'Motivation' },
            { id: 'business_process', label: 'Business Process' },
            { id: 'layered', label: 'Layered' },
        ],

        /**
         * Initialize the read-only viewer with ArchiMate elements.
         * @param {Array} elements  Flat array of element objects with layer, name, type, id.
         * @param {Array} relationships  Array of relationship objects (source_id, target_id, type).
         */
        initViewer: function(elements, relationships) {
            if (!elements || elements.length === 0) return;
            this.viewerVisible = true;
            const self = this;
            this.$nextTick(function() {
                const container = document.getElementById('archimate-viewer-canvas');
                if (!container || typeof ComposerRenderer === 'undefined') {
                    self.viewerVisible = false;
                    return;
                }
                self.renderer = ComposerRenderer.create(container, {
                    mode: 'view',
                    height: 320,
                    background: '#fafbfc',
                });
                self.renderer.loadElements(elements, relationships || []);
                self.renderer.fitToContent();
            });
        },

        /**
         * Switch the active viewpoint filter.
         * @param {string} vpId  Viewpoint identifier.
         */
        switchViewpoint: function(vpId) {
            this.activeViewpoint = vpId;
            /* Future: re-filter elements by viewpoint and reload */
        },

        /**
         * Clean up the JointJS paper and graph to avoid memory leaks.
         */
        destroyViewer: function() {
            if (this.renderer) {
                this.renderer.destroy();
                this.renderer = null;
            }
        },
    };
}
