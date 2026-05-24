import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class RuntimeTaskMetadata:
    task_id: str
    name: str
    owner: str
    execution_origin: str
    correlation_id: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str = "queued"
    error: str | None = None

    @property
    def runtime_duration(self) -> float | None:
        if self.started_at is None:
            return None
        finished_at = self.finished_at or datetime.now(UTC)
        return max(0.0, (finished_at - self.started_at).total_seconds())


class AsyncTaskQueue:
    """In-process async task tracker for MVP orchestration work."""

    def __init__(self) -> None:
        self._tasks: dict[asyncio.Task, RuntimeTaskMetadata] = {}
        self._history: list[RuntimeTaskMetadata] = []

    def submit(
        self,
        awaitable: Awaitable,
        *,
        name: str = "anonymous-task",
        owner: str = "system",
        execution_origin: str = "system",
        correlation_id: str | None = None,
    ) -> asyncio.Task:
        metadata = RuntimeTaskMetadata(
            task_id=str(uuid4()),
            name=name,
            owner=owner,
            execution_origin=execution_origin,
            correlation_id=correlation_id or str(uuid4()),
            queued_at=datetime.now(UTC),
        )
        task = asyncio.create_task(self._run(awaitable, metadata))
        self._tasks[task] = metadata
        task.add_done_callback(self._finalize)
        return task

    def list_metadata(self) -> list[RuntimeTaskMetadata]:
        return [*self._tasks.values(), *self._history[-100:]]

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks.keys(), return_exceptions=True)

    async def cancel_all(self) -> None:
        for task, metadata in list(self._tasks.items()):
            metadata.status = "cancel_requested"
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.keys(), return_exceptions=True)
        self._tasks.clear()

    async def cleanup_stale(self, *, stale_after_seconds: int = 3600) -> None:
        now = datetime.now(UTC)
        for task, metadata in list(self._tasks.items()):
            if task.done():
                self._tasks.pop(task, None)
                continue
            timestamp = metadata.started_at or metadata.queued_at
            if (now - timestamp).total_seconds() > stale_after_seconds:
                metadata.status = "stale"
                task.cancel()

    async def _run(self, awaitable: Awaitable, metadata: RuntimeTaskMetadata):
        metadata.started_at = datetime.now(UTC)
        metadata.status = "running"
        try:
            result = await awaitable
            metadata.status = "success"
            return result
        except asyncio.CancelledError:
            metadata.status = "cancelled"
            raise
        except Exception as exc:
            metadata.status = "failed"
            metadata.error = str(exc)
            raise
        finally:
            metadata.finished_at = datetime.now(UTC)

    def _finalize(self, task: asyncio.Task) -> None:
        metadata = self._tasks.pop(task, None)
        if metadata is not None:
            self._history.append(metadata)
            self._history = self._history[-100:]


task_queue = AsyncTaskQueue()
