/**
 * vendors/create_modal.js
 * Alpine.js component factory for the "Create Vendor" modal.
 * Reads the POST URL from window.__VENDOR_CONFIG__.createVendorUrl.
 *
 * Backend response contract (vendor_management.create_vendor):
 *   Success: { status: 'success', vendor_id: <int>, message: <str> }  HTTP 201
 *   Error:   { error: <str> }                                          HTTP 4xx
 */

function vendorCreateModal() {
  return {
    formData: { name: '', vendor_type: '', country: '', website: '', description: '' },
    submitting: false,
    errorMsg: '',
    submitCreateVendor() {
      // FAR-017: Prevent double-click duplicates
      if (this.submitting) return;
      if (!this.formData.name.trim()) {
        this.errorMsg = 'Vendor name is required.';
        return;
      }
      this.submitting = true;
      this.errorMsg = '';
      const url = (window.__VENDOR_CONFIG__ && window.__VENDOR_CONFIG__.createVendorUrl)
        ? window.__VENDOR_CONFIG__.createVendorUrl
        : '/vendor-management/create';

      Platform.fetch.post(url, this.formData)
        .then((data) => {
          this.submitting = false;
          if (data.error) {
            this.errorMsg = data.error;
            return;
          }
          if (data.status === 'success' || data.vendor_id) {
            Platform.modal.close('create-vendor');
            if (window.Platform && window.Platform.toast) {
              Platform.toast.success('Vendor created successfully');
            } else if (typeof window.showToast === 'function') {
              window.showToast('Vendor created successfully', 'success');
            }
            this.formData = { name: '', vendor_type: '', country: '', website: '', description: '' };
            setTimeout(function() { window.location.reload(); }, 800);
            return;
          }
          this.errorMsg = data.message || 'An unexpected error occurred.';
        })
        .catch(() => {
          this.submitting = false;
          this.errorMsg = 'Network error. Please try again.';
        });
    }
  };
}

// Register the component with Alpine so `x-data="vendorCreateModal()"` resolves
// to THIS factory (with submitCreateVendor + the correct createVendorUrl POST
// target). A stale duplicate that exposed submit()/POST /api/vendors used to be
// registered in alpine-architecture.js and shadowed this one, so the template's
// @submit.prevent="submitCreateVendor()" threw "submitCreateVendor is not a
// function" under the CSP Alpine build and no request was ever issued.
document.addEventListener('alpine:init', function () {
  Alpine.data('vendorCreateModal', vendorCreateModal);
});
// Expose factory on window only for backward-compat / testing.
window.vendorCreateModal = vendorCreateModal;
