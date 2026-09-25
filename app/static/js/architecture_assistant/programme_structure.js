// Person picker for the programme-structure preview (R1-06).
// One instance per field (programme owner, each workstream lead). A debounced
// search against the minimal, rate-limited, organisation-scoped lead-search
// endpoint; the chosen id travels in a hidden input, never free text
// (DESIGN.md entity-field rule). Top-level window factory: the CSP-safe
// Alpine evaluator resolves x-data names against window.
function personPicker(searchUrl, label) {
  return {
    searchUrl: searchUrl,
    label: label || '',
    query: '',
    results: [],
    selectedId: '',
    open: false,
    searching: false,
    message: '',

    async search() {
      if (this.selectedId) this.selectedId = '';
      const query = this.query.trim();
      if (query.length < 2) {
        this.results = [];
        this.open = false;
        this.message = '';
        return;
      }
      this.searching = true;
      this.open = true;
      this.message = '';
      try {
        const body = await Platform.fetch.get(this.searchUrl, { q: query }, { silent: true });
        const rows = body && body.data ? body.data : body;
        this.results = Array.isArray(rows && rows.people) ? rows.people : [];
        if (!this.results.length) this.message = 'No people match.';
      } catch (error) {
        this.results = [];
        this.message = error.message || 'People could not be searched.';
      } finally {
        this.searching = false;
      }
    },

    choose(person) {
      this.selectedId = String(person.id);
      this.query = person.display_name;
      this.open = false;
    },

    close() {
      this.open = false;
    },
  };
}
window.personPicker = personPicker;
