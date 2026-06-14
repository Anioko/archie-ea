# DESIGN.md — A.R.C.H.I.E. Design System

> **For AI agents:** Read this file before editing any template or UI file.
> This describes the complete design system used by this Flask + Tailwind CSS + shadcn/ui + Alpine.js application.
> The canonical source of truth for patterns is `docs/design_system/pattern_registry.json`.
> The canonical color token map is `docs/design_system/token_map.json`.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python / Flask (Jinja2 templates) |
| Styling | Tailwind CSS v3 + shadcn/ui design tokens |
| Interactivity | Alpine.js v3 (no jQuery, no React) |
| Icons | Lucide Icons (via CDN, `data-lucide="icon-name"`) |
| Layout | Three base templates: `layouts/admin_base.html`, `layouts/base.html`, `layouts/public_base.html` |

---

## Color Tokens (MANDATORY — never use raw Tailwind colors)

All colors use CSS variables defined in `app/static/css/shadcn_tokens.css`. Reference them via Tailwind semantic classes only.

### Core Tokens

| Purpose | Tailwind class | CSS variable | Light mode |
|---------|---------------|-------------|-----------|
| Page background | `bg-background` | `--background` | white |
| Page text | `text-foreground` | `--foreground` | near-black |
| Card background | `bg-card` | `--card` | white |
| Card text | `text-card-foreground` | `--card-foreground` | near-black |
| Muted background | `bg-muted` | `--muted` | light gray |
| Muted text | `text-muted-foreground` | `--muted-foreground` | medium gray |
| Primary (blue) | `bg-primary` / `text-primary` | `--primary` | #3b82f6 |
| Primary label | `text-primary-foreground` | `--primary-foreground` | near-white |
| Destructive (red) | `bg-destructive` / `text-destructive` | `--destructive` | red |
| Success | `bg-success` / `text-success` | `--success` | emerald |
| Warning | `bg-warning` / `text-warning` | `--warning` | amber |
| Info | `bg-info` / `text-info` | `--info` | blue |
| Border | `border-border` | `--border` | light gray |
| Input border | `border-input` | `--input` | light gray |
| Focus ring | `ring-ring` | `--ring` | blue |
| Border radius | `rounded-lg` | `--radius` | 0.5rem |

### ArchiMate Layer Colors (domain-specific)

| Layer | Color | Usage |
|-------|-------|-------|
| Motivation | violet (`--layer-motivation`) | Goals, Drivers, Outcomes, Requirements |
| Strategy | amber (`--layer-strategy`) | Courses of Action |
| Business | emerald (`--layer-business`) | Processes, Roles, Actors |
| Application | blue (`--layer-application`) | Services, Components, Data |
| Technology | green (`--layer-technology`) | Nodes, Devices, Networks |
| Implementation | sky (`--layer-implementation`) | Work Packages, Plateaus |
| Risk | red (`--layer-risk`) | Assessments, Issues |

### Forbidden Color Classes

**Never** use raw Tailwind color scales — the pre-commit hook `check_token_migration.py` will block the commit.

```
❌ bg-white         → ✅ bg-background
❌ bg-gray-50       → ✅ bg-muted/30
❌ bg-gray-100      → ✅ bg-muted
❌ text-gray-500    → ✅ text-muted-foreground
❌ text-gray-700    → ✅ text-foreground
❌ text-gray-900    → ✅ text-foreground
❌ bg-blue-500      → ✅ bg-primary
❌ text-blue-600    → ✅ text-primary
❌ bg-red-500       → ✅ bg-destructive
❌ text-red-500     → ✅ text-destructive
❌ border-gray-200  → ✅ border-border
❌ text-white       → ✅ text-primary-foreground (on primary bg)
```

Green and yellow have no semantic tokens — use emerald and amber scales directly for status colors.

---

## Typography

All text uses Tailwind's default font stack. Key classes:

| Use | Class |
|-----|-------|
| Page heading | `text-2xl font-bold text-foreground` |
| Section heading | `text-lg font-semibold text-foreground` |
| Body text | `text-sm text-foreground` |
| Secondary / help text | `text-sm text-muted-foreground` |
| Label | `text-xs font-medium text-muted-foreground uppercase tracking-wide` |
| Code / mono | `font-mono text-sm` |

---

## Layout

### Base Templates

Every page **must** extend one of these — never write standalone HTML:

```jinja
{# Admin/dashboard pages #}
{% extends 'layouts/admin_base.html' %}

{# Standard pages #}
{% extends 'layouts/base.html' %}

{# Public / auth pages #}
{% extends 'layouts/public_base.html' %}
```

**Forbidden** — these do not exist:
- `{% extends 'layouts/main.html' %}` ❌
- `{% extends 'admin/base.html' %}` ❌
- `{% extends 'layouts/sidebar.html' %}` ❌

### Sidebar

Always include via:
```jinja
{% include 'components/admin_sidebar.html' %}
```

**Never** duplicate or inline the sidebar HTML.

### Page Structure (admin pages)

```html
{% block content %}
<div class="flex-1 overflow-auto">
  <!-- Page header with breadcrumbs -->
  {% from 'components/page_header.html' import page_header %}
  {{ page_header(title='Page Title', breadcrumbs=[('Home', url_for('main.index')), ('Current', None)]) }}

  <div class="p-6 space-y-6">
    <!-- page content here -->
  </div>
</div>
{% endblock %}
```

---

## Components

### Buttons

```html
<!-- Primary -->
<button type="button" class="inline-flex items-center justify-center rounded-md text-sm font-medium
  bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2
  disabled:opacity-50 disabled:pointer-events-none">
  Save
</button>

<!-- Secondary -->
<button type="button" class="inline-flex items-center justify-center rounded-md text-sm font-medium
  bg-secondary text-secondary-foreground hover:bg-secondary/80 h-9 px-4 py-2">
  Cancel
</button>

<!-- Destructive -->
<button type="button" class="inline-flex items-center justify-center rounded-md text-sm font-medium
  bg-destructive text-destructive-foreground hover:bg-destructive/90 h-9 px-4 py-2">
  Delete
</button>

<!-- Outline -->
<button type="button" class="inline-flex items-center justify-center rounded-md text-sm font-medium
  border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">
  Export
</button>

<!-- Ghost -->
<button type="button" class="inline-flex items-center justify-center rounded-md text-sm font-medium
  hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">
  View
</button>

<!-- Icon-only (must have aria-label) -->
<button type="button" aria-label="Close" class="inline-flex items-center justify-center rounded-md
  hover:bg-accent hover:text-accent-foreground h-9 w-9">
  <i data-lucide="x" class="h-4 w-4"></i>
</button>
```

**Rules:**
- Every `<button>` **must** have `type="button"` (or `type="submit"` if it's a submit button — never omit it)
- Never use `onclick=` HTML attributes — use Alpine `@click` or `data-action`
- Icon-only buttons must have `aria-label`
- Always include `disabled:opacity-50 disabled:pointer-events-none`

### Cards

```jinja
{% import 'components/card.html' as card %}

{% call card.card() %}
  {% call card.card_header() %}
    {% call card.card_title() %}Title{% endcall %}
    {% call card.card_description() %}Optional description{% endcall %}
  {% endcall %}
  {% call card.card_content() %}
    <p class="text-sm text-muted-foreground">Content here.</p>
  {% endcall %}
  {% call card.card_footer() %}
    <button type="button" class="...">Action</button>
  {% endcall %}
{% endcall %}
```

**Forbidden:** `<div class="card">`, Bootstrap `card-body`, `bg-white` on cards.

### Badges / Status Pills

```html
<!-- Success -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium
  bg-emerald-500/10 text-emerald-600 border border-emerald-500/30">Active</span>

<!-- Warning -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium
  bg-amber-500/10 text-amber-600 border border-amber-500/30">Pending</span>

<!-- Danger -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium
  bg-red-500/10 text-red-600 border border-red-500/30">Error</span>

<!-- Info -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium
  bg-blue-500/10 text-blue-600 border border-blue-500/30">Info</span>

<!-- Neutral -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium
  bg-muted text-muted-foreground border border-border">Draft</span>
```

### Form Inputs

```html
<input type="text"
  class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1
    text-sm shadow-sm transition-colors placeholder:text-muted-foreground
    focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
    disabled:cursor-not-allowed disabled:opacity-50"
  placeholder="Search...">
```

**Forbidden:** Bootstrap `form-control`, `form-group`, `input-group`, inline width/height styles.

### Modals

```jinja
{% from 'components/modal.html' import modal %}

{# Trigger #}
<button type="button" data-modal-open="my-modal">Open Modal</button>

{# Modal definition #}
{% call modal(id='my-modal', title='Modal Title', size='default') %}
  <p class="text-sm text-muted-foreground">Modal content here.</p>
{% endcall %}
```

```js
// JavaScript API
Platform.modal.open('my-modal', { key: value });
Platform.modal.close('my-modal');
```

**Forbidden:**
- `x-show='showModal'` local Alpine state for modals
- `window.openModal()` / `window.closeModal()` (legacy)
- Inline modal HTML without the macro
- `x-cloak` on modal root elements (they use `hidden` attribute)

### Metrics Cards (KPI widgets)

```jinja
{% from 'components/metrics_card.html' import metrics_card %}

{{ metrics_card(
  title='Total Applications',
  value=metrics.applications,
  icon='layers',
  trend='+12%',
  trend_direction='up'
) }}
```

### Empty States

```jinja
{% from 'components/empty_state.html' import empty_state %}

{{ empty_state(
  icon='inbox',
  title='No results found',
  description='Try adjusting your search or filters.',
  cta_label='Add New',
  cta_href=url_for('resource.create')
) }}
```

### Skeleton / Loading States

```jinja
{% from 'components/skeleton.html' import skeleton_table, skeleton_card %}

{# Table loading state #}
<div x-show="loading">{{ skeleton_table(rows=5, cols=4) }}</div>

{# Card loading state #}
{{ skeleton_card() }}
```

**Button-level loading (inline is OK here):**
```html
<button type="button" :disabled="isSubmitting">
  <span x-show="isSubmitting"
    class="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full inline-block">
  </span>
  <span x-show="!isSubmitting">Submit</span>
</button>
```

### Data Tables

```js
// Alpine component (preferred)
x-data="dataTable({ apiUrl: '/api/resource', perPage: 25 })"

// Or composition mixin
Alpine.data('myPage', function() {
  return Object.assign({}, Platform.dataTable.mixin({ apiUrl: '/api/resource' }), {
    // page-specific state
  });
});
```

**Rules:**
- Null values render as em dash (`—`), never `£0.00` or blank
- Currency via `window.currencyManager.format()`, never hardcoded
- Use arrays (`[]`), not `Set`, for selection state (Alpine cannot observe Set mutations)
- Four required states: loading (skeleton), empty (no data), empty (filtered), populated

**Forbidden:** jQuery DataTables, Bootstrap `table-striped`, manual `innerHTML` string-building for rows.

---

## Alpine.js Patterns

### General Rules

- Every `x-show` element **must** also have `x-cloak` to prevent flash-of-unstyled-content (FOUC)
- **Exception:** Modal root elements use `hidden` attribute, NOT `x-show`/`x-cloak`
- `Alpine.data()` component names must be globally unique
- Use `$nextTick()` instead of `setTimeout()` for post-render operations
- Use `$watch()` instead of `setTimeout()` for reactive state monitoring
- Never nest `x-data` scopes with the same variable name

```html
<!-- Page-level Alpine component -->
<div x-data="myPage()" x-cloak>
  <!-- content -->
</div>

<script>
Alpine.data('myPage', function() {
  return {
    isOpen: false,
    items: [],
    async init() {
      const resp = await fetch('/api/items');
      this.items = await resp.json();
    }
  };
});
</script>
```

### Global Loading Overlay

```js
// Show/hide platform-wide loading overlay
Platform.loading.start();
// ... async work ...
Platform.loading.stop();
```

---

## Icons

Uses Lucide Icons. All icons are rendered via the data attribute and auto-initialized:

```html
<i data-lucide="layers" class="h-4 w-4"></i>
<i data-lucide="chevron-down" class="h-4 w-4 text-muted-foreground"></i>
```

Common sizes: `h-4 w-4` (small), `h-5 w-5` (default), `h-6 w-6` (large), `h-12 w-12` (hero).

---

## Navigation / Tabs

```jinja
{% from 'macros/nav_macros_shadcn.html' import pill_tabs, tab_panel %}
```

**Forbidden files:**
- `macros/nav_macros_shadcn_fixed.html` — DELETED
- `macros/nav_macros.html` — DEPRECATED

---

## Entity Pickers (search-select fields)

Any form field for a user, application, vendor, or ArchiMate element **must** use a live-search picker — not a plain `<input type="text">`.

| Entity | API endpoint |
|--------|-------------|
| Users | `GET /api/users` |
| Applications | `GET /applications/api/list?search={q}&limit=10` |
| ArchiMate elements | `GET /architecture/decisions/api/element-search?q={q}` |
| Vendor products | `GET /api/vendor/search?q={q}` |
| APQC processes | `GET /api/apqc/search?q={q}` |

Pattern: search input → 300ms debounce → API call → dropdown results → click to select → hidden input gets `id`.

---

## ArchiMate Layer Rules (domain-specific)

Every backend CREATE for a motivation entity (Driver, Goal, Constraint, Requirement, Risk, Metric, Plateau, WorkPackage) **must** call `_sync_archimate_element()` to create a corresponding `ArchiMateElement` row. Plain textareas are not acceptable for these entities — the field IS the ArchiMate element.

| Domain model | ArchiMate type | Layer |
|-------------|----------------|-------|
| SolutionDriver | Driver | Motivation |
| SolutionGoal | Goal | Motivation |
| SolutionConstraint | Constraint | Motivation |
| SolutionRequirement | Requirement | Motivation |
| SolutionRisk | Assessment | Motivation |
| SolutionMetric | Outcome | Motivation |
| SolutionPlateau | Plateau | Implementation |

---

## Impact Analysis API

Use the canonical endpoint — do not create new impact scoring logic:

```js
const resp = await fetch('/api/v1/impact/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ app_id, scenario })
});
const json = await resp.json();
const data = json.data ?? json; // unwrap success_response() wrapper
```

Risk level badge colors: `CRITICAL`/`HIGH` → `text-destructive`, `MEDIUM` → `text-amber-600`, `LOW` → `text-emerald-600`.

---

## What Not to Do (summary)

| ❌ Forbidden | ✅ Use instead |
|-------------|--------------|
| Raw Tailwind colors (`gray-*`, `blue-*`, etc.) | Semantic tokens (`bg-background`, `text-primary`, etc.) |
| Bootstrap classes (`btn-primary`, `card-body`, `form-control`) | Tailwind + shadcn classes |
| jQuery / `$(...)` | Alpine.js |
| `onclick=` HTML attributes | Alpine `@click` or `data-action` |
| `window.openModal()` | `Platform.modal.open('id')` |
| Inline modal HTML | `{% call modal(...) %}` macro |
| `setTimeout()` for reactive state | `$nextTick()` or `$watch()` |
| `new Set()` for Alpine selection state | Arrays `[]` |
| `{% extends 'layouts/main.html' %}` | `{% extends 'layouts/admin_base.html' %}` |
| `{% include 'partials/sidebar.html' %}` | `{% include 'components/admin_sidebar.html' %}` |
| Standalone `<button>` without `type=` | Always `type="button"` or `type="submit"` |
| Hand-rolled stat divs | `{{ metrics_card(...) }}` macro |
| Inline empty state HTML | `{{ empty_state(...) }}` macro |
| Custom loading spinners | `{{ skeleton_table(...) }}` macros |

---

*Authoritative sources: `docs/design_system/pattern_registry.json` · `docs/design_system/token_map.json` · `app/static/css/shadcn_tokens.css` · `tailwind.config.js`*
