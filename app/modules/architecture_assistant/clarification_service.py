"""Step 1 Clarification Service — generates targeted questions from the problem brief.

Flow:
1. User enters problem description
2. generate_questions() → LLM produces 3-5 specific clarifying questions
3. User answers (or skips with defaults)
4. merge_answers() → produces enriched brief for motivation element generation
"""

import json
import logging

logger = logging.getLogger(__name__)

CLARIFICATION_PROMPT = """You are an enterprise architect reviewing a problem statement. Generate exactly 4-5 clarifying questions.

PROBLEM DESCRIPTION:
{problem_statement}

PORTFOLIO CONTEXT — entities already tracked in this enterprise architecture platform:
{portfolio_context}

Return EXACTLY 4-5 questions in this order:

QUESTION 1 (MANDATORY — entity elicitation, id: "q_entities"):
Ask the user to name 3-6 specific record types or objects this system will manage.
Example wording: "What are the main types of records or objects this system needs to manage? Please name 3-6 specific things — for example, a vendor risk tracker might manage: Vendor, RiskAssessment, ComplianceReport, AuditFinding, RemediationAction."
type: "entity_names", entity_type: null

QUESTION 2 (MANDATORY — auth model, id: "q_auth"):
Ask who uses the system and what each type of user can do. Reference portfolio entities by name where known.
Example: "Who are the different types of users, and what is the most important action each type can perform? (e.g., Compliance Officer: approve/reject vendor risk scores; Vendor Manager: submit compliance documents; Admin: configure scoring thresholds)"
type: "auth_model", entity_type: null

QUESTIONS 3-5 (generate 2-3 architecture-specific questions):
1. REFERENCE existing portfolio entities BY NAME when relevant
2. For entity-selection questions, use type: "entity_picker" and entity_type: one of applications/capabilities/archimate_elements/vendors
3. Focus on: integration boundaries, key business rules this system enforces automatically, data flows, compliance constraints
4. NEVER ask about budget, timeline, or boilerplate NFRs

Return ONLY valid JSON:
{{
    "questions": [
        {{
            "id": "q_entities",
            "question": "What are the main types of records or objects this system needs to manage? Please name 3-6 specific things...",
            "context": "These names become the data model. Specific names produce domain-specific code — generic names produce generic scaffolding.",
            "skip_default": "Will be inferred from the problem statement keywords",
            "type": "entity_names",
            "entity_type": null
        }},
        {{
            "id": "q_auth",
            "question": "Who are the different types of users, and what is the most important action each type can perform?",
            "context": "Defines access controls, route guards, and RBAC configuration in generated code",
            "skip_default": "Single authenticated user role with full access",
            "type": "auth_model",
            "entity_type": null
        }}
    ]
}}"""

MERGE_PROMPT = """Merge this problem description with the clarifying answers into a structured brief.

ORIGINAL PROBLEM:
{original_brief}

CLARIFYING ANSWERS:
{answers_text}

Return the merged brief in this EXACT format. Use these section headers verbatim:

## Core Entities
[From the q_entities answer: comma-separated PascalCase names. If no answer, derive 4-6 domain-specific names from the problem statement. Example: Vendor, RiskAssessment, ComplianceReport, AuditFinding]

## Access Model
[From the q_auth answer: one line per role — "RoleName: can do X, Y, Z". If no answer, derive 2-3 roles from context. Example: ComplianceOfficer: review and approve vendor risk scores | VendorManager: submit compliance documents | Admin: configure scoring rules]

## Business Rules
[Any explicit rules from the answers — one line each, starting with a trigger condition. Omit this section entirely if no rules were mentioned.]

## Problem Description
[All original detail plus enriched context from the remaining answers, as flowing prose. Keep all specifics.]"""


STOPWORDS = frozenset({
    # English grammar/function words ONLY — domain words like 'application',
    # 'cloud', 'CRM', 'legacy' are deliberately kept for portfolio matching.
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    'just', 'because', 'but', 'and', 'or', 'if', 'while', 'that', 'this',
    'these', 'those', 'what', 'which', 'who', 'whom', 'its', 'our', 'we',
    'they', 'them', 'their', 'your', 'you', 'any', 'also', 'about',
})


class ClarificationService:
    """Generates clarifying questions and merges answers into enriched brief."""

    def _extract_keywords(self, text):
        """Extract meaningful keywords from problem statement for portfolio search.

        Uses 3+ char minimum (catches CRM, SAP, ERP, API) and minimal stopwords
        that only remove English grammar words — domain words are preserved.
        """
        import re
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        return list(dict.fromkeys(w for w in words if w not in STOPWORDS))[:12]

    def _get_portfolio_context(self, problem_statement):
        """Query existing portfolio entities matching the problem statement keywords."""
        keywords = self._extract_keywords(problem_statement)
        if not keywords:
            return "No matching entities found. This appears to be a greenfield initiative."

        sections = []
        try:
            from app import db
            from app.models.capability_models import BusinessCapability
            name_filters = [BusinessCapability.name.ilike(f'%{kw}%') for kw in keywords]
            desc_filters = [BusinessCapability.description.ilike(f'%{kw}%') for kw in keywords]
            caps = BusinessCapability.query.filter(
                db.or_(*name_filters, *desc_filters)
            ).limit(15).all()
            if caps:
                cap_lines = []
                for c in caps:
                    parts = [f'- {c.name}']
                    if hasattr(c, 'description') and c.description:
                        parts.append(f'({c.description[:100]})')
                    cap_lines.append(' '.join(parts))
                sections.append('Relevant capabilities already in this platform:\n' + '\n'.join(cap_lines))
        except Exception as e:
            logger.warning('Portfolio context: capability query failed: %s', e)

        try:
            from app import db
            from app.models.archimate_core import ArchiMateElement
            name_filters = [ArchiMateElement.name.ilike(f'%{kw}%') for kw in keywords]
            desc_filters = [ArchiMateElement.description.ilike(f'%{kw}%') for kw in keywords]
            elems = ArchiMateElement.query.filter(
                db.or_(*name_filters, *desc_filters)
            ).limit(15).all()
            if elems:
                elem_lines = []
                for e in elems:
                    parts = [f'- {e.name} ({e.type}/{e.layer})']
                    if hasattr(e, 'description') and e.description:
                        parts.append(f'— {e.description[:100]}')
                    elem_lines.append(' '.join(parts))
                sections.append('Relevant ArchiMate elements:\n' + '\n'.join(elem_lines))
        except Exception as e:
            logger.warning('Portfolio context: ArchiMate query failed: %s', e)

        try:
            from app import db
            from app.models.application_portfolio import ApplicationComponent
            name_filters = [ApplicationComponent.name.ilike(f'%{kw}%') for kw in keywords]
            desc_filters = [ApplicationComponent.description.ilike(f'%{kw}%') for kw in keywords]
            apps = db.session.query(ApplicationComponent).filter(
                db.or_(*name_filters, *desc_filters)
            ).limit(15).all()
            if apps:
                app_lines = []
                for a in apps:
                    parts = [f'- {a.name}']
                    if hasattr(a, 'description') and a.description:
                        parts.append(f'({a.description[:100]})')
                    app_lines.append(' '.join(parts))
                sections.append('Relevant applications in the portfolio:\n' + '\n'.join(app_lines))
        except Exception as e:
            logger.warning('Portfolio context: application query failed: %s', e)

        if not sections:
            return "No matching entities found in the platform. This appears to be a greenfield initiative. Focus questions on what NEW capabilities and integrations are needed."

        # Count total matches — if very few, likely spurious matches on generic words
        total_matches = sum(s.count('\n- ') for s in sections)
        if total_matches <= 2:
            return "Few matching entities found (possibly coincidental). Treat this as likely greenfield. " + '\n\n'.join(sections)

        return '\n\n'.join(sections)

    def _build_clarification_prompt(self, problem_statement, portfolio_context=''):
        return CLARIFICATION_PROMPT.format(
            problem_statement=problem_statement,
            portfolio_context=portfolio_context or 'No portfolio data available.',
        )

    def generate_questions(self, problem_statement: str) -> list:
        """Generate 3-5 targeted clarifying questions from the problem brief.

        Returns list of dicts: [{id, question, context, skip_default, type, entity_type}]
        Returns empty list if LLM fails.
        """
        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            portfolio_context = self._get_portfolio_context(problem_statement)
            prompt = self._build_clarification_prompt(problem_statement, portfolio_context)
            raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider)

            if not raw_text:
                return []

            # Parse JSON from response
            import re
            text = raw_text.strip()
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```\s*$', '', text)

            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(text[json_start:json_end])
                questions = parsed.get("questions", [])
                return questions[:5]  # Max 5 questions

            return []
        except Exception as e:
            logger.error("Failed to generate clarifying questions: %s", e)
            return []

    def merge_answers(self, original_brief: str, answers: list) -> str:
        """Merge the original brief with clarifying answers into an enriched brief.

        Args:
            original_brief: The original problem description
            answers: List of dicts [{question_id, question, answer}]

        Returns:
            Enriched brief string. Falls back to original if LLM fails.
        """
        if not answers:
            return original_brief

        answers_text = "\n".join(
            f"Q: {a.get('question', '?')}\nA: {a.get('answer', 'Skipped')}"
            for a in answers
            if a.get("answer")  # Skip unanswered
        )

        if not answers_text:
            return original_brief

        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            prompt = MERGE_PROMPT.format(
                original_brief=original_brief,
                answers_text=answers_text,
            )
            raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider)
            return raw_text.strip() if raw_text else original_brief
        except Exception as e:
            logger.error("Failed to merge answers: %s", e)
            return original_brief
