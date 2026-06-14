"""
Tool executor: runs tool calls in-process against the SQLAlchemy service layer.

Design decisions:
  - No HTTP.  Direct DB calls only.  One transaction per tool.
  - EntityResolver handles all name→ID fuzzy matching before any write.
  - Ambiguity returns a clarification request; the LLM re-prompts the user.
  - Exceptions roll back and surface as {"success": False, "error": "..."}.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app import db

from .registry import TOOL_SCHEMA_BY_NAME
from .resolver import EntityResolver

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


class ToolExecutor:

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._resolver = EntityResolver()
        self._org_id = None  # cached lazily

    def _get_organization_id(self) -> int:
        """Return the organization_id for the current user (cached after first call)."""
        if self._org_id is not None:
            return self._org_id
        from sqlalchemy import text
        row = db.session.execute(
            text("SELECT organization_id FROM users WHERE id = :uid"),
            {"uid": self.user_id},
        ).fetchone()
        self._org_id = row[0] if row and row[0] else 1
        return self._org_id

    # ------------------------------------------------------------------ #
    # Public dispatch                                                      #
    # ------------------------------------------------------------------ #

    def execute(self, tool_call: ToolCall) -> dict:
        handler = getattr(self, f"_tool_{tool_call.name}", None)
        if not handler:
            return {"success": False, "error": f"Unknown tool: {tool_call.name}"}
        try:
            return handler(tool_call.arguments)
        except Exception as e:
            db.session.rollback()
            logger.exception("Tool %s failed", tool_call.name)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _get_or_create_problem_id(self, solution_id: int) -> int:
        """
        Get or create the SolutionProblemDefinition for a solution.
        SolutionDriver/Goal/Constraint all require a problem_id FK.
        Creates SolutionAnalysisSession + SolutionProblemDefinition if absent.
        """
        from datetime import datetime as _dt
        from app.models.solution_architect_models import (
            SolutionAnalysisSession,
            SolutionProblemDefinition,
            SolutionSessionStatus,
        )

        # Look up by the canonical agent-session name for this solution
        session_name = f"Agent session — solution {solution_id}"
        session = SolutionAnalysisSession.query.filter_by(name=session_name).first()
        if not session:
            session = SolutionAnalysisSession(
                name=session_name,
                status=SolutionSessionStatus.COMPLETED,
                created_by_id=self.user_id,
                created_at=_dt.utcnow(),
                updated_at=_dt.utcnow(),
                current_version=1,
                organization_id=self._get_organization_id(),
            )
            db.session.add(session)
            db.session.flush()

        prob = SolutionProblemDefinition.query.filter_by(session_id=session.id).first()
        if not prob:
            prob = SolutionProblemDefinition(
                session_id=session.id,
                problem_description="Agent-initiated session",
                organization_id=self._get_organization_id(),
            )
            db.session.add(prob)
            db.session.flush()

        return prob.id

    def _clarify(self, entity: str, result: dict) -> dict:
        return {
            "success": False,
            "needs_clarification": True,
            "entity": entity,
            "candidates": result.get("candidates", []),
            "error": (
                f"Ambiguous {entity} name — found {len(result['candidates'])} matches. "
                "Ask the user which one they meant."
                if result["candidates"]
                else f"No {entity} found with that name. Ask the user to check the name."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: create_solution                                                #
    # ------------------------------------------------------------------ #

    def _tool_create_solution(self, args: dict) -> dict:
        from app.models.solution_models import Solution

        sol = Solution(
            name=args["name"],
            description=args.get("description", ""),
            business_domain=args.get("business_domain"),
            solution_type=args.get("solution_type"),
            status="planned",
            governance_status="draft",
            organization_id=self._get_organization_id(),
        )
        db.session.add(sol)
        db.session.commit()
        logger.info("AgentRunner created solution id=%s name=%r user=%s", sol.id, sol.name, self.user_id)
        return {
            "success": True,
            "result": {"id": sol.id, "name": sol.name},
            "message": f"Created solution '{sol.name}' (ID {sol.id}).",
            "url": f"/solutions/{sol.id}",
        }

    # ------------------------------------------------------------------ #
    # Tool: link_capability_to_solution                                   #
    # ------------------------------------------------------------------ #

    def _tool_link_capability_to_solution(self, args: dict) -> dict:
        sol_r = self._resolver.resolve_solution(args["solution_name"])
        cap_r = self._resolver.resolve_capability(args["capability_name"])

        if not sol_r["resolved"]:
            return self._clarify("solution", sol_r)
        if not cap_r["resolved"]:
            return self._clarify("capability", cap_r)

        from app.models.solution_models import SolutionCapabilityMapping

        # Avoid duplicate
        existing = SolutionCapabilityMapping.query.filter_by(
            solution_id=sol_r["id"],
            capability_id=cap_r["id"],
        ).first()
        if existing:
            return {
                "success": True,
                "result": {"solution": sol_r["name"], "capability": cap_r["name"]},
                "message": (
                    f"Capability '{cap_r['name']}' is already linked to "
                    f"solution '{sol_r['name']}'."
                ),
            }

        mapping = SolutionCapabilityMapping(
            solution_id=sol_r["id"],
            capability_id=cap_r["id"],
            support_level=args.get("support_level", "primary"),
            notes=args.get("notes"),
            created_by_id=self.user_id,
        )
        db.session.add(mapping)
        db.session.commit()
        return {
            "success": True,
            "result": {"solution": sol_r["name"], "capability": cap_r["name"]},
            "message": (
                f"Linked capability '{cap_r['name']}' to solution '{sol_r['name']}' "
                f"({args.get('support_level', 'primary')} support)."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: link_application_to_capability                                #
    # ------------------------------------------------------------------ #

    def _tool_link_application_to_capability(self, args: dict) -> dict:
        app_r = self._resolver.resolve_application(args["application_name"])
        cap_r = self._resolver.resolve_capability(args["capability_name"])

        if not app_r["resolved"]:
            return self._clarify("application", app_r)
        if not cap_r["resolved"]:
            return self._clarify("capability", cap_r)

        from app.models.application_capability import ApplicationCapabilityMapping

        existing = ApplicationCapabilityMapping.query.filter_by(
            application_component_id=app_r["id"],
            business_capability_id=cap_r["id"],
        ).first()
        if existing:
            return {
                "success": True,
                "message": (
                    f"'{app_r['name']}' is already mapped to capability '{cap_r['name']}'."
                ),
            }

        mapping = ApplicationCapabilityMapping(
            application_component_id=app_r["id"],
            business_capability_id=cap_r["id"],
            support_level=args.get("coverage_level", "partial"),
        )
        db.session.add(mapping)
        db.session.commit()
        return {
            "success": True,
            "result": {"application": app_r["name"], "capability": cap_r["name"]},
            "message": (
                f"Mapped application '{app_r['name']}' to capability '{cap_r['name']}' "
                f"({args.get('coverage_level', 'partial')} coverage)."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: create_archimate_element                                       #
    # ------------------------------------------------------------------ #

    def _tool_create_archimate_element(self, args: dict) -> dict:
        try:
            from app.models.archimate_core import ArchiMateElement
        except ImportError:
            from app.models.models import ArchiMateElement

        elem = ArchiMateElement(
            name=args["name"],
            type=args["type"],
            layer=args["layer"],
            description=args.get("description", ""),
            organization_id=self._get_organization_id(),
        )
        db.session.add(elem)
        db.session.flush()  # get elem.id before linking

        # Optionally link to a solution
        solution_name = args.get("solution_name")
        if solution_name:
            sol_r = self._resolver.resolve_solution(solution_name)
            if sol_r["resolved"]:
                from app.models.solution_archimate_element import SolutionArchiMateElement
                link = SolutionArchiMateElement(
                    solution_id=sol_r["id"],
                    element_id=elem.id,
                    layer_type=args["layer"],
                    element_table='archimate_elements',
                )
                db.session.add(link)

        db.session.commit()
        return {
            "success": True,
            "result": {"id": elem.id, "name": elem.name, "type": elem.type, "layer": elem.layer},
            "message": (
                f"Created ArchiMate element '{elem.name}' ({elem.type}, {elem.layer} layer)"
                + (f" and linked to solution '{sol_r['name']}'." if solution_name and sol_r.get("resolved") else ".")
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: update_application_status (approve tier — pre-approved by     #
    # ApprovalGate before this is called)                                 #
    # ------------------------------------------------------------------ #

    def _tool_update_application_status(self, args: dict) -> dict:
        app_r = self._resolver.resolve_application(args["application_name"])
        if not app_r["resolved"]:
            return self._clarify("application", app_r)

        from app.models.application_component_fast import ApplicationComponent
        app_obj = ApplicationComponent.query.get(app_r["id"])
        if not app_obj:
            return {"success": False, "error": "Application not found"}

        old_status = app_obj.deployment_status
        app_obj.deployment_status = args["new_status"]
        db.session.commit()
        logger.info(
            "AgentRunner updated application id=%s status %r → %r (user=%s, rationale=%r)",
            app_r["id"], old_status, args["new_status"], self.user_id, args.get("rationale"),
        )
        return {
            "success": True,
            "result": {
                "application": app_r["name"],
                "old_status": old_status,
                "new_status": args["new_status"],
            },
            "message": (
                f"Updated '{app_r['name']}' status from '{old_status}' to '{args['new_status']}'."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: submit_for_arb_review (approve tier)                          #
    # ------------------------------------------------------------------ #

    def _tool_submit_for_arb_review(self, args: dict) -> dict:
        sol_r = self._resolver.resolve_solution(args["solution_name"])
        if not sol_r["resolved"]:
            return self._clarify("solution", sol_r)

        from app.models.solution_models import Solution
        from datetime import datetime

        sol = Solution.query.get(sol_r["id"])
        if not sol:
            return {"success": False, "error": "Solution not found"}

        # AIC-318: evidence gate — check workspace artifacts before ARB submission
        workspace_id = args.get("workspace_id")
        if workspace_id:
            try:
                from app.modules.ai_chat.services.workbench_kernel import WorkbenchKernel
                kernel = WorkbenchKernel()
                workflow_type = args.get("workflow_type", "greenfield")
                gate = kernel.check_evidence_gate(workspace_id, workflow_type)
                if not gate.get("pass"):
                    missing = gate.get("missing", [])
                    actions = gate.get("suggested_actions", [])
                    return {
                        "success": False,
                        "error": "Evidence gate: workspace artifacts insufficient for ARB submission.",
                        "missing_artifacts": missing,
                        "suggested_actions": actions,
                    }
            except Exception as _eg_err:
                logger.warning("AIC-318: evidence gate check failed (non-blocking): %s", _eg_err)

        sol.governance_status = "arb_review"
        sol.arb_submission_date = datetime.utcnow()
        db.session.commit()
        logger.info("AgentRunner submitted solution id=%s for ARB review (user=%s)", sol.id, self.user_id)
        return {
            "success": True,
            "result": {"solution": sol.name, "phase": args["phase"]},
            "message": (
                f"Submitted '{sol.name}' for ARB review at {args['phase']} phase. "
                "Governance status set to 'arb_review'."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: query_capability_gaps (read-only)                             #
    # ------------------------------------------------------------------ #

    def _tool_query_capability_gaps(self, args: dict) -> dict:
        from app.models.business_capabilities import BusinessCapability
        from app.models.solution_models import SolutionCapabilityMapping

        max_maturity = args.get("max_maturity", 2)
        domain_filter = args.get("business_domain")
        limit = min(args.get("limit", 20), 100)

        q = BusinessCapability.query.filter(
            BusinessCapability.current_maturity_level <= max_maturity
        )
        if domain_filter:
            q = q.filter(BusinessCapability.business_domain.ilike(f"%{domain_filter}%"))

        caps = q.order_by(BusinessCapability.current_maturity_level.asc()).limit(limit).all()

        rows = []
        for c in caps:
            app_count = ApplicationCapabilityMapping_count(c.id)
            rows.append({
                "id": c.id,
                "name": c.name,
                "current_maturity": c.current_maturity_level,
                "target_maturity": c.target_maturity_level,
                "business_domain": c.business_domain,
                "strategic_importance": c.strategic_importance,
                "supporting_apps": app_count,
            })

        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "message": (
                f"Found {len(rows)} capabilities with maturity ≤ {max_maturity}"
                + (f" in '{domain_filter}'" if domain_filter else "") + "."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: find_applications (read-only)                                 #
    # ------------------------------------------------------------------ #

    def _tool_find_applications(self, args: dict) -> dict:
        from app.models.application_component_fast import ApplicationComponent

        limit = min(args.get("limit", 15), 50)
        q = ApplicationComponent.query

        name_filter = args.get("name_contains")
        if name_filter:
            q = q.filter(ApplicationComponent.name.ilike(f"%{name_filter}%"))

        status_filter = args.get("status")
        if status_filter:
            q = q.filter(ApplicationComponent.deployment_status == status_filter)

        # Capability filter: join through ApplicationCapabilityMapping
        cap_name = args.get("capability_name")
        if cap_name:
            cap_r = self._resolver.resolve_capability(cap_name)
            if cap_r["resolved"]:
                from app.models.application_capability import ApplicationCapabilityMapping
                cap_ids = [
                    row.application_component_id
                    for row in ApplicationCapabilityMapping.query.filter_by(
                        business_capability_id=cap_r["id"]
                    ).all()
                ]
                q = q.filter(ApplicationComponent.id.in_(cap_ids))

        apps = q.limit(limit).all()
        rows = [
            {
                "id": a.id,
                "name": a.name,
                "status": a.deployment_status,
                "owner_team": getattr(a, "owner_team", None),
            }
            for a in apps
        ]
        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "message": f"Found {len(rows)} application(s).",
        }


    # ------------------------------------------------------------------ #
    # Tool: create_driver                                                 #
    # ------------------------------------------------------------------ #

    def _tool_create_driver(self, args: dict) -> dict:
        from app.models.solution_architect_models import SolutionDriver, DriverType
        problem_id = self._get_or_create_problem_id(args["solution_id"])
        driver = SolutionDriver(
            problem_id=problem_id,
            name=args["name"],
            description=args.get("description", ""),
            driver_type=DriverType(args["driver_type"]),
            ai_generated=True,
            organization_id=self._get_organization_id(),
        )
        db.session.add(driver)
        db.session.commit()
        logger.info("Agent created driver id=%s solution=%s", driver.id, args["solution_id"])
        return {
            "success": True,
            "result": {"id": driver.id, "name": driver.name, "entity_type": "driver", "solution_id": args["solution_id"]},
            "message": f"Added driver '{driver.name}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: create_goal                                                   #
    # ------------------------------------------------------------------ #

    def _tool_create_goal(self, args: dict) -> dict:
        from app.models.solution_architect_models import SolutionGoal
        problem_id = self._get_or_create_problem_id(args["solution_id"])
        goal = SolutionGoal(
            problem_id=problem_id,
            name=args["name"],
            description=args.get("description", ""),
            priority=args.get("priority", 3),
            ai_generated=True,
            organization_id=self._get_organization_id(),
        )
        db.session.add(goal)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": goal.id, "name": goal.name, "entity_type": "goal", "solution_id": args["solution_id"]},
            "message": f"Added goal '{goal.name}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: create_constraint                                             #
    # ------------------------------------------------------------------ #

    def _tool_create_constraint(self, args: dict) -> dict:
        from app.models.solution_architect_models import SolutionConstraint, ConstraintType
        problem_id = self._get_or_create_problem_id(args["solution_id"])
        constraint = SolutionConstraint(
            problem_id=problem_id,
            name=args["name"],
            description=args.get("description", ""),
            constraint_type=ConstraintType(args["constraint_type"]),
            severity=args.get("severity", 3),
            ai_generated=True,
            organization_id=self._get_organization_id(),
        )
        db.session.add(constraint)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": constraint.id, "name": constraint.name, "entity_type": "constraint", "solution_id": args["solution_id"]},
            "message": f"Added constraint '{constraint.name}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: create_requirement                                            #
    # ------------------------------------------------------------------ #

    def _tool_create_requirement(self, args: dict) -> dict:
        from app.models.solution_architect_models import SolutionRequirement, RequirementType
        req = SolutionRequirement(
            solution_id=args["solution_id"],
            name=args["name"],
            description=args.get("description", args["name"]),
            requirement_type=RequirementType(args["requirement_type"]) if args.get("requirement_type") else None,
            ai_generated=True,
            status="open",
            organization_id=self._get_organization_id(),
        )
        db.session.add(req)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": req.id, "name": req.name, "entity_type": "requirement", "solution_id": args["solution_id"]},
            "message": f"Added requirement '{req.name}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: create_risk                                                   #
    # ------------------------------------------------------------------ #

    def _tool_create_risk(self, args: dict) -> dict:
        from app.models.solution_lifecycle_models import SolutionRisk
        risk = SolutionRisk(
            solution_id=args["solution_id"],
            risk_description=args["risk_description"],
            impact=args["impact"],
            probability=args["probability"],
            mitigation=args.get("mitigation", ""),
            status="open",
            created_by_id=self.user_id,
        )
        db.session.add(risk)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": risk.id, "entity_type": "risk", "solution_id": args["solution_id"]},
            "message": f"Added risk '{args['risk_description'][:60]}' (impact={args['impact']}) to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: create_option                                                 #
    # ------------------------------------------------------------------ #

    def _tool_create_option(self, args: dict) -> dict:
        from app.models.solution_architect_models import (
            SolutionRecommendation, RecommendationOptionType, SolutionAnalysisSession,
        )
        session_name = f"Agent session — solution {args['solution_id']}"
        session = SolutionAnalysisSession.query.filter_by(name=session_name).first()
        if not session:
            self._get_or_create_problem_id(args["solution_id"])
            session = SolutionAnalysisSession.query.filter_by(name=session_name).first()
        rec = SolutionRecommendation(
            session_id=session.id,
            name=args["name"],
            option_type=RecommendationOptionType(args["option_type"]),
            is_recommended=False,
        )
        db.session.add(rec)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": rec.id, "name": rec.name, "entity_type": "option", "solution_id": args["solution_id"]},
            "message": f"Added option '{rec.name}' ({args['option_type']}) to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: mark_option_recommended                                       #
    # ------------------------------------------------------------------ #

    def _tool_mark_option_recommended(self, args: dict) -> dict:
        from app.models.solution_architect_models import SolutionRecommendation, SolutionAnalysisSession
        session = SolutionAnalysisSession.query.filter_by(solution_id=args["solution_id"]).first()
        if not session:
            return {"success": False, "error": "No options found for this solution — create options first."}
        options = SolutionRecommendation.query.filter_by(session_id=session.id).all()
        if not options:
            return {"success": False, "error": "No options found for this solution — create options first."}
        option_name = args["option_name"].lower()
        match = next(
            (o for o in options if option_name in o.name.lower() or o.name.lower() in option_name),
            None,
        )
        if not match:
            names = [o.name for o in options]
            return {"success": False, "error": f"Option '{args['option_name']}' not found. Available: {names}"}
        for o in options:
            o.is_recommended = False
        match.is_recommended = True
        db.session.commit()
        return {
            "success": True,
            "result": {"id": match.id, "name": match.name, "entity_type": "option"},
            "message": f"Marked '{match.name}' as the recommended option for solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: link_application_to_solution                                 #
    # ------------------------------------------------------------------ #

    def _tool_link_application_to_solution(self, args: dict) -> dict:
        app_r = self._resolver.resolve_application(args["application_name"])
        if not app_r["resolved"]:
            return self._clarify("application", app_r)
        from app.models.solution_models import Solution
        sol = Solution.query.get(args["solution_id"])
        if not sol:
            return {"success": False, "error": f"Solution {args['solution_id']} not found."}
        from app.models.application_component_fast import ApplicationComponent
        app_obj = ApplicationComponent.query.get(app_r["id"])
        if app_obj in sol.applications:
            return {
                "success": True,
                "result": {"application": app_r["name"], "entity_type": "application_link"},
                "message": f"'{app_r['name']}' is already linked to this solution.",
            }
        sol.applications.append(app_obj)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": app_r["id"], "name": app_r["name"], "entity_type": "application_link", "solution_id": args["solution_id"]},
            "message": f"Linked application '{app_r['name']}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: link_vendor_product                                           #
    # ------------------------------------------------------------------ #

    def _tool_link_vendor_product(self, args: dict) -> dict:
        vp_r = self._resolver.resolve_vendor_product(args["vendor_product_name"])
        if not vp_r["resolved"]:
            return self._clarify("vendor_product", vp_r)
        from app.models.solution_models import Solution
        from app.models.vendor.vendor_organization import VendorProduct
        sol = Solution.query.get(args["solution_id"])
        if not sol:
            return {"success": False, "error": f"Solution {args['solution_id']} not found."}
        vp = VendorProduct.query.get(vp_r["id"])
        if vp in sol.vendor_products:
            return {
                "success": True,
                "result": {"vendor_product": vp_r["name"], "entity_type": "vendor_product_link"},
                "message": f"'{vp_r['name']}' is already linked to this solution.",
            }
        sol.vendor_products.append(vp)
        db.session.commit()
        return {
            "success": True,
            "result": {"id": vp_r["id"], "name": vp_r["name"], "entity_type": "vendor_product_link", "solution_id": args["solution_id"]},
            "message": f"Linked vendor product '{vp_r['name']}' to solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: run_inference_engine                                          #
    # ------------------------------------------------------------------ #

    def _tool_run_inference_engine(self, args: dict) -> dict:
        from app.models.solution_archimate_element import SolutionArchiMateElement
        from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine

        dry_run = args.get("dry_run", False)
        links = SolutionArchiMateElement.query.filter_by(solution_id=args["solution_id"]).all()
        if not links:
            return {
                "success": True,
                "result": {"elements_processed": 0},
                "message": "No ArchiMate elements linked to this solution. Link elements first.",
            }

        total_created = 0
        total_relationships = 0
        errors = []
        engine = ArchiMateInferenceEngine(architecture_id=0)

        for link in links:
            try:
                result = engine.repair(link.element_id, dry_run=dry_run)
                total_created += result.get("created", 0)
                total_relationships += result.get("relationships_created", 0)
            except Exception as e:
                errors.append(str(e))

        action = "Would create" if dry_run else "Created"
        return {
            "success": True,
            "result": {
                "elements_processed": len(links),
                "elements_created": total_created,
                "relationships_created": total_relationships,
                "dry_run": dry_run,
                "errors": errors[:3],
            },
            "message": (
                f"Inference engine ran on {len(links)} elements. "
                f"{action} {total_created} new elements and {total_relationships} relationships."
                + (f" {len(errors)} errors." if errors else "")
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: generate_blueprint_narrative (approve tier)                  #
    # ------------------------------------------------------------------ #

    def _tool_generate_blueprint_narrative(self, args: dict) -> dict:
        solution_id = args["solution_id"]
        section_id = args["section_id"]
        try:
            from app.modules.solutions_strategic.v2.routes.solution_blueprint_routes import (
                generate_section_narrative,
            )
            generate_section_narrative(solution_id, section_id)
            return {
                "success": True,
                "result": {"solution_id": solution_id, "section_id": section_id},
                "message": f"Generated narrative for section '{section_id}' of solution {solution_id}.",
            }
        except Exception as e:
            logger.exception("generate_blueprint_narrative failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Tool: create_archimate_relationship                                 #
    # ------------------------------------------------------------------ #

    def _tool_create_archimate_relationship(self, args: dict) -> dict:
        src_r = self._resolver.resolve_archimate_element(args["source_element_name"])
        tgt_r = self._resolver.resolve_archimate_element(args["target_element_name"])
        if not src_r["resolved"]:
            return self._clarify("source ArchiMate element", src_r)
        if not tgt_r["resolved"]:
            return self._clarify("target ArchiMate element", tgt_r)
        from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
        engine = ArchiMateInferenceEngine(architecture_id=0)
        try:
            engine.graph.get_or_create_relationship(
                source_id=src_r["id"],
                target_id=tgt_r["id"],
                relationship_type=args["relationship_type"],
                provenance="agent",
                confidence=0.9,
            )
            db.session.commit()
            return {
                "success": True,
                "result": {"source": src_r["name"], "target": tgt_r["name"], "type": args["relationship_type"]},
                "message": (
                    f"Created {args['relationship_type']} relationship: "
                    f"'{src_r['name']}' → '{tgt_r['name']}'."
                ),
            }
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Tool: diagnose_chain (read-only)                                   #
    # ------------------------------------------------------------------ #

    def _tool_diagnose_chain(self, args: dict) -> dict:
        elem_r = self._resolver.resolve_archimate_element(args["element_name"])
        if not elem_r["resolved"]:
            return self._clarify("ArchiMate element", elem_r)
        from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
        engine = ArchiMateInferenceEngine(architecture_id=0)
        result = engine.diagnose(elem_r["id"])
        return {
            "success": True,
            "result": result,
            "message": (
                f"Chain diagnosis for '{elem_r['name']}': "
                f"{result.get('completeness_score', 0):.0%} complete. "
                f"Missing: {result.get('missing_elements', [])}."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: explain_element (read-only)                                  #
    # ------------------------------------------------------------------ #

    def _tool_explain_element(self, args: dict) -> dict:
        elem_r = self._resolver.resolve_archimate_element(args["element_name"])
        if not elem_r["resolved"]:
            return self._clarify("ArchiMate element", elem_r)
        from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
        engine = ArchiMateInferenceEngine(architecture_id=0)
        result = engine.explain(elem_r["id"])
        return {
            "success": True,
            "result": result,
            "message": f"Provenance chain for '{elem_r['name']}' traced.",
        }

    # ------------------------------------------------------------------ #
    # Tool: simulate_impact (read-only)                                  #
    # ------------------------------------------------------------------ #

    def _tool_simulate_impact(self, args: dict) -> dict:
        elem_r = self._resolver.resolve_archimate_element(args["element_name"])
        if not elem_r["resolved"]:
            return self._clarify("ArchiMate element", elem_r)
        from app.modules.architecture.services.inference_engine_service import ArchiMateInferenceEngine
        engine = ArchiMateInferenceEngine(architecture_id=0)
        result = engine.simulate_change_impact(elem_r["id"], scope="both")
        affected = result.get("affected_count", 0)
        return {
            "success": True,
            "result": result,
            "message": (
                f"Impact simulation for '{elem_r['name']}': "
                f"{affected} downstream elements affected across all layers."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: get_solution_summary (read-only)                             #
    # ------------------------------------------------------------------ #

    def _tool_get_solution_summary(self, args: dict) -> dict:
        from app.models.solution_models import Solution
        sol = Solution.query.get(args["solution_id"])
        if not sol:
            return {"success": False, "error": f"Solution {args['solution_id']} not found."}
        return {
            "success": True,
            "result": {
                "id": sol.id,
                "name": sol.name,
                "governance_status": sol.governance_status,
                "adm_phase": sol.adm_phase,
                "maturity_level": sol.maturity_current,
                "applications_count": _safe_count(sol.applications),
                "risks_count": _safe_count(sol.risks) if hasattr(sol, "risks") else None,
            },
            "message": (
                f"Solution '{sol.name}': phase={sol.adm_phase}, "
                f"CMM maturity={sol.maturity_current or 0}/5, governance={sol.governance_status}."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: get_completeness_score (read-only)                           #
    # ------------------------------------------------------------------ #

    def _tool_get_completeness_score(self, args: dict) -> dict:
        try:
            from app.modules.solutions_strategic.v2.services.blueprint_completeness_service import (
                BlueprintCompletenessService,
            )
            svc = BlueprintCompletenessService()
            scores = svc.score_all(args["solution_id"])
            # Summarise: overall = mean of section overalls
            section_scores = {k: v.get("overall", 0) for k, v in scores.items()}
            overall = round(sum(section_scores.values()) / max(len(section_scores), 1))
            return {
                "success": True,
                "result": {"overall_pct": overall, "sections": section_scores},
                "message": f"Overall completeness: {overall}%. Lowest sections: "
                           + ", ".join(
                               f"{k}={v}%" for k, v in sorted(section_scores.items(), key=lambda x: x[1])[:3]
                           ),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Tool: update_solution_fields                                        #
    # ------------------------------------------------------------------ #

    def _tool_update_solution_fields(self, args: dict) -> dict:
        from app.models.solution_models import Solution
        sol = Solution.query.get(args["solution_id"])
        if not sol:
            return {"success": False, "error": f"Solution {args['solution_id']} not found."}
        updatable = ["solution_owner", "business_sponsor", "technical_lead", "description"]
        updated = []
        for field in updatable:
            if field in args and args[field]:
                setattr(sol, field, args[field])
                updated.append(field)
        if not updated:
            return {"success": False, "error": "No fields provided to update."}
        db.session.commit()
        return {
            "success": True,
            "result": {"updated_fields": updated},
            "message": f"Updated {', '.join(updated)} on solution {args['solution_id']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: update_solution_phase                                         #
    # ------------------------------------------------------------------ #

    def _tool_update_solution_phase(self, args: dict) -> dict:
        from app.models.solution_models import Solution
        sol = Solution.query.get(args["solution_id"])
        if not sol:
            return {"success": False, "error": f"Solution {args['solution_id']} not found."}
        old_phase = sol.adm_phase
        sol.adm_phase = args["phase"]
        db.session.commit()
        return {
            "success": True,
            "result": {"old_phase": old_phase, "new_phase": args["phase"]},
            "message": f"Advanced solution {args['solution_id']} from phase {old_phase} to {args['phase']}.",
        }

    # ------------------------------------------------------------------ #
    # Tool: search_archimate_elements (read-only)                        #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Tool: search_capabilities_by_problem (read-only, semantic)          #
    # ------------------------------------------------------------------ #

    def _tool_search_capabilities_by_problem(self, args: dict) -> dict:
        """
        Semantic search over 516 business capabilities using SentenceTransformer
        cosine similarity. Falls back to keyword ILIKE if embeddings unavailable.
        Returns top-N capabilities ranked by relevance to the problem description.
        """
        from app.models.business_capabilities import BusinessCapability
        from app.models.application_capability import ApplicationCapabilityMapping

        query_text = args.get("problem_description", "")
        limit = min(args.get("limit", 10), 25)

        if not query_text.strip():
            return {"success": False, "error": "problem_description is required"}

        caps = BusinessCapability.query.filter(
            BusinessCapability.name.isnot(None)
        ).limit(600).all()

        if not caps:
            return {"success": False, "error": "No capabilities found in platform"}

        # --- Attempt semantic ranking via SentenceTransformer ---
        try:
            import numpy as np
            from app.services.vector_embedding_service import VectorEmbeddingService

            svc = VectorEmbeddingService()
            texts = [
                f"{c.name} {c.description or ''} {c.business_domain or ''}".strip()
                for c in caps
            ]
            query_vec = np.array(svc.embed_text(query_text))
            cap_vecs = np.array([svc.embed_text(t) for t in texts])

            # Cosine similarity (vectors already L2-normalised by all-MiniLM)
            scores = cap_vecs @ query_vec
            top_idx = np.argsort(scores)[::-1][:limit]

            rows = []
            for i in top_idx:
                c = caps[i]
                app_count = ApplicationCapabilityMapping.query.filter_by(
                    business_capability_id=c.id
                ).count()
                rows.append({
                    "id": c.id,
                    "name": c.name,
                    "business_domain": c.business_domain,
                    "current_maturity": c.current_maturity_level,
                    "target_maturity": c.target_maturity_level,
                    "gap": max(0, (c.target_maturity_level or 3) - (c.current_maturity_level or 1)),
                    "strategic_importance": c.strategic_importance,
                    "supporting_apps": app_count,
                    "relevance_score": round(float(scores[i]), 3),
                })
            method = "semantic"

        except Exception as embed_err:
            logger.warning("Semantic capability search fell back to keyword: %s", embed_err)
            # Keyword fallback — split query into tokens, ILIKE each
            tokens = [t for t in query_text.lower().split() if len(t) > 3][:6]
            q = BusinessCapability.query
            if tokens:
                from sqlalchemy import or_
                conditions = [
                    BusinessCapability.name.ilike(f"%{t}%") for t in tokens
                ] + [
                    BusinessCapability.description.ilike(f"%{t}%") for t in tokens
                ]
                q = q.filter(or_(*conditions))
            caps_kw = q.limit(limit).all()
            rows = []
            for c in caps_kw:
                app_count = ApplicationCapabilityMapping.query.filter_by(
                    business_capability_id=c.id
                ).count()
                rows.append({
                    "id": c.id,
                    "name": c.name,
                    "business_domain": c.business_domain,
                    "current_maturity": c.current_maturity_level,
                    "target_maturity": c.target_maturity_level,
                    "gap": max(0, (c.target_maturity_level or 3) - (c.current_maturity_level or 1)),
                    "strategic_importance": c.strategic_importance,
                    "supporting_apps": app_count,
                })
            method = "keyword"

        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "search_method": method,
            "message": (
                f"Found {len(rows)} capabilities relevant to your problem ({method} search). "
                "Use link_capability_to_solution to attach the relevant ones."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: find_applications_by_capability (read-only)                   #
    # ------------------------------------------------------------------ #

    def _tool_find_applications_by_capability(self, args: dict) -> dict:
        """
        Returns all applications mapped to a named capability.
        Grounds Phase 4 in the real 881-app catalog instead of invented names.
        """
        from app.models.application_capability import ApplicationCapabilityMapping
        from app.models.application_component_fast import ApplicationComponent

        cap_name = args.get("capability_name", "")
        if not cap_name.strip():
            return {"success": False, "error": "capability_name is required"}

        cap_r = self._resolver.resolve_capability(cap_name)
        if not cap_r.get("resolved"):
            return {
                "success": False,
                "error": f"Capability '{cap_name}' not found. Use search_capabilities_by_problem to find the right name.",
            }

        cap_id = cap_r["id"]
        mappings = ApplicationCapabilityMapping.query.filter_by(
            business_capability_id=cap_id
        ).limit(30).all()

        if not mappings:
            return {
                "success": True,
                "result": [],
                "count": 0,
                "capability_name": cap_r.get("name", cap_name),
                "message": f"No applications currently mapped to '{cap_r.get('name', cap_name)}'. This is a coverage gap.",
            }

        app_ids = [m.application_component_id for m in mappings]
        apps = ApplicationComponent.query.filter(
            ApplicationComponent.id.in_(app_ids)
        ).all()

        app_map = {a.id: a for a in apps}
        rows = []
        for m in mappings:
            a = app_map.get(m.application_component_id)
            if not a:
                continue
            rows.append({
                "id": a.id,
                "name": a.name,
                "deployment_status": a.deployment_status,
                "coverage_level": getattr(m, "coverage_level", None),
                "owner_team": getattr(a, "owner_team", None),
            })

        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "capability_id": cap_id,
            "capability_name": cap_r.get("name", cap_name),
            "message": (
                f"Found {len(rows)} application(s) mapped to '{cap_r.get('name', cap_name)}'. "
                "Use link_application_to_solution to attach relevant ones to your solution."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: find_technical_capabilities (Phase 5 grounding)              #
    # ------------------------------------------------------------------ #

    def _tool_find_technical_capabilities(self, args: dict) -> dict:
        """
        Return L1/L2 technical capabilities from the ACM taxonomy, optionally
        filtered by domain or keyword. Each result includes how many applications
        in the catalog already cover it — gaps (0 apps) are flagged explicitly.
        """
        from app.models.technical_capability import TechnicalCapability

        domain = args.get("domain")
        query = args.get("query", "").strip().lower()
        limit = min(args.get("limit", 15), 30)

        q = TechnicalCapability.query.filter(
            TechnicalCapability.level.in_(["L1", "L2"])
        )
        if domain:
            q = q.filter(TechnicalCapability.acm_domain == domain)
        if query:
            q = q.filter(
                db.or_(
                    TechnicalCapability.name.ilike(f"%{query}%"),
                    TechnicalCapability.description.ilike(f"%{query}%"),
                )
            )

        caps = q.order_by(
            TechnicalCapability.acm_domain,
            TechnicalCapability.level_number,
            TechnicalCapability.code,
        ).limit(limit).all()

        rows = []
        for c in caps:
            app_count = db.session.execute(
                db.text(
                    "SELECT COUNT(*) FROM application_technical_capability_mapping "
                    "WHERE technical_capability_id = :cid"
                ),
                {"cid": c.id},
            ).scalar() or 0
            rows.append({
                "id": c.id,
                "name": c.name,
                "domain": c.acm_domain,
                "level": c.level,
                "code": c.code,
                "description": c.description,
                "apps_covering": app_count,
                "is_gap": app_count == 0,
            })

        gaps = [r for r in rows if r["is_gap"]]
        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "gaps_count": len(gaps),
            "message": (
                f"Found {len(rows)} technical capabilities "
                + (f"in domain '{domain}'" if domain else "")
                + f". {len(gaps)} have zero app coverage (gaps). "
                "Use create_archimate_element (type=Node/SystemSoftware/TechnologyService) "
                "to model technology components that address these gaps."
            ),
        }

    # ------------------------------------------------------------------ #
    # Tool: verify_codegen                                                #
    # ------------------------------------------------------------------ #

    def _tool_verify_codegen(self, args: dict) -> dict:
        from app.services.codegen_verifier_service import CodegenVerifierService

        solution_id = args.get("solution_id")
        if not solution_id and args.get("solution_name"):
            resolved = self._resolver.resolve_solution(args["solution_name"])
            if isinstance(resolved, dict) and resolved.get("clarification_needed"):
                return resolved
            solution_id = resolved

        if not solution_id:
            return {"success": False, "error": "Provide solution_id or solution_name."}

        result = CodegenVerifierService.verify_solution(solution_id)
        if not result.get("success"):
            return result

        r = result["result"]
        grade_emoji = {"A": "✅", "B": "✅", "C": "⚠️", "D": "⚠️", "F": "🔴"}.get(r["grade"], "❓")
        result["message"] = (
            f"{grade_emoji} Codegen Score: {r['score']}/100 — Grade {r['grade']} "
            f"({r['coverage_pct']}% element coverage). "
            f"{r['archimate_element_count']} ArchiMate elements → ~{r['expected_route_count']} expected routes. "
            f"Findings: {r['findings_summary']['CRITICAL']} CRITICAL, {r['findings_summary']['HIGH']} HIGH."
        )
        return result

    # ------------------------------------------------------------------ #
    # Tool: propose_rationalization                                        #
    # ------------------------------------------------------------------ #

    def _tool_propose_rationalization(self, args: dict) -> dict:
        from app.services.rationalization_proposal_service import RationalizationProposalService
        limit = min(args.get("limit", 10), 25)
        return RationalizationProposalService.generate_proposals(limit=limit)

    # ------------------------------------------------------------------ #
    # Tool: build_architecture_plan                                        #
    # ------------------------------------------------------------------ #

    def _tool_build_architecture_plan(self, args: dict) -> dict:
        from app.services.orchestration_planner_service import OrchestrationPlannerService
        goal = args.get("goal", "")
        if not goal:
            return {"success": False, "error": "goal is required."}
        solution_id = args.get("solution_id")
        return OrchestrationPlannerService.build_plan(goal=goal, solution_id=solution_id)

    # ------------------------------------------------------------------ #
    # Tool: poll_infrastructure                                            #
    # ------------------------------------------------------------------ #

    def _tool_poll_infrastructure(self, args: dict) -> dict:
        from app.services.infrastructure_polling_service import InfrastructurePollingService
        return InfrastructurePollingService.poll_infrastructure(
            include_abacus=args.get("include_abacus", True),
            include_llm=args.get("include_llm", True),
            additional_urls=args.get("additional_urls"),
        )

    # ------------------------------------------------------------------ #
    # Tool: infer_schema                                                   #
    # ------------------------------------------------------------------ #

    def _tool_infer_schema(self, args: dict) -> dict:
        from app.services.schema_inference_service import SchemaInferenceService

        input_text = args.get("input_text", "").strip()
        if not input_text:
            return {"success": False, "error": "input_text is required."}

        fmt = args.get("format", "auto")
        if fmt == "auto":
            lower = input_text.lower()
            fmt = "ddl" if "create table" in lower else "openapi"

        if fmt == "ddl":
            result = SchemaInferenceService.infer_from_ddl(input_text)
            count = result.get("table_count", 0)
            key = "table_count"
        else:
            result = SchemaInferenceService.infer_from_openapi(input_text)
            count = result.get("schema_count", 0)
            key = "schema_count"

        if result.get("success"):
            result["message"] = (
                f"Inferred {count} DataObject(s) from {fmt.upper()}. "
                f"Call create_archimate_element for each item in 'create_args' to persist them."
            )
            if args.get("solution_id"):
                result["message"] += (
                    f" Then link to solution {args['solution_id']} via link_archimate_elements_to_solution."
                )
        return result

    # ------------------------------------------------------------------ #

    def _tool_validate_sap_clean_core(self, args: dict) -> dict:
        from app.services.sap_clean_core_service import SAPCleanCoreService

        # Portfolio-level scan
        if args.get("include_portfolio_scan"):
            return SAPCleanCoreService.quick_scan_portfolio(limit=20)

        # Resolve solution_id
        solution_id = args.get("solution_id")
        if not solution_id and args.get("solution_name"):
            resolved = self._resolver.resolve_solution(args["solution_name"])
            if isinstance(resolved, dict) and resolved.get("clarification_needed"):
                return resolved
            solution_id = resolved

        if not solution_id:
            return {
                "success": False,
                "error": (
                    "Provide solution_id or solution_name to validate, "
                    "or set include_portfolio_scan=true for a portfolio-wide SAP clean-core scan."
                ),
            }

        result = SAPCleanCoreService.validate_solution(solution_id)
        if not result.get("success"):
            return result

        r = result["result"]
        # Build a concise message the LLM can narrate directly
        f_counts = r["findings_summary"]
        tier_emoji = {"CLEAN_CORE_COMPLIANT": "✅", "AT_RISK": "⚠️", "NON_COMPLIANT": "🔴"}.get(
            r["compliance_tier"], "❓"
        )
        result["message"] = (
            f"{tier_emoji} SAP Clean-Core Score: {r['score']}/100 — {r['compliance_tier'].replace('_', ' ')}. "
            f"Upgrade risk: {r['upgrade_risk']}. "
            f"Findings: {f_counts['CRITICAL']} CRITICAL, {f_counts['HIGH']} HIGH, "
            f"{f_counts['MEDIUM']} MEDIUM, {f_counts['INFO']} INFO."
        )
        return result

    # ------------------------------------------------------------------ #

    def _tool_search_archimate_elements(self, args: dict) -> dict:
        try:
            from app.models.archimate_core import ArchiMateElement
        except ImportError:
            from app.models.models import ArchiMateElement

        limit = min(args.get("limit", 15), 50)
        q = ArchiMateElement.query

        if args.get("name_contains"):
            q = q.filter(ArchiMateElement.name.ilike(f"%{args['name_contains']}%"))
        if args.get("layer"):
            q = q.filter(ArchiMateElement.layer == args["layer"])
        if args.get("element_type"):
            q = q.filter(ArchiMateElement.type == args["element_type"])

        elements = q.limit(limit).all()
        rows = [{"id": e.id, "name": e.name, "type": e.type, "layer": e.layer} for e in elements]
        return {
            "success": True,
            "result": rows,
            "count": len(rows),
            "message": f"Found {len(rows)} ArchiMate element(s).",
        }


# ------------------------------------------------------------------ #
# Lightweight helper (avoids importing ApplicationCapabilityMapping   #
# at module level to prevent circular imports)                        #
# ------------------------------------------------------------------ #

def _safe_count(relationship_attr) -> int:
    """Count a SQLAlchemy relationship safely whether it's dynamic or a loaded list."""
    try:
        return relationship_attr.count()
    except TypeError:
        # list.count() requires an argument — it's a loaded list
        return len(list(relationship_attr))
    except Exception:
        return 0


def ApplicationCapabilityMapping_count(capability_id: int) -> int:
    try:
        from app.models.application_capability import ApplicationCapabilityMapping
        return ApplicationCapabilityMapping.query.filter_by(
            business_capability_id=capability_id
        ).count()
    except Exception:
        return 0
