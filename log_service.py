"""
Log Service - File-based logging with rotation, retention, and search.
Inspired by pm2-logrotate: rotate by size/date, keep N files, auto-cleanup.
"""

import logging
import os
import gzip
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from threading import Lock
import json

logger = logging.getLogger(__name__)

from log_indexer import LogIndexer, extract_job_id, JOB_ID_RE

LOG_HEADER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\]\s*(.*)$")


class LogService:

    def __init__(
        self,
        log_dir: str = "logs",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 10,  # Keep last 10 rotated files
        retention_days: int = 7,  # Keep logs for 7 days
        useIndexer: bool = False,
        max_log_entries: int = 100_000,  # Max logs per job in DB mode before auto-rotation
        max_total_lines: int = 50_000,  # Max total lines per job in file mode
        rotation_keep_ratio: float = 0.5,  # Ratio of logs to keep when rotating (0.5 = 50%)
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.retention_days = retention_days
        self.max_log_entries = max_log_entries
        self.max_total_lines = max_total_lines
        self.rotation_keep_ratio = rotation_keep_ratio
        self._locks: Dict[str, Lock] = {}
        self._lock = Lock()  # For locks dict

        self.useIndexer = useIndexer
        if self.useIndexer:
            self.log_indexer = LogIndexer(f"{log_dir}/log_indexer.db")

    def _extract_job_id_int(self, job_id: str) -> int:
        """Extract numeric job_id from string format (e.g., 'job-scheduler.job.123' -> 123)."""
        m = JOB_ID_RE.search(job_id)
        if m:
            return int(m.group(1))
        # Fallback: try to extract any number from the string
        numbers = re.findall(r"\d+", job_id)
        if numbers:
            return int(numbers[-1])  # Use last number found
        # Last resort: use hash of string (not ideal but works)
        return abs(hash(job_id)) % (10**9)

    def _get_lock(self, job_id: str) -> Lock:
        """Get or create a lock for a job_id."""
        with self._lock:
            if job_id not in self._locks:
                self._locks[job_id] = Lock()
            return self._locks[job_id]

    def _get_log_file(self, job_id: str) -> Path:
        """Get current log file path for a job_id."""
        safe_id = job_id.replace("/", "_").replace("\\", "_")
        return self.log_dir / f"{safe_id}.log"

    def _get_rotated_files(self, job_id: str) -> List[Path]:
        """Get all rotated log files for a job_id, sorted by creation time."""
        safe_id = job_id.replace("/", "_").replace("\\", "_")
        pattern = f"{safe_id}.log.*"
        files = sorted(
            self.log_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files

    def _count_total_lines(self, job_id: str) -> int:
        """Count total lines across all log files (rotated and current) for a job.

        Optimized: counts newlines instead of parsing full content.
        """
        total_lines = 0

        # Count lines in rotated files (gzipped)
        rotated_files = self._get_rotated_files(job_id)
        for rotated_file in rotated_files:
            try:
                if rotated_file.suffix == ".gz":
                    with gzip.open(rotated_file, "rt", encoding="utf-8") as f:
                        total_lines += sum(1 for _ in f)
                else:
                    with open(rotated_file, "r", encoding="utf-8") as f:
                        total_lines += sum(1 for _ in f)
            except Exception:
                pass  # Skip corrupted files

        # Count lines in current file
        current_file = self._get_log_file(job_id)
        if current_file.exists():
            try:
                with open(current_file, "r", encoding="utf-8") as f:
                    total_lines += sum(1 for _ in f)
            except Exception:
                pass

        return total_lines

    def _rotate_log(self, job_id: str, current_file: Path) -> Path:
        """Rotate log file: compress old one, return new file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_file = current_file.parent / f"{current_file.stem}.{timestamp}.log.gz"

        # Compress current file
        with open(current_file, "rb") as f_in:
            with gzip.open(rotated_file, "wb") as f_out:
                f_out.writelines(f_in)

        current_file.unlink()

        # Smart rotation: check total lines across all files
        total_lines = self._count_total_lines(job_id)
        if total_lines > self.max_total_lines:
            # Keep only the latest logs based on rotation_keep_ratio
            keep_lines = int(self.max_total_lines * self.rotation_keep_ratio)
            self._trim_old_logs(job_id, keep_lines)
            logger.info(
                f"Auto-trimmed logs for job {job_id}: "
                f"kept {keep_lines} latest lines, total was {total_lines} lines"
            )
        else:
            # Standard rotation: keep max_files rotated files
            rotated_files = self._get_rotated_files(job_id)
            if len(rotated_files) > self.max_files:
                for old_file in rotated_files[self.max_files :]:
                    old_file.unlink()

        return current_file  # Return path for new file

    def _trim_old_logs(self, job_id: str, keep_lines: int):
        """Trim old logs by keeping only the latest keep_lines entries.

        After trimming, the recent logs are kept in the main current file
        so that API fetch can access them directly.
        """
        # Read all log entries from all files (oldest to newest)
        all_entries = []

        rotated_files = self._get_rotated_files(job_id)
        for rotated_file in reversed(rotated_files):
            entries = self._read_log_file(rotated_file)
            all_entries.extend(entries)

        current_file = self._get_log_file(job_id)
        if current_file.exists():
            entries = self._read_log_file(current_file)
            all_entries.extend(entries)

        # Keep only the latest keep_lines entries
        if len(all_entries) > keep_lines:
            all_entries = all_entries[-keep_lines:]

        # Delete all old rotated files
        for rotated_file in rotated_files:
            rotated_file.unlink()

        # Delete current file if it exists
        if current_file.exists():
            current_file.unlink()

        # Write trimmed logs back to the MAIN current file (not compressed)
        # This ensures API can fetch recent logs directly
        if all_entries:
            with open(current_file, "w", encoding="utf-8") as f:
                for entry in all_entries:
                    log_line = f"{entry['timestamp']} [{entry['level']}] {entry['message']}\n"
                    f.write(log_line)

    def write_log(self, job_id: str, level: str, message: str, timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_line = f"{timestamp} [{level}] {message}\n"
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }

        # Write to SQLite if useIndexer is enabled, otherwise write to file
        if self.useIndexer:
            try:
                job_id_int = self._extract_job_id_int(job_id)
                self.log_indexer.insert_log(
                    job_id=job_id_int,
                    level=level,
                    message=message,
                    timestamp=timestamp,
                )

                # Auto-rotate: check if log count exceeds threshold
                log_count = self.log_indexer.get_log_count(job_id_int)
                if log_count > self.max_log_entries:
                    # Keep latest logs based on rotation_keep_ratio
                    keep_count = int(self.max_log_entries * self.rotation_keep_ratio)
                    self.log_indexer.rotate_job_logs_by_count(job_id_int, keep_count)
                    logger.info(
                        f"Auto-rotated logs for job {job_id}: "
                        f"kept {keep_count} latest logs, deleted {log_count - keep_count} oldest logs"
                    )
            except Exception:
                pass  # Don't fail on SQLite write errors
        else:
            # Write to file (original mode)
            lock = self._get_lock(job_id)
            with lock:
                log_file = self._get_log_file(job_id)

                # Check if rotation needed
                if log_file.exists() and log_file.stat().st_size >= self.max_file_size:
                    self._rotate_log(job_id, log_file)

                # Append log
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(log_line)

    def _read_log_file(self, file_path: Path) -> List[Dict]:
        entries = []

        try:
            if file_path.suffix == ".gz":
                f = gzip.open(file_path, "rt", encoding="utf-8")
            else:
                f = open(file_path, "r", encoding="utf-8")

            with f:
                current_entry = None
                line_num = 0

                for raw_line in f:
                    line_num += 1
                    line = raw_line.rstrip("\n")

                    header_match = LOG_HEADER_RE.match(line)

                    if header_match:
                        # Close previous entry
                        if current_entry:
                            entries.append(current_entry)

                        timestamp, level, message = header_match.groups()
                        current_entry = {
                            "offset": line_num,
                            "timestamp": timestamp,
                            "level": level,
                            "message": message or "",
                        }
                    else:
                        # Always append continuation lines (including blanks)
                        if current_entry:
                            current_entry["message"] += "\n" + line
                        else:
                            # Edge case: file starts without header
                            current_entry = {
                                "offset": line_num,
                                "timestamp": "",
                                "level": "INFO",
                                "message": line,
                            }

                if current_entry:
                    entries.append(current_entry)

        except Exception:
            pass

        return entries

    def search_logs(
        self,
        job_id: str,
        search_text: Optional[str] = None,
        offset: Optional[int] = None,
        limit: int = 1000,
        sort: str = "desc",
    ) -> Dict:
        """
        Search logs for a job_id.
        Args:
            job_id: Job identifier
            search_text: Text to search for (optional)
            offset: Start from this offset (optional)
            limit: Max results (default 1000)
            sort: Sort order - "asc" (oldest first) or "desc" (newest first, default)
        Returns: {logs: List[Dict], total: int, filtered: int, current_offset: int}
        """
        # Use SQLite if useIndexer is enabled
        if self.useIndexer:
            try:
                job_id_int = self._extract_job_id_int(job_id)

                if search_text:
                    # Use FTS search from log_indexer
                    results = self.log_indexer.search_logs(
                        job_id=job_id_int,
                        query=search_text,
                        limit=limit,
                    )
                else:
                    # Get latest N logs (e.g., 500 latest messages)
                    order_desc = sort == "desc"
                    results = self.log_indexer.get_latest_logs(
                        job_id=job_id_int,
                        limit=limit,
                        order_desc=order_desc,
                    )

                # Convert to expected format
                logs = []
                for r in results:
                    logs.append(
                        {
                            "offset": r.get("id", 0),
                            "timestamp": r.get("timestamp", ""),
                            "level": r.get("level", "INFO"),
                            "message": r.get("message", ""),
                        }
                    )

                # Sort by offset
                reverse = sort == "desc"
                logs.sort(key=lambda e: e["offset"], reverse=reverse)

                # Apply offset filter if provided
                if offset is not None and offset > 0:
                    if sort == "desc":
                        logs = [e for e in logs if e["offset"] <= offset]
                    else:
                        logs = [e for e in logs if e["offset"] >= offset]

                result_entries = logs[:limit]
                min_offset = result_entries[0]["offset"] if result_entries else None
                max_offset = result_entries[-1]["offset"] if result_entries else None

                return {
                    "logs": result_entries,
                    "total": len(logs),  # Approximate total
                    "filtered": len(result_entries) if search_text else len(logs),
                    "returned": len(result_entries),
                    "min_offset": min_offset,
                    "max_offset": max_offset,
                    "has_more": len(logs) > limit,
                }
            except Exception as e:
                # Fallback to file-based search on error
                pass

        # File-based search (original implementation)
        lock = self._get_lock(job_id)
        with lock:
            all_entries = []
            global_offset = 1

            rotated_files = self._get_rotated_files(job_id)
            for rotated_file in reversed(rotated_files):
                entries = self._read_log_file(rotated_file)
                # Assign global offsets
                for entry in entries:
                    entry["offset"] = global_offset
                    global_offset += 1
                all_entries.extend(entries)

            # Read current log file (newest)
            current_file = self._get_log_file(job_id)
            if current_file.exists():
                entries = self._read_log_file(current_file)
                # Assign global offsets
                for entry in entries:
                    entry["offset"] = global_offset
                    global_offset += 1
                all_entries.extend(entries)

            total = len(all_entries)

            if search_text:
                search_lower = search_text.lower()
                all_entries = [
                    e
                    for e in all_entries
                    if search_lower in e["message"].lower() or search_lower in e["level"].lower()
                ]

            filtered_count = len(all_entries)
            reverse = sort == "desc"
            all_entries.sort(key=lambda e: e["offset"], reverse=reverse)
            if offset is not None and offset > 0:
                if sort == "desc":
                    all_entries = [e for e in all_entries if e["offset"] <= offset]
                else:
                    all_entries = [e for e in all_entries if e["offset"] >= offset]
            result_entries = all_entries[:limit]

            min_offset = result_entries[0]["offset"] if result_entries else None
            max_offset = result_entries[-1]["offset"] if result_entries else None

            # Determine if there are more logs available for pagination
            has_more = len(all_entries) > limit

            return {
                "logs": result_entries,
                "total": total,
                "filtered": filtered_count,
                "returned": len(result_entries),
                "min_offset": min_offset,
                "max_offset": max_offset,
                "has_more": has_more,
            }

    def search_logs_with_following(
        self,
        job_id: str,
        keyword: str,
        n_following: int = 25,
        limit: int = 100,
        sort: str = "desc",
    ) -> Dict:
        # Use SQLite if useIndexer is enabled
        # print("useIndexer", self.useIndexer)
        if self.useIndexer:
            try:
                job_id_int = self._extract_job_id_int(job_id)

                # Use search_logs_with_following from log_indexer
                groups = self.log_indexer.search_logs_with_following(
                    job_id=job_id_int,
                    query=keyword,
                    following_lines=n_following,
                    limit=limit,
                )

                # Convert to expected format
                result_groups = []
                for group in groups:
                    match = group.get("match", {})
                    following = group.get("following", [])

                    result_groups.append(
                        {
                            "matched_entry": {
                                "offset": match.get("id", 0),
                                "timestamp": match.get("timestamp", ""),
                                "level": match.get("level", "INFO"),
                                "message": match.get("message", ""),
                            },
                            "following_entries": [
                                {
                                    "offset": f.get("id", 0),
                                    "timestamp": f.get("timestamp", ""),
                                    "level": f.get("level", "INFO"),
                                    "message": f.get("message", ""),
                                }
                                for f in following
                            ],
                            "offset": match.get("id", 0),
                            "timestamp": match.get("timestamp", ""),
                        }
                    )

                # Sort by offset
                reverse = sort == "desc"
                result_groups.sort(key=lambda g: g["offset"], reverse=reverse)

                return {
                    "groups": result_groups[:limit],
                    "total_matches": len(result_groups),
                    "returned": len(result_groups[:limit]),
                }
            except Exception as e:
                print(f"Error in search_logs_with_following: {e}")
                # Fallback to file-based search on error
                return {
                    "groups": [],
                    "total_matches": 0,
                    "returned": 0,
                }

        # File-based search (original implementation)
        lock = self._get_lock(job_id)
        with lock:
            all_entries = []
            global_offset = 1

            # Read all log files in chronological order
            rotated_files = self._get_rotated_files(job_id)
            for rotated_file in reversed(rotated_files):
                entries = self._read_log_file(rotated_file)
                for entry in entries:
                    entry["offset"] = global_offset
                    global_offset += 1
                all_entries.extend(entries)

            # Read current log file (newest)
            current_file = self._get_log_file(job_id)
            if current_file.exists():
                entries = self._read_log_file(current_file)
                for entry in entries:
                    entry["offset"] = global_offset
                    global_offset += 1
                all_entries.extend(entries)

            keyword_lower = keyword.lower()
            matched_groups = []
            i = 0

            # Find matched entries and group with following entries
            while i < len(all_entries):
                entry = all_entries[i]
                message_lower = entry.get("message", "").lower()
                level_lower = entry.get("level", "").lower()

                # Check if this entry matches the keyword
                if keyword_lower in message_lower or keyword_lower in level_lower:
                    # Start a new group with the matched entry
                    group = {
                        "matched_entry": entry,
                        "following_entries": [],
                        "offset": entry["offset"],  # Use matched entry's offset for sorting
                        "timestamp": entry.get("timestamp", ""),
                    }

                    # Add up to n_following entries that do NOT contain the keyword
                    for j in range(1, n_following + 1):
                        if i + j >= len(all_entries):
                            break
                        next_entry = all_entries[i + j]
                        next_message_lower = next_entry.get("message", "").lower()
                        next_level_lower = next_entry.get("level", "").lower()

                        # Stop if next entry also matches keyword
                        if keyword_lower in next_message_lower or keyword_lower in next_level_lower:
                            break

                        group["following_entries"].append(next_entry)

                    matched_groups.append(group)
                    # Skip over the matched entry and its following entries
                    i += len(group["following_entries"]) + 1
                else:
                    i += 1

            total_matches = len(matched_groups)

            # Sort groups by offset (chronological order)
            reverse = sort == "desc"
            matched_groups.sort(key=lambda g: g["offset"], reverse=reverse)

            # Limit results
            result_groups = matched_groups[:limit]

            return {
                "groups": result_groups,
                "total_matches": total_matches,
                "returned": len(result_groups),
            }

    def cleanup_old_logs(self):
        """Remove log files older than retention_days."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0

        for log_file in self.log_dir.glob("*.log*"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
            except Exception:
                pass

        return deleted_count

    def clear_logs(self, job_id: str):
        job_id_int = self._extract_job_id_int(job_id)
        if self.useIndexer:
            try:
                self.log_indexer.rotate_job_logs_by_count(job_id_int, 0)
            except Exception as e:
                logger.error(f"Error in clear_logs useIndexer: {e}")
                return {"success": False, "error": str(e)}
            return {"success": True}
        else:
            try:
                # Write to file (original mode)
                lock = self._get_lock(job_id)
                with lock:
                    log_file = self._get_log_file(job_id)

                    # Check if rotation needed
                    if log_file.exists():
                        # Clear the file by opening in write mode (truncates file)
                        with open(log_file, "w", encoding="utf-8") as f:
                            pass  # File is now empty
            except Exception as e:
                logger.error(f"Error in clear_logs via file mode: {e}")
                return {"success": False, "error": str(e)}
            return {"success": True}
