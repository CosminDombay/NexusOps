from backend.app.common.repository import BaseRepository
from backend.app.modules.provisioning.models import ProvisioningRequest, VirtualMachine

from sqlalchemy import select
from uuid import UUID


class VirtualMachineRepository(BaseRepository[VirtualMachine]):
    pass


class ProvisioningRequestRepository(BaseRepository[ProvisioningRequest]):
    async def create(self, request: ProvisioningRequest) -> ProvisioningRequest:
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_by_id(self, request_id: UUID) -> ProvisioningRequest | None:
        result = await self.session.execute(
            select(ProvisioningRequest).where(ProvisioningRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[ProvisioningRequest]:
        result = await self.session.execute(
            select(ProvisioningRequest).order_by(ProvisioningRequest.created_at.desc())
        )
        return list(result.scalars().all())
