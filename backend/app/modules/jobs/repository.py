from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.jobs.models import CustomOperationalAction, Job


class JobRepository(BaseRepository[Job]):
    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Job]:
        result = await self.session.execute(select(Job).order_by(Job.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_target(self, target_server_id: UUID) -> list[Job]:
        result = await self.session.execute(
            select(Job)
            .where(Job.target_server_id == target_server_id)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())


class CustomOperationalActionRepository(BaseRepository[CustomOperationalAction]):
    async def create(self, action: CustomOperationalAction) -> CustomOperationalAction:
        self.session.add(action)
        await self.session.flush()
        await self.session.refresh(action)
        return action

    async def get_by_slug(self, slug: str) -> CustomOperationalAction | None:
        result = await self.session.execute(select(CustomOperationalAction).where(CustomOperationalAction.slug == slug))
        return result.scalar_one_or_none()

    async def list(self) -> list[CustomOperationalAction]:
        result = await self.session.execute(
            select(CustomOperationalAction).order_by(CustomOperationalAction.category, CustomOperationalAction.name)
        )
        return list(result.scalars().all())

    async def delete(self, action: CustomOperationalAction) -> None:
        await self.session.delete(action)
