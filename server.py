import asyncio
import inspect
from typing import Annotated, Optional
from fastapi import (
    Depends,
    FastAPI,
    Body,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging

from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from create_data import create_data
from log_handler import JobLogHandler
from log_service import LogService
from models import Job, Plugin, SqlVersion
from plugin_manager import PluginManager, PluginSpec
from ws_manager import WSConnectionManager
import os
import dotenv
import uvloop
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from datetime import datetime, date
from enum import Enum as BaseEnum


dotenv.load_dotenv()
# Configure logging to show INFO and above messages
logging.basicConfig(level=logging.DEBUG, handlers=[logging.NullHandler()])
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

manager = WSConnectionManager()


# define state transform for app
def get_plugin_manager(request: Request) -> PluginManager:
    return request.app.state.plugin_manager


def get_log_service(request: Request) -> LogService:
    return request.app.state.log_service


PluginManagerState = Annotated[PluginManager, Depends(get_plugin_manager)]
LogServiceState = Annotated[LogService, Depends(get_log_service)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # These will be initialised once an event loop is running (inside lifespan)
    db_connection = os.getenv("DB_CONNECTION")
    assert db_connection
    if ":memory:" in db_connection:
        from sqlalchemy.pool import StaticPool

        # single connection for testing
        db_engine = create_engine(
            db_connection,
            poolclass=StaticPool,
        )
        create_data(db_engine)
    else:
        db_engine = create_engine(db_connection)

    # Initialise log service and handler
    use_log_indexer = os.getenv("USE_LOG_INDEXER", "false").lower() in ("true", "1", "yes")
    log_service = LogService(
        log_dir=os.getenv("LOG_DIR", "logs"),
        max_file_size=int(os.getenv("LOG_MAX_SIZE", 10 * 1024 * 1024)),
        max_files=int(os.getenv("LOG_MAX_FILES", 10)),
        retention_days=int(os.getenv("LOG_RETENTION_DAYS", 7)),
        useIndexer=use_log_indexer,
    )

    loop = asyncio.get_running_loop()
    log_handler = JobLogHandler(manager.send_log, loop, log_service=log_service)

    plugin_manager = PluginManager(
        db_engine,
        log_handler=log_handler,
        module_paths=os.getenv("MODULE_PATH", "").split(":"),
    )
    plugin_manager.reload_all_jobs()

    # ---- STARTUP ----
    plugin_manager.start()

    # store in app state
    app.state.plugin_manager = plugin_manager
    app.state.log_service = log_service

    yield

    # ---- SHUTDOWN ----
    plugin_manager.stop()

    # Immediate hard exit after 1 second for cleaning up
    await asyncio.sleep(1)
    os._exit(0)


def describe_callable(obj):
    """Extract documentation and signature for a callable or object."""

    data = {}

    if callable(obj):
        data["type"] = "function"
        data["doc"] = inspect.getdoc(obj)
        try:
            data["signature"] = str(inspect.signature(obj))
        except (ValueError, TypeError):
            data["signature"] = None
    else:
        data["type"] = "variable"
        data["doc"] = str(obj)

    return data


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check(plugin_manager: PluginManagerState):

    from sqlalchemy import text

    try:
        # Check database connection
        db_engine = plugin_manager.db_engine
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "plugin_manager": "initialized",
            "plugins_count": len(plugin_manager.get_plugin_names()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}",
        )


@app.websocket("/ws/logs/{job_id}")
async def websocket_logs_endpoint(websocket: WebSocket, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    await manager.connect(websocket, scheduler_job_id)
    try:
        while True:
            # Keep connection alive; you can also handle client messages here if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, scheduler_job_id)


@app.get("/plugins")
def plugins(plugin_manager: PluginManagerState):
    return plugin_manager.get_all_plugins()


@app.get("/plugin/by-name/{plugin_name}")
def get_plugin_by_name(plugin_manager: PluginManagerState, plugin_name: str):
    """
    Get a single plugin by package name with all its jobs.
    Returns 404 if plugin not found.
    """
    with Session(plugin_manager.db_engine) as session:
        stmt = select(Plugin).where(Plugin.package == plugin_name)
        plugin = session.execute(stmt).scalar_one_or_none()

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

        # Get all jobs for this plugin
        stmt_jobs = select(Job).where(Job.plugin_id == plugin.id)
        jobs = session.execute(stmt_jobs).scalars().all()

        return {
            "id": plugin.id,
            "package": plugin.package,
            "interval": plugin.interval,
            "description": plugin.description,
            "jobs": [
                {
                    "id": job.id,
                    "session_id": job.session_id,
                    "plugin_id": job.plugin_id,
                    "config": job.config,
                    "description": job.description,
                    "active": job.active,
                }
                for job in jobs
            ],
        }


@app.post("/plugins")
def create_plugin(plugin_manager: PluginManagerState, payload: dict = Body(...)):
    """
    Create a plugin record and load it into the PluginManager.

    Expected payload:
    {
      "package": "plugins.sample_plugin@v0_1_0.Plugin",
      "interval": 60,
      "description": "Sample plugin"
    }
    """

    required_keys = {"package", "interval"}
    if not required_keys.issubset(payload):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: package, interval",
        )

    # Load into manager
    try:
        plugin_id = plugin_manager.add_plugin(
            payload["package"], int(payload["interval"]), payload.get("description")
        )
        return {
            "id": plugin_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin: {str(e)}",
        )


@app.post("/template/{package}")
def template(plugin_manager: PluginManagerState, package: str, payload: dict = Body(...)):
    plugin_instance = plugin_manager.get_plugin_instance(package)
    template_str = payload.get("template", "")
    if plugin_instance is None:
        return {"result": template_str}

    try:
        template_engine = plugin_instance.env().from_string(template_str)
        result = template_engine.render(**payload["params"])
        return {"result": result}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to render template: {str(e)}",
        )


@app.get("/schema/{session_id}/{plugin_id}")
def schema(plugin_manager: PluginManagerState, session_id: int, plugin_id: int):
    plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
    assert plugin_item

    try:
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)
        if plugin != None:
            configs = plugin_manager.get_jobs_for_plugin_and_user(plugin_id, session_id)
            if len(configs) == 0:
                # add empty config so that when saving it will be new job
                configs.append(
                    Job(
                        active=False,
                        description="",
                        id=0,
                        config=plugin.config().model_dump_json(),
                        plugin_id=plugin_id,
                        session_id=session_id,
                    )
                )

            # Built-in Jinja tags are provided by extensions
            env = plugin.env()

            return {
                "schema": plugin.schema(),
                "configs": configs,
                "env": {
                    "globals": {
                        name: describe_callable(value) for name, value in env.globals.items()
                    },
                    "filters": {
                        name: describe_callable(value) for name, value in env.filters.items()
                    },
                    "tests": sorted(env.tests.keys()),
                    "tags": sorted(
                        set(
                            tag
                            for ext in env.extensions.values()
                            for tag in getattr(ext, "tags", [])
                        )
                    ),
                },
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load schema: {str(e)}")


@app.post("/activate/{job_id}/{activation}")
def activate_config(plugin_manager: PluginManagerState, job_id: int, activation: bool):
    if activation:
        plugin_manager.activate_job(job_id)
    else:
        plugin_manager.deactivate_job(job_id)
    return {"success": True}


@app.post("/delete/{job_id}")
def delete_job(plugin_manager: PluginManagerState, job_id: int):
    plugin_manager.remove_job(job_id)
    return {"success": True}


@app.post("/reload/{package}")
def reload_plugin(plugin_manager: PluginManagerState, package: str):
    try:
        plugin_manager.load_plugin(package, True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload plugin: {str(e)}")


@app.post("/download/{name}")
def download_module(plugin_manager: PluginManagerState, name: str, payload: dict = Body(...)):
    try:
        version_or_vsi = payload["version"]
        success = plugin_manager.download_package(name, version_or_vsi)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download module: {str(e)}")


@app.put("/install/{package}")
def install_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.install()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install plugin: {str(e)}")


@app.put("/uninstall/{package}")
def uninstall_module(plugin_manager: PluginManagerState, package: str):
    try:
        plugin = plugin_manager.get_plugin_instance(package)
        assert plugin
        return {"success": plugin.uninstall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin: {str(e)}")


@app.delete("/plugins/{plugin_id}")
def delete_plugin(plugin_manager: PluginManagerState, plugin_id: int):
    """
    Delete a plugin from the database and unload it from memory.
    Also removes all associated jobs.
    """
    try:
        plugin_manager.delete_plugin(plugin_id)
        return {"success": True, "message": f"Plugin with id {plugin_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plugin: {str(e)}")


@app.post("/config/{job_id}")
def update_config(plugin_manager: PluginManagerState, job_id: int, payload: dict = Body(...)):
    try:
        if job_id == 0:
            plugin_id = payload["pluginId"]
        else:
            job_item = plugin_manager.get_job_by_id(job_id)
            assert job_item
            plugin_id = job_item.plugin_id

        plugin_item = plugin_manager.get_plugin_by_id(plugin_id)
        assert plugin_item
        plugin = plugin_manager.get_plugin_instance(plugin_item.package)
        if not plugin:
            return {"error": "Plugin not found"}
        config = plugin.config(payload.get("config"))
        if job_id == 0:
            # Accept both userId (legacy) and sessionId (new)
            session_id = payload.get("sessionId") or payload.get("userId")
            if not session_id:
                raise HTTPException(status_code=400, detail="sessionId or userId is required")
            plugin_manager.add_job(
                session_id,
                plugin_id,
                config.model_dump_json(),
                payload.get("description"),
            )
        else:
            plugin_manager.update_job(job_id, config.model_dump_json(), payload.get("description"))

        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@app.get("/api/logs/{job_id}")
def search_logs(
    log_service: LogServiceState,
    job_id: int,
    search: Optional[str] = None,
    offset: Optional[int] = None,
    limit: int = 1000,
    sort: str = "desc",
):
    """
    Search logs for a job_id.
    Query params:
    - job_id: job identifier (format: plugin_id/session_id/job_id, e.g., "5/1/10")
    - search: text to search for (optional)
    - offset: start from this offset (optional)
    - limit: max results (default 1000)
    - sort: sort order - "asc" (oldest first) or "desc" (newest first, default)
    """
    try:
        scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
        result = log_service.search_logs(
            job_id=scheduler_job_id,
            search_text=search,
            offset=offset,
            limit=limit,
            sort=sort,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")


@app.get("/api/logs/{job_id}/signals")
def search_logs_with_following(
    log_service: LogServiceState,
    job_id: int,
    keyword: str,
    n_following: int = 25,
    limit: int = 100,
    sort: str = "desc",
):
    try:
        scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
        result = log_service.search_logs_with_following(
            job_id=scheduler_job_id,
            keyword=keyword,
            n_following=n_following,
            limit=limit,
            sort=sort,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search logs with following: {str(e)}"
        )


@app.post("/api/logs/{job_id}/clear")
def clear_logs(log_service: LogServiceState, job_id: int):
    scheduler_job_id = PluginManager.get_job_scheduler_id(job_id)
    result = log_service.clear_logs(scheduler_job_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/api/sql-versions")
def create_sql_version(plugin_manager: PluginManagerState, payload: dict = Body(...)):
    required_keys = {"name", "sql_query"}
    if not required_keys.issubset(payload):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: name, sql_query",
        )

    try:
        with Session(plugin_manager.db_engine) as session:
            sql_version = SqlVersion(
                name=payload["name"],
                description=payload.get("description"),
                sql_query=payload["sql_query"],
                tags=payload.get("tags"),
            )
            session.add(sql_version)
            session.commit()
            session.refresh(sql_version)

            return {
                "id": sql_version.id,
                "name": sql_version.name,
                "description": sql_version.description,
                "sql_query": sql_version.sql_query,
                "created_at": sql_version.created_at.isoformat(),
                "updated_at": sql_version.updated_at.isoformat(),
                "is_active": sql_version.is_active,
                "tags": sql_version.tags,
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create SQL version: {str(e)}",
        )


@app.get("/api/sql-versions")
def get_sql_versions(
    plugin_manager: PluginManagerState,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    try:
        with Session(plugin_manager.db_engine) as session:
            stmt = select(SqlVersion)
            if search:
                stmt = stmt.where(SqlVersion.name.ilike(f"%{search}%"))

            stmt = stmt.order_by(SqlVersion.created_at.desc()).limit(limit).offset(offset)
            versions = session.execute(stmt).scalars().all()

            return {
                "versions": [
                    {
                        "id": v.id,
                        "name": v.name,
                        "description": v.description,
                        "sql_query": v.sql_query,
                        "created_at": v.created_at.isoformat(),
                        "updated_at": v.updated_at.isoformat(),
                        "is_active": v.is_active,
                        "tags": v.tags,
                    }
                    for v in versions
                ],
                "count": len(versions),
                "search": search,
                "limit": limit,
                "offset": offset,
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch SQL versions: {str(e)}",
        )


@app.get("/api/sql-versions/latest")
def get_latest_sql_version(plugin_manager: PluginManagerState):
    """
    Get the latest SQL version sorted by updated_at DESC.
    Returns 404 if no SQL version exists.

    Note: This route must be defined BEFORE /api/sql-versions/{version_id}
    to prevent FastAPI from trying to parse 'latest' as an integer.
    """
    try:
        with Session(plugin_manager.db_engine) as session:
            stmt = select(SqlVersion).order_by(SqlVersion.updated_at.desc()).limit(1)
            version = session.execute(stmt).scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail="No SQL version found",
                )

            return {
                "id": version.id,
                "name": version.name,
                "description": version.description,
                "sql_query": version.sql_query,
                "created_at": version.created_at.isoformat(),
                "updated_at": version.updated_at.isoformat(),
                "is_active": version.is_active,
                "tags": version.tags,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest SQL version: {str(e)}",
        )


@app.get("/api/sql-versions/{version_id}")
def get_sql_version(
    plugin_manager: PluginManagerState,
    version_id: int,
):
    try:
        with Session(plugin_manager.db_engine) as session:
            stmt = select(SqlVersion).where(
                SqlVersion.id == version_id,
            )
            version = session.execute(stmt).scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail=f"SQL version {version_id} not found",
                )

            return {
                "id": version.id,
                "name": version.name,
                "description": version.description,
                "sql_query": version.sql_query,
                "created_at": version.created_at.isoformat(),
                "updated_at": version.updated_at.isoformat(),
                "is_active": version.is_active,
                "tags": version.tags,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch SQL version: {str(e)}",
        )


@app.put("/api/sql-versions/{version_id}")
def update_sql_version(
    plugin_manager: PluginManagerState,
    version_id: int,
    payload: dict = Body(...),
):
    """
    Update an existing SQL version.

    Expected payload:
    {
      "name": "v1.1",  # Optional
      "description": "Updated ranking",  # Optional
      "sql_query": "SELECT ...",  # Optional
      "tags": "{...}"  # Optional
    }
    """
    try:
        with Session(plugin_manager.db_engine) as session:
            stmt = select(SqlVersion).where(SqlVersion.id == version_id)
            version = session.execute(stmt).scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail=f"SQL version {version_id} not found",
                )

            # Update fields if provided
            if "name" in payload:
                version.name = payload["name"]
            if "description" in payload:
                version.description = payload["description"]
            if "sql_query" in payload:
                version.sql_query = payload["sql_query"]
            if "tags" in payload:
                version.tags = payload["tags"]

            version.updated_at = datetime.now()

            session.commit()
            session.refresh(version)

            return {
                "id": version.id,
                "name": version.name,
                "description": version.description,
                "sql_query": version.sql_query,
                "created_at": version.created_at.isoformat(),
                "updated_at": version.updated_at.isoformat(),
                "is_active": version.is_active,
                "tags": version.tags,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update SQL version: {str(e)}",
        )


@app.delete("/api/sql-versions/{version_id}")
def delete_sql_version(plugin_manager: PluginManagerState, version_id: int):
    try:
        with Session(plugin_manager.db_engine) as session:
            stmt = select(SqlVersion).where(SqlVersion.id == version_id)
            version = session.execute(stmt).scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail=f"SQL version {version_id} not found",
                )

            session.delete(version)
            session.commit()

            return {
                "success": True,
                "message": f"SQL version {version_id} deleted",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete SQL version: {str(e)}",
        )


@app.post("/api/sql-versions/{version_id}/activate")
def activate_sql_version(plugin_manager: PluginManagerState, version_id: int):

    try:
        with Session(plugin_manager.db_engine) as session:
            # Get the version to activate
            stmt = select(SqlVersion).where(SqlVersion.id == version_id)
            version = session.execute(stmt).scalar_one_or_none()

            if not version:
                raise HTTPException(
                    status_code=404,
                    detail=f"SQL version {version_id} not found",
                )

            session_id = version.id

            # Deactivate all versions for this session
            update_stmt = (
                update(SqlVersion).where(SqlVersion.id == session_id).values(is_active=False)
            )
            session.execute(update_stmt)

            # Activate the selected version
            version.is_active = True

            session.commit()

            return {
                "success": True,
                "message": f"SQL version {version_id} activated",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate SQL version: {str(e)}",
        )


@app.post("/api/mlflow/sync")
async def mlflow_sync(plugin_manager: PluginManagerState, payload: dict = Body(...)):
    import httpx
    import json
    import logging
    from typing import Dict, Any, List

    # Validate required fields
    required_fields = {"plugin_name", "model_tag", "webhook_url", "webhook_api_key"}
    if not required_fields.issubset(payload):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {required_fields - set(payload.keys())}",
        )

    plugin_name = payload["plugin_name"]
    model_tag = payload["model_tag"]
    webhook_url = payload["webhook_url"]
    webhook_api_key = payload["webhook_api_key"]
    webhook_test_key = payload.get("webhook_test_key", "")
    session_id = payload.get("session_id", 1)
    model_type = payload.get("model_type", "mlflow_custom")

    # Setup logger
    logger = logging.getLogger(f"mlflow_sync.{model_tag}")
    logger.info(f"🔍 Starting MLflow sync for model_tag: '{model_tag}'")

    try:
        # Step 1: Fetch active models from MLflow
        from plugins.mlflow_plugin.utils import get_models_with_backtest_watching

        active_models = get_models_with_backtest_watching()
        logger.info(f"✅ Found {len(active_models)} active models in MLflow")
        active_identities = {m["identity"] for m in active_models}

        # Step 2: Get existing jobs from database by querying plugin directly
        with Session(plugin_manager.db_engine) as session:
            stmt = select(Plugin).where(Plugin.package == plugin_name)
            target_plugin = session.execute(stmt).scalar_one_or_none()

            if not target_plugin:
                raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")

            plugin_id = target_plugin.id

            # Get all jobs for this plugin
            stmt_jobs = select(Job).where(Job.plugin_id == plugin_id)
            jobs = session.execute(stmt_jobs).scalars().all()

            # Build map of existing jobs: {model_identity: job_id}
            existing_jobs: Dict[str, int] = {}
            for job in jobs:
                try:
                    config = json.loads(job.config) if isinstance(job.config, str) else job.config
                    identity = config.get("model_identity")
                    tag = config.get("model_tag")

                    if tag == model_tag and identity:
                        existing_jobs[identity] = job.id
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"⚠️  Failed to parse job {job.id} config: {e}")

        existing_identities = set(existing_jobs.keys())
        logger.info(f"📊 Found {len(existing_jobs)} existing jobs with tag '{model_tag}'")

        # Step 3: Determine sync plan
        to_create = active_identities - existing_identities
        to_stop = existing_identities - active_identities
        logger.info(f"🔄 Sync plan: {len(to_create)} to create, {len(to_stop)} to stop")

        # Step 4: Get base config - try SQL version first, fallback to plugin default
        try:
            # Try to fetch latest SQL version
            sql_query_from_version = None  # Store SQL query separately
            with Session(plugin_manager.db_engine) as session:
                stmt = select(SqlVersion).order_by(SqlVersion.updated_at.desc()).limit(1)
                sql_version = session.execute(stmt).scalar_one_or_none()

                if sql_version:
                    logger.info(f"📋 Using SQL version config: {sql_version.name}")
                    sql_query_from_version = sql_version.sql_query  # Store the SQL query

                    # Parse SQL version tags as base config
                    if sql_version.tags:
                        try:
                            plugin_default_config = (
                                json.loads(sql_version.tags)
                                if isinstance(sql_version.tags, str)
                                else sql_version.tags
                            )
                            logger.info(f"✅ Loaded config from SQL version tags")
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"⚠️  Failed to parse SQL version tags: {e}, falling back to plugin default"
                            )
                            plugin_default_config = None
                    else:
                        plugin_default_config = (
                            {}
                        )  # Empty dict if no tags, but we still have SQL query

                    # Add SQL query to config if we have it
                    if plugin_default_config is not None and sql_query_from_version:
                        plugin_default_config["sql"] = sql_query_from_version
                else:
                    logger.info(f"⚠️  No SQL version found, using plugin default config")
                    plugin_default_config = None

            # Fallback to plugin default config if SQL version config not available
            if plugin_default_config is None:
                import importlib

                parts = plugin_name.rsplit(".", 1)
                module_path = parts[0] if len(parts) == 2 else plugin_name
                class_name = parts[1] if len(parts) == 2 else "Plugin"

                module = importlib.import_module(module_path)
                plugin_class = getattr(module, class_name, None)

                if plugin_class and hasattr(plugin_class, "config"):
                    default_config_obj = plugin_class.config()
                    if hasattr(default_config_obj, "model_dump"):
                        plugin_default_config = default_config_obj.model_dump()
                    elif hasattr(default_config_obj, "dict"):
                        plugin_default_config = default_config_obj.dict()
                    else:
                        plugin_default_config = dict(default_config_obj)
                    logger.info(f"✅ Loaded plugin default config")
                else:
                    plugin_default_config = {}
                    logger.warning(f"⚠️  No plugin config method found")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load config: {e}")
            plugin_default_config = {}

        # Step 5: Execute sync
        created = []
        stopped = []
        errors = []
        jobs_to_delete = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "test-system-api-key": webhook_test_key,
                "Content-Type": "application/json",
            }

            # Create new models
            for model in active_models:
                identity = model["identity"]
                if identity not in to_create:
                    continue

                try:
                    # Call webhook to register model
                    resp = await client.post(
                        f"{webhook_url}/api/test-system/model",
                        headers=headers,
                        json={
                            "modelName": model["model_name"],
                            "identity": identity,
                            "tag": model_tag,
                            "version": str(model["version"]),
                        },
                    )

                    if resp.status_code in (200, 201):
                        logger.info(f"✅ Registered model via webhook: {identity}")

                        # Build job config
                        job_config = plugin_default_config.copy()
                        job_config.update(
                            {
                                "model_type": model.get("model_name") or model_type,
                                "model_identity": identity,
                                "model_tag": model_tag,
                                "model_uri": model.get("model_uri", ""),
                                "webhook_url": webhook_url,
                                "webhook_api_key": webhook_api_key,
                                "enable_use_default_config": False,
                            }
                        )

                        # Custom JSON serializer for non-serializable objects
                        def json_serializer(obj):
                            if isinstance(obj, (datetime, date)):
                                return obj.isoformat()
                            if isinstance(obj, BaseEnum):
                                return obj.value
                            if hasattr(obj, "__dict__"):
                                return str(obj)
                            return str(obj)

                        # Create job via PluginManager
                        plugin_manager.add_job(
                            session_id,
                            plugin_id,
                            json.dumps(job_config, default=json_serializer),
                            f"Auto-created for {identity}",
                        )
                        logger.info(f"📝 Created job for {identity}")
                        created.append(identity)

                    elif "exist" in resp.text.lower() or resp.status_code == 409:
                        # Model already exists, try to start it
                        logger.info(f"⚠️  Model already exists, calling start endpoint: {identity}")
                        start_resp = await client.post(
                            f"{webhook_url}/api/test-system/model/start",
                            headers=headers,
                            json={"identity": identity},
                        )

                        if start_resp.status_code in (200, 201):
                            logger.info(f"✅ Started existing model via webhook: {identity}")

                            # Build job config
                            job_config = plugin_default_config.copy()
                            job_config.update(
                                {
                                    "model_type": model.get("model_name") or model_type,
                                    "model_identity": identity,
                                    "model_tag": model_tag,
                                    "model_uri": model.get("model_uri", ""),
                                    "webhook_url": webhook_url,
                                    "webhook_api_key": webhook_api_key,
                                    "enable_use_default_config": False,
                                }
                            )

                            # Custom JSON serializer for non-serializable objects
                            def json_serializer(obj):
                                if isinstance(obj, (datetime, date)):
                                    return obj.isoformat()
                                if isinstance(obj, BaseEnum):
                                    return obj.value
                                if hasattr(obj, "__dict__"):
                                    return str(obj)
                                return str(obj)

                            # Create job via PluginManager
                            plugin_manager.add_job(
                                session_id,
                                plugin_id,
                                json.dumps(job_config, default=json_serializer),
                                f"Auto-created for {identity}",
                            )
                            logger.info(f"📝 Created job for {identity}")
                            created.append(identity)
                        else:
                            error = f"HTTP {start_resp.status_code}: {start_resp.text[:200]}"
                            logger.warning(f"⚠️  Failed to start {identity}: {error}")
                            errors.append({"identity": identity, "action": "start", "error": error})

                    else:
                        error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"⚠️  Failed to register {identity}: {error}")
                        errors.append({"identity": identity, "action": "create", "error": error})

                except Exception as e:
                    logger.error(f"❌ Error creating {identity}: {e}")
                    errors.append({"identity": identity, "action": "create", "error": str(e)})

            # Stop inactive models
            for model_identity in to_stop:
                job_id = existing_jobs.get(model_identity)

                try:
                    resp = await client.post(
                        f"{webhook_url}/api/test-system/model/stop",
                        headers=headers,
                        json={"identity": model_identity, "unlockCredential": True},
                    )

                    if resp.status_code in (200, 201):
                        logger.info(f"🛑 Stopped model via webhook: {model_identity}")
                        stopped.append(model_identity)
                        if job_id:
                            jobs_to_delete.append(job_id)
                    else:
                        error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"⚠️  Failed to stop {model_identity}: {error}")
                        errors.append(
                            {"identity": model_identity, "action": "stop", "error": error}
                        )

                except Exception as e:
                    logger.error(f"❌ Error stopping {model_identity}: {e}")
                    errors.append({"identity": model_identity, "action": "stop", "error": str(e)})

        # Step 6: Delete stopped jobs
        for job_id in jobs_to_delete:
            try:
                plugin_manager.remove_job(job_id)
                logger.info(f"🗑️  Deleted job {job_id}")
            except Exception as e:
                logger.error(f"❌ Failed to delete job {job_id}: {e}")
                errors.append({"action": "delete_job", "job_id": job_id, "error": str(e)})

        logger.info(
            f"✨ Sync complete: {len(created)} created, {len(stopped)} stopped, "
            f"{len(errors)} errors"
        )

        return {
            "created": created,
            "stopped": stopped,
            "errors": errors,
            "active_count": len(active_identities),
            "existing_count": len(existing_identities),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ MLflow sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"MLflow sync failed: {str(e)}")


# static site
static_files = os.getenv("STATIC_FILES")
if static_files:
    app.mount(
        "/",
        StaticFiles(directory=static_files, html=True),
        name="static",
    )
