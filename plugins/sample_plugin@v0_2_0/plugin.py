import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    version: str = "2.0"


class Plugin:

    _config = Config()

    @hookimpl
    def set_config(self, config):
        self._config = self._config.model_validate(config)
        return self._config

    @hookimpl
    def schema(self):
        return self._config.model_json_schema()

    @hookimpl
    def config(self):
        return self._config

    @hookimpl
    async def run(self):
        return self._config
