import os
from enum import Enum
from typing import Optional

import httpx

from enforcer import ExecutionContext, global_permission


class ModelType(str, Enum):
    top10_assets = "top10_assets"
    top5_assets = "top5_assets"
    top41_assets = "top41_assets"
    btc_model = "btc_model"
    all = "all"

    def __str__(self):
        return self.value


def _is_test_env(env: str) -> bool:
    return env == "forward_test"


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


@global_permission("job")
def list_trade_models(
    ctx: ExecutionContext,
    env: str = "production",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    status: str = "active",
):
    versions = []
    try:
        url, key = _get_api_config(env, api_url, api_key)
        if _is_test_env(env):
            # Test env: GET /api/test-system/models?status=running
            resp = httpx.get(
                f"{url}/api/test-system/models?status=running",
                headers={"test-system-api-key": key, "Content-Type": "application/json"},
                timeout=60,
            )
        else:
            resp = httpx.get(
                f"{url}/api/trading-models",
                params={"status": "active"},
                headers={"quant-api-key": key, "Content-Type": "application/json"},
                timeout=30,
            )
        resp.raise_for_status()
        result = resp.json()
        print("result: ", result)
        if _is_test_env(env):
            items = result.get("models", [])
            print("items: ", items)
            for item in items:
                versions.append({"id": item.get("identity"), "name": item.get("identity", "")})
        else:
            items = result.get("data", []) if isinstance(result, dict) else result
            for item in items:
                versions.append(
                    {"id": item.get("key") or item.get("id"), "name": item.get("key", "")}
                )
        return {"versions": versions}
    except Exception as e:
        return {"versions": [{"id": item.value, "name": item.value} for item in ModelType]}


@global_permission("job")
def create_trade_model(
    ctx: ExecutionContext,
    payload: dict,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    env: str = "production",
):
    url, key = _get_api_config(env, api_url, api_key)
    print(payload)

    if _is_test_env(env):
        # Test env: POST /api/test-system/model
        headers = {"test-system-api-key": key, "Content-Type": "application/json"}
        identity = payload.get("key", payload.get("key", ""))
        test_payload = {
            "modelName": identity,
            "identity": identity,
            "tag": payload.get("tag", ""),
            "version": "1",
        }
        resp = httpx.post(
            f"{url}/api/test-system/model",
            headers=headers,
            json=test_payload,
            timeout=30,
        )
        if "exist" in resp.text.lower() or resp.status_code == 409:
            start_resp = httpx.post(
                f"{url}/api/test-system/model/start",
                headers=headers,
                json={"identity": identity},
                timeout=30,
            )
            start_resp.raise_for_status()
            return {"id": identity, "name": identity, "started": True}
        resp.raise_for_status()
        result = resp.json()
        return {"id": result.get("key") or result.get("id") or identity, "name": identity, **result}

    # Production: POST /api/trading-models
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


@global_permission("job")
def deactivate_trade_model(
    ctx: ExecutionContext,
    key: str,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    env: str = "production",
):
    url, api_key_resolved = _get_api_config(env, api_url, api_key)

    if _is_test_env(env):
        # Test env: POST /api/test-system/model/stop
        resp = httpx.post(
            f"{url}/api/test-system/model/stop",
            headers={"test-system-api-key": api_key_resolved, "Content-Type": "application/json"},
            json={"identity": key, "unlockCredential": True},
            timeout=30,
        )
    else:
        # Production: PUT /api/trading-models/key/{key}
        resp = httpx.put(
            f"{url}/api/trading-models/key/{key}",
            json={"status": "inactive"},
            headers={"quant-api-key": api_key_resolved},
            timeout=30,
        )

    resp.raise_for_status()
    return {"success": True, "message": f"Trade model {key} deactivated"}
