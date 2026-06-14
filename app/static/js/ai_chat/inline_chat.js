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
                const resp = await fetch("/ai-chat/message", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this._csrfToken(),
                    },
                    body: JSON.stringify({
                        message: text,
                        element_id: elementId,
                        context_type: contextType,
                        domain: domain,
                    }),
                });

                if (!resp.ok) {
                    throw new Error(`Server error ${resp.status}`);
                }

                const data = await resp.json();
                this.messages.push({
                    role: "assistant",
                    text: data.response || data.message || "No response received.",
                });
            } catch (err) {
                this.errorMsg = err.message || "Request failed. Please try again.";
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

        _csrfToken() {
            const el = document.querySelector("meta[name=csrf-token]");
            return el ? el.content : "";
        },
    };
}
