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
from typing import Optional

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
            "ui:field": "Template", "type": "markdown"
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
            "ui:field": "Template", "type": "markdown"
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


def fetch_positions_with_pnl(base_url: str, api_key: str, start_time: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch positions from API with PNL data.
    
    Args:
        base_url: API base URL
        api_key: API key for authentication
        start_time: Start time in ISO format (e.g., '2026-01-01T00:00:00Z')
    
    Returns:
        List of positions with symbol, direction, pnl, entryTime, modelKey
    """
    url = f"{base_url}/api/test-system/models/positions"
    headers = {"test-system-api-key": api_key, "accept": "application/json"}
    
    try:
        if start_time:
            response = httpx.get(url, headers=headers, params={"startTime": start_time}, timeout=30.0)
        else:
            response = httpx.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("positions", []) if data.get("ok") else []
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []


def format_pnl_table(models: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format PNL data as DataFrame with color-coded icons for PNL values and job status."""
    if not models:
        return "No running models found."
    print(models)
    
    # Store original models for latestPostion access
    models_dict = {model.get('identity', ''): model for model in models}
    
    df = pd.DataFrame(models)
    
    # Include latestPositionAt in the columns
    df = df[['modelName', 'identity', 'totalPnl', 'latestPositionAt', 'status']].copy()
    df.columns = ['Model', 'Identity', 'PNL', 'Last Position Time', 'Status']
    
    # Extract all identities to query jobs efficiently
    identities = [model.get('identity', '') for model in models if model.get('identity')]
    
    # Use optimized query to get only jobs with matching model_keys (PostgreSQL JSON operators)
    matched_jobs = dao.get_jobs_by_model_keys(identities) if identities else []
    
    # Create a mapping of identity -> (job_id, active status)
    identity_job_map = {}
    for job in matched_jobs:
        try:
            job_config = json.loads(job.config)
            model_key = job_config.get("model_key")
            if model_key:
                identity_job_map[model_key] = {
                    'job_id': job.id,
                    'active': job.active,
                    'description': job.description or 'No description'
                }
        except:
            continue
    
    # Format PNL with colored arrows and numbers (HTML)
    def format_pnl_with_color(x):
        if pd.notna(x):
            if x > 0:
                # Green arrow and number for profit
                return f"<span style='color: #28a745;'>↗ +${x:.4f}</span>"
            else:
                # Red arrow and number for loss or zero
                return f"<span style='color: #dc3545;'>↘ ${x:.4f}</span>"
        return "$0"
    
    # Format latestPositionAt to UTC time
    def format_last_position(x):
        if pd.isna(x) or x is None or x == '':
            return "-"
        try:
            # Parse the timestamp and convert to UTC
            dt = pd.to_datetime(x)
            # Format as UTC string
            return dt.strftime('%Y-%m-%d %H:%M UTC')
        except:
            return str(x)
    
    # Format latest position info (symbol, direction, PNL) like signals
    def format_latest_position(row):
        identity = row['Identity']
        model = models_dict.get(identity)
        
        if not model or 'latestPostion' not in model:
            return "-"
        
        latest_pos = model.get('latestPostion')
        if not latest_pos:
            return "-"
        
        symbol = latest_pos.get('symbol', '')
        direction = latest_pos.get('direction', '')
        pnl = latest_pos.get('pnl')
        
        if not symbol or not direction:
            return "-"
        
        # Color symbol based on direction (BUY = green, SELL = red)
        if direction.upper() in ['BUY', 'LONG']:
            symbol_colored = f"<span style='color: #28a745; font-weight: bold;'>{symbol}</span>"
        elif direction.upper() in ['SELL', 'SHORT']:
            symbol_colored = f"<span style='color: #dc3545; font-weight: bold;'>{symbol}</span>"
        else:
            symbol_colored = f"**{symbol}**"
        
        # Format PNL with colored arrow - convert to float for comparison
        if pnl is not None:
            try:
                pnl_value = float(pnl)
                if pnl_value > 0:
                    pnl_str = f"<span style='color: #28a745;'>↗ +${pnl_value:.5f}</span>"
                elif pnl_value < 0:
                    pnl_str = f"<span style='color: #dc3545;'>↘ ${pnl_value:.5f}</span>"
                else:
                    pnl_str = "$0"
            except (ValueError, TypeError):
                pnl_str = "-"
        else:
            pnl_str = "-"
        
        return f"{symbol_colored} {pnl_str}"
    
    # Format status based on job existence and active status
    def format_status(row):
        identity = row['Identity']
        job_info = identity_job_map.get(identity)
        
        if not job_info:
            # No job found for this identity
            return "<span style='color: #6c757d;'>⊘ No Job</span>"
        
        job_name = job_info['description']
        is_active = job_info['active']
        
        if is_active:
            return f"<span style='color: #28a745;'>✓ Active ({job_name})</span>"
        else:
            return f"<span style='color: #ffc107;'>⏸ Inactive ({job_name})</span>"
    
    df['PNL'] = df['PNL'].apply(format_pnl_with_color)
    df['Last Position Time'] = df['Last Position Time'].apply(format_last_position)
    df['Latest Position'] = df.apply(format_latest_position, axis=1)
    df['Status'] = df.apply(format_status, axis=1)
    
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
            job_id=scheduler_id, keyword=keyword, n_following=2, limit=50,
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
                    direction = "LONG"
                elif new_mu < 0:
                    direction = "SHORT"
                else:
                    direction = "NONE"
                
                all_table_data.append({
                    'pred_time': pred_time,
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
        
        # Extract identities and use optimized query
        identities = [model.get("identity", "") for model in models if model.get("identity")]
        
        # Use optimized query to get only jobs with matching model_keys
        jobs_list = dao.get_jobs_by_model_keys(identities) if identities else []
        
        # Create mapping of identity -> job for quick lookup
        identity_to_job = {}
        for job in jobs_list:
            try:
                job_config = json.loads(job.config)
                model_key = job_config.get("model_key")
                if model_key:
                    identity_to_job[model_key] = job
            except:
                continue
        
        # Match models with jobs
        matched_jobs = []
        for model in models:
            identity = model.get("identity", "")
            job = identity_to_job.get(identity)
            if job:
                matched_jobs.append({
                    "job_id": job.id,
                    "model_name": model.get("modelName", ""),
                    "identity": identity,
                    "pnl": model.get("totalPnl", 0)
                })
        
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
        
        min_pred_time = combined_df['pred_time'].min()
        start_time_iso = min_pred_time.isoformat() + 'Z'
        
        positions = fetch_positions_with_pnl(
            config.webhook_url,
            config.webhook_api_key,
            start_time_iso
        )        
        # Create a mapping of (symbol, direction, modelKey, pred_time_hour) -> pnl
        # Need to convert BUY/SELL to LONG/SHORT and match by hourly time window
        pnl_map = {}
        for pos in positions:
            symbol = pos.get('symbol', '')
            model_key = pos.get('modelKey', '')
            entry_time_str = pos.get('entryTime', '')
            pnl = pos.get('pnl', 0) or 0
            
            # Parse entryTime and round to hour
            try:
                from datetime import datetime
                entry_time = pd.to_datetime(entry_time_str)
                # Round to hour: 2026-01-20T09:00:21.405Z -> 2026-01-20 09:00:00
                entry_hour = entry_time.floor('h')
                entry_hour_naive = entry_hour.tz_localize(None) if entry_hour.tz is not None else entry_hour
                entry_hour_iso = entry_hour_naive.isoformat()
                
                key = (symbol, model_key, entry_hour_iso)
                pnl_map[key] = pnl
            except:
                continue
        # Map PNL to each signal
        def format_signal_with_pnl(row):
            symbol = row['base_asset']
            direction = row['direction']
            identity = row['_identity']
            is_gated = row['is_gated']
            pred_time = row['pred_time']
            
            pred_hour = pred_time.floor('h')
            # Convert to naive datetime (remove timezone) then to ISO string
            pred_hour_naive = pred_hour.tz_localize(None) if pred_hour.tz is not None else pred_hour
            pred_hour_iso = pred_hour_naive.isoformat()
            
            # Check if this symbol entered an order (exists in pnl_map)
            key = (symbol, identity, pred_hour_iso)
            has_order = key in pnl_map
            
            # Get PNL from positions API
            pnl = pnl_map.get(key, 0)
            
            # Add asterisk marker if entered order
            marker = "*" if has_order else ""
            
            # Color for symbol based on direction
            if direction == "LONG":
                symbol_colored = f"<span style='color: #28a745; font-weight: bold;'>{marker}{symbol}</span>"  # Green
            elif direction == "SHORT":
                symbol_colored = f"<span style='color: #dc3545; font-weight: bold;'>{marker}{symbol}</span>"  # Red
            else:
                symbol_colored = f"**{marker}{symbol}**"
            
            # PNL with colored arrow
            if pnl > 0:
                # Green arrow and number for profit
                pnl_str = f"<span style='color: #28a745;'>↗ +${pnl:.5f}</span>"
            elif pnl < 0:
                # Red arrow and number for loss
                pnl_str = f"<span style='color: #dc3545;'>↘ ${pnl:.5f}</span>"
            else:
                pnl_str = "$0"
            
            # Format: Symbol Direction PNL
            if is_gated:
                return f"~~{symbol_colored}~~ {pnl_str}"
            else:
                return f"{symbol_colored} {pnl_str}"
        
        combined_df['signal'] = combined_df.apply(format_signal_with_pnl, axis=1)

        pivot = combined_df.pivot_table(
            index=['pred_time', 'base_asset'],
            columns='_identity',
            values='signal',
            aggfunc='first'
        )
        
        pivot = pivot.fillna('-')
        
        pivot = pivot.sort_index(level='pred_time', ascending=False)
        
        # if len(pivot) > 50:
        #     pivot = pivot.head(50)
        
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

def _get_pnl_dashboard(config: Config) -> pd.DataFrame:
    """Render PNL dashboard only."""
    if not isinstance(config, Config):
        config = Config.model_validate(config)
    models = get_running_models(config.webhook_url, config.webhook_api_key)
    return format_pnl_table(models)


# ============================================================================
# Plugin
# ============================================================================

class Plugin:
    _env = {
        "get_pnl_dashboard": _get_pnl_dashboard,
        "get_signal_comparison": get_signal_comparison,
    }
    
    @hookimpl
    @classmethod
    def install(cls) -> bool:
        return True
    
    @hookimpl
    @classmethod
    def env(cls) ->  dict[str, Any]:
        return cls._env
    
    @hookimpl
    @classmethod
    def schema(cls, ctx):
        return Config.model_json_schema()
    
    @hookimpl
    @classmethod
    def config(
        cls,
        ctx,
        json: Optional[dict[str, Any]] = None,
        validate: Optional[bool] = False,
    ):
        if isinstance(json, str):
            import json as json_module
            json = json_module.loads(json)
        return Config.model_validate(json or {})
    
    @hookimpl
    @classmethod
    def roles(cls):
        return {"admin"}
    
    @hookimpl
    @classmethod
    async def run(cls, ctx, config: Config, logger: logging.Logger, render: Callable[[str, Environment, dict], Any]):
        logger.info(f"ForwardTestDashboard: {config.webhook_url}")
        return True
