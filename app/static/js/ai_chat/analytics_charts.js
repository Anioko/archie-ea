/**
 * AI Chat Analytics Dashboard — Alpine.js component.
 *
 * Fetches /ai-chat/admin/analytics/data?days=N and populates
 * stat cards, tables, and CSS-based bar charts.  No external
 * chart library required.
 */

/* global Alpine */
function aiChatAnalytics() {
  return {
    days: "30",
    loading: true,
    error: null,
    data: {
      total_messages: 0,
      positive_pct: 0,
      active_users: 0,
      avg_response_time_ms: 0,
      feedback_summary: { total_positive: 0, total_negative: 0, by_domain: {} },
      usage_by_domain: [],
      usage_by_persona: [],
      provider_stats: [],
      daily_usage: [],
      top_templates: [],
    },

    /** Bootstrap: called once via x-init. */
    init() {
      this.fetchData();
    },

    /** Fetch analytics JSON for the selected date range. */
    async fetchData() {
      this.loading = true;
      this.error = null;
      try {
        let url = "/ai-chat/admin/analytics/data?days=" + encodeURIComponent(this.days);
        let resp = await fetch(url, {
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!resp.ok) {
          throw new Error("Server returned " + resp.status);
        }
        let json = await resp.json();
        // Ensure nested objects exist so templates never access properties of null
        json.feedback_summary = json.feedback_summary || { total_positive: 0, total_negative: 0, by_domain: {} };
        json.feedback_summary.by_domain = json.feedback_summary.by_domain || {};
        json.usage_by_domain = json.usage_by_domain || [];
        json.usage_by_persona = json.usage_by_persona || [];
        json.daily_usage = json.daily_usage || [];
        json.provider_stats = json.provider_stats || [];
        json.top_templates = json.top_templates || [];
        this.data = json;
      } catch (err) {
        this.error = "Failed to load analytics: " + err.message;
      } finally {
        this.loading = false;
      }
    },

    // ---------------------------------------------------------------
    // Helper methods for CSS bar charts
    // ---------------------------------------------------------------

    /**
     * Return the width percentage for a feedback bar segment.
     * @param {string} domain - Domain key from feedback_summary.by_domain.
     * @param {string} type   - "positive" or "negative".
     * @returns {number}
     */
    feedbackBarPct(domain, type) {
      let summary = this.data.feedback_summary || {};
      let byDomain = summary.by_domain || {};
      let info = byDomain[domain];
      if (!info) return 0;
      let total = info.positive + info.negative;
      if (total === 0) return 0;
      return Math.round((info[type] / total) * 100);
    },

    /**
     * Return the share % of a domain count relative to total messages.
     * @param {number} count
     * @returns {string}
     */
    domainSharePct(count) {
      if (!this.data.total_messages || this.data.total_messages === 0) return "0.0";
      return (count / this.data.total_messages * 100).toFixed(1);
    },

    /**
     * Return the height % for a daily bar relative to the max day count.
     * Minimum 2% so zero-count days still show a sliver.
     * @param {number} count
     * @returns {number}
     */
    dailyBarHeight(count) {
      let max = 0;
      let usage = this.data.daily_usage || [];
      for (let i = 0; i < usage.length; i++) {
        if (usage[i].count > max) {
          max = usage[i].count;
        }
      }
      if (max === 0) return 2;
      return Math.max(2, Math.round((count / max) * 100));
    },

    /**
     * Return the width % for a persona bar relative to the top persona count.
     * @param {number} count
     * @returns {number}
     */
    personaBarPct(count) {
      let personas = this.data.usage_by_persona || [];
      if (!personas.length) return 0;
      let max = personas[0].count; // already sorted desc
      if (max === 0) return 0;
      return Math.max(3, Math.round((count / max) * 100));
    },
  };
}
