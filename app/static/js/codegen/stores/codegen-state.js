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
            opts.headers = Object.assign(
                {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken(),
                },
                opts.headers || {}
            );
            let resp = await fetch(url, opts);
            let text = await resp.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (e) {
                let preview = text.substring(0, 300).replace(/<[^>]+>/g, ' ').trim();
                throw new Error('Server returned non-JSON (HTTP ' + resp.status + '): ' + preview);
            }
            if (!resp.ok) {
                throw new Error(data.error || ('HTTP ' + resp.status));
            }
            return data;
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
