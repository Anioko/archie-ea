"""RAG service for Architecture Assistant — retrieves organizational context."""
import logging
from app import db

logger = logging.getLogger(__name__)


class ArchitectureRAGService:
    """Retrieves relevant organizational context for LLM prompts."""

    def get_context_for_solution(self, business_domain=None, capability_ids=None, max_tokens=2000):
        """Gather architecture principles, prior decisions, and reference architectures."""
        ctx = {
            "principles": self._get_principles(business_domain),
            "prior_decisions": self._get_prior_arb_decisions(business_domain),
            "reference_architectures": self._get_reference_architectures(business_domain),
            "existing_patterns": self._get_solution_patterns(business_domain),
        }
        return ctx

    def _get_principles(self, domain):
        """Retrieve architecture principles from ArchiMate Principle elements."""
        try:
            q = ("SELECT name, description FROM archimate_elements "
                 "WHERE type = 'Principle' AND (description IS NOT NULL) "
                 "ORDER BY name LIMIT 20")
            rows = db.session.execute(db.text(q)).fetchall()
            return [{"name": r[0], "description": r[1]} for r in rows]
        except Exception as e:
            logger.warning("RAG principles query failed: %s", e)
            return []

    def _get_prior_arb_decisions(self, domain):
        """Retrieve prior ARB decisions for similar domains."""
        try:
            q = (
                "SELECT s.name, s.governance_status, s.business_domain, s.description "
                "FROM solutions s WHERE s.governance_status IN ('approved', 'arb_approved') "
            )
            params = {}
            if domain:
                q += "AND s.business_domain = :domain "
                params["domain"] = domain
            q += "ORDER BY s.arb_approval_date DESC NULLS LAST LIMIT 10"
            rows = db.session.execute(db.text(q), params).fetchall()
            return [{"name": r[0], "status": r[1], "domain": r[2], "description": r[3] or ""} for r in rows]
        except Exception as e:
            logger.warning("RAG prior decisions query failed: %s", e)
            return []

    def _get_reference_architectures(self, domain):
        """Retrieve reference architecture patterns."""
        try:
            q = ("SELECT name, description, pattern_type FROM solution_patterns "
                 "WHERE approval_status = 'approved' ")
            q += "ORDER BY name LIMIT 10"
            rows = db.session.execute(db.text(q)).fetchall()
            return [{"name": r[0], "description": r[1], "type": r[2]} for r in rows]
        except Exception as e:
            logger.warning("RAG reference architectures query failed: %s", e)
            return []

    def _get_solution_patterns(self, domain):
        """Retrieve existing solution patterns for the domain."""
        try:
            q = "SELECT name, description, solution_type FROM solutions WHERE status = 'deployed'"
            params = {}
            if domain:
                q += " AND business_domain = :domain"
                params["domain"] = domain
            q += " ORDER BY created_at DESC LIMIT 5"
            rows = db.session.execute(db.text(q), params).fetchall()
            return [{"name": r[0], "description": r[1] or "", "type": r[2] or ""} for r in rows]
        except Exception as e:
            logger.warning("RAG solution patterns query failed: %s", e)
            return []

    def format_context(self, ctx, max_tokens=2000):
        """Format context into a string suitable for LLM prompt injection."""
        parts = []

        if ctx.get("principles"):
            parts.append("## Organization Architecture Principles")
            for p in ctx["principles"][:10]:
                parts.append(f"- **{p['name']}**: {p['description'][:200]}")

        if ctx.get("prior_decisions"):
            parts.append("\n## Prior ARB Decisions (same domain)")
            for d in ctx["prior_decisions"][:5]:
                parts.append(f"- {d['name']} ({d['status']}): {d['description'][:150]}")

        if ctx.get("reference_architectures"):
            parts.append("\n## Reference Architectures")
            for r in ctx["reference_architectures"][:5]:
                parts.append(f"- {r['name']}: {r['description'][:150]}")

        text = "\n".join(parts)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[...truncated]"
        return text
