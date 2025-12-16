import logging
import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    version: str = "2.0"


logger = logging.getLogger(__name__)


class Plugin:

    @hookimpl
    @classmethod
    def schema(cls):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json):
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: Config):
        logger.info(f"running with config: {config}")
        return True
