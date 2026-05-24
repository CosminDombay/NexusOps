# NexusOps Service Files for Review

This file contains the requested service module source code with each original path shown directly above its code block.

## backend/app/modules/workflows/service.py

```python
from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.workflows.models import (
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowRunRead, WorkflowStepCreate, WorkflowStepRead


class WorkflowNotFoundError(Exception):
    """Raised when a workflow run cannot be found."""


class WorkflowStepNotFoundError(Exception):
    """Raised when a workflow step cannot be found."""


class WorkflowInvalidTransitionError(Exception):
    """Raised when a workflow transition is not valid."""


class WorkflowService:
    def __init__(
        self,
        *,
        workflow_repository: WorkflowRunRepository,
        step_repository: WorkflowStepRepository,
        server_repository: ServerRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.server_repository = server_repository
        self.audit_service = audit_service or AuditService(AuditEventRepository(workflow_repository.session))

    async def list_workflows(self, *, target_server_id: UUID | None = None) -> list[WorkflowRunRead]:
        workflows = (
            await self.workflow_repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.workflow_repository.list()
        )
        return [await self._to_read(item) for item in workflows]

    async def get_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self.workflow_repository.get_by_id(workflow_run_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow run not found")
        return await self._to_read(workflow)

    async def create_workflow(self, payload: WorkflowCreate) -> WorkflowRunRead:
        workflow = await self.workflow_repository.create(
            WorkflowRun(
                workflow_type=payload.workflow_type,
                trigger_source=payload.trigger_source,
                target_server_id=payload.target_server_id,
                initiated_by=payload.initiated_by,
                context_json=payload.context_json,
                status=WorkflowStatus.PENDING,
            )
        )
        await self.workflow_repository.session.commit()
        await self._audit_workflow(workflow, "workflow.created", "success")
        return await self._to_read(workflow)

    async def mark_queued(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.QUEUED
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.queued", "success")
        return await self._to_read(workflow)

    async def start_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        if workflow.status == WorkflowStatus.CANCELLED:
            raise WorkflowInvalidTransitionError("Cancelled workflow cannot be started")
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = workflow.started_at or datetime.now(UTC)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.started", "success")
        return await self._to_read(workflow)

    async def complete_workflow(self, workflow_run_id: UUID, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.SUCCESS
        workflow.finished_at = datetime.now(UTC)
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.completed", "success")
        return await self._to_read(workflow)

    async def fail_workflow(self, workflow_run_id: UUID, error_message: str, result_summary: dict | None = None) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.FAILED
        workflow.finished_at = datetime.now(UTC)
        workflow.error_message = error_message
        workflow.result_summary = result_summary or workflow.result_summary
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.failed", "failed", error=error_message)
        return await self._to_read(workflow)

    async def cancel_workflow(self, workflow_run_id: UUID) -> WorkflowRunRead:
        workflow = await self._workflow(workflow_run_id)
        workflow.status = WorkflowStatus.CANCELLED
        workflow.finished_at = datetime.now(UTC)
        await self.workflow_repository.session.commit()
        await self.workflow_repository.session.refresh(workflow, attribute_names=["steps"])
        await self._audit_workflow(workflow, "workflow.cancelled", "cancelled")
        return await self._to_read(workflow)

    async def add_step(self, workflow_run_id: UUID, payload: WorkflowStepCreate) -> WorkflowStepRead:
        await self._workflow(workflow_run_id)
        step = await self.step_repository.create(
            WorkflowStep(
                workflow_run_id=workflow_run_id,
                step_order=payload.step_order,
                step_type=payload.step_type,
                name=payload.name,
                metadata_json=payload.metadata_json,
            )
        )
        await self.step_repository.session.commit()
        return await self._step_to_read(step)

    async def start_step(self, step_id: UUID) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.RUNNING
        step.started_at = step.started_at or datetime.now(UTC)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def complete_step(self, step_id: UUID, log_output: str | None = None, metadata_json: dict | None = None) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.SUCCESS
        step.finished_at = datetime.now(UTC)
        if log_output:
            step.log_output = self._append_text(step.log_output, log_output)
        if metadata_json:
            step.metadata_json = {**step.metadata_json, **metadata_json}
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def fail_step(self, step_id: UUID, error_output: str, log_output: str | None = None) -> WorkflowStepRead:
        step = await self._step(step_id)
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = datetime.now(UTC)
        step.error_output = self._append_text(step.error_output, error_output)
        if log_output:
            step.log_output = self._append_text(step.log_output, log_output)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def append_log(self, step_id: UUID, message: str, *, stderr: bool = False) -> WorkflowStepRead:
        step = await self._step(step_id)
        if stderr:
            step.error_output = self._append_text(step.error_output, message)
        else:
            step.log_output = self._append_text(step.log_output, message)
        await self.step_repository.session.commit()
        await self.step_repository.session.refresh(step)
        return await self._step_to_read(step)

    async def _workflow(self, workflow_run_id: UUID) -> WorkflowRun:
        workflow = await self.workflow_repository.get_by_id(workflow_run_id)
        if workflow is None:
            raise WorkflowNotFoundError("Workflow run not found")
        return workflow

    async def _step(self, step_id: UUID) -> WorkflowStep:
        step = await self.step_repository.get_by_id(step_id)
        if step is None:
            raise WorkflowStepNotFoundError("Workflow step not found")
        return step

    @staticmethod
    def _append_text(existing: str, message: str) -> str:
        if not existing:
            return message
        return f"{existing.rstrip()}\n{message}"

    async def _to_read(self, workflow: WorkflowRun) -> WorkflowRunRead:
        data = WorkflowRunRead.model_validate(workflow)
        hostname = await self._hostname(workflow.target_server_id)
        steps = [await self._step_to_read(step) for step in workflow.steps]
        target_nodes = [item for item in {hostname, *[step.target_hostname for step in steps]} if item]
        linked_job_ids: list[str] = []
        for step in steps:
            raw_job_ids = step.metadata_json.get("job_ids") if step.metadata_json else None
            if isinstance(raw_job_ids, list):
                linked_job_ids.extend(str(job_id) for job_id in raw_job_ids)
        current_step = next((step.name for step in steps if step.status == WorkflowStepStatus.RUNNING), None)
        return data.model_copy(
            update={
                "target_hostname": hostname,
                "steps": steps,
                "current_step": current_step,
                "completed_steps": sum(1 for step in steps if step.status == WorkflowStepStatus.SUCCESS),
                "failed_steps": sum(1 for step in steps if step.status == WorkflowStepStatus.FAILED),
                "duration_seconds": self._duration_seconds(workflow.started_at, workflow.finished_at),
                "target_nodes": target_nodes,
                "linked_job_ids": sorted(set(linked_job_ids)),
            }
        )

    async def _step_to_read(self, step: WorkflowStep) -> WorkflowStepRead:
        data = WorkflowStepRead.model_validate(step)
        target_server_id = step.metadata_json.get("target_server_id") if step.metadata_json else None
        hostname = await self._hostname(target_server_id)
        return data.model_copy(update={"target_hostname": hostname})

    async def _hostname(self, server_id) -> str | None:
        if self.server_repository is None or not server_id:
            return None
        try:
            server_uuid = server_id if isinstance(server_id, UUID) else UUID(str(server_id))
        except ValueError:
            return None
        server = await self.server_repository.get_by_id(server_uuid)
        return server.hostname if server else None

    @staticmethod
    def _duration_seconds(started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if started_at is None:
            return None
        start = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
        end = finished_at or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return max(0, int((end - start).total_seconds()))

    async def _audit_workflow(
        self,
        workflow: WorkflowRun,
        event_type: str,
        result: str,
        *,
        error: str | None = None,
    ) -> None:
        await self.audit_service.record(
            event_type=event_type,
            actor_username=workflow.initiated_by,
            target_type="workflow_run",
            target_id=workflow.id,
            result=result,
            workflow_run_id=workflow.id,
            metadata={
                "workflow_type": workflow.workflow_type.value,
                "trigger_source": workflow.trigger_source.value,
                "target_server_id": str(workflow.target_server_id) if workflow.target_server_id else None,
            },
            error=error,
        )

```

## backend/app/modules/deployments/service.py

```python
from datetime import UTC, datetime
import re
from hashlib import sha256
from uuid import UUID

from backend.app.modules.deployments.models import (
    Deployment,
    DeploymentExecution,
    DeploymentRevision,
    DeploymentStatus,
    DeploymentTarget,
    DeploymentTargetExecution,
)
from backend.app.modules.deployments.repository import (
    DeploymentExecutionRepository,
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
    DeploymentTargetExecutionRepository,
)
from backend.app.modules.deployments.schemas import (
    DeploymentCreate,
    DeploymentLogsRead,
    DeploymentExecutionRead,
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentRevisionRead,
    DeploymentStatusRead,
    DeploymentTargetExecutionRead,
    DeploymentTargetRead,
    DeploymentUpdate,
)
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError


class DeploymentNotFoundError(Exception):
    """Raised when a deployment cannot be found."""


class DeploymentValidationError(Exception):
    """Raised when a deployment request is invalid."""


class DockerComposeDeploymentService:
    """SSH-backed Docker Compose deployment orchestration."""

    COMPOSE_FILENAME = "docker-compose.yaml"
    ENV_FILENAME = ".env"

    def __init__(
        self,
        *,
        repository: DeploymentRepository,
        target_repository: DeploymentTargetRepository,
        revision_repository: DeploymentRevisionRepository,
        server_repository: ServerRepository,
        job_service: JobService,
        execution_repository: DeploymentExecutionRepository | None = None,
        target_execution_repository: DeploymentTargetExecutionRepository | None = None,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.repository = repository
        self.target_repository = target_repository
        self.revision_repository = revision_repository
        self.execution_repository = execution_repository or DeploymentExecutionRepository(repository.session)
        self.target_execution_repository = target_execution_repository or DeploymentTargetExecutionRepository(repository.session)
        self.server_repository = server_repository
        self.job_service = job_service
        self.credential_service = credential_service

    async def list_deployments(self, *, server_id: UUID | None = None) -> list[DeploymentRead]:
        deployments = (
            await self.repository.list_for_server(server_id)
            if server_id is not None
            else await self.repository.list()
        )
        return [await self._to_read(deployment) for deployment in deployments]

    async def create_deployment(self, payload: DeploymentCreate) -> DeploymentRead:
        target_ids = payload.target_server_ids or ([payload.target_server_id] if payload.target_server_id else [])
        if not target_ids:
            raise DeploymentValidationError("Select at least one deployment target")
        servers = [await self._managed_server(target_id) for target_id in target_ids]
        deployment = await self.repository.create(
            Deployment(
                name=payload.name,
                description=payload.description,
                compose_content=payload.compose_content,
                env_content=payload.env_content,
                credential_refs=payload.credential_refs,
                status=DeploymentStatus.DRAFT,
            )
        )
        for server in servers:
            await self.target_repository.create(
                DeploymentTarget(
                    deployment_id=deployment.id,
                    server_id=server.id,
                    remote_path=payload.remote_path,
                    status=DeploymentStatus.DRAFT,
                )
            )
        await self.repository.session.commit()
        return await self._to_read(deployment)

    async def delete_deployment(self, deployment_id: UUID) -> None:
        deployment = await self.repository.get_by_id(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError("Deployment not found")

        await self.target_execution_repository.delete_for_deployment(deployment.id)
        await self.execution_repository.delete_for_deployment(deployment.id)
        await self.revision_repository.delete_for_deployment(deployment.id)
        await self.target_repository.delete_for_deployment(deployment.id)
        await self.repository.delete(deployment)
        await self.repository.session.commit()

    async def update_deployment(self, deployment_id: UUID, payload: DeploymentUpdate) -> DeploymentRead:
        deployment = await self.repository.get_by_id(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError("Deployment not found")

        target_ids = payload.target_server_ids or ([payload.target_server_id] if payload.target_server_id else [])
        if not target_ids:
            raise DeploymentValidationError("Select at least one deployment target")
        servers = [await self._managed_server(target_id) for target_id in target_ids]

        deployment.name = payload.name
        deployment.description = payload.description
        deployment.compose_content = payload.compose_content
        deployment.env_content = payload.env_content
        deployment.credential_refs = payload.credential_refs
        deployment.status = DeploymentStatus.DRAFT
        await self.target_repository.delete_for_deployment(deployment.id)
        for server in servers:
            await self.target_repository.create(
                DeploymentTarget(
                    deployment_id=deployment.id,
                    server_id=server.id,
                    remote_path=payload.remote_path,
                    status=DeploymentStatus.DRAFT,
                )
            )

        await self.repository.session.commit()
        await self.repository.session.refresh(deployment)
        return await self._to_read(deployment)

    async def deploy(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "deploy")

    async def deploy_for_target(self, deployment_id: UUID, target_server_id: UUID) -> DeploymentOperationRead:
        deployment, targets = await self._deployment_and_targets(deployment_id)
        if target_server_id not in {target.server_id for target in targets}:
            raise DeploymentValidationError("Deployment target does not match the profile target host")
        return await self._run_operation(deployment.id, "deploy", target_server_ids={target_server_id})

    async def redeploy(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "redeploy")

    async def restart(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "restart")

    async def stop(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "stop")

    async def status(self, deployment_id: UUID) -> DeploymentStatusRead:
        deployment, targets = await self._deployment_and_targets(deployment_id)
        jobs = []
        for target in targets:
            command = self._compose_command(target, deployment, "ps")
            jobs.append(
                await self.job_service.execute(
                    JobExecuteRequest(
                        target_server_id=target.server_id,
                        operation_type=f"deployment:{deployment.id}:status",
                        command=command,
                    )
                )
            )
        return DeploymentStatusRead(
            deployment_id=deployment.id,
            target_server_id=targets[0].server_id if targets else None,
            job=jobs[0] if jobs else None,
            jobs=jobs,
        )

    async def logs(self, deployment_id: UUID) -> DeploymentLogsRead:
        deployment, targets = await self._deployment_and_targets(deployment_id)
        jobs = []
        log_parts = []
        for target in targets:
            command = self._compose_command(target, deployment, "logs --tail=200")
            job = await self.job_service.execute(
                JobExecuteRequest(
                    target_server_id=target.server_id,
                    operation_type=f"deployment:{deployment.id}:logs",
                    command=command,
                )
            )
            jobs.append(job)
            log_parts.append(f"===== {target.server_id} =====\n{job.stdout or ''}".rstrip())
        return DeploymentLogsRead(
            deployment_id=deployment.id,
            target_server_id=targets[0].server_id if targets else None,
            logs="\n\n".join(log_parts),
            job=jobs[0] if jobs else None,
            jobs=jobs,
        )

    async def _run_operation(
        self,
        deployment_id: UUID,
        operation: str,
        *,
        target_server_ids: set[UUID] | None = None,
    ) -> DeploymentOperationRead:
        deployment, all_targets = await self._deployment_and_targets(deployment_id)
        targets = [target for target in all_targets if target_server_ids is None or target.server_id in target_server_ids]
        if not targets:
            raise DeploymentValidationError("Deployment has no matching target hosts")
        for target in targets:
            await self._managed_server(target.server_id)
        deployment.status = DeploymentStatus.DEPLOYING
        for target in targets:
            target.status = DeploymentStatus.DEPLOYING
        await self.repository.session.commit()

        execution = await self.execution_repository.create(
            DeploymentExecution(
                deployment_id=deployment.id,
                operation=operation,
                status=DeploymentStatus.DEPLOYING,
                trigger_source="manual",
                started_at=datetime.now(UTC),
            )
        )
        await self.repository.session.commit()

        jobs = []
        revisions = []
        target_executions = []
        for target in targets:
            target_execution = await self.target_execution_repository.create(
                DeploymentTargetExecution(
                    execution_id=execution.id,
                    deployment_id=deployment.id,
                    target_id=target.id,
                    server_id=target.server_id,
                    status=DeploymentStatus.DEPLOYING,
                    started_at=datetime.now(UTC),
                )
            )
            revision = await self.revision_repository.create(
                DeploymentRevision(
                    deployment_id=deployment.id,
                    server_id=target.server_id,
                    revision_number=await self.revision_repository.next_revision_number(deployment.id),
                    operation=operation,
                    compose_content=deployment.compose_content,
                    env_content=deployment.env_content,
                    status=DeploymentStatus.DEPLOYING,
                )
            )
            await self.repository.session.commit()
            try:
                command, redacted_command = await self._operation_commands(deployment, target, operation)
                job = await self.job_service.execute(
                    JobExecuteRequest(
                        target_server_id=target.server_id,
                        operation_type=f"deployment:{deployment.id}:{operation}",
                        command=command,
                        redacted_command=redacted_command,
                    )
                )
                next_status = DeploymentStatus.RUNNING if job.exit_code == 0 and operation != "stop" else DeploymentStatus.FAILED
                if job.exit_code == 0 and operation == "stop":
                    next_status = DeploymentStatus.STOPPED

                target.status = next_status
                target.last_job_id = job.id
                revision.status = next_status
                revision.job_id = job.id
                revision.stdout = job.stdout
                revision.stderr = job.stderr
                target_execution.status = next_status
                target_execution.job_id = job.id
                target_execution.revision_id = revision.id
                target_execution.stdout = job.stdout
                target_execution.stderr = job.stderr
                target_execution.finished_at = datetime.now(UTC)
                jobs.append(job)
            except Exception as exc:
                target.status = DeploymentStatus.FAILED
                revision.status = DeploymentStatus.FAILED
                revision.stderr = str(exc)
                target_execution.status = DeploymentStatus.FAILED
                target_execution.error_message = str(exc)
                target_execution.finished_at = datetime.now(UTC)
            revisions.append(revision)
            target_executions.append(target_execution)
            await self.repository.session.commit()

        deployment.status = self._rollup_status([target.status for target in targets], operation)
        execution.status = deployment.status
        execution.finished_at = datetime.now(UTC)
        execution.result_summary = {
            "target_count": len(targets),
            "success_count": sum(1 for item in target_executions if item.status in {DeploymentStatus.RUNNING, DeploymentStatus.STOPPED, DeploymentStatus.SUCCESS}),
            "failed_count": sum(1 for item in target_executions if item.status == DeploymentStatus.FAILED),
            "job_ids": [str(job.id) for job in jobs],
        }
        failed_messages = [item.error_message for item in target_executions if item.error_message]
        execution.error_message = "\n".join(failed_messages) if failed_messages else None
        await self.repository.session.commit()
        for revision in revisions:
            await self.repository.session.refresh(revision)
        await self.repository.session.refresh(execution)
        return DeploymentOperationRead(
            deployment=await self._to_read(deployment),
            job=jobs[0] if jobs else None,
            revision=DeploymentRevisionRead.model_validate(revisions[0]) if revisions else None,
            jobs=jobs,
            revisions=[DeploymentRevisionRead.model_validate(item) for item in revisions],
            execution=await self._execution_to_read(execution),
        )

    async def _deployment_and_targets(self, deployment_id: UUID) -> tuple[Deployment, list[DeploymentTarget]]:
        deployment = await self.repository.get_by_id(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError("Deployment not found")
        targets = await self.target_repository.list_for_deployment(deployment.id)
        if not targets:
            raise DeploymentValidationError("Deployment has no target host")
        return deployment, targets

    async def _managed_server(self, server_id: UUID):
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")
        if not server.managed or server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            raise JobTargetNotManagedError("Target server is not managed")
        return server

    async def _to_read(self, deployment: Deployment) -> DeploymentRead:
        targets = await self.target_repository.list_for_deployment(deployment.id)
        target_reads = [await self._target_to_read(target) for target in targets]
        executions = [await self._execution_to_read(item) for item in await self.execution_repository.list_for_deployment(deployment.id)]
        first_target = targets[0] if targets else None
        first_server = await self.server_repository.get_by_id(first_target.server_id) if first_target else None
        return DeploymentRead(
            id=deployment.id,
            name=deployment.name,
            description=deployment.description,
            compose_content=deployment.compose_content,
            env_content=deployment.env_content,
            credential_refs=deployment.credential_refs,
            status=deployment.status,
            target_server_id=first_target.server_id if first_target else None,
            target_server_ids=[target.server_id for target in targets],
            target_hostname=first_server.hostname if first_server else None,
            targets=target_reads,
            latest_execution=executions[0] if executions else None,
            execution_history=executions[:5],
            remote_path=first_target.remote_path if first_target else None,
            ports=self._extract_ports(deployment.compose_content),
            compose_source="inline",
            uptime_seconds=self._uptime_seconds(deployment) if deployment.status == DeploymentStatus.RUNNING else None,
            health_state=self._health_state(deployment.status),
            sync_status=self._sync_status(deployment, first_target),
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
        )

    async def _target_to_read(self, target: DeploymentTarget) -> DeploymentTargetRead:
        server = await self.server_repository.get_by_id(target.server_id)
        executions = await self.target_execution_repository.list_for_deployment(target.deployment_id)
        last_execution = next((item for item in executions if item.target_id == target.id), None)
        return DeploymentTargetRead.model_validate(target).model_copy(
            update={
                "hostname": server.hostname if server else None,
                "node_type": server.node_type.value if server else None,
                "environment": server.environment.value if server else None,
                "provider": server.provider if server else None,
                "readiness": self._server_readiness(server),
                "last_execution": await self._target_execution_to_read(last_execution) if last_execution else None,
            }
        )

    async def _execution_to_read(self, execution: DeploymentExecution) -> DeploymentExecutionRead:
        target_executions = [
            await self._target_execution_to_read(item)
            for item in await self.target_execution_repository.list_for_execution(execution.id)
        ]
        return DeploymentExecutionRead.model_validate(execution).model_copy(
            update={
                "duration_seconds": self._duration_seconds(execution.started_at, execution.finished_at),
                "target_count": len(target_executions),
                "success_count": sum(1 for item in target_executions if item.status in {DeploymentStatus.RUNNING, DeploymentStatus.STOPPED, DeploymentStatus.SUCCESS}),
                "failed_count": sum(1 for item in target_executions if item.status == DeploymentStatus.FAILED),
                "target_executions": target_executions,
            }
        )

    async def _target_execution_to_read(self, execution: DeploymentTargetExecution | None) -> DeploymentTargetExecutionRead | None:
        if execution is None:
            return None
        server = await self.server_repository.get_by_id(execution.server_id)
        return DeploymentTargetExecutionRead.model_validate(execution).model_copy(
            update={
                "hostname": server.hostname if server else None,
                "duration_seconds": self._duration_seconds(execution.started_at, execution.finished_at),
            }
        )

    async def _operation_commands(self, deployment: Deployment, target: DeploymentTarget, operation: str) -> tuple[str, str]:
        deployment_path = self._deployment_path(target, deployment)
        compose = self._heredoc(self.COMPOSE_FILENAME, deployment.compose_content, "NEXUSOPS_COMPOSE_EOF")
        env_content, redacted_env_content = await self._env_contents(deployment)
        env = self._heredoc(self.ENV_FILENAME, env_content, "NEXUSOPS_ENV_EOF")
        redacted_env = self._heredoc(self.ENV_FILENAME, redacted_env_content, "NEXUSOPS_ENV_EOF")
        if operation in {"deploy", "redeploy"}:
            actions = [
                self._docker_compose("version"),
                self._docker_compose("pull"),
                self._docker_compose("up -d"),
            ]
        elif operation == "restart":
            actions = [self._docker_compose("restart")]
        elif operation == "stop":
            actions = [self._docker_compose("stop")]
        else:
            raise DeploymentValidationError("Unsupported deployment operation")

        prefix = [
            "set -e",
            f"mkdir -p {self._sh_quote(deployment_path)}",
            f"cd {self._sh_quote(deployment_path)}",
        ]
        return (
            "\n".join([*prefix, compose, env, *actions]),
            "\n".join([*prefix, compose, redacted_env, *actions]),
        )

    async def _env_contents(self, deployment: Deployment) -> tuple[str, str]:
        lines = [deployment.env_content or ""]
        redacted_lines = [deployment.env_content or ""]
        for env_key, credential_ref in sorted((deployment.credential_refs or {}).items()):
            clean_key = env_key.strip()
            clean_ref = credential_ref.strip()
            if not clean_key or not clean_ref:
                continue
            if self.credential_service is None:
                raise DeploymentValidationError("Credential service is required for deployment credential refs")
            credential = await self.credential_service.resolve_credential(clean_ref)
            secret = credential.secret or credential.private_key
            if not secret:
                raise DeploymentValidationError(f"Credential for {clean_key} has no usable secret value")
            lines.append(f"{clean_key}={self._dotenv_quote(secret)}")
            redacted_lines.append(f"{clean_key}=********")
        return "\n".join(part for part in lines if part), "\n".join(part for part in redacted_lines if part)

    @staticmethod
    def _deployment_path(target: DeploymentTarget, deployment: Deployment) -> str:
        safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in deployment.name.lower())
        return f"{target.remote_path.rstrip('/')}/{safe_name}"

    @staticmethod
    def _heredoc(filename: str, content: str, marker: str) -> str:
        base_marker = marker
        digest = sha256(content.encode("utf-8")).hexdigest()
        suffix_length = 12
        attempt = 0
        while re.search(rf"^{re.escape(marker)}$", content, flags=re.MULTILINE):
            attempt += 1
            counter_suffix = f"_{attempt}" if suffix_length == len(digest) else ""
            marker = f"{base_marker}_{digest[:suffix_length]}{counter_suffix}"
            suffix_length = min(len(digest), suffix_length + 4)
        return f"cat > {filename} <<'{marker}'\n{content}\n{marker}"

    @classmethod
    def _compose_command(cls, target: DeploymentTarget, deployment: Deployment, compose_args: str) -> str:
        deployment_path = cls._deployment_path(target, deployment)
        return "\n".join(
            [
                "set -e",
                f"cd {cls._sh_quote(deployment_path)}",
                cls._docker_compose(compose_args),
            ]
        )

    @classmethod
    def _docker_compose(cls, compose_args: str) -> str:
        return f"docker compose -f {cls.COMPOSE_FILENAME} --env-file {cls.ENV_FILENAME} {compose_args}"

    @staticmethod
    def _sh_quote(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _dotenv_quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _extract_ports(compose_content: str) -> list[str]:
        ports: list[str] = []
        for match in re.finditer(r"['\"]?(\d{2,5}:\d{1,5}(?:/(?:tcp|udp))?)['\"]?", compose_content):
            value = match.group(1)
            if value not in ports:
                ports.append(value)
        return ports[:8]

    @staticmethod
    def _uptime_seconds(deployment: Deployment) -> int | None:
        updated_at = deployment.updated_at
        if updated_at is None:
            return None
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return max(0, int((datetime.now(UTC) - updated_at).total_seconds()))

    @staticmethod
    def _health_state(status: DeploymentStatus) -> str:
        if status in {DeploymentStatus.RUNNING, DeploymentStatus.SUCCESS}:
            return "healthy"
        if status == DeploymentStatus.PARTIAL_SUCCESS:
            return "degraded"
        if status == DeploymentStatus.FAILED:
            return "failed"
        if status == DeploymentStatus.STOPPED:
            return "stopped"
        return "unknown"

    @staticmethod
    def _rollup_status(statuses: list[DeploymentStatus], operation: str) -> DeploymentStatus:
        if not statuses:
            return DeploymentStatus.FAILED
        success_states = {DeploymentStatus.RUNNING, DeploymentStatus.SUCCESS}
        if operation == "stop":
            success_states = {DeploymentStatus.STOPPED}
        success_count = sum(1 for status in statuses if status in success_states)
        failed_count = sum(1 for status in statuses if status == DeploymentStatus.FAILED)
        if success_count == len(statuses):
            return DeploymentStatus.STOPPED if operation == "stop" else DeploymentStatus.RUNNING
        if success_count and failed_count:
            return DeploymentStatus.PARTIAL_SUCCESS
        if failed_count == len(statuses):
            return DeploymentStatus.FAILED
        return DeploymentStatus.DEGRADED

    @staticmethod
    def _duration_seconds(started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if started_at is None:
            return None
        start = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
        end = finished_at or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return max(0, int((end - start).total_seconds()))

    @staticmethod
    def _server_readiness(server) -> str:
        if server is None:
            return "unknown"
        if server.lifecycle_state in {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }:
            return server.lifecycle_state.value
        if not server.ip_address or server.ip_address.startswith("0."):
            return "ip_missing"
        if str(server.last_health_status) == "unreachable":
            return "ssh_unreachable"
        return "managed" if server.managed else "unmanaged"

    @staticmethod
    def _sync_status(deployment: Deployment, target: DeploymentTarget | None) -> str:
        if target is None:
            return "missing-target"
        if deployment.status == DeploymentStatus.DRAFT:
            return "pending-deploy"
        if deployment.status == target.status:
            return "synced"
        return "drifted"

```

## backend/app/modules/automations/service.py

```python
from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.automations.models import Automation, AutomationOperationType
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.schemas import AutomationCreate, AutomationRead, AutomationTargetRead, AutomationUpdate
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.schemas import JobActionExecuteRequest
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.schemas import PackageExecuteRequest
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowTriggerSource, WorkflowType
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowStepCreate
from backend.app.modules.workflows.service import WorkflowService


class AutomationNotFoundError(Exception):
    """Raised when an automation cannot be found."""


class AutomationValidationError(Exception):
    """Raised when automation configuration is invalid."""


class AutomationService:
    def __init__(
        self,
        *,
        repository: AutomationRepository,
        server_repository: ServerRepository,
        workflow_service: WorkflowService,
        job_service: JobService | None = None,
        profile_service: ProfileService | None = None,
        package_service: PackageAutomationService | None = None,
    ) -> None:
        self.repository = repository
        self.server_repository = server_repository
        self.workflow_service = workflow_service
        self.job_service = job_service
        self.profile_service = profile_service
        self.package_service = package_service

    async def list_automations(self, *, target_server_id: UUID | None = None) -> list[AutomationRead]:
        automations = (
            await self.repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.repository.list()
        )
        workflows = await self.workflow_service.list_workflows(target_server_id=target_server_id)
        servers = await self.server_repository.list(include_inactive=True)
        return [
            self._to_read(
                automation,
                workflows=[workflow for workflow in workflows if workflow.context_json.get("automation_id") == str(automation.id)],
                servers=servers,
            )
            for automation in automations
        ]

    async def create_automation(self, payload: AutomationCreate) -> AutomationRead:
        self._validate_supported_operation(payload.operation_type)
        await self._validate_targets([str(item) for item in payload.target_server_ids])
        automation = await self.repository.create(
            Automation(
                name=payload.name,
                description=payload.description,
                enabled=payload.enabled,
                schedule_type=payload.schedule_type,
                cron_expression=payload.cron_expression,
                interval_seconds=payload.interval_seconds,
                target_mode=payload.target_mode,
                target_server_ids=[str(item) for item in payload.target_server_ids],
                operation_type=payload.operation_type,
                reference_id=payload.reference_id,
                raw_command=payload.raw_command,
                variables_json=payload.variables_json,
                credential_refs=payload.credential_refs,
            )
        )
        await self.repository.session.commit()
        return self._to_read(automation)

    async def update_automation(self, automation_id: UUID, payload: AutomationUpdate) -> AutomationRead:
        automation = await self._automation(automation_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "operation_type" in update_data and update_data["operation_type"] is not None:
            self._validate_supported_operation(update_data["operation_type"])
        if "target_server_ids" in update_data and update_data["target_server_ids"] is not None:
            update_data["target_server_ids"] = [str(item) for item in update_data["target_server_ids"]]
            await self._validate_targets(update_data["target_server_ids"])
        for key, value in update_data.items():
            setattr(automation, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def delete_automation(self, automation_id: UUID) -> None:
        automation = await self._automation(automation_id)
        await self.repository.delete(automation)
        await self.repository.session.commit()

    async def enable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = True
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def disable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = False
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def create_run_workflow(
        self,
        automation_id: UUID,
        *,
        trigger_source: WorkflowTriggerSource = WorkflowTriggerSource.MANUAL,
    ):
        automation = await self._automation(automation_id)
        target_server_id = UUID(automation.target_server_ids[0]) if automation.target_server_ids else None
        workflow_type = {
            AutomationOperationType.ACTION: WorkflowType.SCHEDULED_ACTION,
            AutomationOperationType.PROFILE: WorkflowType.SCHEDULED_PROFILE,
            AutomationOperationType.PACKAGE: WorkflowType.SCHEDULED_PACKAGE,
        }.get(automation.operation_type)
        if workflow_type is None:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

        workflow = await self.workflow_service.create_workflow(
            WorkflowCreate(
                workflow_type=workflow_type,
                trigger_source=trigger_source,
                target_server_id=target_server_id,
                context_json={"automation_id": str(automation.id), "automation_name": automation.name},
            )
        )
        await self.workflow_service.mark_queued(workflow.id)
        return workflow

    async def execute_automation_workflow(self, automation_id: UUID, workflow_run_id: UUID) -> None:
        automation = await self._automation(automation_id)
        await self.workflow_service.start_workflow(workflow_run_id)
        status = WorkflowStatus.SUCCESS
        result_summary: dict[str, object] = {"automation_id": str(automation.id), "jobs": []}

        try:
            for index, server_id in enumerate(automation.target_server_ids, start=1):
                step = await self.workflow_service.add_step(
                    workflow_run_id,
                    WorkflowStepCreate(
                        step_order=index,
                        step_type=automation.operation_type.value,
                        name=f"{automation.name} on {server_id}",
                        metadata_json={"target_server_id": server_id},
                    ),
                )
                await self.workflow_service.start_step(step.id)
                try:
                    jobs = await self._execute_operation(automation, UUID(server_id))
                    result_summary["jobs"] = [*result_summary["jobs"], *[str(job.id) for job in jobs]]
                    await self.workflow_service.complete_step(
                        step.id,
                        log_output="\n".join((job.stdout or "").strip() for job in jobs if job.stdout),
                        metadata_json={"job_ids": [str(job.id) for job in jobs]},
                    )
                except Exception as exc:
                    status = WorkflowStatus.FAILED
                    await self.workflow_service.fail_step(step.id, str(exc))
                    raise
            await self.workflow_service.complete_workflow(workflow_run_id, result_summary=result_summary)
        except Exception as exc:
            await self.workflow_service.fail_workflow(workflow_run_id, str(exc), result_summary=result_summary)
        finally:
            automation.last_run_at = datetime.now(UTC)
            automation.last_status = status.value
            await self.repository.session.commit()

    async def _execute_operation(self, automation: Automation, target_server_id: UUID):
        if automation.operation_type == AutomationOperationType.ACTION:
            if self.job_service is None:
                raise AutomationValidationError("Job service is required for action automations")
            job = await self.job_service.execute_action(
                JobActionExecuteRequest(
                    target_server_id=target_server_id,
                    action_id=automation.reference_id or "",
                )
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PACKAGE:
            if self.package_service is None:
                raise AutomationValidationError("Package service is required for package automations")
            job = await self.package_service.execute_definition(
                automation.reference_id or "",
                PackageExecuteRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                ),
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PROFILE:
            if self.profile_service is None:
                raise AutomationValidationError("Profile service is required for profile automations")
            result = await self.profile_service.apply_profile(
                automation.reference_id or "",
                ProfileApplyRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                ),
            )
            return result.jobs

        raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    async def _validate_targets(self, server_ids: list[str]) -> None:
        for server_id in server_ids:
            server = await self.server_repository.get_by_id(UUID(server_id))
            if server is None:
                raise AutomationValidationError(f"Target server not found: {server_id}")
            if not server.managed or server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
                raise AutomationValidationError(f"Target server is not executable: {server.hostname}")

    async def _automation(self, automation_id: UUID) -> Automation:
        automation = await self.repository.get_by_id(automation_id)
        if automation is None:
            raise AutomationNotFoundError("Automation not found")
        return automation

    @staticmethod
    def _validate_supported_operation(operation_type: AutomationOperationType) -> None:
        if operation_type not in {
            AutomationOperationType.ACTION,
            AutomationOperationType.PROFILE,
            AutomationOperationType.PACKAGE,
        }:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    def _to_read(self, automation: Automation, *, workflows=None, servers=None) -> AutomationRead:
        workflows = sorted(workflows or [], key=lambda item: item.created_at, reverse=True)
        servers = servers or []
        target_nodes = []
        for server_id in automation.target_server_ids:
            server = next((item for item in servers if str(item.id) == str(server_id)), None)
            if server:
                target_nodes.append(
                    AutomationTargetRead(
                        id=str(server.id),
                        hostname=server.hostname,
                        node_type=server.node_type.value,
                        environment=server.environment.value,
                        provider=server.provider,
                        source=server.source,
                        tags=server.tags,
                    )
                )
        last_success = next((workflow for workflow in workflows if workflow.status.value == "success"), None)
        last_failure = next((workflow for workflow in workflows if workflow.status.value == "failed"), None)
        recent = workflows[:5]
        last = recent[0] if recent else None
        runtime_state = "disabled" if not automation.enabled else "idle"
        if last and last.status.value in {"queued", "running", "success", "failed", "cancelled", "pending"}:
            runtime_state = "queued" if last.status.value == "pending" else last.status.value

        return AutomationRead.model_validate(automation).model_copy(
            update={
                "runtime_state": runtime_state,
                "last_success_at": last_success.finished_at if last_success else None,
                "last_failure_at": last_failure.finished_at if last_failure else None,
                "last_duration_seconds": last.duration_seconds if last else None,
                "execution_count": len(workflows),
                "target_nodes": target_nodes,
                "recent_executions": recent,
            }
        )

```

## backend/app/modules/profiles/service.py

```python
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from backend.app.common.variables import VariableResolutionError, VariableResolutionService
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.jobs.actions import get_action
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.definitions import get_package_definition
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.definitions import InfrastructureProfile, get_profile, list_profiles
from backend.app.modules.profiles.models import InfrastructureProfileRecord
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.schemas import (
    InfrastructureProfileCreate,
    InfrastructureProfileRead,
    InfrastructureProfileUpdate,
    ProfileApplyRead,
    ProfileBulkApplyRead,
    ProfileBulkApplyRequest,
    ProfileBulkHostResult,
    ProfileApplyRequest,
    ProfileCloneRequest,
)


class ProfileNotFoundError(Exception):
    """Raised when a profile template cannot be found."""


class ProfileStepResolutionError(Exception):
    """Raised when a profile step references an unknown action/package."""


class ProfileConflictError(Exception):
    """Raised when a profile slug already exists."""


class BuiltinProfileError(Exception):
    """Raised when trying to mutate a built-in profile."""


SYSTEM_TEMPLATE_VERSION = "2026.05.16"


class ProfileService:
    """Application service for reusable infrastructure profile orchestration."""

    def __init__(
        self,
        *,
        job_service: JobService,
        repository: InfrastructureProfileRepository | None = None,
        package_repository: PackageDefinitionRepository | None = None,
        deployment_service: DockerComposeDeploymentService | None = None,
    ) -> None:
        self.job_service = job_service
        self.repository = repository
        self.package_repository = package_repository
        self.deployment_service = deployment_service
        self.variable_service = VariableResolutionService()

    async def list_profiles(self) -> list[InfrastructureProfileRead]:
        profiles = [self._builtin_to_read(profile) for profile in list_profiles()]
        if self.repository is None:
            return profiles

        custom_profiles = [self._record_to_read(record) for record in await self.repository.list()]
        custom_ids = {profile.id for profile in custom_profiles}
        return [profile for profile in profiles if profile.id not in custom_ids] + custom_profiles

    async def get_profile(self, profile_id: str) -> InfrastructureProfileRead:
        if self.repository is not None:
            record = await self.repository.get_by_slug(profile_id)
            if record is not None:
                return self._record_to_read(record)

        profile = get_profile(profile_id)
        if profile is None:
            raise ProfileNotFoundError("Profile not found")
        return self._builtin_to_read(profile)

    async def create_profile(self, payload: InfrastructureProfileCreate) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        if get_profile(payload.id) or await self.repository.get_by_slug(payload.id):
            raise ProfileConflictError("Profile already exists")

        record = InfrastructureProfileRecord(
            slug=payload.id,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            tags=payload.tags,
            steps=[self._normalize_step(step.model_dump()) for step in payload.steps],
            variables=[variable.model_dump() for variable in payload.variables],
            is_builtin=False,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise ProfileConflictError("Profile already exists") from exc
        return self._record_to_read(record)

    async def update_profile(
        self,
        profile_id: str,
        payload: InfrastructureProfileUpdate,
    ) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        record = await self.repository.get_by_slug(profile_id)
        builtin = get_profile(profile_id)
        if record is None and builtin is not None:
            record = await self._create_builtin_override(builtin)
        if record is None:
            raise ProfileNotFoundError("Profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if "steps" in update_data and update_data["steps"] is not None:
            update_data["steps"] = [
                self._normalize_step(step.model_dump() if hasattr(step, "model_dump") else step)
                for step in payload.steps or []
            ]
        if "variables" in update_data and update_data["variables"] is not None:
            update_data["variables"] = [
                variable.model_dump() if hasattr(variable, "model_dump") else variable
                for variable in payload.variables or []
            ]

        for key, value in update_data.items():
            setattr(record, key, value)
        record.is_modified = True
        record.modified_at = datetime.now(UTC)

        await self.repository.session.commit()
        await self.repository.session.refresh(record)
        return self._record_to_read(record)

    async def delete_profile(self, profile_id: str) -> None:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")

        if get_profile(profile_id):
            raise BuiltinProfileError("Built-in profiles cannot be deleted")

        record = await self.repository.get_by_slug(profile_id)
        if record is None:
            raise ProfileNotFoundError("Profile not found")

        await self.repository.delete(record)
        await self.repository.session.commit()

    async def clone_profile(self, profile_id: str, payload: ProfileCloneRequest) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        if get_profile(payload.id) or await self.repository.get_by_slug(payload.id):
            raise ProfileConflictError("Profile already exists")
        source = await self.get_profile(profile_id)
        record = InfrastructureProfileRecord(
            slug=payload.id,
            name=payload.name or f"{source.name} Copy",
            category=source.category,
            description=source.description,
            tags=[*source.tags, "cloned"],
            steps=[self._normalize_step(step.model_dump()) for step in source.steps],
            variables=[variable.model_dump() for variable in source.variables],
            is_builtin=False,
            is_modified=False,
            base_version=source.base_version,
            source_template_id=source.id,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise ProfileConflictError("Profile already exists") from exc
        return self._record_to_read(record)

    async def reset_profile(self, profile_id: str) -> InfrastructureProfileRead:
        if self.repository is None:
            raise RuntimeError("Profile repository is required")
        if get_profile(profile_id) is None:
            raise BuiltinProfileError("Only built-in profiles can be reset")
        record = await self.repository.get_by_slug(profile_id)
        if record is not None:
            await self.repository.delete(record)
            await self.repository.session.commit()
        return await self.get_profile(profile_id)

    async def apply_profile(self, profile_id: str, payload: ProfileApplyRequest) -> ProfileApplyRead:
        profile = await self.get_profile(profile_id)

        jobs = []
        status = "success"
        for step in profile.steps:
            if getattr(step, "enabled", True) is False:
                continue
            if step.kind == "deployment":
                if self.deployment_service is None:
                    raise ProfileStepResolutionError("Deployment service is required for deployment profile steps")
                try:
                    deployment_id = UUID(step.reference_id)
                except ValueError as exc:
                    raise ProfileStepResolutionError(
                        f"Deployment step requires a deployment UUID: {step.reference_id}"
                    ) from exc
                deployment_result = await self.deployment_service.deploy_for_target(
                    deployment_id,
                    payload.target_server_id,
                )
                jobs.append(deployment_result.job)
                if deployment_result.job.status == "failed" and payload.stop_on_failure:
                    status = "failed"
                    break
                continue
            credential_ref = getattr(step, "credential_ref", None)
            command, redacted_command = await self._resolve_step_commands(
                step.kind,
                step.reference_id,
                variables=payload.variables,
                credential_refs=payload.credential_refs,
                command=step.command,
                profile_variables=[variable.model_dump() for variable in profile.variables],
            )
            job = await self.job_service.execute(
                JobExecuteRequest(
                    target_server_id=payload.target_server_id,
                    operation_type=f"profile:{profile.id}:{step.id}",
                    command=command,
                    redacted_command=redacted_command,
                    credential_ref=credential_ref,
                )
            )
            jobs.append(job)
            if job.status == "failed" and payload.stop_on_failure:
                status = "failed"
                break

        if any(job.status == "failed" for job in jobs) and status != "failed":
            status = "completed_with_failures"

        return ProfileApplyRead(
            profile_id=profile.id,
            target_server_id=payload.target_server_id,
            status=status,
            jobs=jobs,
            message=f"Profile {profile.name} executed {len(jobs)} step(s).",
        )

    async def apply_profile_bulk(self, payload: ProfileBulkApplyRequest) -> ProfileBulkApplyRead:
        results: list[ProfileBulkHostResult] = []
        for target_server_id in payload.target_server_ids:
            server = await self.job_service.server_repository.get_by_id(target_server_id)
            try:
                result = await self.apply_profile(
                    payload.profile_id,
                    ProfileApplyRequest(
                        target_server_id=target_server_id,
                        stop_on_failure=payload.stop_on_failure,
                        variables=payload.variables,
                        credential_refs=payload.credential_refs,
                    ),
                )
                results.append(
                    ProfileBulkHostResult(
                        target_server_id=target_server_id,
                        target_hostname=result.jobs[0].target_hostname if result.jobs else None,
                        success=result.status == "success",
                        result=result,
                        error=None if result.status == "success" else result.status,
                    )
                )
            except Exception as exc:
                results.append(
                    ProfileBulkHostResult(
                        target_server_id=target_server_id,
                        target_hostname=server.hostname if server else None,
                        success=False,
                        error=str(exc),
                    )
                )

        success_count = sum(1 for result in results if result.success)
        return ProfileBulkApplyRead(
            profile_id=payload.profile_id,
            success_count=success_count,
            failure_count=len(results) - success_count,
            results=results,
        )

    async def _resolve_step_command(
        self,
        kind: str,
        reference_id: str,
        *,
        variables: dict[str, str],
        profile_variables: list[dict],
        command: str | None = None,
    ) -> str:
        if kind == "command":
            return self.variable_service.resolve_text(
                command or "",
                definitions=profile_variables,
                variables=variables,
            )

        if kind in {"deployment", "script"}:
            raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

        if kind == "action":
            action = get_action(reference_id)
            if action is None and self.job_service.action_repository is not None:
                action = await self.job_service.action_repository.get_by_slug(reference_id)
            if action is None:
                raise ProfileStepResolutionError(f"Unknown action reference: {reference_id}")
            return self.variable_service.resolve_text(
                action.command,
                definitions=profile_variables,
                variables=variables,
            )

        if kind == "package":
            package_read = None
            if self.package_repository is not None:
                package_service = PackageAutomationService(repository=self.package_repository)
                try:
                    package_read = await package_service.get_definition(reference_id)
                except Exception:
                    package_read = None
            if package_read is None:
                package = get_package_definition(reference_id)
                if package is None:
                    raise ProfileStepResolutionError(f"Unknown package reference: {reference_id}")
                definitions = [*profile_variables, *package.variables]
                install = self.variable_service.resolve_text(package.install_command, definitions=definitions, variables=variables)
                validation = self.variable_service.resolve_text(package.validation_command, definitions=definitions, variables=variables)
                return f"{install} && {validation}"
            definitions = [*profile_variables, *[variable.model_dump() for variable in package_read.variables]]
            install = self.variable_service.resolve_text(package_read.install_command, definitions=definitions, variables=variables)
            validation = self.variable_service.resolve_text(package_read.validation_command, definitions=definitions, variables=variables)
            return f"{install} && {validation}"

        raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

    async def _resolve_step_commands(
        self,
        kind: str,
        reference_id: str,
        *,
        variables: dict[str, str],
        credential_refs: dict[str, str],
        profile_variables: list[dict],
        command: str | None = None,
    ) -> tuple[str, str]:
        if kind == "command":
            return await self._resolve_text_pair(command or "", profile_variables, variables, credential_refs)

        if kind == "action":
            action = get_action(reference_id)
            if action is None and self.job_service.action_repository is not None:
                action = await self.job_service.action_repository.get_by_slug(reference_id)
            if action is None:
                raise ProfileStepResolutionError(f"Unknown action reference: {reference_id}")
            return await self._resolve_text_pair(action.command, profile_variables, variables, credential_refs)

        if kind == "package":
            package_read = None
            if self.package_repository is not None:
                package_service = PackageAutomationService(
                    repository=self.package_repository,
                    credential_service=self.job_service.credential_service,
                )
                try:
                    package_read = await package_service.get_definition(reference_id)
                except Exception:
                    package_read = None
            if package_read is None:
                package = get_package_definition(reference_id)
                if package is None:
                    raise ProfileStepResolutionError(f"Unknown package reference: {reference_id}")
                definitions = [*profile_variables, *package.variables]
                install, redacted_install = await self._resolve_text_pair(
                    package.install_command,
                    definitions,
                    variables,
                    credential_refs,
                )
                validation, redacted_validation = await self._resolve_text_pair(
                    package.validation_command,
                    definitions,
                    variables,
                    credential_refs,
                )
                return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

            definitions = [*profile_variables, *[variable.model_dump() for variable in package_read.variables]]
            install, redacted_install = await self._resolve_text_pair(
                package_read.install_command,
                definitions,
                variables,
                credential_refs,
            )
            validation, redacted_validation = await self._resolve_text_pair(
                package_read.validation_command,
                definitions,
                variables,
                credential_refs,
            )
            return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

        raise ProfileStepResolutionError(f"Unsupported profile step kind: {kind}")

    async def _resolve_text_pair(
        self,
        text: str,
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> tuple[str, str]:
        secret_values = await self._resolve_secret_variables(definitions, credential_refs)
        safe_variables = self._without_sensitive_plaintext(definitions, variables, credential_refs)
        runtime_variables = {**safe_variables, **secret_values}
        redacted_variables = {**safe_variables, **{name: "********" for name in secret_values}}
        return (
            self.variable_service.resolve_text(text, definitions=definitions, variables=runtime_variables),
            self.variable_service.resolve_text(text, definitions=definitions, variables=redacted_variables),
        )

    async def _resolve_secret_variables(
        self,
        definitions: list[dict],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        secret_values: dict[str, str] = {}
        sensitive_names = [str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")]
        for name in sensitive_names:
            credential_ref = credential_refs.get(name)
            if not credential_ref:
                definition = next(item for item in definitions if item.get("name") == name)
                if definition.get("required"):
                    raise VariableResolutionError(f"Sensitive variable {name} requires a credential reference")
                continue
            if self.job_service.credential_service is None:
                raise VariableResolutionError("Credential service is required for sensitive profile variables")
            credential = await self.job_service.credential_service.resolve_credential(credential_ref)
            secret = credential.secret or credential.private_key
            if not secret:
                raise VariableResolutionError(f"Credential reference for {name} has no usable secret value")
            secret_values[name] = secret
        return secret_values

    @staticmethod
    def _without_sensitive_plaintext(
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        sensitive_names = {str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")}
        unsafe = sorted(name for name in sensitive_names if variables.get(name) and not credential_refs.get(name))
        if unsafe:
            raise VariableResolutionError(
                "Sensitive variable(s) must use credential references: " + ", ".join(unsafe)
            )
        return {name: value for name, value in variables.items() if name not in sensitive_names}

    @staticmethod
    def _builtin_to_read(profile: InfrastructureProfile) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=profile.id,
            name=profile.name,
            category=profile.category,
            description=profile.description,
            tags=profile.tags,
            steps=[ProfileService._normalize_step(step.__dict__) for step in profile.steps],
            variables=profile.variables,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
        )

    @staticmethod
    def _record_to_read(record: InfrastructureProfileRecord) -> InfrastructureProfileRead:
        return InfrastructureProfileRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            description=record.description,
            tags=record.tags,
            steps=[ProfileService._normalize_step(step) for step in record.steps],
            variables=record.variables,
            is_builtin=record.is_builtin,
            is_modified=record.is_modified,
            base_version=record.base_version,
            source_template_id=record.source_template_id,
            modified_at=record.modified_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _create_builtin_override(self, profile: InfrastructureProfile) -> InfrastructureProfileRecord:
        assert self.repository is not None
        record = InfrastructureProfileRecord(
            slug=profile.id,
            name=profile.name,
            category=profile.category,
            description=profile.description,
            tags=profile.tags,
            steps=[ProfileService._normalize_step(step.__dict__) for step in profile.steps],
            variables=profile.variables,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
            source_template_id=profile.id,
        )
        record = await self.repository.create(record)
        await self.repository.session.flush()
        return record

    @staticmethod
    def _normalize_step(step: dict) -> dict:
        kind = step.get("kind") or ("command" if step.get("type") == "script" else step.get("type"))
        reference_id = step.get("reference_id") or step.get("target") or step.get("id") or ""
        step_type = "script" if kind == "command" else kind
        return {
            **step,
            "id": step.get("id") or f"{kind}-{reference_id}",
            "name": step.get("name") or reference_id,
            "kind": kind,
            "reference_id": reference_id,
            "type": step.get("type") or step_type,
            "target": step.get("target") or reference_id,
            "enabled": step.get("enabled", True),
            "credential_ref": step.get("credential_ref"),
        }

```

## backend/app/modules/packages/service.py

```python
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from backend.app.common.variables import VariableResolutionError, VariableResolutionService
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.jobs.schemas import BulkExecutionRead, JobBulkExecuteRequest, JobExecuteRequest, JobRead
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.definitions import (
    PackageDefinition,
    get_package_definition,
    list_package_definitions,
)
from backend.app.modules.packages.models import PackageDefinitionRecord
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.schemas import (
    PackageDefinitionCreate,
    PackageDefinitionRead,
    PackageDefinitionUpdate,
    PackageBulkApplyRequest,
    PackageCloneRequest,
    PackageExecuteRequest,
)


class PackageDefinitionNotFoundError(Exception):
    """Raised when a package definition cannot be found."""


class PackageDefinitionConflictError(Exception):
    """Raised when a package definition slug already exists."""


class BuiltinPackageDefinitionError(Exception):
    """Raised when trying to mutate a built-in package definition."""


SYSTEM_TEMPLATE_VERSION = "2026.05.16"


class PackageAutomationService:
    """Application service for reusable package definitions."""

    def __init__(
        self,
        *,
        repository: PackageDefinitionRepository | None = None,
        job_service: JobService | None = None,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.repository = repository
        self.job_service = job_service
        self.credential_service = credential_service
        self.variable_service = VariableResolutionService()

    async def list_definitions(self) -> list[PackageDefinitionRead]:
        definitions = [self._builtin_to_read(definition) for definition in list_package_definitions()]
        if self.repository is None:
            return definitions

        custom_definitions = [self._record_to_read(record) for record in await self.repository.list()]
        custom_ids = {definition.id for definition in custom_definitions}
        return [definition for definition in definitions if definition.id not in custom_ids] + custom_definitions

    async def get_definition(self, package_id: str) -> PackageDefinitionRead:
        if self.repository is not None:
            record = await self.repository.get_by_slug(package_id)
            if record is not None:
                return self._record_to_read(record)

        definition = get_package_definition(package_id)
        if definition is None:
            raise PackageDefinitionNotFoundError("Package definition not found")
        return self._builtin_to_read(definition)

    async def create_definition(self, payload: PackageDefinitionCreate) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id):
            raise PackageDefinitionConflictError("Package definition already exists")

        record = PackageDefinitionRecord(
            slug=payload.id,
            name=payload.name,
            category=payload.category,
            supported_os=payload.supported_os,
            install_command=payload.install_command,
            uninstall_command=payload.uninstall_command,
            validation_command=payload.validation_command,
            variables=[variable.model_dump() for variable in payload.variables],
            tags=payload.tags,
            description=payload.description,
            is_builtin=False,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise PackageDefinitionConflictError("Package definition already exists") from exc
        return self._record_to_read(record)

    async def update_definition(
        self,
        package_id: str,
        payload: PackageDefinitionUpdate,
    ) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        record = await self.repository.get_by_slug(package_id)
        builtin = get_package_definition(package_id)
        if record is None and builtin is not None:
            record = await self._create_builtin_override(builtin)
        if record is None:
            raise PackageDefinitionNotFoundError("Package definition not found")

        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "variables" and value is not None:
                value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
            setattr(record, key, value)
        record.is_modified = True
        record.modified_at = datetime.now(UTC)

        await self.repository.session.commit()
        await self.repository.session.refresh(record)
        return self._record_to_read(record)

    async def delete_definition(self, package_id: str) -> None:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")

        if get_package_definition(package_id):
            raise BuiltinPackageDefinitionError("Built-in package definitions cannot be deleted")

        record = await self.repository.get_by_slug(package_id)
        if record is None:
            raise PackageDefinitionNotFoundError("Package definition not found")

        await self.repository.delete(record)
        await self.repository.session.commit()

    async def clone_definition(self, package_id: str, payload: PackageCloneRequest) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")
        if get_package_definition(payload.id) or await self.repository.get_by_slug(payload.id):
            raise PackageDefinitionConflictError("Package definition already exists")

        source = await self.get_definition(package_id)
        record = PackageDefinitionRecord(
            slug=payload.id,
            name=payload.name or f"{source.name} Copy",
            category=source.category,
            supported_os=source.supported_os,
            install_command=source.install_command,
            uninstall_command=source.uninstall_command,
            validation_command=source.validation_command,
            variables=[variable.model_dump() for variable in source.variables],
            tags=[*source.tags, "cloned"],
            description=source.description,
            is_builtin=False,
            is_modified=False,
            base_version=source.base_version,
            source_template_id=source.id,
        )
        try:
            record = await self.repository.create(record)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise PackageDefinitionConflictError("Package definition already exists") from exc
        return self._record_to_read(record)

    async def reset_definition(self, package_id: str) -> PackageDefinitionRead:
        if self.repository is None:
            raise RuntimeError("Package definition repository is required")
        if get_package_definition(package_id) is None:
            raise BuiltinPackageDefinitionError("Only built-in package definitions can be reset")
        record = await self.repository.get_by_slug(package_id)
        if record is not None:
            await self.repository.delete(record)
            await self.repository.session.commit()
        return await self.get_definition(package_id)

    async def execute_definition(self, package_id: str, payload: PackageExecuteRequest) -> JobRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(package_id)
        command, redacted_command = await self._resolve_definition_commands(
            definition,
            payload.variables,
            payload.credential_refs,
        )
        return await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=payload.target_server_id,
                operation_type=f"package:{definition.id}",
                command=command,
                redacted_command=redacted_command,
            )
        )

    async def execute_definition_bulk(self, payload: PackageBulkApplyRequest) -> BulkExecutionRead:
        if self.job_service is None:
            raise RuntimeError("Job service is required")

        definition = await self.get_definition(payload.package_id)
        command, redacted_command = await self._resolve_definition_commands(
            definition,
            payload.variables,
            payload.credential_refs,
        )
        return await self.job_service.execute_bulk(
            JobBulkExecuteRequest(
                target_server_ids=payload.target_server_ids,
                operation_type=f"package:{definition.id}",
                command=command,
                redacted_command=redacted_command,
            )
        )

    @staticmethod
    def _builtin_to_read(definition: PackageDefinition) -> PackageDefinitionRead:
        return PackageDefinitionRead(
            **definition.__dict__,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
        )

    @staticmethod
    def _record_to_read(record: PackageDefinitionRecord) -> PackageDefinitionRead:
        return PackageDefinitionRead(
            id=record.slug,
            name=record.name,
            category=record.category,
            supported_os=record.supported_os,
            install_command=record.install_command,
            uninstall_command=record.uninstall_command,
            validation_command=record.validation_command,
            variables=record.variables,
            tags=record.tags,
            description=record.description,
            is_builtin=record.is_builtin,
            is_modified=record.is_modified,
            base_version=record.base_version,
            source_template_id=record.source_template_id,
            modified_at=record.modified_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _create_builtin_override(self, definition: PackageDefinition) -> PackageDefinitionRecord:
        assert self.repository is not None
        record = PackageDefinitionRecord(
            slug=definition.id,
            name=definition.name,
            category=definition.category,
            supported_os=definition.supported_os,
            install_command=definition.install_command,
            uninstall_command=definition.uninstall_command,
            validation_command=definition.validation_command,
            variables=definition.variables,
            tags=definition.tags,
            description=definition.description,
            is_builtin=True,
            is_modified=False,
            base_version=SYSTEM_TEMPLATE_VERSION,
            source_template_id=definition.id,
        )
        record = await self.repository.create(record)
        await self.repository.session.flush()
        return record

    def _resolve_definition_command(
        self,
        definition: PackageDefinitionRead,
        variables: dict[str, str],
    ) -> str:
        try:
            install = self.variable_service.resolve_text(
                definition.install_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
            )
            validation = self.variable_service.resolve_text(
                definition.validation_command,
                definitions=[variable.model_dump() for variable in definition.variables],
                variables=variables,
            )
        except VariableResolutionError:
            raise
        return f"{install} && {validation}"

    async def _resolve_definition_commands(
        self,
        definition: PackageDefinitionRead,
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> tuple[str, str]:
        definitions = [variable.model_dump() for variable in definition.variables]
        secret_values = await self._resolve_secret_variables(definitions, credential_refs)
        safe_variables = self._without_sensitive_plaintext(definitions, variables, credential_refs)
        runtime_variables = {**safe_variables, **secret_values}
        redacted_variables = {**safe_variables, **{name: "********" for name in secret_values}}

        install = self.variable_service.resolve_text(
            definition.install_command,
            definitions=definitions,
            variables=runtime_variables,
        )
        validation = self.variable_service.resolve_text(
            definition.validation_command,
            definitions=definitions,
            variables=runtime_variables,
        )
        redacted_install = self.variable_service.resolve_text(
            definition.install_command,
            definitions=definitions,
            variables=redacted_variables,
        )
        redacted_validation = self.variable_service.resolve_text(
            definition.validation_command,
            definitions=definitions,
            variables=redacted_variables,
        )
        return f"{install} && {validation}", f"{redacted_install} && {redacted_validation}"

    async def _resolve_secret_variables(
        self,
        definitions: list[dict],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        secret_values: dict[str, str] = {}
        sensitive_names = [str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")]
        for name in sensitive_names:
            credential_ref = credential_refs.get(name)
            if not credential_ref:
                definition = next(item for item in definitions if item.get("name") == name)
                if definition.get("required"):
                    raise VariableResolutionError(f"Sensitive variable {name} requires a credential reference")
                continue
            if self.credential_service is None:
                raise VariableResolutionError("Credential service is required for sensitive package variables")
            credential = await self.credential_service.resolve_credential(credential_ref)
            secret = credential.secret or credential.private_key
            if not secret:
                raise VariableResolutionError(f"Credential reference for {name} has no usable secret value")
            secret_values[name] = secret
        return secret_values

    @staticmethod
    def _without_sensitive_plaintext(
        definitions: list[dict],
        variables: dict[str, str],
        credential_refs: dict[str, str],
    ) -> dict[str, str]:
        sensitive_names = {str(item["name"]) for item in definitions if item.get("name") and item.get("sensitive")}
        unsafe = sorted(name for name in sensitive_names if variables.get(name) and not credential_refs.get(name))
        if unsafe:
            raise VariableResolutionError(
                "Sensitive variable(s) must use credential references: " + ", ".join(unsafe)
            )
        return {name: value for name, value in variables.items() if name not in sensitive_names}

```

