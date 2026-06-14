"""Readiness evaluation for TOGAF deliverable authoring."""

from typing import Any, Mapping


class TOGAFDeliverableReadinessService:
    """Evaluate whether a deliverable is ready for review and export."""

    def build_readiness_view(
        self,
        content: Mapping[str, Any],
        *,
        traceability_view: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        sections = content.get("sections") or []
        traceability_sections = {section.get("key"): section for section in (traceability_view or {}).get("sections") or []}
        section_views = []
        missing_sections = 0
        missing_evidence = 0
        governance_blockers = 0
        ready_sections = 0

        for section in sections:
            section_view = self._evaluate_section(section, traceability_sections.get(section.get("key")) or {})
            section_views.append(section_view)
            if section_view["is_ready"]:
                ready_sections += 1
            if section_view["missing_content"]:
                missing_sections += 1
            if section_view["missing_evidence"]:
                missing_evidence += 1
            if section_view["governance_blockers"]:
                governance_blockers += 1

        gating_blockers = []
        if missing_sections:
            gating_blockers.append(f"{missing_sections} required section{'s' if missing_sections != 1 else ''} still need substantive content.")
        if missing_evidence:
            gating_blockers.append(f"{missing_evidence} required section{'s' if missing_evidence != 1 else ''} are missing canonical source evidence.")
        if governance_blockers:
            gating_blockers.append(f"{governance_blockers} required section{'s' if governance_blockers != 1 else ''} still have governance blockers.")

        can_finalize = not gating_blockers
        return {
            "sections": section_views,
            "total_sections": len(sections),
            "required_sections": sum(1 for section in sections if section.get("required")),
            "ready_sections": ready_sections,
            "remaining_sections": missing_sections,
            "missing_evidence_sections": missing_evidence,
            "governance_blocked_sections": governance_blockers,
            "can_submit_for_review": can_finalize,
            "can_export": can_finalize,
            "gating_blockers": gating_blockers,
        }

    def _evaluate_section(self, section: Mapping[str, Any], traceability_section: Mapping[str, Any]) -> dict[str, Any]:
        fields = section.get("fields") or {}
        has_field_content = any(self._has_content(value) for value in fields.values())
        has_narrative = self._has_content(section.get("manual_narrative")) or self._has_content(section.get("generated_narrative"))
        has_sources = bool(section.get("source_ref_ids")) or bool(traceability_section.get("refs"))
        missing_content = bool(section.get("required")) and not (has_field_content or has_narrative)
        missing_evidence = bool(section.get("required")) and not has_sources
        governance_blockers = list((section.get("readiness") or {}).get("blocking_issues") or [])
        return {
            "key": section.get("key"),
            "title": section.get("title"),
            "is_ready": not missing_content and not missing_evidence and not governance_blockers,
            "missing_content": missing_content,
            "missing_evidence": missing_evidence,
            "governance_blockers": governance_blockers,
        }

    @staticmethod
    def _has_content(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True


togaf_deliverable_readiness_service = TOGAFDeliverableReadinessService()
