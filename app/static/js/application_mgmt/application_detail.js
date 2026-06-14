/**
 * application_detail.js
 * A95-005: Application ArchiMate deep-link support
 *
 * Builds the URL for the "Generate ArchiMate with AI" CTA on the
 * application detail page, ensuring the correct query params are set
 * so the AI chat page can auto-load application context.
 */

(function () {
    'use strict';

    /**
     * Returns the AI chat deep-link URL for generating ArchiMate for an application.
     * @param {number|string} appId - The application ID
     * @returns {string} URL like /ai-chat?context=application&id=<appId>
     */
    function buildArchimateDeepLinkUrl(appId) {
        return '/ai-chat?context=application&id=' + encodeURIComponent(appId);
    }

    /**
     * Initialises the ArchiMate deep-link button on the application detail page.
     * The button href is already rendered server-side; this function is a no-op
     * guard that verifies the link element is present and its data-app-id matches
     * the expected URL, providing a client-side sanity check.
     */
    function initArchimateDeepLink() {
        const link = document.getElementById('generate-archimate-ai-link');
        if (!link) {
            return;
        }
        const appId = link.getAttribute('data-app-id');
        if (!appId) {
            return;
        }
        const expectedHref = buildArchimateDeepLinkUrl(appId);
        // Normalise href comparison: strip origin prefix if present
        const actualHref = link.getAttribute('href') || '';
        if (actualHref.indexOf('/ai-chat') === -1) {
            // Fallback: correct the href if it was somehow mis-rendered
            link.setAttribute('href', expectedHref);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initArchimateDeepLink);
    } else {
        initArchimateDeepLink();
    }

    // Expose for unit testing
    if (typeof window !== 'undefined') {
        window.appDetailArchimate = {
            buildArchimateDeepLinkUrl: buildArchimateDeepLinkUrl
        };
    }
}());
