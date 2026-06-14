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

// NOTE: Alpine.data('vendorCreateModal', ...) is registered centrally in
// alpine-architecture.js — do NOT register it here a second time.
// Expose factory on window only for backward-compat / testing.
window.vendorCreateModal = vendorCreateModal;
