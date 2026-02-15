import argparse
import sys
import json
import logging
from typing import Tuple

from config import load_config, validate_config, ConfigError
from api import WavelogAPI, WavelogAPIError


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        fmt='%(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    
    logger.setLevel(level)
    logger.addHandler(handler)


def log_version_info(version_data: dict) -> None:
    logger.info("Wavelog API Information")
    logger.info(f"Wavelog Version: {version_data.get('version', 'N/A')}")


def check_api_health(api_client: WavelogAPI) -> bool:
    try:
        logger.info("Checking Wavelog API availability...")
        version_data = api_client.get_version()
        logger.info("Wavelog API is available!")
        log_version_info(version_data)
        return True
    except WavelogAPIError as e:
        logger.error(f"API error: {e}")
        return False


def download_adif(api_client: WavelogAPI) -> Tuple[str, int]:
    try:
        logger.info(f"Downloading contacts in ADIF format from station {api_client.station_id}...")
        adif_content, qso_count = api_client.get_contacts_adif()
        logger.info(f"Successfully downloaded {qso_count} QSOs")
        return adif_content, qso_count
    except WavelogAPIError as e:
        logger.error(f"API error while downloading ADIF: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description='QSLMaster - Download QSO from Wavelog for QSL card label preparation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s --config config.json
  %(prog)s -c /path/to/config.json
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose mode (more information)'
    )
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        
        validate_config(config)
        logger.info("Configuration loaded and validated")
        
        if args.verbose:
            logger.debug(f"Station ID: {config['station_id']}")
            logger.debug(f"Wavelog URL: {config['wavelog_url']}")
        
        api_client = WavelogAPI(
            base_url=config['wavelog_url'],
            api_key=config['api_key'],
            station_id=config['station_id']
        )
        
        if not check_api_health(api_client):
            sys.exit(1)
        
        try:
            adif_content, qso_count = download_adif(api_client)
            logger.info(f"ADIF data loaded with {qso_count} QSOs")
        except WavelogAPIError as e:
            sys.exit(1)
        
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
