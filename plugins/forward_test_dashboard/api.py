from schemas import settings
import httpx
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

API_TIMEOUT_SHORT = 10.0
API_TIMEOUT_LONG = 30.0

base_url = "https://api-quantsigengine-uat.orai.network"
api_key = settings.test_system_api_key


async def _get(
    url: str,
    api_key: str,
    params=None,
    timeout=API_TIMEOUT_SHORT,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={
                    "test-system-api-key": api_key,
                    "accept": "application/json",
                },
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.warning("API error %s: %s", url, e)
    except Exception:
        logger.exception("Unexpected API failure: %s", url)

    return {}


async def get_running_models(**kwargs: Any) -> List[Dict[str, Any]]:
    data = await _get(
        f"{base_url}/api/test-system/models",
        api_key,
        params=kwargs,
    )
    return sorted(data.get("models", []), key=lambda m: m.get("createdAt") or "")


async def fetch_positions(**kwargs: Any) -> List[Dict[str, Any]]:
    data = await _get(
        f"{base_url}/api/test-system/models/positions",
        api_key,
        params=kwargs,
        timeout=API_TIMEOUT_LONG,
    )
    return data.get("positions", [])


async def fetch_stats_running_models(**kwargs: Any) -> List[Dict[str, Any]]:
    data = await _get(
        f"{base_url}/api/test-system/models/stats",
        api_key,
        params=kwargs,
    )
    return sorted(data.get("stats", []), key=lambda m: m.get("startedAt") or "")


async def update_model_config(
    identity: str,
    config: Dict[str, Any],
    config_name: Optional[str] = None,
) -> Dict[str, Any]:
    if not identity:
        raise ValueError("identity is required")
    payload = {
        "identity": identity,
        "config": config,
    }
    if config_name:
        payload["configName"] = config_name

    url = f"{base_url}/api/test-system/model/config"
    timeout = API_TIMEOUT_SHORT
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.put(
                url,
                headers={
                    "test-system-api-key": api_key,
                    "accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.warning("API error %s: %s", url, e)
    except Exception:
        logger.exception("Unexpected API failure: %s", url)

    return {}


async def get_equity_curve_forward_test(
    identity: str,
    start_time: Optional[str],
    end_time: Optional[str],
) -> List[Dict[str, Any]]:
    params = {}
    if start_time:
        params["startDate"] = start_time
    if end_time:
        params["endDate"] = end_time
    data = await _get(
        f"{base_url}/api/test-system/models/{identity}/equity",
        api_key,
        params=params,
        timeout=API_TIMEOUT_LONG,
    )
    return data.get("data", [])
