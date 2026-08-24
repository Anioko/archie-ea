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
      const response = await fetch(`/architecture-journey/work/${this.journeyId}/state`, {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
        },
        body: JSON.stringify(changes),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'The journey could not be saved.');
      return payload.data;
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
