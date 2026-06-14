/**
 * arb/review_detail.js
 * ARB review detail page — AI assessment trigger.
 * Reads the assess URL from window.__ARB_CONFIG__.assessReviewUrl.
 */

async function assessReview() {
    const url = window.__ARB_CONFIG__?.assessReviewUrl;
    if (!url) {
        console.error('[arb/review_detail] assessReviewUrl not set in __ARB_CONFIG__');
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
        console.error('[arb/review_detail] Error:', error);
        Platform.toast.error('Error assessing review');
    }
}

window.assessReview = assessReview;
