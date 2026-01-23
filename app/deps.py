from typing import Annotated
from fastapi import Depends, HTTPException, Request

from auth import UserContext
from log_service import LogService
from plugin_manager import PluginManager


def get_plugin_manager(request: Request):
    return request.app.state.plugin_manager


def get_log_service(request: Request):
    return request.app.state.log_service


async def get_user(request: Request) -> UserContext:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401)
    user_id, username = user
    plugin_manager: PluginManager = request.app.state.plugin_manager
    roles = await plugin_manager.dao.get_user_roles(user_id)
    return UserContext(user_id, frozenset(roles), username)


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]
LogServiceState = Annotated[LogService, Depends(get_log_service)]
UserState = Annotated[UserContext, Depends(get_user)]
