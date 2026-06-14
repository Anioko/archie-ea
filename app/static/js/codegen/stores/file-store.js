/**
 * Alpine store: files — file list, selection, dirty-tracking, save.
 * Depends on Alpine.store('codegen') being registered first.
 */
document.addEventListener('alpine:init', function () {
    Alpine.store('files', {
        /* ── state ── */
        list: [],          // sorted path strings
        selected: '',      // currently open path
        content: '',       // content of selected file
        dirty: {},         // { path: true } — unsaved edits per file
        edited: [],        // paths that have been saved at least once this session
        loading: false,

        /* ── load file list from server ── */
        loadList: async function () {
            let s = Alpine.store('codegen');
            this.loading = true;
            try {
                let data = await s.apiFetch('/solutions/' + s.solutionId + '/codegen/file-list');
                this.list = (data.files || []).slice().sort();
            } catch (e) {
                // First visit or no files yet — leave list empty
                this.list = [];
            } finally {
                this.loading = false;
            }
        },

        /* ── load content for a specific path ── */
        loadContent: async function (path) {
            let s = Alpine.store('codegen');
            let data = await s.apiFetch(
                '/solutions/' + s.solutionId + '/codegen/file-content?path=' + encodeURIComponent(path)
            );
            this.selected = path;
            this.content = data.content || '';
        },

        /* ── save edited content back to server ── */
        save: async function (path, content) {
            let s = Alpine.store('codegen');
            await s.apiFetch('/solutions/' + s.solutionId + '/codegen/files', {
                method: 'PATCH',
                body: JSON.stringify({ path: path, content: content }),
            });
            delete this.dirty[path];
            if (!this.edited.includes(path)) {
                this.edited = this.edited.concat([path]);
            }
        },

        /* ── mark a file as having unsaved changes ── */
        markDirty: function (path) {
            this.dirty[path] = true;
        },

        /* ── clear dirty flag (after discard) ── */
        clearDirty: function (path) {
            delete this.dirty[path];
        },
    });
});
