import textwrap
import pytest
from helper import extract_job_id
import gzip
from log_indexer import (
    LogIndexer,
    iter_log_lines,
)  # replace your_module accordingly


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_logs.db"
    return str(db_path)


@pytest.fixture
def log_indexer(temp_db):
    return LogIndexer(db_path=temp_db)


def test_extract_job_id():
    filename = "job-scheduler.job.123"
    assert extract_job_id(filename) == 123

    with pytest.raises(ValueError):
        extract_job_id("invalid_filename.log")


def test_insert_and_search(log_indexer):
    job_id = 1
    log_indexer.insert_log(job_id, "INFO", "First log")
    log_indexer.insert_log(job_id, "ERROR", "Second log")

    results = log_indexer.search_logs(job_id, "First")
    assert len(results) == 1
    assert results[0]["message"] == "First log"

    results = log_indexer.search_logs(job_id, "log")
    assert len(results) >= 2


def test_search_with_following(log_indexer):
    job_id = 2
    for i in range(5):
        log_indexer.insert_log(job_id, "INFO", f"Message {i}")

    groups = log_indexer.search_logs_with_following(job_id, "Message 1", following_lines=2)
    assert len(groups) == 1
    group = groups[0]
    assert group["match"]["message"] == "Message 1"
    assert len(group["following"]) == 2
    assert group["following"][0]["message"] == "Message 2"


def test_rotate_job_logs_by_count(log_indexer):
    job_id = 3
    for i in range(10):
        log_indexer.insert_log(job_id, "INFO", f"Log {i}")

    # Keep only 5 latest logs
    log_indexer.rotate_job_logs_by_count(job_id, keep=5)

    logs = log_indexer.get_latest_logs(job_id, limit=10, order_desc=True)
    assert len(logs) == 5
    assert logs[0]["message"] == "Log 9"
    assert logs[-1]["message"] == "Log 5"


def test_import_log_files(tmp_path, log_indexer):
    # Create a sample log file
    log_file = tmp_path / "job-scheduler.job.42.log"
    content = textwrap.dedent(
        """
    2026-01-12 10:00:00 [INFO] Starting job
    2026-01-12 10:01:00 [ERROR] Something failed
    Invalid line without timestamp or level
    """
    )

    log_file.write_text(content.strip())

    log_indexer.import_log_files(str(log_file))

    logs = log_indexer.get_latest_logs(42, limit=10)
    messages = [log["message"] for log in logs]

    assert "Starting job" in messages
    assert "Something failed" in messages
    assert "Invalid line without timestamp or level" in messages


def test_iter_log_lines_plain_and_gz(tmp_path):
    # Plain text file
    txt_file = tmp_path / "logfile.log"
    lines = ["line1", "line2", "", "line3"]
    txt_file.write_text("\n".join(lines))

    read_lines = list(iter_log_lines(txt_file))
    assert read_lines == ["line1", "line2", "line3"]

    # Gzipped file
    gz_file = tmp_path / "logfile.log.gz"
    with gzip.open(gz_file, "wt") as f:
        f.write("\n".join(lines))

    read_lines_gz = list(iter_log_lines(gz_file))
    assert read_lines_gz == ["line1", "line2", "line3"]
