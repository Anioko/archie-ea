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
                const response = await fetch(`/admin/feature-flags/${id}/toggle`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                    }
                });

                const data = await response.json();

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
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (error) {
                // Reset loading state
                this.toggleStates[id].toggling = false;
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
