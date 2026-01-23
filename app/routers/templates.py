from fastapi import APIRouter, Body, HTTPException, Response
from app.deps import PluginManagerState, UserState
from renderer import Renderer
from schemas import ConfigPayload, TemplatePayload, settings
from template_plugin import TemplatePlugin
from models import Job

router = APIRouter(prefix="/template", tags=["templates", "user-templates"])


@router.post("/{package}")
async def render_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: TemplatePayload = Body(...),
):

    try:
        plugin_instance = plugin_manager.get_plugin_instance(package)

        # fallback to user plugin, usualy plugin package is namespace with dot while plugin template is just name
        if plugin_instance is None:
            plugin_instance = TemplatePlugin(f"{settings.user_plugin_path}/{package}")

        ctx = plugin_manager.create_ctx(user, package)
        # env will be extra to make sure params can not override
        result = await Renderer.render(
            ctx, payload.template, payload.params, **plugin_instance.env()
        )
        return Response(content=result, media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to render template: {str(e)}",
        )


# support template plugin, install by user
@router.get("/user/{package}")
def get_user_template(plugin_manager: PluginManagerState, user: UserState, package: str):
    try:
        tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
        ctx = plugin_manager.create_ctx(user)
        config = tpl_plugin.config(ctx)
        return {
            "schema": tpl_plugin.schema(ctx),
            "jobs": [
                Job(
                    active=False,
                    description=tpl_plugin.description,
                    id=0,
                    config=config.model_dump(mode="json"),
                    plugin_id=package,
                )
            ],
            "user": ctx.user,
            "globals": Renderer.get_globals_doc(tpl_plugin.env()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get user template plugin: {str(e)}",
        )


@router.post("/user/{package}")
def update_user_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: ConfigPayload = Body(...),
):
    try:
        tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
        ctx = plugin_manager.create_ctx(user)
        tpl_plugin.save(ctx, payload.description, payload.config)
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to run template plugin: {str(e)}",
        )


@router.post("/user/run/{package}")
async def run_user_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload=Body(...),
):
    try:
        tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
        ctx = plugin_manager.create_ctx(user)
        config = tpl_plugin.config(ctx, payload)
        result = await tpl_plugin.run(ctx, config)
        return Response(content=result, media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to run template plugin: {str(e)}",
        )
