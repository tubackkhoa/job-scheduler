import os
from typing import Optional

import httpx


def _get_api_config(
    env: str = "production",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> tuple[str, str]:
    if env == "production":
        resolved_url = api_url or os.getenv("MULTI_USER_WEBHOOK_URL", "")
        resolved_key = api_key or os.getenv("MULTI_USER_WEBHOOK_API_KEY", "")
        if not resolved_url or not resolved_key:
            raise ValueError(
                "Production environment requires MULTI_USER_WEBHOOK_URL and MULTI_USER_WEBHOOK_API_KEY env vars"
            )
        return resolved_url, resolved_key

    # For uat, staging, or other envs - require explicit api_url and api_key
    if not api_url or not api_key:
        raise ValueError(f"Environment '{env}' requires explicit api_url and api_key")
    return api_url, api_key


def list_trade_models(
    env: str = "production",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    status: str = "active",
):
    url, key = _get_api_config(env, api_url, api_key)
    resp = httpx.get(
        f"{url}/api/trading-models",
        params={"status": status},
        headers={"Authorization": f"Bearer {key}"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    items = result.get("data", []) if isinstance(result, dict) else result
    return {
        "versions": [
            {"id": item.get("key") or item.get("id"), "name": item.get("name", ""), **item}
            for item in items
        ]
    }


def create_trade_model(
    payload: dict,
    env: str = "production",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    url, key = _get_api_config(env, api_url, api_key)
    payload.setdefault("status", "active")
    resp = httpx.post(
        f"{url}/api/trading-models",
        json=payload,
        headers={"quant-api-key": key},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    return {"id": result.get("key") or result.get("id"), "name": result.get("name", ""), **result}


def deactivate_trade_model(
    key: str,
    env: str = "production",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    url, api_key_resolved = _get_api_config(env, api_url, api_key)
    resp = httpx.put(
        f"{url}/api/trading-models/key/{key}",
        json={"status": "inactive"},
        headers={"quant-api-key": api_key_resolved},
        timeout=30,
    )
    resp.raise_for_status()
    return {"success": True, "message": f"Trade model {key} deactivated"}
