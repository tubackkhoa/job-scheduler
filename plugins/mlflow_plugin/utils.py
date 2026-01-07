"""
MLflow Helper Module

Provides wrapper functions for MLflow experiment tracking.
Supports local SQLite storage with graceful fallback if MLflow is unavailable.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
import numpy as np

from alpha_miner.core.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

import mlflow
from mlflow.tracking import MlflowClient

try:
    import mlflow.xgboost
except ImportError:
    pass

try:
    import mlflow.lightgbm
except ImportError:
    pass

try:
    import mlflow.catboost
except ImportError:
    pass

try:
    import mlflow.sklearn
except ImportError:
    pass

# Global state
_mlflow_initialized = False
_mlflow_enabled = False


def init_mlflow(config: Dict[str, Any]) -> bool:
    """
    Initialize MLflow with configuration.
    
    Reads MLFLOW_TRACKING_URI from environment variable first,
    falls back to config value if not set.
    
    Args:
        config: Dictionary with keys:
            - enabled: bool
            - tracking_uri: str (fallback if MLFLOW_TRACKING_URI not in env)
            - experiment_name: str
    
    Returns:
        True if successfully initialized, False otherwise
    """
    global _mlflow_initialized, _mlflow_enabled
    
    _mlflow_enabled = config.get('enabled', False)
    
    if not _mlflow_enabled:
        logger.info("MLflow tracking disabled in config")
        return False
    
    try:
        # Read from environment first, then config
        tracking_uri = os.getenv('MLFLOW_TRACKING_URI', config.get('tracking_uri', 'sqlite:///data/mlflow/mlflow.db'))
        experiment_name = os.getenv('MLFLOW_EXPERIMENT_NAME', config.get('experiment_name', 'alpha-miner-training'))
        
        # Ensure directory exists for SQLite
        if tracking_uri.startswith('sqlite:///'):
            db_path = tracking_uri.replace('sqlite:///', '')
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Set tracking URI
        mlflow.set_tracking_uri(tracking_uri)
        
        # Set or create experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            mlflow.create_experiment(experiment_name)
        mlflow.set_experiment(experiment_name)
        
        _mlflow_initialized = True
        logger.info(f"✅ MLflow initialized")
        logger.info(f"   Tracking URI: {tracking_uri}")
        logger.info(f"   Experiment: {experiment_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize MLflow: {e}", exc_info=True)
        _mlflow_enabled = False
        return False


def is_enabled() -> bool:
    """Check if MLflow tracking is enabled and initialized."""
    return _mlflow_enabled and _mlflow_initialized


def end_run() -> None:
    """End the current active MLflow run."""
    if not is_enabled():
        return
    
    try:
        mlflow.end_run()
    except Exception as e:
        logger.warning(f"Failed to end MLflow run: {e}")


DEFAULT_LOG_FILE = Path("data/pipeline_output/temp_configs/current_training.log")

@contextmanager
def start_run(
    run_name: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    nested: bool = False,
    enable_log: bool = True,
    log_file: Optional[Path] = None,
):
    """
    Context manager for MLflow run.
    
    Automatically logs training log file (current_training.log) as artifact:
    - At the start of the run (if file exists)
    - At the end of the run (complete log)

    Args:
        run_name: Optional name for the run
        tags: Optional tags dictionary
        nested: If True, create as nested run
    
    Yields:
        mlflow.ActiveRun or None if disabled
    """
    if not is_enabled():
        # MLflow disabled - just yield None and continue normally
        try:
            yield None
        except Exception:
            raise  # Re-raise any exceptions from the with block
        return
    
    if not log_file:
        log_file = DEFAULT_LOG_FILE

    try:
        with mlflow.start_run(run_name=run_name, nested=nested) as run:
            if tags:
                mlflow.set_tags(tags)

            try:
                yield run
            except Exception as e:
                logger.error(f"MLflow run error: {e}", exc_info=True)
                raise
            finally:
                # Log complete training log file at the end of the run
                if log_file.exists() and enable_log:
                    try:
                        log_artifact(str(log_file), artifact_path="logs")
                        logger.info(f"✅ Logged complete training log to MLflow at run end: {log_file}")
                    except Exception as e:
                        logger.warning(f"Failed to log complete training log at run end: {e}")

    except Exception as e:
        logger.error(f"MLflow run error: {e}", exc_info=True)
        raise  # Re-raise to not suppress the error


def log_params(params: Dict[str, Any]) -> None:
    """Log parameters to current MLflow run."""
    if not is_enabled():
        return
    
    try:
        # Flatten nested dicts and convert values to strings
        flat_params = {}
        for key, value in params.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    flat_params[f"{key}.{k}"] = str(v)
            else:
                flat_params[key] = value
        
        mlflow.log_params(flat_params)
    except Exception as e:
        logger.error(f"Failed to log params: {e}", exc_info=True)


def log_metrics(metrics: Dict[str, float], step: Optional[int] = None) -> None:
    """Log metrics to current MLflow run."""
    if not is_enabled():
        return
    
    try:
        # Filter out non-numeric values
        numeric_metrics = {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
        mlflow.log_metrics(numeric_metrics, step=step)
    except Exception as e:
        logger.error(f"Failed to log metrics: {e}", exc_info=True)


def log_cv_summary(fold_metrics: List[Dict[str, float]]) -> None:
    """
    Log cross-validation summary metrics.
    
    Args:
        fold_metrics: List of metric dictionaries from each fold
    """
    if not is_enabled() or not fold_metrics:
        return
    
    try:
        
        avg_metrics = {}
        for key in fold_metrics[0].keys():
            values = [m[key] for m in fold_metrics if key in m and isinstance(m[key], (int, float))]
            if values:
                avg_metrics[f'cv_avg_{key}'] = float(np.mean(values))
                avg_metrics[f'cv_std_{key}'] = float(np.std(values))
        
        mlflow.log_metrics(avg_metrics)
        
    except Exception as e:
        logger.error(f"Failed to log CV summary: {e}", exc_info=True)


def log_cv_folds_artifact(fold_metrics: List[Dict[str, float]], filename: str = "cv_folds.json") -> None:
    """
    Log fold metrics as JSON artifact.
    
    Args:
        fold_metrics: List of metric dictionaries from each fold
        filename: Name of the artifact file
    """
    if not is_enabled() or not fold_metrics:
        return
    
    try:
        import tempfile
        
        # Create temp file with fold metrics
        temp_path = Path(tempfile.gettempdir()) / filename
        with open(temp_path, 'w') as f:
            json.dump(fold_metrics, f, indent=2, default=str)
        
        mlflow.log_artifact(str(temp_path))
        
        # Clean up
        temp_path.unlink(missing_ok=True)
        
        logger.info(f"Logged CV folds artifact: {filename}")
        
    except Exception as e:
        logger.error(f"Failed to log CV folds artifact: {e}", exc_info=True)


def log_model(
    model: Any,
    model_type: str,
    artifact_path: str = "model",
    registered_model_name: Optional[str] = None,
    input_example: Optional[Any] = None
) -> None:
    """
    Log model artifact to MLflow.
    
    Args:
        model: Trained model object
        model_type: Type of model ('xgboost', 'lightgbm', etc.)
        artifact_path: Path/name within MLflow artifacts
        registered_model_name: Optional name to register in Model Registry
        input_example: Optional input example for model signature inference
    """
    if not is_enabled():
        return
    
    try:
        # Create a dummy input example if not provided (for signature inference)
        if input_example is None:
            # Try to get feature count from model
            try:
                if hasattr(model, 'n_features_in_'):
                    n_features = model.n_features_in_
                elif hasattr(model, 'feature_names_in_'):
                    n_features = len(model.feature_names_in_)
                elif hasattr(model, 'n_features_'):
                    n_features = model.n_features_
                else:
                    n_features = 10  # Default fallback
                
                input_example = np.zeros((1, n_features))
            except Exception:
                input_example = None
        
        # Use 'name' parameter instead of deprecated 'artifact_path' for MLflow >= 2.17
        # But keep backward compatibility
        log_kwargs = {
            'registered_model_name': registered_model_name
        }
        
        if input_example is not None:
            log_kwargs['input_example'] = input_example
        
        if model_type == 'xgboost':
            mlflow.xgboost.log_model(model, name=artifact_path, **log_kwargs)  # type: ignore
        elif model_type == 'lightgbm':
            mlflow.lightgbm.log_model(model, name=artifact_path, **log_kwargs)  # type: ignore
        elif model_type == 'catboost':
            mlflow.catboost.log_model(model, name=artifact_path, **log_kwargs)  # type: ignore
        else:
            # Fallback to sklearn
            mlflow.sklearn.log_model(model, name=artifact_path, **log_kwargs)  # type: ignore
        
        logger.info(f"Model logged to MLflow: {artifact_path}")
        if registered_model_name:
            logger.info(f"   Registered as: {registered_model_name}")
        
    except Exception as e:
        logger.error(f"Failed to log model: {e}", exc_info=True)


def log_artifact(local_path: str, artifact_path: Optional[str] = None) -> None:
    """Log a local file as artifact."""
    if not is_enabled():
        return
    
    try:
        mlflow.log_artifact(local_path, artifact_path)
    except Exception as e:
        logger.error(f"Failed to log artifact: {e}", exc_info=True)


def set_tags(tags: Dict[str, str]) -> None:
    """Set tags on current run."""
    if not is_enabled():
        return
    
    try:
        mlflow.set_tags(tags)
    except Exception as e:
        logger.error(f"Failed to set tags: {e}", exc_info=True)


def get_run_id() -> Optional[str]:
    """Get current active run ID."""
    if not is_enabled():
        return None
    
    try:
        active_run = mlflow.active_run()
        return active_run.info.run_id if active_run else None
    except Exception:
        return None


def register_model(run_id: str, artifact_path: str, model_name: str) -> Optional[str]:
    """
    Register a model from a run to the Model Registry.
    
    Args:
        run_id: MLflow run ID
        artifact_path: Path to model artifact in the run
        model_name: Name to register the model under
    
    Returns:
        Model version string or None if failed
    """
    if not is_enabled():
        return None
    
    try:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        result = mlflow.register_model(model_uri, model_name)
        logger.info(f"✅ Model registered: {model_name} v{result.version}")
        return result.version
    except Exception as e:
        logger.error(f"Failed to register model: {e}", exc_info=True)
        return None


# =============================================================================
# MODEL REGISTRY HELPERS
# =============================================================================

def find_models_by_universe_and_alias(universe: str, alias: str = "staging") -> List[Dict[str, Any]]:
    """
    Find registered models by universe tag and alias.
    
    Args:
        universe: Universe tag value (e.g., 'u5', 'u10', 'u41')
        alias: Model alias to filter by (e.g., 'staging', 'production')
    
    Returns:
        List of dicts with model info: name, version, uri
    """
    try:
        tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        
        client = MlflowClient()
        results = []
        
        # Search for models with universe tag
        models = client.search_registered_models(
            filter_string=f"tags.universe = '{universe}'"
        )
        
        for m in models:
            aliases = m.aliases or {}
            if alias in aliases:
                results.append({
                    "name": m.name,
                    "version": aliases[alias],
                    "uri": f"models:/{m.name}@{alias}"
                })
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to find models by universe: {e}", exc_info=True)
        return []


def list_registered_models() -> List[Dict[str, Any]]:
    """
    List all registered models in MLflow Model Registry.
    
    Returns:
        List of dicts with model info: name, latest_versions, tags
    """
    try:
        tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        
        client = MlflowClient()
        models = client.search_registered_models()
        
        results = []
        for m in models:
            results.append({
                "name": m.name,
                "latest_versions": [v.version for v in (m.latest_versions or [])],
                "tags": dict(m.tags) if m.tags else {},
                "aliases": dict(m.aliases) if m.aliases else {}
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to list registered models: {e}", exc_info=True)
        return []



def get_models_with_backtest_watching(
    model_name_prefix: Optional[str] = None,
) -> List[Dict[str, Any]]:
    try:
        tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        client = MlflowClient()
        results: List[Dict[str, Any]] = []

        # get all registered models
        registered_models = client.search_registered_models()

        for model in registered_models:
            # Optional filter theo prefix
            if model_name_prefix and not model.name.startswith(model_name_prefix):
                continue

            # ⚠️ Phải dùng search_model_versions để lấy ALL versions
            versions = client.search_model_versions(f"name='{model.name}'")

            for mv in versions:
                tags = mv.tags or {}

                # Chỉ cần tồn tại key "backtest_watching"
                if "backtest_watching" not in tags:
                    continue

                results.append({
                    "model_name": model.name,
                    "version": mv.version,
                    "stage": mv.current_stage,
                    "run_id": mv.run_id,
                    "tags": dict(tags),
                    "model_uri": f"models:/{model.name}/{mv.version}",
                    "identity": f"{model.name}:{mv.version}"
                })

        return results


    except Exception as e:
        logger.error(f"Failed to find model versions with backtest_watching tag: {e}", exc_info=True)
        return []

# =============================================================================
# CLASS WRAPPER FOR CONVENIENT IMPORT
# =============================================================================

class MLflowHelper:
    """
    Wrapper class to provide object-oriented interface to MLflow helper functions.
    Usage: from alpha_miner.core.mlflow_helper import mlflow_helper
    """
    
    @staticmethod
    def init_mlflow(config: Dict[str, Any]) -> bool:
        return init_mlflow(config)
    
    @staticmethod
    def is_enabled() -> bool:
        return is_enabled()
    
    @staticmethod
    def start_run(run_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None, nested: bool = False):
        return start_run(run_name, tags, nested)
    
    @staticmethod
    def end_run() -> None:
        return end_run()
    
    @staticmethod
    def log_params(params: Dict[str, Any]) -> None:
        return log_params(params)
    
    @staticmethod
    def log_metrics(metrics: Dict[str, float], step: Optional[int] = None) -> None:
        return log_metrics(metrics, step)
    
    @staticmethod
    def log_cv_summary(fold_metrics: List[Dict[str, float]]) -> None:
        return log_cv_summary(fold_metrics)
    
    @staticmethod
    def log_cv_folds_artifact(fold_metrics: List[Dict[str, float]], filename: str = "cv_folds.json") -> None:
        return log_cv_folds_artifact(fold_metrics, filename)
    
    @staticmethod
    def log_model(model: Any, model_type: str, artifact_path: str = "model", registered_model_name: Optional[str] = None, input_example: Optional[Any] = None) -> None:
        return log_model(model, model_type, artifact_path, registered_model_name, input_example)
    
    @staticmethod
    def log_artifact(local_path: str, artifact_path: Optional[str] = None) -> None:
        return log_artifact(local_path, artifact_path)
    
    @staticmethod
    def set_tags(tags: Dict[str, str]) -> None:
        return set_tags(tags)
    
    @staticmethod
    def get_run_id() -> Optional[str]:
        return get_run_id()
    
    @staticmethod
    def register_model(run_id: str, artifact_path: str, model_name: str) -> Optional[str]:
        return register_model(run_id, artifact_path, model_name)



# Singleton instance for convenient import
mlflow_helper = MLflowHelper()