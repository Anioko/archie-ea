/* The Ask page.
 *
 * A person opens a question card, types a business noun, chooses a match and
 * gets that question's answer for it. Two questions today: impact (L1, "what
 * breaks") and risk (L6, "what could hurt"). One question is open at a time
 * (openKey), and one shared picker (fixed input id / $refs.pickerInput --
 * see _entity_picker.html) sits in whichever panel is open; onSelect()
 * dispatches by openKey rather than always loading the impact answer.
 * answeredKey records which question the CURRENT result set belongs to, so
 * switching the open question does not change which results are showing
 * until a new answer actually arrives.
 *
 * Registered as a top-level window factory and referenced as
 * x-data="askSurface()"; the CSP-safe expression interpreter resolves names
 * against the component scope and window, never against Alpine.data().
 */
function askSurface() {
    var Intelligence = window.Intelligence;
    return Object.assign(Intelligence.picker('ask'), Intelligence.drawerState(), {
        openKey: null,
        answeredKey: null,
        state: 'idle',
        busy: false,
        centreId: null,
        rows: [],
        notComputed: false,
        stale: false,
        withheld: false,
        staleNotice: '',
        twinMapUrl: '',
        recomputing: false,
        recomputeLine: '',
        recomputeFailed: false,
        riskState: 'idle',
        riskBusy: false,
        risks: [],

        init() {
            this.twinMapUrl = this.$el.getAttribute('data-twin-map-url') || '';
        },

        toggleQuestion(key) {
            this.openKey = this.openKey === key ? null : key;
            if (this.openKey) {
                var self = this;
                this.$nextTick(function () { self.$refs.pickerInput.focus(); });
            }
        },

        twinMapHref(row) {
            return this.twinMapUrl + '?element=' + row.elementId;
        },

        onSelect(option) {
            if (this.openKey === 'risk') {
                this.loadRisk(option.id);
            } else {
                this.load(option.id);
            }
        },

        async load(elementId) {
            this.answeredKey = 'impact';
            this.centreId = elementId;
            this._loadSeq = (this._loadSeq || 0) + 1;
            var seq = this._loadSeq;
            this.busy = true;
            this.state = 'loading';
            this.notComputed = false;
            this.stale = false;
            this.withheld = false;
            this.syncDrawer();
            try {
                var payload = await Intelligence.fetchImpact(elementId, { maxDepth: 3, includeDerived: true });
                if (seq !== this._loadSeq) return;
                this.rows = Intelligence.buildRows(payload, elementId);
                var answer = Intelligence.answerState(payload, this.rows, true);
                this.notComputed = answer.notComputed;
                this.stale = answer.stale;
                this.withheld = answer.withheld;
                this.staleNotice = answer.notice;
                this.state = this.rows.length ? 'ready' : 'empty';
                var name = Intelligence.nameOf(payload.elements || {}, elementId) || this.term.trim();
                this.statusText = Intelligence.connectionsText(this.rows.length, name, answer.withheld);
            } catch (err) {
                if (seq !== this._loadSeq) return;
                this.rows = [];
                this.state = 'error';
            }
            this.busy = false;
            this.syncDrawer();
            this.$nextTick(function () { Intelligence.refreshIcons(); });
        },

        /* L6 counterpart of load(). No provenance-drawer sync -- the drawer
           reads impact-shaped detail (detailOf()/row.key); risk cards do not
           open it. No stale/withheld notices either: those describe the
           derivation engine's own staleness, a concept this endpoint does
           not surface at the top level (each risk's own affectedSummary
           carries its blast radius's derivation_state if a caller needs it). */
        async loadRisk(elementId) {
            this.answeredKey = 'risk';
            this.riskCentreId = elementId;
            this._riskLoadSeq = (this._riskLoadSeq || 0) + 1;
            var seq = this._riskLoadSeq;
            this.riskBusy = true;
            this.riskState = 'loading';
            try {
                var payload = await Intelligence.fetchRisk(elementId, { maxDepth: 3, includeDerived: true });
                if (seq !== this._riskLoadSeq) return;
                this.risks = Intelligence.buildRisks(payload);
                this.riskState = this.risks.length ? 'ready' : 'empty';
            } catch (err) {
                if (seq !== this._riskLoadSeq) return;
                this.risks = [];
                this.riskState = 'error';
            }
            this.riskBusy = false;
            this.$nextTick(function () { Intelligence.refreshIcons(); });
        },

        async recomputeNow() {
            this.recomputing = true;
            this.recomputeLine = '';
            this.recomputeFailed = false;
            try {
                await Intelligence.recompute();
            } catch (err) {
                this.recomputing = false;
                if (Intelligence.failureStatus(err) === 409) {
                    this.recomputeLine = Intelligence.BUSY_LINE;
                } else {
                    this.recomputeLine = Intelligence.ERROR_LINE;
                    this.recomputeFailed = true;
                }
                return;
            }
            this.recomputing = false;
            await this.load(this.centreId);
            Intelligence.keepPlace(this.$refs.resultsHeading, this.stale || this.notComputed);
        }
    });
}
window.askSurface = askSurface;
