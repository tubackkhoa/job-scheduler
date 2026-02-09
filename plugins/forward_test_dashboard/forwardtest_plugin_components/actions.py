from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
from ..database.config_repository import ConfigRepository, ForwardTestPluginModel
from ..database.db_repository import ForwardTestRepository
import json

logger = logging.getLogger(__name__)

def register_model_config(payload: str) -> bool:
    """
    Register a new model with default configuration.
    """
    repo = ConfigRepository()

    print ("vinhdeptrai ::", payload)

    model_name_mlflow = payload.get("key")
    model_version_mlflow = payload.get("name")

    model_name = model_name_mlflow + "/" + model_version_mlflow
    
    # Check if exists
    existing = repo.get_model(model_name)
    if existing:
        logger.info(f"Model {model_name} already registered.")
        return True
    
    # Default config as per requirements
    # "start_date': thời điểm hiện tại dứoi dạng timestamp"
    default_config = {
        "tp_pct": 2.5,
        "sl_pct": 1.7,
        "start_date": datetime.now().timestamp()
    }
    
    model = ForwardTestPluginModel(
        model_name=model_name,
        config=default_config
    )
    
    result = repo.register_model(model)

    if (result):
        return {"status": "success"}
    else:
        return {"status": "failed"}


def update_model_config(model_name: str, config: Dict[str, Any]) -> bool:
    """
    Update model configuration.
    Input config has 'start_date' as 'YYYY-MM-DD' string.
    Must convert to timestamp (UTC) for DB.
    """
    repo = ConfigRepository()
    
    # Prepare config for DB
    db_config = config.copy()
    
    # Handle start_date conversion: String 'YYYY-MM-DD' -> Timestamp
    if "start_date" in db_config:
        start_date_val = db_config["start_date"]
        if isinstance(start_date_val, str):
            try:
                dt = datetime.strptime(start_date_val, "%Y-%m-%d")
                from datetime import timezone
                dt = dt.replace(tzinfo=timezone.utc)
                db_config["start_date"] = dt.timestamp()
            except ValueError:
                logger.error(f"Invalid date format for start_date: {start_date_val}. Expected YYYY-MM-DD.")
                pass
    
    return repo.update_config(model_name, db_config)

def get_running_models() -> List[Dict[str, Any]]:
    """
    Get all running (active) models from DB.
    Output 'start_date' in conversion: Timestamp -> 'YYYY-MM-DD'.
    Format: [{"identity": model_name, "currentConfig": config}]
    """
    repo = ConfigRepository()
    models = repo.get_all_models()
    
    result = []
    for m in models:
        if m.status != "active":
            continue
            
        display_config = m.config.copy() if m.config else {}
        
        # Convert start_date: Timestamp -> String 'YYYY-MM-DD'
        if "start_date" in display_config:
            ts = display_config["start_date"]
            if isinstance(ts, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ts, tz=datetime.now().astimezone().tzinfo) 
                    from datetime import timezone
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    display_config["start_date"] = dt.strftime("%Y-%m-%d")
                except Exception as e:
                    logger.error(f"Error converting timestamp {ts}: {e}")
            elif isinstance(ts, str):
                 # Already string?
                 pass
                 
        result.append({
            "identity": m.model_name,
            "currentConfig": display_config
        })
        
    return result

def get_running_models_list() -> dict:
    """
    Get all running (active) models from DB.
    Format: [{"id": model_name, "name": model_name}]
    """
    repo = ConfigRepository()
    models = repo.get_all_models()
    
    result = []
    for m in models:
        # Assuming status='active' is what we want, consistent with other methods
        if m.status != "active":
            continue
        
        result.append({"id": m.model_name, "name": m.model_name})
    
    print ("vinhdeptrai", result)
    return {"versions": result}


def get_pnl_from_db(identity: str, start_time: Optional[str], end_time: Optional[str]) -> dict:
    """
    get all position from table forward_test_performance and return pnl list :
    this is format from forward_test_performance using plugins/forward_test_dashboard/database/db_repository.py
    get only list of last_position and return list of last_position from start_time and end_time

    model_id	identity	model_name	total_running_time	status	total_positions	total_pnl	pnl_delta_1h	pnl_delta_4h	pnl_delta_1d	winrate	max_drawdown	last_position	started_at	updated_at
1	u5_mixed_jan16/14	u5_mixed_jan16/14	30d 0h	running	717	6.758100626279863	-1.1629435771860113	-1.9283354473350187	-5.310806041177023	51.46443514644351	-1.1235044676651542	{"pnl": -1.1629435771860113, "side": "BUY", "time": "2026-02-04T05:00:00", "symbol": "SOL"}	2026-01-05T06:00:00	2026-02-04T07:00:00
    """

    repo = ForwardTestRepository()

    start_dt = None
    end_dt = None
    
    # Defaults logic
    if end_time:
        try:
             if end_time.endswith('Z'):
                 end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
             else:
                 end_dt = datetime.fromisoformat(end_time)
        except ValueError:
             end_dt = datetime.now()
    else:
        end_dt = datetime.now()
        
    if start_time:
        try:
             if start_time.endswith('Z'):
                 start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
             else:
                 start_dt = datetime.fromisoformat(start_time)
        except ValueError:
             start_dt = end_dt - timedelta(days=30)
    else:
        start_dt = end_dt - timedelta(days=30)
                
    
    history = repo.get_performance_history(identity, start_dt, end_dt)
    print ("vinhdeptrai1:::", history)
    
    pnl_list = []
    for record in history:
        last_pos = record.get("last_position")
        if not last_pos:
            continue
            
        # Parse if string
        if isinstance(last_pos, str):
            try:
                last_pos = json.loads(last_pos)
            except json.JSONDecodeError:
                continue
        
        # Determine time from record if missing in last_pos
        if "time" not in last_pos and record.get("updated_at"):
             # Use updated_at as fallback time
             updated_at = record["updated_at"]
             if isinstance(updated_at, datetime):
                 last_pos["time"] = updated_at.isoformat()
             else:
                 last_pos["time"] = str(updated_at)
                 
        pnl_list.append(last_pos)
        
    return {"pnl": pnl_list}


def get_equity_curve_forward_test_fromdb(    
        base_url: str,
        api_key: str,
        identity: str,
        start_time: Optional[str],
        end_time: Optional[str]
    ) -> List[dict]:
    """
    This function build equity curve for a specific model.
    it will get list of last_position from get_pnl_from_db, calculate accumulated pnl and return list of equity curve as format bellow.
    return format :
    [{'time': '2026-01-16T12:01:23.634Z', 'openTime': '2026-01-16T10:00:15.764Z', 'pnl': -0.015359999999999673, 'accumulatedPnl': -0.015359999999999673, 'symbol': 'ETH', 'side': 'BUY'}, {'time': '2026-01-20T14:00:20.213Z', 'openTime': '2026-01-20T12:00:18.837Z', 'pnl': -0.06709800000000087, 'accumulatedPnl': -0.08245800000000054, 'symbol': 'BNB', 'side': 'BUY'}, {'time': '2026-01-20T16:00:15.450Z', 'openTime': '2026-01-20T14:00:24.566Z', 'pnl': -0.15017599999999948, 'accumulatedPnl': -0.23263400000000004, 'symbol': 'ETH', 'side': 'BUY'}, {'time': '2026-01-20T17:00:16.200Z', 'openTime': '2026-01-20T16:00:19.988Z', 'pnl': -0.041044999999999554, 'accumulatedPnl': -0.27367899999999956, 'symbol': 'XRP', 'side': 'BUY'}, {'time': '2026-01-20T20:00:17.288Z', 'openTime': '2026-01-20T17:00:20.694Z', 'pnl': -0.057353999999999364, 'accumulatedPnl': -0.33103299999999897, 'symbol': 'BTC', 'side': 'BUY'}]
    """

    # print ("get equity curve for identity: ", identity, start_time, end_time)
    pnl_data = get_pnl_from_db(identity, start_time, end_time)
    raw_pnl_list = pnl_data.get("pnl", [])
    
    equity_curve = []
    accumulated_pnl = 0.0
    
    for item in raw_pnl_list:
        pnl = item.get("pnl", 0.0)
        accumulated_pnl += pnl
        
        # Prepare curve item
        curve_item = {
            "time": item.get("time"),
            # For openTime, if not present, we might want to default to time or None
            # The user example implies openTime is available.
            "openTime": item.get("openTime", item.get("time")), 
            "pnl": pnl,
            "accumulatedPnl": accumulated_pnl,
            "symbol": item.get("symbol"),
            "side": item.get("side")
        }
        
        equity_curve.append(curve_item)
        
    print ("equity curve: ", equity_curve)
    return equity_curve
