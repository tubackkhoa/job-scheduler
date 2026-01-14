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
{% extends "base" %}
{% block content %}
{  
  "quote_asset": {{ quote_asset | tojson }},
  "extra_bars": {{ extra_bars }},
  "base_assets": {{ base_assets | tojson }}
}
{% endblock %}
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
{% set data = {
  "labels": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
  "datasets": [
    {
      "label": "top_5",
      "data": [500,300,-200,400,-100,600,700,-300,200,400,-150,500],
      "borderColor": "blue",
      "backgroundColor": "rgba(0,0,255,0.1)",
      "tension": 0.3
    },
    {
      "label": "top_10",
      "data": [700,-400,350,600,-500,700,800,-200,400,300,-250,700],
      "borderColor": "orange",
      "backgroundColor": "rgba(255,165,0,0.1)",
      "tension": 0.3
    },
    {
      "label": "top_41",
      "data": [1000,500,-700,900,-600,1100,1200,-400,800,700,-300,1000],
      "borderColor": "purple",
      "backgroundColor": "rgba(128,0,128,0.1)",
      "tension": 0.3
    }
  ]
} %}
  
```chart
{
  "type": "line",
  "data": {{ data }},
  "options": {
    "responsive": true,
    "plugins": {
      "title": {
        "display": true,
        "text": "Chatbots PNL Comparison Over Months"
      }
    }
  }
}
"""


def pick(d, keys):
    return {k: d[k] for k in keys if k in d}


def tolist(obj, *include):
    result = []
    for item in obj:
        data = item.to_dict()
        if include:
            data = pick(data, include)
        result.append(data)
    return result
