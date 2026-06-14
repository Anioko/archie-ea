"""
GenomePatchService — Natural Language → JSON Patch on Architectural Genome

Takes a genome JSON dict and a plain-English instruction, uses an LLM to
produce a JSON Patch (RFC 6902), identifies affected templates, and can
apply the patch to produce an updated genome.
"""
import copy
import json
import logging
import re
from typing import Optional

from app.modules.codegen.services.genome_field_template_map import get_affected_templates

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert at modifying application architecture specifications (Architectural Genomes).
Convert a natural language instruction into a minimal JSON Patch (RFC 6902).

Rules:
1. Return ONLY a JSON array of patch operations. No prose, no markdown.
2. Each operation: {"op": "add"|"replace"|"remove", "path": "/json/pointer", "value": ...}
3. "remove" ops have NO "value" field.
4. Use the SMALLEST possible patch — only change what the instruction asks for.
5. JSON Pointer paths use "/" separator: "/modules/referrals/views/list/export_formats"
6. If ambiguous or inapplicable, return: [{"op": "comment", "error": "reason"}]
7. Never change solution_name, solution_id, or problem fields.
"""


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2048) -> Optional[str]:
    """Call LLM using the same pattern as genome_extraction_service."""
    try:
        from app.modules.ai_chat.services.llm_service import LLMService
        provider, model = LLMService._get_configured_provider()
        tok = LLMService.get_max_tokens_limit(provider, model, requested_max=max_tokens)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        raw_text, _ = LLMService._call_llm(prompt=full_prompt, model=model, provider=provider, max_tokens=tok)
        return (raw_text or "").strip()
    except Exception as exc:
        logger.warning("GenomePatchService LLM call failed: %s", exc)
        return None


class GenomePatchService:

    def _call_llm(self, prompt: str) -> str:
        result = _call_llm(system_prompt=_SYSTEM_PROMPT, user_prompt=prompt)
        return result or ""

    def _extract_json(self, text: str) -> Optional[list]:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None

    def patch(self, genome: dict, nl_instruction: str) -> dict:
        """Generate a JSON Patch from a natural language instruction."""
        try:
            genome_summary = json.dumps(genome, indent=2)[:4000]
            prompt = (
                f"Genome (current state):\n{genome_summary}\n\n"
                f"Instruction: {nl_instruction}\n\nReturn only the JSON Patch array."
            )
            raw = self._call_llm(prompt)
            patch_ops = self._extract_json(raw)

            if patch_ops is None:
                return {"success": False, "patch_ops": [], "affected_templates": [],
                        "confidence": 0.0, "error": "LLM returned unparseable response"}

            if len(patch_ops) == 1 and patch_ops[0].get("op") == "comment":
                return {"success": False, "patch_ops": [], "affected_templates": [],
                        "confidence": 0.0, "error": patch_ops[0].get("error", "Cannot apply instruction")}

            valid_ops = [
                op for op in patch_ops
                if isinstance(op, dict)
                and op.get("op") in ("add", "replace", "remove", "move", "copy", "test")
                and "path" in op
                and (op["op"] in ("remove", "move", "copy", "test") or "value" in op)
            ]

            if not valid_ops:
                return {"success": False, "patch_ops": [], "affected_templates": [],
                        "confidence": 0.0, "error": "No valid patch operations in LLM response"}

            paths = [op["path"] for op in valid_ops]
            return {
                "success": True,
                "patch_ops": valid_ops,
                "affected_templates": get_affected_templates(paths),
                "confidence": 0.85,
                "error": None,
            }
        except Exception as exc:
            logger.exception("GenomePatchService.patch failed: %s", exc)
            return {"success": False, "patch_ops": [], "affected_templates": [],
                    "confidence": 0.0, "error": str(exc)}

    def apply_patch(self, genome: dict, patch_ops: list) -> dict:
        """Apply RFC 6902 patch operations to a genome dict (returns new dict)."""
        result = copy.deepcopy(genome)
        for op in patch_ops:
            op_type = op.get("op")
            path = op.get("path", "")
            parts = [p for p in path.lstrip("/").split("/") if p]
            if not parts:
                continue
            target = result
            try:
                for part in parts[:-1]:
                    target = target[part] if isinstance(target, dict) else target[int(part)]
                key = parts[-1]
                if op_type in ("add", "replace"):
                    if isinstance(target, list):
                        if key == "-":
                            target.append(op["value"])
                        else:
                            target[int(key)] = op["value"]
                    else:
                        target[key] = op["value"]
                elif op_type == "remove":
                    if isinstance(target, list):
                        del target[int(key)]
                    else:
                        target.pop(key, None)
            except (KeyError, IndexError, TypeError) as e:
                logger.warning("Patch op %s on %s failed: %s", op_type, path, e)
        return result
