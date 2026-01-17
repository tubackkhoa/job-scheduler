from enum import Enum
import logging
import os
import json
from typing import Dict, Any, List, Optional
import httpx
from jinja2 import Environment
import pluggy
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from enum import Enum as BaseEnum
from datetime import datetime, date

import models
import plugin_manager

PROJECT_NAME = "job-scheduler"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class ModelTag(str, Enum):
    staging = "staging"
    production = "production"
    uat = "uat"

    def __str__(self):
        return self.value


class Config(BaseModel):
    model_tag: ModelTag = ModelTag.uat
    webhook_url: str = Field(
        default="",
        title="Webhook URL",
        description="Custom webhook URL for sending signals.",
    )
    webhook_api_key: str = Field(
        default="",
        title="Webhook API Key",
        description="Custom webhook API key for sending signals.",
        json_schema_extra={
            "ui:widget": "password",
            "ui:options": {"autocomplete": "off"},
        },
    )

    webhook_test_key: str = Field(
        default="",
        title="Webhook Test Key",
        description="Custom webhook test key for sending signals.",
        json_schema_extra={
            "ui:widget": "password",
            "ui:options": {"autocomplete": "off"},
        },
    )

    plugin_name: str = Field(
        default="alpha_miner.plugins.UatUserCustomConfigPlugin",
        description="Name of the plugin that handles model from MLflow",
    )


def get_db_engine() -> Optional[Engine]:
    """Get database engine from environment."""
    db_url = os.getenv("DB_CONNECTION")
    if not db_url:
        return None
    return create_engine(db_url)


def fetch_active_models(model_tag: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    """Fetch active models from MLflow filtered by model_tag."""
    from .utils import get_models_with_backtest_watching

    all_models = get_models_with_backtest_watching()
    logger.info(f"Active models: {all_models}")
    # active_models = [
    #     m for m in all_models
    #     if model_tag in m.get("tags", {})
    # ]
    active_models = all_models
    logger.info(f"✅ Found {len(active_models)} active models in MLflow")
    return active_models


def get_existing_jobs(
    engine: Engine, plugin_name: str, model_tag: str, logger: logging.Logger
) -> Dict[str, int]:
    """Query existing jobs from database. Returns {model_identity: job_id}."""
    existing_jobs = {}

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"""
            SELECT j.id, j.config
            FROM jobs j
            JOIN plugins p ON p.id = j.plugin_id
            WHERE p.package = '{plugin_name}'
        """
            )
        )

        for row in result:
            job_id = row[0]
            try:
                job_config = json.loads(row[1])
                identity = job_config.get("model_identity")
                tag = job_config.get("model_tag")
                if tag == model_tag and identity:
                    existing_jobs[identity] = job_id
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"⚠️  Failed to parse job {job_id} config: {e}")

    logger.info(f"📊 Found {len(existing_jobs)} existing jobs with tag '{model_tag}'")
    return existing_jobs


def get_plugin_id(engine: Engine, plugin_name: str) -> Optional[int]:
    """Get plugin_id for a given package name."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"""
            SELECT id FROM plugins WHERE package = '{plugin_name}'
        """
            )
        )
        row = result.fetchone()
        return row[0] if row else None


def get_plugin_default_config(plugin_name: str, logger: logging.Logger) -> Dict[str, Any]:
    """Load plugin class and get its default config (includes SQL)."""
    try:
        import importlib

        # Parse module and class name
        parts = plugin_name.rsplit(".", 1)
        if len(parts) == 2:
            module_path, class_name = parts
        else:
            module_path = plugin_name
            class_name = "Plugin"

        # Import module and get class
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name, None)

        if plugin_class and hasattr(plugin_class, "config"):
            default_config = plugin_class.config()
            # Convert pydantic model to dict if needed
            if hasattr(default_config, "model_dump"):
                return default_config.model_dump()
            elif hasattr(default_config, "dict"):
                return default_config.dict()
            return dict(default_config)

        logger.warning(f"⚠️  Plugin {plugin_name} has no config method")
        return {}

    except Exception as e:
        logger.warning(f"⚠️  Failed to load plugin config from {plugin_name}: {e}")
        return {}


def build_job_config(
    model: Dict[str, Any],
    model_tag: str,
    webhook_url: str,
    webhook_api_key: str,
    plugin_default_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build job config by merging plugin defaults with model-specific values."""
    config = plugin_default_config.copy()

    config.update(
        {
            "model_type": model["model_name"],
            "model_identity": model["identity"],
            "model_tag": str(model_tag),
            "model_uri": model.get("model_uri", ""),
            "webhook_url": webhook_url,
            "webhook_api_key": webhook_api_key,
        }
    )

    return config


def create_job_in_db(
    pm: plugin_manager.PluginManager,
    engine: Engine,
    plugin_id: int,
    session_id: int,
    config: Dict[str, Any],
    description: str,
    logger: logging.Logger,
) -> Optional[int]:
    """Insert a new job using PluginManager or fallback to direct SQL."""

    # Custom JSON encoder for non-serializable objects
    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, BaseEnum):
            return obj.value
        if hasattr(obj, "__dict__"):
            return str(obj)
        return str(obj)

    config_json = json.dumps(config, default=json_serializer)

    try:
        if pm:
            pm.add_job(session_id, plugin_id, config_json, description)
            logger.info(f"📝 Created job via PluginManager")
            return None
    except ImportError:
        pass

    try:
        config_json_escaped = config_json.replace("'", "''")
        description_escaped = description.replace("'", "''")

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"""
                INSERT INTO jobs (session_id, plugin_id, config, description, active)
                VALUES ({session_id}, {plugin_id}, '{config_json_escaped}', '{description_escaped}', true)
                RETURNING id
            """
                )
            )
            conn.commit()
            row = result.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"❌ Failed to create job: {e}")
        return None


def delete_jobs(
    pm: plugin_manager.PluginManager, engine: Engine, job_ids: List[int], logger: logging.Logger
) -> bool:
    """Batch delete jobs using PluginManager or fallback to direct SQL."""
    if not job_ids:
        return True

    try:
        if pm:
            pm.remove_jobs(job_ids)
            logger.info(f"🗑️  Deleted {len(job_ids)} jobs via PluginManager: {job_ids}")
            return True
    except ImportError:
        pass

    try:
        ids = ",".join(str(jid) for jid in job_ids)
        with engine.connect() as conn:
            conn.execute(text(f"DELETE FROM jobs WHERE id IN ({ids})"))
            conn.commit()
        logger.info(f"🗑️  Deleted {len(job_ids)} jobs: {job_ids}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete jobs: {e}")
        return False


class Plugin:

    _env = Environment()

    @staticmethod
    def attach_to_manager(plugin_manager: plugin_manager.PluginManager):
        ml_plugin = models.Plugin(id=0, package="plugins.mlflow_plugin.Plugin", interval=3)
        ml_config = Config()
        ml_job = models.Job(plugin_id=ml_plugin.id, active=True, config=ml_config.model_dump_json())
        plugin = plugin_manager.load_plugin(ml_plugin.package)
        assert plugin
        plugin.env().globals["plugin_manager"] = plugin_manager
        plugin_manager.add_job_instance(ml_job.id, ml_job.active, ml_plugin)

    @hookimpl
    @classmethod
    def env(cls) -> Environment:
        return cls._env

    @hookimpl
    @classmethod
    def schema(cls, ctx):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json=None):
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: Config, logger: logging.Logger) -> Dict[str, Any]:
        """Sync jobs with active MLflow models."""

        pm: plugin_manager.PluginManager = cls.env().globals["plugin_manager"]

        # Validate config
        if config.model_tag != ModelTag.production:
            if not config.webhook_url or not config.webhook_api_key:
                raise ValueError("Webhook URL and API key required for non-production")

        logger.info(f"🔍 Syncing jobs for model_tag: '{config.model_tag}'")

        # Get database engine
        engine = get_db_engine()
        if not engine:
            logger.error("❌ DB_CONNECTION env var not set")
            return {"error": "Database not configured"}

        # Step 1: Fetch active models from MLflow
        active_models = fetch_active_models(str(config.model_tag), logger)
        active_identities = {m["identity"] for m in active_models}

        # Step 2: Get existing jobs from database
        try:
            existing_jobs = get_existing_jobs(
                engine, config.plugin_name, str(config.model_tag), logger
            )
        except Exception as e:
            logger.error(f"❌ Database query failed: {e}")
            return {"error": f"Database error: {str(e)}"}

        existing_identities = set(existing_jobs.keys())

        to_create = active_identities - existing_identities
        to_stop = existing_identities - active_identities
        logger.info(f"🔄 Sync plan: {len(to_create)} to create, {len(to_stop)} to stop")

        plugin_id = get_plugin_id(engine, config.plugin_name)
        plugin_default_config = get_plugin_default_config(config.plugin_name, logger)

        # Step 4: Execute sync
        created = []
        stopped = []
        errors = []
        jobs_to_delete = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "test-system-api-key": config.webhook_test_key,
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
                        f"{config.webhook_url}/api/test-system/model",
                        headers=headers,
                        json={
                            "modelName": model["model_name"],
                            "identity": identity,
                            "tag": str(config.model_tag),
                            "version": str(model["version"]),
                        },
                    )

                    if resp.status_code in (200, 201):
                        logger.info(f"✅ Registered: {identity}")

                        # Create job in database
                        if plugin_id:
                            job_config = build_job_config(
                                model,
                                str(config.model_tag),
                                config.webhook_url,
                                config.webhook_api_key,
                                plugin_default_config,
                            )
                            job_id = create_job_in_db(
                                pm,
                                engine,
                                plugin_id,
                                1,
                                job_config,
                                f"Auto-created for {identity}",
                                logger,
                            )
                            if job_id:
                                logger.info(f"📝 Created job {job_id} for {identity}")

                        created.append(identity)
                    else:
                        error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"⚠️  Failed to create {identity}: {error}")
                        errors.append({"identity": identity, "action": "create", "error": error})

                except Exception as e:
                    logger.error(f"❌ Error creating {identity}: {e}")
                    errors.append({"identity": identity, "action": "create", "error": str(e)})

            # Stop inactive models
            for model_identity in to_stop:
                job_id = existing_jobs.get(model_identity)

                try:
                    resp = await client.post(
                        f"{config.webhook_url}/api/test-system/model/stop",
                        headers=headers,
                        json={"identity": model_identity, "unlockCredential": True},
                    )

                    if resp.status_code in (200, 201):
                        logger.info(f"🛑 Stopped: {model_identity}")
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

        # Step 5: Batch delete stopped jobs
        if jobs_to_delete:
            if not delete_jobs(pm, engine, jobs_to_delete, logger):
                errors.append({"action": "delete_jobs", "job_ids": jobs_to_delete})

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
