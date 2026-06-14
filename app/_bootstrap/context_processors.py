"""
Context processors — global template variables.
"""

import flask


def init_context_processors(app):
    """Register all context processors for Jinja templates."""

    _dashboard_categories_cache = {"data": None, "timestamp": 0}
    _applications_cache = {"data": None, "timestamp": 0}
    _cache_ttl = 300  # 5 minutes

    @app.context_processor
    def inject_dashboard_categories():
        """Make dashboard categories available to all templates - OPTIMIZED WITH CACHING"""
        import time
        from collections import defaultdict

        from flask import request, url_for
        from sqlalchemy.exc import OperationalError, ProgrammingError

        from app.extensions import db
        try:
            from app.main.dynamic_dashboards import MODEL_REGISTRY
        except ImportError:
            MODEL_REGISTRY = {}  # module deleted, dashboard categories disabled

        default_result = {"dashboard_categories": {}, "dashboard_registry_url": "#"}

        try:
            if request.endpoint and not any(
                path in request.path for path in ["/auto-dashboard", "/dashboard"]
            ):
                return default_result
        except Exception:
            return default_result

        current_time = time.time()
        if (
            _dashboard_categories_cache["data"] is not None
            and current_time - _dashboard_categories_cache["timestamp"] < _cache_ttl
        ):
            result = _dashboard_categories_cache["data"].copy()
            try:
                result["dashboard_registry_url"] = url_for(
                    "dynamic_dashboards.model_registry_index"
                )
            except Exception:
                result["dashboard_registry_url"] = "#"
            return result

        try:
            category_icons = {
                "Vendor Management": "store",
                "Application Architecture": "layers",
                "Business Architecture": "building - 2",
                "Implementation": "rocket",
                "Governance": "scale",
                "Strategy": "target",
                "Technology": "cpu",
                "Data Architecture": "database",
                "Cost Intelligence": "dollar-sign",
                "Compliance": "shield-check",
                "Requirements": "file-text",
                "Reference Models": "book-open",
                "Enterprise Intelligence": "brain",
                "Integration": "link",
            }

            categories = defaultdict(list)
            for model_name, info in MODEL_REGISTRY.items():
                category = info.get("category", "Other")
                try:
                    model_class = info.get("model")
                    if model_class is not None:
                        count = model_class.query.count()
                    else:
                        count = 0
                except (OperationalError, ProgrammingError):
                    db.session.rollback()
                    count = 0
                except Exception:
                    count = 0
                categories[category].append(
                    {
                        "name": model_name,
                        "label": info.get("label", model_name),
                        "count": count,
                        "icon": info.get("icon", "database"),
                        "description": info.get("description", ""),
                    }
                )

            for category in categories:
                categories[category].sort(
                    key=lambda x: (-x["count"], x["label"])
                )
            sorted_categories = dict(
                sorted(
                    categories.items(),
                    key=lambda item: (-sum(m["count"] for m in item[1]), item[0]),
                )
            )
            for cat_name in sorted_categories:
                sorted_categories[cat_name] = [
                    {**m, "icon": category_icons.get(cat_name, "folder")}
                    if "icon" not in m or m["icon"] == "database"
                    else m
                    for m in sorted_categories[cat_name]
                ]

            _dashboard_categories_cache["data"] = {
                "dashboard_categories": sorted_categories,
            }
            _dashboard_categories_cache["timestamp"] = current_time

            try:
                registry_url = url_for("dynamic_dashboards.model_registry_index")
            except Exception:
                registry_url = "#"  # blueprint not registered

            return {
                "dashboard_categories": sorted_categories,
                "dashboard_registry_url": registry_url,
            }
        except (OperationalError, ProgrammingError):
            db.session.rollback()
            return default_result
        except Exception as e:  # fabricated-values-ok
            app.logger.debug(f"Error loading dashboard categories: {e}")
            return default_result

    @app.context_processor
    def inject_guardrail_status():
        """Make guardrail status available to admin templates"""
        return {"guardrail_status": "active"}

    @app.context_processor
    def inject_applications_and_vendors():
        """Make applications and vendors available to admin templates that need them"""
        import time

        from flask import request
        from sqlalchemy.exc import OperationalError, ProgrammingError

        from app.extensions import db

        try:
            if request.endpoint and not any(
                path in request.path
                for path in ["/admin", "/capability", "/architecture", "/enterprise"]
            ):
                return {"applications": [], "vendors": []}
        except Exception:
            return {"applications": [], "vendors": []}

        current_time = time.time()
        if (
            _applications_cache["data"] is not None
            and current_time - _applications_cache["timestamp"] < _cache_ttl
        ):
            return _applications_cache["data"]

        try:
            from app.models.application_portfolio import ApplicationComponent

            applications = (
                ApplicationComponent.query.order_by(ApplicationComponent.name).all()
            )

            try:
                from app.models.vendor.vendor_organization import VendorOrganization
                vendors = VendorOrganization.query.order_by(VendorOrganization.name).all()
            except Exception:
                vendors = []

            result = {"applications": applications, "vendors": vendors}
            _applications_cache["data"] = result
            _applications_cache["timestamp"] = current_time
            return result
        except (OperationalError, ProgrammingError):
            db.session.rollback()
            return {"applications": [], "vendors": []}
        except Exception as e:  # fabricated-values-ok
            db.session.rollback()
            app.logger.debug(f"Error loading applications/vendors: {e}")
            return {"applications": [], "vendors": []}

    @app.context_processor
    def inject_flask():
        """Make flask object available to all templates to fix flash messaging issues"""
        return {"flask": flask}

    _nav_counts_cache = {"data": None, "timestamp": 0}

    @app.context_processor
    def inject_nav_counts():
        """Live entity counts for sidebar navigation labels.

        Replaces hardcoded counts that go stale (sidebar said 358 vendors
        while the dashboard card said 17). Cached for 5 minutes — these
        render on every page.
        """
        import time

        now = time.time()
        if (
            _nav_counts_cache["data"] is not None
            and now - _nav_counts_cache["timestamp"] < _cache_ttl
        ):
            return {"nav_counts": _nav_counts_cache["data"]}

        counts = {"applications": 0, "vendors": 0, "elements": 0, "capabilities": 0}
        try:
            from app import db
            from app.models.application_portfolio import ApplicationComponent
            from app.models.archimate_core import ArchiMateElement
            from app.models.business_capabilities import BusinessCapability
            from app.models.vendor.vendor_organization import VendorOrganization

            counts["applications"] = (
                db.session.query(db.func.count(ApplicationComponent.id)).scalar() or 0
            )
            counts["vendors"] = (
                db.session.query(db.func.count(VendorOrganization.id)).scalar() or 0
            )
            counts["elements"] = (
                db.session.query(db.func.count(ArchiMateElement.id)).scalar() or 0
            )
            counts["capabilities"] = (
                db.session.query(db.func.count(BusinessCapability.id)).scalar() or 0
            )
            _nav_counts_cache["data"] = counts
            _nav_counts_cache["timestamp"] = now
        except Exception as e:
            app.logger.warning(f"nav counts unavailable: {e}")

        return {"nav_counts": counts}

    @app.context_processor
    def inject_feature_flags():
        """Make feature flag helpers available to all templates"""
        from app.models import FeatureFlag

        return {
            "is_feature_enabled": FeatureFlag.is_feature_enabled,
            "get_feature": lambda key: FeatureFlag.query.filter_by(key=key).first(),
            "sidebar_features": FeatureFlag.get_sidebar_features,
        }

    @app.context_processor
    def inject_north_star_config():
        """Make North Star navigation flags available to templates.
        
        Phase 1: Renamed terms, hidden admin items (NORTH-STAR-001)
        Phase 2: Complete ArchiMate 3.2 layer navigation (NORTH-STAR-002)
        Phase 3: Professional visual polish (NORTH-STAR-003)
        """
        from app.models import FeatureFlag
        
        # Initialize defaults — Phase 3 (professional blue theme) is ON by default:
        # the North Star visual standard is the platform's committed direction.
        phase1_enabled = True
        phase2_enabled = True
        phase3_enabled = True

        try:
            phase1_flag = FeatureFlag.query.filter_by(key='north_star_navigation').first()
            if phase1_flag:
                phase1_enabled = phase1_flag.enabled

            phase2_flag = FeatureFlag.query.filter_by(key='north_star_phase2').first()
            if phase2_flag:
                phase2_enabled = phase2_flag.enabled

            phase3_flag = FeatureFlag.query.filter_by(key='north_star_phase3').first()
            if phase3_flag:
                phase3_enabled = phase3_flag.enabled

        except Exception as e:
            # A failing query earlier in the request can poison the transaction so
            # these FeatureFlag reads raise InFailedSqlTransaction. Roll back so the
            # rest of the request (and the pooled connection) recovers cleanly.
            try:
                from app.extensions import db
                db.session.rollback()
            except Exception:
                pass
            app.logger.error(f"North Star context processor error: {e}", exc_info=True)

        return {
            "north_star_enabled": phase1_enabled,
            "north_star_phase2_enabled": phase2_enabled,
            "north_star_phase3_enabled": phase3_enabled,
            # Short alias used in base templates
            "phase3_enabled": phase3_enabled,
        }

    @app.context_processor
    def inject_user_feature_flags():
        """Provide feature flags as a JSON-serializable dict for Alpine.store('user')."""
        from flask_login import current_user

        from app.models import FeatureFlag

        if not current_user.is_authenticated:
            return {"user_feature_flags": {}}

        try:
            flags = FeatureFlag.query.filter_by(enabled=True).all()
            flag_dict = {f.key: True for f in flags}
            return {"user_feature_flags": flag_dict}
        except Exception:
            from app.extensions import db
            db.session.rollback()
            return {"user_feature_flags": {}}

    @app.context_processor
    def inject_page_guide_context():
        """Provide resolved page-guide context to authenticated templates."""
        from flask import request
        from flask_login import current_user

        if not current_user.is_authenticated:
            return {"page_guide_context": {"enabled": False, "supported": False}}

        try:
            from app.modules.ai_chat.services.page_guide_registry import (
                build_generic_page_guide,
                resolve_page_guide,
            )
            from app.modules.ai_chat.services.page_guide_service import PageGuideService

            entry = resolve_page_guide(request.endpoint, request.view_args or {})
            enabled = PageGuideService.is_enabled()
            if not entry:
                if not enabled:
                    return {"page_guide_context": {"enabled": False, "supported": False}}
                entry = build_generic_page_guide(request.endpoint, request.view_args or {})

            return {
                "page_guide_context": {
                    "enabled": enabled,
                    "supported": entry.get("guide_mode") == "specialized",
                    "guide_mode": entry.get("guide_mode", "specialized"),
                    "page_key": entry["page_key"],
                    "scope_key": entry["scope_key"],
                    "title": entry["title"],
                    "summary": entry["summary"],
                    "starter_questions": entry.get("starter_questions", []),
                    "glossary": entry.get("glossary", []),
                    "suggested_actions": entry.get("suggested_actions", []),
                }
            }
        except Exception:
            return {"page_guide_context": {"enabled": False, "supported": False}}

    # S1-01: Role-based sidebar section visibility
    ROLE_SECTION_MAP = {
        "enterprise_architect": {
            "home", "application", "architecture", "solutions",
            "roadmaps", "governance", "capabilities", "tools",
            "data", "utilities", "admin",
        },
        "solutions_architect": {
            "home", "application", "architecture", "solutions",
            "governance", "capabilities",
        },
        "business_architect": {
            "home", "capabilities", "governance", "architecture",
        },
        "data_architect": {
            "home", "architecture", "application", "capabilities", "data",
        },
        "technology_architect": {
            "home", "architecture", "application", "tools", "utilities",
        },
        "application_architect": {
            "home", "application", "capabilities", "architecture",
        },
        "integration_architect": {
            "home", "architecture", "application", "tools", "utilities",
        },
        "compliance": {
            "home", "governance", "architecture", "roadmaps",
        },
        "manager": {
            "home", "governance", "roadmaps", "architecture",
        },
    }

    # PLT-040: enterprise_role-based sidebar visibility (takes precedence over archetype)
    # NS-006: Updated for North Star Persona MVP with 8 enterprise roles
    ENTERPRISE_ROLE_SECTION_MAP = {
        "solution_architect": {
            "home", "solutions", "portfolio", "architecture", "capabilities",
            "roadmaps", "governance", "data_integration",
        },
        "enterprise_architect": {
            "home", "solutions", "portfolio", "architecture", "capabilities",
            "roadmaps", "governance", "data_integration",
            # Legacy aliases
            "application", "tools", "data", "utilities",
        },
        "arb_member": {
            "home", "solutions", "portfolio", "governance",
        },
        "portfolio_manager": {
            "home", "solutions", "portfolio", "capabilities", "roadmaps",
            "governance", "procurement",
            # Legacy aliases
            "application", "tools",
        },
        "cto": {
            "home", "solutions", "portfolio", "capabilities", "roadmaps",
            "governance",
        },
        "procurement": {
            "home", "portfolio", "procurement",
            # Legacy alias for portfolio
            "application",
        },
        "application_manager": {
            "home", "solutions", "portfolio", "my_applications", "roadmaps",
            # Legacy alias for portfolio
            "application",
        },
        "platform_admin": {
            "home", "solutions", "portfolio", "architecture", "capabilities",
            "roadmaps", "governance", "procurement", "my_applications",
            "data_integration", "administration",
            # Legacy aliases for backward compatibility
            "application", "tools", "data", "utilities", "admin",
        },
    }

    @app.context_processor
    def inject_user_visible_sections():
        """Inject role-based sidebar sections for persona-specific navigation (S1-01, NS-006)."""
        from flask_login import current_user

        # Default: show everything (admins and unknown roles see all)
        # NS-006: Added portfolio, procurement, my_applications, data_integration, administration
        all_sections = {
            "home", "application", "architecture", "solutions",
            "roadmaps", "governance", "capabilities", "tools",
            "data", "utilities", "admin",
            # North Star Persona MVP sections
            "portfolio", "procurement", "my_applications",
            "data_integration", "administration",
        }

        if not current_user.is_authenticated:
            return {"user_visible_sections": all_sections, "show_all_sections": True}

        # Check localStorage-backed "Show All" override (passed via cookie)
        from flask import request
        show_all = request.cookies.get("show_all_sections") == "true"

        if show_all or current_user.is_admin():
            return {"user_visible_sections": all_sections, "show_all_sections": True}

        # PLT-040: enterprise_role takes precedence over role_archetype
        enterprise_role = getattr(current_user, "enterprise_role", None)
        if enterprise_role:
            ent_key = enterprise_role.strip().lower().replace(" ", "_")
            if ent_key in ENTERPRISE_ROLE_SECTION_MAP:
                return {"user_visible_sections": ENTERPRISE_ROLE_SECTION_MAP[ent_key], "show_all_sections": False}

        archetype = getattr(current_user, "role_archetype", None)
        if archetype:
            key = archetype.strip().lower().replace(" ", "_")
            visible = ROLE_SECTION_MAP.get(key, all_sections)
        else:
            visible = all_sections

        return {"user_visible_sections": visible, "show_all_sections": False}

    app.jinja_env.globals["flask"] = flask

    # NS-006: Register role-based access functions for persona navigation
    from app.utils.role_access import role_access_context_processor
    role_funcs = role_access_context_processor()
    for name, func in role_funcs.items():
        app.jinja_env.globals[name] = func

    # Register HTML sanitizer filter for safe rendering of user-generated rich text
    from app.utils.html_sanitizer import sanitize_html
    app.jinja_env.filters["sanitize_html"] = sanitize_html

    # Register error humanization filter for workflow error messages
    from app.utils.template_utils import humanize_error
    app.jinja_env.filters["humanize_error"] = humanize_error

    # Register date/datetime formatting filters
    def _filter_format_date(value, fmt='%d %b %Y'):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        return str(value)

    def _filter_format_datetime(value, fmt='%d %b %Y %H:%M'):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        return str(value)

    app.jinja_env.filters["format_date"] = _filter_format_date
    app.jinja_env.filters["format_datetime"] = _filter_format_datetime

    # Cache-busting: compute git hash once at startup for static file versioning
    import subprocess
    _static_version = None
    try:
        _static_version = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8").strip()
    except Exception:
        import time
        _static_version = str(int(time.time()))

    @app.context_processor
    def inject_static_version():
        """Provide static_version for cache-busting JS/CSS includes."""
        return {"static_version": _static_version}

    def _filter_versioned_static(filename):
        """Jinja2 filter: {{ 'js/foo.js' | versioned_static }}
        Returns URL with ?v=<git_hash> for cache-busting."""
        url = flask.url_for("static", filename=filename)
        return f"{url}?v={_static_version}"

    app.jinja_env.filters["versioned_static"] = _filter_versioned_static

    # Override url_for globally so ALL static file references auto-version.
    # This covers all 132 uses across 66 templates without touching each file.
    _original_url_for = flask.url_for

    def _versioned_url_for(endpoint, **values):
        url = _original_url_for(endpoint, **values)
        if endpoint == "static" and _static_version:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}v={_static_version}"
        return url

    app.jinja_env.globals["url_for"] = _versioned_url_for

    # COM-013: Expose POSTHOG_API_KEY to templates for the browser JS snippet.
    @app.context_processor
    def inject_posthog_key():
        import os
        return {"posthog_key": os.environ.get("POSTHOG_API_KEY", "")}
