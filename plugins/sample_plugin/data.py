from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import inspect, text
import pandas as pd
from sqlalchemy.engine.url import make_url

countries = {
    "USA": [
        "New York",
        "Los Angeles",
        "Chicago",
        "Houston",
        "Phoenix",
        "Philadelphia",
        "San Antonio",
        "San Diego",
        "Dallas",
        "San Jose",
    ],
    "France": [
        "Paris",
        "Marseille",
        "Lyon",
        "Toulouse",
        "Nice",
        "Nantes",
        "Strasbourg",
        "Montpellier",
        "Bordeaux",
        "Lille",
    ],
    "Japan": [
        "Tokyo",
        "Yokohama",
        "Osaka",
        "Nagoya",
        "Sapporo",
        "Fukuoka",
        "Kobe",
        "Kyoto",
        "Kawasaki",
        "Saitama",
    ],
    "Brazil": [
        "São Paulo",
        "Rio de Janeiro",
        "Brasília",
        "Salvador",
        "Fortaleza",
        "Belo Horizonte",
        "Manaus",
        "Curitiba",
        "Recife",
        "Goiânia",
    ],
    "India": [
        "Mumbai",
        "Delhi",
        "Bangalore",
        "Hyderabad",
        "Ahmedabad",
        "Chennai",
        "Kolkata",
        "Surat",
        "Pune",
        "Jaipur",
    ],
}

SQL_TPL = """
{% set infer_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S') %}
{% set users = get_users() %}

WITH time_bounds AS (
  SELECT
    TIMESTAMP '{{ infer_ts }}' AS infer_ts,
    TIMESTAMP '{{ infer_ts }}'
      - INTERVAL '{{ warmup_bars + extra_bars }} hour' AS ts_warmup_start
),

ohlcv_binance_futures_in_range AS (
  SELECT *
  FROM public."ohlcv_binance-futures_1h" t
  CROSS JOIN time_bounds b
  WHERE t.quote_asset = '{{ quote_asset }}'
    AND t.user in {{ users | in_clause }}
    AND t.base_asset IN {{ base_assets | in_clause }}
    AND t.open_time >= b.ts_warmup_start
    AND t.open_time <= b.infer_ts
)

SELECT * FROM ohlcv_binance_futures_in_range;
"""

JSON_TPL = """
{  
  "quote_asset": {{ quote_asset | tojson }},
  "extra_bars": {{ extra_bars }},
  "base_assets": {{ base_assets | tojson }}
}
"""


YAML_TPL = """
quote_asset: {{ quote_asset }}
extra_bars: {{ extra_bars }}
base_assets:
{% for base_asset in base_assets %}
  - {{ base_asset }}
{% endfor %}
"""

MD_TPL = """
{{ run_sql(sql_connection, sql).to_markdown(index=False) }}
"""

DYNAMIC_CODE = """
import { FieldProps } from '@rjsf/utils';

const { useCallback, useState } = React;
const { Box, Button, TextField, Typography } = Mui;
const { buildJinjaContext } = Utils;

export default function ({
  registry,
  onChange,
  formData,
  fieldPathId,
}: FieldProps<string>) {
  const render = useCallback(
    buildJinjaContext(
      registry.formContext.pluginPackage,
      registry.formContext.formData,
    ),
    [registry.formContext],
  );

  const [input, setInput] = useState(
    formData || `{{ dao.get_all_plugins() | pick("title","description") | tojson }}`,
  );
  const [output, setOutput] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await render(input, {});
      setOutput(JSON.stringify(result, null, 2));
    } catch (err: any) {
      setError(err?.message ?? 'Execution failed');
      setOutput('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Typography variant="subtitle1">Jinja Input</Typography>

      <TextField
        multiline
        minRows={4}
        value={input}
        onBlur={() => {
          onChange(input, fieldPathId.path);
        }}
        onChange={(e) => setInput(e.target.value)}
        fullWidth
      />

      <Button variant="contained" onClick={handleRun} disabled={loading}>
        {loading ? 'Running…' : 'Run'}
      </Button>

      <Typography variant="subtitle1">Output (JSON)</Typography>

      <TextField
        multiline
        minRows={6}
        maxRows={10}
        value={output}
        fullWidth
        InputProps={{ readOnly: true }}
      />

      {error && <Typography color="error">{error}</Typography>}
    </Box>
  );
}
"""


async def get_namespace(engine: AsyncEngine) -> dict:
    async with engine.begin() as conn:

        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            namespace = {}
            for table_name in inspector.get_table_names():
                # (optional) skip sqlite internal tables
                if table_name.startswith("sqlite_"):
                    continue

                columns = inspector.get_columns(table_name)
                namespace[table_name] = [col["name"] for col in columns]

            return namespace

        return await conn.run_sync(_inspect)


async def get_db_info(sql_connection: str):
    engine = create_async_engine(sql_connection)

    dialect = make_url(sql_connection).get_backend_name()
    namespace = await get_namespace(engine)

    return {"dialect": dialect, "namespace": namespace}


async def run_sql(sql_connection: str, sql: str) -> pd.DataFrame:
    engine = create_async_engine(sql_connection)
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))

        rows = result.fetchall()
        return pd.DataFrame(rows, columns=list(result.keys()))
