/**
 * ARCH-064 — lazy loading for the capability map's mapping dialogs.
 *
 * Five dialogs (mapping-modal, acm-mapping-modal, process-mapping-modal,
 * apqc-mapping-modal, archimate-mapping-modal) used to be rendered into the
 * page on every load even though all five start closed. They are now fetched
 * from `capability_map.mapping_modal_partial` the first time something needs
 * one, and injected into #lazy-modal-host — which lives inside the page's
 * Alpine root, so the injected `@click` handlers resolve in exactly the scope
 * they resolved in before.
 *
 * Two details that are easy to get wrong:
 *  - Markup inserted with innerHTML never executes its <script> tags, and the
 *    APQC / ArchiMate dialogs define their own Alpine component functions in an
 *    inline script. Those scripts are therefore lifted out and executed FIRST,
 *    before the markup is inserted, or Alpine would walk an `x-data` naming a
 *    function that does not exist yet.
 *  - Alpine initialises injected nodes through its MutationObserver, not
 *    synchronously. `Alpine.nextTick()` is awaited so callers that reach for
 *    `Alpine.$data(el)` get an initialised component.
 */
(function (global) {
    'use strict';

    var HOST_ID = 'lazy-modal-host';
    var inFlight = {};

    function host() {
        return document.getElementById(HOST_ID);
    }

    function partialUrl(modalId) {
        var el = host();
        if (!el || !el.dataset.partialUrl) {
            return null;
        }
        return el.dataset.partialUrl.replace('__VARIANT__', encodeURIComponent(modalId));
    }

    function runScripts(fragment) {
        var scripts = fragment.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            var original = scripts[i];
            var replacement = document.createElement('script');
            for (var a = 0; a < original.attributes.length; a++) {
                replacement.setAttribute(original.attributes[a].name, original.attributes[a].value);
            }
            replacement.textContent = original.textContent;
            original.parentNode.removeChild(original);
            document.head.appendChild(replacement);
        }
    }

    function alpineSettled() {
        if (global.Alpine && typeof global.Alpine.nextTick === 'function') {
            return global.Alpine.nextTick();
        }
        return Promise.resolve();
    }

    async function fetchAndInject(modalId) {
        var url = partialUrl(modalId);
        if (!url) {
            throw new Error('Lazy modal host is missing; cannot load ' + modalId);
        }
        var resp = await fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) {
            throw new Error('Failed to load ' + modalId + ' (HTTP ' + resp.status + ')');
        }
        var html = await resp.text();

        var holder = document.createElement('template');
        holder.innerHTML = html;
        runScripts(holder.content);
        host().appendChild(holder.content);

        await alpineSettled();
        if (global.lucide && typeof global.lucide.createIcons === 'function') {
            global.lucide.createIcons();
        }
        return document.getElementById(modalId);
    }

    /**
     * Resolve with the dialog's root element, loading it if it is not in the
     * DOM yet. Concurrent callers share one request.
     *
     * Resolves with `null` — after telling the user through Platform.toast —
     * when the fragment cannot be loaded. It does not
     * reject: every caller is an `@click` handler, so a rejection would surface
     * only as an unhandled promise. Callers MUST check the result and return
     * rather than operating on a dialog that is not there.
     */
    function ensure(modalId) {
        var existing = document.getElementById(modalId);
        if (existing) {
            return Promise.resolve(existing);
        }
        if (inFlight[modalId]) {
            return inFlight[modalId];
        }
        inFlight[modalId] = fetchAndInject(modalId).catch(function (err) {
            delete inFlight[modalId];
            if (global.Platform && global.Platform.toast) {
                global.Platform.toast.error(
                    'The mapping dialog could not be loaded. Please try again.'
                );
            }
            return null;
        });
        return inFlight[modalId];
    }

    global.CapabilityMapModals = { ensure: ensure };
})(window);
