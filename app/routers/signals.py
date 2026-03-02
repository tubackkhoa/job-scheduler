from fastapi import APIRouter

from app.deps import PluginManagerState

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/{job_id}")
async def get_signal_messages(
    plugin_manager: PluginManagerState,
    job_id: int,
    limit: int = 100,
):

    signals = await plugin_manager.dao.get_signal_messages(job_id=job_id, limit=limit)
    return {
        "signals": signals,
        "count": len(signals),
        "job_id": job_id,
    }


@router.get("/model/{model_key}")
async def get_signal_messages_by_model(
    plugin_manager: PluginManagerState,
    model_key: str,
    limit: int = 100,
):

    signals = await plugin_manager.dao.get_signal_messages_by_model(
        model_key=model_key, limit=limit
    )
    return {
        "signals": signals,
        "count": len(signals),
        "model_key": model_key,
    }
