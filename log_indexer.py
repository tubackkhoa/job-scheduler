import gzip
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Dict, Optional


# Match:
# 2025-12-31 08:02:37 [INFO] message
LOG_LINE_RE = re.compile(
    r"""
    ^
    (?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})
    \s+\[(?P<level>[A-Z]+)\]
    \s+(?P<msg>.*)
    $
    """,
    re.VERBOSE,
)


def iter_log_lines(path: Path) -> Iterable[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line


def extract_job_id(filename: str) -> str:
    # job-scheduler.job.19.log
    # job-scheduler.job.3.20251227_090304.log.gz
    return filename.split(".log", 1)[0]


class LogIndexer:
    def __init__(self, db_path="logs_index.db"):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = sqlite3.connect(str(db_path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA temp_store=MEMORY")
        self.db.execute("PRAGMA cache_size=-100000")  # ~100MB

        self._init_schema()

    def _init_schema(self):
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS logs_fts
            USING fts5(
                job_id,
                level,
                message,
                content='logs',
                content_rowid='id',
                tokenize='unicode61'
            );

            -- ✅ per-job fast tailing
            CREATE INDEX IF NOT EXISTS idx_logs_job_id_id
            ON logs(job_id, id DESC);
            """
        )
        self.db.commit()

    def rotate_job_logs_by_count(
        self,
        job_id: str,
        keep: int = 100_000,
    ):
        with self.db:
            self.db.execute(
                """
                DELETE FROM logs
                WHERE job_id = ?
                AND id NOT IN (
                    SELECT id
                    FROM logs
                    WHERE job_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (job_id, job_id, keep),
            )

            # keep FTS in sync
            self.db.execute(
                """
                DELETE FROM logs_fts
                WHERE rowid NOT IN (SELECT id FROM logs)
                """
            )

    # ------------------------------------------------------------
    # Insert log (indexed immediately)
    # ------------------------------------------------------------
    def insert_log(
        self,
        job_id: str,
        level: str,
        message: str,
        timestamp: Optional[str] = None,
    ):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.db:
            cur = self.db.execute(
                """
                INSERT INTO logs (job_id, timestamp, level, message)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, timestamp, level, message),
            )

            self.db.execute(
                """
                INSERT INTO logs_fts (rowid, job_id, level, message)
                VALUES (?, ?, ?, ?)
                """,
                (cur.lastrowid, job_id, level, message),
            )

    # ------------------------------------------------------------
    # FAST FTS SEARCH
    # ------------------------------------------------------------
    def search_logs(
        self,
        job_id: str,
        query: str,
        limit: int = 1000,
    ):
        rows = self.db.execute(
            """
            SELECT
                l.job_id,
                l.timestamp,
                l.level,
                l.message
            FROM logs_fts
            JOIN logs l ON l.id = logs_fts.rowid
            WHERE logs_fts.job_id = ?
            AND logs_fts MATCH ?
            ORDER BY l.id
            LIMIT ?
            """,
            (job_id, query, limit),
        ).fetchall()

        return [
            {
                "job_id": r[0],
                "timestamp": r[1],
                "level": r[2],
                "message": r[3],
            }
            for r in rows
        ]

    def import_log_files(self, filename: str):
        path = Path(filename)

        job_id = extract_job_id(path.name)

        for line in iter_log_lines(path):
            m = LOG_LINE_RE.match(line)
            if not m:
                # fallback: store raw line
                self.insert_log(
                    job_id=job_id,
                    level="INFO",
                    message=line,
                )
                continue

            self.insert_log(
                job_id=job_id,
                timestamp=m.group("ts"),
                level=m.group("level"),
                message=m.group("msg"),
            )

    def get_logs_after_id(
        self,
        last_id: int = 0,
        job_id: str | None = None,
        limit: int = 1000,
    ):
        if job_id:
            rows = self.db.execute(
                """
                SELECT id, job_id, timestamp, level, message
                FROM logs
                WHERE id > ? AND job_id = ?
                ORDER BY id
                LIMIT ?
                """,
                (last_id, job_id, limit),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT id, job_id, timestamp, level, message
                FROM logs
                WHERE id > ?
                ORDER BY id
                LIMIT ?
                """,
                (last_id, limit),
            ).fetchall()

        return [
            {
                "id": r[0],
                "job_id": r[1],
                "timestamp": r[2],
                "level": r[3],
                "message": r[4],
            }
            for r in rows
        ]


log_indexer = LogIndexer("data/log_indexer.db")

# log_indexer.import_log_files(
#     filename="logs/job-scheduler.job.19.log",
# )

# # after importing logs for a job
# log_indexer.rotate_job_logs_by_count(
#     job_id="job-scheduler.job.19",
#     keep=100_000,
# )

import time

start = time.time()
logs = log_indexer.get_logs_after_id(
    job_id="job-scheduler.job.19",
)
elapsed = time.time() - start

for log in logs:
    print(f"{log['timestamp']} [{log['level']}] {log['message']}")
    last_id = log["id"]

print("elapsed", elapsed, "s")

start = time.time()
matches = log_indexer.search_logs(
    job_id="job-scheduler.job.19", query="Loaded model config from database", limit=1000
)
elapsed = time.time() - start
for log in matches:
    print(log)
print("elapsed", elapsed, "s")
