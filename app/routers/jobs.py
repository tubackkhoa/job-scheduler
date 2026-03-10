from fastapi import APIRouter, Body, HTTPException

from app.deps import PluginManagerState, UserState
from schemas import ConfigPayload

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/config")
async def get_config(plugin_manager: PluginManagerState, user: UserState, job_id: int):
    ctx = plugin_manager.create_ctx(user)
    job_item = await plugin_manager.dao.get_job(job_id)
    if not job_item:
        return {}
    plugin_item = plugin_manager.dao.plugin_cache.get(job_item.plugin_id)
    if not plugin_item:
        return {}
    plugin = plugin_manager.get_plugin_instance(plugin_item[1])
    if not plugin:
        return {}
    return plugin.config(ctx, job_item.config).model_dump(mode="json")


@router.post("/{job_id}/activate")
async def activate_job(plugin_manager: PluginManagerState, user: UserState, job_id: int):

    job_item = await plugin_manager.dao.get_job(job_id)
    if not job_item:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    await plugin_manager.activate_job(job_id)
    ctx = plugin_manager.create_ctx(user)

    plugin_manager.hook.on_active_job(ctx=ctx, json=job_item.config)

    return {"success": True}


@router.post("/{job_id}/deactivate")
async def deactivate_job(plugin_manager: PluginManagerState, user: UserState, job_id: int):
    job_item = await plugin_manager.dao.get_job(job_id)
    if not job_item:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    await plugin_manager.deactivate_job(job_id)

    ctx = plugin_manager.create_ctx(user)

    plugin_manager.hook.on_deactive_job(ctx=ctx, json=job_item.config)

    return {"success": True}


@router.delete("/{job_id}")
async def delete_job(plugin_manager: PluginManagerState, job_id: int):
    await plugin_manager.remove_job(job_id)
    return {"success": True}


@router.post("/{job_id}/config")
async def update_job_config(
    plugin_manager: PluginManagerState,
    user: UserState,
    job_id: int,
    payload: ConfigPayload = Body(...),
):

    if job_id == 0:
        # Validate required fields for new job creation
        if payload.plugin_id is None:
            raise HTTPException(status_code=400, detail="pluginId is required when job_id is 0")
        if payload.session_id is None:
            raise HTTPException(status_code=400, detail="sessionId is required when job_id is 0")
        plugin_id = payload.plugin_id
        session_id = payload.session_id
    else:
        job_item = await plugin_manager.dao.get_job(job_id)
        if not job_item:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        plugin_id = job_item.plugin_id

    plugin_item = plugin_manager.dao.plugin_cache.get(plugin_id)
    if not plugin_item:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")
    package = plugin_item[1]
    plugin = plugin_manager.get_plugin_instance(package)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    ctx = plugin_manager.create_ctx(user, package)
    # validate before saving
    config = plugin.config(ctx, payload.config, True)
    if job_id == 0:
        await plugin_manager.add_job(
            session_id,
            plugin_id,
            config.model_dump(mode="json"),
            payload.description,
        )
    else:
        await plugin_manager.dao.update_job(
            job_id, config.model_dump(mode="json"), payload.description
        )

    return config
