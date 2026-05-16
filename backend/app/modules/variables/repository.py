from uuid import UUID

from sqlalchemy import select

from backend.app.common.repository import BaseRepository
from backend.app.modules.variables.models import Variable


class VariableRepository(BaseRepository[Variable]):
    async def create(self, variable: Variable) -> Variable:
        self.session.add(variable)
        await self.session.flush()
        await self.session.refresh(variable)
        return variable

    async def get_by_id(self, variable_id: UUID) -> Variable | None:
        result = await self.session.execute(select(Variable).where(Variable.id == variable_id))
        return result.scalar_one_or_none()

    async def list(self) -> list[Variable]:
        result = await self.session.execute(select(Variable).order_by(Variable.key.asc()))
        return list(result.scalars().all())
