import gzip
import logging
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
    def __init__(self, db_path="logs_index.db", keep_size=100_000):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.keep_size = keep_size
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

    def rebuild_fts_index(self):
        # Rebuild the FTS index if needed
        self.db.execute("INSERT INTO logs_fts(logs_fts) VALUES('rebuild')")
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
        # Rebuild the FTS index to keep it consistent after deletes
        self.rebuild_fts_index()

    def get_log_count(self, job_id: int) -> int:
        """Get total number of logs for a specific job."""
        result = self.db.execute(
            "SELECT COUNT(*) FROM logs WHERE job_id = ?",
            (job_id,)
        ).fetchone()
        return result[0] if result else 0

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
            return cur.lastrowid

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

    def search_logs_with_following(
        self,
        job_id: int,
        query: str,
        following_lines: int = 0,
        limit: int = 1000,
    ):
        # --------------------------------------------------
        # Phase 1: find matching rowids
        # --------------------------------------------------
        match_ids = [
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
        

        if not match_ids:
            return []

        min_id = match_ids[0]
        max_id = match_ids[-1] + following_lines

        # --------------------------------------------------
        # Phase 2: single contiguous scan
        # --------------------------------------------------
        rows = self.db.execute(
            """
            SELECT id, job_id, timestamp, level, message
            FROM logs
            WHERE job_id = ?
            AND id BETWEEN ? AND ?
            ORDER BY id
            """,
            (job_id, min_id, max_id),
        ).fetchall()

        # Build id → log mapping
        log_map = {
            r[0]: {
                "id": r[0],
                "job_id": r[1],
                "timestamp": r[2],
                "level": r[3],
                "message": r[4],
            }
            for r in rows
        }

        # --------------------------------------------------
        # Phase 3: group per match
        # --------------------------------------------------
        groups = []
        for match_id in match_ids:
            if match_id not in log_map:
                continue

            group = {
                "match": log_map[match_id],
                "following": [],
            }

            for i in range(1, following_lines + 1):
                next_id = match_id + i
                if next_id in log_map:
                    group["following"].append(log_map[next_id])

            groups.append(group)

        return groups

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

    def get_latest_logs(
        self,
        job_id: int,
        limit: int = 1000,
        order_desc: bool = True,
    ):
        """
        Get N latest logs for a job_id.
        Args:
            job_id: Job identifier
            limit: Number of latest logs to retrieve
            order_desc: If True, return newest first (DESC), else oldest first (ASC)
        Returns: List of log dictionaries
        """
        order_clause = "DESC" if order_desc else "ASC"
        rows = self.db.execute(
            f"""
            SELECT id, job_id, timestamp, level, message
            FROM logs
            WHERE job_id = ?
            ORDER BY id {order_clause}
            LIMIT ?
            """,
            (job_id, limit),
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


# log_indexer = LogIndexer("data/log_indexer.db")

# Example usage:
# log_indexer.import_log_files(filename="logs/job-scheduler.job.16.log")

# log_indexer.insert_log(19, "INFO", "pham thanh tu is working")


# import time


# log_indexer = LogIndexer("data/log_indexer.db")

# # Example usage:
# log_indexer.import_log_files(filename="logs/job-scheduler.job.16.log")


# import time


# def print_log(log):
#     print(f"{log['timestamp']} {log['message']}")





# def print_following_log(log):
#     print_log(log["match"])
#     for sub_log in log["following"]:
#         print_log(sub_log)


# start = time.time()
# matches = log_indexer.search_logs_with_following(
#     job_id=16, query="Ranking completed", limit=2, following_lines=11
# )



# elapsed = time.time() - start
# for log in matches:
#     print_following_log(log)

# print("elapsed", elapsed, "s")
