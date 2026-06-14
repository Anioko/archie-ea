"""
ADR Service - Generate Architecture Decision Records with LLM
Sprint 1.5: ADR Generation (Quick Win Feature)

File: app/services/adr_service.py
"""

import json

from flask import current_app

from app.extensions import db
from app.models.adr_models import ArchitectureDecisionRecord
from app.services.llm.openai_service import OpenAIService


class ADRService:
    """Service for generating and managing Architecture Decision Records"""

    def __init__(self):
        self.llm = OpenAIService(model="gpt - 4 - turbo")

    def generate_adr_from_session(self, session_id, tenant_id, user_id):
        """
        Generate ADR from completed architecture session

        Args:
            session_id: Architecture session ID
            tenant_id: Tenant ID
            user_id: User ID

        Returns:
            ArchitectureDecisionRecord: Generated ADR
        """
        from app.services.architecture_assistant_service import ArchitectureAssistantService

        assistant_service = ArchitectureAssistantService()
        session = assistant_service.get_session(session_id, tenant_id)

        # Validate session is ready for ADR
        if not session.selected_option:
            raise ValueError("No solution option selected")

        # Build context from session data
        context = self._build_adr_context(session)

        # Generate ADR using LLM
        adr_content = self._generate_adr_with_llm(context, tenant_id, user_id, session_id)

        # Get next ADR number for tenant
        next_number = ArchitectureDecisionRecord.get_next_adr_number(tenant_id)

        # Create ADR record
        adr = ArchitectureDecisionRecord(
            tenant_id=tenant_id,
            session_id=session_id,
            adr_number=next_number,
            title=adr_content["title"],
            status="proposed",
            context=adr_content["context"],
            decision=adr_content["decision"],
            consequences=adr_content.get("consequences", ""),
            stakeholders=session.stakeholders or [],
            options_considered=self._extract_options(session),
            decision_criteria=adr_content.get("decision_criteria", {}),
            created_by=user_id,
        )

        db.session.add(adr)
        db.session.commit()

        return adr

    def _build_adr_context(self, session):
        """Extract context from session for ADR generation"""
        return {
            "capability": {
                "name": session.capability.name,
                "description": session.capability.description,
            },
            "gap_analysis": {
                "gaps": session.gap_analysis.gaps_identified if session.gap_analysis else [],
                "impact": session.gap_analysis.impact_assessment if session.gap_analysis else {},
            },
            "selected_option": {
                "approach": session.selected_option.approach,
                "description": session.selected_option.description,
                "technologies": session.selected_option.technologies or [],
                "cost": session.selected_option.estimated_cost,
                "pros": session.selected_option.pros or [],
                "cons": session.selected_option.cons or [],
            },
            "alternatives": [
                {
                    "approach": opt.approach,
                    "description": opt.description,
                    "rejected_reason": getattr(opt, "rejection_reason", "Not selected"),
                }
                for opt in session.options
                if opt.id != session.selected_option.id
            ],
        }

    def _generate_adr_with_llm(self, context, tenant_id, user_id, session_id):
        """Use LLM to generate ADR content"""

        system_prompt = """You are an expert Enterprise Architect creating Architecture Decision Records.
Follow the Nygard format. Respond with valid JSON only."""

        user_prompt = f"""Create an Architecture Decision Record for this decision:

**Capability:** {context['capability']['name']}
**Problem:** {context['gap_analysis'].get('gaps', [])}

**Selected Option:**
- Approach: {context['selected_option']['approach']}
- Description: {context['selected_option']['description']}
- Technologies: {context['selected_option']['technologies']}

**Alternatives Considered:**
{context['alternatives']}

Generate ADR with:
1. Title (concise, describes decision)
2. Context (the issue we're addressing)
3. Decision (what we decided to do)
4. Consequences (positive and negative impacts)

Respond with JSON only."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        adr_text = self.llm.generate_completion(
            messages=messages,
            temperature=0.6,
            max_tokens=2500,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            operation="adr_generation",
        )

        return json.loads(adr_text)

    def export_adr_markdown(self, adr_id, tenant_id):
        """Export ADR as Markdown"""
        adr = self._get_adr(adr_id, tenant_id)

        markdown = f"""# ADR-{adr.adr_number:04d}: {adr.title}

**Status:** {adr.status.upper()}
**Date:** {adr.proposed_date.strftime('%Y-%m-%d')}

## Context

{adr.context}

## Decision

{adr.decision}

## Consequences

{adr.consequences}

---
*Created by: User {adr.created_by}*
*Approved by: User {adr.approved_by or 'Pending'}*
"""
        return markdown

    def _get_adr(self, adr_id, tenant_id):
        """Get ADR with tenant check"""
        adr = (
            db.session.query(ArchitectureDecisionRecord)
            .filter_by(id=adr_id, tenant_id=tenant_id)
            .first()
        )

        if not adr:
            raise ValueError(f"ADR {adr_id} not found")

        return adr

    def _extract_options(self, session):
        """Extract options for ADR"""
        return [
            {
                "approach": opt.approach,
                "description": opt.description,
                "selected": opt.id == session.selected_option.id,
            }
            for opt in session.options
        ]
