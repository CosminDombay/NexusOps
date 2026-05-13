from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.jobs.models import Job


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
