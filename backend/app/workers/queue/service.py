import asyncio
from collections.abc import Awaitable


class AsyncTaskQueue:
    """In-process async task tracker for MVP orchestration work."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def submit(self, awaitable: Awaitable) -> asyncio.Task:
        task = asyncio.create_task(awaitable)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


task_queue = AsyncTaskQueue()
