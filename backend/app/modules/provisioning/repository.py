from __future__ import annotations

from sqlalchemy import select
from uuid import UUID

from backend.app.common.repository import BaseRepository
from backend.app.modules.provisioning.models import (
    ProvisioningBlueprint,
    ProvisioningBatch,
    ProvisioningRequest,
    VirtualMachine,
)


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

    async def list_by_batch(self, batch_id: UUID) -> list[ProvisioningRequest]:
        result = await self.session.execute(
            select(ProvisioningRequest)
            .where(ProvisioningRequest.batch_id == batch_id)
            .order_by(ProvisioningRequest.batch_index.asc())
        )
        return list(result.scalars().all())

    async def delete(self, request: ProvisioningRequest) -> None:
        await self.session.delete(request)
        await self.session.flush()


class ProvisioningBlueprintRepository(BaseRepository[ProvisioningBlueprint]):
    async def create(self, blueprint: ProvisioningBlueprint) -> ProvisioningBlueprint:
        self.session.add(blueprint)
        await self.session.flush()
        await self.session.refresh(blueprint)
        return blueprint

    async def get_by_id(self, blueprint_id: UUID) -> ProvisioningBlueprint | None:
        result = await self.session.execute(
            select(ProvisioningBlueprint).where(ProvisioningBlueprint.id == blueprint_id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[ProvisioningBlueprint]:
        result = await self.session.execute(
            select(ProvisioningBlueprint).order_by(ProvisioningBlueprint.name.asc())
        )
        return list(result.scalars().all())

    async def delete(self, blueprint: ProvisioningBlueprint) -> None:
        await self.session.delete(blueprint)


class ProvisioningBatchRepository(BaseRepository[ProvisioningBatch]):
    async def create(self, batch: ProvisioningBatch) -> ProvisioningBatch:
        self.session.add(batch)
        await self.session.flush()
        await self.session.refresh(batch)
        return batch

    async def get_by_id(self, batch_id: UUID) -> ProvisioningBatch | None:
        result = await self.session.execute(
            select(ProvisioningBatch).where(ProvisioningBatch.id == batch_id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[ProvisioningBatch]:
        result = await self.session.execute(
            select(ProvisioningBatch).order_by(ProvisioningBatch.created_at.desc())
        )
        return list(result.scalars().all())
