import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    version: str = "1.0"


class Plugin:

    @hookimpl
    @classmethod
    def schema(cls):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json):
        if json is None:
            return Config()
        return Config.model_validate(json)

    @hookimpl
    @classmethod
    async def run(cls, config: Config):
        return True
