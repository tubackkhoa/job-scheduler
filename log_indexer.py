import gzip
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Iterable, Optional


# Match log lines:
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

# Extract numeric job_id from filename, e.g. job-scheduler.job.123 → 123
JOB_ID_RE = re.compile(r"job-scheduler\.job\.(\d+)")


def iter_log_lines(path: Path) -> Iterable[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line


def extract_job_id(filename: str) -> int:
    m = JOB_ID_RE.search(filename)
    if not m:
        raise ValueError(f"Cannot extract job_id from filename: {filename}")
    return int(m.group(1))


class LogIndexer:
    def __init__(self, db_path="logs_index.db", rotate_size=100_000):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.rotate_size = rotate_size
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
                job_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS logs_fts
            USING fts5(
                job_id UNINDEXED,
                level,
                message,
                content='logs',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE INDEX IF NOT EXISTS idx_logs_job_id_id
            ON logs(job_id, id DESC);
            """
        )
        self.db.commit()

    def rotate_job_logs_by_count(
        self,
        job_id: int,
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

    def insert_log(
        self,
        job_id: int,
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
        if cur.lastrowid:
            # cheap trigger, no DB scan
            if cur.lastrowid % int(self.rotate_size * 1.5) == 0:
                self.rotate_job_logs_by_count(
                    job_id=job_id,
                    keep=self.rotate_size,
                )

    def search_logs(
        self,
        job_id: int,
        query: str,
        limit: int = 1000,
    ):
        # Phase 1: FTS lookup (rowids only, very fast)
        rowids = [
            r[0]
            for r in self.db.execute(
                """
                SELECT rowid
                FROM logs_fts
                WHERE job_id = ?
                AND logs_fts MATCH ?
                ORDER BY rowid
                LIMIT ?
                """,
                (job_id, query, limit),
            )
        ]

        if not rowids:
            return []

        # Phase 2: fetch actual rows by PRIMARY KEY
        placeholders = ",".join("?" * len(rowids))
        rows = self.db.execute(
            f"""
            SELECT job_id, timestamp, level, message
            FROM logs
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            rowids,
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
        job_id: Optional[int] = None,
        limit: int = 1000,
    ):
        if job_id is not None:
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


import time

start = time.time()
matches = log_indexer.search_logs(job_id=19, query="Loaded model config from database", limit=100)
elapsed = time.time() - start
# for log in matches:
#     print(log)
print("elapsed", elapsed, "s")


# cd log_indexer_rs && maturin build --release && pip install ./target/wheels/log_indexer_rs-0.1.0-cp312-cp312-macosx_11_0_arm64.whl
import log_indexer_rs

log_indexer = log_indexer_rs.LogIndexer("data/log_indexer.db")
start = time.time()
logs = log_indexer.search_logs(job_id=19, query="Loaded model config from database", limit=100)
elapsed = time.time() - start
# for log in logs:
#     print(log)
print("elapsed", elapsed, "s")
