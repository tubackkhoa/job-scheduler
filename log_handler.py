import asyncio
import logging
from math import log
from typing import Any, Callable, Optional
from log_service import LogService


class JobLogHandler(logging.Handler):
    def __init__(
        self,
        log_callback: Callable[[Any], Any],
        loop: asyncio.AbstractEventLoop,
        log_service: Optional[LogService] = None,
    ):
        super().__init__()
        self.log_callback = log_callback
        self.log_service = log_service
        self.loop = loop
        self.queue: asyncio.Queue = asyncio.Queue()

        # single drain task → preserves order
        self.loop.create_task(self._drain())

    async def _drain(self):
        while True:
            log_event = await self.queue.get()
            try:
                # Write to file service (synchronous, but fast)
                if self.log_service:
                    try:
                        self.log_service.write_log(
                            log_event["job_id"],
                            log_event["level"],
                            log_event["message"],
                        )
                    except Exception:
                        pass  # Don't fail on file write errors

                # Send via websocket
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
