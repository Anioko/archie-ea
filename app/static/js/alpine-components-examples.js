/**
 * =============================================================================
 * ALPINE.JS UNIFIED ARCHITECTURE — EXAMPLES & MIGRATION GUIDE
 * alpine-components-examples.js
 * =============================================================================
 *
 * This file is NOT loaded in production. It is the canonical reference for:
 *   1. How to write a new component using the unified architecture
 *   2. How to write the corresponding HTML
 *   3. How to migrate a broken legacy component
 *
 * =============================================================================
 * EXAMPLE A — FORM COMPONENT
 * =============================================================================
 *
 * STEP 1: Register in alpine-architecture.js (inside the alpine:init listener)
 *
 *   Alpine.data('myEntityCreateModal', function () {
 *       return Object.assign(
 *           {}, _asyncMixin(), _modalMixin(),
 *           _formMixin({ name: '', type: '', notes: '' }),
 *           {
 *               apiUrl: '/api/my-entity',
 *
 *               validate() {
 *                   this.validationErrors = {};
 *                   if (!this.formData.name || !this.formData.name.trim())
 *                       this._setFieldError('name', 'Name is required.');
 *                   return !this._hasErrors();
 *               },
 *
 *               async submit() {
 *                   if (!this.validate()) return;
 *                   this._startLoading();
 *                   try {
 *                       var data = await window.apiFetch(this.apiUrl, {
 *                           method: 'POST',
 *                           body: this.formData
 *                       });
 *                       this._handleSuccess('Entity created.');
 *                       this.$dispatch('entity-created', { entity: data });
 *                       this.closeModal();
 *                   } catch (err) { this._handleError(err); }
 *               }
 *           }
 *       );
 *   });
 *
 * STEP 2: HTML template (inside a Jinja2 template, using the modal macro)
 *
 *   {% call modal(id='create-entity', title='New Entity') %}
 *     <div x-data="myEntityCreateModal"
 *          @entity-created.window="$dispatch('reload-table')">
 *
 *       <!-- Error banner -->
 *       <div x-show="errorMsg" x-text="errorMsg"
 *            class="rounded-md bg-destructive/10 text-destructive text-sm px-3 py-2 mb-4"
 *            x-cloak></div>
 *
 *       <form @submit.prevent="submit" class="space-y-4">
 *
 *         <!-- Name field -->
 *         <div>
 *           <label class="block text-sm font-medium mb-1">
 *             Name <span class="text-destructive">*</span>
 *           </label>
 *           <input type="text" x-model="formData.name"
 *                  :class="validationErrors.name ? 'border-destructive' : 'border-input'"
 *                  class="flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm
 *                         ring-offset-background focus-visible:outline-none focus-visible:ring-2
 *                         focus-visible:ring-ring" />
 *           <p x-show="validationErrors.name" x-text="validationErrors.name"
 *              class="text-xs text-destructive mt-1" x-cloak></p>
 *         </div>
 *
 *         <!-- Submit -->
 *         <div class="flex justify-end gap-2 pt-2">
 *           <button type="button" @click="closeModal()"
 *                   class="inline-flex items-center justify-center rounded-md border border-input
 *                          bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
 *             Cancel
 *           </button>
 *           <button type="submit" :disabled="loading"
 *                   class="inline-flex items-center justify-center rounded-md bg-primary
 *                          text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90
 *                          disabled:opacity-50 disabled:cursor-not-allowed">
 *             <span x-show="loading" class="mr-2">
 *               <i data-lucide="loader-2" class="h-4 w-4 animate-spin"></i>
 *             </span>
 *             <span x-text="loading ? 'Saving...' : 'Create'"></span>
 *           </button>
 *         </div>
 *       </form>
 *     </div>
 *   {% endcall %}
 *
 * =============================================================================
 * EXAMPLE B — TABLE COMPONENT
 * =============================================================================
 *
 * STEP 1: Register in alpine-architecture.js
 *
 *   Alpine.data('myEntityTable', function (config) {
 *       return Object.assign({}, _asyncMixin(), _tableMixin(), {
 *           apiUrl: (config && config.apiUrl) || '/api/my-entity',
 *           init() { this._loadItems(); },
 *           async _loadItems() {
 *               this._startLoading();
 *               try {
 *                   var data = await window.apiFetch(this.apiUrl + '?' + this._buildQueryString());
 *                   this.items = data.items || [];
 *                   this.totalItems = data.total || this.items.length;
 *                   this._stopLoading();
 *               } catch (err) { this._handleError(err); }
 *           }
 *       });
 *   });
 *
 * STEP 2: HTML template
 *
 *   <div x-data="myEntityTable({ apiUrl: '/api/my-entity' })"
 *        @reload-table.window="_loadItems()">
 *
 *     <!-- Search -->
 *     <input type="search" x-model="search" @input.debounce.300ms="onSearchInput()"
 *            placeholder="Search..."
 *            class="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm" />
 *
 *     <!-- Loading skeleton -->
 *     <div x-show="loading" class="py-8 text-center text-muted-foreground text-sm" x-cloak>
 *       <i data-lucide="loader-2" class="h-5 w-5 animate-spin inline-block mr-2"></i>
 *       Loading...
 *     </div>
 *
 *     <!-- Error state -->
 *     <div x-show="errorMsg && !loading" x-text="errorMsg"
 *          class="rounded-md bg-destructive/10 text-destructive text-sm px-3 py-2" x-cloak></div>
 *
 *     <!-- Table -->
 *     <div x-show="!loading && !errorMsg" class="rounded-md border">
 *       <table class="w-full text-sm">
 *         <thead class="bg-muted/50">
 *           <tr>
 *             <th class="px-4 py-3 text-left font-medium cursor-pointer"
 *                 @click="setSort('name')">
 *               Name
 *               <i data-lucide="chevrons-up-down" class="h-3 w-3 inline-block ml-1"></i>
 *             </th>
 *           </tr>
 *         </thead>
 *         <tbody>
 *           <template x-for="item in items" :key="item.id">
 *             <tr class="border-t hover:bg-muted/30">
 *               <td class="px-4 py-3" x-text="item.name"></td>
 *             </tr>
 *           </template>
 *           <tr x-show="items.length === 0">
 *             <td class="px-4 py-8 text-center text-muted-foreground">No results found.</td>
 *           </tr>
 *         </tbody>
 *       </table>
 *     </div>
 *
 *     <!-- Pagination -->
 *     <div class="flex items-center justify-between px-4 py-3 border-t">
 *       <span class="text-sm text-muted-foreground"
 *             x-text="`${totalItems} total`"></span>
 *       <div class="flex gap-1">
 *         <button @click="prevPage()" :disabled="!hasPrev"
 *                 class="inline-flex items-center justify-center rounded-md border border-input
 *                        bg-background px-3 py-1.5 text-sm disabled:opacity-50">
 *           <i data-lucide="chevron-left" class="h-4 w-4"></i>
 *         </button>
 *         <span class="inline-flex items-center px-3 text-sm"
 *               x-text="`${page} / ${totalPages}`"></span>
 *         <button @click="nextPage()" :disabled="!hasNext"
 *                 class="inline-flex items-center justify-center rounded-md border border-input
 *                        bg-background px-3 py-1.5 text-sm disabled:opacity-50">
 *           <i data-lucide="chevron-right" class="h-4 w-4"></i>
 *         </button>
 *       </div>
 *     </div>
 *   </div>
 *
 * =============================================================================
 * EXAMPLE C — MODAL COMPONENT (standalone, opened by event)
 * =============================================================================
 *
 * STEP 1: Register in alpine-architecture.js (already done for confirmDialog)
 *
 * STEP 2: Mount once in admin_base.html (or any base layout):
 *
 *   <div x-data="confirmDialog"
 *        @confirm-request.window="openModal($event.detail)"
 *        x-show="open"
 *        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
 *        x-cloak>
 *     <div class="bg-background rounded-lg border shadow-lg p-6 max-w-sm w-full mx-4"
 *          @click.stop>
 *       <h2 class="text-lg font-semibold mb-2">Confirm Action</h2>
 *       <p class="text-sm text-muted-foreground mb-6" x-text="message"></p>
 *       <div class="flex justify-end gap-2">
 *         <button @click="cancel()"
 *                 class="inline-flex items-center justify-center rounded-md border border-input
 *                        bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
 *                 x-text="cancelLabel"></button>
 *         <button @click="confirm()"
 *                 class="inline-flex items-center justify-center rounded-md bg-destructive
 *                        text-destructive-foreground px-4 py-2 text-sm font-medium hover:bg-destructive/90"
 *                 x-text="confirmLabel"></button>
 *       </div>
 *     </div>
 *   </div>
 *
 * STEP 3: Trigger from any component:
 *
 *   this.$dispatch('confirm-request', {
 *       message: 'Delete this item?',
 *       confirmLabel: 'Delete',
 *       onConfirm: async () => { await this._deleteItem(); }
 *   });
 *
 * =============================================================================
 * MIGRATION GUIDE — Converting Legacy Components
 * =============================================================================
 *
 * PATTERN 1: Global function used as x-data
 * ─────────────────────────────────────────
 * BEFORE (broken — global scope pollution, undefined if script loads late):
 *
 *   <script>
 *     function roadmapApp() {
 *       return { workPackages: [], loading: true, ... };
 *     }
 *   </script>
 *   <div x-data="roadmapApp()">
 *
 * AFTER (unified — registered before Alpine initialises):
 *
 *   <!-- In alpine-architecture.js, inside alpine:init: -->
 *   Alpine.data('roadmapApp', function (config) {
 *       return Object.assign({}, _asyncMixin(), { ... });
 *   });
 *
 *   <!-- In HTML: -->
 *   <div x-data="roadmapApp({ apiBase: '/api/technology-roadmap' })">
 *
 * ─────────────────────────────────────────
 * PATTERN 2: Inline object x-data (anonymous, no reuse)
 * ─────────────────────────────────────────
 * BEFORE (broken — cannot be tested, duplicated across pages):
 *
 *   <div x-data="{ open: false, loading: false, items: [] }">
 *
 * AFTER (for simple toggles — use primitive widgets):
 *
 *   <div x-data="accordionWidget(false)">   <!-- for open/close -->
 *   <div x-data="dropdownWidget">           <!-- for dropdowns -->
 *   <div x-data="tabsWidget('overview')">  <!-- for tabs -->
 *
 * AFTER (for complex state — register a named component):
 *
 *   Alpine.data('myWidget', function () { return { ... }; });
 *   <div x-data="myWidget">
 *
 * ─────────────────────────────────────────
 * PATTERN 3: Raw fetch() inside a component
 * ─────────────────────────────────────────
 * BEFORE (broken — no CSRF, no error toast, no loading state):
 *
 *   fetch('/api/vendors', { method: 'POST', body: JSON.stringify(data) })
 *     .then(r => r.json())
 *     .then(data => { ... })
 *     .catch(err => console.error(err));
 *
 * AFTER (unified):
 *
 *   this._startLoading();
 *   try {
 *       var data = await window.apiFetch('/api/vendors', { method: 'POST', body: this.formData });
 *       this._handleSuccess('Vendor created.');
 *   } catch (err) { this._handleError(err); }
 *
 * ─────────────────────────────────────────
 * PATTERN 4: Modal state inside page component
 * ─────────────────────────────────────────
 * BEFORE (broken — page re-renders reset modal state, scope collision):
 *
 *   <div x-data="{ items: [], showModal: false, modalData: {} }">
 *     <button @click="showModal = true">Open</button>
 *     <div x-show="showModal">... form ...</div>
 *   </div>
 *
 * AFTER (separated):
 *
 *   <!-- Page component owns table only -->
 *   <div x-data="vendorList" @vendor-created.window="_loadItems()">
 *     <button onclick="document.getElementById('create-vendor-modal').dispatchEvent(
 *                 new CustomEvent('open-modal'))">
 *       New Vendor
 *     </button>
 *     ...table...
 *   </div>
 *
 *   <!-- Modal component is completely separate -->
 *   <div x-data="vendorCreateModal"
 *        @open-modal="openModal()"
 *        x-show="open" x-cloak ...>
 *     ...form...
 *   </div>
 *
 * ─────────────────────────────────────────
 * PATTERN 5: window.__CONFIG__ globals
 * ─────────────────────────────────────────
 * BEFORE (broken — implicit global, order-dependent):
 *
 *   window.__VENDOR_CONFIG__ = { createVendorUrl: '{{ url_for(...) }}' };
 *   function vendorCreateModal() {
 *     var url = window.__VENDOR_CONFIG__.createVendorUrl;
 *   }
 *
 * AFTER (pass config as component argument via data attribute):
 *
 *   <!-- In Jinja2 template: -->
 *   <div x-data="vendorCreateModal({ apiUrl: '{{ url_for('vendor_management.create_vendor') }}' })">
 *
 *   <!-- In alpine-architecture.js: -->
 *   Alpine.data('vendorCreateModal', function (config) {
 *       return Object.assign({}, ..., {
 *           apiUrl: (config && config.apiUrl) || '/api/vendors',
 *           ...
 *       });
 *   });
 *
 * ─────────────────────────────────────────
 * PATTERN 6: Duplicate component names across pages
 * ─────────────────────────────────────────
 * BEFORE (broken — three files all define roadmapApp() globally):
 *
 *   technology_roadmap/enhanced_roadmap_fixed.html: function roadmapApp() { ... }
 *   strategic_roadmap/enhanced_roadmap_fixed.html:  function roadmapApp() { ... }
 *   hybrid_roadmap/enhanced_roadmap_fixed.html:     function roadmapApp() { ... }
 *
 * AFTER (one definition, parameterised):
 *
 *   <!-- alpine-architecture.js: -->
 *   Alpine.data('roadmapApp', function (config) { ... });
 *
 *   <!-- technology_roadmap template: -->
 *   <div x-data="roadmapApp({ apiBase: '/api/technology-roadmap' })">
 *
 *   <!-- strategic_roadmap template: -->
 *   <div x-data="roadmapApp({ apiBase: '/api/strategic-roadmap' })">
 *
 *   <!-- hybrid_roadmap template: -->
 *   <div x-data="roadmapApp({ apiBase: '/api/hybrid-roadmap' })">
 *
 * =============================================================================
 * STORE ARCHITECTURE (defined in admin_base.html — DO NOT redefine elsewhere)
 * =============================================================================
 *
 * $store.sidebar      — { open: bool }
 * $store.loading      — { active: bool, start(), stop() }
 * $store.theme        — { dark: bool, toggle() }
 * $store.announcer    — { announce(text), assertive(text) }
 * $store.user         — { role, isAdmin, isAuthenticated, displayName, featureFlags }
 * $store.notifications — { count, items, startPolling(), stopPolling(), markAllRead() }
 *
 * Access from any component:
 *   this.$store.loading.start()
 *   this.$store.announcer.announce('Item saved.')
 *   if (this.$store.user.isAdmin) { ... }
 *
 * DO NOT add new stores in page templates. Add them in admin_base.html only.
 *
 * =============================================================================
 * LIFECYCLE PATTERN
 * =============================================================================
 *
 *   Alpine.data('myComponent', function (config) {
 *       return {
 *           // 1. Declare all state upfront — no undefined variables
 *           items: [],
 *           loading: false,
 *           errorMsg: '',
 *
 *           // 2. init() — called by Alpine after x-data is evaluated
 *           init() {
 *               this._loadData();
 *               // Set up event listeners if needed
 *               this.$watch('someState', (val) => this._onStateChange(val));
 *           },
 *
 *           // 3. destroy() — called by Alpine when element is removed from DOM
 *           destroy() {
 *               // Clear timers, remove listeners
 *               if (this._pollTimer) clearInterval(this._pollTimer);
 *           },
 *
 *           // 4. afterOpen(detail) — called by _modalMixin when modal opens
 *           afterOpen(detail) { /* populate form from detail */ },
 *
 *           // 5. afterClose() — called by _modalMixin when modal closes
 *           afterClose() { this.resetForm(); }
 *       };
 *   });
 *
 * =============================================================================
 * COMPONENT COMMUNICATION PATTERNS
 * =============================================================================
 *
 * A. Parent → Child: pass config object to Alpine.data constructor
 *      x-data="myTable({ apiUrl: '/api/items', pageSize: 50 })"
 *
 * B. Child → Parent: dispatch custom events
 *      this.$dispatch('item-created', { item: data });
 *      Parent listens: @item-created.window="_loadItems()"
 *
 * C. Sibling → Sibling: dispatch on window
 *      this.$dispatch('reload-table');
 *      Sibling listens: @reload-table.window="_loadItems()"
 *
 * D. Any → Modal: dispatch open event
 *      this.$dispatch('confirm-request', { message: '...', onConfirm: fn });
 *      Modal listens: @confirm-request.window="openModal($event.detail)"
 *
 * E. Global state: use Alpine stores (defined in admin_base.html)
 *      this.$store.loading.start();
 *      this.$store.announcer.announce('Saved.');
 *
 * =============================================================================
 * VALIDATION PATTERN
 * =============================================================================
 *
 *   validate() {
 *       this.validationErrors = {};                    // always reset first
 *
 *       if (!this.formData.name || !this.formData.name.trim())
 *           this._setFieldError('name', 'Name is required.');
 *
 *       if (this.formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.formData.email))
 *           this._setFieldError('email', 'Enter a valid email address.');
 *
 *       return !this._hasErrors();                     // true = valid
 *   },
 *
 *   async submit() {
 *       if (!this.validate()) return;                  // gate: validate first
 *       this._startLoading();
 *       try { ... } catch (err) { this._handleError(err); }
 *   }
 *
 *   <!-- In HTML, show field errors: -->
 *   <p x-show="validationErrors.name" x-text="validationErrors.name"
 *      class="text-xs text-destructive mt-1" x-cloak></p>
 *
 * =============================================================================
 * CHECKLIST FOR NEW COMPONENTS
 * =============================================================================
 *
 *   [ ] Name follows convention (domain + Page/Modal/Table/Widget)
 *   [ ] Registered via Alpine.data() in alpine-architecture.js
 *   [ ] Uses _asyncMixin() for loading/error/success state
 *   [ ] Uses _formMixin() if it owns a form
 *   [ ] Uses _tableMixin() if it owns a data table
 *   [ ] Uses _modalMixin() if it is a modal
 *   [ ] All async calls go through window.apiFetch()
 *   [ ] validate() is separate from submit()
 *   [ ] destroy() clears any timers or listeners
 *   [ ] No inline JS in HTML (x-data references registered name only)
 *   [ ] No raw fetch() calls
 *   [ ] No alert() or console.error() for user-facing errors
 *   [ ] No window.__CONFIG__ globals (pass via config argument instead)
 *   [ ] No modal state inside page components
 *   [ ] No page state inside modal components
 *   [ ] All state declared upfront (no undefined variables)
 */
