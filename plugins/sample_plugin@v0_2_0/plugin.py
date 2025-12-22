import logging
import pluggy
from pydantic import BaseModel

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    version: str = "2.0"
    symbols: str = ",".join(["BTC", "ETH", "SOL", "LINK"])


class Plugin:

    @hookimpl
    @classmethod
    def schema(cls):
        return Config.model_json_schema()

    @hookimpl
    @classmethod
    def config(cls, json=None):
        return Config.model_validate(json or {})

    @hookimpl
    @classmethod
    async def run(cls, config: Config, logger: logging.Logger):
        from .data import create_signals

        logger.debug(f"running with config: {config}")
        symbols = [s.strip() for s in config.symbols.split(",")]
        signals = create_signals(symbols)
        return signals
