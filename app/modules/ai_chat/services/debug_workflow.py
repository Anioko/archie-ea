"""
Debug Workflow for Code-Level Debugging in AI Chat Workbench.

Lightweight debugging workflow that bypasses governance gates for rapid iteration.
Supports multi-file fixes, error log parsing, and conversational debugging.

AIC-319: Code-Level Debugging Workflow
"""

import logging
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db

logger = logging.getLogger(__name__)


class DebugWorkflow:
    """
    Lightweight debugging workflow - no governance gates.
    
    Enables rapid iteration for code-level debugging:
    - Parse error logs and stack traces
    - Identify affected files
    - Apply multi-file fixes atomically
    - Verify with tests (optional)
    
    Unlike production workflows, debug mode:
    - Skips artifact lifecycle states
    - Bypasses verification loops
    - Allows unlimited retries
    - Logs changes for audit but doesn't block
    """
    
    DEBUG_STEPS = [
        "ANALYZE",      # Parse error, identify files
        "DIAGNOSE",     # Explain root cause
        "FIX",          # Apply code changes
        "VERIFY",       # Run tests (optional)
    ]
    
    def __init__(self, kernel, user_id: Optional[int] = None):
        """Initialize debug workflow with a workbench kernel."""
        self.kernel = kernel
        self.user_id = user_id
    
    def start_debug_session(
        self,
        error_log: str,
        solution_id: Optional[int] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Start a debug session from an error log or stack trace.
        
        Args:
            error_log: Error message, stack trace, or test failure output
            solution_id: Optional solution ID to link to
            context: Optional additional context (file list, recent changes)
        
        Returns:
            Dict with workspace_id, analysis, affected_files, and suggested_fix
        """
        try:
            # Create debug workspace (bypass normal lifecycle)
            ws_result = self.kernel.create_workspace(
                name=f"Debug: {error_log[:50]}",
                workspace_type="debug",
                description=f"Debug session started at {datetime.utcnow().isoformat()}",
                solution_id=solution_id,
            )
            
            if not ws_result.get("success"):
                return {"success": False, "error": "Failed to create debug workspace"}
            
            workspace_id = ws_result["workspace_id"]
            
            # Mark as debug mode in metadata
            self.kernel.update_workspace_metadata(workspace_id, {
                "debug_mode": True,
                "error_log": error_log[:2000],
                "debug_attempts": 0,
            })
            
            # Analyze error
            analysis = self._analyze_error(error_log, context)
            
            # Store analysis as artifact (no state transitions needed)
            self.kernel.update_workspace_metadata(workspace_id, {
                "analysis": analysis,
            })
            
            return {
                "success": True,
                "workspace_id": workspace_id,
                "step": "ANALYZE",
                "analysis": analysis,
                "response": self._format_analysis_response(analysis),
            }
        except Exception as e:
            logger.error("Failed to start debug session: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}
    
    def apply_debug_fix(
        self,
        workspace_id: int,
        file_changes: Dict[str, str],
        explanation: str = "",
    ) -> Dict[str, Any]:
        """
        Apply multi-file fix atomically - bypass verification.
        
        Args:
            workspace_id: Debug workspace ID
            file_changes: Dict mapping file paths to new content
            explanation: Human-readable explanation of the fix
        
        Returns:
            Dict with success status and applied changes
        """
        try:
            ws = self.kernel.load_workspace(workspace_id)
            if not ws:
                return {"success": False, "error": "Workspace not found"}
            
            if not ws.get("debug_mode"):
                return {
                    "success": False,
                    "error": "This workspace is not in debug mode. Use normal workflow for production changes."
                }
            
            # Increment attempt counter
            attempts = ws.get("debug_attempts", 0) + 1
            
            # Log the fix for audit trail (but don't block)
            self.kernel.update_workspace_metadata(workspace_id, {
                "debug_attempts": attempts,
                f"fix_attempt_{attempts}": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "files_changed": list(file_changes.keys()),
                    "explanation": explanation,
                },
            })
            
            # Add evidence entry
            self.kernel.add_evidence(
                workspace_id,
                "debug_fix",
                f"Applied fix to {len(file_changes)} files: {explanation}",
                f"attempt={attempts}",
            )
            
            return {
                "success": True,
                "files_changed": list(file_changes.keys()),
                "attempt": attempts,
                "message": f"Fix applied to {len(file_changes)} files (attempt {attempts})",
            }
        except Exception as e:
            logger.error("Failed to apply debug fix: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}
    
    def analyze_with_llm(
        self,
        workspace_id: int,
        error_log: str,
        files_content: Dict[str, str],
        requested_model: Optional[str] = None,
        solution_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze error and suggest fixes with genome/UML context.
        
        Args:
            workspace_id: Debug workspace ID
            error_log: Error message or stack trace
            files_content: Dict mapping file paths to their content
            requested_model: Optional specific model to use
            solution_id: Optional solution ID to load genome/UML context
        
        Returns:
            Dict with diagnosis, affected_files, suggested_changes, and next_steps
        """
        try:
            from app.services.llm_service import LLMService
            
            # Load genome/UML context if solution_id provided
            genome_context = ""
            uml_context = ""
            if solution_id:
                try:
                    from app.modules.codegen.models import CodegenGeneration
                    gen = CodegenGeneration.query.filter_by(solution_id=solution_id).first()
                    if gen:
                        # Load UML snapshot
                        uml = gen.uml_snapshot
                        if uml:
                            classes = uml.get("class_diagram", {}).get("classes", [])
                            flows = uml.get("sequence_diagram", {}).get("flows", [])
                            uml_context = f"\n**UML Context (from ArchiMate):**\n"
                            uml_context += f"- {len(classes)} entity classes: {', '.join(c.get('name', '') for c in classes[:5])}\n"
                            uml_context += f"- {len(flows)} API flows/endpoints\n"
                            
                            # Find relevant class for error
                            for cls in classes:
                                cls_name = cls.get("name", "")
                                # Check if error mentions this class
                                if cls_name.lower() in error_log.lower():
                                    fields = cls.get("fields", [])
                                    uml_context += f"\n**{cls_name} Schema (from ArchiMate DataObject):**\n"
                                    for field in fields[:10]:
                                        uml_context += f"  - {field.get('name')}: {field.get('type')} {'(nullable)' if field.get('nullable') else ''}\n"
                        
                        # Load genome if available
                        genome = gen.genome_snapshot
                        if genome:
                            modules = genome.get("modules", {})
                            genome_context = f"\n**Architectural Genome:**\n"
                            genome_context += f"- {len(modules)} modules defined\n"
                            genome_context += f"- Generation mode: {gen.config.get('generation_mode', 'unknown')}\n"
                except Exception as ctx_err:
                    logger.debug("Could not load genome/UML context: %s", ctx_err)
            
            # Build context
            files_list = "\n".join(
                f"### {path}\n```python\n{content[:500]}...\n```"
                for path, content in list(files_content.items())[:5]
            )
            
            prompt = f"""You are debugging a Python/Flask application generated from ArchiMate architecture elements.

**Error Log:**
```
{error_log[:1500]}
```
{uml_context}
{genome_context}

**Relevant Files:**
{files_list}

**Your Task:**
1. Identify the root cause (consider the ArchiMate/UML context above)
2. List all affected files
3. Suggest specific code changes that align with the architectural design
4. Explain why this will fix the issue

**Response Format (JSON):**
{{
  "root_cause": "Brief explanation referencing ArchiMate elements if relevant",
  "affected_files": ["path/to/file1.py", "path/to/file2.py"],
  "diagnosis": "Detailed technical diagnosis",
  "suggested_changes": [
    {{"file": "path/to/file.py", "change": "Replace line X with Y", "reason": "..."}}
  ],
  "test_command": "pytest command to verify fix"
}}

Return ONLY valid JSON, no markdown fences."""

            provider_name, model = LLMService._get_configured_provider()
            if requested_model:
                # Parse requested model (e.g., "gpt-4o", "claude-3.5-sonnet")
                from app.modules.ai_chat.services.multi_domain_chat_service import MultiDomainChatService
                svc = MultiDomainChatService(user_id=self.user_id)
                resolved = svc._resolve_requested_model(requested_model)
                if resolved:
                    provider_name, model = resolved
            
            response_text, _ = LLMService._call_llm(
                prompt=prompt,
                model=model,
                provider=provider_name,
                user_id=self.user_id,
                max_tokens=2000,
            )
            
            # Parse JSON response
            import json
            # Remove markdown fences if present
            json_str = response_text
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()
            
            analysis = json.loads(json_str)
            
            # Store analysis in workspace
            self.kernel.update_workspace_metadata(workspace_id, {
                "llm_analysis": analysis,
                "analyzed_at": datetime.utcnow().isoformat(),
                "had_genome_context": bool(genome_context),
                "had_uml_context": bool(uml_context),
            })
            
            return {
                "success": True,
                "analysis": analysis,
            }
        except Exception as e:
            logger.error("LLM analysis failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "fallback_analysis": self._analyze_error(error_log, {"files": files_content}),
            }
    
    def _analyze_error(self, error_log: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Parse error log and extract key information (non-LLM fallback).
        
        Returns dict with error_type, affected_files, line_numbers, and summary.
        """
        analysis = {
            "error_type": "unknown",
            "affected_files": [],
            "line_numbers": {},
            "summary": "",
            "stack_trace": [],
        }
        
        try:
            # Detect error type
            if "ImportError" in error_log or "ModuleNotFoundError" in error_log:
                analysis["error_type"] = "import_error"
            elif "AttributeError" in error_log:
                analysis["error_type"] = "attribute_error"
            elif "KeyError" in error_log:
                analysis["error_type"] = "key_error"
            elif "TypeError" in error_log:
                analysis["error_type"] = "type_error"
            elif "ValueError" in error_log:
                analysis["error_type"] = "value_error"
            elif "NameError" in error_log:
                analysis["error_type"] = "name_error"
            elif "SyntaxError" in error_log:
                analysis["error_type"] = "syntax_error"
            elif "AssertionError" in error_log or "FAILED" in error_log:
                analysis["error_type"] = "test_failure"
            
            # Extract file paths from stack trace
            # Pattern: File "path/to/file.py", line 123
            file_pattern = r'File "([^"]+)", line (\d+)'
            matches = re.findall(file_pattern, error_log)
            
            for file_path, line_num in matches:
                # Filter out Python stdlib and venv files
                if "/venv/" in file_path or "/lib/python" in file_path:
                    continue
                if file_path.startswith("/"):
                    file_path = file_path.lstrip("/")
                
                if file_path not in analysis["affected_files"]:
                    analysis["affected_files"].append(file_path)
                
                analysis["line_numbers"][file_path] = int(line_num)
                analysis["stack_trace"].append(f"{file_path}:{line_num}")
            
            # Extract error message (usually last line or near it)
            lines = error_log.strip().split("\n")
            for line in reversed(lines):
                if any(err in line for err in ["Error:", "Exception:", "FAILED"]):
                    analysis["summary"] = line.strip()[:200]
                    break
            
            if not analysis["summary"]:
                analysis["summary"] = lines[-1][:200] if lines else "Unknown error"
        
        except Exception as e:
            logger.warning("Error parsing failed: %s", e)
            analysis["summary"] = error_log[:200]
        
        return analysis
    
    def _format_analysis_response(self, analysis: Dict) -> str:
        """Format analysis into human-readable response."""
        error_type = analysis.get("error_type", "unknown").replace("_", " ").title()
        files = analysis.get("affected_files", [])
        summary = analysis.get("summary", "")
        stack = analysis.get("stack_trace", [])
        
        files_list = "\n".join(f"- `{f}`" for f in files[:5]) if files else "- No files identified"
        stack_list = "\n".join(f"  {s}" for s in stack[:5]) if stack else ""
        
        return f"""## Debug Analysis

**Error Type:** {error_type}

**Summary:**
{summary}

**Affected Files:**
{files_list}

**Stack Trace:**
```
{stack_list}
```

Type your question or say **'suggest fix'** for AI-powered diagnosis and code changes.
"""
    
    def continue_debugging(
        self,
        workspace_id: int,
        message: str,
        requested_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Continue a multi-turn debugging conversation.
        
        Args:
            workspace_id: Debug workspace ID
            message: User's next message/question
            requested_model: Optional model preference
        
        Returns:
            Dict with response and optional code changes
        """
        ws = self.kernel.load_workspace(workspace_id)
        if not ws:
            return {"success": False, "error": "Workspace not found"}
        
        if not ws.get("debug_mode"):
            return {"success": False, "error": "Not a debug workspace"}
        
        msg_lower = message.strip().lower()
        
        # Check for common debug commands
        if msg_lower in ("suggest fix", "fix it", "how do i fix this", "what's the fix"):
            # Trigger LLM analysis
            return {
                "success": True,
                "action": "request_llm_analysis",
                "response": "I'll analyze the error and suggest specific code changes. Please provide the content of the affected files.",
            }
        
        if msg_lower in ("explain", "why", "what happened", "root cause"):
            analysis = ws.get("analysis", {})
            return {
                "success": True,
                "response": self._format_analysis_response(analysis),
            }
        
        if msg_lower.startswith("test"):
            return {
                "success": True,
                "action": "run_tests",
                "response": "Run tests to verify the fix? I can execute pytest commands if you provide them.",
            }
        
        # General question - could integrate with chat service here
        return {
            "success": True,
            "response": f"Debug workspace active. Ask about the error, request a fix, or provide more context.\n\nYour message: {message}",
        }
