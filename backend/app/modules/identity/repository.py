from uuid import UUID

from sqlalchemy import delete, select

from backend.app.common.repository import BaseRepository
from backend.app.modules.identity.models import (
    IdentityExecution,
    LinuxGroup,
    LinuxUser,
    PermissionTemplate,
    SSHKey,
)


class LinuxUserRepository(BaseRepository[LinuxUser]):
    async def create(self, user: LinuxUser) -> LinuxUser:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> LinuxUser | None:
        result = await self.session.execute(select(LinuxUser).where(LinuxUser.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> LinuxUser | None:
        result = await self.session.execute(select(LinuxUser).where(LinuxUser.username == username))
        return result.scalar_one_or_none()

    async def list(self) -> list[LinuxUser]:
        result = await self.session.execute(select(LinuxUser).order_by(LinuxUser.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, user: LinuxUser) -> None:
        await self.session.execute(delete(LinuxUser).where(LinuxUser.id == user.id))


class LinuxGroupRepository(BaseRepository[LinuxGroup]):
    async def create(self, group: LinuxGroup) -> LinuxGroup:
        self.session.add(group)
        await self.session.flush()
        await self.session.refresh(group)
        return group

    async def get_by_id(self, group_id: UUID) -> LinuxGroup | None:
        result = await self.session.execute(select(LinuxGroup).where(LinuxGroup.id == group_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> LinuxGroup | None:
        result = await self.session.execute(select(LinuxGroup).where(LinuxGroup.name == name))
        return result.scalar_one_or_none()

    async def list(self) -> list[LinuxGroup]:
        result = await self.session.execute(select(LinuxGroup).order_by(LinuxGroup.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, group: LinuxGroup) -> None:
        await self.session.execute(delete(LinuxGroup).where(LinuxGroup.id == group.id))


class SSHKeyRepository(BaseRepository[SSHKey]):
    async def create(self, key: SSHKey) -> SSHKey:
        self.session.add(key)
        await self.session.flush()
        await self.session.refresh(key)
        return key

    async def get_by_id(self, key_id: UUID) -> SSHKey | None:
        result = await self.session.execute(select(SSHKey).where(SSHKey.id == key_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[SSHKey]:
        result = await self.session.execute(select(SSHKey).order_by(SSHKey.created_at.desc()))
        return list(result.scalars().all())


class PermissionTemplateRepository(BaseRepository[PermissionTemplate]):
    async def create(self, template: PermissionTemplate) -> PermissionTemplate:
        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)
        return template

    async def get_by_id(self, template_id: UUID) -> PermissionTemplate | None:
        result = await self.session.execute(
            select(PermissionTemplate).where(PermissionTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[PermissionTemplate]:
        result = await self.session.execute(
            select(PermissionTemplate).order_by(PermissionTemplate.created_at.desc())
        )
        return list(result.scalars().all())


class IdentityExecutionRepository(BaseRepository[IdentityExecution]):
    async def create(self, execution: IdentityExecution) -> IdentityExecution:
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def list(self) -> list[IdentityExecution]:
        result = await self.session.execute(
            select(IdentityExecution).order_by(IdentityExecution.created_at.desc())
        )
        return list(result.scalars().all())
