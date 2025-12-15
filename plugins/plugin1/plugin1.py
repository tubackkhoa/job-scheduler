import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    version: str = "1.0"


class Plugin1:

    _config = Config()

    @hookimpl
    def init(self, config):
        self._config = self._config.model_validate(config)
        return self._config

    @hookimpl
    def migrate(self, new_config):
        # transform config first
        self._config = self._config.model_validate(new_config)
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
