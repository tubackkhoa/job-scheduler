from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.deps import PluginManagerState, UserState
from typing import Annotated
from schemas import JobFilters


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/jobs")
async def list_jobs(
    plugin_manager: PluginManagerState,
    user: UserState,
    filters: JobFilters = Depends(),
    version_id: Annotated[list[str] | None, Query()] = None,
    include_signals: Optional[bool] = False,
):
    try:
        ctx = plugin_manager.create_ctx(user)
        jobs, total = await plugin_manager.dao.get_jobs_by_filters(ctx, filters)

        results = {
            "jobs": jobs,
            "total": total,
        }

        if include_signals:
            results["signals_map"] = await plugin_manager.dao.get_signals_for_jobs(
                [job.id for job in jobs], limit_per_job=1
            )

        if version_id:

            collected_ids = defaultdict(set)
            for job in jobs:

                for key in version_id:
                    vid: Optional[int] = job.config.get(key) if job.config else None
                    if vid:
                        collected_ids[key].add(vid)

            all_version_ids = {vid for ids in collected_ids.values() for vid in ids}

            if all_version_ids:
                versions = await plugin_manager.dao.get_value_versions_by_filters(
                    ids=list(all_version_ids)
                )

                # cache for search
                versions_map = {v["id"]: v for v in versions}

                results["versions"] = {
                    key: [versions_map[vid] for vid in ids if vid in versions_map]
                    for key, ids in collected_ids.items()
                }

        return results

    except Exception as e:
        raise HTTPException(500, f"Failed to list jobs: {str(e)}")
