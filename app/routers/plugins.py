from fastapi import APIRouter, Body, HTTPException
from app.deps import PluginManagerState, UserState
from models import Job
from package_downloader import download_package
from renderer import Renderer
from schemas import DownloadPayload, PluginCreatePayload
from plugin_manager import scheduler_logger

router = APIRouter(prefix="/plugins", tags=["plugins"])


def get_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    plugin_item = plugin_manager.dao.plugin_cache.get(plugin_id)
    if not plugin_item:
        raise HTTPException(status_code=404, detail="Plugin not found")
    package = plugin_item[1]
    plugin = plugin_manager.get_plugin_instance(package)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin instance not found")
    return plugin, package


@router.get("")
def plugins(
    plugin_manager: PluginManagerState,
):
    return [
        {"id": id, "interval": interval, "package": package, "description": description}
        for id, (interval, package, description) in plugin_manager.dao.plugin_cache.items()
    ]


@router.post("")
def create_plugin(plugin_manager: PluginManagerState, payload: PluginCreatePayload = Body(...)):
    """
    Create a plugin record and load it into the PluginManager.

    Expected payload:
    {
      "package": "plugins.sample_plugin@v0_1_0.Plugin",
      "interval": 60,
      "description": "Sample plugin"
    }
    """
    # Load into manager
    try:
        plugin_id = plugin_manager.add_plugin(
            payload.package, payload.interval, payload.description
        )
        return {
            "id": plugin_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    """
    Delete a plugin from the database and unload it from memory.
    Also removes all associated jobs.
    """
    try:
        await plugin_manager.delete_plugin(plugin_id)
        return {"success": True, "message": f"Plugin with id {plugin_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plugin: {str(e)}")


@router.get("/routes/{plugin_id}")
async def routes(
    plugin_manager: PluginManagerState,
    user: UserState,
    plugin_id: int,
):
    plugin, _ = get_plugin(plugin_manager, plugin_id)
    return plugin.routes()


@router.get("/schema/{session_id}/{plugin_id}")
async def schema(
    plugin_manager: PluginManagerState,
    user: UserState,
    session_id: int,
    plugin_id: int,
):

    plugin, package = get_plugin(plugin_manager, plugin_id)

    try:
        ctx = plugin_manager.create_ctx(user, package)
        jobs = await plugin_manager.dao.get_jobs_by_plugin_and_session(ctx, plugin_id, session_id)
        for job in jobs:
            job.config = plugin.config(ctx, job.config).model_dump(mode="json")

        if len(jobs) == 0:
            # add empty config so that when saving it will be new job
            jobs.append(
                Job(
                    active=False,
                    description="",
                    id=0,
                    config=plugin.config(ctx).model_dump(mode="json"),
                    plugin_id=plugin_id,
                    session_id=session_id,
                )
            )

        # Built-in Jinja tags are provided by extensions
        return {
            "user": ctx.user,
            "schema": plugin.schema(ctx),
            "jobs": jobs,
            "globals": Renderer.get_globals_doc(plugin.env()),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load schema: {str(e)}")


@router.post("/reload/{package}")
def reload_plugin(plugin_manager: PluginManagerState, package: str):
    try:
        plugin_manager.load_plugin(package, True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload plugin: {str(e)}")


@router.post("/download/{name}")
def download_module(
    plugin_manager: PluginManagerState, name: str, payload: DownloadPayload = Body(...)
):
    try:
        version_or_vsi = payload.version
        success = download_package(
            scheduler_logger, plugin_manager.plugin_path, name, version_or_vsi
        )
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download module: {str(e)}")


@router.put("/install/{package}")
def install_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.install()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install plugin: {str(e)}")


@router.put("/uninstall/{package}")
def uninstall_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.uninstall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin: {str(e)}")
