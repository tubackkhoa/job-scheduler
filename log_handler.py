import asyncio
import logging
from typing import Any, Callable


class JobLogHandler(logging.Handler):
    def __init__(
        self,
        log_callback: Callable[[Any], Any],
        loop: asyncio.AbstractEventLoop,
        max_inflight=500,
    ):
        super().__init__()
        self.queue = asyncio.Queue()
        self.log_callback = log_callback
        self.sem = asyncio.Semaphore(max_inflight)
        loop.create_task(self._drain())

    async def _drain(self):
        while True:
            log_event = await self.queue.get()
            await self.sem.acquire()
            asyncio.create_task(self._send(log_event))
            self.queue.task_done()

    async def _send(self, log_event):
        try:
            await self.log_callback(log_event)  # send_log
        except Exception:
            pass
        finally:
            self.sem.release()

    def emit(self, record: logging.LogRecord):
        log_entry = self.format(record)

        # Schedule async callback safely
        self.queue.put_nowait(
            {
                "job_id": record.name,
                "level": record.levelname,
                "message": log_entry,
            }
        )
