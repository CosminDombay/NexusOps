from sqlalchemy.exc import IntegrityError

from backend.app.modules.variables.models import Variable
from backend.app.modules.variables.repository import VariableRepository
from backend.app.modules.variables.schemas import VariableCreate, VariableRead


class VariableConflictError(Exception):
    """Raised when a variable key is already in use."""


class VariableService:
    def __init__(self, repository: VariableRepository) -> None:
        self.repository = repository

    async def list_variables(self) -> list[VariableRead]:
        return [VariableRead.model_validate(variable) for variable in await self.repository.list()]

    async def create_variable(self, payload: VariableCreate) -> VariableRead:
        variable = Variable(**payload.model_dump())
        try:
            variable = await self.repository.create(variable)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise VariableConflictError("Variable key already exists") from exc
        return VariableRead.model_validate(variable)
