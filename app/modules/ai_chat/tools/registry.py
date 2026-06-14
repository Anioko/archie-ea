"""
Tool registry for AI Chat agent mode.

Each schema defines one operation the LLM can invoke. The 'tier' field controls
execution behaviour:
  - 'auto'    : executed immediately, no user confirmation required
  - 'approve' : queued for explicit user confirmation before any DB write

Tools always accept names (not IDs) — the EntityResolver converts them.
"""

TOOL_SCHEMAS = [
    {
        "name": "create_solution",
        "description": (
            "Create a new architectural solution in the repository. "
            "Use when the user asks to design, propose, plan, or create a new solution, "
            "programme, or initiative."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short, descriptive name for the solution (e.g. 'CRM Modernisation')",
                },
                "description": {
                    "type": "string",
                    "description": "Business problem the solution addresses",
                },
                "business_domain": {
                    "type": "string",
                    "description": "Primary business domain",
                    "enum": [
                        "customer", "finance", "hr", "operations",
                        "technology", "supply_chain", "risk", "legal",
                    ],
                },
                "solution_type": {
                    "type": "string",
                    "description": "Classification of the solution",
                    "enum": ["Platform", "Product", "Service", "Integration", "Migration"],
                },
            },
            "required": ["name", "description"],
        },
        "tier": "auto",
    },
    {
        "name": "link_capability_to_solution",
        "description": (
            "Link a business capability to a solution to show what capabilities "
            "the solution delivers, enables, or affects. "
            "Use when the user wants to map capabilities to a solution."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_name": {
                    "type": "string",
                    "description": "Name of the solution (fuzzy matched)",
                },
                "capability_name": {
                    "type": "string",
                    "description": "Name of the business capability (fuzzy matched)",
                },
                "support_level": {
                    "type": "string",
                    "description": "How the solution supports this capability",
                    "enum": ["primary", "secondary", "planned", "partial"],
                },
                "notes": {
                    "type": "string",
                    "description": "Optional rationale or notes for the mapping",
                },
            },
            "required": ["solution_name", "capability_name"],
        },
        "tier": "auto",
    },
    {
        "name": "link_application_to_capability",
        "description": (
            "Map an application to a business capability it supports. "
            "Use when the user wants to record which applications cover a capability."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "application_name": {
                    "type": "string",
                    "description": "Name of the application (fuzzy matched)",
                },
                "capability_name": {
                    "type": "string",
                    "description": "Name of the business capability (fuzzy matched)",
                },
                "coverage_level": {
                    "type": "string",
                    "description": "Degree to which the application covers the capability",
                    "enum": ["full", "partial", "planned"],
                },
                "notes": {"type": "string"},
            },
            "required": ["application_name", "capability_name"],
        },
        "tier": "auto",
    },
    {
        "name": "create_archimate_element",
        "description": (
            "Create a new ArchiMate element and optionally attach it to a solution. "
            "Use when the user asks to model a component, service, process, data object, "
            "or any other ArchiMate concept."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Element name (e.g. 'Customer Data Service')",
                },
                "type": {
                    "type": "string",
                    "description": (
                        "ArchiMate element type. Examples: ApplicationComponent, "
                        "ApplicationService, BusinessProcess, BusinessFunction, "
                        "DataObject, TechnologyService, SystemSoftware, Node"
                    ),
                },
                "layer": {
                    "type": "string",
                    "description": "ArchiMate layer",
                    "enum": ["business", "application", "technology", "motivation", "implementation"],
                },
                "description": {"type": "string"},
                "solution_name": {
                    "type": "string",
                    "description": "Solution to attach this element to (optional, fuzzy matched)",
                },
            },
            "required": ["name", "type", "layer"],
        },
        "tier": "auto",
    },
    {
        "name": "update_application_status",
        "description": (
            "Update the deployment/lifecycle status of an application. "
            "Use when the user wants to mark an application as retiring, "
            "decommissioned, in production, strategic, etc. "
            "REQUIRES USER CONFIRMATION before executing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "application_name": {
                    "type": "string",
                    "description": "Name of the application (fuzzy matched)",
                },
                "new_status": {
                    "type": "string",
                    "description": "New lifecycle/deployment status",
                    "enum": [
                        "design", "development", "testing",
                        "production", "retiring", "decommissioned",
                    ],
                },
                "rationale": {
                    "type": "string",
                    "description": "Business reason for the status change",
                },
            },
            "required": ["application_name", "new_status", "rationale"],
        },
        "tier": "approve",
    },
    {
        "name": "submit_for_arb_review",
        "description": (
            "Submit a solution for Architecture Review Board (ARB) governance review. "
            "REQUIRES USER CONFIRMATION before executing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_name": {
                    "type": "string",
                    "description": "Name of the solution to submit (fuzzy matched)",
                },
                "phase": {
                    "type": "string",
                    "description": "TOGAF ADM phase at which the review is requested",
                    "enum": ["concept", "design", "build", "deploy"],
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context or questions for the ARB",
                },
            },
            "required": ["solution_name", "phase"],
        },
        "tier": "approve",
    },
    {
        "name": "query_capability_gaps",
        "description": (
            "Find business capabilities with no supporting applications, "
            "or capabilities below a specified maturity threshold. "
            "Read-only — safe to execute without confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_maturity": {
                    "type": "integer",
                    "description": "Return capabilities AT or BELOW this maturity level (1-5). Default 2.",
                    "minimum": 1,
                    "maximum": 5,
                },
                "business_domain": {
                    "type": "string",
                    "description": "Filter by business domain (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 20)",
                    "default": 20,
                    "maximum": 100,
                },
            },
        },
        "tier": "auto",
    },
    {
        "name": "find_applications",
        "description": (
            "Search for applications by name, status, or capability. "
            "Read-only — safe to execute without confirmation. "
            "Use when the user asks what applications exist, "
            "which apps support a capability, or wants to find a specific app."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name_contains": {
                    "type": "string",
                    "description": "Partial name to search for",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by deployment status",
                    "enum": [
                        "design", "development", "testing",
                        "production", "retiring", "decommissioned",
                    ],
                },
                "capability_name": {
                    "type": "string",
                    "description": "Return only apps linked to this capability",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 15)",
                    "default": 15,
                    "maximum": 50,
                },
            },
        },
        "tier": "auto",
    },
    # ------------------------------------------------------------------ #
    # J1 CRUD tools                                                       #
    # ------------------------------------------------------------------ #
    {
        "name": "create_driver",
        "description": (
            "Add a business driver to a solution (ArchiMate Motivation layer). "
            "Use when the user says a solution is motivated by cost pressure, compliance, "
            "market demand, or any other business force."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer", "description": "Solution ID (injected from context when on blueprint page)"},
                "name": {"type": "string", "description": "Short driver name, e.g. 'Regulatory Compliance Pressure'"},
                "description": {"type": "string", "description": "Explanation of the driver"},
                "driver_type": {
                    "type": "string",
                    "enum": ["technology", "stakeholder", "external", "internal"],
                    "description": "Category of driver",
                },
            },
            "required": ["solution_id", "name", "driver_type"],
        },
        "tier": "auto",
    },
    {
        "name": "create_goal",
        "description": (
            "Add a goal to a solution (ArchiMate Motivation layer). "
            "Use when the user describes a desired outcome or success criterion."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "name": {"type": "string", "description": "Goal statement, e.g. 'Reduce TCO 20% in 12 months'"},
                "description": {"type": "string"},
                "priority": {"type": "integer", "description": "1 (highest) to 5 (lowest)", "minimum": 1, "maximum": 5},
            },
            "required": ["solution_id", "name"],
        },
        "tier": "auto",
    },
    {
        "name": "create_constraint",
        "description": (
            "Add a constraint to a solution (ArchiMate Motivation layer). "
            "Use when the user mentions a hard limit: budget cap, regulatory requirement, timeline, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "name": {"type": "string", "description": "Constraint name, e.g. 'Budget cap £500k'"},
                "description": {"type": "string"},
                "constraint_type": {
                    "type": "string",
                    "enum": ["budget", "timeline", "resource", "compliance", "technical", "organizational"],
                },
                "severity": {"type": "integer", "description": "1 (soft) to 5 (hard limit)", "minimum": 1, "maximum": 5},
            },
            "required": ["solution_id", "name", "constraint_type"],
        },
        "tier": "auto",
    },
    {
        "name": "create_requirement",
        "description": (
            "Add a functional or non-functional requirement to a solution. "
            "Use when the user specifies something the solution MUST do or achieve."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "name": {"type": "string", "description": "Requirement name, e.g. 'Support 1000 concurrent users'"},
                "description": {"type": "string"},
                "requirement_type": {
                    "type": "string",
                    "enum": ["functional", "quality", "constraint"],
                },
            },
            "required": ["solution_id", "name", "description", "requirement_type"],
        },
        "tier": "auto",
    },
    {
        "name": "create_risk",
        "description": (
            "Add a risk to a solution risk register. "
            "Use when the user identifies a threat, concern, or uncertainty for the solution."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "risk_description": {"type": "string", "description": "Description of the risk"},
                "impact": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "probability": {"type": "string", "enum": ["low", "medium", "high"]},
                "mitigation": {"type": "string", "description": "Optional mitigation strategy"},
            },
            "required": ["solution_id", "risk_description", "impact", "probability"],
        },
        "tier": "auto",
    },
    {
        "name": "create_option",
        "description": (
            "Add a Phase E solution option/recommendation. "
            "Use when the user describes an approach: buy a product, build custom, reuse existing, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "name": {"type": "string", "description": "Option name, e.g. 'Buy Vendor Solution'"},
                "option_type": {
                    "type": "string",
                    "enum": ["buy", "build", "reuse", "partner", "hybrid"],
                },
            },
            "required": ["solution_id", "name", "option_type"],
        },
        "tier": "auto",
    },
    {
        "name": "mark_option_recommended",
        "description": (
            "Mark one solution option as the architect's recommended choice. "
            "Use when the user selects or endorses a specific option."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "option_name": {"type": "string", "description": "Name of the option to mark (fuzzy matched)"},
            },
            "required": ["solution_id", "option_name"],
        },
        "tier": "auto",
    },
    {
        "name": "link_application_to_solution",
        "description": (
            "Link an existing application from the 850-app catalog to a solution. "
            "Use when the user says a solution involves, replaces, or integrates with an application."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "application_name": {"type": "string", "description": "Application name (fuzzy matched against 850 apps)"},
                "role": {
                    "type": "string",
                    "enum": ["primary", "supporting", "integrating"],
                    "description": "How the application relates to the solution",
                },
            },
            "required": ["solution_id", "application_name"],
        },
        "tier": "auto",
    },
    {
        "name": "link_vendor_product",
        "description": (
            "Link a vendor product from the catalog to a solution (Phase E). "
            "Use when the user identifies a commercial product as part of the technology stack."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "vendor_product_name": {"type": "string", "description": "Vendor product name (fuzzy matched)"},
            },
            "required": ["solution_id", "vendor_product_name"],
        },
        "tier": "auto",
    },
    {
        "name": "run_inference_engine",
        "description": (
            "Run the ArchiMate Inference Engine on a solution's elements to fill missing "
            "cross-layer chain elements (Motivation→Strategy→Business→Application→Technology→Implementation). "
            "Use when the user asks to complete, fill in, or repair the architecture chain."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, show what would be created without writing to DB. Default false.",
                },
            },
            "required": ["solution_id"],
        },
        "tier": "auto",
    },
    {
        "name": "generate_blueprint_narrative",
        "description": (
            "Generate an AI narrative for a specific blueprint section. "
            "REQUIRES USER CONFIRMATION — this overwrites existing section text. "
            "section_id examples: sec-1 (Summary), sec-2 (Strategic), sec-3 (Business), "
            "sec-4 (Application), sec-5 (Options), sec-7 (Governance), sec-8 (Risks)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "section_id": {"type": "string", "description": "Blueprint section ID, e.g. 'sec-2'"},
            },
            "required": ["solution_id", "section_id"],
        },
        "tier": "approve",
    },
    # ------------------------------------------------------------------ #
    # ArchiMate Intelligence tools                                        #
    # ------------------------------------------------------------------ #
    {
        "name": "create_archimate_relationship",
        "description": (
            "Create a typed ArchiMate relationship between two existing elements. "
            "Use when the user wants to model how elements connect."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_element_name": {"type": "string", "description": "Source element name (fuzzy matched)"},
                "target_element_name": {"type": "string", "description": "Target element name (fuzzy matched)"},
                "relationship_type": {
                    "type": "string",
                    "enum": ["Realization", "Serving", "Assignment", "Aggregation", "Composition",
                             "Association", "Influence", "Triggering", "Flow", "Specialization", "Access"],
                },
                "solution_id": {"type": "integer", "description": "Solution to attach to (optional)"},
            },
            "required": ["source_element_name", "target_element_name", "relationship_type"],
        },
        "tier": "auto",
    },
    {
        "name": "diagnose_chain",
        "description": (
            "Show missing elements in an ArchiMate element's chain without repairing. "
            "Read-only. Use when the user asks what's incomplete or what's missing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "element_name": {"type": "string", "description": "Element name (fuzzy matched)"},
            },
            "required": ["element_name"],
        },
        "tier": "auto",
    },
    {
        "name": "explain_element",
        "description": (
            "Explain why an ArchiMate element exists by tracing its upstream provenance chain. "
            "Read-only. Use when the user asks 'why does X exist?' or 'what drives X?'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "element_name": {"type": "string", "description": "Element name (fuzzy matched)"},
            },
            "required": ["element_name"],
        },
        "tier": "auto",
    },
    {
        "name": "simulate_impact",
        "description": (
            "Show the blast radius if an ArchiMate element is retired or changed. "
            "Read-only. Returns all downstream dependents across all 6 layers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "element_name": {"type": "string", "description": "Element name (fuzzy matched)"},
            },
            "required": ["element_name"],
        },
        "tier": "auto",
    },
    # ------------------------------------------------------------------ #
    # Solution State tools                                                #
    # ------------------------------------------------------------------ #
    {
        "name": "get_solution_summary",
        "description": (
            "Read the current state of a solution: maturity score, linked entity counts, "
            "ARB status, and completeness gaps. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
            },
            "required": ["solution_id"],
        },
        "tier": "auto",
    },
    {
        "name": "get_completeness_score",
        "description": (
            "Get the blueprint completeness score with dimension breakdown "
            "(Elements %, Relationships %, Traceability %). Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
            },
            "required": ["solution_id"],
        },
        "tier": "auto",
    },
    {
        "name": "update_solution_fields",
        "description": (
            "Update solution metadata: owner, business_sponsor, technical_lead, or description. "
            "Use when the user assigns roles or updates the solution description."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "solution_owner": {"type": "string"},
                "business_sponsor": {"type": "string"},
                "technical_lead": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["solution_id"],
        },
        "tier": "auto",
    },
    {
        "name": "update_solution_phase",
        "description": (
            "Advance the solution's TOGAF ADM phase (A through H). "
            "Use when the user says they're done with a phase and ready to move on."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer"},
                "phase": {
                    "type": "string",
                    "enum": ["A", "B", "C", "D", "E", "F", "G", "H"],
                    "description": "Target ADM phase",
                },
            },
            "required": ["solution_id", "phase"],
        },
        "tier": "auto",
    },
    # ------------------------------------------------------------------ #
    # Capability Architect Phase 2-4 grounding tools                     #
    # ------------------------------------------------------------------ #
    {
        "name": "search_capabilities_by_problem",
        "description": (
            "Semantic search over 516 business capabilities to find which ones "
            "are most relevant to a stated problem or initiative. "
            "Use at the START of Phase 2 — before asking the user what capabilities "
            "they need. Returns capabilities ranked by relevance with maturity gaps "
            "and current application coverage count. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "problem_description": {
                    "type": "string",
                    "description": "The problem or initiative description to search against",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max capabilities to return (default 10, max 25)",
                    "default": 10,
                    "maximum": 25,
                },
            },
            "required": ["problem_description"],
        },
        "tier": "auto",
    },
    {
        "name": "find_applications_by_capability",
        "description": (
            "Find all applications in the 881-app catalog already mapped to a "
            "specific business capability. "
            "Use at Phase 4 (Application layer) to ground architecture in real "
            "existing systems rather than inventing application names. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "capability_name": {
                    "type": "string",
                    "description": "Business capability name (fuzzy matched)",
                },
            },
            "required": ["capability_name"],
        },
        "tier": "auto",
    },
    {
        "name": "find_technical_capabilities",
        "description": (
            "Find technical capabilities from the ACM (Application Capability Model) taxonomy "
            "across 7 domains: USER-EXPERIENCE, APPLICATION-SERVICES, DATA-STORAGE, "
            "SECURITY-IDENTITY, DEVOPS-PLATFORM, AI-ANALYTICS, COMMUNICATION. "
            "Use at Phase 5 (Technology layer) BEFORE suggesting Nodes or SystemSoftware — "
            "grounds the technology architecture in the real 273-capability taxonomy. "
            "Returns L1/L2 capabilities with how many apps already cover each one. "
            "Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter by ACM domain (optional)",
                    "enum": [
                        "USER-EXPERIENCE", "APPLICATION-SERVICES", "DATA-STORAGE",
                        "SECURITY-IDENTITY", "DEVOPS-PLATFORM", "AI-ANALYTICS", "COMMUNICATION",
                    ],
                },
                "query": {
                    "type": "string",
                    "description": "Keyword search across capability names and descriptions (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max capabilities to return (default 15, max 30)",
                    "default": 15,
                    "maximum": 30,
                },
            },
        },
        "tier": "auto",
    },
    {
        "name": "search_archimate_elements",
        "description": (
            "Search ArchiMate elements by name, layer, or type. Read-only. "
            "Use when the user asks what elements exist or wants to find a specific element."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name_contains": {"type": "string"},
                "layer": {
                    "type": "string",
                    "enum": ["motivation", "strategy", "business", "application", "technology", "implementation"],
                },
                "element_type": {"type": "string", "description": "e.g. ApplicationComponent, BusinessProcess"},
                "limit": {"type": "integer", "default": 15, "maximum": 50},
            },
        },
        "tier": "auto",
    },
    # ------------------------------------------------------------------ #
    # Gap-closure tools (AI-Architect capability expansion)              #
    # ------------------------------------------------------------------ #
    {
        "name": "verify_codegen",
        "description": (
            "Verify that a solution's generated artifacts trace back to ArchiMate sources. "
            "Checks application-layer coverage, data-layer coverage, technology-layer presence, "
            "and element name quality. Returns a score (0-100), grade (A-F), and findings. "
            "USE when: codegen was run on a solution and the user asks if it's conformant; "
            "after building a solution architecture to check it's ready for generation; "
            "or when the user asks about codegen quality or ARB readiness for a solution. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {"type": "integer", "description": "Solution to verify"},
                "solution_name": {"type": "string", "description": "Solution name (fuzzy matched if solution_id not provided)"},
            },
        },
        "tier": "auto",
    },
    {
        "name": "propose_rationalization",
        "description": (
            "Generate autonomous TIME (Tolerate/Invest/Migrate/Eliminate) rationalization proposals "
            "from portfolio data. Surfaces ELIMINATE candidates with no active programme, "
            "capability duplication clusters, on-premise migration backlog, and INVEST apps needing "
            "sponsorship — all with evidence and recommended next steps. "
            "USE when the user asks: 'what should we retire?', 'where are we duplicating capability?', "
            "'what's the rationalization pipeline?', or any portfolio optimisation question. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max proposals to return (default 10)",
                    "default": 10,
                    "maximum": 25,
                },
            },
        },
        "tier": "auto",
    },
    {
        "name": "build_architecture_plan",
        "description": (
            "Build a multi-step architecture execution plan for a goal. "
            "Selects the right template (SAP transformation, rationalization, solution design, "
            "data governance, programme setup) and returns an ordered list of steps, each with "
            "the ARCHIE tool to call, dependency on previous steps, and a gate-check condition. "
            "USE when the user says 'help me plan', 'what are the steps to', 'sequence this work', "
            "or asks how to execute a transformation, design, or programme. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The architecture goal or work to plan (natural language)",
                },
                "solution_id": {
                    "type": "integer",
                    "description": "If the plan is for a specific solution, provide its ID",
                },
            },
            "required": ["goal"],
        },
        "tier": "auto",
    },
    {
        "name": "poll_infrastructure",
        "description": (
            "Check configured infrastructure endpoints for reachability. "
            "Probes: Abacus API connector, LLM API endpoints, integration pattern URLs. "
            "Returns up/down status per endpoint, latency, and a delta summary of what's "
            "modelled in ARCHIE vs what's actually reachable. "
            "USE when the user asks about connectivity, 'is X reachable?', infrastructure health, "
            "or wants to know if configured integrations are live. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_abacus": {"type": "boolean", "default": True},
                "include_llm": {"type": "boolean", "default": True},
                "additional_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra URLs to probe (max 20)",
                },
            },
        },
        "tier": "auto",
    },
    {
        "name": "infer_schema",
        "description": (
            "Parse SQL DDL or OpenAPI 3.x JSON/YAML and infer ArchiMate DataObject elements. "
            "Returns a list of DataObject candidates with field attributes, ready to create "
            "via create_archimate_element. Does NOT write to DB — returns candidates for review. "
            "USE when the user pastes a CREATE TABLE statement, OpenAPI schema block, or asks "
            "'import this schema', 'create data objects from this DDL', or similar. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "The DDL or OpenAPI JSON/YAML text to parse",
                },
                "format": {
                    "type": "string",
                    "enum": ["ddl", "openapi", "auto"],
                    "description": "Input format. 'auto' detects from content (default).",
                    "default": "auto",
                },
                "solution_id": {
                    "type": "integer",
                    "description": "If provided, the inferred DataObjects will be suggested for this solution",
                },
            },
            "required": ["input_text"],
        },
        "tier": "auto",
    },
    {
        "name": "validate_sap_clean_core",
        "description": (
            "Validate a solution's architecture against the SAP RISE clean-core extension model. "
            "Detects Tier 3/4 violations (RFC/BAPI integrations, CMOD/SMOD modifications, direct SAP coupling, "
            "missing BTP mediation layer, legacy ECC/R3 systems) and returns a scored compliance report. "
            "USE THIS TOOL whenever the user asks about: SAP clean core, RISE compliance, S/4HANA upgrade "
            "readiness, SAP extension model, custom code risk, ABAP modifications, BTP architecture, "
            "or SAP transformation posture. Also use proactively when a solution contains SAP components "
            "and the user asks about its architecture quality or ARB readiness. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solution_id": {
                    "type": "integer",
                    "description": "ID of the solution to validate",
                },
                "solution_name": {
                    "type": "string",
                    "description": "Name of the solution (used to resolve solution_id if not provided; fuzzy matched)",
                },
                "include_portfolio_scan": {
                    "type": "boolean",
                    "description": (
                        "If true, scan all solutions with SAP footprint and return a portfolio-level "
                        "compliance summary. Use when the user asks about the overall SAP estate or "
                        "programme-level clean-core posture."
                    ),
                    "default": False,
                },
            },
        },
        "tier": "auto",
    },
]

# Index by name for O(1) lookup
TOOL_SCHEMA_BY_NAME = {s["name"]: s for s in TOOL_SCHEMAS}
