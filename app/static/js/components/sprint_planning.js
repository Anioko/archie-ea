// app/static/js/components/sprint_planning.js
// Sprint Planning Panel — Alpine.js component for TPM sprint planning on ADM Kanban board.
(function (global) {
    "use strict";

    function sprintPlanningPanel() {
        return {
            open: false,
            sprints: [],
            activeSprint: null,
            loading: false,
            boardId: null,
            showCreateForm: false,
            newSprint: { name: "", startDate: "", endDate: "", capacityPoints: 0 },

            async init() {
                await this._resolveBoardId();
                if (this.boardId) {
                    await this.loadSprints();
                }
            },

            async _resolveBoardId() {
                try {
                    const data = await Platform.fetch("/api/sprints/default-board");
                    this.boardId = data.board_id;
                } catch (e) {
                    // Could not resolve board_id; surface the failure to the user.
                    if (window.Platform && Platform.toast) {
                        Platform.toast.error("Could not load the sprint board");
                    }
                    // Re-throw to prevent further processing with invalid boardId.
                    throw e;
                }
            },

            async loadSprints() {
                if (!this.boardId) return;
                this.loading = true;
                try {
                    const data = await Platform.fetch.get(`/api/sprints`, { board_id: this.boardId });
                    this.sprints = Array.isArray(data) ? data : [];
                    this.activeSprint =
                        this.sprints.find((s) => s.status === "active") ||
                        this.sprints.find((s) => s.status === "planning") ||
                        null;
                } catch (e) {
                    // loadSprints failed; do not invent data.
                    this.sprints = [];
                    // Re-throw to surface the failure.
                    throw e;
                } finally {
                    this.loading = false;
                }
            },

            async createSprint(name, startDate, endDate, capacityPoints) {
                if (!this.boardId || !name) return;
                try {
                    await Platform.fetch.post("/api/sprints", {
                        board_id: this.boardId,
                        name: name,
                        start_date: startDate || null,
                        end_date: endDate || null,
                        capacity_points: Number(capacityPoints) || 0,
                    });
                    this.newSprint = { name: "", startDate: "", endDate: "", capacityPoints: 0 };
                    this.showCreateForm = false;
                    await this.loadSprints();
                } catch (e) {
                    // createSprint failed; surface the failure to the user.
                    if (window.Platform && Platform.toast) Platform.toast.error("Could not create the sprint.");
                    // Re-throw to prevent further processing.
                    throw e;
                }
            },

            async assignCard(cardRef, sprintId) {
                if (!sprintId) return;
                try {
                    await Platform.fetch.patch(`/api/sprints/${sprintId}/cards`, { card_ref: cardRef });
                    await this.loadSprints();
                } catch (e) {
                    // assignCard failed; surface the failure to the user.
                    if (window.Platform && Platform.toast) Platform.toast.error("Could not assign the card to that sprint.");
                    // Re-throw to prevent further processing.
                    throw e;
                }
            },

            get totalPoints() {
                return (
                    this.activeSprint?.cards?.reduce(
                        (s, c) => s + (c.story_points || 0),
                        0
                    ) || 0
                );
            },

            get overCapacity() {
                return this.totalPoints > (this.activeSprint?.capacity_points || 0);
            },
        };
    }

    global.sprintPlanningPanel = sprintPlanningPanel;
})(window);
