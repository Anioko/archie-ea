/**
 * Information map index — data domain edit/delete modal state.
 *
 * Registered on `alpine:init` rather than at top level: alpine.min.js is loaded
 * with `defer`, so calling Alpine.data() while this file executes throws
 * "Alpine is not defined", the component is never registered, and the page sits
 * inert behind x-cloak.
 */
document.addEventListener('alpine:init', function () {
    Alpine.data('informationMapIndex', function () {
        return {
            domainForm: {},
            domainDeleteForm: {},

            openDomainEdit(domain) {
                this.domainForm = Object.assign({}, domain);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('domain-edit-modal');
                }
            },

            openDomainDelete(domain) {
                this.domainDeleteForm = Object.assign({}, domain);
                if (window.Platform && window.Platform.modal) {
                    window.Platform.modal.open('domain-delete-modal');
                }
            }
        };
    });
});
