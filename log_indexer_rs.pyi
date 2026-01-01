from typing import Optional, List, Dict

class LogIndexer:
    def __init__(
        self, db_path: Optional[str] = None, rotate_size: Optional[int] = None
    ) -> None: ...
    def rotate_job_logs_by_count(self, job_id: int, keep: Optional[int] = None) -> None: ...
    def insert_log(
        self,
        job_id: int,
        level: str,
        message: str,
        timestamp: Optional[str] = None,
    ) -> None: ...
    def search_logs(
        self,
        job_id: int,
        query: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, object]]: ...
    def import_log_files(self, filename: str) -> None: ...
    def get_logs_after_id(
        self,
        last_id: Optional[int] = None,
        job_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, object]]: ...
