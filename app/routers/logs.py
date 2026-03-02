from typing import Optional

from fastapi import APIRouter, HTTPException

from app.deps import LogServiceState
from plugin_manager import PluginManager

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/{job_id}")
def search_logs(
    log_service: LogServiceState,
    job_id: int,
    search: Optional[str] = None,
    offset: Optional[int] = None,
    limit: int = 1000,
    sort: str = "desc",
):
    """
    Search logs for a job_id.
    Query params:
    - job_id: job identifier (format: plugin_id/session_id/job_id, e.g., "5/1/10")
    - search: text to search for (optional)
    - offset: start from this offset (optional)
    - limit: max results (default 1000)
    - sort: sort order - "asc" (oldest first) or "desc" (newest first, default)
    """

    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    result = log_service.search_logs(
        job_id=scheduler_job_id,
        search_text=search,
        offset=offset,
        limit=limit,
        sort=sort,
    )
    return result


@router.get("/{job_id}/signals")
def search_logs_with_following(
    log_service: LogServiceState,
    job_id: int,
    keyword: str,
    n_following: int = 25,
    limit: int = 100,
    sort: str = "desc",
):

    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    result = log_service.search_logs_with_following(
        job_id=scheduler_job_id,
        keyword=keyword,
        n_following=n_following,
        limit=limit,
        sort=sort,
    )
    return result


@router.post("/{job_id}/clear")
def clear_logs(log_service: LogServiceState, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    result = log_service.clear_logs(scheduler_job_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
