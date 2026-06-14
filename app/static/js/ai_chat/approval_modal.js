/**
 * AI Chat CRUD Approval Manager — Alpine.js component.
 *
 * Polls /ai-chat/approvals/pending every 30 seconds, renders a badge count
 * in the chat header, and provides a modal to review / approve / reject
 * pending CRUD operations requested via the AI chat.
 */
function registerApprovalManager() {
    if (!window.Alpine || window.__approvalManagerRegistered) {
        return;
    }
    window.__approvalManagerRegistered = true;
    window.Alpine.data("approvalManager", () => ({
        /** State */
        open: false,
        approvals: [],
        loading: false,
        error: null,
        /** ID of the approval currently being rejected (shows reason textarea) */
        rejectingId: null,
        rejectReason: "",
        /** Busy flags keyed by approval id — prevents double-click */
        busyIds: {},
        /** Polling handle */
        _pollHandle: null,

        /* ------------------------------------------------------------------ */
        /*  Lifecycle                                                          */
        /* ------------------------------------------------------------------ */

        init() {
            this.fetchPending();
            this._pollHandle = setInterval(() => this.fetchPending(), 30000);
        },

        destroy() {
            if (this._pollHandle) {
                clearInterval(this._pollHandle);
                this._pollHandle = null;
            }
        },

        /* ------------------------------------------------------------------ */
        /*  Data fetching                                                      */
        /* ------------------------------------------------------------------ */

        async fetchPending() {
            try {
                const res = await fetch("/ai-chat/approvals/pending", {
                    headers: {
                        "X-CSRFToken": window.csrfToken || "",
                    },
                    credentials: "same-origin",
                });
                if (!res.ok) {
                    throw new Error("HTTP " + res.status);
                }
                const data = await res.json();
                if (data.success) {
                    this.approvals = data.approvals || [];
                    this.error = null;
                }
            } catch (err) {
                console.error("[approvalManager] fetchPending failed:", err);
                // Don't overwrite approvals on transient network errors
            }
        },

        /* ------------------------------------------------------------------ */
        /*  Actions                                                            */
        /* ------------------------------------------------------------------ */

        async approve(approvalId) {
            if (this.busyIds[approvalId]) return;
            this.busyIds[approvalId] = true;
            this.error = null;
            try {
                const res = await fetch(
                    "/ai-chat/approvals/" + approvalId + "/approve",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": window.csrfToken || "",
                        },
                        credentials: "same-origin",
                    }
                );
                const data = await res.json();
                if (data.success) {
                    this.approvals = this.approvals.filter(
                        (a) => a.id !== approvalId
                    );
                } else {
                    this.error = data.error || "Approval failed";
                }
            } catch (err) {
                this.error = "Network error — please try again";
            } finally {
                delete this.busyIds[approvalId];
            }
        },

        startReject(approvalId) {
            this.rejectingId = approvalId;
            this.rejectReason = "";
            this.error = null;
        },

        cancelReject() {
            this.rejectingId = null;
            this.rejectReason = "";
        },

        async confirmReject(approvalId) {
            if (this.busyIds[approvalId]) return;
            this.busyIds[approvalId] = true;
            this.error = null;
            try {
                const res = await fetch(
                    "/ai-chat/approvals/" + approvalId + "/reject",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": window.csrfToken || "",
                        },
                        credentials: "same-origin",
                        body: JSON.stringify({ reason: this.rejectReason }),
                    }
                );
                const data = await res.json();
                if (data.success) {
                    this.approvals = this.approvals.filter(
                        (a) => a.id !== approvalId
                    );
                    this.rejectingId = null;
                    this.rejectReason = "";
                } else {
                    this.error = data.error || "Rejection failed";
                }
            } catch (err) {
                this.error = "Network error — please try again";
            } finally {
                delete this.busyIds[approvalId];
            }
        },

        /* ------------------------------------------------------------------ */
        /*  Modal helpers                                                      */
        /* ------------------------------------------------------------------ */

        openModal() {
            this.open = true;
            this.error = null;
            this.rejectingId = null;
            this.rejectReason = "";
            this.fetchPending();
        },

        closeModal() {
            this.open = false;
        },

        /** Format ISO date to a short human-readable form */
        formatDate(iso) {
            if (!iso) return "";
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        },

        /** Return a Tailwind color token name for an operation type */
        opColor(type) {
            if (type === "create") return "success";
            if (type === "update") return "warning";
            if (type === "delete") return "destructive";
            return "muted-foreground";
        },

        /** Pending count for the badge */
        get pendingCount() {
            return this.approvals.length;
        },
    }));
}

if (window.Alpine) {
    registerApprovalManager();
} else {
    document.addEventListener("alpine:init", registerApprovalManager, { once: true });
}
