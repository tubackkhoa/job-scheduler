import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from log_handler import JobLogHandler  # Replace with your actual module name
from log_service import LogService  # Your LogService import


@pytest.mark.asyncio
async def test_job_log_handler_emit_and_drain_calls_callback_and_log_service():
    loop = asyncio.get_event_loop()
    log_callback = AsyncMock()
    log_service = MagicMock(spec=LogService)

    handler = JobLogHandler()
    handler.add_hook(log_callback)
    handler.add_hook(log_service.write_log)

    # Prepare a log record
    record = logging.LogRecord(
        name="job123",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    record.levelname = "INFO"

    # Emit the log (should enqueue the event)
    handler.emit(record)

    # Wait a moment for the drain task to process the queue
    await asyncio.sleep(0.1)

    # Check that log_service.write_log was called correctly
    log_service.write_log.assert_called_once()
    called_arg = log_service.write_log.call_args[0][0]  # first positional argument
    assert called_arg["job_id"] == "job123"
    assert called_arg["level"] == "INFO"
    assert called_arg["message"] == handler.format(record)

    # Check that the async log_callback was awaited with the correct log event
    log_callback.assert_awaited_once()
    called_arg = log_callback.call_args[0][0]
    assert called_arg["job_id"] == "job123"
    assert called_arg["level"] == "INFO"
    assert called_arg["message"] == handler.format(record)


@pytest.mark.asyncio
async def test_job_log_handler_handles_log_service_exception_gracefully():
    loop = asyncio.get_event_loop()
    log_callback = AsyncMock()
    log_service = MagicMock(spec=LogService)
    # Raise exception on write_log to simulate failure
    log_service.write_log.side_effect = Exception("write failure")

    handler = JobLogHandler()
    handler.add_hook(log_callback)
    handler.add_hook(log_service.write_log)

    record = logging.LogRecord(
        name="job456",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="Error log message",
        args=(),
        exc_info=None,
    )
    record.levelname = "ERROR"

    handler.emit(record)

    # Wait for the drain to process (should NOT raise)
    await asyncio.sleep(0.1)

    # log_callback still should be called despite log_service failure
    log_callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_job_log_handler_emit_without_log_service():
    loop = asyncio.get_event_loop()
    log_callback = AsyncMock()

    handler = JobLogHandler()
    handler.add_hook(log_callback)

    record = logging.LogRecord(
        name="job789",
        level=logging.WARNING,
        pathname=__file__,
        lineno=30,
        msg="Warning log message",
        args=(),
        exc_info=None,
    )
    record.levelname = "WARNING"

    handler.emit(record)
    await asyncio.sleep(0.1)

    log_callback.assert_awaited_once()
