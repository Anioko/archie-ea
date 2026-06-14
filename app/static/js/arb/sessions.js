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
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify(this.formData)
      })
        .then(r => r.json())
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
        .catch(() => {
          this.submitting = false;
          this.errorMsg = 'Network error. Please try again.';
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
