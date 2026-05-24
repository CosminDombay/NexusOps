# Deployments Review

Generated from the current NexusOps workspace for focused code review.

## backend/app/modules/deployments/models.py

``python
from enum import StrEnum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class DeploymentStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    DEPLOYING = "deploying"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Deployment(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployments"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    compose_content: Mapped[str] = mapped_column(Text)
    env_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_refs: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DRAFT,
        nullable=False,
        index=True,
    )


class DeploymentTarget(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_targets"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    remote_path: Mapped[str] = mapped_column(String(500), default="/opt/nexusops/deployments")
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DRAFT,
        nullable=False,
        index=True,
    )
    last_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)


class DeploymentRevision(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_revisions"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    compose_content: Mapped[str] = mapped_column(Text)
    env_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.DEPLOYING,
        nullable=False,
        index=True,
    )
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_executions"

    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.QUEUED,
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[str] = mapped_column(String(100), default="manual", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentTargetExecution(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_target_executions"

    execution_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_executions.id"), index=True)
    deployment_id: Mapped[UUID] = mapped_column(ForeignKey("deployments.id"), index=True)
    target_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_targets.id"), index=True)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=DeploymentStatus.QUEUED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    revision_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_revisions.id"), nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

````

## backend/app/modules/deployments/schemas.py

``python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.modules.deployments.models import DeploymentStatus
from backend.app.modules.jobs.schemas import JobRead
from backend.app.modules.orchestration.activity import OperationalActivityRead


class DeploymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_server_id: UUID | None = None
    target_server_ids: list[UUID] = Field(default_factory=list)
    compose_content: str = Field(min_length=1, max_length=20000)
    env_content: str | None = Field(default=None, max_length=20000)
    credential_refs: dict[str, str] = Field(default_factory=dict)
    remote_path: str = Field(default="/opt/nexusops/deployments", min_length=1, max_length=500)

    @field_validator("name", "compose_content", "remote_path")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("target_server_ids")
    @classmethod
    def dedupe_target_server_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class DeploymentUpdate(DeploymentCreate):
    pass


class DeploymentRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    compose_content: str
    env_content: str | None = None
    credential_refs: dict[str, str] = Field(default_factory=dict)
    status: DeploymentStatus
    target_server_id: UUID | None = None
    target_server_ids: list[UUID] = Field(default_factory=list)
    target_hostname: str | None = None
    targets: list["DeploymentTargetRead"] = Field(default_factory=list)
    latest_execution: "DeploymentExecutionRead | None" = None
    execution_history: list["DeploymentExecutionRead"] = Field(default_factory=list)
    remote_path: str | None = None
    ports: list[str] = Field(default_factory=list)
    compose_source: str = "inline"
    uptime_seconds: int | None = None
    health_state: str = "unknown"
    sync_status: str = "unknown"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentTargetRead(BaseModel):
    id: UUID
    server_id: UUID
    hostname: str | None = None
    node_type: str | None = None
    environment: str | None = None
    provider: str | None = None
    readiness: str = "unknown"
    remote_path: str
    status: DeploymentStatus
    last_job_id: UUID | None = None
    last_execution: "DeploymentTargetExecutionRead | None" = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentRevisionRead(BaseModel):
    id: UUID
    deployment_id: UUID
    server_id: UUID
    revision_number: int
    operation: str
    job_id: UUID | None = None
    status: DeploymentStatus
    stdout: str | None = None
    stderr: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentTargetExecutionRead(BaseModel):
    id: UUID
    execution_id: UUID
    deployment_id: UUID
    target_id: UUID
    server_id: UUID
    hostname: str | None = None
    status: DeploymentStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    job_id: UUID | None = None
    revision_id: UUID | None = None
    stdout: str | None = None
    stderr: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentExecutionRead(BaseModel):
    id: UUID
    deployment_id: UUID
    operation: str
    status: DeploymentStatus
    trigger_source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    target_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    result_summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    target_executions: list[DeploymentTargetExecutionRead] = Field(default_factory=list)
    activity_timeline: list[OperationalActivityRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentOperationRead(BaseModel):
    deployment: DeploymentRead
    job: JobRead | None = None
    revision: DeploymentRevisionRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)
    revisions: list[DeploymentRevisionRead] = Field(default_factory=list)
    execution: DeploymentExecutionRead | None = None


class DeploymentStatusRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID | None = None
    job: JobRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)


class DeploymentLogsRead(BaseModel):
    deployment_id: UUID
    target_server_id: UUID | None = None
    logs: str
    job: JobRead | None = None
    jobs: list[JobRead] = Field(default_factory=list)

````

## backend/app/modules/deployments/repository.py

``python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.deployments.models import (
    Deployment,
    DeploymentExecution,
    DeploymentRevision,
    DeploymentTarget,
    DeploymentTargetExecution,
)


class DeploymentRepository(BaseRepository[Deployment]):
    async def create(self, deployment: Deployment) -> Deployment:
        self.session.add(deployment)
        await self.session.flush()
        await self.session.refresh(deployment)
        return deployment

    async def get_by_id(self, deployment_id: UUID) -> Deployment | None:
        result = await self.session.execute(select(Deployment).where(Deployment.id == deployment_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Deployment]:
        result = await self.session.execute(select(Deployment).order_by(Deployment.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_server(self, server_id: UUID) -> list[Deployment]:
        result = await self.session.execute(
            select(Deployment)
            .join(DeploymentTarget, DeploymentTarget.deployment_id == Deployment.id)
            .where(DeploymentTarget.server_id == server_id)
            .order_by(Deployment.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def delete(self, deployment: Deployment) -> None:
        await self.session.delete(deployment)


class DeploymentTargetRepository(BaseRepository[DeploymentTarget]):
    async def create(self, target: DeploymentTarget) -> DeploymentTarget:
        self.session.add(target)
        await self.session.flush()
        await self.session.refresh(target)
        return target

    async def get_for_deployment(self, deployment_id: UUID) -> DeploymentTarget | None:
        result = await self.session.execute(
            select(DeploymentTarget).where(DeploymentTarget.deployment_id == deployment_id)
        )
        return result.scalar_one_or_none()

    async def list_for_deployment(self, deployment_id: UUID) -> list[DeploymentTarget]:
        result = await self.session.execute(
            select(DeploymentTarget).where(DeploymentTarget.deployment_id == deployment_id)
        )
        return list(result.scalars().all())

    async def delete_for_deployment(self, deployment_id: UUID) -> None:
        await self.session.execute(delete(DeploymentTarget).where(DeploymentTarget.deployment_id == deployment_id))


class DeploymentRevisionRepository(BaseRepository[DeploymentRevision]):
    async def create(self, revision: DeploymentRevision) -> DeploymentRevision:
        self.session.add(revision)
        await self.session.flush()
        await self.session.refresh(revision)
        return revision

    async def list_for_deployment(self, deployment_id: UUID) -> list[DeploymentRevision]:
        result = await self.session.execute(
            select(DeploymentRevision)
            .where(DeploymentRevision.deployment_id == deployment_id)
            .order_by(DeploymentRevision.revision_number.desc())
        )
        return list(result.scalars().all())

    async def next_revision_number(self, deployment_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(DeploymentRevision.revision_number)).where(
                DeploymentRevision.deployment_id == deployment_id
            )
        )
        return int(result.scalar_one_or_none() or 0) + 1

    async def delete_for_deployment(self, deployment_id: UUID) -> None:
        await self.session.execute(delete(DeploymentRevision).where(DeploymentRevision.deployment_id == deployment_id))


class DeploymentExecutionRepository(BaseRepository[DeploymentExecution]):
    async def create(self, execution: DeploymentExecution) -> DeploymentExecution:
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def list_for_deployment(self, deployment_id: UUID) -> list[DeploymentExecution]:
        result = await self.session.execute(
            select(DeploymentExecution)
            .where(DeploymentExecution.deployment_id == deployment_id)
            .order_by(DeploymentExecution.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_for_deployment(self, deployment_id: UUID) -> None:
        await self.session.execute(delete(DeploymentExecution).where(DeploymentExecution.deployment_id == deployment_id))


class DeploymentTargetExecutionRepository(BaseRepository[DeploymentTargetExecution]):
    async def create(self, execution: DeploymentTargetExecution) -> DeploymentTargetExecution:
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def list_for_execution(self, execution_id: UUID) -> list[DeploymentTargetExecution]:
        result = await self.session.execute(
            select(DeploymentTargetExecution)
            .where(DeploymentTargetExecution.execution_id == execution_id)
            .order_by(DeploymentTargetExecution.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_deployment(self, deployment_id: UUID) -> list[DeploymentTargetExecution]:
        result = await self.session.execute(
            select(DeploymentTargetExecution)
            .where(DeploymentTargetExecution.deployment_id == deployment_id)
            .order_by(DeploymentTargetExecution.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_for_deployment(self, deployment_id: UUID) -> None:
        await self.session.execute(
            delete(DeploymentTargetExecution).where(DeploymentTargetExecution.deployment_id == deployment_id)
        )

````

## backend/app/modules/deployments/service.py

``python
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
from backend.app.modules.orchestration.semantics import (
    deployment_execution_failure_states,
    deployment_execution_success_states,
)
from backend.app.modules.orchestration.utils import (
    aggregate_target_executions,
    duration_seconds,
    rollup_status,
)


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
                env_content=deployment.env_content,
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
        except Exception as exc:
            target.status = DeploymentStatus.FAILED
            revision.status = DeploymentStatus.FAILED
            revision.stderr = str(exc)
            target_execution.status = DeploymentStatus.FAILED
            target_execution.error_message = str(exc)
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
        deployment.status = self._rollup_status([target.status for target in targets], operation)
        execution.status = deployment.status
        execution.finished_at = datetime.now(UTC)
        target_aggregate = aggregate_target_executions(
            target_executions,
            success_states=deployment_execution_success_states(),
            failure_states=deployment_execution_failure_states(),
        )
        execution.result_summary = target_aggregate.summary.as_result_summary()
        execution.error_message = (
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

````

## backend/app/modules/deployments/router.py

``python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.db.session import AsyncSessionLocal, get_db_session
from backend.app.modules.audit.repository import AuditEventRepository
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
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
    DeploymentOperationRead,
    DeploymentRead,
    DeploymentStatusRead,
    DeploymentUpdate,
)
from backend.app.modules.deployments.service import (
    DeploymentNotFoundError,
    DeploymentValidationError,
    DockerComposeDeploymentService,
)
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService, JobTargetNotFoundError, JobTargetNotManagedError

router = APIRouter()


async def get_deployment_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DockerComposeDeploymentService:
    server_repository = ServerRepository(session)
    return DockerComposeDeploymentService(
        repository=DeploymentRepository(session),
        target_repository=DeploymentTargetRepository(session),
        revision_repository=DeploymentRevisionRepository(session),
        execution_repository=DeploymentExecutionRepository(session),
        target_execution_repository=DeploymentTargetExecutionRepository(session),
        server_repository=server_repository,
        job_service=JobService(
            job_repository=JobRepository(session),
            server_repository=server_repository,
            ssh_adapter=ParamikoSshAdapter(),
            credential_service=CredentialService(repository=CredentialRepository(session)),
            audit_service=AuditService(AuditEventRepository(session)),
            session_factory=AsyncSessionLocal,
        ),
        credential_service=CredentialService(repository=CredentialRepository(session)),
    )


@router.get("", response_model=list[DeploymentRead])
async def list_deployments(
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
    server_id: UUID | None = None,
) -> list[DeploymentRead]:
    return await service.list_deployments(server_id=server_id)


@router.post("", response_model=DeploymentRead, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    try:
        return await service.create_deployment(payload)
    except DeploymentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobTargetNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{deployment_id}/deploy", response_model=DeploymentOperationRead)
async def deploy(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.deploy(deployment_id))


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> None:
    await _run(lambda: service.delete_deployment(deployment_id))


@router.put("/{deployment_id}", response_model=DeploymentRead)
async def update_deployment(
    deployment_id: UUID,
    payload: DeploymentUpdate,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentRead:
    return await _run(lambda: service.update_deployment(deployment_id, payload))


@router.post("/{deployment_id}/redeploy", response_model=DeploymentOperationRead)
async def redeploy(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.redeploy(deployment_id))


@router.post("/{deployment_id}/restart", response_model=DeploymentOperationRead)
async def restart(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.restart(deployment_id))


@router.post("/{deployment_id}/stop", response_model=DeploymentOperationRead)
async def stop(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentOperationRead:
    return await _run(lambda: service.stop(deployment_id))


@router.get("/{deployment_id}/status", response_model=DeploymentStatusRead)
async def get_status(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentStatusRead:
    return await _run(lambda: service.status(deployment_id))


@router.get("/{deployment_id}/logs", response_model=DeploymentLogsRead)
async def get_logs(
    deployment_id: UUID,
    service: Annotated[DockerComposeDeploymentService, Depends(get_deployment_service)],
) -> DeploymentLogsRead:
    return await _run(lambda: service.logs(deployment_id))


async def _run(operation):
    try:
        return await operation()
    except DeploymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DeploymentValidationError, JobTargetNotManagedError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except JobTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

````

## backend/app/modules/deployments/tasks.py

``python
"""Future background tasks for Docker Compose deployments."""

````

## frontend/src/features/deployments/api/deploymentsApi.ts

``typescript
import { apiClient } from '../../../lib/api/client';
import type { CreateDeploymentPayload, Deployment, DeploymentLogs, DeploymentOperation, DeploymentStatusResult, UpdateDeploymentPayload } from '../types/deployment';

export async function listDeployments(filters: { serverId?: string } = {}): Promise<Deployment[]> {
  const response = await apiClient.get<Deployment[]>('/deployments', {
    params: filters.serverId ? { server_id: filters.serverId } : undefined,
  });
  return response.data;
}

export async function createDeployment(payload: CreateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.post<Deployment>('/deployments', payload);
  return response.data;
}

export async function deleteDeployment(deploymentId: string): Promise<void> {
  await apiClient.delete(`/deployments/${deploymentId}`);
}

export async function updateDeployment(deploymentId: string, payload: UpdateDeploymentPayload): Promise<Deployment> {
  const response = await apiClient.put<Deployment>(`/deployments/${deploymentId}`, payload);
  return response.data;
}

export async function runDeploymentOperation(
  deploymentId: string,
  operation: 'deploy' | 'redeploy' | 'restart' | 'stop',
): Promise<DeploymentOperation> {
  const response = await apiClient.post<DeploymentOperation>(`/deployments/${deploymentId}/${operation}`);
  return response.data;
}

export async function getDeploymentLogs(deploymentId: string): Promise<DeploymentLogs> {
  const response = await apiClient.get<DeploymentLogs>(`/deployments/${deploymentId}/logs`);
  return response.data;
}

export async function getDeploymentStatus(deploymentId: string): Promise<DeploymentStatusResult> {
  const response = await apiClient.get<DeploymentStatusResult>(`/deployments/${deploymentId}/status`);
  return response.data;
}

````

## frontend/src/features/deployments/types/deployment.ts

``typescript
import type { OperationalActivity } from '../../../components/operations/runtimeTypes';
import type { Job } from '../../jobs/types/job';

export type DeploymentStatus =
  | 'draft'
  | 'queued'
  | 'deploying'
  | 'running'
  | 'success'
  | 'partial_success'
  | 'degraded'
  | 'stopped'
  | 'failed'
  | 'cancelled'
  | 'created'
  | 'deployed';

export type DeploymentTargetExecution = {
  id: string;
  execution_id: string;
  deployment_id: string;
  target_id: string;
  server_id: string;
  hostname: string | null;
  status: DeploymentStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  job_id: string | null;
  revision_id: string | null;
  stdout: string | null;
  stderr: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DeploymentExecution = {
  id: string;
  deployment_id: string;
  operation: string;
  status: DeploymentStatus;
  trigger_source: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  target_count: number;
  success_count: number;
  failed_count: number;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  target_executions: DeploymentTargetExecution[];
  activity_timeline: OperationalActivity[];
  created_at: string;
  updated_at: string;
};

export type DeploymentTarget = {
  id: string;
  server_id: string;
  hostname: string | null;
  node_type: string | null;
  environment: string | null;
  provider: string | null;
  readiness: string;
  remote_path: string;
  status: DeploymentStatus;
  last_job_id: string | null;
  last_execution: DeploymentTargetExecution | null;
  created_at: string;
  updated_at: string;
};

export type Deployment = {
  id: string;
  name: string;
  description: string | null;
  compose_content: string;
  env_content: string | null;
  credential_refs: Record<string, string>;
  status: DeploymentStatus;
  target_server_id: string | null;
  target_server_ids?: string[];
  target_hostname: string | null;
  targets: DeploymentTarget[];
  latest_execution: DeploymentExecution | null;
  execution_history: DeploymentExecution[];
  remote_path: string | null;
  ports: string[];
  compose_source: string;
  uptime_seconds: number | null;
  health_state: string;
  sync_status: string;
  created_at: string;
  updated_at: string;
};

export type CreateDeploymentPayload = {
  name: string;
  description?: string | null;
  target_server_id: string;
  target_server_ids?: string[];
  compose_content: string;
  env_content?: string | null;
  credential_refs?: Record<string, string>;
  remote_path?: string;
};

export type UpdateDeploymentPayload = CreateDeploymentPayload;

export type DeploymentOperation = {
  deployment: Deployment;
  job: Job | null;
  revision?: unknown | null;
  jobs: Job[];
  revisions?: unknown[];
  execution: DeploymentExecution | null;
};

export type DeploymentLogs = {
  deployment_id: string;
  target_server_id: string;
  logs: string;
  job: Job | null;
  jobs: Job[];
};

export type DeploymentStatusResult = {
  deployment_id: string;
  target_server_id: string | null;
  job: Job | null;
  jobs: Job[];
};

````

## frontend/src/features/deployments/DeploymentsPage.tsx

``tsx
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Eye,
  FileText,
  KeyRound,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCw,
  Server,
  Square,
  Terminal,
  Trash2,
  X,
} from 'lucide-react';

import { PageHeader } from '../../components/layout/PageHeader';
import { PageActionButton, RuntimeBadge, CollapsibleSection } from '../../components/operations/OperationalComponents';
import { OperationalTimeline } from '../../components/operations/OperationalTimeline';
import { formatDurationSeconds, formatOperationalLabel } from '../../components/operations/runtimeFormat';
import { getApiErrorMessage } from '../../lib/api/client';
import { listCredentials } from '../credentials/api/credentialsApi';
import type { Credential } from '../credentials/types/credential';
import { listServers } from '../inventory/api/serversApi';
import { TargetSelector } from '../inventory/components/TargetSelector';
import { useTargetSelection } from '../inventory/hooks/useTargetSelection';
import type { Server as InventoryServer } from '../inventory/types/server';
import { selectedTargetIds } from '../inventory/types/targetSelection';
import type { Job } from '../jobs/types/job';
import {
  createDeployment,
  deleteDeployment,
  getDeploymentLogs,
  getDeploymentStatus,
  listDeployments,
  runDeploymentOperation,
  updateDeployment,
} from './api/deploymentsApi';
import type { CreateDeploymentPayload, Deployment, DeploymentStatus } from './types/deployment';

const defaultCompose = `services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`;

const defaultRemotePath = '/opt/nexusops/deployments';
const statusFilters: Array<DeploymentStatus | 'all'> = [
  'all',
  'running',
  'deploying',
  'partial_success',
  'degraded',
  'stopped',
  'failed',
  'draft',
];

type DrawerMode = 'create' | 'edit' | null;
type DeploymentOperationName = 'deploy' | 'redeploy' | 'restart' | 'stop';

export function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [servers, setServers] = useState<InventoryServer[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('');
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [statusFilter, setStatusFilter] = useState<DeploymentStatus | 'all'>('all');
  const [name, setName] = useState('nginx-demo');
  const [targetServerId, setTargetServerId] = useState('');
  const targetSelector = useTargetSelection('single');
  const [composeContent, setComposeContent] = useState(defaultCompose);
  const [envContent, setEnvContent] = useState('');
  const [remotePath, setRemotePath] = useState(defaultRemotePath);
  const [credentialRefs, setCredentialRefs] = useState<
    Array<{ key: string; credentialId: string }>
  >([]);
  const [logs, setLogs] = useState('');
  const [inspectOutput, setInspectOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [editingDeploymentId, setEditingDeploymentId] = useState<string | null>(null);

  const selectedDeployment =
    deployments.find((deployment) => deployment.id === selectedDeploymentId) ??
    deployments[0] ??
    null;
  const filteredDeployments = useMemo(
    () =>
      deployments.filter(
        (deployment) =>
          statusFilter === 'all' || normalizeStatus(deployment.status) === statusFilter,
      ),
    [deployments, statusFilter],
  );

  async function refresh() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDeployments, nextServers, nextCredentials] = await Promise.all([
        listDeployments(),
        listServers(),
        listCredentials(),
      ]);
      setDeployments(nextDeployments);
      setServers(nextServers);
      setCredentials(nextCredentials);
      setTargetServerId((current) => current || nextServers[0]?.id || '');
      setSelectedDeploymentId((current) => current || nextDeployments[0]?.id || '');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsLoading(false);
    }
  }

  function deploymentPayload(targets: string[]): CreateDeploymentPayload {
    return {
      name: name.trim(),
      target_server_id: targets[0],
      target_server_ids: targets,
      compose_content: composeContent,
      env_content: envContent || null,
      remote_path: remotePath.trim(),
      credential_refs: Object.fromEntries(
        credentialRefs
          .filter((item) => item.key.trim() && item.credentialId)
          .map((item) => [item.key.trim(), item.credentialId]),
      ),
    };
  }

  function resetForm() {
    setEditingDeploymentId(null);
    setName('nginx-demo');
    setComposeContent(defaultCompose);
    setEnvContent('');
    setRemotePath(defaultRemotePath);
    setCredentialRefs([]);
    targetSelector.setMode('single');
    targetSelector.setSelectedId(targetServerId);
    targetSelector.setSelectedIds([]);
  }

  function openCreateDrawer() {
    resetForm();
    setDrawerMode('create');
  }

  function openEditDrawer(deployment: Deployment) {
    setEditingDeploymentId(deployment.id);
    setSelectedDeploymentId(deployment.id);
    setName(deployment.name);
    setComposeContent(deployment.compose_content);
    setEnvContent(deployment.env_content ?? '');
    setRemotePath(deployment.remote_path ?? defaultRemotePath);
    setCredentialRefs(
      Object.entries(deployment.credential_refs ?? {}).map(([key, credentialId]) => ({
        key,
        credentialId,
      })),
    );
    targetSelector.setMode((deployment.target_server_ids?.length ?? 0) > 1 ? 'bulk' : 'single');
    targetSelector.setSelectedId(deployment.target_server_id ?? '');
    targetSelector.setSelectedIds(deployment.target_server_ids ?? []);
    setTargetServerId(deployment.target_server_id ?? '');
    setDrawerMode('edit');
    setError(null);
  }

  async function handleSave() {
    const targets = selectedTargetIds({
      ...targetSelector.selection,
      selectedId: targetSelector.selection.selectedId || targetServerId,
    });
    if (!name.trim() || targets.length === 0 || !composeContent.trim() || !remotePath.trim()) {
      setError('Deployment name, target, compose YAML, and remote path are required.');
      return;
    }
    setIsWorking(true);
    setError(null);
    try {
      const payload = deploymentPayload(targets);
      if (editingDeploymentId) {
        const deployment = await updateDeployment(editingDeploymentId, payload);
        setDeployments((current) =>
          current.map((item) => (item.id === deployment.id ? deployment : item)),
        );
        setSelectedDeploymentId(deployment.id);
      } else {
        const deployment = await createDeployment(payload);
        setDeployments((current) => [deployment, ...current]);
        setSelectedDeploymentId(deployment.id);
      }
      setDrawerMode(null);
      resetForm();
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function run(deployment: Deployment, operation: DeploymentOperationName) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await runDeploymentOperation(deployment.id, operation);
      setDeployments((current) =>
        current.map((item) => (item.id === result.deployment.id ? result.deployment : item)),
      );
      setLogs(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function inspect(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentStatus(deployment.id);
      setInspectOutput(formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function loadLogs(deployment: Deployment) {
    setSelectedDeploymentId(deployment.id);
    setIsWorking(true);
    setError(null);
    try {
      const result = await getDeploymentLogs(deployment.id);
      setLogs(result.logs || formatJobsOutput(result.jobs.length ? result.jobs : result.job ? [result.job] : []));
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  async function handleDeleteDeployment(deployment: Deployment) {
    const confirmed = window.confirm(
      `Delete deployment ${deployment.name}? This removes the NexusOps record and history only. It does not stop containers or remove files from the server.`,
    );
    if (!confirmed) return;
    setIsWorking(true);
    setError(null);
    try {
      await deleteDeployment(deployment.id);
      const nextDeployments = deployments.filter((item) => item.id !== deployment.id);
      setDeployments(nextDeployments);
      setSelectedDeploymentId(nextDeployments[0]?.id ?? '');
      setLogs('');
      setInspectOutput('');
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setIsWorking(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Docker Deployments"
        description="Operational Compose services deployed to inventory-managed Linux hosts."
        actions={
          <>
            <PageActionButton icon={RefreshCw} tone="secondary" onClick={() => void refresh()}>
              Refresh
            </PageActionButton>
            <PageActionButton icon={Plus} onClick={openCreateDrawer}>
              Create deployment
            </PageActionButton>
          </>
        }
      />

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Services" value={deployments.length} />
          <Metric
            label="Running"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'running').length}
          />
          <Metric
            label="Failed"
            value={deployments.filter((item) => normalizeStatus(item.status) === 'failed').length}
          />
          <Metric
            label="Drift"
            value={deployments.filter((item) => item.sync_status !== 'synced').length}
          />
        </div>
      </section>

      <section className="flex flex-wrap gap-2">
        {statusFilters.map((status) => (
          <button
            key={status}
            className={`rounded-md px-3 py-2 text-sm font-semibold ${statusFilter === status ? 'bg-zinc-950 text-white' : 'border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50'}`}
            type="button"
            onClick={() => setStatusFilter(status)}
          >
            {status === 'all' ? 'All' : statusLabel(status)}
          </button>
        ))}
      </section>

      {isLoading ? (
        <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-500">
          Loading deployments...
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-3">
        {filteredDeployments.map((deployment) => (
          <DeploymentCard
            key={deployment.id}
            deployment={deployment}
            selected={deployment.id === selectedDeployment?.id}
            isWorking={isWorking}
            onSelect={() => setSelectedDeploymentId(deployment.id)}
            onRun={run}
            onInspect={inspect}
            onLogs={loadLogs}
            onEdit={openEditDrawer}
            onDelete={handleDeleteDeployment}
          />
        ))}
        {!filteredDeployments.length && !isLoading ? (
          <div className="rounded-md border border-dashed border-zinc-300 bg-white p-8 text-sm text-zinc-500 xl:col-span-3">
            No deployments match this view.
          </div>
        ) : null}
      </section>

      <CollapsibleSection
        title="Runtime output"
        description="Inspect and logs output are available on demand so the deployment list stays scannable."
      >
        <section className="grid gap-4 xl:grid-cols-2">
        <OutputPanel
          title="Inspect"
          value={inspectOutput || selectedDeploymentSummary(selectedDeployment)}
        />
        <OutputPanel title="Logs" value={logs || 'No logs loaded.'} />
        </section>
      </CollapsibleSection>

      {drawerMode ? (
        <DeploymentDrawer
          mode={drawerMode}
          servers={servers}
          credentials={credentials}
          targetSelector={targetSelector}
          name={name}
          composeContent={composeContent}
          envContent={envContent}
          remotePath={remotePath}
          credentialRefs={credentialRefs}
          isWorking={isWorking}
          onNameChange={setName}
          onComposeChange={setComposeContent}
          onEnvChange={setEnvContent}
          onRemotePathChange={setRemotePath}
          onCredentialRefsChange={setCredentialRefs}
          onTargetServerIdChange={setTargetServerId}
          onClose={() => {
            setDrawerMode(null);
            resetForm();
          }}
          onSave={() => void handleSave()}
        />
      ) : null}
    </div>
  );
}

function DeploymentCard({
  deployment,
  selected,
  isWorking,
  onSelect,
  onRun,
  onInspect,
  onLogs,
  onEdit,
  onDelete,
}: {
  deployment: Deployment;
  selected: boolean;
  isWorking: boolean;
  onSelect: () => void;
  onRun: (deployment: Deployment, operation: DeploymentOperationName) => Promise<void>;
  onInspect: (deployment: Deployment) => Promise<void>;
  onLogs: (deployment: Deployment) => Promise<void>;
  onEdit: (deployment: Deployment) => void;
  onDelete: (deployment: Deployment) => Promise<void>;
}) {
  return (
    <article
      className={`rounded-md border bg-white p-4 shadow-sm ${selected ? 'border-cyan-400 ring-1 ring-cyan-200' : 'border-zinc-200'}`}
    >
      <button className="w-full text-left" type="button" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-zinc-950">{deployment.name}</h2>
            <p className="mt-1 flex items-center gap-1 text-sm text-zinc-500">
              <Server className="h-4 w-4" aria-hidden="true" />
              {deployment.targets.length > 1 ? (
                <span className="font-semibold text-zinc-700">{deployment.targets.length} targets</span>
              ) : deployment.target_server_id ? (
                <Link
                  className="font-semibold text-zinc-700 hover:text-zinc-950"
                  to={`/inventory/${deployment.target_server_id}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  {deployment.target_hostname ?? 'Open host'}
                </Link>
              ) : (
                'No target'
              )}
            </p>
          </div>
          <RuntimeBadge value={deployment.status} />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Info
            label="Ports"
            value={deployment.ports.length ? deployment.ports.join(', ') : 'none'}
          />
          <Info label="Health" value={deployment.health_state} />
          <Info label="Sync" value={deployment.sync_status} />
          <Info label="Uptime" value={formatDuration(deployment.uptime_seconds)} />
        </div>
        <DeploymentTargets deployment={deployment} />
        <DeploymentExecutionSummary deployment={deployment} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip icon={FileText} label={deployment.compose_source} />
          {Object.keys(deployment.credential_refs ?? {}).length ? (
            <Chip
              icon={KeyRound}
              label={`${Object.keys(deployment.credential_refs).length} secret refs`}
            />
          ) : null}
          {deployment.remote_path ? (
            <Chip icon={Activity} label={deploymentPathPreview(deployment)} />
          ) : null}
        </div>
      </button>
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          icon={Play}
          label="Start"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'deploy')}
        />
        <ActionButton
          icon={Square}
          label="Stop"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'stop')}
        />
        <ActionButton
          icon={RotateCw}
          label="Restart"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'restart')}
        />
        <ActionButton
          icon={RefreshCw}
          label="Redeploy"
          disabled={isWorking}
          onClick={() => void onRun(deployment, 'redeploy')}
        />
        <ActionButton
          icon={Eye}
          label="Inspect"
          disabled={isWorking}
          onClick={() => void onInspect(deployment)}
        />
        <ActionButton
          icon={Terminal}
          label="Logs"
          disabled={isWorking}
          onClick={() => void onLogs(deployment)}
        />
        <ActionButton
          icon={Pencil}
          label="Edit"
          disabled={isWorking}
          onClick={() => onEdit(deployment)}
        />
        <ActionButton
          icon={Trash2}
          label="Delete"
          disabled={isWorking}
          tone="danger"
          onClick={() => void onDelete(deployment)}
        />
      </div>
    </article>
  );
}

function DeploymentTargets({ deployment }: { deployment: Deployment }) {
  const targets = deployment.targets.length
    ? deployment.targets
    : deployment.target_server_id
      ? [
          {
            id: deployment.target_server_id,
            server_id: deployment.target_server_id,
            hostname: deployment.target_hostname,
            node_type: null,
            environment: null,
            provider: null,
            readiness: 'unknown',
            remote_path: deployment.remote_path ?? '',
            status: deployment.status,
            last_job_id: null,
            last_execution: null,
            created_at: deployment.created_at,
            updated_at: deployment.updated_at,
          },
        ]
      : [];

  if (!targets.length) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment targets configured.</p>;
  }

  return (
    <div className="mt-4 grid gap-2">
      {targets.map((target) => (
        <div key={target.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div>
            <Link
              className="text-sm font-semibold text-zinc-950 hover:text-zinc-700"
              to={`/inventory/${target.server_id}`}
              onClick={(event) => event.stopPropagation()}
            >
              {target.hostname ?? target.server_id}
            </Link>
            <p className="mt-0.5 text-xs text-zinc-500">
              {formatNodeType(target.node_type)} - {target.environment ?? 'unknown'} - {target.provider ?? 'unknown'} - {formatLabel(target.readiness)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RuntimeBadge value={target.status} />
            <span className="text-xs text-zinc-500">{formatDuration(target.last_execution?.duration_seconds ?? null)}</span>
          </div>
          {target.last_execution?.error_message ? (
            <p className="basis-full text-xs text-rose-700">{target.last_execution.error_message}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function DeploymentExecutionSummary({ deployment }: { deployment: Deployment }) {
  const execution = deployment.latest_execution;
  if (!execution) {
    return <p className="mt-3 text-sm text-zinc-500">No deployment executions yet.</p>;
  }
  return (
    <div className="mt-3 rounded-md border border-zinc-200 px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-zinc-950">{formatLabel(execution.operation)} execution</span>
        <RuntimeBadge value={execution.status} />
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {execution.success_count}/{execution.target_count} succeeded
        {execution.failed_count ? `, ${execution.failed_count} failed` : ''} - {formatDuration(execution.duration_seconds)}
      </p>
      {execution.error_message ? <p className="mt-1 text-xs text-rose-700">{execution.error_message}</p> : null}
      <div className="mt-3">
        <OperationalTimeline
          activities={execution.activity_timeline}
          emptyText="No deployment runtime activity has been recorded yet."
        />
      </div>
    </div>
  );
}

function DeploymentDrawer({
  mode,
  servers,
  credentials,
  targetSelector,
  name,
  composeContent,
  envContent,
  remotePath,
  credentialRefs,
  isWorking,
  onNameChange,
  onComposeChange,
  onEnvChange,
  onRemotePathChange,
  onCredentialRefsChange,
  onTargetServerIdChange,
  onClose,
  onSave,
}: {
  mode: 'create' | 'edit';
  servers: InventoryServer[];
  credentials: Credential[];
  targetSelector: ReturnType<typeof useTargetSelection>;
  name: string;
  composeContent: string;
  envContent: string;
  remotePath: string;
  credentialRefs: Array<{ key: string; credentialId: string }>;
  isWorking: boolean;
  onNameChange: (value: string) => void;
  onComposeChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onRemotePathChange: (value: string) => void;
  onCredentialRefsChange: (value: Array<{ key: string; credentialId: string }>) => void;
  onTargetServerIdChange: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 overflow-hidden bg-zinc-950/40 p-3 sm:p-5">
      <aside className="mx-auto flex h-full w-[min(100%,56rem)] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-md bg-white shadow-xl sm:max-w-[calc(100vw-2.5rem)]">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-zinc-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">
              {mode === 'edit' ? 'Edit deployment' : 'Create deployment'}
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              Compose content, target host, and runtime secrets stay in the existing deployment
              workflow.
            </p>
          </div>
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 text-zinc-600 hover:bg-zinc-50"
            type="button"
            onClick={onClose}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="grid min-w-0 flex-1 gap-4 overflow-y-auto overflow-x-hidden p-5">
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Deployment name</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
            />
          </label>
          <div className="min-w-0">
            <TargetSelector
              servers={servers}
              eligibility="deployments"
              selection={targetSelector.selection}
              filters={targetSelector.filters}
              title="Deployment target"
              description="Select the inventory host that will run this Compose service."
              onFiltersChange={targetSelector.setFilters}
              onSelectionChange={(selection) => {
                targetSelector.setMode(selection.mode);
                targetSelector.setSelectedId(selection.selectedId);
                targetSelector.setSelectedIds(selection.selectedIds);
                onTargetServerIdChange(selection.selectedId);
              }}
            />
          </div>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Compose YAML</span>
            <textarea
              className="mt-2 min-h-72 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={composeContent}
              onChange={(event) => onComposeChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Remote base path</span>
            <input
              className="mt-2 h-10 w-full rounded-md border border-zinc-300 px-3 font-mono text-sm"
              placeholder={defaultRemotePath}
              value={remotePath}
              onChange={(event) => onRemotePathChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-zinc-950">Environment file</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-md border border-zinc-300 p-3 font-mono text-sm"
              value={envContent}
              onChange={(event) => onEnvChange(event.target.value)}
            />
          </label>
          <section className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-zinc-950">Credential-backed env</span>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
                type="button"
                onClick={() =>
                  onCredentialRefsChange([
                    ...credentialRefs,
                    { key: '', credentialId: credentials[0]?.id ?? '' },
                  ])
                }
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                Add secret
              </button>
            </div>
            {credentialRefs.length ? (
              <div className="space-y-2">
                {credentialRefs.map((item, index) => (
                  <div key={index} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                    <input
                      className="h-10 rounded-md border border-zinc-300 px-3 font-mono text-sm"
                      placeholder="ENV_KEY"
                      value={item.key}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, key: event.target.value } : row,
                          ),
                        )
                      }
                    />
                    <select
                      className="h-10 rounded-md border border-zinc-300 px-3 text-sm"
                      value={item.credentialId}
                      onChange={(event) =>
                        onCredentialRefsChange(
                          credentialRefs.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, credentialId: event.target.value } : row,
                          ),
                        )
                      }
                    >
                      <option value="">Select credential</option>
                      {credentials.map((credential) => (
                        <option key={credential.id} value={credential.id}>
                          {credential.name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="inline-flex h-10 items-center justify-center rounded-md border border-rose-300 px-3 text-rose-700 hover:bg-rose-50"
                      type="button"
                      onClick={() =>
                        onCredentialRefsChange(
                          credentialRefs.filter((_, rowIndex) => rowIndex !== index),
                        )
                      }
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">
                Use credentials for tokens, passwords, and API keys that should not live in the env
                editor.
              </p>
            )}
          </section>
          <div className="flex justify-end gap-2 border-t border-zinc-200 pt-4">
            <button
              className="inline-flex h-10 items-center rounded-md border border-zinc-300 px-4 text-sm font-semibold text-zinc-700 hover:bg-zinc-50"
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="inline-flex h-10 items-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white disabled:bg-zinc-300"
              disabled={isWorking}
              type="button"
              onClick={onSave}
            >
              {mode === 'edit' ? 'Save changes' : 'Create deployment'}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-zinc-950">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-zinc-800">{value}</p>
    </div>
  );
}

function Chip({ icon: Icon, label }: { icon: typeof FileText; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </span>
  );
}

function OutputPanel({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold text-zinc-950">{title}</h3>
      <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-zinc-800 bg-zinc-950 p-4 text-xs leading-5 text-zinc-100 shadow-inner">
        {value}
      </pre>
    </section>
  );
}

function deploymentPathPreview(deployment: Deployment): string {
  const safeName = deployment.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
  return `${deployment.remote_path?.replace(/\/$/, '')}/${safeName}`;
}

function statusLabel(status: DeploymentStatus | 'all'): string {
  if (status === 'draft') return 'created';
  return formatLabel(status);
}

function normalizeStatus(status: DeploymentStatus): DeploymentStatus {
  if (status === 'created') return 'draft';
  if (status === 'deployed') return 'running';
  return status;
}

function ActionButton({
  icon: Icon,
  label,
  disabled,
  tone = 'default',
  onClick,
}: {
  icon: typeof Play;
  label: string;
  disabled: boolean;
  tone?: 'default' | 'danger';
  onClick: () => void;
}) {
  const className =
    tone === 'danger'
      ? 'inline-flex h-9 items-center gap-2 rounded-md border border-rose-300 px-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50'
      : 'inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50';
  return (
    <button className={className} disabled={disabled} type="button" onClick={onClick}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}

function formatDuration(seconds: number | null): string {
  return seconds === null ? 'unknown' : formatDurationSeconds(seconds);
}

function formatLabel(value: string): string {
  return formatOperationalLabel(value);
}

function formatNodeType(value: string | null): string {
  if (value === 'lxc') return 'LXC';
  if (value === 'vm') return 'VM';
  return value ? formatLabel(value) : 'Unknown';
}

function formatJobsOutput(jobs: Job[]): string {
  if (!jobs.length) return '';
  return jobs
    .map((job) =>
      [
        `===== ${job.operation_type} (${job.status}) =====`,
        job.stdout ?? '',
        job.stderr ?? '',
      ]
        .filter(Boolean)
        .join('\n'),
    )
    .join('\n\n');
}

function selectedDeploymentSummary(deployment: Deployment | null): string {
  if (!deployment) return 'Select a deployment to inspect runtime state.';
  const execution = deployment.latest_execution;
  return [
    `name: ${deployment.name}`,
    `status: ${statusLabel(normalizeStatus(deployment.status))}`,
    `targets: ${deployment.targets.length ? deployment.targets.map((target) => `${target.hostname ?? target.server_id}=${target.status}`).join(', ') : deployment.target_hostname ?? deployment.target_server_id ?? 'none'}`,
    `latest execution: ${execution ? `${execution.operation} ${execution.status} (${execution.success_count}/${execution.target_count} succeeded)` : 'none'}`,
    `ports: ${deployment.ports.length ? deployment.ports.join(', ') : 'none'}`,
    `compose source: ${deployment.compose_source}`,
    `health: ${deployment.health_state}`,
    `sync: ${deployment.sync_status}`,
    `remote path: ${deployment.remote_path ?? 'none'}`,
  ].join('\n');
}

````

