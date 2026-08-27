/**
 * ENT-044: Collapsible inline AI chat panel for entity detail pages.
 *
 * Usage:  x-data="inlineChat(elementId, contextType, domain)"
 *
 * @param {number}  elementId    - ID of the entity (solution, vendor, app…)
 * @param {string}  contextType  - 'solution' | 'vendor' | 'application'
 * @param {string}  domain       - Pre-selected domain hint (e.g. 'architecture')
 */
function inlineChat(elementId, contextType, domain) {  // mass-deletion-ok
    return {
        // ── state ────────────────────────────────────────────────────────────
        open: false,
        messages: [],
        inputText: "",
        loading: false,
        errorMsg: "",

        // ── computed ─────────────────────────────────────────────────────────
        get hasMessages() {
            return this.messages.length > 0;
        },

        // ── lifecycle ────────────────────────────────────────────────────────
        init() {
            this.$watch("open", (val) => {
                if (val && !this.hasMessages) {
                    this._greet();
                }
            });
        },

        _greet() {
            this.messages.push({
                role: "assistant",
                text: `Hi! I'm your AI architect. Ask me anything about this ${contextType}.`,
            });
        },

        // ── actions ──────────────────────────────────────────────────────────
        toggle() {
            this.open = !this.open;
        },

        async send() {
            const text = this.inputText.trim();
            if (!text || this.loading) return;

            this.messages.push({ role: "user", text });
            this.inputText = "";
            this.loading = true;
            this.errorMsg = "";

            try {
                // Platform.fetch.post automatically injects CSRF token and serializes plain object to JSON.
                // It throws a structured PlatformError on non-ok responses, which we catch below.
                const data = await Platform.fetch.post("/ai-chat/message", {
                    message: text,
                    element_id: elementId,
                    context_type: contextType,
                    domain: domain,
                }, { silent: true }); // silent:true because we paint our own inline error state (this.errorMsg)

                this.messages.push({
                    role: "assistant",
                    text: data.response || data.message || "No response received.",
                });
            } catch (err) {
                // Platform.fetch throws on any network or HTTP error; surface the failure to the user.
                this.errorMsg = err.message || "Request failed. Please try again.";
                // Do NOT swallow the error: we have set errorMsg which will be displayed inline.
                // No fallback value is substituted; the UI will show the error message.
            } finally {
                this.loading = false;
                this.$nextTick(() => this._scrollToBottom());
            }
        },

        handleKey(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                this.send();
            }
        },

        _scrollToBottom() {
            const el = this.$refs.messageList;
            if (el) el.scrollTop = el.scrollHeight;
        },

        // CSRF token is now automatically injected by Platform.fetch for mutating methods.
        // No need for a separate helper; keep it for potential other uses but note it's not used by send().
        _csrfToken() {
            const el = document.querySelector("meta[name=csrf-token]");
            return el ? el.content : "";
        },
    };
}
