from typing import List, Dict, Any, Optional
from datetime import datetime
import msgspec
import msgspec.json as ms
from pydantic import BaseModel, Field
import logging
from .perp_postgres_client import PerpPostgresClient

logger = logging.getLogger(__name__)


class ForwardTestPluginModel(BaseModel):
    model_name: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    send_to_marketplace: bool = False
    trade_policy_version: Optional[str] = "2.7"
    config: Dict[str, Any]


class ConfigRepository:
    def __init__(self):
        self.table_name = "forward_test_plugin_models"

    def get_all_models(self) -> List[ForwardTestPluginModel]:
        with PerpPostgresClient() as client:
            table_ref = client.get_table_reference(self.table_name)
            query = f"""
                SELECT model_name, status, created_at, updated_at, 
                       send_to_marketplace, trade_policy_version, config
                FROM {table_ref}
            """

            rows = client.fetch_all(query)
            models = []
            for row in rows:
                try:
                    # Config might be returned as string or dict depending on driver
                    config_val = row.get("config", {})
                    if isinstance(config_val, str):
                        try:
                            config_val = ms.decode(config_val)
                        except msgspec.DecodeError:
                            config_val = {}

                    model = ForwardTestPluginModel(
                        model_name=row["model_name"],
                        status=row["status"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        send_to_marketplace=row.get("send_to_marketplace", False),
                        trade_policy_version=row.get("trade_policy_version"),
                        config=config_val,
                    )
                    models.append(model)
                except Exception as e:
                    logger.error(f"Error parsing model row {row}: {e}")

            return models

    def register_model(self, model: ForwardTestPluginModel) -> bool:
        with PerpPostgresClient() as client:
            # Helper to escape single quotes for SQL string literal
            def es(s):
                if s is None:
                    return "NULL"
                return str(s).replace("'", "''")

            config_json = ms.encode(model.config).decode()

            # Construct raw Postgres SQL
            # We must inline values because postgres_execute takes the whole query as a string.
            # Handle boolean explicitly
            send_to_marketplace = "true" if model.send_to_marketplace else "false"

            # Note: We rely on Python's str(datetime) producing standard ISO format which Postgres accepts.

            query = f"""
                INSERT INTO forward_test_plugin_models 
                (model_name, status, created_at, updated_at, send_to_marketplace, trade_policy_version, config)
                VALUES (
                    '{es(model.model_name)}', 
                    '{es(model.status)}', 
                    '{es(model.created_at)}', 
                    '{es(model.updated_at)}', 
                    {send_to_marketplace}, 
                    '{es(model.trade_policy_version)}', 
                    '{es(config_json)}'::jsonb
                )
            """

            try:
                # Use postgres_execute via CALL, passing parameters to CALL to handle escaping of the query string itself
                client.execute_query("CALL postgres_execute(?, ?)", (client.db_alias, query))
                return True
            except Exception as e:
                logger.error(f"Failed to register model {model.model_name}: {e}")
                return False

    def update_config(self, model_name: str, new_config: Dict[str, Any]) -> bool:
        with PerpPostgresClient() as client:

            def es(s):
                if s is None:
                    return "NULL"
                return str(s).replace("'", "''")

            config_json = ms.encode(new_config).decode()
            updated_at = datetime.now()

            query = f"""
                UPDATE forward_test_plugin_models
                SET config = '{es(config_json)}'::jsonb, updated_at = '{es(updated_at)}'
                WHERE model_name = '{es(model_name)}'
            """

            try:
                client.execute_query("CALL postgres_execute(?, ?)", (client.db_alias, query))
                return True
            except Exception as e:
                logger.error(f"Failed to update config for {model_name}: {e}")
                return False

    def get_model(self, model_name: str) -> Optional[ForwardTestPluginModel]:
        with PerpPostgresClient() as client:
            table_ref = client.get_table_reference(self.table_name)
            query = f"""
                SELECT model_name, status, created_at, updated_at, 
                       send_to_marketplace, trade_policy_version, config
                FROM {table_ref}
                WHERE model_name = ?
            """

            row = client.fetch_one(query, (model_name,))
            if row:
                try:
                    config_val = row.get("config", {})
                    if isinstance(config_val, str):
                        try:
                            config_val = ms.decode(config_val)
                        except msgspec.DecodeError:
                            config_val = {}

                    return ForwardTestPluginModel(
                        model_name=row["model_name"],
                        status=row["status"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        send_to_marketplace=row.get("send_to_marketplace", False),
                        trade_policy_version=row.get("trade_policy_version"),
                        config=config_val,
                    )
                except Exception as e:
                    logger.error(f"Error parsing model {model_name}: {e}")
            return None
