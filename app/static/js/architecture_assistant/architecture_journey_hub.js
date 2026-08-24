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
        const response = await fetch('/architecture-journey/start-architecture', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
          },
          body: JSON.stringify({
            title: this.title,
            intent: this.intent,
            selected_layers: this.layers,
            selected_deliverables: this.deliverables,
            outcome_type: this.outcomeType,
          }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'The journey could not be created.');
        window.location.assign(payload.data.redirect);
      } catch (error) {
        this.error = error.message || 'The journey could not be created.';
        this.starting = false;
      }
    },

    async startSolution() {
      if (this.startingSolution) return;
      this.startingSolution = true;
      this.error = '';
      try {
        const response = await fetch('/architecture-journey/start', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
          },
          body: '{}',
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Solution design could not be started.');
        window.location.assign(payload.data.redirect);
      } catch (error) {
        this.error = error.message || 'Solution design could not be started.';
        this.startingSolution = false;
      }
    },
  }));
});
