/**
 * arb/sessions.js
 * Alpine.js component factory for the "Create ARB Session" modal.
 * Reads the POST URL from window.__ARB_CONFIG__.createSessionUrl.
 */

function arbSessionModal() {
  return {
    formData: {
      name: '',
      description: '',
      scheduled_date: '',
      duration_minutes: 120,
      chair_id: '',
      secretary_id: '',
      location: '',
      meeting_link: ''
    },
    submitting: false,
    errorMsg: '',
    submitCreateSession() {
      // FAR-017: Prevent double-click duplicates
      if (this.submitting) return;
      if (!this.formData.name.trim()) { this.errorMsg = 'Session name is required.'; return; }
      if (!this.formData.scheduled_date) { this.errorMsg = 'Scheduled date is required.'; return; }
      if (!this.formData.chair_id) { this.errorMsg = 'Chair is required.'; return; }
      this.submitting = true;
      this.errorMsg = '';
      const url = window.__ARB_CONFIG__?.createSessionUrl || '/arb/sessions/create';
      Platform.fetch.post(url, this.formData, { silent: true })
        .then(data => {
          this.submitting = false;
          if (!data.success) {
            this.errorMsg = Object.values(data.errors || {}).join(' ') || 'An error occurred.';
            return;
          }
          Platform.modal.close('create-arb-session');
          showToast({ title: 'Session scheduled successfully', variant: 'default' });
          setTimeout(() => window.location.reload(), 800);
        })
        .catch(err => {
          this.submitting = false;
          // Every failure must reach the user. Reporting the server's own reason
          // beats a generic line: a 500 here used to read "Network error. Please
          // try again." while the response body said exactly what was wrong.
          const data = (err && err.data) || {};
          const fieldErrors = Object.values(data.errors || {}).filter(Boolean).join(' ');
          this.errorMsg =
            fieldErrors || data.error || (err && err.message) ||
            'The session could not be scheduled.';
          if (window.Platform && Platform.toast) {
            Platform.toast.error(this.errorMsg);
          }
        });
    }
  };
}

document.addEventListener('alpine:init', () => {
  if (window.Alpine) {
    window.Alpine.data('arbSessionModal', arbSessionModal);
  }
});

window.arbSessionModal = arbSessionModal;
