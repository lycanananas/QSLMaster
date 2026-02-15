import argparse
import sys
import json
import logging
from typing import Optional, List, Tuple
from datetime import datetime

from config import load_config, validate_config, ConfigError
from api import WavelogAPI, WavelogAPIError
import adif_io


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


def parse_adif_content(adif_content: str) -> List:
    try:
        qsos, headers = adif_io.read_from_string(adif_content)
        logger.info(f"Parsed {len(qsos)} QSO records from ADIF")
        return qsos
    except Exception as e:
        logger.error(f"ADIF parsing error: {e}")
        raise


def parse_date_arg(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Invalid date format. Use YYYY-MM-DD, got: {date_str}")


def filter_qsos_by_date_range(
    qsos: List,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> List:
    try:
        from_datetime = parse_date_arg(from_date) if from_date else None
        to_datetime = parse_date_arg(to_date) if to_date else None
        
        filtered = []
        
        for qso in qsos:
            qso_date = qso.get('QSO_DATE', '')
            time_on = qso.get('TIME_ON', '000000')
            
            if not qso_date:
                continue
            
            try:
                datetime_str = f"{qso_date}{time_on}"
                qso_datetime = datetime.strptime(datetime_str, '%Y%m%d%H%M%S')
            except ValueError:
                continue
            
            if from_datetime and qso_datetime < from_datetime:
                continue
            
            if to_datetime:
                to_date_eod = to_datetime.replace(hour=23, minute=59, second=59)
                if qso_datetime > to_date_eod:
                    continue
            
            filtered.append(qso)
        
        if from_date or to_date:
            range_str = f" between {from_date}" if from_date else ""
            if to_date:
                range_str += f" and {to_date}" if range_str else f" until {to_date}"
            logger.info(f"Filtered to {len(filtered)} QSOs{range_str}")
        
        return filtered
    except ValueError as e:
        logger.error(f"Date parsing error: {e}")
        raise


def print_qso_summary(qsos: List, title: str = "QSO Summary") -> None:
    if not qsos:
        logger.info(f"{title}: No QSOs")
        return
    
    countries = set()
    valid_dates = []
    
    for qso in qsos:
        dxcc = qso.get('DXCC')
        if dxcc:
            countries.add(dxcc)
        
        qso_date = qso.get('QSO_DATE')
        time_on = qso.get('TIME_ON', '000000')
        if qso_date:
            try:
                datetime_str = f"{qso_date}{time_on}"
                qso_datetime = datetime.strptime(datetime_str, '%Y%m%d%H%M%S')
                valid_dates.append(qso_datetime)
            except ValueError:
                pass
    
    logger.info(f"{title}:")
    logger.info(f"  Total QSOs: {len(qsos)}")
    
    if valid_dates:
        logger.info(f"  Date range: {min(valid_dates).strftime('%Y-%m-%d %H:%M:%S')} to {max(valid_dates).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if countries:
        logger.info(f"  Countries/DXCC: {len(countries)}")



def main():
    parser = argparse.ArgumentParser(
        description='QSLMaster - Download QSO from Wavelog for QSL card label preparation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s --config config.json
  %(prog)s -c /path/to/config.json --from-date 2024-01-01 --to-date 2024-12-31
  %(prog)s -c config.json --from-date 2024-06-01
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '--from-date',
        type=str,
        default=None,
        help='Filter QSOs from date (format: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--to-date',
        type=str,
        default=None,
        help='Filter QSOs to date (format: YYYY-MM-DD)'
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
            qsos = parse_adif_content(adif_content)
            
            logger.info(f"ADIF data loaded with {qso_count} QSOs, {len(qsos)} parsed successfully")
            
            if args.from_date or args.to_date:
                qsos = filter_qsos_by_date_range(qsos, args.from_date, args.to_date)
            
            print_qso_summary(qsos, "QSO Data Summary")
            
            logger.info(f"Ready to process {len(qsos)} QSOs")
            
        except (WavelogAPIError, ValueError) as e:
            logger.error(f"Error processing ADIF data: {e}")
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
