from uuid import UUID

from sqlalchemy import func, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.deployments.models import (
    Deployment,
    DeploymentRevision,
    DeploymentTarget,
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
