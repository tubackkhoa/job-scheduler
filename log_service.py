"""
Log Service - File-based logging with rotation, retention, and search.
Inspired by pm2-logrotate: rotate by size/date, keep N files, auto-cleanup.
"""

import os
import gzip
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from threading import Lock
import json


class LogService:

    def __init__(
        self,
        log_dir: str = "logs",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 10,  # Keep last 10 rotated files
        retention_days: int = 7,  # Keep logs for 7 days
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.retention_days = retention_days
        self._locks: Dict[str, Lock] = {}
        self._lock = Lock()  # For locks dict

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

    def _rotate_log(self, job_id: str, current_file: Path) -> Path:
        """Rotate log file: compress old one, return new file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_file = current_file.parent / f"{current_file.stem}.{timestamp}.log.gz"

        # Compress current file
        with open(current_file, "rb") as f_in:
            with gzip.open(rotated_file, "wb") as f_out:
                f_out.writelines(f_in)

        current_file.unlink()

        rotated_files = self._get_rotated_files(job_id)
        if len(rotated_files) > self.max_files:
            for old_file in rotated_files[self.max_files :]:
                old_file.unlink()

        return current_file  # Return path for new file

    def write_log(self, job_id: str, level: str, message: str, timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_line = f"{timestamp} [{level}] {message}\n"
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
        }

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
        """Read log entries from a file (plain or gzipped), supporting multiline log messages."""
        entries = []
        try:
            if file_path.suffix == ".gz":
                with gzip.open(file_path, "rt", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            current_entry = None
            line_num = 0

            for raw_line in lines:
                line_num += 1
                line = raw_line.rstrip("\n")
                if not line.strip():
                    continue

                # Check if line starts with timestamp pattern: "YYYY-MM-DD HH:MM:SS"
                if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line):
                    # Save previous entry if any
                    if current_entry:
                        entries.append(current_entry)

                    # Parse new log entry line: timestamp, level, message
                    match = re.match(
                        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.+)$", line
                    )
                    if match:
                        timestamp, level, message = match.groups()
                        current_entry = {
                            "offset": line_num,
                            "timestamp": timestamp,
                            "level": level,
                            "message": message,
                        }
                    else:
                        # Fallback: treat whole line as message
                        current_entry = {
                            "offset": line_num,
                            "timestamp": "",
                            "level": "INFO",
                            "message": line,
                        }
                else:
                    # Continuation line: append to last message with newline
                    if current_entry:
                        current_entry["message"] += "\n" + line
                    else:
                        # No current entry? Treat as standalone info line
                        current_entry = {
                            "offset": line_num,
                            "timestamp": "",
                            "level": "INFO",
                            "message": line,
                        }

            # Append last entry if exists
            if current_entry:
                entries.append(current_entry)

        except Exception:
            pass  # Skip corrupted files

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
