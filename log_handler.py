import asyncio
import logging
from typing import Any, Callable


class JobLogHandler(logging.Handler):
    def __init__(
        self,
        log_callback: Callable[[Any], Any],
        loop: asyncio.AbstractEventLoop,
    ):
        super().__init__()
        self.log_callback = log_callback
        self.loop = loop
        self.queue: asyncio.Queue = asyncio.Queue()

        # single drain task → preserves order
        self.loop.create_task(self._drain())

    async def _drain(self):
        while True:
            log_event = await self.queue.get()
            try:
                await self.log_callback(log_event)
            except Exception:
                pass
            finally:
                self.queue.task_done()

    def emit(self, record: logging.LogRecord):

        log_entry = self.format(record)

        log_event = {
            "job_id": record.name,
            "level": record.levelname,
            "message": log_entry,
        }

        # thread-safe enqueue, non-blocking
        self.loop.call_soon_threadsafe(
            self.queue.put_nowait,
            log_event,
        )
