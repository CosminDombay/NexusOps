from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Base repository contract for persistence-focused modules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

