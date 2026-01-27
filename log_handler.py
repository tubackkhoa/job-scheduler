import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Optional
from log_service import LogService
from models import DAO
from helpers import extract_job_id_int


class JobLogHandler(logging.Handler):
    def __init__(
        self,
        log_callback: Callable[[Any], Any],
        loop: asyncio.AbstractEventLoop,
        log_service: Optional[LogService] = None,
        dao: Optional[DAO] = None,
    ):
        super().__init__()
        self.log_callback = log_callback
        self.log_service = log_service
        self.dao = dao
        self.loop = loop
        self.queue: asyncio.Queue = asyncio.Queue()
        self.signal_queue: asyncio.Queue = asyncio.Queue()
        self.detected_ranking_table: dict[str, bool] = {}

        # single drain task → preserves order
        self.loop.create_task(self._drain())
        if self.dao:
            self.loop.create_task(self._drain_signals())

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

    async def _drain_signals(self):
        while True:
            if not self.dao:
                continue
            signal_data = await self.signal_queue.get()
            print("signal_data: ", signal_data)
            try:
                await self.loop.run_in_executor(
                    None,
                    self.dao.save_signal_message,
                    extract_job_id_int(signal_data["job_id"]),
                    signal_data["message"],
                    signal_data["created_at"],
                )
            except Exception as e:
                print(f"Error saving signal message: {e}")
            finally:
                self.signal_queue.task_done()

    def emit(self, record: logging.LogRecord):
        log_entry = self.format(record)
        if self.detected_ranking_table.get(record.name):
            signal_data = {
                "job_id": record.name,
                "message": log_entry,
                "created_at": datetime.fromtimestamp(record.created),
            }
            self.loop.call_soon_threadsafe(
                self.signal_queue.put_nowait,
                signal_data,
            )
            del self.detected_ranking_table[record.name]

        if "ranking table ::::" in log_entry:
            self.detected_ranking_table[record.name] = True

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
