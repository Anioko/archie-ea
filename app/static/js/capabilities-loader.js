/**
 * Capability Mapping Data Loader
 * Shared module for loading and rendering capability data across pages
 *
 * Pattern: Fetch from /api/v1/mappings/* endpoints and render with common UI
 */

class CapabilityLoader {
  constructor(options = {}) {
    this.apiBaseUrl = options.apiBaseUrl || '/api/v1/mappings';
    this.debug = options.debug || false;
  }

  log(msg, data) {
    if (this.debug) {

    }
  }

  /**
   * Fetch capabilities from API
   * @param {string} endpoint - API endpoint (e.g., 'technical-to-vendor')
   * @param {object} params - Query parameters
   * @returns {Promise<Array>}
   */
  async fetchCapabilities(endpoint, params) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const url = `${this.apiBaseUrl}/${endpoint}?${queryString}`;
      this.log(`Fetching: ${url}`);

      const response = await fetch(url, {
        headers: { 'Accept': 'application/json' }
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      const mappings = data.data || data.mappings || [];
      this.log(`Fetched ${mappings.length} records`);
      return mappings;
    } catch (error) {
      this.log('Error fetching:', error);
      throw error;
    }
  }

  /**
   * Render capability grid (for detail/tab views)
   * @param {Array} mappings - Capability mapping data
   * @param {object} options - Render options
   * @returns {HTMLElement}
   */
  renderCapabilityGrid(mappings, options = {}) {
    const {
      groupBy = 'coverage_type', // coverage_type or none
      showProgress = true,
      showNotes = true
    } = options;

    const container = document.createElement('div');

    if (!mappings || mappings.length === 0) {
      safeHTML(container, `
        <div class="text-center py-8">
          <i data-lucide="target" class="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50"></i>
          <h4 class="text-lg font-semibold text-foreground mb-2">No capabilities mapped</h4>
          <p class="text-muted-foreground text-sm">No capability data available.</p>
        </div>
      `);
      return container;
    }

    if (groupBy === 'coverage_type') {
      const grouped = this.groupByCoverageType(mappings);
      Object.entries(grouped).forEach(([coverage, items]) => {
        const section = this.renderCoverageSection(coverage, items, { showProgress, showNotes });
        container.appendChild(section);
      });
    } else {
      const grid = this.renderCapabilityItems(mappings, { showProgress, showNotes });
      container.appendChild(grid);
    }

    // Reinit lucide icons if available
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }

    return container;
  }

  /**
   * Group mappings by coverage type
   * @param {Array} mappings
   * @returns {object}
   */
  groupByCoverageType(mappings) {
    const grouped = {};
    mappings.forEach(m => {
      const coverage = m.coverage_type || 'unknown';
      if (!grouped[coverage]) grouped[coverage] = [];
      grouped[coverage].push(m);
    });
    return grouped;
  }

  /**
   * Render section for a coverage type
   * @param {string} coverage - Coverage type (core/supporting/optional)
   * @param {Array} items - Capability items
   * @param {object} options
   * @returns {HTMLElement}
   */
  renderCoverageSection(coverage, items, options = {}) {
    const { showProgress = true, showNotes = true } = options;

    const coverageColors = {
      'core': 'text-emerald-700 bg-emerald-500/5 border-emerald-200',
      'supporting': 'text-primary bg-primary/5 border-primary/20',
      'optional': 'text-foreground bg-muted/30 border-border'
    };
    const colors = coverageColors[coverage] || 'text-foreground bg-muted/30 border-border';

    const section = document.createElement('div');
    section.className = `border rounded-lg p-4 ${colors}`;

    const title = document.createElement('h4');
    title.className = 'font-semibold mb-3 capitalize';
    title.textContent = `${coverage} Capabilities`;
    section.appendChild(title);

    const grid = this.renderCapabilityItems(items, options);
    section.appendChild(grid);

    return section;
  }

  /**
   * Render grid of capability items
   * @param {Array} items
   * @param {object} options
   * @returns {HTMLElement}
   */
  renderCapabilityItems(items, options = {}) {
    const { showProgress = true, showNotes = true } = options;

    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3';

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'p-3 rounded border border-inherit bg-background/50';

      let html = `
        <div class="flex justify-between items-start mb-2">
          <p class="font-medium text-sm">${this.escapeHtml(item.capability_name || item.capability || 'Unknown')}</p>
        </div>
        <div class="space-y-1 text-xs">
      `;

      if (item.fit_score !== undefined) {
        html += `
          <div class="flex justify-between">
            <span>Fit Score:</span>
            <strong>${item.fit_score}/100</strong>
          </div>
        `;
      }

      if (item.maturity_level !== undefined) {
        html += `
          <div class="flex justify-between">
            <span>Maturity:</span>
            <strong>Level ${item.maturity_level}/5</strong>
          </div>
        `;
      }

      if (showProgress && item.coverage_percentage !== undefined) {
        html += `
          <div class="flex justify-between mb-1">
            <span>Coverage:</span>
            <strong>${item.coverage_percentage}%</strong>
          </div>
          <div class="w-full bg-muted rounded-full h-1.5">
            <div class="bg-primary h-1.5 rounded-full" style="width: ${item.coverage_percentage}%"></div>
          </div>
        `;
      }

      if (showNotes && item.notes) {
        html += `<p class="text-muted-foreground italic mt-2">${this.escapeHtml(item.notes)}</p>`;
      }

      html += '</div>';
      (window.safeHTML || function(el, h) { el.innerHTML = h; })(card, html);
      grid.appendChild(card);
    });

    return grid;
  }

  /**
   * Load and display capability counts as badges (for list pages)
   * @param {string} selector - CSS selector for badge elements
   * @param {string} endpoint - API endpoint
   * @param {function} idGetter - Function to get ID from element
   */
  async loadBadgeCounts(selector, endpoint, idGetter = (el) => el.getAttribute('data-app-id')) {
    const badges = document.querySelectorAll(selector);

    for (const badge of badges) {
      const id = idGetter(badge);
      if (!id) continue;

      try {
        const mappings = await this.fetchCapabilities(endpoint, { application_id: id });

        const counts = { 'core': 0, 'supporting': 0, 'optional': 0 };
        mappings.forEach(m => {
          const coverage = m.coverage_type || 'optional';
          counts[coverage]++;
        });

        (window.safeHTML || function(el, h) { el.innerHTML = h; })(badge, this.formatBadgeCounts(counts));
      } catch (error) {
        this.log('Badge load error:', error);
        (window.safeHTML || function(el, h) { el.innerHTML = h; })(badge, '<span class="text-muted-foreground/60">—</span>');
      }
    }

    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }
  }

  /**
   * Format counts as badge HTML
   * @param {object} counts - { core, supporting, optional }
   * @returns {string}
   */
  formatBadgeCounts(counts) {
    const total = counts.core + counts.supporting + counts.optional;

    if (total === 0) {
      return '<span class="text-muted-foreground/60">None</span>';
    }

    let html = '';
    if (counts.core > 0) html += `<span class="text-emerald-700 font-semibold">${counts.core}</span>`;
    if (counts.supporting > 0) html += `${html ? ' ' : ''}<span class="text-primary">${counts.supporting}</span>`;
    if (counts.optional > 0) html += `${html ? ' ' : ''}<span class="text-muted-foreground">${counts.optional}</span>`;

    return html;
  }

  /**
   * Escape HTML to prevent XSS
   * @param {string} text
   * @returns {string}
   */
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }
}

// Initialize global instance
const capabilityLoader = new CapabilityLoader();
