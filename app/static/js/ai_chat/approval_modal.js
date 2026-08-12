/**
 * AI Chat CRUD Approval Manager — Alpine.js component.
 *
 * Polls /ai-chat/approvals/pending every 30 seconds, renders a badge count
 * in the chat header, and provides a modal to review / approve / reject
 * pending CRUD operations requested via the AI chat.
 *
 * State lives in a single Alpine.store('approvals') instance, not in the
 * Alpine.data factory below. Two DOM mounts use x-data="approvalManager"
 * (the header badge trigger and the approvals modal, ai_chat/index.html) —
 * Alpine.data factories are instantiated fresh per mount, so with state and
 * init() living on the factory each mount ran its own fetchPending() +
 * setInterval(), doubling the /ai-chat/approvals/pending poll (shell-overhaul
 * Wave 2, Task 5). The factory now just proxies to the shared store, so
 * there is exactly one poll loop no matter how many mounts exist.
 */
function registerApprovalManager() {
    if (!window.Alpine || window.__approvalManagerRegistered) {
        return;
    }
    window.__approvalManagerRegistered = true;

    window.Alpine.store("approvals", {
        /** State */
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
        _initialized: false,

        /* ------------------------------------------------------------------ */
        /*  Lifecycle                                                          */
        /* ------------------------------------------------------------------ */

        init() {
            if (this._initialized) {
                return;
            }
            this._initialized = true;
            this.fetchPending();
            this._pollHandle = setInterval(() => this.fetchPending(), 30000);
        },

        destroy() {
            if (this._pollHandle) {
                clearInterval(this._pollHandle);
                this._pollHandle = null;
            }
            this._initialized = false;
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
    });

    // Starts the single fetchPending()/setInterval() loop (guarded by
    // _initialized above, so re-registering the Alpine.data factory below
    // across mounts never starts a second one).
    window.Alpine.store("approvals").init();

    // Thin per-mount facade — every x-data="approvalManager" mount reads
    // and writes the same Alpine.store('approvals') instance above, so the
    // header badge trigger and the approvals modal share one copy of state
    // instead of each polling and tracking it independently.
    window.Alpine.data("approvalManager", () => ({
        get approvals() {
            return Alpine.store("approvals").approvals;
        },
        get loading() {
            return Alpine.store("approvals").loading;
        },
        get error() {
            return Alpine.store("approvals").error;
        },
        get rejectingId() {
            return Alpine.store("approvals").rejectingId;
        },
        set rejectingId(value) {
            Alpine.store("approvals").rejectingId = value;
        },
        get rejectReason() {
            return Alpine.store("approvals").rejectReason;
        },
        set rejectReason(value) {
            Alpine.store("approvals").rejectReason = value;
        },
        get busyIds() {
            return Alpine.store("approvals").busyIds;
        },
        get pendingCount() {
            return Alpine.store("approvals").pendingCount;
        },
        fetchPending() {
            return Alpine.store("approvals").fetchPending();
        },
        approve(approvalId) {
            return Alpine.store("approvals").approve(approvalId);
        },
        startReject(approvalId) {
            return Alpine.store("approvals").startReject(approvalId);
        },
        cancelReject() {
            return Alpine.store("approvals").cancelReject();
        },
        confirmReject(approvalId) {
            return Alpine.store("approvals").confirmReject(approvalId);
        },
        formatDate(iso) {
            return Alpine.store("approvals").formatDate(iso);
        },
        opColor(type) {
            return Alpine.store("approvals").opColor(type);
        },
    }));
}

if (window.Alpine) {
    registerApprovalManager();
} else {
    document.addEventListener("alpine:init", registerApprovalManager, { once: true });
}
