import asyncio
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from log_handler import LogEvent
from ws_manager import WSConnectionManager  # Replace with your module import


@pytest.mark.asyncio
async def test_connect_adds_websocket_and_accepts():
    manager = WSConnectionManager()
    websocket = AsyncMock(spec=WebSocket)

    job_id = "job1"
    await manager.connect(websocket, job_id)

    # websocket.accept should be called
    websocket.accept.assert_awaited_once()
    # WebSocket should be in active_connections list
    assert websocket in manager.active_connections[job_id]


def test_disconnect_removes_websocket_and_cleans_empty_list():
    manager = WSConnectionManager()
    websocket = MagicMock(spec=WebSocket)
    job_id = "job2"

    # Add websocket manually
    manager.active_connections[job_id].append(websocket)

    # Disconnect websocket
    manager.disconnect(websocket, job_id)

    # Websocket should be removed
    assert websocket not in manager.active_connections.get(job_id, [])

    # Since list is empty, job_id should be removed entirely
    assert job_id not in manager.active_connections


@pytest.mark.asyncio
async def test_send_log_sends_to_all_and_disconnects_on_exception():
    manager = WSConnectionManager()
    job_id = "job3"

    # Create two mock websockets
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)

    manager.active_connections[job_id].extend([ws1, ws2])

    # Setup ws1.send_json to succeed, ws2.send_json to raise exception
    ws1.send_json.return_value = asyncio.Future()
    ws1.send_json.return_value.set_result(None)
    ws2.send_json.side_effect = Exception("send failure")

    message: LogEvent = {
        "type": "log",
        "job_id": job_id,
        "level": "INFO",
        "message": "Test log message",
        "created_at": datetime.now(),
    }

    await manager.send_log(message)

    # ws1.send_json should be called once with payload containing level/message/time
    ws1.send_json.assert_called_once()
    sent_payload = ws1.send_json.call_args[0][0]
    assert sent_payload["level"] == message["level"]
    assert sent_payload["message"] == message["message"]
    assert "time" in sent_payload

    # ws2.send_json should be called once and raise exception
    ws2.send_json.assert_called_once()

    # ws2 should be disconnected and removed
    assert ws2 not in manager.active_connections.get(job_id, [])


@pytest.mark.asyncio
async def test_send_log_no_connections():
    manager = WSConnectionManager()
    message: LogEvent = {
        "type": "log",
        "job_id": "nonexistent_job",
        "level": "INFO",
        "message": "No connections here",
        "created_at": datetime.now(),
    }

    # Should not raise error or do anything
    await manager.send_log(message)
