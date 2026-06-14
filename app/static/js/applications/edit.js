/**
 * applications/edit.js
 * Form validation and Lucide icon init for the application edit page.
 */

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('editForm');
    const nameInput = document.getElementById('name');

    if (form && nameInput) {
        form.addEventListener('submit', function (e) {
            const name = nameInput.value.trim();
            if (!name) {
                e.preventDefault();
                Platform.toast.warning('Application name is required');
                nameInput.focus();
                return false;
            }
        });
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});
