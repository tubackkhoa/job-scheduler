import argparse
import json
import os
import sys
from typing import Optional, Dict, Any, List

import httpx


def find_plugin_by_name(api_server: str, plugin_name: str) -> Optional[Dict[str, Any]]:
    """Find a plugin by package name using the optimized endpoint"""
    try:
        resp = httpx.get(f"{api_server}/plugin/by-name/{plugin_name}", timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise


def find_job_by_model_identify(
    plugin: Dict[str, Any],
    model_identify: str,
    model_tag: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find a job by model_identity in its config"""
    for job in plugin.get("jobs", []):
        config_str = job.get("config", "{}")
        try:
            config = json.loads(config_str) if isinstance(config_str, str) else config_str
        except json.JSONDecodeError:
            continue
        
        if config.get("model_identity") == model_identify:
            if model_tag is None or config.get("model_tag") == model_tag:
                return job
    
    return None


def create_job(
    api_server: str,
    plugin_id: int,
    session_id: int,
    config: Dict[str, Any],
    description: str = ""
) -> Dict[str, Any]:
    """
    POST /config/0 - Create a new job
    
    Expected payload:
    {
        "pluginId": int,
        "sessionId": int,
        "config": {...},  # Will be validated by plugin.config()
        "description": str
    }
    """
    payload = {
        "pluginId": plugin_id,
        "sessionId": session_id,
        "config": config,
        "description": description,
    }
    
    resp = httpx.post(
        f"{api_server}/config/0",
        json=payload,
        timeout=30.0
    )
    resp.raise_for_status()
    return resp.json()


def activate_job(api_server: str, job_id: int, activation: bool) -> Dict[str, Any]:
    """
    POST /activate/{job_id}/{activation} - Activate or deactivate a job
    """
    activation_str = "true" if activation else "false"
    resp = httpx.post(
        f"{api_server}/activate/{job_id}/{activation_str}",
        timeout=30.0
    )
    resp.raise_for_status()
    return resp.json()


def mlflow_sync(api_server: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST /api/mlflow/sync - Trigger MLflow model sync
    """
    resp = httpx.post(
        f"{api_server}/api/mlflow/sync",
        json=config,
        timeout=300.0
    )
    resp.raise_for_status()
    return resp.json()


def delete_job(api_server: str, job_id: int) -> Dict[str, Any]:
    """
    POST /delete/{job_id} - Delete a job
    """
    resp = httpx.post(
        f"{api_server}/delete/{job_id}",
        timeout=30.0
    )
    resp.raise_for_status()
    return resp.json()


def action_start(args: argparse.Namespace) -> int:
    """Start action: Create and activate a new job"""
    print(f"🔍 Finding plugin: {args.plugin_name}")
    
    plugin = find_plugin_by_name(args.api_server, args.plugin_name)
    if not plugin:
        print(f"❌ Plugin not found: {args.plugin_name}")
        return 1
    
    plugin_id = plugin["id"]
    print(f"✅ Found plugin ID: {plugin_id}")
    
    # Check if job already exists
    existing_job = find_job_by_model_identify(
        plugin,
        args.model_identify,
        args.model_tag
    )
    
    if existing_job:
        job_id = existing_job["id"]
        print(f"⚠️  Job already exists (ID: {job_id}), activating...")
        result = activate_job(args.api_server, job_id, True)
        print(f"✅ Job activated: {result}")
        return 0
    
    # Build config - these fields will be validated by target plugin's config()
    config = {
        "model_tag": args.model_tag,
        "model_type": args.model_type,
        "model_identity": args.model_identify,
        "webhook_url": args.webhook_api,
        "webhook_api_key": args.webhook_api_key,
        "webhook_test_key": args.webhook_test_key or "",
        "enable_use_default_config": False,
    }
    
    description = f"CLI-created job for {args.model_identify}"
    
    # Call webhook to register/start model
    print(f"📞 Calling webhook to register model: {args.model_identify}")
    try:
        headers = {
            "test-system-api-key": args.webhook_test_key or "",
            "Content-Type": "application/json",
        }
        
        # Try to create model first
        resp = httpx.post(
            f"{args.webhook_api}/api/test-system/model",
            headers=headers,
            json={
                "modelName": args.model_identify.split(":")[0],  # Extract model name from identity
                "identity": args.model_identify,
                "tag": args.model_tag,
                "version": args.model_identify.split(":")[-1] if ":" in args.model_identify else "1",
            },
            timeout=30.0
        )
        
        if resp.status_code in (200, 201):
            print(f"✅ Model registered via webhook: {args.model_identify}")
        elif "exist" in resp.text.lower() or resp.status_code == 409:
            # Model already exists, try to start it
            print(f"⚠️  Model already exists, calling start endpoint...")
            start_resp = httpx.post(
                f"{args.webhook_api}/api/test-system/model/start",
                headers=headers,
                json={"identity": args.model_identify},
                timeout=30.0
            )
            
            if start_resp.status_code in (200, 201):
                print(f"✅ Model started via webhook: {args.model_identify}")
            else:
                print(f"⚠️  Failed to start model: {start_resp.status_code} - {start_resp.text[:200]}")
                return 1
        else:
            print(f"⚠️  Webhook returned status {resp.status_code}: {resp.text[:200]}")
            return 1
            
    except httpx.HTTPError as e:
        print(f"❌ Webhook call failed: {e}")
        return 1
    
    print(f"📝 Creating job with config: {json.dumps(config, indent=2)}")
    
    try:
        result = create_job(
            args.api_server,
            plugin_id,
            args.session_id,
            config,
            description
        )
        print(f"✅ Job created successfully!")
        print(f"   Response: {json.dumps(result, indent=2)}")
        
        # Find the newly created job to activate it
        # Need to refresh plugin data to get the new job
        plugin = find_plugin_by_name(args.api_server, args.plugin_name)
        if plugin:
            new_job = find_job_by_model_identify(
                plugin,
                args.model_identify,
                args.model_tag
            )
            
            if new_job:
                job_id = new_job["id"]
                print(f"🚀 Activating job ID: {job_id}")
                activate_result = activate_job(args.api_server, job_id, True)
                print(f"✅ Job activated: {activate_result}")
        
        return 0
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Failed to create job: {e.response.status_code} - {e.response.text}")
        return 1


def action_sync(args: argparse.Namespace) -> int:
    """Sync action: Run full MLflow sync flow"""
    print(f"🔄 Starting MLflow sync...")
    print(f"   Model tag: {args.model_tag}")
    print(f"   Plugin: {args.plugin_name}")
    print()
    
    config = {
        "plugin_name": args.plugin_name,
        "model_tag": args.model_tag,
        "webhook_url": args.webhook_api,
        "webhook_api_key": args.webhook_api_key,
        "webhook_test_key": args.webhook_test_key or "",
        "session_id": args.session_id,
        "model_type": args.model_type,
        "enable_use_default_config": False,
    }
    
    try:
        result = mlflow_sync(args.api_server, config)
        
        print(f"✅ Sync complete!")
        print(f"   📊 Active models: {result['active_count']}")
        print(f"   📊 Existing jobs: {result['existing_count']}")
        print(f"   ✨ Created: {len(result['created'])} models")
        print(f"   🛑 Stopped: {len(result['stopped'])} models")
        
        if result['created']:
            print(f"\n   Created models:")
            for identity in result['created']:
                print(f"     • {identity}")
        
        if result['stopped']:
            print(f"\n   Stopped models:")
            for identity in result['stopped']:
                print(f"     • {identity}")
        
        if result['errors']:
            print(f"\n   ⚠️  Errors: {len(result['errors'])}")
            for err in result['errors']:
                print(f"     • {err}")
            return 1
        
        return 0
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Sync failed: {e.response.status_code} - {e.response.text}")
        return 1


def action_stop(args: argparse.Namespace) -> int:
    """Stop action: Deactivate an existing job"""
    print(f"🔍 Finding plugin: {args.plugin_name}")
    
    plugin = find_plugin_by_name(args.api_server, args.plugin_name)
    if not plugin:
        print(f"❌ Plugin not found: {args.plugin_name}")
        return 1
    
    plugin_id = plugin["id"]
    print(f"✅ Found plugin ID: {plugin_id}")
    
    # Find job by model_identify
    job = find_job_by_model_identify(
        plugin,
        args.model_identify,
        args.model_tag
    )
    
    if not job:
        print(f"❌ Job not found for model: {args.model_identify}")
        return 1
    
    job_id = job["id"]
    
    # Parse job config to get webhook settings
    config_str = job.get("config", "{}")
    try:
        config = json.loads(config_str) if isinstance(config_str, str) else config_str
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse job config: {e}")
        return 1
        
    # Use webhook settings from CLI args if provided, otherwise fall back to job config
    webhook_url = args.webhook_api or config.get("webhook_url")
    webhook_test_key = args.webhook_test_key or config.get("webhook_test_key", "")
    model_identity = args.model_identify
    
    if webhook_url:
        print(f"� Calling webhook to stop model: {model_identity}")
        try:
            headers = {
                "test-system-api-key": webhook_test_key,
                "Content-Type": "application/json",
            }
            
            resp = httpx.post(
                f"{webhook_url}/api/test-system/model/stop",
                headers=headers,
                json={"identity": model_identity, "unlockCredential": True},
                timeout=30.0
            )
            
            if resp.status_code in (200, 201):
                print(f"✅ Webhook stopped model: {model_identity}")
            else:
                print(f"⚠️  Webhook returned status {resp.status_code}: {resp.text[:200]}")
                if not args.force:
                    print(f"💡 Use --force to proceed anyway")
                    return 1
                    
        except httpx.HTTPError as e:
            print(f"⚠️  Webhook call failed: {e}")
            if not args.force:
                print(f"💡 Use --force to proceed anyway")
                return 1
    else:
        print(f"⚠️  No webhook_url found in job config, skipping webhook call")
    
    # Now deactivate/delete the job
    print(f"🛑 Deactivating job ID: {job_id}")
    try:
        result = activate_job(args.api_server, job_id, False)
        print(f"✅ Job deactivated: {result}")
        
        if args.delete:
            print(f"🗑️  Deleting job ID: {job_id}")
            delete_result = delete_job(args.api_server, job_id)
            print(f"✅ Job deleted: {delete_result}")
        
        return 0
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Failed to deactivate job: {e.response.status_code} - {e.response.text}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="MLflow Job Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=["start", "stop", "sync"],
        help="Action: 'start' to create/activate, 'stop' to deactivate, 'sync' to run full flow"
    )

    parser.add_argument(
        "--model-type",
        type=str,
        required=False,
        default="mlflow_custom",
        help="Model type: 'mlflow_custom'"
    )
    
    parser.add_argument(
        "--api-server",
        type=str,
        default=os.getenv("MLFLOW_API_SERVER", "http://localhost:8000"),
        help="Job scheduler API URL (default: $MLFLOW_API_SERVER)"
    )
    
    parser.add_argument(
        "--plugin-name",
        type=str,
        required=True,
        help="Target plugin package name"
    )
    
    parser.add_argument(
        "--model-identify",
        type=str,
        required=True,
        help="Model identity (e.g., 'model_name:version')"
    )
    
    parser.add_argument(
        "--model-tag",
        type=str,
        default="uat",
        help="Model tag (default: uat)"
    )
    
    parser.add_argument(
        "--webhook-api",
        type=str,
        default=os.getenv("MLFLOW_WEBHOOK_API", ""),
        help="Webhook API URL (required for 'start')"
    )
    
    parser.add_argument(
        "--webhook-api-key",
        type=str,
        default=os.getenv("MLFLOW_WEBHOOK_API_KEY", ""),
        help="Webhook API key (required for 'start')"
    )
    
    parser.add_argument(
        "--webhook-test-key",
        type=str,
        default=os.getenv("MLFLOW_WEBHOOK_TEST_KEY", ""),
        help="Webhook test key (optional)"
    )
    
    parser.add_argument(
        "--session-id",
        type=int,
        default=1,
        help="Session ID (default: 1)"
    )
    
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete job after stopping (only for 'stop')"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force stop even if webhook call fails (only for 'stop')"
    )
    
    args = parser.parse_args()
    
    if args.action in ["start", "sync"]:
        if not args.webhook_api:
            parser.error(f"--webhook-api is required for '{args.action}'")
        if not args.webhook_api_key:
            parser.error(f"--webhook-api-key is required for '{args.action}'")
    
    print(f"🎯 MLflow Job CLI - {args.action.upper()}")
    print(f"   API: {args.api_server}")
    print(f"   Plugin: {args.plugin_name}")
    print(f"   Model: {args.model_identify} ({args.model_tag})")
    print()
    
    try:
        if args.action == "start":
            exit_code = action_start(args)
        elif args.action == "stop":
            exit_code = action_stop(args)
        else:  # sync
            exit_code = action_sync(args)
        
        sys.exit(exit_code)
        
    except httpx.ConnectError as e:
        print(f"❌ Connection error: {args.api_server}")
        print(f"   {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
