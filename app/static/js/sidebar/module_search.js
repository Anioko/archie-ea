/*
 * Sidebar "Search navigation..." -> all modules.
 *
 * The box used to filter only the links already rendered in the persona's own zones, so a working
 * page that lives in /modules/ (Impact Analysis, for a Solution Architect) could not be found by name.
 * /api/sidebar/search already returns `type: "module"` hits built from visible_module_links() (the
 * list /modules/ renders, minus anything the user is barred from); the Ctrl-K modal uses it. This asks
 * the same endpoint, so there is one index and one visibility rule.
 *
 * Behaviour, each pinned by tests/journeys/test_journey_sidebar_module_search.py:
 *   - under 2 characters: no request (the endpoint answers 400 below that);
 *   - typing is debounced to one request for the final query;
 *   - a slow earlier response never overwrites a newer one;
 *   - a failed request is reported as `error`, never as "no results".
 */
(function (root) {
    'use strict';

    var MIN_LENGTH = 2;
    var DEFAULT_DELAY_MS = 250;

    function create(options) {
        var fetchJson = options.fetchJson;
        var onChange = options.onChange;
        var delay = options.delay === undefined ? DEFAULT_DELAY_MS : options.delay;
        var timer = null;
        var latest = 0;

        function publish(query, results, loading, error) {
            onChange({ query: query, results: results, loading: loading, error: error });
        }

        function search(raw) {
            var query = (raw || '').trim();
            clearTimeout(timer);
            var ticket = ++latest;
            if (query.length < MIN_LENGTH) {
                publish(query, [], false, false);
                return;
            }
            publish(query, [], true, false);
            timer = setTimeout(function () {
                Promise.resolve()
                    .then(function () { return fetchJson(query); })
                    .then(function (body) {
                        if (ticket !== latest) return;
                        var modules = ((body && body.results) || [])
                            .filter(function (hit) { return hit.type === 'module'; })
                            .map(function (hit) { return { name: hit.name, url: hit.url }; });
                        publish(query, modules, false, false);
                    })
                    .catch(function () {
                        if (ticket !== latest) return;
                        publish(query, [], false, true);
                    });
            }, delay);
        }

        return { search: search };
    }

    root.SidebarModuleSearch = { create: create };
})(window);
