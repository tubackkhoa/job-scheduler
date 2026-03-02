from fastapi import APIRouter, Body
from app.deps import PluginManagerState, UserState

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def get_all_users(plugin_manager: PluginManagerState, user: UserState):

    return [
        {
            "id": id,
            "username": username,
            "roles": roles,
        }
        for id, (roles, username) in plugin_manager.dao.user_cache.items()
    ]


@router.post("/{user_id}")
async def update_user(
    user_id: int, plugin_manager: PluginManagerState, user: UserState, payload=Body(...)
):

    ctx = plugin_manager.create_ctx(user)
    roles: list[str] = payload["roles"]
    return await plugin_manager.dao.update_user_roles(ctx, user_id, roles)


@router.get("/policy")
def policy(plugin_manager: PluginManagerState):
    if plugin_manager.enforcer:
        return plugin_manager.enforcer.get_policy()
    return []
