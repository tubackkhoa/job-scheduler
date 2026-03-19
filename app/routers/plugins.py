from typing import Optional
from fastapi import APIRouter, Body, HTTPException
from app.deps import PluginManagerState, UserState
from models import Job
from package_downloader import download_package
from renderer import Renderer
from schemas import DownloadPayload, PluginCreatePayload, settings
from plugin_manager import scheduler_logger

router = APIRouter(prefix="/plugins", tags=["plugins"])


def get_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    plugin_item = plugin_manager.dao.plugin_cache.get(plugin_id)
    if not plugin_item:
        raise HTTPException(status_code=404, detail="Plugin not found")
    package = plugin_item[0]
    plugin = plugin_manager.get_plugin_instance(package)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin instance not found")
    return plugin, package


@router.get("")
def plugins(
    plugin_manager: PluginManagerState,
):

    return [
        {"id": id, "package": package, "description": description}
        for id, (package, description) in plugin_manager.dao.plugin_cache.items()
    ]


@router.post("")
async def create_plugin(
    plugin_manager: PluginManagerState, payload: PluginCreatePayload = Body(...)
):
    """
    Create a plugin record and load it into the PluginManager.

    Expected payload:
    {
      "package": "plugins.sample_plugin@v0_1_0.Plugin",
      "description": "Sample plugin"
    }
    """
    # Load into manager

    plugin_id = await plugin_manager.add_plugin(payload.package, payload.description)
    return {
        "id": plugin_id,
    }


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    """
    Delete a plugin from the database and unload it from memory.
    Also removes all associated jobs.
    """

    await plugin_manager.delete_plugin(plugin_id)
    return {"success": True, "message": f"Plugin with id {plugin_id} deleted"}


@router.get("/routes")
async def all_routes(plugin_manager: PluginManagerState):
    return plugin_manager.routes_cache


@router.get("/routes/{plugin_id}")
async def routes(
    plugin_manager: PluginManagerState,
    plugin_id: int,
):
    _, package = get_plugin(plugin_manager, plugin_id)
    routes = plugin_manager.routes_cache[package]
    return {"package": package, "routes": routes}


@router.get("/routes/{plugin_id}/schema")
async def route_schema(
    plugin_manager: PluginManagerState,
    plugin_id: int,
    route: str,
):
    plugin, _ = get_plugin(plugin_manager, plugin_id)
    if not hasattr(plugin, "routes"):
        return
    for key, code_schema in plugin.routes():
        if key == route:
            return code_schema


@router.get("/value_versions")
async def value_versions(
    plugin_manager: PluginManagerState,
    user: UserState,
    field_id: str,
    plugin_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):

    ctx = plugin_manager.create_ctx(user)
    result = await plugin_manager.dao.get_value_versions(
        ctx,
        f"{plugin_id or "*"}.{field_id}",
        search,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/schema/{session_id}/{plugin_id}")
async def schema(
    plugin_manager: PluginManagerState,
    user: UserState,
    session_id: int,
    plugin_id: int,
):

    plugin, package = get_plugin(plugin_manager, plugin_id)

    ctx = plugin_manager.create_ctx(user, package)
    jobs = await plugin_manager.dao.get_jobs_by_plugin_and_session(
        ctx,
        plugin_id,
        session_id,
        include_fields=[Job.id, Job.active, Job.description, Job.cron_expr],
    )

    if len(jobs) == 0:
        # add empty config so that when saving it will be new job
        jobs.append(
            Job(
                active=False,
                description="Unnamed Job",
                cron_expr=settings.default_cron,
                id=0,
                config=plugin.config(ctx).model_dump(mode="json"),
            )
        )

    # Built-in Jinja tags are provided by extensions
    return {
        "schema": plugin.schema(ctx),
        "jobs": jobs,
        "globals": Renderer.get_globals_doc(plugin.env()),
    }


@router.post("/reload/{package}")
def reload_plugin(plugin_manager: PluginManagerState, package: str):

    plugin_manager.load_plugin(package, True)
    return {"success": True}


@router.post("/download/{name}")
def download_module(
    plugin_manager: PluginManagerState, name: str, payload: DownloadPayload = Body(...)
):

    version_or_vsi = payload.version
    success = download_package(scheduler_logger, plugin_manager.plugin_path, name, version_or_vsi)
    return {"success": success}


@router.put("/install/{package}")
async def install_module(plugin_manager: PluginManagerState, package: str):
    plugin = plugin_manager.get_plugin_instance(package)
    assert plugin
    return {"success": await plugin.install()}


@router.put("/uninstall/{package}")
async def uninstall_module(plugin_manager: PluginManagerState, package: str):
    plugin = plugin_manager.get_plugin_instance(package)
    assert plugin
    return {"success": await plugin.uninstall()}
