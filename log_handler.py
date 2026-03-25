import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Literal, Awaitable, TypedDict, Union


# --- TypedDict for log events ---
class LogEvent(TypedDict):
    job_id: str
    level: str
    message: str
    created_at: datetime
    type: Literal["log", "signal"]


# --- Hook type ---
LogHook = Callable[[LogEvent], Union[Awaitable[Any], Any]]


class JobLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_callbacks: list[LogHook] = []
        self.loop = asyncio.get_running_loop()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.detected_ranking_table: dict[str, bool] = {}

        # single drain task → preserves order
        self.loop.create_task(self._drain())

    # --- Hook management methods ---
    def add_hook(self, hook: LogHook):
        """Add a new log callback."""
        self.log_callbacks.append(hook)

    def remove_hook(self, hook: LogHook):
        """Remove an existing log callback, if present."""
        try:
            self.log_callbacks.remove(hook)
        except ValueError:
            pass  # ignore if hook not found

    async def _run_hooks(self, log_event: LogEvent):
        for cb in self.log_callbacks:
            result = cb(log_event)
            if asyncio.iscoroutine(result):
                await result

    async def _drain(self):
        while True:
            log_event = await self.queue.get()
            try:
                await self._run_hooks(log_event)
            except Exception:
                # never break logging flow
                pass
            finally:
                self.queue.task_done()

    def emit(self, record: logging.LogRecord):
        log_entry = self.format(record)
        created_at = datetime.fromtimestamp(record.created)

        # default event
        log_event: LogEvent = {
            "job_id": record.name,
            "level": record.levelname,
            "message": log_entry,
            "created_at": created_at,
            "type": "log",
        }

        # --- signal detection logic ---
        if self.detected_ranking_table.get(record.name):
            log_event["type"] = "signal"
            del self.detected_ranking_table[record.name]

        if "ranking table" in log_entry:
            self.detected_ranking_table[record.name] = True

        # thread-safe enqueue
        self.loop.call_soon_threadsafe(self.queue.put_nowait, log_event)
