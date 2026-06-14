/**
 * Vendor Options Analysis — Redirect Shim
 *
 * The Vendor Options Analysis feature has been migrated from a modal to a
 * dedicated full-page workflow at /dashboard/vendor-analysis.
 *
 * This file keeps the legacy openVendorAnalysisModal() global so that any
 * page that still calls it (vendor list, application list) will navigate
 * to the new page instead of trying to open a non-existent modal.
 */

function openVendorAnalysisModal() {
  window.location.href = '/dashboard/vendor-analysis/new';
}

window.openVendorAnalysisModal = openVendorAnalysisModal;
