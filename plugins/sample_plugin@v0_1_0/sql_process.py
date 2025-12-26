from datetime import datetime
from jinja2 import Environment, BaseLoader


env = Environment(
    loader=BaseLoader(),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
env.globals["datetime"] = datetime


def generate_sql(sql_template, params: dict) -> str:

    template = env.from_string(sql_template)
    rendered_sql = template.render(**params)

    return rendered_sql
