"""
STACK_REGISTRY — single source of truth for all supported codegen language slugs.

IMPORTANT FOR LLM AGENTS:
  Every entry defines exactly what a language slug generates and does NOT generate.
  Read the 'description' and 'api_only' / 'frontend' fields before choosing a slug.
  Silent assumptions about stack composition are the #1 source of wrong codegen choices.

Key rules:
  - 'react-shadcn' uses FastAPI as backend. There is NO Flask + Next.js option.
  - 'python-fastapi' and 'python-flask' are API-only — they produce NO frontend code.
  - 'react-native-expo' is mobile-only — it produces NO backend or web frontend code.
  - 'azure-bicep' and 'azure-logic-app' are infrastructure/workflow — NO application code.
  - 'power-platform-solution' is no-code — NO server-side application code.

Schema per entry:
  backend  (str|None): exact backend framework slug, or None if none
  frontend (str|None): exact frontend framework slug, or None if none
  mobile   (str|None): exact mobile framework slug, or None if none
  label    (str):      short human-readable name for UI display
  description (str):  full description including explicit "no X" statements
  api_only (bool):    True when the stack produces API code with no UI component
  is_fullstack (bool):True when stack produces BOTH backend AND frontend code
  in_ui    (bool):    True when this slug should appear in the Step 7 language selector
"""

STACK_REGISTRY: dict[str, dict] = {
    "python-fastapi": {
        "backend": "fastapi",
        "frontend": None,
        "mobile": None,
        "label": "Python API (FastAPI)",
        "description": (
            "FastAPI + SQLAlchemy + Alembic + pytest. "
            "API only — produces NO frontend code. "
            "For FastAPI + Next.js frontend, use 'react-shadcn' instead."
        ),
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "python-flask": {
        "backend": "flask",
        "frontend": None,
        "mobile": None,
        "label": "Python API (Flask)",
        "description": (
            "Flask + SQLAlchemy + pytest. "
            "API only — produces NO frontend code. "
            "There is NO Flask + Next.js full-stack option. "
            "For a full-stack app with Next.js, use 'react-shadcn' (FastAPI backend)."
        ),
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "go-chi": {
        "backend": "go-chi",
        "frontend": None,
        "mobile": None,
        "label": "Go API (Chi)",
        "description": "Chi router + pgx + testify. API only — produces NO frontend code.",
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "java-spring-boot": {
        "backend": "spring-boot",
        "frontend": None,
        "mobile": None,
        "label": "Java API (Spring Boot)",
        "description": "Spring Boot 3 + JPA + JUnit 5. API only — produces NO frontend code.",
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "salesforce-apex": {
        "backend": "apex",
        "frontend": "lwc",
        "mobile": None,
        "label": "Salesforce (Apex + LWC)",
        "description": "Apex classes + Lightning Web Components + Custom Objects. Salesforce platform only.",
        "api_only": False,
        "is_fullstack": True,
        "in_ui": True,
    },
    "react-shadcn": {
        "backend": "fastapi",
        "frontend": "nextjs-14",
        "mobile": None,
        "label": "Full-Stack (FastAPI + Next.js 14)",
        "description": (
            "FastAPI backend + Next.js 14 App Router + shadcn/ui + Tailwind CSS. "
            "Backend is FastAPI — NOT Flask. "
            "For Flask + Next.js, use 'flask-nextjs' instead."
        ),
        "api_only": False,
        "is_fullstack": True,
        "in_ui": True,
    },
    "flask-nextjs": {
        "backend": "flask",
        "frontend": "nextjs-14",
        "mobile": None,
        "label": "Full-Stack (Flask + Next.js 14)",
        "description": (
            "Flask backend + Next.js 14 App Router + shadcn/ui + Tailwind CSS. "
            "Flask Blueprints + Flask-SQLAlchemy + Marshmallow + Flask-JWT-Extended. "
            "Frontend: Next.js 14 App Router with per-entity CRUD pages, typed API client, Zod schemas."
        ),
        "api_only": False,
        "is_fullstack": True,
        "in_ui": True,
    },
    "flask-react": {
        "backend": "flask",
        "frontend": "react-vite",
        "mobile": None,
        "label": "Full-Stack (Flask + React SPA)",
        "description": (
            "Flask backend + React 18 SPA via Vite + shadcn/ui + Tailwind CSS + React Router v6. "
            "Flask Blueprints + Flask-SQLAlchemy + Marshmallow + Flask-JWT-Extended. "
            "Frontend: Vite + React 18 + TypeScript with per-entity CRUD pages and typed API client."
        ),
        "api_only": False,
        "is_fullstack": True,
        "in_ui": True,
    },
    "react-native-expo": {
        "backend": None,
        "frontend": None,
        "mobile": "expo",
        "label": "React Native (Expo)",
        "description": (
            "Expo + React Native + NativeWind. "
            "Mobile only — produces NO backend or web frontend code. "
            "Pair with 'python-fastapi' for the API layer."
        ),
        "api_only": False,
        "is_fullstack": False,
        "in_ui": True,
    },
    "sap-cap": {
        "backend": "sap-cap",
        "frontend": None,
        "mobile": None,
        "label": "SAP CAP",
        "description": "SAP Cloud Application Programming Model — CDS schema + service + handlers.",
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "azure-bicep": {
        "backend": None,
        "frontend": None,
        "mobile": None,
        "label": "Azure Bicep (IaC)",
        "description": (
            "Azure Bicep + ARM templates. "
            "Infrastructure only — produces NO application code, no frontend, no backend."
        ),
        "api_only": False,
        "is_fullstack": False,
        "in_ui": True,
    },
    "power-platform-solution": {
        "backend": None,
        "frontend": "power-apps",
        "mobile": None,
        "label": "Power Platform Solution",
        "description": (
            "Power Apps canvas app + Power Automate flows + solution.xml. "
            "No-code platform — produces NO server-side application code."
        ),
        "api_only": False,
        "is_fullstack": False,
        "in_ui": True,
    },
    "sap-btp-integration": {
        "backend": "sap-btp",
        "frontend": None,
        "mobile": None,
        "label": "SAP BTP Integration Suite",
        "description": "SAP BTP Integration Suite iFlow XML + OData service + deploy script.",
        "api_only": True,
        "is_fullstack": False,
        "in_ui": True,
    },
    "azure-logic-app": {
        "backend": None,
        "frontend": None,
        "mobile": None,
        "label": "Azure Logic App",
        "description": (
            "Azure Logic App workflow JSON + ARM deployment template. "
            "No-code workflow — produces NO application backend code."
        ),
        "api_only": False,
        "is_fullstack": False,
        "in_ui": True,
    },
}

# Derived set for O(1) membership checks — kept for backward compat
SUPPORTED_LANGUAGES: set[str] = set(STACK_REGISTRY)


def describe_stack(language: str) -> str:
    """Return a concise human-readable description for a language slug.

    Used in error messages so LLMs get explicit corrective text, not just
    a list of valid slugs.

    Example:
        describe_stack("react-shadcn")
        → "Full-Stack (FastAPI + Next.js 14): FastAPI backend + Next.js 14 ..."
    """
    entry = STACK_REGISTRY.get(language)
    if not entry:
        valid = ", ".join(sorted(STACK_REGISTRY))
        return f"Unknown language '{language}'. Valid slugs: {valid}"
    return f"{entry['label']}: {entry['description']}"


def validate_language(language: str | None) -> list[str]:
    """Return a list of error strings (empty = valid).

    Validates that the language slug exists in the registry and returns
    corrective error messages if not — messages include explicit "X does not
    exist" statements so LLMs cannot rationalize their way to wrong choices.
    """
    if not language:
        return [
            "genome.language is required. "
            f"Set to one of: {', '.join(sorted(STACK_REGISTRY))}. "
            "See app/modules/codegen/stack_registry.py for full stack details."
        ]
    if language not in STACK_REGISTRY:
        common_mistakes = {
            "flask":             "python-flask (API only — no frontend)",
            "fastapi":           "python-fastapi (API only — no frontend)",
            "flask-nextjs":      "flask-nextjs (Flask + Next.js 14 full-stack)",
            "flask-react":       "flask-react (Flask + React SPA full-stack)",
            "python":            "python-fastapi or python-flask",
            "react":             "react-shadcn (FastAPI + Next.js 14) or flask-nextjs (Flask + Next.js 14)",
            "nextjs":            "react-shadcn (FastAPI + Next.js 14) or flask-nextjs (Flask + Next.js 14)",
            "next.js":           "react-shadcn (FastAPI + Next.js 14) or flask-nextjs (Flask + Next.js 14)",
            "full-stack":        "react-shadcn (FastAPI + Next.js 14), flask-nextjs (Flask + Next.js 14), or flask-react (Flask + React SPA)",
            "fullstack":         "react-shadcn (FastAPI + Next.js 14), flask-nextjs (Flask + Next.js 14), or flask-react (Flask + React SPA)",
            "react-native":      "react-native-expo",
            "expo":              "react-native-expo",
            "spring":            "java-spring-boot",
            "spring-boot":       "java-spring-boot",
        }
        suggestion = common_mistakes.get(language.lower())
        if suggestion is None:
            # Explicitly non-existent combination
            msg = (
                f"genome.language='{language}' does not exist in this system. "
                "Available stacks: " + ", ".join(sorted(STACK_REGISTRY))
            )
        elif suggestion:
            msg = (
                f"genome.language='{language}' is not a valid slug. "
                f"Did you mean: {suggestion}? "
                "Available stacks: " + ", ".join(sorted(STACK_REGISTRY))
            )
        else:
            msg = (
                f"genome.language='{language}' is not recognised. "
                "Available stacks: " + ", ".join(sorted(STACK_REGISTRY))
            )
        return [msg]
    return []
