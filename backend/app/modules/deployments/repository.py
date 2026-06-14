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

    async def get_by_id(self, deployment_id: UUID, *, include_deleted: bool = False) -> Deployment | None:
        query = select(Deployment).where(Deployment.id == deployment_id)
        if not include_deleted:
            query = query.where(Deployment.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, *, include_deleted: bool = False, only_deleted: bool = False) -> list[Deployment]:
        query = select(Deployment)
        if only_deleted:
            query = query.where(Deployment.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.where(Deployment.deleted_at.is_(None))
        result = await self.session.execute(query.order_by(Deployment.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_server(self, server_id: UUID) -> list[Deployment]:
        result = await self.session.execute(
            select(Deployment)
            .join(DeploymentTarget, DeploymentTarget.deployment_id == Deployment.id)
            .where(DeploymentTarget.server_id == server_id)
            .where(Deployment.deleted_at.is_(None))
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

    async def delete_by_ids(self, target_ids: list[UUID]) -> None:
        if not target_ids:
            return
        await self.session.execute(delete(DeploymentTarget).where(DeploymentTarget.id.in_(target_ids)))


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

    async def delete_for_targets(self, target_ids: list[UUID]) -> None:
        if not target_ids:
            return
        await self.session.execute(delete(DeploymentTargetExecution).where(DeploymentTargetExecution.target_id.in_(target_ids)))
