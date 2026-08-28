document.addEventListener('alpine:init', () => {
  Alpine.data('architectureJourneyWorkspace', (journeyId, initialEvidence, initialStage, initialParticipants, canManageMembers) => ({
    journeyId,
    evidence: Array.isArray(initialEvidence) ? initialEvidence : [],
    participants: Array.isArray(initialParticipants) ? initialParticipants : [],
    canManageMembers: Boolean(canManageMembers),
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

    // ── participants ────────────────────────────────────────────────────
    // Names supplied by the read model are resolved live from users, never copied
    // into a journey membership row. Refresh the tenant directory for the picker
    // and as a fallback if an older deployment returns ids without display data.
    peopleDirectory: [],
    participantsLoading: false,
    memberQuery: '',
    memberResults: [],
    selectedMember: null,
    memberRole: 'contributor',
    memberPickerOpen: false,
    memberSearching: false,
    activeMemberIndex: -1,
    savingMember: false,

    async init() {
      if (this.canManageMembers) await this.loadPeopleDirectory();
    },

    async loadPeopleDirectory() {
      this.participantsLoading = true;
      try {
        const body = await Platform.fetch.get('/api/users', null, { silent: true });
        this.peopleDirectory = Array.isArray(body.users) ? body.users : [];
      } catch (error) {
        this.peopleDirectory = [];
        Platform.toast.error(error.message || 'Participant details could not be loaded.');
      } finally {
        this.participantsLoading = false;
      }
    },

    get participantCountLabel() {
      const count = this.participants.length;
      return `${count} ${count === 1 ? 'person' : 'people'}`;
    },

    participantDirectoryEntry(person) {
      return this.peopleDirectory.find((candidate) => candidate.id === person.user_id) || null;
    },

    participantName(person) {
      const entry = this.participantDirectoryEntry(person);
      return person.name || (entry && entry.name) || 'User unavailable';
    },

    participantEmail(person) {
      const entry = this.participantDirectoryEntry(person);
      return person.email || (entry && entry.email) || 'Account details unavailable';
    },

    participantInitials(person) {
      const name = this.participantName(person);
      if (name === 'User unavailable') return '—';
      return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
    },

    roleLabel(role) {
      return String(role || 'contributor').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
    },

    async searchMembers() {
      if (!this.peopleDirectory.length && !this.participantsLoading) await this.loadPeopleDirectory();
      this.memberSearching = true;
      this.memberPickerOpen = true;
      this.activeMemberIndex = -1;
      if (this.selectedMember && this.memberQuery.trim() !== this.selectedMember.name) this.selectedMember = null;
      const query = this.memberQuery.trim().toLowerCase();
      const existingIds = this.participants.map((person) => person.user_id);
      this.memberResults = this.peopleDirectory.filter((person) => {
        const searchable = `${person.name || ''} ${person.email || ''}`.toLowerCase();
        return !existingIds.includes(person.id) && (!query || searchable.includes(query));
      }).slice(0, 12);
      this.memberSearching = false;
    },

    get activeMemberResultId() {
      const person = this.memberResults[this.activeMemberIndex];
      return this.memberPickerOpen && person ? `journey-member-option-${person.id}` : null;
    },

    moveMemberResult(delta) {
      if (!this.memberPickerOpen) this.memberPickerOpen = true;
      if (!this.memberResults.length) return;
      this.activeMemberIndex = Math.max(0, Math.min(this.memberResults.length - 1, this.activeMemberIndex + delta));
    },

    selectActiveMember() {
      const person = this.memberResults[this.activeMemberIndex];
      if (this.memberPickerOpen && person) this.selectMember(person);
    },

    selectMember(person) {
      this.selectedMember = person;
      this.memberQuery = person.name;
      this.closeMemberPicker();
    },

    closeMemberPicker() {
      this.memberPickerOpen = false;
      this.activeMemberIndex = -1;
    },

    async addMember() {
      if (this.savingMember || !this.selectedMember) return;
      this.savingMember = true;
      this.error = '';
      try {
        await Platform.fetch.post(
          `/architecture-journey/work/${this.journeyId}/members`,
          { user_id: this.selectedMember.id, role: this.memberRole },
          { silent: true },
        );
        this.participants.push({
          user_id: this.selectedMember.id,
          name: this.selectedMember.name,
          email: this.selectedMember.email,
          role: this.memberRole,
          is_owner: false,
        });
        const name = this.selectedMember.name;
        this.selectedMember = null;
        this.memberQuery = '';
        this.memberResults = [];
        Platform.toast.success(`${name} was added to the journey.`);
      } catch (error) {
        this.error = error.message || 'That person could not be added.';
        Platform.toast.error(this.error);
      } finally {
        this.savingMember = false;
      }
    },

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
    linkEntityType: 'application',
    linkRelation: 'references',
    savingLink: false,
    recordQuery: '',
    recordResults: [],
    selectedRecord: null,
    recordPickerOpen: false,
    recordSearching: false,
    activeRecordIndex: -1,
    unlinkingLinkId: null,

    resetRecordPicker() {
      this.recordQuery = '';
      this.recordResults = [];
      this.selectedRecord = null;
      this.closeRecordPicker();
    },

    async searchRecords() {
      const query = this.recordQuery.trim();
      if (this.selectedRecord && query !== this.selectedRecord.name) this.selectedRecord = null;
      if (query.length < 2) {
        this.recordResults = [];
        this.recordPickerOpen = Boolean(query);
        return;
      }
      this.recordSearching = true;
      this.recordPickerOpen = true;
      this.activeRecordIndex = -1;
      try {
        if (this.linkEntityType === 'application') {
          const body = await Platform.fetch.get(
            `/applications/api/list?search=${encodeURIComponent(query)}&per_page=10`,
            null,
            { silent: true },
          );
          this.recordResults = (body.applications || []).map((record) => ({
            id: record.id,
            name: record.name,
            context: record.lifecycle_status ? `Lifecycle: ${record.lifecycle_status}` : 'Application portfolio',
          }));
        } else {
          const body = await Platform.fetch.get(
            `/archimate/api/elements/search?q=${encodeURIComponent(query)}&limit=12`,
            null,
            { silent: true },
          );
          const records = Array.isArray(body) ? body : (body.elements || body.data || []);
          this.recordResults = records.slice(0, 12).map((record) => ({
            id: record.id,
            name: record.name,
            context: [record.layer, record.element_type || record.type].filter(Boolean).join(' · '),
          }));
        }
      } catch (error) {
        this.recordResults = [];
        this.error = error.message || 'The record catalog could not be searched.';
        Platform.toast.error(this.error);
      } finally {
        this.recordSearching = false;
      }
    },

    get activeRecordResultId() {
      const record = this.recordResults[this.activeRecordIndex];
      return this.recordPickerOpen && record ? `journey-record-option-${record.id}` : null;
    },

    moveRecordResult(delta) {
      if (!this.recordPickerOpen) this.recordPickerOpen = true;
      if (!this.recordResults.length) return;
      this.activeRecordIndex = Math.max(0, Math.min(this.recordResults.length - 1, this.activeRecordIndex + delta));
    },

    selectActiveRecord() {
      const record = this.recordResults[this.activeRecordIndex];
      if (this.recordPickerOpen && record) this.selectRecord(record);
    },

    selectRecord(record) {
      this.selectedRecord = record;
      this.recordQuery = record.name;
      this.closeRecordPicker();
    },

    closeRecordPicker() {
      this.recordPickerOpen = false;
      this.activeRecordIndex = -1;
    },

    async addLink() {
      if (this.savingLink || !this.selectedRecord) return;
      this.savingLink = true;
      this.error = '';
      try {
        await Platform.fetch.post(
          `/architecture-journey/work/${this.journeyId}/links`,
          { entity_type: this.linkEntityType, entity_id: this.selectedRecord.id, relation: this.linkRelation },
          { silent: true },
        );
        // The counts are rendered server-side, so the page is reloaded rather than
        // incremented in place. Adjusting a number locally would show a count the
        // server has not confirmed -- the exact class of claim this screen exists
        // to avoid making.
        window.location.reload();
      } catch (error) {
        this.error = error.message || 'That record could not be linked.';
        Platform.toast.error(this.error);
      } finally {
        this.savingLink = false;
      }
    },

    async unlinkLink(linkId) {
      if (this.unlinkingLinkId !== null) return;
      this.unlinkingLinkId = linkId;
      this.error = '';
      try {
        await Platform.fetch.delete(
          `/architecture-journey/work/${this.journeyId}/links/${linkId}`,
          { silent: true },
        );
        Platform.toast.success('The record was unlinked.');
        window.location.reload();
      } catch (error) {
        this.error = error.message || 'The record could not be unlinked.';
        Platform.toast.error(this.error);
      } finally {
        this.unlinkingLinkId = null;
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
