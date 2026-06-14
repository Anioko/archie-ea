/**
 * applications/create_modal.js
 * Alpine.js component factory for the "Create Application" modal.
 * Reads the POST URL from window.__APP_CONFIG__.createApplicationUrl.
 */

function applicationCreateModal() {
  return {
    formData: {
      name: '',
      application_code: '',
      application_type: '',
      criticality: '',
      deployment_status: '',
      business_owner: '',
      description: ''
    },
    submitting: false,
    errorMsg: '',
    submitCreateApplication() {
      // FAR-017: Prevent double-click duplicates
      if (this.submitting) return;
      if (!this.formData.name.trim()) {
        this.errorMsg = 'Application name is required.';
        return;
      }
      this.submitting = true;
      this.errorMsg = '';
      const url = window.__APP_CONFIG__?.createApplicationUrl || '/applications/create';

      Platform.fetch.post(url, this.formData)
        .then(data => {
          this.submitting = false;
          if (!data.success) {
            this.errorMsg = (data.errors || []).join(' ') || 'An error occurred.';
            return;
          }
          Platform.modal.close('create-application');
          if (window.Platform && window.Platform.toast) {
            Platform.toast.success('Application created successfully');
          }
          setTimeout(() => window.location.reload(), 800);
        })
        .catch(() => {
          this.submitting = false;
          this.errorMsg = 'Network error. Please try again.';
        });
    }
  };
}

// NOTE: Alpine.data('applicationCreateModal', ...) is registered by alpine-architecture.js.
// Do NOT register it here — that would create a duplicate and override the authoritative
// version that uses _fetch(), _toast(), _asyncMixin(), _formMixin(), and _modalMixin().
window.applicationCreateModal = applicationCreateModal;
