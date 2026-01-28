import httpx
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

API_TIMEOUT_SHORT = 10.0
API_TIMEOUT_LONG = 30.0


def _get(
    url: str,
    api_key: str,
    params=None,
    timeout=API_TIMEOUT_SHORT,
) -> dict:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
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


def get_running_models(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    data = _get(
        f"{base_url}/api/test-system/models",
        api_key,
        params={"status": "running"},
    )
    return sorted(data.get("models", []), key=lambda m: m.get("createdAt") or "")


def fetch_positions(base_url: str, api_key: str, start_time: Optional[str]) -> List[Dict[str, Any]]:
    data = _get(
        f"{base_url}/api/test-system/models/positions",
        api_key,
        params={"startTime": start_time} if start_time else None,
        timeout=API_TIMEOUT_LONG,
    )
    return data.get("positions", [])

def fetch_stats_running_models(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    data = _get(
        f"{base_url}/api/test-system/models/stats",
        api_key,
        params={"status": "running"},
    )
    return sorted(data.get("stats", []), key=lambda m: m.get("startedAt") or "")