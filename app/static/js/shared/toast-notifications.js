/**
 * Toast Notification System
 * Modern, non-blocking notification system for Flask-Shadcn platform
 *
 * Shadcn-styled toast notifications with:
 * - Multiple types (success, error, warning, info)
 * - Auto-dismiss with configurable timing
 * - Action buttons support
 * - Queue management
 * - Animations
 *
 * Usage:
 *   toast.success('Operation completed!');
 *   toast.error('Failed to save', { description: 'Database error' });
 *   toast.warning('Are you sure?', { action: { label: 'Confirm', onClick: () => {} } });
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.toasts = [];
        this.maxToasts = 5;
        this.defaultDuration = 4000;
        this.init();
    }

    init() {
        // Create container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toast-container');
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - Main message
     * @param {string} type - Type: success, error, warning, info
     * @param {Object} options - Additional options
     */
    show(message, type = 'info', options = {}) {
        const {
            description = '',
            duration = this.defaultDuration,
            action = null,
            dismissible = true,
            icon = null
        } = options;

        // Limit number of toasts
        if (this.toasts.length >= this.maxToasts) {
            this.dismiss(this.toasts[0].id);
        }

        const toastId = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const toast = this.createToastElement(toastId, message, type, description, action, dismissible, icon);

        this.container.appendChild(toast);
        this.toasts.push({ id: toastId, element: toast });

        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('toast-show');
        });

        // Auto-dismiss (if duration > 0)
        if (duration > 0) {
            setTimeout(() => this.dismiss(toastId), duration);
        }

        return toastId;
    }

    createToastElement(id, message, type, description, action, dismissible, customIcon) {
        const toast = document.createElement('div');
        toast.id = id;
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');

        // Icon based on type
        const icons = {
            success: 'check-circle',
            error: 'x-circle',
            warning: 'alert-triangle',
            info: 'info'
        };
        const iconName = customIcon || icons[type] || icons.info;

        let html = `
            <div class="toast-content">
                <div class="toast-icon">
                    <i data-lucide="${iconName}"></i>
                </div>
                <div class="toast-body">
                    <div class="toast-message">${this.escapeHtml(message)}</div>
                    ${description ? `<div class="toast-description">${this.escapeHtml(description)}</div>` : ''}
                </div>
                <div class="toast-actions">
                    ${action ? `<button class="toast-action-btn" data-action="true">${this.escapeHtml(action.label)}</button>` : ''}
                    ${dismissible ? `<button class="toast-close" aria-label="Close"><i data-lucide="x"></i></button>` : ''}
                </div>
            </div>
        `;

        safeHTML(toast, html);

        // Add event listeners
        if (dismissible) {
            toast.querySelector('.toast-close').addEventListener('click', () => this.dismiss(id));
        }

        if (action) {
            toast.querySelector('.toast-action-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                if (action.onClick) action.onClick();
                if (action.dismissOnClick !== false) this.dismiss(id);
            });
        }

        // Initialize Lucide icons
        if (window.lucide) {
            setTimeout(() => window.lucide.createIcons(), 0);
        }

        return toast;
    }

    dismiss(toastId) {
        const toastIndex = this.toasts.findIndex(t => t.id === toastId);
        if (toastIndex === -1) return;

        const toast = this.toasts[toastIndex].element;
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');

        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            this.toasts.splice(toastIndex, 1);
        }, 300);
    }

    dismissAll() {
        this.toasts.forEach(toast => this.dismiss(toast.id));
    }

    /**
     * Show success toast
     */
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    /**
     * Show error toast
     */
    error(message, options = {}) {
        return this.show(message, 'error', { duration: 6000, ...options });
    }

    /**
     * Show warning toast
     */
    warning(message, options = {}) {
        return this.show(message, 'warning', { duration: 5000, ...options });
    }

    /**
     * Show info toast
     */
    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    /**
     * Show loading toast (doesn't auto-dismiss)
     */
    loading(message, options = {}) {
        return this.show(message, 'info', {
            duration: 0,
            dismissible: false,
            icon: 'loader-2',
            ...options
        });
    }

    /**
     * Show promise toast - shows loading, then success/error based on promise result
     */
    async promise(promise, messages = {}) {
        const {
            loading = 'Loading...',
            success = 'Success!',
            error = 'Error occurred'
        } = messages;

        const loadingToastId = this.loading(loading);

        try {
            const result = await promise;
            this.dismiss(loadingToastId);
            this.success(typeof success === 'function' ? success(result) : success);
            return result;
        } catch (err) {
            this.dismiss(loadingToastId);
            this.error(typeof error === 'function' ? error(err) : error, {
                description: err.message
            });
            throw err;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Create global instance
window.toast = new ToastNotification();

// Legacy alert() replacement helper — handles both string and object call signatures:
//   showToast('message', 'success')          — legacy string API
//   showToast({ title: 'msg', variant: '...' }) — shadcn-style object API
window.showToast = (message, type = 'info') => {
    if (message !== null && typeof message === 'object') {
        const text = message.title || message.message || String(message);
        const variant = message.variant || message.type || type;
        const toastType = variant === 'destructive' ? 'error' : (variant || 'info');
        return window.toast.show(text, toastType);
    }
    return window.toast.show(message, type);
};

// Bridge for Alpine.js $dispatch('show-toast') and CustomEvent('show-toast')
window.addEventListener('show-toast', (e) => {
    const detail = e.detail || {};
    const message = detail.message || '';
    const type = detail.type || 'info';
    if (message && window.toast) {
        window.toast.show(message, type, { duration: detail.duration });
    }
});

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToastNotification;
}
