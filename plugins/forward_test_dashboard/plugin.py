"""ForwardTestDashboard Plugin - Consolidated Implementation"""
import logging
import pluggy
import httpx
import json
import pandas as pd
from pydantic import BaseModel, Field
from typing import Any, Callable, List, Dict
from jinja2 import Environment, DictLoader
from sqlalchemy import create_engine

from plugins import ui_schema
from log_service import LogService
from models import DAO
from schemas import Settings

PROJECT_NAME = "forward_test_dashboard"
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)

# Initialize services similar to server.py
settings = Settings()
db_engine = create_engine(settings.db_connection)
dao = DAO(db_engine)
logger = LogService(useIndexer=False)

class Config(BaseModel):
    webhook_url: str = Field(
        "https://api-quantsigengine-uat.orai.network",
        title="API URL",
        json_schema_extra=ui_schema({"ui:options": {"size": 6}}),
    )
    webhook_api_key: str = Field(
        "", title="API Key",
        json_schema_extra=ui_schema({"ui:widget": "password", "ui:options": {"size": 6}}),
    )
    
    # PNL Preview
    pnl_preview: str = Field(
        "", title="PNL Dashboard",
        json_schema_extra=ui_schema({
            "ui:field": "Template", "type": "markdown",
            "ui:expr": (
                "{ default: {{ get_pnl_dashboard(webhook_url, webhook_api_key) }} }",
                ["webhook_url", "webhook_api_key"]
            ),
        }),
    )
    
    # Signal Preview
    signal_keyword: str = Field(
        "ranking table ::::", title="Signal Keyword",
        json_schema_extra=ui_schema({"ui:options": {"size": 4}}),
    )
    signal_preview: str = Field(
        "", title="Signal Comparison",
        json_schema_extra=ui_schema({
            "ui:field": "Template", "type": "markdown",
            "ui:expr": (
                "{ default: {{ get_signal_comparison(formData) }} }",
            ),
        }),
    )

    # plugin_id: int = Field(
    #     0,
    #     title="Choose plugin",
    #     json_schema_extra=ui_schema(
    #         {
    #             "ui:field": "Select",
    #             "ui:options": {"size": 6, "id": "id", "title": "package"},
    #             "ui:expr": (
    #                 """{ default: {{ get_all_plugins() | tolist("id", "package") }} }""",
    #                 [],
    #             ),
    #         }
    #     ),
    # )


def get_running_models(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    """Fetch running models from external API."""
    url = f"{base_url}/api/test-system/models"
    headers = {"test-system-api-key": api_key, "accept": "application/json"}
    try:
        response = httpx.get(url, headers=headers, params={"status": "running"}, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        return data.get("models", []) if data.get("ok") else []
    except Exception:
        return []


def format_pnl_table(models: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format PNL data as DataFrame with color-coded icons for PNL values."""
    if not models:
        return "No running models found."
    
    df = pd.DataFrame(models)
    
    df = df[['modelName', 'identity', 'totalPnl', 'status']].copy()
    df.columns = ['Model', 'Identity', 'PNL', 'Status']
    
    # Format PNL with icons: green up arrow for positive, red down arrow for negative/zero
    def format_pnl_with_icon(x):
        if pd.notna(x):
            formatted = f"{x:+.4f}"
            if x > 0:
                return f"🟢 {formatted}"
            else:
                return f"🔴 {formatted}"
        return "0.0000"
    
    df['PNL'] = df['PNL'].apply(format_pnl_with_icon)
    
    df = df.fillna('N/A')    
    return df


def parse_table_message(message: str) -> Dict[str, Any]:
    """Parse table message from logs (Python version of JS parseTableMessage)."""
    if not message:
        return None
    
    import re
    
    # Clean message - remove timestamp and log level prefix
    cleaned = message.strip()
    cleaned = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[.*?\]\s+', '', cleaned)
    
    # Split into lines and filter empty
    lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
    if len(lines) < 2:
        return None
    
    # Parse header
    header = [h for h in lines[0].split() if h]
    if len(header) < 2:
        return None
    
    # Find pred_time column index
    pred_time_index = -1
    for i, col in enumerate(header):
        if col.lower() == 'pred_time':
            pred_time_index = i
            break
    
    # Parse data rows
    data_rows = []
    for i in range(1, len(lines)):
        line = lines[i]
        if not line or len(line) < 3:
            continue
        
        cells = [c for c in line.split() if c]
        
        # Remove index if present (first column is a number)
        if cells and re.match(r'^\d+$', cells[0]):
            cells = cells[1:]
        
        # Merge date and time for pred_time column if needed
        if pred_time_index >= 0 and pred_time_index < len(cells) - 1:
            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            time_pattern = r'^\d{2}:\d{2}:\d{2}$'
            
            if (re.match(date_pattern, cells[pred_time_index]) and 
                re.match(time_pattern, cells[pred_time_index + 1])):
                # Merge date and time
                cells[pred_time_index] = f"{cells[pred_time_index]} {cells[pred_time_index + 1]}"
                cells.pop(pred_time_index + 1)
        
        # Pad or trim to match header length
        while len(cells) < len(header):
            cells.append('')
        cells = cells[:len(header)]
        
        if len(cells) >= min(len(header), 2):
            data_rows.append(cells)
    
    if not data_rows:
        return None
    
    return {'header': header, 'rows': data_rows}


def extract_signals_from_job(job_id: int, keyword: str) -> pd.DataFrame:
    """Extract and parse signals from a single job's logs, returning DataFrame with formatted signals."""
    try:
        scheduler_id = f"job-scheduler.job.{job_id}"
        result = logger.search_logs_with_following(
            job_id=scheduler_id, keyword=keyword, n_following=2, limit=100,
            sort="desc",
        )
        
        all_table_data = []
        
        for group in result.get("groups", []):
            entry = group.get("following_entries", [])
            message = entry[-1].get("message", "")
            
            # Parse the table message
            parsed = parse_table_message(message)
            if not parsed:
                continue
            
            header = parsed['header']
            rows = parsed['rows']
            
            # Find important column indices
            pred_time_idx = -1
            base_asset_idx = -1
            new_mu_idx = -1
            gated_flag_idx = -1
            
            for i, col in enumerate(header):
                col_lower = col.lower()
                if col_lower == 'pred_time':
                    pred_time_idx = i
                elif col_lower == 'base_asset':
                    base_asset_idx = i
                elif col_lower == 'new_mu':
                    new_mu_idx = i
                elif col_lower in ['gated_flag', 'effective_gated_flag']:
                    gated_flag_idx = i
            
            # Extract data from each row
            for row in rows:
                if pred_time_idx < 0 or base_asset_idx < 0:
                    continue
                
                # Extract values
                pred_time = row[pred_time_idx] if pred_time_idx < len(row) else ''
                base_asset = row[base_asset_idx] if base_asset_idx < len(row) else ''
                new_mu_str = row[new_mu_idx] if new_mu_idx >= 0 and new_mu_idx < len(row) else ''
                gated_flag = row[gated_flag_idx] if gated_flag_idx >= 0 and gated_flag_idx < len(row) else ''
                
                # Parse new_mu to determine direction
                try:
                    new_mu = float(new_mu_str) if new_mu_str and new_mu_str.lower() != 'none' else 0
                except:
                    new_mu = 0
                
                is_gated = gated_flag == '1' or gated_flag == '1.0' or gated_flag == 'True'
                
                if new_mu > 0:
                    icon = "🟢"
                    direction = "LONG"
                elif new_mu < 0:
                    icon = "🔴"
                    direction = "SHORT"
                else:
                    icon = "⚪"
                    direction = "NONE"
                
                if is_gated:
                    signal = f"~~{base_asset}~~ {icon}"
                else:
                    signal = f"{base_asset} {icon}"
                
                all_table_data.append({
                    'pred_time': pred_time,
                    'signal': signal,
                    'base_asset': base_asset,
                    'direction': direction,
                    'new_mu': new_mu,
                    'is_gated': is_gated,
                    'gated_flag': gated_flag
                })
        
        if not all_table_data:
            return pd.DataFrame()
        
        # Convert to DataFrame - keep individual signals, don't group yet
        df = pd.DataFrame(all_table_data)
        return df
        
    except Exception as e:
        print(f"Error extracting signals: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def get_signal_comparison(config: Config) -> pd.DataFrame:
    try:
        if not isinstance(config, Config):
            config = Config.model_validate(config)
        
        if not config.webhook_url or not config.webhook_api_key:
            return pd.DataFrame({"message": ["Please provide webhook URL and API key."]})
        
        models = get_running_models(config.webhook_url, config.webhook_api_key)
        if not models:
            return pd.DataFrame({"message": ["No running models found from API."]})
        
        all_jobs = dao.get_all_jobs()
        
        matched_jobs = []
        for model in models:
            identity = model.get("identity", "")
            for job in all_jobs:
                try:
                    job_config = json.loads(job.config)
                    if job_config.get("model_key") == identity:
                        matched_jobs.append({
                            "job_id": job.id,
                            "model_name": model.get("modelName", ""),
                            "identity": identity,
                            "pnl": model.get("totalPnl", 0)
                        })
                        break
                except:
                    continue
        
        if not matched_jobs:
            return pd.DataFrame({"message": ["No jobs matched with running models."]})
        
        all_dfs = []
        for job_info in matched_jobs:
            df = extract_signals_from_job(
                job_info["job_id"], 
                config.signal_keyword
            )
            
            if df.empty:
                continue
            
            # Add identity column to differentiate data source
            df['_identity'] = job_info["identity"]
            all_dfs.append(df)
            print(f"Job {job_info['job_id']} ({job_info['identity']}): {len(df)} signals")
        
        if not all_dfs:
            return pd.DataFrame({"message": ["No signals found."]})
        
        # Combine all DataFrames
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        if 'pred_time' not in combined_df.columns or 'base_asset' not in combined_df.columns:
            return pd.DataFrame({"message": ["Missing required columns (pred_time or base_asset)."]})
        
        # Parse pred_time
        combined_df['pred_time'] = pd.to_datetime(combined_df['pred_time'], errors='coerce')
        combined_df = combined_df.dropna(subset=['pred_time'])
        
        if combined_df.empty:
            return pd.DataFrame({"message": ["No valid timestamps found."]})

        pivot = combined_df.pivot_table(
            index=['pred_time', 'base_asset'],
            columns='_identity',
            values='signal',
            aggfunc='first'
        )
        
        pivot = pivot.fillna('-')
        
        pivot = pivot.sort_index(level='pred_time', ascending=False)
        
        if len(pivot) > 50:
            pivot = pivot.head(50)
        
        pivot = pivot.reset_index()
        
        pivot['pred_time'] = pivot['pred_time'].dt.strftime('%Y-%m-%d %H:%M')
        
        pivot = pivot.rename(columns={
            'pred_time': 'Time',
            'base_asset': 'Symbol'
        })
        
        # Group Time column: replace duplicate consecutive times with empty string
        # This creates a visual grouping effect in the markdown table
        time_col = pivot['Time'].copy()
        for i in range(1, len(time_col)):
            if time_col.iloc[i] == time_col.iloc[i-1]:
                pivot.at[i, 'Time'] = ''
        
        return pivot
        
    except Exception as e:
        print(f"Error in get_signal_comparison: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame({"error": [f"Error: {str(e)}"]})




# ============================================================================
# Plugin
# ============================================================================

class Plugin:
    _env = Environment(
        loader=DictLoader({"base": "{% block content %}{% endblock %}"}),
        autoescape=False, trim_blocks=True, lstrip_blocks=True,
    )
    
    @staticmethod
    def _get_pnl_dashboard(config: Config) -> pd.DataFrame:
        """Render PNL dashboard only."""
        if not isinstance(config, Config):
            config = Config.model_validate(config)
        models = get_running_models(config.webhook_url, config.webhook_api_key)
        return format_pnl_table(models)
    
    _env.globals.update({
        "get_pnl_dashboard": _get_pnl_dashboard.__func__,
        "get_signal_comparison": get_signal_comparison,
    })
    
    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return True
    
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
    def roles(cls):
        return {"admin"}
    
    @hookimpl
    @classmethod
    async def run(cls, config: Config, logger: logging.Logger, render: Callable[[str, Environment, dict], Any]):
        logger.info(f"ForwardTestDashboard: {config.webhook_url}")
        return True
