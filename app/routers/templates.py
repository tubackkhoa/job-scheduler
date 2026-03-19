from fastapi import APIRouter, Body, Response
from fastapi.responses import PlainTextResponse
from app.deps import PluginManagerState, UserState
from renderer import Renderer
from schemas import JobPayload, TemplateCodePayload, TemplatePayload, settings
from template_plugin import TemplatePlugin
from models import Job

router = APIRouter(prefix="/templates", tags=["templates", "user-templates"])


@router.post("/{package}")
async def render_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: TemplatePayload = Body(...),
):

    plugin_instance = plugin_manager.get_plugin_instance(package)

    # fallback to user plugin, usualy plugin package is namespace with dot while plugin template is just name
    if plugin_instance is None:
        plugin_instance = TemplatePlugin(f"{settings.user_plugin_path}/{package}")

    ctx = plugin_manager.create_ctx(user, package)
    # env will be extra to make sure params can not override
    result = await Renderer.render(ctx, payload.template, payload.params, **plugin_instance.env())
    return Response(result, media_type="text/plain")


# support template plugin, install by user
@router.get("/user/{package}")
def get_user_template(plugin_manager: PluginManagerState, user: UserState, package: str):

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


@router.get("/user/code/{package}")
def get_user_template_code(package: str):
    plugin_dir = f"{settings.user_plugin_path}/{package}"

    code = {}
    with open(f"{plugin_dir}/plugin.yaml") as f:
        code["form"] = f.read()
    with open(f"{plugin_dir}/plugin.j2") as f:
        code["script"] = f.read()
    return code


@router.post("/user/code/{package}")
def update_user_template_code(
    package: str,
    payload: TemplateCodePayload = Body(...),
):
    plugin_dir = f"{settings.user_plugin_path}/{package}"

    with open(f"{plugin_dir}/plugin.yaml", "w") as f:
        f.write(payload.form)
    with open(f"{plugin_dir}/plugin.j2", "w") as f:
        f.write(payload.script)
    return {"success": True}


@router.post("/user/{package}")
def update_user_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload: JobPayload = Body(...),
):

    tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
    ctx = plugin_manager.create_ctx(user)
    tpl_plugin.save(ctx, payload.description, payload.config)
    return {"success": True}


@router.post("/user/run/{package}")
async def run_user_template(
    plugin_manager: PluginManagerState,
    user: UserState,
    package: str,
    payload=Body(...),
):

    tpl_plugin = TemplatePlugin(f"{settings.user_plugin_path}/{package}")
    ctx = plugin_manager.create_ctx(user)
    config = tpl_plugin.config(ctx, payload)
    result = await tpl_plugin.run(ctx, config)
    return PlainTextResponse(result)
