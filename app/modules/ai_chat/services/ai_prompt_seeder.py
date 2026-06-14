"""AI Prompt Templates Seeder

Seeds a small set of default AIPromptTemplate records if none exist.
Non-critical; best-effort and safe to run on app startup.
"""


def seed_default_ai_prompt_templates():
    """Create default AIPromptTemplate rows if missing."""
    try:
        from datetime import datetime

        from app import db
        from app.models.ai_service import AIPromptTemplate

        templates = [
            {
                "name": "archimate_3_2_generation",
                "description": "Generate ArchiMate 3.2 elements for a solution (strict JSON output).",
                "system_prompt": (
                    "You are an enterprise architecture expert specializing in ArchiMate 3.2. "
                    "Given a solution description, produce a strict JSON object with keys: motivation, strategy, business, application, technology, implementation. "
                    "Each key maps to a list of elements where each element is an object with element_type, name, and description. Output ONLY valid JSON."
                ),
                "user_prompt_template": (
                    "Analyze the following solution and suggest ArchiMate 3.2 elements per layer in JSON:\n{solution_json}\n"
                    "Return only JSON conforming to the schema described in the system prompt."
                ),
                "category": "Generation",
            },
            {
                "name": "options_analysis_rationale",
                "description": "Generate decision rationale and evidence for comparing solution options.",
                "system_prompt": (
                    "You are an enterprise architecture decision analyst. Given scored solution options and supporting data, produce a structured decision rationale. "
                    "Include winner, confidence_score (0.0 - 1.0), key evidence points, risks, and mitigations. Output strict JSON."
                ),
                "user_prompt_template": (
                    "Given these options and their scores:\n{options_json}\nAnd weights: {weights_json}\nProvide a JSON rationale with fields: winner_id, confidence_score, evidence:[...], recommended_actions:[...], and short_executive_summary."
                ),
                "category": "Analysis",
            },
            {
                "name": "arb_draft_mapping",
                "description": "Map option analysis outputs to ARB submission fields (auto-fill).",
                "system_prompt": (
                    "You are an Architecture Review Board assistant. Map analysis outputs to ARB submission fields and produce a filled ARB JSON including title, description, business_justification, technical_assessment, risk_analysis, implementation_approach, and cost_estimates. Output strict JSON."
                ),
                "user_prompt_template": (
                    "Map the following analysis output into an ARB draft JSON:\n{analysis_json}\nReturn only the ARB JSON object."
                ),
                "category": "Transformation",
            },
        ]

        created = 0
        for t in templates:
            existing = AIPromptTemplate.query.filter_by(name=t["name"]).first()
            if existing:
                continue
            row = AIPromptTemplate(
                name=t["name"],
                description=t["description"],
                system_prompt=t["system_prompt"],
                user_prompt_template=t["user_prompt_template"],
                category=t.get("category", "general"),
            )
            db.session.add(row)
            created += 1

        if created:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        # Seeding must be best-effort and non-fatal at startup
        pass
