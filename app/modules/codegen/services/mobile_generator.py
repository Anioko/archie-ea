"""
Genome-Driven Mobile App Generator

Generates a React Native / Expo mobile app from an Architectural Genome.
Reads the genome's `mobile` section for push notifications, offline config,
biometric auth, and native features. Reads `modules` for CRUD screens.

Unlike _generate_expo_mobile() in codegen_routes.py (which reads UML snapshots),
this generator reads the genome directly and produces richer output including:
- Push notification service with channels from genome
- Offline cache with Tier 1/2 sync based on genome config
- Biometric authentication gate
- Per-module CRUD screens with state machine actions

Pipeline position:
  Genome → MobileGenerator → {mobile/...} files → merged into codegen output
"""
import logging
import os
import re
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


_ICON_KEYWORDS: list[tuple[list[str], str]] = [
    (["user", "member", "customer", "client", "employee", "contact", "person", "staff"], "Users"),
    (["order", "purchase", "cart", "sale"], "ShoppingCart"),
    (["invoice", "bill", "receipt"], "Receipt"),
    (["payment", "transaction", "charge", "fee"], "CreditCard"),
    (["product", "catalog", "listing"], "Package"),
    (["inventory", "stock", "warehouse"], "ArchiveBox"),
    (["project", "programme", "initiative"], "FolderKanban"),
    (["task", "ticket", "issue", "todo"], "CheckSquare"),
    (["document", "report", "contract", "policy", "form"], "FileText"),
    (["vendor", "supplier", "partner"], "Building2"),
    (["event", "meeting", "appointment", "booking", "reservation", "session"], "CalendarDays"),
    (["work_order", "maintenance", "repair", "service_request"], "Wrench"),
    (["asset", "equipment", "device", "machine"], "Server"),
    (["location", "address", "site", "facility", "place"], "MapPin"),
    (["notification", "alert", "message"], "Bell"),
    (["shipment", "delivery", "logistics", "freight"], "Truck"),
]


def _get_icon_for_entity(name: str) -> str:
    """Return the best lucide-react-native icon name for an entity based on its name."""
    n = name.lower().replace(" ", "_")
    for keywords, icon in _ICON_KEYWORDS:
        if any(kw in n for kw in keywords):
            return icon
    return "Layers"


def generate_mobile_from_genome(genome: dict, mobile_ui_framework: str = "nativewind") -> dict:
    """
    Generate React Native / Expo mobile app files from an Architectural Genome.

    Args:
        genome: Validated genome dict with optional `mobile` section.
        mobile_ui_framework: UI framework to use. "nativewind" (default) uses Tailwind/NativeWind;
            "paper" uses React Native Paper (MD3). Paper templates in paper/ override base templates
            via FileSystemLoader priority ordering.

    Returns:
        Dict of filepath -> content for the mobile/ directory.
    """
    base_template_dir = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "..",
        "solutions_product", "templates", "react_native_expo",
    ))
    # Legacy alias kept for backwards compat
    template_dir = base_template_dir

    if mobile_ui_framework == "paper":
        paper_override_dir = os.path.join(base_template_dir, "paper")
        loader = FileSystemLoader([paper_override_dir, base_template_dir])
    else:
        loader = FileSystemLoader(base_template_dir)

    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    solution_name = genome.get("solution_name", "My App")
    solution_slug = re.sub(r"[^a-z0-9]", "_", solution_name.lower()).strip("_") or "my_app"
    modules = genome.get("modules", {})
    mobile_cfg = genome.get("mobile", {})
    ux_prefs = genome.get("ux_preferences", {})
    security = genome.get("security", {})
    idp = genome.get("identity_provider", {})

    # Determine auth mode
    auth = "jwt-local" if idp.get("type") in ("jwt-local", "oidc") else "none"

    # Build class list from genome modules (same structure the existing templates expect)
    classes = _modules_to_classes(modules)

    # Annotate each class with pagination flag based on data_volumes in ux_preferences
    data_volumes = ux_prefs.get("data_volumes", {})
    for cls in classes:
        slug = cls.get("table_name") or cls["name"].lower()
        vol = data_volumes.get(slug, {})
        cls["use_pagination"] = vol.get("volume_tier") in ("medium", "large")

    # Offline config
    offline_cfg = mobile_cfg.get("offline", {})
    offline_tier = offline_cfg.get("tier", 1)
    offline_entities = offline_cfg.get("offline_entities", [])

    # Push notification config
    push_cfg = mobile_cfg.get("push_notifications", {})
    push_enabled = push_cfg.get("enabled", False)
    push_channels = push_cfg.get("channels", [])

    # Features
    features = set(mobile_cfg.get("features", []))
    has_biometric = "biometric_auth" in features

    # Attach semantic icon to each class for use in tab bar and dashboard
    for cls in classes:
        cls["icon"] = _get_icon_for_entity(cls["name"])

    # Build tab_classes from architect-specified tab order in ux_preferences
    tab_order = ux_prefs.get("navigation", {}).get("tab_order") if isinstance(ux_prefs.get("navigation"), dict) else None
    if tab_order:
        class_by_name = {cls["name"].lower(): cls for cls in classes}
        tab_classes = []
        for entity in tab_order:
            cls_item = class_by_name.get(entity.lower())
            if cls_item:
                tab_classes.append(cls_item)
        # append any classes not in tab_order (up to max 3 total)
        named = {cls["name"].lower() for cls in tab_classes}
        for cls in classes:
            if len(tab_classes) >= 3:
                break
            if cls["name"].lower() not in named:
                tab_classes.append(cls)
    else:
        tab_classes = classes[:3]

    # Get primary colour from ux_preferences (fallback to hardcoded default)
    primary_color = (
        ux_prefs.get("design_system", {}).get("primary_color")
        or ux_prefs.get("primary_color")
        or "#6366f1"
    )

    bundle_id = mobile_cfg.get("bundle_id", f"com.archie.{solution_slug.replace('-', '')}")
    privacy_policy_url = mobile_cfg.get("privacy_policy_url", "https://your-domain.com/privacy")
    terms_url = mobile_cfg.get("terms_url", "https://your-domain.com/terms")
    api_base_url = mobile_cfg.get("api_base_url", "https://api.your-domain.com")
    expo_project_id = mobile_cfg.get("expo_project_id", "")
    monitoring_cfg = mobile_cfg.get("monitoring", {})
    monitoring_enabled = monitoring_cfg.get("enabled", False)

    base_ctx = {
        "solution_name": solution_name,
        "solution_slug": solution_slug,
        "app_slug": solution_slug,
        "classes": classes,
        "tab_classes": tab_classes,
        "primary_color": primary_color,
        "auth": auth,
        "offline_tier": offline_tier,
        "offline_entities": offline_entities,
        "push_channels": push_channels,
        "push_enabled": push_enabled,
        "features": list(features),
        "has_biometric": has_biometric,
        "bundle_id": bundle_id,
        "privacy_policy_url": privacy_policy_url,
        "terms_url": terms_url,
        "api_base_url": api_base_url,
        "expo_project_id": expo_project_id,
        "monitoring_enabled": monitoring_enabled,
        "mobile_ui_framework": mobile_ui_framework,
    }

    files: dict = {}

    # ── Root config files ──
    # NativeWind-only files that must be excluded when using Paper
    _NATIVEWIND_ONLY = {"tailwind.config.js.j2", "global.css.j2"}

    single_templates = [
        ("package.json.j2", "mobile/package.json"),
        ("app.json.j2", "mobile/app.json"),
        ("tsconfig.json.j2", "mobile/tsconfig.json"),
        ("babel.config.js.j2", "mobile/babel.config.js"),
        ("metro.config.js.j2", "mobile/metro.config.js"),
        ("tailwind.config.js.j2", "mobile/tailwind.config.js"),
        ("global.css.j2", "mobile/global.css"),
        ("eas.json.j2", "mobile/eas.json"),
        ("README.md.j2", "mobile/README.md"),
        ("gitignore.j2", "mobile/.gitignore"),
        # Core lib files
        ("src/lib/schemas.ts.j2", "mobile/src/lib/schemas.ts"),
        ("src/lib/api.ts.j2", "mobile/src/lib/api.ts"),
        # Navigation
        ("app/_layout.tsx.j2", "mobile/app/_layout.tsx"),
        ("app/(tabs)/_layout.tsx.j2", "mobile/app/(tabs)/_layout.tsx"),
        ("app/index.tsx.j2", "mobile/app/(tabs)/index.tsx"),
        ("app/(tabs)/profile.tsx.j2", "mobile/app/(tabs)/profile.tsx"),
    ]

    # Auth screens
    if auth != "none":
        single_templates.extend([
            ("app/login.tsx.j2", "mobile/app/login.tsx"),
            ("app/register.tsx.j2", "mobile/app/register.tsx"),
            ("src/providers/AuthProvider.tsx.j2", "mobile/src/providers/AuthProvider.tsx"),
        ])

    # Genome-driven templates
    # Offline cache (always — Tier 1 is read cache, Tier 2 adds mutation queue)
    single_templates.append(
        ("src/lib/offline_cache.ts.j2", "mobile/src/lib/offline_cache.ts"),
    )

    # Push notifications
    if push_enabled:
        single_templates.append(
            ("src/lib/push_notifications.ts.j2", "mobile/src/lib/push_notifications.ts"),
        )

    # Biometric gate
    if has_biometric:
        single_templates.append(
            ("src/providers/BiometricGate.tsx.j2", "mobile/src/providers/BiometricGate.tsx"),
        )

    # Always-on components and hooks
    single_templates.extend([
        ("components/offline_banner.tsx.j2", "mobile/src/components/OfflineBanner.tsx"),
        ("components/status_badge.tsx.j2", "mobile/src/components/StatusBadge.tsx"),
        ("src/lib/auth_store.ts.j2", "mobile/src/lib/auth_store.ts"),
        ("hooks/use_entity.ts.j2", "mobile/src/hooks/useEntity.ts"),
        ("hooks/use_offline_sync.ts.j2", "mobile/src/hooks/useOfflineSync.ts"),
        ("hooks/use_push_notifications.ts.j2", "mobile/src/hooks/usePushNotifications.ts"),
        ("jest.config.js.j2", "mobile/jest.config.js"),
        ("jest.setup.js.j2", "mobile/jest.setup.js"),
        ("store-metadata/app-store.md.j2", "mobile/store-metadata/app-store.md"),
        ("store-metadata/play-store.md.j2", "mobile/store-metadata/play-store.md"),
        ("store-metadata/SCREENSHOTS.md.j2", "mobile/store-metadata/SCREENSHOTS.md"),
        ("assets/generate-assets.sh.j2", "mobile/assets/generate-assets.sh"),
        ("assets/create-placeholders.py.j2", "mobile/assets/create-placeholders.py"),
    ])

    # Sentry crash reporting (conditional on genome.mobile.monitoring.enabled)
    if monitoring_enabled:
        single_templates.append(
            ("src/lib/sentry.ts.j2", "mobile/src/lib/sentry.ts"),
        )

    # Render single templates
    for tpl_name, out_path in single_templates:
        # Skip NativeWind-exclusive config files when using Paper
        if mobile_ui_framework == "paper" and tpl_name in _NATIVEWIND_ONLY:
            logger.debug("Mobile template %s skipped (paper framework, NativeWind-only)", tpl_name)
            continue
        try:
            tpl = env.get_template(tpl_name)
            files[out_path] = tpl.render(**base_ctx)
        except Exception as exc:
            logger.debug("Mobile template %s skipped: %s", tpl_name, exc)
            # Don't write error comments — just skip missing templates

    # ── Per-resource screens ──
    # List screens live inside (tabs) so the tab bar can navigate to them natively.
    # New/Detail remain Stack-level routes (with back button / modal presentation).
    per_resource_templates = [
        ("app/[resource]/index.tsx.j2", "mobile/app/(tabs)/{slug}.tsx"),
        ("app/[resource]/new.tsx.j2", "mobile/app/{slug}/new.tsx"),
        ("app/[resource]/[id].tsx.j2", "mobile/app/{slug}/[id].tsx"),
        ("__tests__/[resource].test.tsx.j2", "mobile/__tests__/{slug}.test.tsx"),
    ]

    for cls in classes:
        slug = cls.get("table_name") or cls["name"].lower()
        # Add state machine info if this module has one
        module_key = _find_module_key(modules, cls["name"])
        state_machine = None
        if module_key:
            state_machine = modules[module_key].get("state_machine")

        cls_ctx = {
            **base_ctx,
            "name": cls["name"],
            "table_name": slug,
            "fields": cls.get("fields", []),
            "relationships": cls.get("relationships", []),
            "validations": cls.get("validations", []),
            "description": cls.get("description", ""),
            "state_machine": state_machine,
            "is_offline_entity": module_key in offline_entities,
            "use_pagination": cls.get("use_pagination", False),
            # Aliases for test template compatibility
            "entity_name": cls["name"],
            "resource_name": slug,
            "confirmed_fields": cls.get("fields", []),
        }

        for tpl_name, out_pattern in per_resource_templates:
            out_path = out_pattern.format(slug=slug)
            try:
                tpl = env.get_template(tpl_name)
                files[out_path] = tpl.render(**cls_ctx)
            except Exception as exc:
                logger.debug("Mobile resource template %s skipped for %s: %s", tpl_name, slug, exc)

    # ── Generate .env.example with mobile-specific vars ──
    env_lines = [
        f"# {solution_name} — Mobile App Environment",
        f"EXPO_PUBLIC_API_URL=http://localhost:8000",
    ]
    if push_enabled:
        env_lines.append("# Firebase project ID for push notifications")
        env_lines.append("EXPO_PUBLIC_FIREBASE_PROJECT_ID=")
    env_lines.append("")
    files["mobile/.env.example"] = "\n".join(env_lines)

    return files


def _modules_to_classes(modules: dict) -> list:
    """Convert genome modules to the class list format that Expo templates expect.

    Templates expect: [{name, table_name, fields: [{name, type, ...}], relationships, validations}]
    """
    classes = []
    for mod_key, mod_def in modules.items():
        root = mod_def.get("aggregate_root")
        if not root:
            continue

        # Convert genome fields to template-expected format
        fields = []
        for field in mod_def.get("fields", {}).get(root, []):
            f = {
                "name": field.get("name", ""),
                "type": _genome_type_to_ts(field.get("type", "string")),
                "required": field.get("required", True),
                "description": field.get("description", ""),
            }
            if field.get("format"):
                f["format"] = field["format"]
            if field.get("enum_values"):
                f["enum"] = field["enum_values"]
            if field.get("max_length"):
                f["maxLength"] = field["max_length"]
            if field.get("foreign_key"):
                f["foreignKey"] = field["foreign_key"]
            fields.append(f)

        # Build validations from fields
        validations = []
        for field in fields:
            if field.get("required"):
                validations.append({
                    "field": field["name"],
                    "type": "required",
                    "message": f"{field['name']} is required",
                })
            if field.get("format") == "email":
                validations.append({
                    "field": field["name"],
                    "type": "email",
                    "message": "Must be a valid email",
                })
            if field.get("maxLength"):
                validations.append({
                    "field": field["name"],
                    "type": "maxLength",
                    "value": field["maxLength"],
                    "message": f"Max {field['maxLength']} characters",
                })

        # Build relationships from foreign keys
        relationships = []
        for field in mod_def.get("fields", {}).get(root, []):
            fk = field.get("foreign_key")
            if fk:
                ref_entity = fk.split(".")[0]
                relationships.append({
                    "field": field["name"],
                    "target": ref_entity,
                    "type": "belongsTo",
                })

        slug = re.sub(r"[^a-z0-9]", "_", root.lower()).strip("_")
        classes.append({
            "name": root,
            "table_name": slug,
            "fields": fields,
            "relationships": relationships,
            "validations": validations,
            "description": mod_def.get("_rationale", ""),
        })

    return classes


def _find_module_key(modules: dict, entity_name: str) -> Optional[str]:
    """Find the module key that contains the given entity as aggregate root."""
    for mod_key, mod_def in modules.items():
        if mod_def.get("aggregate_root") == entity_name:
            return mod_key
    return None


_TS_TYPE_MAP = {
    "string": "string",
    "integer": "number",
    "float": "number",
    "decimal": "number",
    "boolean": "boolean",
    "datetime": "string",
    "date": "string",
    "text": "string",
    "json": "object",
    "uuid": "string",
    "enum": "string",
}


def _genome_type_to_ts(genome_type: str) -> str:
    """Map genome field type to TypeScript type."""
    return _TS_TYPE_MAP.get(genome_type, "string")
