# Macro Component Catalog - Quick Reference

**Total:** 114 macros | **Updated:** 2026-02-04

Quick reference for all reusable components. Full docs: [docs/design-system/components.md](../../docs/design-system/components.md)

---

## ⚠️ DEPRECATED MACROS (Removal: v2.0)

**The following macros are deprecated and will be removed:**

### Deprecated Files
- ❌ **macros/nav_macros.html** - Use `macros/nav_macros_shadcn_fixed.html` instead
- ❌ **macros/shadcn_compat.html::shadcn_button** - Use `components/button.html` instead
- ❌ **macros/shadcn_compat.html::shadcn_input** - Use `components/input.html` instead
- ❌ **macros/shadcn_compat.html::shadcn_table** - Use `components/table.html` instead

**Check your templates:**
```bash
python scripts/guardrails/check_component_duplication.py --check-deprecated
python scripts/guardrails/analyze_deprecated_usage.py --by-macro
```

**See migration guide:** [docs/design-system/components.md#migration-guide](../../docs/design-system/components.md#migration-guide)

---

## Most Used Components

```jinja2
{% from 'components/button.html' import button %}
{% from 'components/input.html' import input, label %}
{% from 'components/card.html' import card %}
{% from 'components/alert.html' import alert %}
{% from 'components/modal.html' import modal %}
```

## All Components (A-Z)

| Component | File | Category |
|-----------|------|----------|
| accordion | components/accordion.html | Layout |
| alert | components/alert.html | Feedback |
| avatar | components/avatar.html | UI |
| badge | components/badge.html | UI |
| button | components/button.html | Action |
| card | components/card.html | Container |
| checkbox | components/checkbox.html | Form |
| data_table | components/data_table.html | Data |
| dialog | components/dialog.html | Feedback |
| dropdown_menu | components/dropdown.html | Navigation |
| input | components/input.html | Form |
| loading_button | components/loading_button.html | Action |
| modal | components/modal.html | Feedback |
| progress | components/progress.html | Feedback |
| select | components/select.html | Form |
| skeleton | components/skeleton.html | Feedback |
| switch | components/switch.html | Form |
| table | components/table.html | Data |
| tabs | components/tabs.html | Navigation |
| textarea | components/input.html | Form |
| tooltip | components/tooltip.html | Feedback |

**+ 93 more components** in components/ and macros/ directories.

See full catalog in [docs/design-system/components.md](../../docs/design-system/components.md)
