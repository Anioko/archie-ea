document.addEventListener('alpine:init', () => {
  Alpine.data('architectureJourneyHub', () => ({
    title: '',
    intent: document.body.dataset.requestedJourneyIntent || '',
    layers: [],
    deliverables: [],
    outcomeType: 'undecided',
    starting: false,
    startingSolution: false,
    error: '',

    init() {
      const params = new URLSearchParams(window.location.search);
      const requested = (params.get('intent') || '').replaceAll('-', '_');
      if (requested) this.intent = requested;
      if (requested === 'business_transformation') {
        this.layers = ['motivation', 'strategy', 'business', 'data', 'implementation', 'governance'];
        this.deliverables = ['capability_map', 'value_stream', 'operating_model', 'roadmap'];
        this.outcomeType = 'undecided';
      }
    },

    get canStart() {
      return Boolean(this.title && this.intent && this.layers.length);
    },

    async startJourney() {
      if (!this.canStart || this.starting) return;
      this.starting = true;
      this.error = '';
      try {
        // Platform.fetch will automatically inject CSRF token and serialize plain object to JSON.
        // It throws a structured PlatformError on non-ok responses, which we catch below.
        const payload = await Platform.fetch.post('/architecture-journey/start-architecture', {
          title: this.title,
          intent: this.intent,
          selected_layers: this.layers,
          selected_deliverables: this.deliverables,
          outcome_type: this.outcomeType,
        }, { silent: true }); // silent: true because we paint our own inline error state
        // Platform.fetch returns the parsed response body directly (already JSON).
        // The server returns a { data: { redirect: ... } } structure on success.
        window.location.assign(payload.data.redirect);
      } catch (error) {
        // Platform.fetch throws a PlatformError with a message suitable for user display.
        // We preserve the existing inline error painting.
        this.error = error.message || 'The journey could not be created.';
        this.starting = false;
      }
    },

    async startSolution() {
      if (this.startingSolution) return;
      this.startingSolution = true;
      this.error = '';
      try {
        // Platform.fetch will automatically inject CSRF token and serialize plain object to JSON.
        // Passing an empty object as body ensures correct JSON serialization.
        const payload = await Platform.fetch.post('/architecture-journey/start', {}, { silent: true });
        // Platform.fetch returns the parsed response body directly (already JSON).
        // The server returns a { data: { redirect: ... } } structure on success.
        window.location.assign(payload.data.redirect);
      } catch (error) {
        // Platform.fetch throws a PlatformError with a message suitable for user display.
        // We preserve the existing inline error painting.
        this.error = error.message || 'Solution design could not be started.';
        this.startingSolution = false;
      }
    },
  }));
});
