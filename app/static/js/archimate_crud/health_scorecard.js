/**
 * Architecture Repository Health Scorecard
 * Alpine.js component that fetches and displays 7 ArchiMate semantic layer health tests.
 */
document.addEventListener("alpine:init", function () {
    Alpine.data("healthScorecard", function () {
        return {
            loading: false,
            repairing: null,
            repairResult: null,
            data: null,
            error: null,

            async loadScorecard() {
                this.loading = true;
                this.error = null;
                try {
                    const resp = await fetch("/architecture/api/health-scorecard");
                    if (!resp.ok) throw new Error("HTTP " + resp.status);
                    this.data = await resp.json();
                } catch (e) {
                    this.error = e.message || "Unknown error";
                } finally {
                    this.loading = false;
                    this.$nextTick(function () {
                        if (typeof lucide !== "undefined") lucide.createIcons();
                    });
                }
            },

            /** Run inference engine repair for a failing test */
            async repairTest(testName) {
                this.repairing = testName;
                this.repairResult = null;
                try {
                    let resp = await fetch("/architecture/api/health-scorecard/repair", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({test: testName}),
                    });
                    if (!resp.ok) {
                        const err = await resp.json();
                        this.repairResult = {error: err.error || "Repair failed"};
                        return;
                    }
                    const result = await resp.json();
                    this.repairResult = result;
                    // Refresh scorecard to show updated results
                    await this.loadScorecard();
                } catch (e) {
                    this.repairResult = {error: e.message || "Unknown error"};
                } finally {
                    this.repairing = null;
                    this.$nextTick(function () {
                        if (typeof lucide !== "undefined") lucide.createIcons();
                    });
                }
            },

            /** Check if a test supports automated repair */
            canRepair: function (testName) {
                const repairable = [
                    "motivation_integrity", "relationship_density",
                    "cross_layer_trace", "im_layer",
                ];
                return repairable.indexOf(testName) !== -1;
            },

            /** Card border colour based on pass/fail */
            cardBorder: function (test) {
                if (!test) return "border-border";
                return test.pass
                    ? "border-emerald-500/30"
                    : "border-destructive/30";
            },

            /** Icon background colour */
            iconBg: function (test) {
                if (!test) return "bg-muted-foreground";
                return test.pass ? "bg-emerald-500" : "bg-destructive";
            },

            /** Badge classes */
            badge: function (test) {
                if (!test) return "";
                return test.pass
                    ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/30"
                    : "bg-destructive/10 text-destructive border border-destructive/30";
            },
        };
    });
});
