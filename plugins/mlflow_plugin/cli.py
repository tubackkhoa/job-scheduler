import argparse
import json
import os
import sys
from typing import Optional, Dict, Any, List

import httpx


def get_plugins(api_server: str) -> List[Dict[str, Any]]:
    """GET /plugins - Get all plugins with their jobs"""
    resp = httpx.get(f"{api_server}/plugins", timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def find_plugin_by_name(api_server: str, plugin_name: str) -> Optional[Dict[str, Any]]:
    """Find a plugin by package name"""
    plugins = get_plugins(api_server)
    for plugin in plugins:
        if plugin.get("package") == plugin_name:
            return plugin
    return None


def find_job_by_model_identify(
    api_server: str, 
    plugin_id: int, 
    model_identify: str,
    model_tag: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find a job by model_identity in its config"""
    plugins = get_plugins(api_server)
    
    for plugin in plugins:
        if plugin.get("id") != plugin_id:
            continue
            
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
        args.api_server, 
        plugin_id, 
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
        "model_identity": args.model_identify,
        "webhook_url": args.webhook_api,
        "webhook_api_key": args.webhook_api_key,
        "webhook_test_key": args.webhook_test_key or "",
    }
    
    description = f"CLI-created job for {args.model_identify}"
    
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
        new_job = find_job_by_model_identify(
            args.api_server,
            plugin_id,
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
        args.api_server, 
        plugin_id, 
        args.model_identify,
        args.model_tag
    )
    
    if not job:
        print(f"❌ Job not found for model: {args.model_identify}")
        return 1
    
    job_id = job["id"]
    print(f"🛑 Stopping job ID: {job_id}")
    
    try:
        result = activate_job(args.api_server, job_id, False)
        print(f"✅ Job stopped: {result}")
        
        if args.delete:
            print(f"🗑️  Deleting job ID: {job_id}")
            delete_result = delete_job(args.api_server, job_id)
            print(f"✅ Job deleted: {delete_result}")
        
        return 0
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Failed to stop job: {e.response.status_code} - {e.response.text}")
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
        choices=["start", "stop"],
        help="Action: 'start' to create/activate, 'stop' to deactivate"
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
        choices=["staging", "production", "uat"],
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
    
    args = parser.parse_args()
    
    if args.action == "start":
        if not args.webhook_api:
            parser.error("--webhook-api is required for 'start'")
        if not args.webhook_api_key:
            parser.error("--webhook-api-key is required for 'start'")
    
    print(f"🎯 MLflow Job CLI - {args.action.upper()}")
    print(f"   API: {args.api_server}")
    print(f"   Plugin: {args.plugin_name}")
    print(f"   Model: {args.model_identify} ({args.model_tag})")
    print()
    
    try:
        if args.action == "start":
            exit_code = action_start(args)
        else:
            exit_code = action_stop(args)
        
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
