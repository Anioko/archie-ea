function featureFlagsManager() {
    return {
        toggleStates: {},
        
        init() {
            // Initialize all toggle states from the DOM
            document.querySelectorAll('[data-feature-id]').forEach(el => {
                const id = parseInt(el.dataset.featureId);
                const isEnabled = el.dataset.initialEnabled === 'true';
                this.toggleStates[id] = { enabled: isEnabled, toggling: false };
            });
        },
        
        async toggleFeature(id) {
            // Ensure state exists
            if (!this.toggleStates[id]) {
                this.toggleStates[id] = { enabled: false, toggling: false };
            }
            
            // Set loading state
            this.toggleStates[id].toggling = true;
            
            try {
                // Use Platform.fetch.post which automatically injects CSRF token and serializes JSON
                const data = await Platform.fetch.post(`/admin/feature-flags/${id}/toggle`, undefined, { silent: true });

                // Platform.fetch throws on non-ok responses, so if we reach here the request succeeded
                // The response is already parsed JSON
                if (data.success) {
                    // Update state
                    this.toggleStates[id].enabled = data.enabled;
                    this.toggleStates[id].toggling = false;
                    
                    // Reinitialize lucide icons after Alpine updates DOM
                    setTimeout(() => {
                        if (window.lucide) lucide.createIcons();
                    }, 50);
                    
                    // Show success message
                    this.showToast(`Feature ${data.enabled ? 'enabled' : 'disabled'}`, 'success');
                } else {
                    // The server returned a 200 but with success:false
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (error) {
                // Reset loading state
                this.toggleStates[id].toggling = false;
                // Platform.fetch already showed a toast unless silent:true, which we set.
                // We still show our own toast to maintain existing behavior.
                this.showToast('Error: ' + error.message, 'error');
            }
        },
        
        showToast(message, type = 'info') {
            // Simple console log for now - you can enhance this

            
            // Flash message in top right
            const toast = document.createElement('div');
            toast.className = `fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg ${
                type === 'success' ? 'bg-emerald-500 text-primary-foreground' : 'bg-destructive text-primary-foreground'
            }`;
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.transition = 'opacity 0.3s';
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    };
}
