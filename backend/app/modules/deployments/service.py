from uuid import UUID

from backend.app.modules.deployments.models import (
    Deployment,
    DeploymentRevision,
    DeploymentStatus,
    DeploymentTarget,
)
from backend.app.modules.deployments.repository import (
    DeploymentRepository,
    DeploymentRevisionRepository,
    DeploymentTargetRepository,
)
from backend.app.modules.deployments.schemas import (
    DeploymentCreate,
    DeploymentLogsRead,
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentRevisionRead,
    DeploymentStatusRead,
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

    def __init__(
        self,
        *,
        repository: DeploymentRepository,
        target_repository: DeploymentTargetRepository,
        revision_repository: DeploymentRevisionRepository,
        server_repository: ServerRepository,
        job_service: JobService,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.repository = repository
        self.target_repository = target_repository
        self.revision_repository = revision_repository
        self.server_repository = server_repository
        self.job_service = job_service
        self.credential_service = credential_service

    async def list_deployments(self) -> list[DeploymentRead]:
        deployments = await self.repository.list()
        return [await self._to_read(deployment) for deployment in deployments]

    async def create_deployment(self, payload: DeploymentCreate) -> DeploymentRead:
        server = await self._managed_server(payload.target_server_id)
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

    async def deploy(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "deploy")

    async def redeploy(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "redeploy")

    async def restart(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "restart")

    async def stop(self, deployment_id: UUID) -> DeploymentOperationRead:
        return await self._run_operation(deployment_id, "stop")

    async def status(self, deployment_id: UUID) -> DeploymentStatusRead:
        deployment, target = await self._deployment_and_target(deployment_id)
        command = f"cd {self._sh_quote(self._deployment_path(target, deployment))} && docker compose ps"
        job = await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=target.server_id,
                operation_type=f"deployment:{deployment.id}:status",
                command=command,
            )
        )
        return DeploymentStatusRead(deployment_id=deployment.id, target_server_id=target.server_id, job=job)

    async def logs(self, deployment_id: UUID) -> DeploymentLogsRead:
        deployment, target = await self._deployment_and_target(deployment_id)
        command = f"cd {self._sh_quote(self._deployment_path(target, deployment))} && docker compose logs --tail=200"
        job = await self.job_service.execute(
            JobExecuteRequest(
                target_server_id=target.server_id,
                operation_type=f"deployment:{deployment.id}:logs",
                command=command,
            )
        )
        return DeploymentLogsRead(
            deployment_id=deployment.id,
            target_server_id=target.server_id,
            logs=job.stdout or "",
            job=job,
        )

    async def _run_operation(self, deployment_id: UUID, operation: str) -> DeploymentOperationRead:
        deployment, target = await self._deployment_and_target(deployment_id)
        await self._managed_server(target.server_id)
        deployment.status = DeploymentStatus.DEPLOYING
        target.status = DeploymentStatus.DEPLOYING
        await self.repository.session.commit()

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

        deployment.status = next_status
        target.status = next_status
        target.last_job_id = job.id
        revision.status = next_status
        revision.job_id = job.id
        revision.stdout = job.stdout
        revision.stderr = job.stderr
        await self.repository.session.commit()
        await self.repository.session.refresh(revision)
        return DeploymentOperationRead(
            deployment=await self._to_read(deployment),
            job=job,
            revision=DeploymentRevisionRead.model_validate(revision),
        )

    async def _deployment_and_target(self, deployment_id: UUID) -> tuple[Deployment, DeploymentTarget]:
        deployment = await self.repository.get_by_id(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError("Deployment not found")
        target = await self.target_repository.get_for_deployment(deployment.id)
        if target is None:
            raise DeploymentValidationError("Deployment has no target host")
        return deployment, target

    async def _managed_server(self, server_id: UUID):
        server = await self.server_repository.get_by_id(server_id)
        if server is None:
            raise JobTargetNotFoundError("Target server not found")
        if not server.managed or server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
            raise JobTargetNotManagedError("Target server is not managed")
        return server

    async def _to_read(self, deployment: Deployment) -> DeploymentRead:
        target = await self.target_repository.get_for_deployment(deployment.id)
        server = await self.server_repository.get_by_id(target.server_id) if target else None
        return DeploymentRead(
            id=deployment.id,
            name=deployment.name,
            description=deployment.description,
            compose_content=deployment.compose_content,
            env_content=deployment.env_content,
            credential_refs=deployment.credential_refs,
            status=deployment.status,
            target_server_id=target.server_id if target else None,
            target_hostname=server.hostname if server else None,
            remote_path=target.remote_path if target else None,
            created_at=deployment.created_at,
            updated_at=deployment.updated_at,
        )

    async def _operation_commands(self, deployment: Deployment, target: DeploymentTarget, operation: str) -> tuple[str, str]:
        deployment_path = self._deployment_path(target, deployment)
        compose = self._heredoc("compose.yml", deployment.compose_content)
        env_content, redacted_env_content = await self._env_contents(deployment)
        env = self._heredoc(".env", env_content)
        redacted_env = self._heredoc(".env", redacted_env_content)
        if operation in {"deploy", "redeploy"}:
            action = "docker compose version && docker compose pull && docker compose up -d"
        elif operation == "restart":
            action = "docker compose restart"
        elif operation == "stop":
            action = "docker compose stop"
        else:
            raise DeploymentValidationError("Unsupported deployment operation")
        prefix = (
            f"mkdir -p {self._sh_quote(deployment_path)} && "
            f"cd {self._sh_quote(deployment_path)} && "
        )
        return f"{prefix}{compose} && {env} && {action}", f"{prefix}{compose} && {redacted_env} && {action}"

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
    def _heredoc(filename: str, content: str) -> str:
        return f"cat > {filename} <<'NEXUSOPS_EOF'\n{content}\nNEXUSOPS_EOF"

    @staticmethod
    def _sh_quote(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _dotenv_quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        return f'"{escaped}"'
