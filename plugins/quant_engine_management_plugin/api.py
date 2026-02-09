from enum import Enum
import httpx
from enforcer import ExecutionContext


base_url = "https://api-quantsigengine-uat.orai.network"
api_key = "Au4mL7ugEkD4qxxmYPe9f1bH"


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


def list_trade_models(
    ctx: ExecutionContext,
    env: str = "production",
    status: str = "active",
):
    versions = []
    try:

        if _is_test_env(env):
            # Test env: GET /api/test-system/models?status=running
            resp = httpx.get(
                f"{base_url}/api/test-system/models?status=running",
                headers={"test-system-api-key": api_key, "Content-Type": "application/json"},
                timeout=60,
            )
        else:
            resp = httpx.get(
                f"{base_url}/api/trading-models",
                params={"status": "active"},
                headers={"quant-api-key": api_key, "Content-Type": "application/json"},
                timeout=30,
            )
        resp.raise_for_status()
        result = resp.json()

        if _is_test_env(env):
            items = result.get("models", [])
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


def create_trade_model(
    ctx: ExecutionContext,
    payload: dict,
    env: str = "production",
):

    if _is_test_env(env):
        # Test env: POST /api/test-system/model
        headers = {"test-system-api-key": api_key, "Content-Type": "application/json"}
        identity = payload.get("key", payload.get("key", ""))
        test_payload = {
            "modelName": identity,
            "identity": identity,
            "tag": payload.get("tag", ""),
            "version": "1",
        }
        resp = httpx.post(
            f"{base_url}/api/test-system/model",
            headers=headers,
            json=test_payload,
            timeout=30,
        )
        if "exist" in resp.text.lower() or resp.status_code == 409:
            start_resp = httpx.post(
                f"{base_url}/api/test-system/model/start",
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
        f"{base_url}/api/trading-models",
        json=payload,
        headers={"quant-api-key": api_key},
        timeout=30,
    )
    if "exists" in resp.text.lower() or resp.status_code == 409:
        start_resp = httpx.put(
                f"{url}/api/trading-models/key/{payload.get('key')}",
                headers={"quant-api-key": key},
                json=payload,
                timeout=30,
            )
        start_resp.raise_for_status()
        return {"id": payload.get("key"), "name": payload.get("key"), "started": True}
    resp.raise_for_status()
    result = resp.json()
    return {"id": result.get("key") or result.get("id"), "name": result.get("name", ""), **result}


def deactivate_trade_model(
    ctx: ExecutionContext,
    key: str,
    env: str = "production",
):

    if _is_test_env(env):
        # Test env: POST /api/test-system/model/stop
        resp = httpx.post(
            f"{base_url}/api/test-system/model/stop",
            headers={"test-system-api-key": api_key, "Content-Type": "application/json"},
            json={"identity": key, "unlockCredential": True},
            timeout=30,
        )
    else:
        # Production: PUT /api/trading-models/key/{key}
        resp = httpx.put(
            f"{base_url}/api/trading-models/key/{key}",
            json={"status": "inactive"},
            headers={"quant-api-key": api_key},
            timeout=30,
        )

    resp.raise_for_status()
    return {"success": True, "message": f"Trade model {key} deactivated"}


def activate_forwardtest_model(
    ctx: ExecutionContext,
    key: str,
    env: str = "production",
):

    if _is_test_env(env):
        # Test env: POST /api/test-system/model/start
        resp = httpx.post(
            f"{base_url}/api/test-system/model/start",
            headers={"test-system-api-key": api_key, "Content-Type": "application/json"},
            json={"identity": key},
            timeout=30,
        )
    else:
        # Production: PUT /api/trading-models/key/{key}
        resp = httpx.put(
            f"{url}/api/trading-models/key/{key}",
            json={"status": "active"},
            headers={"quant-api-key": api_key_resolved},
            timeout=30,
        )

    resp.raise_for_status()
    return {"success": True, "message": f"Trade model {key} activated"}


def activate_forwardtest_model(
    ctx: ExecutionContext,
    key: str,
    env: str = "production",
):

    if _is_test_env(env):
        # Test env: POST /api/test-system/model/start
        resp = httpx.post(
            f"{base_url}/api/test-system/model/start",
            headers={"test-system-api-key": api_key, "Content-Type": "application/json"},
            json={"identity": key},
            timeout=30,
        )
        resp.raise_for_status()
        return {"success": True, "message": f"Trade model {key} activated"}
    else:
        raise ValueError("Environment must be 'forward_test' for activate_forwardtest_model")
