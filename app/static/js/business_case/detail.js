/**
 * Alpine component for the Business Case document view.
 *
 * Mirrors the businessModelCanvas pattern (app/templates/business_model/detail.html):
 *   - Free-text/number sections are saved individually on blur via
 *     POST {fieldApiUrl} { field, value }.
 *   - Status + link selects are saved together via
 *     POST {updateApiUrl} { status, capability_id, strategic_initiative_id, solution_id }.
 *   - "Pull financials from links" calls {pullFinancialsApiUrl} and merges any
 *     newly-populated financial fields back into the form.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('businessCaseDetail', (config) => ({
    businessCaseId: config.businessCaseId,
    fields: config.fields || {},
    status: config.status || 'draft',
    capabilityId: config.capabilityId ?? '',
    strategicInitiativeId: config.strategicInitiativeId ?? '',
    solutionId: config.solutionId ?? '',
    fieldApiUrl: config.fieldApiUrl,
    updateApiUrl: config.updateApiUrl,
    pullFinancialsApiUrl: config.pullFinancialsApiUrl,
    draftSectionApiUrl: config.draftSectionApiUrl,

    savingField: null,
    savedField: null,
    savingMeta: false,
    pullingFinancials: false,
    draftingSection: null,
    draftError: null,
    draftErrorMessage: '',

    csrfToken() {
      return document.querySelector('meta[name=csrf-token]')?.content || '';
    },

    async saveField(fieldKey) {
      this.savingField = fieldKey;
      this.savedField = null;
      try {
        const resp = await fetch(this.fieldApiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken()
          },
          body: JSON.stringify({ field: fieldKey, value: this.fields[fieldKey] ?? '' })
        });
        const json = await resp.json();
        if (!resp.ok || !json.success) {
          throw new Error((json.error && json.error.message) || 'Failed to save field');
        }
        this.savedField = fieldKey;
        setTimeout(() => { if (this.savedField === fieldKey) this.savedField = null; }, 1500);
      } catch (e) {
        if (window.Platform && Platform.toast) {
          Platform.toast.error(e.message || 'Failed to save field');
        }
      } finally {
        this.savingField = null;
      }
    },

    async saveMeta() {
      this.savingMeta = true;
      try {
        const resp = await fetch(this.updateApiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken()
          },
          body: JSON.stringify({
            status: this.status,
            capability_id: this.capabilityId || null,
            strategic_initiative_id: this.strategicInitiativeId || null,
            solution_id: this.solutionId || null
          })
        });
        const json = await resp.json();
        if (!resp.ok || !json.success) {
          throw new Error((json.error && json.error.message) || 'Failed to update business case');
        }
        if (window.Platform && Platform.toast) {
          Platform.toast.success('Business case updated');
        }
      } catch (e) {
        if (window.Platform && Platform.toast) {
          Platform.toast.error(e.message || 'Failed to update business case');
        }
      } finally {
        this.savingMeta = false;
      }
    },

    async pullFinancials() {
      this.pullingFinancials = true;
      try {
        const resp = await fetch(this.pullFinancialsApiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken()
          }
        });
        const json = await resp.json();
        if (!resp.ok || !json.success) {
          throw new Error((json.error && json.error.message) || 'Failed to pull financials');
        }
        const data = json.data ?? json;
        const businessCase = data.business_case || {};
        const applied = (data.aggregation && data.aggregation.applied_fields) || [];

        ['capex', 'opex_annual', 'tco_3yr', 'roi_percentage', 'financial_benefit_annual', 'payback_months'].forEach((key) => {
          if (businessCase[key] !== undefined && businessCase[key] !== null) {
            this.fields[key] = businessCase[key];
          }
        });

        if (window.Platform && Platform.toast) {
          if (applied.length) {
            Platform.toast.success(`Pulled financials from links: ${applied.join(', ')}`);
          } else {
            Platform.toast.info('No new figures found on the linked capability, initiative, or solution.');
          }
        }
      } catch (e) {
        if (window.Platform && Platform.toast) {
          Platform.toast.error(e.message || 'Failed to pull financials');
        }
      } finally {
        this.pullingFinancials = false;
      }
    },

    // Advisory only: drafts content into the section's existing textarea
    // (fields[sectionKey]) but never saves it — the user still saves via
    // the existing saveField() blur handler above.
    async draftSection(sectionKey) {
      this.draftingSection = sectionKey;
      this.draftError = null;
      try {
        const resp = await fetch(this.draftSectionApiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken()
          },
          body: JSON.stringify({ section: sectionKey })
        });
        const json = await resp.json();
        if (!resp.ok) {
          throw new Error(json.error || 'Failed to draft section');
        }
        this.fields[sectionKey] = json.draft.content;
      } catch (e) {
        this.draftError = sectionKey;
        this.draftErrorMessage = e.message || 'Failed to draft section';
        if (window.Platform && Platform.toast) {
          Platform.toast.error(this.draftErrorMessage);
        }
      } finally {
        this.draftingSection = null;
      }
    }
  }));
});
