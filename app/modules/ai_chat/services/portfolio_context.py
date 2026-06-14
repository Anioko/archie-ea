"""
PortfolioContextBuilder — compiles a compact portfolio snapshot for the agent system prompt.

Hard token budget: 4000 tokens (~16 000 chars). Never exceeded regardless of portfolio size.
All DB queries are single SELECT/COUNT — no N+1 queries. Target: < 500ms total.
"""
import logging

logger = logging.getLogger(__name__)

TOKEN_BUDGET_CHARS = 14000  # Conservative: 4000 tokens × ~3.5 chars/token


class PortfolioContextBuilder:
    def build(self, solution_id: int, user_id: int, question: str = "") -> str:
        """Return a compact portfolio context block. Returns '' on any error."""
        try:
            active = self._get_active_solution(solution_id)
            if not active:
                return ""

            similar = self._get_similar_solutions(active)
            patterns = self._detect_patterns(solution_id, similar)
            health = self._portfolio_health_snapshot()
            memory = self._recent_interactions(user_id)
            arb = self._recent_arb_decisions()
            learned = self._learned_rules_summary()
            web_context = self._web_search_context(question)

            block = self._format(active, similar, patterns, health, memory, arb, learned, web_context)
            return self._trim_to_budget(block)
        except Exception as exc:
            logger.debug("PortfolioContextBuilder.build failed: %s", exc)
            return ""

    # ------------------------------------------------------------------ #
    # Data methods                                                         #
    # ------------------------------------------------------------------ #

    def _get_active_solution(self, solution_id: int) -> dict:
        from app.models.solution_models import Solution
        sol = Solution.query.get(solution_id)
        if not sol:
            return {}
        return {
            "id": sol.id,
            "name": sol.name,
            "business_domain": getattr(sol, "business_domain", "") or "",
            "adm_phase": getattr(sol, "adm_phase", "A") or "A",
            "status": getattr(sol, "status", "") or "",
        }

    def _get_similar_solutions(self, active: dict, limit: int = 5) -> list:
        """Solutions in same business_domain, excluding the active one."""
        if not active.get("business_domain"):
            return []
        from app.models.solution_models import Solution
        sols = (
            Solution.query
            .filter(
                Solution.business_domain == active["business_domain"],
                Solution.id != active["id"],
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "id": s.id,
                "name": s.name,
                "adm_phase": getattr(s, "adm_phase", "A") or "A",
                "status": getattr(s, "status", "") or "",
                "overall_pct": self._quick_completeness(s.id),
            }
            for s in sols
        ]

    def _quick_completeness(self, solution_id: int) -> int:
        """Fast completeness estimate: count of linked ArchiMate elements / 20."""
        try:
            from app.models.solution_models import SolutionArchiMateElement
            count = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).count()
            return min(100, count * 5)
        except Exception:
            return 0

    def _detect_patterns(self, solution_id: int, similar: list) -> str:
        """Detect shared applications between this solution and similar ones."""
        if not similar:
            return ""
        try:
            from app.models.solution_models import SolutionApplication
            my_apps = {
                row.application_id
                for row in SolutionApplication.query.filter_by(solution_id=solution_id).all()
            }
            if not my_apps:
                return ""
            overlap_names = []
            for sol in similar:
                their_apps = {
                    row.application_id
                    for row in SolutionApplication.query.filter_by(solution_id=sol["id"]).all()
                }
                shared = my_apps & their_apps
                if len(shared) >= 2:
                    overlap_names.append(f"Sol-{sol['id']} \"{sol['name']}\" ({len(shared)} shared apps)")
            if overlap_names:
                return "Integration pattern overlap: " + ", ".join(overlap_names)
            return ""
        except Exception:
            return ""

    def _portfolio_health_snapshot(self) -> dict:
        """Count solutions by status. Single query."""
        try:
            from app.models.solution_models import Solution
            from sqlalchemy import func
            from app import db
            rows = (
                db.session.query(Solution.status, func.count(Solution.id))
                .group_by(Solution.status)
                .all()
            )
            counts = {row[0] or "unknown": row[1] for row in rows}
            total = sum(counts.values())
            return {"total": total, "by_status": counts}
        except Exception:
            return {"total": 0, "by_status": {}}

    def _recent_interactions(self, user_id: int, limit: int = 5) -> list:
        """Last N AI interactions for this user from AIChatAuditLog."""
        try:
            from app.models.ai_chat_audit_log import AIChatAuditLog
            rows = AIChatAuditLog.get_recent_for_user(user_id, limit=limit)
            return [
                {
                    "message": (r.message or "")[:80],
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                }
                for r in rows
            ]
        except Exception:
            return []

    def _recent_arb_decisions(self, limit: int = 5) -> list:
        """Recent ARB decisions — governance mandates the agent should know about.

        Includes structured rationale fields (action_description, new_value) so
        the AI can explain WHY a decision was made, not just that it happened.
        """
        try:
            from app.models.architecture_review_board import ARBAuditLog
            rows = ARBAuditLog.query.order_by(
                ARBAuditLog.timestamp.desc()
            ).limit(limit).all()
            results = []
            for r in rows:
                description = (
                    getattr(r, "action_description", "") or
                    getattr(r, "details", "") or ""
                )
                new_val = getattr(r, "new_value", None) or {}
                source = new_val.get("source", "") if isinstance(new_val, dict) else ""
                results.append({
                    "action": getattr(r, "action", "") or "",
                    "entity_type": getattr(r, "entity_type", "") or "",
                    "description": description[:200],
                    "source": source,
                    "timestamp": r.timestamp.strftime("%Y-%m-%d") if r.timestamp else "",
                })
            return results
        except Exception:
            return []

    def _learned_rules_summary(self, limit: int = 10) -> list:
        """Top learned corrections from ExtractionFeedback — injected into prompt
        so the AI avoids repeating known extraction mistakes."""
        try:
            from app.modules.architecture.services.feedback_learning_service import (
                ExtractionFeedback,
            )
            rows = (
                ExtractionFeedback.query
                .filter(ExtractionFeedback.learned_rule.isnot(None))
                .order_by(ExtractionFeedback.applied_count.desc())
                .limit(limit)
                .all()
            )
            rules = []
            for r in rows:
                rule = r.learned_rule or {}
                if not isinstance(rule, dict):
                    continue
                nm = rule.get("name_mapping")
                tc = rule.get("type_correction")
                if nm:
                    rules.append(
                        f"Name: '{nm.get('from')}' should be '{nm.get('to')}'"
                        f" (context: {nm.get('context', '')})"
                    )
                elif tc:
                    rules.append(
                        f"Type: '{tc.get('from')}' → '{tc.get('to')}'"
                        f" when name contains '{tc.get('name_pattern', '')}'"
                    )
            return rules
        except Exception:
            return []

    def _web_search_context(self, question: str) -> str:
        """Inject web search results for benchmark/industry questions."""
        try:
            from app.services.web_search_service import should_search, search_context, format_search_context
            if not should_search(question):
                return ""
            results = search_context(question)
            return format_search_context(results)
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    # Formatting                                                           #
    # ------------------------------------------------------------------ #

    def _format(self, active: dict, similar: list, patterns: str, health: dict,
                memory: list, arb: list, learned: list = None, web_context: str = "") -> str:
        lines = ["PORTFOLIO CONTEXT:"]

        lines.append(
            f"Active solution: \"{active['name']}\" | "
            f"Domain: {active['business_domain'] or 'unset'} | "
            f"Phase: {active['adm_phase']} | Status: {active['status'] or 'unset'}"
        )

        if similar:
            lines.append("")
            lines.append("Similar solutions (same domain):")
            for s in similar:
                lines.append(
                    f"  - Sol-{s['id']} \"{s['name']}\" "
                    f"[Phase {s['adm_phase']}, ~{s['overall_pct']}% complete, {s['status']}]"
                )

        if patterns:
            lines.append("")
            lines.append(patterns)

        total = health.get("total", 0)
        by_status = health.get("by_status", {})
        if total:
            status_str = " | ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))
            lines.append("")
            lines.append(f"Portfolio health: {total} solutions — {status_str}")

        if arb:
            lines.append("")
            lines.append("Recent governance decisions:")
            for r in arb:
                src = f" [via {r['source']}]" if r.get("source") else ""
                lines.append(
                    f"  - {r['action']} ({r['timestamp']}){src}: {r['description']}"
                )

        if learned:
            lines.append("")
            lines.append("Known extraction corrections (apply these to avoid past mistakes):")
            for rule in learned[:5]:
                lines.append(f"  - {rule}")

        if memory:
            lines.append("")
            lines.append("Recent interactions (this user):")
            for m in memory:
                lines.append(f"  - {m['created_at']}: {m['message']}")

        if web_context:
            lines.append("")
            lines.append(web_context)

        return "\n".join(lines)

    def _trim_to_budget(self, text: str) -> str:
        if len(text) <= TOKEN_BUDGET_CHARS:
            return text
        return text[:TOKEN_BUDGET_CHARS] + "\n[Portfolio context truncated to stay within token budget]"
