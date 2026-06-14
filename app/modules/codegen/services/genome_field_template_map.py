"""
Genome Field → Template Mapping

Maps genome field JSON paths (using * wildcard for module/entity keys) to the
Jinja2 template files that consume those fields. Used by GenomePatchService
to identify which templates need regeneration after a genome patch.
"""
from typing import List

GENOME_FIELD_TEMPLATE_MAP: dict = {
    "modules.*.views.list.export_formats": ["nextjs_shadcn/app/entity_list.tsx.j2"],
    "modules.*.views.list.search_fields": ["nextjs_shadcn/app/entity_list.tsx.j2"],
    "modules.*.views.list.bulk_actions": ["nextjs_shadcn/app/entity_list.tsx.j2"],
    "modules.*.views.list.pagination": ["nextjs_shadcn/app/entity_list.tsx.j2"],
    "modules.*.views.list.empty_state": ["nextjs_shadcn/app/entity_list.tsx.j2"],
    "modules.*.views.detail.show_audit_trail": ["nextjs_shadcn/app/entity_detail.tsx.j2"],
    "modules.*.views.detail.related_lists": ["nextjs_shadcn/app/entity_detail.tsx.j2"],
    "modules.*.state_machine": [
        "nextjs_shadcn/app/entity_list.tsx.j2",
        "nextjs_shadcn/app/entity_detail.tsx.j2",
        "python_fastapi/schema.py.j2",
    ],
    "notifications": ["python_fastapi/notifications/service.py.j2"],
    "notifications.channels": ["python_fastapi/notifications/service.py.j2"],
    "notifications.triggers": ["python_fastapi/notifications/service.py.j2"],
    "payments": [
        "python_fastapi/payments/stripe_router.py.j2",
        "nextjs_shadcn/app/billing/page.tsx.j2",
    ],
    "payments.provider": [
        "python_fastapi/payments/stripe_router.py.j2",
        "nextjs_shadcn/app/billing/page.tsx.j2",
    ],
    "file_storage": ["python_fastapi/main.py.j2"],
    "security.rate_limiting": ["python_fastapi/main.py.j2"],
    "security.multi_tenancy": ["python_fastapi/schema.py.j2", "python_fastapi/main.py.j2"],
    "infrastructure.auth": [
        "python_fastapi/main.py.j2",
        "nextjs_shadcn/middleware_auth.ts.j2",
        "nextjs_shadcn/lib/auth_context.tsx.j2",
    ],
    "workers": ["python_fastapi/workers/worker.py.j2"],
}


def get_affected_templates(field_paths: List[str]) -> List[str]:
    """Return deduplicated list of template filenames for the given genome field paths.

    Accepts both JSON Pointer format (/a/b/c) and dotted format (a.b.c).
    Applies wildcard matching for module-level keys.
    """
    affected = set()
    for path in field_paths:
        dotted = path.lstrip("/").replace("/", ".")
        if dotted in GENOME_FIELD_TEMPLATE_MAP:
            affected.update(GENOME_FIELD_TEMPLATE_MAP[dotted])
            continue
        parts = dotted.split(".")
        if len(parts) >= 3:
            wildcard_key = ".".join([parts[0], "*"] + parts[2:])
            if wildcard_key in GENOME_FIELD_TEMPLATE_MAP:
                affected.update(GENOME_FIELD_TEMPLATE_MAP[wildcard_key])
                continue
        top = parts[0]
        if top in GENOME_FIELD_TEMPLATE_MAP:
            affected.update(GENOME_FIELD_TEMPLATE_MAP[top])
    return sorted(affected)
