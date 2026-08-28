document.addEventListener('alpine:init', () => {
  Alpine.data('architectureJourneyWorkspace', (journeyId, initialEvidence, initialStage) => ({
    journeyId,
    evidence: Array.isArray(initialEvidence) ? initialEvidence : [],
    currentStage: initialStage || 'frame',
    evidenceName: '',
    evidenceReference: '',
    saving: false,
    savingEvidence: false,
    error: '',
    stages: [
      { key: 'frame', label: 'Frame', guidance: 'Agree the purpose, decision and boundaries.' },
      { key: 'discover', label: 'Discover', guidance: 'Gather evidence and map the current state.' },
      { key: 'shape', label: 'Shape', guidance: 'Create options and the architecture needed to compare them.' },
      { key: 'decide', label: 'Decide', guidance: 'Record trade-offs, assurance and the chosen direction.' },
      { key: 'deliver', label: 'Deliver', guidance: 'Publish the outputs and hand off the next action.' },
    ],

    get stageIndex() {
      const index = this.stages.findIndex((stage) => stage.key === this.currentStage);
      return index < 0 ? 0 : index;
    },
    get stageLabel() { return this.stages[this.stageIndex].label; },
    get stageGuidance() { return this.stages[this.stageIndex].guidance; },

    async save(changes) {
      // Platform.fetch automatically injects CSRF token for PATCH, serialises plain objects to JSON,
      // and throws a structured PlatformError on non-ok responses.
      // The existing error handling remains unchanged: we catch the error and surface it to the user.
      try {
        const data = await Platform.fetch.patch(`/architecture-journey/work/${this.journeyId}/state`, changes, { silent: true });
        // Platform.fetch returns the parsed response body directly.
        // The original code expected payload.data; we preserve that expectation.
        return data.data;
      } catch (error) {
        // The original code threw an Error with payload.error or a default message.
        // Platform.fetch throws a PlatformError with a message property.
        // We rethrow an Error with the same message to keep the existing error handling.
        throw new Error(error.message || 'The journey could not be saved.');
      }
    },

    async advance() {
      if (this.saving || this.stageIndex >= this.stages.length - 1) return;
      this.saving = true;
      this.error = '';
      const next = this.stages[this.stageIndex + 1].key;
      try {
        await this.save({ current_stage: next });
        this.currentStage = next;
      } catch (error) {
        this.error = error.message || 'The journey could not be saved.';
      } finally {
        this.saving = false;
      }
    },

    // ── linking records ──────────────────────────────────────────────────
    // A link points at a record that already exists elsewhere. The form never
    // sends an organisation or an author: the server takes both from the session,
    // because a caller who can name the tenant can write into someone else's.
    linkEntityType: 'decision',
    linkEntityId: '',
    linkRelation: 'references',
    savingLink: false,
    linkNotice: '',

    async addLink() {
      if (this.savingLink) return;
      const entityId = parseInt(this.linkEntityId, 10);
      if (!Number.isInteger(entityId) || entityId <= 0) {
        // Said here rather than after a round trip: a 0 or a negative points at no
        // row, and would render as a broken reference that looks like a real one.
        this.error = 'Enter the numeric id of an existing record.';
        return;
      }
      this.savingLink = true;
      this.error = '';
      this.linkNotice = '';
      try {
        await Platform.fetch.post(
          `/architecture-journey/work/${this.journeyId}/links`,
          { entity_type: this.linkEntityType, entity_id: entityId, relation: this.linkRelation },
          { silent: true },
        );
        // The counts are rendered server-side, so the page is reloaded rather than
        // incremented in place. Adjusting a number locally would show a count the
        // server has not confirmed -- the exact class of claim this screen exists
        // to avoid making.
        window.location.reload();
      } catch (error) {
        this.error = error.message || 'That record could not be linked.';
      } finally {
        this.savingLink = false;
      }
    },

    async addEvidence() {
      if (this.savingEvidence || !this.evidenceName || !this.evidenceReference) return;
      this.savingEvidence = true;
      this.error = '';
      const nextEvidence = [...this.evidence, {
        kind: 'document_reference',
        name: this.evidenceName,
        reference: this.evidenceReference,
      }];
      try {
        await this.save({ evidence_manifest: nextEvidence });
        this.evidence = nextEvidence;
        this.evidenceName = '';
        this.evidenceReference = '';
      } catch (error) {
        this.error = error.message || 'The evidence could not be attached.';
      } finally {
        this.savingEvidence = false;
      }
    },
  }));
});
