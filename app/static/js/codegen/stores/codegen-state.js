/**
 * Alpine store: codegen — shared identity, config, errors, and fetch helpers.
 * Loaded BEFORE workbench.js so the store is ready when the component initialises.
 */
document.addEventListener('alpine:init', function () {
    Alpine.store('codegen', {
        /* ── identity ── */
        solutionId: null,
        solutionName: '',
        phase: 1,
        version: 1,

        /* ── config (mirrors workbench component config object) ── */
        config: {
            language: 'python-fastapi',
            generation_mode: 'deterministic',
            python_version: '3.12',
            auth: 'none',
            github_org: '',
            repo_name: '',
            visibility: 'private',
            include_readme: true,
            include_frontend: false,
            template_set_id: null,
            ui_framework: 'none',
            mobile_framework: 'none',
            generation_policy: 'scaffold',
        },

        /* ── error bus ── */
        errors: [],
        successMsg: '',

        /* ── CSRF helper ── */
        csrfToken: function () {
            let el = document.querySelector('meta[name="csrf-token"]');
            return el ? el.content : '';
        },

        /* ── unified fetch wrapper ── */
        apiFetch: async function (url, opts) {
            opts = opts || {};
            // Use Platform.fetch to handle CSRF, JSON serialization, and error throwing.
            // silent:true suppresses the global toast; errors will be caught and displayed inline.
            opts.silent = true;
            try {
                const result = await Platform.fetch(url, opts);
                // Platform.fetch returns parsed JSON for JSON responses, text otherwise.
                // If result is a string, that means the response was not JSON (successful but non-JSON).
                // This is unexpected; throw an error similar to previous behavior.
                if (typeof result === 'string') {
                    let preview = result.substring(0, 300).replace(/<[^>]+>/g, ' ').trim();
                    // The exact HTTP status is not available here; previously it was included.
                    // This is a trade-off for using the higher-level wrapper.
                    throw new Error('Server returned non-JSON (HTTP 2xx): ' + preview);
                }
                return result;
            } catch (err) {
                // err is a PlatformError with properties: message, type, status, data, response.
                // We need to throw an Error with message matching previous apiFetch behavior.
                let msg;
                if (err.data && err.data.error) {
                    msg = err.data.error;
                } else if (err.status) {
                    msg = 'HTTP ' + err.status;
                } else {
                    msg = err.message;
                }
                throw new Error(msg);
            }
        },

        /* ── error helpers ── */
        addError: function (msg, autoDismiss) {
            let entry = { id: Date.now(), text: msg };
            this.errors.unshift(entry);
            if (autoDismiss) {
                let id = entry.id;
                let self = this;
                setTimeout(function () {
                    self.errors = self.errors.filter(function (e) { return e.id !== id; });
                }, 8000);
            }
        },

        clearErrors: function () {
            this.errors = [];
        },

        dismissError: function (id) {
            this.errors = this.errors.filter(function (e) { return e.id !== id; });
        },

        setSuccess: function (msg) {
            this.successMsg = msg;
            let self = this;
            setTimeout(function () { self.successMsg = ''; }, 5000);
        },

        /* ── utility ── */
        kebabCase: function (str) {
            return (str || '')
                .toLowerCase()
                .replace(/[^a-z0-9\s-]/g, '')
                .replace(/[\s_]+/g, '-')
                .replace(/-+/g, '-')
                .replace(/^-|-$/g, '');
        },
    });
});
