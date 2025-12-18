import asyncio
import logging


class JobLogHandler(logging.Handler):
    def __init__(self, log_callback, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.log_callback = log_callback
        self.loop = loop

    def emit(self, record: logging.LogRecord):
        if self.log_callback is None:
            return

        log_entry = self.format(record)

        log_event = {
            "job_id": record.name,
            "level": record.levelname,
            "message": log_entry,
        }

        # Schedule async callback safely
        self.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.log_callback(log_event),
        )
