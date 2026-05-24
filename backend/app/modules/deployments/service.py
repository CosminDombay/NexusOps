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
        deployment, targets, execution = await self._prepare_execution(
            deployment_id,
            operation,
            target_server_ids=target_server_ids,
        )

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
