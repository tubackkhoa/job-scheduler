import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest
from unittest.mock import patch
from datetime import datetime

from log_service import LogService  # Replace with your module import
from log_handler import LogEvent


@pytest.fixture
def temp_log_dir():
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


def test_write_log_creates_log_file(temp_log_dir):
    service = LogService(log_dir=temp_log_dir, max_file_size=1024, max_files=2, useIndexer=False)
    job_id = "job1"
    event: LogEvent = {
        "job_id": job_id,
        "level": "INFO",
        "message": "Test message",
        "created_at": datetime.now(),
        "type": "log",
    }
    service.write_log(event)

    log_file = Path(temp_log_dir) / f"{job_id}.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "Test message" in content


def test_log_rotation_triggered(temp_log_dir):
    max_size = 100
    service = LogService(
        log_dir=temp_log_dir, max_file_size=max_size, max_files=2, useIndexer=False
    )
    job_id = "job2"

    large_event: LogEvent = {
        "job_id": job_id,
        "level": "INFO",
        "message": "X" * (max_size + 10),
        "created_at": datetime.now(),
        "type": "log",
    }
    service.write_log(large_event)

    trigger_event: LogEvent = {
        "job_id": job_id,
        "level": "INFO",
        "message": "Trigger rotation",
        "created_at": datetime.now(),
        "type": "log",
    }
    service.write_log(trigger_event)

    rotated_files = list(Path(temp_log_dir).glob(f"{job_id}.*.log.gz"))
    assert rotated_files, "Rotation files should exist"
    assert len(rotated_files) <= service.max_files


def test_read_log_file_multiline(temp_log_dir):
    service = LogService(log_dir=temp_log_dir)
    job_id = "job3"
    log_file = Path(temp_log_dir) / f"{job_id}.log"
    log_content = (
        "2026-01-12 15:00:00 [INFO] First line\n"
        "continuation line\n"
        "2026-01-12 15:01:00 [ERROR] Another log\n"
    )
    log_file.write_text(log_content)

    entries = service._read_log_file(log_file)
    assert len(entries) == 2
    assert "continuation line" in entries[0]["message"]
    assert entries[0]["level"] == "INFO"
    assert entries[1]["level"] == "ERROR"


def test_search_logs_file_mode(temp_log_dir):
    service = LogService(log_dir=temp_log_dir, useIndexer=False)
    job_id = "job4"
    log_file = Path(temp_log_dir) / f"{job_id}.log"

    log_lines = "\n".join(
        [
            "2026-01-12 10:00:00 [INFO] Start log",
            "2026-01-12 10:01:00 [WARN] Warning message",
            "2026-01-12 10:02:00 [INFO] Another info",
        ]
    )
    log_file.write_text(log_lines)

    result = service.search_logs(job_id, search_text="warn", limit=10)
    assert result["filtered"] == 1
    assert "Warning message" in result["logs"][0]["message"]

    result_all = service.search_logs(job_id, limit=10)
    assert result_all["filtered"] == 3


def test_cleanup_old_logs(temp_log_dir):
    service = LogService(log_dir=temp_log_dir, retention_days=0)
    job_id = "job5"
    log_file = Path(temp_log_dir) / f"{job_id}.log"
    log_file.write_text("Some log data")

    old_time = time.time() - (2 * 24 * 60 * 60)  # 2 days ago
    os.utime(log_file, (old_time, old_time))

    deleted = service.cleanup_old_logs()
    assert deleted >= 1
    assert not log_file.exists()


@patch("log_service.LogIndexer")
def test_clear_logs_file_mode(mock_log_indexer, temp_log_dir):
    service = LogService(log_dir=temp_log_dir, useIndexer=False)
    job_id = "job6"
    log_file = Path(temp_log_dir) / f"{job_id}.log"
    log_file.write_text("Old log data")

    result = service.clear_logs(job_id)
    assert result["success"] is True
    assert log_file.read_text() == ""


@patch("log_service.LogIndexer")
def test_clear_logs_use_indexer_success(mock_log_indexer):
    instance = mock_log_indexer.return_value
    instance.rotate_job_logs_by_count.return_value = None

    service = LogService(useIndexer=True)
    service.log_indexer = instance

    result = service.clear_logs("job7")
    instance.rotate_job_logs_by_count.assert_called_once()
    assert result["success"] is True


@patch("log_service.LogIndexer")
def test_clear_logs_use_indexer_error(mock_log_indexer):
    instance = mock_log_indexer.return_value
    instance.rotate_job_logs_by_count.side_effect = Exception("fail")

    service = LogService(useIndexer=True)
    service.log_indexer = instance

    result = service.clear_logs("job8")
    assert result["success"] is False
    assert result["error"]
