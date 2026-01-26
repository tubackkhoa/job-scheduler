from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.deps import PluginManagerState, UserState
from models import ValueVersion
from typing import Annotated


router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/jobs")
async def list_jobs(
    plugin_manager: PluginManagerState,
    user: UserState,
    search_text: Optional[str] = None,
    active: Optional[bool] = None,
    plugin_id: Annotated[list[int] | None, Query()] = None,
    model_key: Annotated[list[str] | None, Query()] = None,
    sql_id: Annotated[list[int] | None, Query()] = None,
    order_by: Optional[str] = "id",
    sort: Optional[str] = "desc",
    limit: Optional[int] = 20,
    offset: Optional[int] = 0,
    include_signals: Optional[bool] = False,
):
    try:
        ctx = plugin_manager.create_ctx(user)
        result = await plugin_manager.dao.get_jobs_by_filters(ctx, {
            "search_text": search_text,
            "active": active,
            "plugin_id": plugin_id,
            "model_key": model_key,
            "sql_id": sql_id,
            "order_by": order_by,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        })
        
        items = [job.to_dict() for job in result["items"]]
        
        if include_signals:
            job_ids = [job["id"] for job in items]
            signals_map = await plugin_manager.dao.get_signals_for_jobs(job_ids, limit_per_job=1)
            
            for job in items:
                job_signals = signals_map.get(job["id"], [])
                job["signals"] = job_signals
                job["last_signal"] = job_signals[0]['captured_at'] if job_signals else None
        
        return {
            "items": items,
            "total": result["total"],
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")
