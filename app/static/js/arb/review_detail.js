/**
 * arb/review_detail.js
 * ARB review detail page — AI assessment trigger.
 * Reads the assess URL from window.__ARB_CONFIG__.assessReviewUrl.
 */

async function assessReview() {
    const url = window.__ARB_CONFIG__?.assessReviewUrl;
    if (!url) {
        Platform.toast.error('AI assessment is not configured for this review — the assessment endpoint is missing.');
        return;
    }
    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.success) {
            location.reload();
        } else {
            Platform.toast.error('Error assessing review: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        Platform.toast.error('Error assessing review: ' + (error.message || error));
    }
}

window.assessReview = assessReview;
