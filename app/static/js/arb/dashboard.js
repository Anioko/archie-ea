/**
 * arb/dashboard.js
 * Alpine.js component factory for the "Create ARB Review" modal.
 * Capability-based governance: decision_sought, capability impacts, application linkage.
 */

function arbReviewCreateModal() {
  return {
    formData: {
      title: '',
      description: '',
      review_type: '',
      decision_sought: '',
      alternatives_considered: '',
      togaf_phase: '',
      archimate_layer: '',
      priority: 'medium',
      business_impact: 'medium',
      estimated_effort: 'medium',
      solution_id: '',
      adr_id: '',
      architecture_model_id: '',
      application_ids: [],
      capability_ids: [],
      capability_impact_type: 'modifies'
    },
    formOptions: {
      solutions: [],
      review_types: [],
      loadError: false,
      adrs: [],
      architecture_models: [],
      applications: [],
      capabilities: [],
      decision_types: [],
      impact_types: [],
      capability_required_review_types: []
    },
    formDataLoaded: false,
    submitting: false,
    errorMsg: '',

    init() {
      this.loadFormData();
    },

    isCapabilityRequired() {
      const rt = this.formData.review_type;
      return rt && this.formOptions.capability_required_review_types.indexOf(rt) >= 0;
    },

    loadFormData() {
      const url = window.__ARB_CONFIG__?.formDataUrl;
      if (!url || this.formDataLoaded) return;
      fetch(url, {
        method: 'GET',
        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' }
      })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            this.formOptions.solutions = data.solutions || [];
            this.formOptions.review_types = data.review_types || [];
            this.formOptions.adrs = data.adrs || [];
            this.formOptions.architecture_models = data.architecture_models || [];
            this.formOptions.capabilities = data.capabilities || [];
            this.formOptions.applications = data.applications || [];
            this.formOptions.decision_types = data.decision_types || [];
            this.formOptions.impact_types = data.impact_types || [{ value: 'modifies', label: 'Modifies' }];
            this.formOptions.capability_required_review_types = data.capability_required_review_types || [];
            if (data.impact_types && data.impact_types.length > 0) {
              this.formData.capability_impact_type = data.impact_types[0].value;
            }
            this.formDataLoaded = true;
          }
        })
        .catch(() => {
          this.formOptions.loadError = true;
          this.errorMsg = 'Failed to load form options. Please refresh.';
        });
    },

    submitCreateReview() {
      // FAR-017: Prevent double-click duplicates
      if (this.submitting) return;
      if (!this.formData.title.trim()) { this.errorMsg = 'Title is required.'; return; }
      if (!this.formData.review_type) { this.errorMsg = 'Review type is required.'; return; }
      if (!this.formData.decision_sought) { this.errorMsg = 'Decision sought is required.'; return; }
      const capIds = Array.isArray(this.formData.capability_ids)
        ? this.formData.capability_ids.map(id => parseInt(id, 10)).filter(n => !isNaN(n))
        : [];
      if (this.isCapabilityRequired() && capIds.length === 0) {
        this.errorMsg = 'At least one capability is required for this review type.';
        return;
      }
      this.submitting = true;
      this.errorMsg = '';
      const url = window.__ARB_CONFIG__?.createReviewUrl || '/arb/reviews/create';
      const impactType = this.formData.capability_impact_type || 'modifies';
      const capability_impacts = capIds.map(capId => ({
        capability_id: capId,
        impact_type: impactType,
        impact_level: 'medium'
      }));
      const appIds = Array.isArray(this.formData.application_ids)
        ? this.formData.application_ids.map(id => parseInt(id, 10)).filter(n => !isNaN(n))
        : [];
      const payload = {
        title: this.formData.title.trim(),
        description: this.formData.description?.trim() || '',
        review_type: this.formData.review_type,
        decision_sought: this.formData.decision_sought || null,
        alternatives_considered: this.formData.alternatives_considered?.trim() || null,
        togaf_phase: this.formData.togaf_phase || null,
        archimate_layer: this.formData.archimate_layer || null,
        priority: this.formData.priority,
        business_impact: this.formData.business_impact,
        estimated_effort: this.formData.estimated_effort,
        solution_id: this.formData.solution_id ? parseInt(this.formData.solution_id, 10) : null,
        adr_id: this.formData.adr_id ? parseInt(this.formData.adr_id, 10) : null,
        architecture_model_id: this.formData.architecture_model_id ? parseInt(this.formData.architecture_model_id, 10) : null,
        application_ids: appIds,
        capability_impacts: capability_impacts,
        capability_impact_type: impactType
      };
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify(payload)
      })
        .then(r => r.json())
        .then(data => {
          this.submitting = false;
          if (!data.success) {
            this.errorMsg = Object.values(data.errors || {}).join(' ') || (data.error || 'An error occurred.');
            return;
          }
          Platform.modal.close('create-arb-review');
          if (typeof showToast === 'function') {
            showToast({ title: 'Review submitted successfully', variant: 'default' });
          }
          setTimeout(() => window.location.reload(), 800);
        })
        .catch(() => {
          this.submitting = false;
          this.errorMsg = 'Network error. Please try again.';
        });
    }
  };
}

document.addEventListener('alpine:init', () => {
  if (window.Alpine) {
    window.Alpine.data('arbReviewCreateModal', arbReviewCreateModal);
  }
});

window.arbReviewCreateModal = arbReviewCreateModal;
