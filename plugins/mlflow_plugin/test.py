"""
Test script for MLflow Plugin

Run with: python -m plugins.mlflow_plugin.test
"""
import asyncio
import logging
import os
import dotenv

dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mlflow_plugin_test")

# Set environment variables for testing


async def main():
    from plugins.mlflow_plugin import Plugin
    
    # Test config
    test_config = {
        "model_tag": "uat",
        "webhook_url": "http://localhost:3005",
        "webhook_api_key": "abc",
        "webhook_test_key": "abc",
        "plugin_name": "alpha_miner.plugins.UatUserCustomConfigPlugin"
    }
    
    logger.info("🧪 Starting MLflow Plugin Test")
    logger.info(f"📋 Config: {test_config}")
    
    # Get config instance
    config = Plugin.config(test_config)
    logger.info(f"✅ Config validated: {config}")
    
    # Run the plugin
    logger.info("🚀 Running plugin...")
    result = await Plugin.run(config, logger)
    
    logger.info(f"📊 Result: {result}")
    
    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
    print(f"Created: {result.get('created', [])}")
    print(f"Stopped: {result.get('stopped', [])}")
    print(f"Errors: {result.get('errors', [])}")
    print(f"Active count: {result.get('active_count', 0)}")
    print(f"Existing count: {result.get('existing_count', 0)}")
