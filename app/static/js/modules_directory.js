/* All-modules directory (/modules) — client-side filter.
 *
 * The page's own subtitle has always promised "grouped and searchable" while
 * shipping no search control at all. This registers the Alpine component that
 * makes that true. Purely client-side: every link is already in the DOM, so
 * filtering is a visibility decision, never a fetch.
 *
 * Registered on `alpine:init` so it exists before Alpine compiles the page.
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('modulesDirectory', () => ({
        q: '',

        /** True when `label` should stay visible for the current query. */
        matches(label) {
            const needle = this.q.trim().toLowerCase();
            if (!needle) return true;
            return String(label).toLowerCase().includes(needle);
        },

        /** True when at least one label in a section survives the filter, so an
         *  empty section heading is never left stranded above nothing. */
        anySection(labels) {
            return labels.some((label) => this.matches(label));
        },

        /** Count of links currently shown — read from the real label list the
         *  template passes in, never a hardcoded number. */
        shownCount(labels) {
            return labels.filter((label) => this.matches(label)).length;
        },

        clear() {
            this.q = '';
        },
    }));
});
