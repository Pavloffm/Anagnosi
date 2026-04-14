import asyncio
from collections.abc import Callable
from typing import Any


class ConnectionManager:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._worker_task = None

    async def start(self):
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        await self._queue.join()
        self._worker_task.cancel()

    async def _worker(self):
        while True:
            func, args, kwargs, future = await self._queue.get()
            try:
                result = await func(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._queue.task_done()

    async def run(self, func: Callable, *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._queue.put((func, args, kwargs, future))
        return await future
