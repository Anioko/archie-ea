"""F-17, Capgemini dry-run: a workflow step with step_type "human_input" had
no STEP_HANDLERS entry, so _execute_step fell through to dynamic service
invocation with no service_class configured — a step meant to pause for a
person instead ran (and failed) as an automated step. Fixed by routing
human_input through the same waiting_approval pause/resume path approval
steps already use.
"""

import pytest
import uuid


@pytest.mark.usefixtures("db_session")
def test_human_input_step_pauses_instead_of_executing(app, db_session, make_org, tenant_ctx):
    from app.models.workflow_models import EAWorkflowDefinition, EAWorkflowInstance
    from app.services.ea_workflow_engine import EAWorkflowEngine

    org = make_org("ea-workflow-human-input")
    with tenant_ctx(org.id):
        suffix = uuid.uuid4().hex[:10].upper()
        definition = EAWorkflowDefinition(
            workflow_code=f"TEST_HUMAN_INPUT_{suffix}",
            workflow_name="Test human input pause",
            workflow_category="test",
            steps=[{
                "step_id": "collect_input",
                "step_name": "Collect stakeholder sign-off",
                "step_type": "human_input",
                "handler": "human_input",
            }],
            organization_id=org.id,
        )
        db_session.add(definition)
        db_session.commit()

        instance = EAWorkflowInstance(
            workflow_definition_id=definition.id,
            instance_code=f"TEST_HUMAN_INPUT_{suffix}_1",
            status="running",
            context={},
            organization_id=org.id,
        )
        db_session.add(instance)
        db_session.commit()

        with app.app_context():
            engine = EAWorkflowEngine()
            result = engine._execute_step(
                instance, definition.steps[0], step_index=0
            )
            assert result["status"] == "waiting_approval"
            assert result["step_id"] == "collect_input"
