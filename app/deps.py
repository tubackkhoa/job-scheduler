from typing import Annotated
from fastapi import Depends, HTTPException, Request

from auth import UserContext
from log_service import LogService
from plugin_manager import PluginManager


def get_plugin_manager(request: Request):
    return request.app.state.plugin_manager


def get_log_service(request: Request):
    return request.app.state.log_service


def get_user(request: Request) -> UserContext:
    uid = getattr(request.state, "uid", None)
    if uid is None:
        raise HTTPException(status_code=401)

    plugin_manager: PluginManager = request.app.state.plugin_manager
    roles, username = plugin_manager.dao.user_cache.get(uid, ([], ""))
    return UserContext(uid, frozenset(roles), username)


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]
LogServiceState = Annotated[LogService, Depends(get_log_service)]
UserState = Annotated[UserContext, Depends(get_user)]
