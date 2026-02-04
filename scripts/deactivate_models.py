
import httpx
import argparse
import logging
import sys
from typing import List
from pathlib import Path
from dotenv import load_dotenv 
load_dotenv()

from schemas import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BASE_URL = settings.uat_endpoint_api
DEFAULT_TIMEOUT = 30


def stop_model(
    base_url: str,
    api_key: str,
    identity: str,
    unlock_credential: bool = True,
    timeout: float = DEFAULT_TIMEOUT
) -> bool:
    url = f"{base_url}/api/test-system/model/stop"
    
    try:
        resp = httpx.post(
            url,
            headers={
                "test-system-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "identity": identity,
                "unlockCredential": unlock_credential
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        logger.info(f"✓ Successfully stopped model: {identity}")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"✗ HTTP error stopping model {identity}: {e.response.status_code} - {e.response.text}")
        return False
    except httpx.RequestError as e:
        logger.error(f"✗ Request error stopping model {identity}: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error stopping model {identity}: {e}")
        return False


def deactivate_models(
    identities: List[str],
    base_url: str,
    api_key: str,
    unlock_credential: bool = True
) -> dict:
    if not identities:
        logger.warning("No model identities provided")
        return {"success": 0, "failed": 0, "total": 0}
    
    logger.info(f"Starting to deactivate {len(identities)} model(s)...")
    
    success_count = 0
    failed_count = 0
    
    for identity in identities:
        identity = identity.strip()
        if not identity:
            continue
            
        if stop_model(base_url, api_key, identity, unlock_credential):
            success_count += 1
        else:
            failed_count += 1
    
    total = success_count + failed_count
    logger.info(f"\nSummary: {success_count}/{total} models stopped successfully")
    
    if failed_count > 0:
        logger.warning(f"{failed_count} model(s) failed to stop")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "total": total
    }


def main():
    parser = argparse.ArgumentParser(
        description="Deactivate (stop) multiple test system models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stop models from command line
  python scripts/deactivate_models.py --identities model1,model2,model3
  python scripts/deactivate_models.py --identities model1 model2 model3
  
  # Stop models from file
  python scripts/deactivate_models.py --file models.txt
  
  # Use custom API URL and key
  python scripts/deactivate_models.py --identities model1,model2 --url https://api.example.com --api-key YOUR_KEY
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--identities', '-i',
        nargs='+',
        help='Model identities to stop (space or comma-separated)'
    )
    input_group.add_argument(
        '--file', '-f',
        help='File containing model identities (one per line)'
    )
    
    # API configuration
    parser.add_argument(
        '--url',
        default=DEFAULT_BASE_URL,
        help=f'Base URL of the API (default: {DEFAULT_BASE_URL})'
    )
    parser.add_argument(
        '--api-key', '-k',
        help='API key for authentication (required if not set in environment)'
    )
    parser.add_argument(
        '--no-unlock',
        action='store_true',
        help='Do not unlock credentials when stopping models'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f'Request timeout in seconds (default: {DEFAULT_TIMEOUT})'
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key
    if not api_key:
        logger.error("API key is required. Please provide --api-key argument")
        sys.exit(1)
    
    # Get model identities
    if args.identities:
        # Handle comma-separated or space-separated identities
        identities = []
        for item in args.identities:
            identities.extend(item.split(','))
        identities = [i.strip() for i in identities if i.strip()]
    
    if not identities:
        logger.error("No model identities to process")
        sys.exit(1)
    
    # Deactivate models
    result = deactivate_models(
        identities=identities,
        base_url=args.url,
        api_key=api_key,
        unlock_credential=not args.no_unlock
    )
    
    # Exit with appropriate code
    if result['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
