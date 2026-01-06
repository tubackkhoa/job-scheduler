import logging
from jinja2 import BaseLoader, Environment
import pluggy
from pydantic import BaseModel, Field
from .data import create_signals, execute_query, register_table

PROJECT_NAME = "alpha-miner"

hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class Config(BaseModel):
    symbols: str = ",".join(["BTC", "ETH", "SOL", "LINK"])
    md: str = Field(
        """
{% set data = {
    'id': [1, 2, 3, 4],
    'name': ['Alice', 'Bob', 'Charlie', 'David'],
    'age': [25, 30, 35, 40],
    'score': [85.5, 90.0, 88.5, 92.0]
} %}
{{ register_table('people', data) }}
{% set query %}
SELECT id, name, age, score
FROM people
WHERE age > 25
ORDER BY age DESC
{% endset %}
{{ execute_query(query).to_markdown(index=False) }}
""",
        title="Sql result",
        json_schema_extra={
            "ui:field": "Template",
            "type": "markdown",
        },
    )


class Plugin:

    _env = Environment(
        loader=BaseLoader(),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    _env.globals.update({"register_table": register_table, "execute_query": execute_query})

    @hookimpl
    @classmethod
    def env(cls) -> Environment:
        return cls._env

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

        logger.debug(f"running with config: {config}")
        symbols = [s.strip() for s in config.symbols.split(",")]
        signals = create_signals(symbols)
        return signals
