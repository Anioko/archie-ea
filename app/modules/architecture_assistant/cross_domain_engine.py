"""Cross-Domain Chain Engine — evaluates data-driven dependency rules."""

import logging

logger = logging.getLogger(__name__)


class CrossDomainEngine:
    """Evaluates cross-domain dependency rules for a given element."""

    def evaluate(self, domain, archimate_type, element_name, industry_overlay=None):
        """Find all cross-domain dependencies triggered by an element.

        Returns list of dependency dicts.
        """
        from app.models.acm_cross_domain_rule import AcmCrossDomainRule

        # Universal rules only (E5: exclude overlay-specific rules)
        rules = AcmCrossDomainRule.query.filter_by(
            trigger_domain=domain,
            trigger_archimate_type=archimate_type,
            is_active=True,
        ).filter(
            AcmCrossDomainRule.industry_overlay.is_(None)
        ).all()

        # Add overlay-specific rules if overlay is set
        if industry_overlay:
            overlay_rules = AcmCrossDomainRule.query.filter_by(
                trigger_domain=domain,
                trigger_archimate_type=archimate_type,
                is_active=True,
                industry_overlay=industry_overlay,
            ).all()
            rules.extend(overlay_rules)

        dependencies = []
        seen_names = set()

        for rule in rules:
            if not rule.matches(element_name):
                continue
            rendered_name = rule.render_name(element_name)
            dedup_key = (rule.target_domain, rendered_name)
            if dedup_key in seen_names:
                continue
            seen_names.add(dedup_key)

            dependencies.append({
                "rule_id": rule.id,
                "rule_type": rule.rule_type,
                "target_domain": rule.target_domain,
                "target_archimate_type": rule.target_archimate_type,
                "name": rendered_name,
                "description": rule.description,
                "severity": rule.severity,
                "target_relationship_type": rule.target_relationship_type,
                "target_relationship_target": rule.target_relationship_target,
            })

        return dependencies

    def evaluate_all_for_solution(self, solution_id, industry_overlay=None):
        """Evaluate dependencies for all elements in a solution. Returns dict by target domain."""
        from app.models.solution_blueprint_proposal import SolutionBlueprintProposal
        proposals = SolutionBlueprintProposal.query.filter_by(
            solution_id=solution_id,
        ).filter(
            SolutionBlueprintProposal.status.in_(["proposed", "accepted"]),
            SolutionBlueprintProposal.acm_domain.isnot(None),
        ).all()

        all_deps = {}
        for p in proposals:
            deps = self.evaluate(
                domain=p.acm_domain, archimate_type=p.archimate_type,
                element_name=p.name, industry_overlay=industry_overlay,
            )
            for dep in deps:
                target = dep["target_domain"]
                all_deps.setdefault(target, []).append(dep)
        return all_deps
