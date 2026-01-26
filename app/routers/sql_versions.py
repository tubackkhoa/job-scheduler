from typing import Optional
from fastapi import APIRouter, HTTPException

from app.deps import PluginManagerState, UserState

router = APIRouter(prefix="/sql-versions", tags=["sql-versions"])


@router.get("")
async def list_sql_versions(
    plugin_manager: PluginManagerState,
    user: UserState,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    try:
        ctx = plugin_manager.create_ctx(user)
        result = await plugin_manager.dao.get_value_versions(
            ctx,
            "test.sql_id",
            search,
            limit=limit,
            offset=offset,
        )
        print(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list SQL versions: {str(e)}")
