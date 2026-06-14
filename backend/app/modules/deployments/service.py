from datetime import UTC, datetime
import re
from hashlib import sha256
from uuid import UUID

import structlog

from backend.app.common.constants import InventoryHealthStatus
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
    DeploymentContainerRead,
    DeploymentComposeValidationRead,
    DeploymentCreate,
    DeploymentDryRunRead,
    DeploymentDryRunTargetRead,
    DeploymentLogsRead,
    DeploymentExecutionRead,
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentRevisionRead,
    DeploymentRuntimeStateRead,
    DeploymentStatusRead,
    DeploymentTargetExecutionRead,
    DeploymentTargetRead,
    DeploymentUpdate,
)
from backend.app.modules.deployments.runtime import (
    ComposeValidationResult,
    DeploymentRuntimeInspector,
    DeploymentRuntimeState,
    expected_compose_services,
    validate_compose_content,
)
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.schemas import JobExecuteRequest, JobRead
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError
from backend.app.modules.orchestration.activity import deployment_execution_activity_timeline
from backend.app.modules.orchestration.security import CommandValidationError, SecretSanitizer
from backend.app.modules.orchestration.semantics import (
    deployment_execution_failure_states,
    deployment_execution_success_states,
)
from backend.app.modules.orchestration.transitions import validate_deployment_transition
from backend.app.modules.orchestration.utils import (
    aggregate_target_executions,
    duration_seconds,
    rollup_status,
)

logger = structlog.get_logger(__name__)
RUNTIME_STALE_AFTER_SECONDS = 120


class DeploymentNotFoundError(Exception):
    """Raised when a deployment cannot be found."""


class DeploymentValidationError(Exception):
    """Raised when a deployment request is invalid."""


class DeploymentStatusRollupService:
    """Centralizes deployment and target status aggregation."""

    @staticmethod
    def transition(current: DeploymentStatus, next_status: DeploymentStatus) -> DeploymentStatus:
        validate_deployment_transition(current, next_status)
        return next_status

    @staticmethod
    def rollup(statuses: list[DeploymentStatus], operation: str) -> DeploymentStatus:
        if operation == "runtime":
            if not statuses:
                return DeploymentStatus.FAILED
            if all(status == DeploymentStatus.RUNNING for status in statuses):
                return DeploymentStatus.RUNNING
            if all(status == DeploymentStatus.STOPPED for status in statuses):
                return DeploymentStatus.STOPPED
            if all(status == DeploymentStatus.FAILED for status in statuses):
                return DeploymentStatus.FAILED
            return DeploymentStatus.DEGRADED
        success_states = {DeploymentStatus.RUNNING, DeploymentStatus.SUCCESS}
        if operation == "stop":
            success_states = {DeploymentStatus.STOPPED}
        return rollup_status(
            statuses,
            success_states=success_states,
            failure_states={DeploymentStatus.FAILED},
            empty_status=DeploymentStatus.FAILED,
            all_success_status=DeploymentStatus.STOPPED if operation == "stop" else DeploymentStatus.RUNNING,
            partial_success_status=DeploymentStatus.PARTIAL_SUCCESS,
            all_failed_status=DeploymentStatus.FAILED,
            mixed_status=DeploymentStatus.DEGRADED,
        )


class DeploymentExecutionCoordinator:
    """Lightweight execution ownership marker for deployment runs."""

    @staticmethod
    def mark_owned(execution: DeploymentExecution) -> None:
        # TODO: replace this local marker with distributed leases before multi-worker execution.
        execution.result_summary = {
            **(execution.result_summary or {}),
            "execution_owner": "local-process",
            "lease_strategy": "in-process",
        }


class DeploymentRuntimeReconciler:
    """Queries live Docker Compose state and reconciles deployment runtime status."""

    def __init__(self, deployment_service: "DockerComposeDeploymentService") -> None:
        self.deployment_service = deployment_service

    async def reconcile(
        self,
        deployment: Deployment,
        targets: list[DeploymentTarget],
    ) -> dict[UUID, DeploymentRuntimeState]:
        # TODO: call this from a scheduled reconciliation loop once queue leases exist.
        states: dict[UUID, DeploymentRuntimeState] = {}
        for target in targets:
            states[target.id] = await self.reconcile_target(deployment, target)
        if states:
            deployment.status = self.deployment_service.status_rollup.rollup(
                [state.status for state in states.values()],
                "runtime",
            )
            await self.deployment_service.repository.session.commit()
            logger.info(
                "deployment_runtime_reconciled",
                deployment_id=str(deployment.id),
                target_count=len(states),
                status=deployment.status.value,
            )
        return states

    async def reconcile_target(
        self,
        deployment: Deployment,
        target: DeploymentTarget,
    ) -> DeploymentRuntimeState:
        desired_running = deployment.status not in {
            DeploymentStatus.DRAFT,
            DeploymentStatus.STOPPED,
            DeploymentStatus.CANCELLED,
        }
        expected_services = expected_compose_services(deployment.compose_content)
        command = self.deployment_service._runtime_inspection_command(target, deployment)
        server = await self.deployment_service.server_repository.get_by_id(target.server_id)
        if server is not None and server.last_health_status == InventoryHealthStatus.UNREACHABLE:
            state = DeploymentRuntimeState(
                target_server_id=target.server_id,
                status=DeploymentStatus.DEGRADED if desired_running else DeploymentStatus.STOPPED,
                runtime_state="unreachable",
                sync_status="unknown",
                health_state="unreachable",
                missing_services=sorted(expected_services),
                error=server.last_health_error or "Target host is unreachable",
            )
            self.deployment_service._persist_runtime_state(target, state)
            logger.warning(
                "deployment_runtime_target_unreachable",
                deployment_id=str(deployment.id),
                target_id=str(target.id),
                server_id=str(target.server_id),
                hostname=getattr(server, "hostname", None),
            )
            return state
        try:
            job = await self.deployment_service.job_service.execute(
                JobExecuteRequest(
                    target_server_id=target.server_id,
                    operation_type=f"deployment:{deployment.id}:runtime-refresh",
                    command=command,
                    credential_ref=deployment.execution_credential_ref,
                )
            )
            if job.exit_code != 0:
                state = DeploymentRuntimeInspector.failed(
                    target_server_id=target.server_id,
                    error=job.stderr or "Runtime inspection failed",
                    expected_services=expected_services,
                    desired_running=desired_running,
                )
            else:
                state = DeploymentRuntimeInspector.parse(
                    target_server_id=target.server_id,
                    stdout=job.stdout or "",
                    expected_services=expected_services,
                    desired_running=desired_running,
                )
        except (CommandValidationError, JobTargetNotFoundError, JobTargetNotManagedError) as exc:
            state = DeploymentRuntimeInspector.failed(
                target_server_id=target.server_id,
                error=str(exc),
                expected_services=expected_services,
                desired_running=desired_running,
            )
        self.deployment_service._persist_runtime_state(target, state)
        return state


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
        self.status_rollup = DeploymentStatusRollupService()
        self.execution_coordinator = DeploymentExecutionCoordinator()
        self.secret_sanitizer = SecretSanitizer()
        self.runtime_reconciler = DeploymentRuntimeReconciler(self)

    async def list_deployments(self, *, server_id: UUID | None = None) -> list[DeploymentRead]:
        deployments = (
            await self.repository.list_for_server(server_id)
            if server_id is not None
            else await self.repository.list()
        )
        return [await self._to_read(deployment) for deployment in deployments]

    async def create_deployment(self, payload: DeploymentCreate) -> DeploymentRead:
        self._validate_compose_or_raise(payload.compose_content)
        await self._validate_execution_credential_ref(payload.execution_credential_ref)
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
                execution_credential_ref=payload.execution_credential_ref,
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
        self._validate_compose_or_raise(payload.compose_content)
        await self._validate_execution_credential_ref(payload.execution_credential_ref)

        target_ids = payload.target_server_ids or ([payload.target_server_id] if payload.target_server_id else [])
        if not target_ids:
            raise DeploymentValidationError("Select at least one deployment target")
        servers = [await self._managed_server(target_id) for target_id in target_ids]

        deployment.name = payload.name
        deployment.description = payload.description
        deployment.compose_content = payload.compose_content
        deployment.env_content = payload.env_content
        deployment.credential_refs = payload.credential_refs
        deployment.execution_credential_ref = payload.execution_credential_ref
        deployment.status = DeploymentStatus.DRAFT
        await self._sync_deployment_targets(deployment, [server.id for server in servers], payload.remote_path)

        await self.repository.session.commit()
        await self.repository.session.refresh(deployment)
        return await self._to_read(deployment)

    async def deploy(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "deploy")

    async def dry_run(self, deployment_id: UUID, operation: str = "deploy") -> DeploymentDryRunRead:
        deployment, targets = await self._deployment_and_targets(deployment_id)
        return await self._dry_run_for(deployment, targets, operation)

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
        runtime_states = await self.runtime_reconciler.reconcile(deployment, targets)
        jobs = []
        for target in targets:
            command = self._compose_command(target, deployment, "ps")
            jobs.append(
                await self.job_service.execute(
                    JobExecuteRequest(
                        target_server_id=target.server_id,
                        operation_type=f"deployment:{deployment.id}:status",
                        command=command,
                        credential_ref=deployment.execution_credential_ref,
                    )
                )
            )
        return DeploymentStatusRead(
            deployment_id=deployment.id,
            target_server_id=targets[0].server_id if targets else None,
            job=jobs[0] if jobs else None,
            jobs=jobs,
            runtime_states=[self._runtime_state_to_read(item) for item in runtime_states.values()],
        )

    async def refresh_runtime(self, deployment_id: UUID) -> DeploymentRead:
        deployment, targets = await self._deployment_and_targets(deployment_id)
        runtime_states = await self.runtime_reconciler.reconcile(deployment, targets)
        return await self._to_read(deployment, runtime_states=runtime_states)

    async def validate_payload(self, payload: DeploymentCreate, operation: str = "deploy") -> DeploymentDryRunRead:
        await self._validate_execution_credential_ref(payload.execution_credential_ref)
        target_ids = payload.target_server_ids or ([payload.target_server_id] if payload.target_server_id else [])
        servers = [await self._managed_server(target_id) for target_id in target_ids]
        validation = validate_compose_content(payload.compose_content)
        targets = []
        synthetic_deployment = Deployment(
            name=payload.name,
            description=payload.description,
            compose_content=payload.compose_content,
            env_content=payload.env_content,
            credential_refs=payload.credential_refs,
            execution_credential_ref=payload.execution_credential_ref,
            status=DeploymentStatus.DRAFT,
        )
        for server in servers:
            synthetic_target = DeploymentTarget(
                deployment_id=UUID(int=0),
                server_id=server.id,
                remote_path=payload.remote_path,
                status=DeploymentStatus.DRAFT,
            )
            targets.append(await self._dry_run_target(synthetic_deployment, synthetic_target, server, operation))
        return DeploymentDryRunRead(
            operation=operation,
            validation=self._compose_validation_to_read(validation),
            targets=targets,
            env_keys=self._env_keys(payload.env_content),
            credential_env_keys=sorted(payload.credential_refs),
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
                    credential_ref=deployment.execution_credential_ref,
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
        deployment, targets, execution = await self._prepare_execution(
            deployment_id,
            operation,
            target_server_ids=target_server_ids,
        )
        if operation in {"deploy", "redeploy"}:
            self._validate_compose_or_raise(deployment.compose_content)

        jobs: list[JobRead] = []
        revisions: list[DeploymentRevision] = []
        target_executions: list[DeploymentTargetExecution] = []
        for target in targets:
            job, revision, target_execution = await self._execute_target_operation(
                deployment,
                execution,
                target,
                operation,
            )
            if job is not None:
                jobs.append(job)
            revisions.append(revision)
            target_executions.append(target_execution)

        return await self._finalize_execution(
            deployment,
            execution,
            targets,
            operation,
            jobs=jobs,
            revisions=revisions,
            target_executions=target_executions,
        )

    async def _prepare_execution(
        self,
        deployment_id: UUID,
        operation: str,
        *,
        target_server_ids: set[UUID] | None = None,
    ) -> tuple[Deployment, list[DeploymentTarget], DeploymentExecution]:
        deployment, all_targets = await self._deployment_and_targets(deployment_id)
        targets = [
            target
            for target in all_targets
            if target_server_ids is None or target.server_id in target_server_ids
        ]
        if not targets:
            raise DeploymentValidationError("Deployment has no matching target hosts")
        for target in targets:
            await self._managed_server(target.server_id)
        deployment.status = self.status_rollup.transition(deployment.status, DeploymentStatus.DEPLOYING)
        for target in targets:
            target.status = self.status_rollup.transition(target.status, DeploymentStatus.DEPLOYING)
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
        self.execution_coordinator.mark_owned(execution)
        await self.repository.session.commit()
        return deployment, targets, execution

    async def _execute_target_operation(
        self,
        deployment: Deployment,
        execution: DeploymentExecution,
        target: DeploymentTarget,
        operation: str,
    ) -> tuple[JobRead | None, DeploymentRevision, DeploymentTargetExecution]:
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
                env_content=self.secret_sanitizer.redact_text(deployment.env_content),
                status=DeploymentStatus.DEPLOYING,
            )
        )
        await self.repository.session.commit()

        job: JobRead | None = None
        try:
            command, redacted_command = await self._operation_commands(deployment, target, operation)
            job = await self.job_service.execute(
                JobExecuteRequest(
                    target_server_id=target.server_id,
                    operation_type=f"deployment:{deployment.id}:{operation}",
                    command=command,
                    redacted_command=redacted_command,
                    credential_ref=deployment.execution_credential_ref,
                )
            )
            next_status = (
                DeploymentStatus.RUNNING
                if job.exit_code == 0 and operation != "stop"
                else DeploymentStatus.FAILED
            )
            if job.exit_code == 0 and operation == "stop":
                next_status = DeploymentStatus.STOPPED

            target.status = self.status_rollup.transition(target.status, next_status)
            target.last_job_id = job.id
            revision.status = self.status_rollup.transition(revision.status, next_status)
            revision.job_id = job.id
            revision.stdout = self.secret_sanitizer.redact_text(job.stdout)
            revision.stderr = self.secret_sanitizer.redact_text(job.stderr)
            target_execution.status = self.status_rollup.transition(target_execution.status, next_status)
            target_execution.job_id = job.id
            target_execution.revision_id = revision.id
            target_execution.stdout = self.secret_sanitizer.redact_text(job.stdout)
            target_execution.stderr = self.secret_sanitizer.redact_text(job.stderr)
            target_execution.finished_at = datetime.now(UTC)
        except (CommandValidationError, DeploymentValidationError, JobTargetNotFoundError, JobTargetNotManagedError) as exc:
            safe_error = self.secret_sanitizer.redact_text(str(exc)) or "Deployment target execution failed"
            target.status = self.status_rollup.transition(target.status, DeploymentStatus.FAILED)
            revision.status = self.status_rollup.transition(revision.status, DeploymentStatus.FAILED)
            revision.stderr = safe_error
            target_execution.status = self.status_rollup.transition(target_execution.status, DeploymentStatus.FAILED)
            target_execution.error_message = safe_error
            target_execution.finished_at = datetime.now(UTC)
        await self.repository.session.commit()
        return job, revision, target_execution

    async def _finalize_execution(
        self,
        deployment: Deployment,
        execution: DeploymentExecution,
        targets: list[DeploymentTarget],
        operation: str,
        *,
        jobs: list[JobRead],
        revisions: list[DeploymentRevision],
        target_executions: list[DeploymentTargetExecution],
    ) -> DeploymentOperationRead:
        deployment.status = self.status_rollup.rollup([target.status for target in targets], operation)
        execution.status = self.status_rollup.transition(execution.status, deployment.status)
        execution.finished_at = datetime.now(UTC)
        target_aggregate = aggregate_target_executions(
            target_executions,
            success_states=deployment_execution_success_states(),
            failure_states=deployment_execution_failure_states(),
        )
        execution.result_summary = target_aggregate.summary.as_result_summary()
        execution.error_message = self.secret_sanitizer.redact_text(
            "\n".join(target_aggregate.summary.failure_messages)
            if target_aggregate.summary.failure_messages
            else None
        )
        await self.repository.session.commit()
        for revision in revisions:
            await self.repository.session.refresh(revision)
        await self.repository.session.refresh(execution)
        return DeploymentOperationRead(
            deployment=await self._to_read(deployment, refresh_runtime=True),
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

    async def _to_read(
        self,
        deployment: Deployment,
        *,
        refresh_runtime: bool = False,
        runtime_states: dict[UUID, DeploymentRuntimeState] | None = None,
    ) -> DeploymentRead:
        targets = await self.target_repository.list_for_deployment(deployment.id)
        if refresh_runtime and targets and deployment.status != DeploymentStatus.DRAFT:
            runtime_states = await self.runtime_reconciler.reconcile(deployment, targets)
        runtime_states = runtime_states or {}
        target_reads = [await self._target_to_read(target, runtime_state=runtime_states.get(target.id)) for target in targets]
        executions = [await self._execution_to_read(item) for item in await self.execution_repository.list_for_deployment(deployment.id)]
        first_target = targets[0] if targets else None
        first_server = await self.server_repository.get_by_id(first_target.server_id) if first_target else None
        runtime_state = self._aggregate_runtime_state([target.runtime_state for target in target_reads])
        health_state = self._aggregate_health_state([target.health_state for target in target_reads], deployment.status)
        sync_status = "drifted" if any(target.sync_status == "drifted" for target in target_reads) else self._sync_status(deployment, first_target)
        runtime_checked_at = max(
            [target.runtime_checked_at for target in target_reads if target.runtime_checked_at],
            default=None,
        )
        runtime_age_seconds = self._age_seconds(runtime_checked_at)
        runtime_failure_reason = self._deployment_failure_reason(target_reads)
        return DeploymentRead(
            id=deployment.id,
            name=deployment.name,
            description=deployment.description,
            compose_content=deployment.compose_content,
            env_content=deployment.env_content,
            credential_refs=deployment.credential_refs,
            execution_credential_ref=deployment.execution_credential_ref,
            status=deployment.status,
            execution_status=executions[0].status if executions else None,
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
            runtime_state=runtime_state,
            health_state=health_state,
            sync_status=sync_status,
            runtime_checked_at=runtime_checked_at,
            runtime_error="; ".join(target.runtime_error for target in target_reads if target.runtime_error) or None,
            runtime_stale=self._is_runtime_stale(runtime_checked_at),
            runtime_age_seconds=runtime_age_seconds,
            runtime_failure_reason=runtime_failure_reason,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
        )

    async def _target_to_read(
        self,
        target: DeploymentTarget,
        *,
        runtime_state: DeploymentRuntimeState | None = None,
    ) -> DeploymentTargetRead:
        server = await self.server_repository.get_by_id(target.server_id)
        executions = await self.target_execution_repository.list_for_deployment(target.deployment_id)
        last_execution = next((item for item in executions if item.target_id == target.id), None)
        checked_at = runtime_state.inspected_at if runtime_state else target.runtime_checked_at
        containers = [
            DeploymentContainerRead(
                service=container.service,
                name=container.name,
                state=container.state,
                health=container.health,
                uptime_seconds=container.uptime_seconds,
                restart_count=container.restart_count,
            )
            for container in (runtime_state.containers if runtime_state else [])
        ] if runtime_state else [
            DeploymentContainerRead.model_validate(container)
            for container in (target.runtime_containers or [])
        ]
        missing_services = runtime_state.missing_services if runtime_state else list(target.missing_services or [])
        runtime_error = runtime_state.error if runtime_state else target.runtime_error
        return DeploymentTargetRead.model_validate(target).model_copy(
            update={
                "hostname": server.hostname if server else None,
                "node_type": server.node_type.value if server else None,
                "environment": server.environment.value if server else None,
                "provider": server.provider if server else None,
                "readiness": self._server_readiness(server),
                "last_execution": await self._target_execution_to_read(last_execution) if last_execution else None,
                "runtime_state": runtime_state.runtime_state if runtime_state else target.runtime_state,
                "health_state": runtime_state.health_state if runtime_state else target.health_state,
                "sync_status": runtime_state.sync_status if runtime_state else target.sync_status,
                "runtime_checked_at": checked_at,
                "runtime_error": runtime_error,
                "runtime_stale": self._is_runtime_stale(checked_at),
                "runtime_age_seconds": self._age_seconds(checked_at),
                "runtime_failure_reason": self._target_failure_reason(
                    target,
                    containers=containers,
                    missing_services=missing_services,
                    runtime_error=runtime_error,
                ),
                "containers": containers,
                "missing_services": missing_services,
            }
        )

    async def _execution_to_read(self, execution: DeploymentExecution) -> DeploymentExecutionRead:
        target_executions = [
            await self._target_execution_to_read(item)
            for item in await self.target_execution_repository.list_for_execution(execution.id)
        ]
        target_aggregate = aggregate_target_executions(
            target_executions,
            success_states=deployment_execution_success_states(),
            failure_states=deployment_execution_failure_states(),
        )
        return DeploymentExecutionRead.model_validate(execution).model_copy(
            update={
                "duration_seconds": duration_seconds(execution.started_at, execution.finished_at),
                "target_count": target_aggregate.summary.total_count,
                "success_count": target_aggregate.summary.success_count,
                "failed_count": target_aggregate.summary.failed_count,
                "target_executions": target_executions,
                "activity_timeline": deployment_execution_activity_timeline(execution, target_executions),
            }
        )

    async def _target_execution_to_read(self, execution: DeploymentTargetExecution | None) -> DeploymentTargetExecutionRead | None:
        if execution is None:
            return None
        server = await self.server_repository.get_by_id(execution.server_id)
        return DeploymentTargetExecutionRead.model_validate(execution).model_copy(
            update={
                "hostname": server.hostname if server else None,
                "duration_seconds": duration_seconds(execution.started_at, execution.finished_at),
            }
        )

    @staticmethod
    def _runtime_state_to_read(state: DeploymentRuntimeState) -> DeploymentRuntimeStateRead:
        return DeploymentRuntimeStateRead(
            target_server_id=state.target_server_id,
            status=state.status,
            runtime_state=state.runtime_state,
            sync_status=state.sync_status,
            health_state=state.health_state,
            containers=[
                DeploymentContainerRead(
                    service=container.service,
                    name=container.name,
                    state=container.state,
                    health=container.health,
                    uptime_seconds=container.uptime_seconds,
                    restart_count=container.restart_count,
                )
                for container in state.containers
            ],
            missing_services=state.missing_services,
            inspected_at=state.inspected_at,
            error=state.error,
        )

    @staticmethod
    def _persist_runtime_state(target: DeploymentTarget, state: DeploymentRuntimeState) -> None:
        target.status = state.status
        target.runtime_state = state.runtime_state
        target.health_state = state.health_state
        target.sync_status = state.sync_status
        target.runtime_checked_at = state.inspected_at
        target.runtime_error = state.error[:2000] if state.error else None
        target.runtime_containers = [
            {
                "service": container.service,
                "name": container.name,
                "state": container.state,
                "health": container.health,
                "uptime_seconds": container.uptime_seconds,
                "restart_count": container.restart_count,
            }
            for container in state.containers
        ]
        target.missing_services = list(state.missing_services)

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
            self._deployment_filesystem_function(),
            self._docker_sudo_fallback_function(),
            f"nexusops_ensure_deployment_dir {self._sh_quote(deployment_path)}",
            f"cd {self._sh_quote(deployment_path)}",
        ]
        return (
            "\n".join([*prefix, compose, env, *actions]),
            "\n".join([*prefix, compose, redacted_env, *actions]),
        )

    async def _dry_run_for(
        self,
        deployment: Deployment,
        targets: list[DeploymentTarget],
        operation: str,
    ) -> DeploymentDryRunRead:
        validation = validate_compose_content(deployment.compose_content)
        dry_run_targets = []
        for target in targets:
            server = await self.server_repository.get_by_id(target.server_id)
            dry_run_targets.append(await self._dry_run_target(deployment, target, server, operation))
        return DeploymentDryRunRead(
            deployment_id=deployment.id,
            operation=operation,
            validation=self._compose_validation_to_read(validation),
            targets=dry_run_targets,
            env_keys=self._env_keys(deployment.env_content),
            credential_env_keys=sorted(deployment.credential_refs or {}),
        )

    async def _dry_run_target(
        self,
        deployment: Deployment,
        target: DeploymentTarget,
        server,
        operation: str,
    ) -> DeploymentDryRunTargetRead:
        command, redacted_command = await self._operation_commands(deployment, target, operation)
        deployment_path = self._deployment_path(target, deployment)
        return DeploymentDryRunTargetRead(
            server_id=target.server_id,
            hostname=server.hostname if server else None,
            remote_path=target.remote_path,
            deployment_path=deployment_path,
            execution_credential_ref=deployment.execution_credential_ref,
            command_preview=self.secret_sanitizer.redact_text(command) or "",
            redacted_command_preview=redacted_command,
        )

    @staticmethod
    def _validate_compose_or_raise(compose_content: str) -> None:
        validation = validate_compose_content(compose_content)
        if validation.errors:
            raise DeploymentValidationError("; ".join(validation.errors))

    async def _sync_deployment_targets(
        self,
        deployment: Deployment,
        target_server_ids: list[UUID],
        remote_path: str,
    ) -> None:
        existing_targets = await self.target_repository.list_for_deployment(deployment.id)
        existing_by_server = {target.server_id: target for target in existing_targets}
        desired_ids = set(target_server_ids)

        removed_target_ids = [
            target.id for target in existing_targets if target.server_id not in desired_ids
        ]
        await self.target_execution_repository.delete_for_targets(removed_target_ids)
        await self.target_repository.delete_by_ids(removed_target_ids)

        for server_id in target_server_ids:
            target = existing_by_server.get(server_id)
            if target is None:
                await self.target_repository.create(
                    DeploymentTarget(
                        deployment_id=deployment.id,
                        server_id=server_id,
                        remote_path=remote_path,
                        status=DeploymentStatus.DRAFT,
                    )
                )
                continue
            target.remote_path = remote_path
            target.status = DeploymentStatus.DRAFT

    async def _validate_execution_credential_ref(self, credential_ref: str | None) -> None:
        if not credential_ref or self.credential_service is None:
            return
        try:
            await self.credential_service.resolve_credential(credential_ref)
        except CredentialNotFoundError as exc:
            raise DeploymentValidationError(
                "Execution credential not found. Select an existing password or SSH password credential."
            ) from exc

    @staticmethod
    def _compose_validation_to_read(validation: ComposeValidationResult) -> DeploymentComposeValidationRead:
        return DeploymentComposeValidationRead(
            valid=validation.valid,
            errors=validation.errors,
            warnings=validation.warnings,
            services=validation.services,
        )

    @staticmethod
    def _env_keys(env_content: str | None) -> list[str]:
        keys: list[str] = []
        for line in (env_content or "").splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#") or "=" not in clean:
                continue
            key = clean.split("=", 1)[0].strip()
            if key and key not in keys:
                keys.append(key)
        return keys

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
            self.secret_sanitizer.add_secret(secret)
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
                cls._docker_sudo_fallback_function(),
                f"cd {cls._sh_quote(deployment_path)}",
                cls._docker_compose(compose_args),
            ]
        )

    @classmethod
    def _runtime_inspection_command(cls, target: DeploymentTarget, deployment: Deployment) -> str:
        deployment_path = cls._deployment_path(target, deployment)
        inspect_format = "{{json .}}"
        return "\n".join(
            [
                cls._docker_sudo_fallback_function(),
                f"cd {cls._sh_quote(deployment_path)}",
                f"ids=$({cls._docker_compose('ps -q')} 2>/dev/null || true)",
                "if [ -z \"$ids\" ]; then project=$(basename \"$PWD\"); ids=$(nexusops_docker ps -a --filter \"label=com.docker.compose.project=$project\" -q 2>/dev/null || true); fi",
                "if [ -z \"$ids\" ]; then exit 0; fi",
                f"nexusops_docker inspect --format '{inspect_format}' $ids",
            ]
        )

    @classmethod
    def _docker_compose(cls, compose_args: str) -> str:
        return f"nexusops_docker compose -f {cls.COMPOSE_FILENAME} --env-file {cls.ENV_FILENAME} {compose_args}"

    @staticmethod
    def _docker_sudo_fallback_function() -> str:
        return "\n".join(
            [
                "nexusops_docker() {",
                "  err_file=$(mktemp)",
                "  if docker \"$@\" 2>\"$err_file\"; then rm -f \"$err_file\"; return 0; fi",
                "  status=$?",
                "  if grep -qiE 'permission denied|cannot connect to the docker daemon|docker.sock|dial unix' \"$err_file\"; then",
                "    sudo_err_file=$(mktemp)",
                "    if sudo docker \"$@\" 2>\"$sudo_err_file\"; then rm -f \"$err_file\" \"$sudo_err_file\"; return 0; fi",
                "    sudo_status=$?",
                "    cat \"$err_file\" >&2",
                "    cat \"$sudo_err_file\" >&2",
                "    rm -f \"$err_file\" \"$sudo_err_file\"",
                "    return \"$sudo_status\"",
                "  fi",
                "  cat \"$err_file\" >&2",
                "  rm -f \"$err_file\"",
                "  return \"$status\"",
                "}",
            ]
        )

    @staticmethod
    def _deployment_filesystem_function() -> str:
        return "\n".join(
            [
                "nexusops_ensure_deployment_dir() {",
                "  deployment_dir=\"$1\"",
                "  if mkdir -p \"$deployment_dir\" 2>/dev/null; then return 0; fi",
                "  sudo mkdir -p \"$deployment_dir\"",
                "  sudo chown \"$(id -u):$(id -g)\" \"$deployment_dir\"",
                "}",
            ]
        )

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
    def _age_seconds(value: datetime | None) -> int | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return max(0, int((datetime.now(UTC) - value).total_seconds()))

    @classmethod
    def _is_runtime_stale(cls, value: datetime | None) -> bool:
        age = cls._age_seconds(value)
        return age is None or age > RUNTIME_STALE_AFTER_SECONDS

    @staticmethod
    def _target_failure_reason(
        target: DeploymentTarget,
        *,
        containers: list[DeploymentContainerRead],
        missing_services: list[str],
        runtime_error: str | None,
    ) -> str | None:
        if runtime_error:
            return runtime_error
        if missing_services:
            return "Missing services: " + ", ".join(missing_services)
        unhealthy = [container.service for container in containers if container.health == "unhealthy"]
        if unhealthy:
            return "Unhealthy services: " + ", ".join(unhealthy)
        stopped = [container.service for container in containers if container.state not in {"running"}]
        if target.status in {DeploymentStatus.RUNNING, DeploymentStatus.SUCCESS} and stopped:
            return "Stopped services: " + ", ".join(stopped)
        if target.status == DeploymentStatus.FAILED:
            return "Last deployment execution failed"
        return None

    @staticmethod
    def _deployment_failure_reason(targets: list[DeploymentTargetRead]) -> str | None:
        reasons = [target.runtime_failure_reason for target in targets if target.runtime_failure_reason]
        if reasons:
            return "; ".join(dict.fromkeys(reasons))
        stale = [target.hostname or str(target.server_id) for target in targets if target.runtime_stale]
        if stale:
            return "Runtime check stale on " + ", ".join(stale)
        return None

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
        success_states = {DeploymentStatus.RUNNING, DeploymentStatus.SUCCESS}
        if operation == "stop":
            success_states = {DeploymentStatus.STOPPED}
        return rollup_status(
            statuses,
            success_states=success_states,
            failure_states={DeploymentStatus.FAILED},
            empty_status=DeploymentStatus.FAILED,
            all_success_status=DeploymentStatus.STOPPED if operation == "stop" else DeploymentStatus.RUNNING,
            partial_success_status=DeploymentStatus.PARTIAL_SUCCESS,
            all_failed_status=DeploymentStatus.FAILED,
            mixed_status=DeploymentStatus.DEGRADED,
        )

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

    @staticmethod
    def _aggregate_runtime_state(states: list[str]) -> str:
        filtered = [state for state in states if state and state != "unknown"]
        if not filtered:
            return "unknown"
        if all(state == "running" for state in filtered):
            return "running"
        if all(state == "stopped" for state in filtered):
            return "stopped"
        if any(state in {"degraded", "missing"} for state in filtered):
            return "degraded"
        return "mixed"

    @staticmethod
    def _aggregate_health_state(states: list[str], status: DeploymentStatus) -> str:
        filtered = [state for state in states if state and state != "unknown"]
        if not filtered:
            return DockerComposeDeploymentService._health_state(status)
        if all(state == "healthy" for state in filtered):
            return "healthy"
        if all(state == "stopped" for state in filtered):
            return "stopped"
        if any(state in {"degraded", "unhealthy"} for state in filtered):
            return "degraded"
        return "unknown"
