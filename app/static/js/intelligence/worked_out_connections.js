/* The Worked-out connections page.
 *
 * Two questions, asked one after the other. The first is the page's figures: the
 * counts, the ratio, when the connections were last worked out and how quickly
 * questions are being answered. The six cards are drawn from that answer alone and
 * never wait for anything else. Once they are on the page, the second question asks
 * how many things the model check found, and the row beside the cards shows a
 * loading treatment until it answers.
 *
 * Every figure is turned into a card model whose accessible name reads the title,
 * the value and the unit together; a figure the answer does not carry is a card that
 * says "Not recorded", never a zero and never a blank.
 *
 * "Work them out now" asks the server to work the connections out for the
 * signed-in person's own tenant, then asks the figures question again. Working the
 * connections out changes nothing the model check reads, so it is not asked again:
 * the row keeps the value it has. The cards stay on the page while it runs; the
 * status region says what is happening.
 *
 * Registered as a top-level window factory and referenced as
 * x-data="workedOutConnections()"; the CSP-safe expression interpreter resolves
 * names against the component scope and window, never against Alpine.data().
 */
function workedOutConnections() {
    var Intelligence = window.Intelligence;

    var YIELD_URL = '/api/v1/intelligence/yield';

    var NOT_WORKED_OUT_LINE = "We haven't worked out the indirect connections for your model yet.";
    var RECALCULATING_LINE = 'Recalculating…';
    var FINISHED_LINE = 'Recalculation finished.';
    var NOT_ENOUGH_LINE = 'Not enough measurements yet';
    var NOTHING_WORKED_OUT = 'Nothing worked out yet';
    var NOT_RECORDED = 'Not recorded';
    var SIZE_UNKNOWN_LINE = 'Findings are not counted here for a model of this size.';

    var IMPACT_QUESTION_CODES = { cross_layer_impact: 'Impact questions' };

    var numbers = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 });
    var fine = new Intl.NumberFormat('en-GB', { maximumSignificantDigits: 2, useGrouping: false });
    var grouped = new Intl.NumberFormat('en-GB');

    function isCount(value) {
        return typeof value === 'number' && isFinite(value);
    }

    /* A count of things: a whole number, never negative. */
    function isWholeCount(value) {
        return isCount(value) && Math.floor(value) === value && value >= 0;
    }

    function noun(count, one, many) {
        return count === 1 ? one : many;
    }

    function hasReason(data, code) {
        return Array.isArray(data.reasons) && data.reasons.indexOf(code) !== -1;
    }

    /* A figure that has a value. The name is what a screen reader reads for it:
       the title, the value and the unit, never the value alone. */
    function figure(title, text, unit) {
        return {
            title: title,
            absent: false,
            plain: false,
            text: text,
            unit: unit,
            name: title + ': ' + text + (unit ? ' ' + unit : '')
        };
    }

    /* A statement in place of a number ("Nothing worked out yet"): a value the answer
       does carry, said in words. It joins its small line with a comma. */
    function statement(title, text, unit) {
        return {
            title: title,
            absent: false,
            plain: true,
            text: text,
            unit: unit,
            name: title + ': ' + text + (unit ? ', ' + unit : '')
        };
    }

    /* A figure the answer does not carry. It reads "Not recorded" on the page and in
       its name; it is never a zero. */
    function absent(title) {
        return { title: title, absent: true, plain: false, text: '', unit: '', name: title + ': ' + NOT_RECORDED };
    }

    function countFigure(title, value, one, many) {
        if (!isCount(value)) return absent(title);
        return figure(title, String(value), noun(value, one, many));
    }

    /* A ratio below one hundredth keeps its first two significant digits, so a small
       one is never rounded to a zero; anything else keeps two decimals. */
    function ratioText(value) {
        if (value === 0) return '0';
        return (value < 0.01 ? fine : numbers).format(value);
    }

    function ratioFigure(title, value) {
        if (!isCount(value)) return absent(title);
        return figure(title, ratioText(value), 'worked out for every explicit one');
    }

    /* When the stored connections were last worked out. A run that stored nothing, and a
       tenant that has never run, both carry no time (null): that reads "Nothing worked
       out yet". A time the answer does not carry at all, or cannot be read, is not
       recorded. The time the last run finished is never used in its place. */
    function workedOutFigure(title, data) {
        if (data.computed_at === null) return statement(title, NOTHING_WORKED_OUT, '');
        var text = Intelligence.timeText(data.computed_at);
        return text ? figure(title, text, '') : absent(title);
    }

    /* "1 second", "0.5 seconds", "2 seconds": the number at two significant digits, and
       "second" only when it reads exactly 1. */
    function secondsText(value) {
        var text = fine.format(value);
        return text + ' ' + noun(Number(text), 'second', 'seconds');
    }

    function recentMeasurements(count) {
        return count + ' recent ' + noun(count, 'measurement', 'measurements') + ' on this server';
    }

    /* What the response time is. It is chosen by the answer's own reason code, never by a
       figure merely being null: below the floor of measurements there is no figure and the
       answer says so; above the slowest range measured the answer says how slow, as a
       lower bound; a null figure the answer gives no reason for is not recorded. The
       count is always the histogram's own, and an answer without one is not recorded. */
    function responseReading(data) {
        if (!isWholeCount(data.sample_count)) return { kind: 'absent' };
        var samples = data.sample_count;
        if (isCount(data.p95_latency_seconds)) {
            return { kind: 'measured', seconds: data.p95_latency_seconds, samples: samples };
        }
        var series = data.p95 && typeof data.p95 === 'object' ? data.p95 : {};
        if (hasReason(data, 'p95_above_highest_bucket') && isCount(series.p95_exceeds_seconds)) {
            return { kind: 'above', seconds: series.p95_exceeds_seconds, samples: samples };
        }
        if (hasReason(data, 'insufficient_samples_for_p95')) return { kind: 'notEnough', samples: samples };
        return { kind: 'absent' };
    }

    function responseFigure(title, data) {
        var reading = responseReading(data);
        if (reading.kind === 'measured') {
            return figure(title, 'Within ' + secondsText(reading.seconds),
                'for 95 in 100 impact questions, from ' + recentMeasurements(reading.samples));
        }
        if (reading.kind === 'above') {
            return figure(title, 'Over ' + secondsText(reading.seconds),
                'for more than 5 in 100 impact questions, from ' + recentMeasurements(reading.samples));
        }
        if (reading.kind === 'notEnough') {
            return statement(title, NOT_ENOUGH_LINE, recentMeasurements(reading.samples));
        }
        return absent(title);
    }

    function blankCards() {
        return {
            explicit: absent('Explicit facts'),
            derived: absent('Worked-out facts'),
            ratio: absent('Ratio'),
            stale: absent('Stale count'),
            workedOutAt: absent('Last worked out'),
            response: absent('Response time')
        };
    }

    function durationText(ms) {
        if (!isCount(ms)) return null;
        if (ms < 1000) return ms + ' ' + noun(ms, 'millisecond', 'milliseconds');
        var seconds = ms / 1000;
        return fine.format(seconds) + ' ' + noun(seconds, 'second', 'seconds');
    }

    function engineText(value) {
        if (Array.isArray(value)) return value.length ? value.join(', ') : null;
        return typeof value === 'string' && value ? value : null;
    }

    function fullTime(iso) {
        if (!iso) return null;
        var text = String(iso);
        if (!/[zZ]$|[+-]\d\d:?\d\d$/.test(text)) text += 'Z';
        return isNaN(new Date(text).getTime()) ? null : text;
    }

    /* The response time as "Full detail" says it: the figure, and what it is the top of. */
    function percentileDetail(data) {
        var reading = responseReading(data);
        if (reading.kind === 'measured') {
            return secondsText(reading.seconds) +
                ', the top of the time range within which 95 in 100 questions were answered';
        }
        if (reading.kind === 'above') {
            var seconds = secondsText(reading.seconds);
            return 'Over ' + seconds + ': fewer than 95 in 100 questions were answered within ' + seconds +
                ', the longest time range measured';
        }
        if (reading.kind === 'notEnough') return NOT_ENOUGH_LINE;
        return null;
    }

    /* What the response time was measured on, in words. Any part the answer does not carry,
       or carries as something this page does not know, makes the whole row "Not recorded". */
    function measuredFromDetail(data) {
        var series = data.p95;
        if (!series || typeof series !== 'object') return null;
        var query = Object.prototype.hasOwnProperty.call(IMPACT_QUESTION_CODES, series.query)
            ? IMPACT_QUESTION_CODES[series.query] : null;
        if (!query) return null;
        if (!isWholeCount(series.depth) || series.depth < 1) return null;
        if (series.include_derived !== true && series.include_derived !== false) return null;
        if (typeof series.scope !== 'string' || !series.scope) return null;
        return query + ' traced ' + series.depth + ' ' + noun(series.depth, 'hop', 'hops') + ' out, ' +
            (series.include_derived ? 'with worked-out connections included' : 'without worked-out connections') +
            ', as answered by this web server since it last started';
    }

    function workedOutAtDetail(data) {
        if (data.computed_at === null) return NOTHING_WORKED_OUT;
        return fullTime(data.computed_at);
    }

    /* What "Full detail" holds: the engine version, the full time, and the response time
       with what it was measured on. A row with no value shows "Not recorded". */
    function detailRows(data) {
        return [
            { label: 'Engine version', value: engineText(data.engine_version) },
            { label: 'Worked out at', value: workedOutAtDetail(data) },
            { label: 'Response time, 95th percentile', value: percentileDetail(data) },
            { label: 'Response time, measured from', value: measuredFromDetail(data) }
        ];
    }

    /* The row beside the cards. It has four states and no other: still asking, a count, a
       model too large to count, and could not be checked. Only a real, whole number is a
       count, so no other state can read as "0 things". */
    function loadingDrift() {
        return { state: 'loading', linked: false, text: '' };
    }

    function unavailableDrift() {
        return { state: 'unavailable', linked: false, text: '' };
    }

    function tooLargeText(count) {
        if (!isWholeCount(count)) return SIZE_UNKNOWN_LINE;
        var size = count === 1 ? '1 element' : grouped.format(count) + ' elements';
        return 'Your model has ' + size + ', so its findings are not counted here.';
    }

    function driftFrom(data) {
        if (isWholeCount(data.drift_finding_count)) {
            return {
                state: 'counted',
                linked: true,
                text: Intelligence.pluralThings(data.drift_finding_count) + ' to look at in your model'
            };
        }
        if (data.drift_finding_count === null && hasReason(data, 'model_too_large_for_drift_check')) {
            return { state: 'too_large', linked: true, text: tooLargeText(data.element_count) };
        }
        return unavailableDrift();
    }

    return {
        loading: true,
        loaded: false,
        failed: false,
        state: '',
        cards: blankCards(),
        staleLine: null,
        recalculation: null,
        drift: loadingDrift(),
        modelChecked: false,
        details: [],
        statusLine: '',
        recomputing: false,
        recomputeFailed: false,
        showRecompute: false,

        init() {
            this.load(false);
        },

        /* Ask the page's figures question. After a recalculation the cards stay where
           they are while it is asked again (`refresh`), so the page never looks broken.
           The model check is asked once, after the figures have been drawn. */
        async load(refresh) {
            if (!refresh) {
                this.loading = true;
                this.failed = false;
            }
            try {
                var resp = await Platform.fetch.get(YIELD_URL, { part: 'figures' }, { silent: true });
                var data = resp && resp.data ? resp.data : null;
                if (!data) throw new Error('no answer');
                this.apply(data);
                this.failed = false;
                this.loaded = true;
            } catch (err) {
                this.loaded = false;
                this.failed = true;
            }
            this.loading = false;
            var self = this;
            this.$nextTick(function () {
                Intelligence.refreshIcons();
                if (!refresh && self.loaded) {
                    // Let the cards paint before the second question is sent, so the two
                    // are never in flight together.
                    window.setTimeout(function () { self.checkModel(); }, 0);
                }
            });
        },

        apply(data) {
            var notWorkedOut = data.state === 'not_computed';
            var outOfDate = data.state === 'stale';
            this.state = data.state;
            this.cards = {
                explicit: countFigure('Explicit facts', data.explicit_count, 'relationship', 'relationships'),
                derived: countFigure('Worked-out facts', data.derived_count, 'relationship', 'relationships'),
                ratio: ratioFigure('Ratio', data.ratio),
                stale: countFigure('Stale count', data.stale_count, 'relationship', 'relationships'),
                workedOutAt: workedOutFigure('Last worked out', data),
                response: responseFigure('Response time', data)
            };
            var when = Intelligence.timeText(data.computed_at);
            this.staleLine = outOfDate
                ? (when ? 'Last worked out ' + when + ' — may be out of date.' : 'May be out of date.')
                : null;
            this.recalculation = durationText(data.last_recompute_duration_ms);
            this.details = detailRows(data);
            this.showRecompute = notWorkedOut || outOfDate;
            if (!this.recomputing) this.statusLine = notWorkedOut ? NOT_WORKED_OUT_LINE : '';
        },

        /* The model check: how many things the drift detector found. Asked once per page
           load, and only when the row that would show it is on the page. An answer that
           cannot be read is "could not check", never a count. */
        async checkModel() {
            if (this.modelChecked || !this.$refs.driftRow) return;
            this.modelChecked = true;
            this.drift = loadingDrift();
            try {
                var resp = await Platform.fetch.get(YIELD_URL, { part: 'model-check' }, { silent: true });
                var data = resp && resp.data ? resp.data : null;
                if (!data) throw new Error('no answer');
                this.drift = driftFrom(data);
            } catch (err) {
                this.drift = unavailableDrift();
            }
        },

        async recomputeNow() {
            if (this.recomputing) return;
            this.recomputing = true;
            this.recomputeFailed = false;
            this.statusLine = RECALCULATING_LINE;
            try {
                await Intelligence.recompute();
            } catch (err) {
                this.recomputing = false;
                if (Intelligence.failureStatus(err) === 409) {
                    this.statusLine = Intelligence.BUSY_LINE;
                } else {
                    this.statusLine = Intelligence.ERROR_LINE;
                    this.recomputeFailed = true;
                }
                return;
            }
            this.recomputing = false;
            await this.load(true);
            if (this.failed) {
                this.statusLine = '';
                return;
            }
            this.statusLine = this.state === 'not_computed' ? NOT_WORKED_OUT_LINE : FINISHED_LINE;
            Intelligence.keepPlace(this.$refs.statusRegion, this.showRecompute);
        }
    };
}
window.workedOutConnections = workedOutConnections;
