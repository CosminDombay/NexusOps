from abc import ABC, abstractmethod
from uuid import UUID


class JobExecutor(ABC):
    """Boundary for dispatching long-running infrastructure tasks."""

    @abstractmethod
    async def enqueue(self, job_id: UUID) -> None:
        raise NotImplementedError

