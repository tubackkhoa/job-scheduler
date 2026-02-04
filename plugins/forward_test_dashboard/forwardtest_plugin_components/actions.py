from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
from ..database.config_repository import ConfigRepository, ForwardTestPluginModel

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
    
    return repo.register_model(model)

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

def get_running_models_list() -> List[str]:
    """
    Get all running (active) models from DB.
    Output 'start_date' in conversion: Timestamp -> 'YYYY-MM-DD'.
    Format: [model_name]
    """
    repo = ConfigRepository()
    models = repo.get_all_models()
    
    result = []
    for m in models:
        if m.status != "active":
            continue
            
        result.append(m.model_name)
        
    print ("vinhdeptrai1", result)
    return result
