/**
 * Issue Board Alpine.js Component
 * Handles Kanban-style issue management with filtering, sorting, and escalation
 */

function issueBoard() {
  return {
    issues: [],
    selectedIssue: null,
    showDetailModal: false,
    showCreateForm: false,
    filters: {
      priority: [],
      status: [],
      assignee: []
    },
    quickFilter: null,
    currentUserId: null,
    solutionId: null,

    /**
     * Initialize the component
     */
    async init() {
      // Get solution ID from page context
      this.solutionId = this.getSolutionIdFromUrl();
      this.currentUserId = this.getCurrentUserId();
      
      if (!this.solutionId) {
        console.warn('No solution ID found');
        return;
      }

      // Load issues
      await this.loadIssues();

      // Set up polling for real-time updates (every 5 seconds)
      this.setupPolling();
    },

    /**
     * Load issues from API
     */
    async loadIssues() {
      try {
        const response = await fetch(`/api/solutions/${this.solutionId}/issues`);
        if (response.ok) {
          this.issues = await response.json();
        }
      } catch (error) {
        console.error('Failed to load issues:', error);
      }
    },

    /**
     * Set up polling for real-time updates
     */
    setupPolling() {
      setInterval(() => {
        this.loadIssues();
      }, 5000);
    },

    /**
     * Get filtered issues for a specific status
     */
    getFilteredIssues(status) {
      return this.issues.filter(issue => {
        // Status filter
        if (issue.status !== status) {
          return false;
        }

        // Priority filter
        if (this.filters.priority.length > 0 && !this.filters.priority.includes(issue.priority)) {
          return false;
        }

        // Quick filters
        if (this.quickFilter === 'unresolved' && issue.status === 'RESOLVED') {
          return false;
        }

        if (this.quickFilter === 'mine' && issue.assigned_to_id !== this.currentUserId) {
          return false;
        }

        return true;
      });
    },

    /**
     * Get P0 issues for escalation timeline
     */
    getP0Issues() {
      return this.issues.filter(issue => issue.priority === 'P0' && issue.status !== 'RESOLVED');
    },

    /**
     * Toggle filter
     */
    toggleFilter(filterType, value) {
      if (this.filters[filterType].includes(value)) {
        this.filters[filterType] = this.filters[filterType].filter(v => v !== value);
      } else {
        this.filters[filterType].push(value);
      }
    },

    /**
     * Open issue detail view
     */
    openIssueDetail(issue) {
      this.selectedIssue = { ...issue };
      this.showDetailModal = true;
      document.getElementById('issue-detail-modal').hidden = false;
    },

    /**
     * Close issue detail modal
     */
    closeDetailModal() {
      this.showDetailModal = false;
      document.getElementById('issue-detail-modal').hidden = true;
    },

    /**
     * Transition issue to a new status
     */
    async transitionIssue(issue, newStatus) {
      try {
        const response = await fetch(
          `/api/solutions/${this.solutionId}/issues/${issue.id}`,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              status: newStatus
            })
          }
        );

        if (response.ok) {
          const updated = await response.json();
          // Update issue in list
          const index = this.issues.findIndex(i => i.id === issue.id);
          if (index !== -1) {
            this.issues[index] = updated;
            this.selectedIssue = { ...updated };
          }
        }
      } catch (error) {
        console.error('Failed to transition issue:', error);
      }
    },

    /**
     * Manually escalate an issue
     */
    async manuallyEscalate(issue) {
      try {
        const response = await fetch(
          `/api/solutions/${this.solutionId}/issues/${issue.id}/escalate`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            }
          }
        );

        if (response.ok) {
          const updated = await response.json();
          const index = this.issues.findIndex(i => i.id === issue.id);
          if (index !== -1) {
            this.issues[index] = updated;
            this.selectedIssue = { ...updated };
          }
        }
      } catch (error) {
        console.error('Failed to escalate issue:', error);
      }
    },

    /**
     * Get escalation progress percentage for P0 issues
     */
    getEscalationProgress(issue) {
      if (!issue.auto_escalate_if_not_resolved_by) {
        return 0;
      }

      const now = new Date();
      const created = new Date(issue.created_at);
      const escalateBy = new Date(issue.auto_escalate_if_not_resolved_by);

      const total = escalateBy - created;
      const elapsed = now - created;
      
      return Math.min(100, Math.max(0, (elapsed / total) * 100));
    },

    /**
     * Format date for display
     */
    formatDate(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    /**
     * Format date with time
     */
    formatDateFull(dateStr) {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    },

    /**
     * Get age text (e.g., "3 days old")
     */
    getAgeText(dateStr, resolved = false) {
      if (!dateStr) return 'Unknown';

      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now - date;
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

      if (diffDays > 0) {
        return resolved ? `${diffDays}d ago` : `${diffDays}d old`;
      }
      return resolved ? `${diffHours}h ago` : `${diffHours}h old`;
    },

    /**
     * Get solution ID from URL
     */
    getSolutionIdFromUrl() {
      const match = window.location.pathname.match(/\/solutions\/(\d+)/);
      return match ? match[1] : null;
    },

    /**
     * Get current user ID
     */
    getCurrentUserId() {
      // This would come from the page or session
      const userElement = document.querySelector('[data-user-id]');
      return userElement ? parseInt(userElement.getAttribute('data-user-id')) : null;
    }
  };
}

// Register the component with Alpine
if (typeof Alpine !== 'undefined') {
  Alpine.data('issueBoard', issueBoard);
}
