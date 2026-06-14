"""Presentation helpers for TOGAF deliverable traceability."""

from typing import Any, Mapping


class TOGAFDeliverableTraceabilityService:
    """Build navigable traceability data from section-level source references."""

    def build_traceability_view(self, content: Mapping[str, Any]) -> dict[str, Any]:
        source_refs = content.get("source_refs") or []
        ref_map = {ref.get("id"): self._decorate_ref(ref) for ref in source_refs if ref.get("id")}
        section_views = []
        for section in content.get("sections") or []:
            refs = [ref_map[ref_id] for ref_id in section.get("source_ref_ids") or [] if ref_id in ref_map]
            section_views.append({
                "key": section.get("key"),
                "title": section.get("title"),
                "refs": refs,
                "navigable_ref_count": sum(1 for ref in refs if ref.get("url")),
            })
        return {
            "sections": section_views,
            "total_refs": len(source_refs),
            "navigable_refs": sum(1 for ref in ref_map.values() if ref.get("url")),
        }

    def _decorate_ref(self, ref: Mapping[str, Any]) -> dict[str, Any]:
        metadata = dict(ref.get("metadata") or {})
        source_type = ref.get("source_type", "")
        return {
            "id": ref.get("id"),
            "label": ref.get("label") or source_type.replace("_", " ").title(),
            "source_type": source_type,
            "source_type_label": source_type.replace("_", " ").title(),
            "metadata": metadata,
            "url": self._build_url(source_type, ref.get("source_id"), metadata),
        }

    @staticmethod
    def _build_url(source_type: str, source_id: Any, metadata: Mapping[str, Any]) -> str | None:
        if source_type in {"workflow_definition", "workflow_steps"}:
            workflow_code = metadata.get("workflow_code")
            return f"/ea-workflows/definitions/{workflow_code}" if workflow_code else None
        if source_type in {"application_component", "application_ownership", "application_governance"} and source_id:
            return f"/applications/{source_id}"
        if source_type == "solution_summary" and source_id:
            return f"/solutions/{source_id}"
        if source_type == "roadmap_summary" and source_id:
            return f"/applications/{source_id}/roadmap"
        return None


togaf_deliverable_traceability_service = TOGAFDeliverableTraceabilityService()
