from fastapi import APIRouter, Body, HTTPException

from app.deps import PluginManagerState, UserState
from schemas import ConfigPayload
from constants import ModelEnv
from utils.trade_models import activate_forwardtest_model, deactivate_trade_model
from schemas import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

def _activate_forwardtest_model(ctx, model_identity):
    try:
        webhook_url = settings.uat_endpoint_api
        webhook_test_apikey = settings.test_system_api_key
        if not webhook_url or not webhook_test_apikey:
            raise HTTPException(status_code=400, detail="webhook_url or webhook_test_apikey is missing")
        activate_forwardtest_model(ctx, model_identity, webhook_url, webhook_test_apikey, ModelEnv.uat_test)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate forwardtest model: {str(e)}")

def _deactivate_forwardtest_model(ctx, model_identity):
    try:
        webhook_url = settings.uat_endpoint_api
        webhook_test_apikey = settings.test_system_api_key
        if not webhook_url or not webhook_test_apikey:
            raise HTTPException(status_code=400, detail="webhook_url or webhook_test_apikey is missing")
        deactivate_trade_model(ctx, model_identity, webhook_url, webhook_test_apikey, ModelEnv.uat_test)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate forwardtest model: {str(e)}")



@router.post("/{job_id}/activate")
async def activate_job(plugin_manager: PluginManagerState, user: UserState, job_id: int):
    
    job_item = await plugin_manager.dao.get_job(job_id)
    if not job_item:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    await plugin_manager.activate_job(job_id)
    config = job_item.to_dict().get("config", {})

    if config.get("model_tag", "") == ModelEnv.uat_test and config.get("model_key", ""):
       ctx = plugin_manager.create_ctx(user)
       _activate_forwardtest_model(ctx, config.get("model_key", ""))
    
    return {"success": True}


@router.post("/{job_id}/deactivate")
async def deactivate_job(plugin_manager: PluginManagerState, user: UserState, job_id: int):
    job_item = await plugin_manager.dao.get_job(job_id)
    if not job_item:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    try:
        await plugin_manager.deactivate_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate job: {str(e)}")
    
    config = job_item.to_dict().get("config", {})
    if config.get("model_tag", "") == ModelEnv.uat_test and config.get("model_key", ""):
       ctx = plugin_manager.create_ctx(user)
       _deactivate_forwardtest_model(ctx, config.get("model_key", ""))
    
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
    try:
        if job_id == 0:
            # Validate required fields for new job creation
            if payload.plugin_id is None:
                raise HTTPException(status_code=400, detail="pluginId is required when job_id is 0")
            if payload.session_id is None:
                raise HTTPException(
                    status_code=400, detail="sessionId is required when job_id is 0"
                )
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
    except HTTPException:
        # Re-raise HTTP exceptions for FastAPI to handle properly
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")
