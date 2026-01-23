from fastapi import APIRouter, Body, HTTPException
from app.deps import PluginManagerState, UserState

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def get_all_users(plugin_manager: PluginManagerState, user: UserState):
    try:
        ctx = plugin_manager.create_ctx(user)
        return await plugin_manager.dao.get_all_users(ctx)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get users: {str(e)}",
        )


@router.post("/{user_id}")
async def update_user(
    user_id: int, plugin_manager: PluginManagerState, user: UserState, payload=Body(...)
):
    try:
        ctx = plugin_manager.create_ctx(user)
        roles: list[str] = payload["roles"]
        return await plugin_manager.dao.update_user_roles(ctx, user_id, roles)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update user: {str(e)}",
        )


@router.get("/roles")
def auth_state(plugin_manager: PluginManagerState):
    return plugin_manager.roles()


@router.get("/policy")
def policy(plugin_manager: PluginManagerState):
    if plugin_manager.enforcer:
        return plugin_manager.enforcer.get_policy()
    return []
