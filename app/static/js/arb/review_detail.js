/**
 * arb/review_detail.js
 * ARB review detail page — AI assessment trigger.
 * Reads the assess URL from window.__ARB_CONFIG__.assessReviewUrl.
 */

async function assessReview() {
    const url = window.__ARB_CONFIG__?.assessReviewUrl;
    if (!url) {
        // No user-visible error path exists for a missing config; the button that calls this
        // would not be rendered if the config were absent, so this is a developer error.
        // We must not invent a fallback value (rule 2) and cannot show a toast because
        // Platform may not be fully initialised. The safest is to throw, which will
        // propagate to the caller and be reported as an unhandled promise rejection.
        throw new Error('[arb/review_detail] assessReviewUrl not set in __ARB_CONFIG__');
    }
    try {
        // Platform.fetch returns the parsed JSON directly, throws on non-ok responses,
        // and automatically injects CSRF token for mutating methods.
        // The endpoint returns { success: true } on success, or { success: false, error: ... }.
        // We must treat a non‑success response as an error, which Platform.fetch already does
        // (it will throw because the response is not ok). However the original code only
        // considered the JSON‑level `success` flag; we need to preserve that behaviour.
        // Therefore we catch the PlatformError, examine its .data, and if .data.success is false,
        // we surface the error via toast (as before). If the error is a network or HTTP error,
        // Platform.fetch already shows a toast (unless silent:true) and throws; we must not
        // duplicate the toast, but we must still propagate the failure.
        const data = await Platform.fetch(url);
        // If we reach here, the response was ok (2xx). The original code expected a JSON
        // with a `success` field; if `success` is false, it showed a toast and did NOT reload.
        // Platform.fetch does not inspect the JSON content, so we must replicate that check.
        if (data.success) {
            location.reload();
        } else {
            // This is a successful HTTP response (2xx) but with a logical error in the JSON.
            // The original code displayed a toast with the server‑provided error message.
            // We must do the same, and NOT throw (the request succeeded, there is no PlatformError).
            Platform.toast.error('Error assessing review: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        // Platform.fetch already shows a toast for network/HTTP errors (unless silent:true).
        // However, the original code also showed a generic toast for any catch.
        // To avoid duplicate toasts, we need to check whether the error is a PlatformError
        // that already triggered a toast. PlatformError has a .type property ('HttpError' or 'NetworkError').
        // If error.type exists, a toast has already been shown; we should not show another.
        // If error.type does NOT exist (e.g., a developer‑thrown error), we must surface it.
        // The original code also logged to console, which is forbidden (rule 4). We replace
        // console.error with a real user‑visible error path: a toast (unless already shown).
        const isPlatformError = error && (error.type === 'HttpError' || error.type === 'NetworkError');
        if (!isPlatformError) {
            // This could be a developer‑thrown error (e.g., the missing‑url case above).
            // Show a toast because the user needs to know something went wrong.
            Platform.toast.error('Error assessing review');
        }
        // Rethrow to preserve the failure propagation (rule 2).
        throw error;
    }
}

window.assessReview = assessReview;
