import pytest

from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.inventory.schemas import ServerCreate
from backend.app.modules.inventory.service import InventoryService
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowTriggerSource, WorkflowType
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowStepCreate
from backend.app.modules.workflows.service import WorkflowService


def workflow_service(db_session) -> WorkflowService:
    return WorkflowService(
        workflow_repository=WorkflowRunRepository(db_session),
        step_repository=WorkflowStepRepository(db_session),
        server_repository=ServerRepository(db_session),
    )


@pytest.mark.asyncio
async def test_workflow_creation_and_transitions(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = workflow_service(db_session)
        workflow = await service.create_workflow(
            WorkflowCreate(
                workflow_type=WorkflowType.PROFILE_EXECUTION,
                trigger_source=WorkflowTriggerSource.MANUAL,
                context_json={"profile_id": "docker-host"},
            )
        )
        step = await service.add_step(
            workflow.id,
            WorkflowStepCreate(step_order=1, step_type="profile_step", name="Install Docker"),
        )

        await service.mark_queued(workflow.id)
        running = await service.start_workflow(workflow.id)
        await service.start_step(step.id)
        await service.append_log(step.id, "step started")
        await service.complete_step(step.id, log_output="step done")
        completed = await service.complete_workflow(workflow.id, result_summary={"jobs": ["job-1"]})

        assert running.status == WorkflowStatus.RUNNING
        assert completed.status == WorkflowStatus.SUCCESS
        assert completed.result_summary == {"jobs": ["job-1"]}
        assert completed.steps[0].log_output == "step started\nstep done"


@pytest.mark.asyncio
async def test_workflow_cancel(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        service = workflow_service(db_session)
        workflow = await service.create_workflow(
            WorkflowCreate(workflow_type=WorkflowType.PACKAGE_EXECUTION)
        )

        cancelled = await service.cancel_workflow(workflow.id)

        assert cancelled.status == WorkflowStatus.CANCELLED
        assert cancelled.finished_at is not None


@pytest.mark.asyncio
async def test_workflow_reads_target_hostnames(client) -> None:
    session = next(iter(client.app.dependency_overrides.values()))
    async for db_session in session():
        server = await InventoryService(ServerRepository(db_session)).create_server(
            ServerCreate(
                hostname="workflow-host-01",
                ip_address="10.9.0.10",
                operating_system="Ubuntu 24.04 LTS",
                environment="lab",
                provider="manual",
                ssh_port=22,
                ssh_username="ubuntu",
            )
        )
        service = workflow_service(db_session)
        workflow = await service.create_workflow(
            WorkflowCreate(
                workflow_type=WorkflowType.SCHEDULED_ACTION,
                trigger_source=WorkflowTriggerSource.MANUAL,
                target_server_id=server.id,
            )
        )
        await service.add_step(
            workflow.id,
            WorkflowStepCreate(
                step_order=1,
                step_type="action",
                name=f"Check host on {server.id}",
                metadata_json={"target_server_id": str(server.id)},
            ),
        )

        read = await service.get_workflow(workflow.id)

        assert read.target_hostname == "workflow-host-01"
        assert read.steps[0].target_hostname == "workflow-host-01"
