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
                    const r = await fetch("/api/sprints/default-board");
                    if (r.ok) {
                        const data = await r.json();
                        this.boardId = data.board_id;
                    }
                } catch (e) {
                    console.warn("sprint_planning: could not resolve board_id", e);
                }
            },

            async loadSprints() {
                if (!this.boardId) return;
                this.loading = true;
                try {
                    const r = await fetch(`/api/sprints?board_id=${this.boardId}`);
                    const data = await r.json();
                    this.sprints = Array.isArray(data) ? data : [];
                    this.activeSprint =
                        this.sprints.find((s) => s.status === "active") ||
                        this.sprints.find((s) => s.status === "planning") ||
                        null;
                } catch (e) {
                    console.warn("sprint_planning: loadSprints failed", e);
                    this.sprints = [];
                } finally {
                    this.loading = false;
                }
            },

            async createSprint(name, startDate, endDate, capacityPoints) {
                if (!this.boardId || !name) return;
                try {
                    await fetch("/api/sprints", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            board_id: this.boardId,
                            name: name,
                            start_date: startDate || null,
                            end_date: endDate || null,
                            capacity_points: Number(capacityPoints) || 0,
                        }),
                    });
                    this.newSprint = { name: "", startDate: "", endDate: "", capacityPoints: 0 };
                    this.showCreateForm = false;
                    await this.loadSprints();
                } catch (e) {
                    console.warn("sprint_planning: createSprint failed", e);
                }
            },

            async assignCard(cardRef, sprintId) {
                if (!sprintId) return;
                try {
                    await fetch(`/api/sprints/${sprintId}/cards`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ card_ref: cardRef }),
                    });
                    await this.loadSprints();
                } catch (e) {
                    console.warn("sprint_planning: assignCard failed", e);
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
