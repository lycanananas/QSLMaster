import argparse
import sys
import json
import logging
import adif_io
import requests
import urllib.parse
import zipfile
import io
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from pyhamtools.callinfo import Callinfo
from pyhamtools.lookuplib import LookupLib
from pathlib import Path
from config import load_config, validate_config, ConfigError
from wavelog import WavelogAPI, WavelogAPIError
from qrz import QRZAPI, QRZAPIError
from poland import process_qsos_poland
from other import process_qsos_other
from pdf_labels import generate_pdf_labels, preview_label_data


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

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if root_logger.handlers:
        for existing in root_logger.handlers:
            existing.setLevel(level)
            existing.setFormatter(formatter)
    else:
        root_logger.addHandler(handler)

    logger.setLevel(level)


def setup_callinfo() -> Tuple[Callinfo, LookupLib]:
    cache_dir = Path.home() / '.cache' / 'qslmaster'
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    country_file = cache_dir / 'cty.plist'
    metadata_file = cache_dir / '.cty_metadata.json'
    
    url = 'https://www.country-files.com/cty/download/cty_plist.zip'
    download_success = False
    
    logger.info("Attempting to download fresh country file (plist)...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            plist_files = [f for f in zf.namelist() if f.endswith('.plist')]
            if not plist_files:
                raise Exception("No .plist file found in ZIP")
            
            plist_content = zf.read(plist_files[0])
            with open(country_file, 'wb') as f:
                f.write(plist_content)
            
            metadata = {
                'downloaded_at': datetime.now().isoformat(),
                'url': url,
                'source': 'https://www.country-files.com/cty/'
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Successfully downloaded and saved country file from {url}")
            download_success = True
            
    except Exception as e:
        logger.warning(f"Failed to download fresh country file: {e}")
        logger.info("Attempting to use cached version as fallback...")
        
        if not country_file.exists():
            logger.error("Country file not available - download failed and no cached version found")
            raise Exception("Cannot initialize CallInfo: country file unavailable and download failed")
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    download_time = metadata.get('downloaded_at', 'unknown')
                    logger.warning(f"Using cached country file from {download_time}")
            except Exception:
                logger.warning("Using cached country file (metadata unavailable)")
        else:
            logger.warning("Using cached country file (download date unknown)")
    
    try:
        lookup_library = LookupLib(lookuptype="countryfile", filename=str(country_file))
        callinfo = Callinfo(lookup_library)
        status = "fresh" if download_success else "cached"
        logger.info(f"CallInfo initialized successfully (using {status} country file)")
        return callinfo, lookup_library
    except Exception as e:
        logger.error(f"Failed to initialize CallInfo: {e}")
        raise


def log_version_info(version_data: dict) -> None:
    logger.info("Wavelog API Information")
    logger.info(f"Wavelog Version: {version_data.get('version', 'N/A')}")


def log_stations_info(api_client: WavelogAPI) -> None:
    stations = api_client.get_station_info()
    logger.info(f"Found {len(stations)} station(s):")
    for station in stations:
        station_id = station.get('station_id')
        callsign = station.get('station_callsign')
        profile = station.get('station_profile_name')
        active = station.get('station_active')
        status = "(active)" if active == "1" else "(inactive)"
        logger.info(f"  Station {station_id}: {callsign} - {profile} {status}")


def check_api_health(api_client: WavelogAPI) -> bool:
    try:
        logger.info("Checking Wavelog API availability...")
        version_data = api_client.get_version()
        logger.info("Wavelog API is available!")
        log_version_info(version_data)
        log_stations_info(api_client)
        return True
    except WavelogAPIError as e:
        logger.error(f"API error: {e}")
        return False


def download_adif(api_client: WavelogAPI) -> Tuple[str, int]:
    try:
        logger.info("Downloading contacts in ADIF format from all stations...")
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


def get_dxcc_name(dxcc_id: int) -> str:
    dxcc_names = {
        269: "Poland",
    }
    try:
        return dxcc_names.get(int(dxcc_id), str(dxcc_id))
    except Exception:
        return str(dxcc_id)


def process_qsos_by_dxcc(qsos: List, callinfo: Callinfo, qrz_api: Optional[QRZAPI] = None) -> Dict[int, Any]:
    dxcc_handlers = {
        269: process_qsos_poland,
    }

    buckets = {dxcc: [] for dxcc in dxcc_handlers}
    other_qsos = []
    handler_results = {}

    for qso in qsos:
        try:
            fullcall = qso.get('CALL', '')
            if not fullcall:
                continue

            homecall = callinfo.get_homecall(fullcall)
            adif_id = callinfo.get_adif_id(homecall)

            if adif_id in buckets:
                buckets[adif_id].append(qso)
            else:
                other_qsos.append(qso)
        except Exception as e:
            logger.warning(f"Could not determine DXCC for {qso.get('CALL', 'unknown')}: {e}")
            other_qsos.append(qso)

    counts = [f"{get_dxcc_name(dxcc)}={len(items)}" for dxcc, items in buckets.items()]
    counts.append(f"Other={len(other_qsos)}")
    logger.info(f"QSOs by DXCC: {', '.join(counts)}")

    for dxcc, handler in dxcc_handlers.items():
        items = buckets.get(dxcc, [])
        if items:
            result = handler(items)
            if result is not None:
                handler_results[dxcc] = (result, len(items))

    if other_qsos:
        verified_other, total_other = process_qsos_other(other_qsos, qrz_api)
        if verified_other:
            handler_results['other'] = (verified_other, total_other)

    return handler_results


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

    parser.add_argument(
        '-o', '--output-adif',
        type=str,
        required=True,
        help='Path to output ADIF file for QSOs to send'
    )
    
    parser.add_argument(
        '--generate-pdf',
        type=str,
        default=None,
        help='Generate PDF labels and save to specified file (e.g., labels.pdf)'
    )
    
    parser.add_argument(
        '--debug-labels',
        action='store_true',
        help='Draw borders around labels in PDF for debugging alignment'
    )
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    try:
        logger.info(f"Loading configuration from: {args.config}")
        config = load_config(args.config)
        
        validate_config(config)
        logger.info("Configuration loaded and validated")
        
        if args.verbose:
            logger.debug(f"Wavelog URL: {config['wavelog_url']}")
        
        api_client = WavelogAPI(
            base_url=config['wavelog_url'],
            api_key=config['api_key']
        )
        
        if not check_api_health(api_client):
            sys.exit(1)
        
        qrz_api = None
        if config.get('qrz_username') and config.get('qrz_password'):
            try:
                qrz_api = QRZAPI(config['qrz_username'], config['qrz_password'])
                logger.info("QRZ API initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize QRZ API: {e}")
        
        try:
            callinfo, lookup_library = setup_callinfo()
            
            adif_content, qso_count = download_adif(api_client)
            qsos = parse_adif_content(adif_content)
            
            logger.info(f"ADIF data loaded with {qso_count} QSOs, {len(qsos)} parsed successfully")
            
            if args.from_date or args.to_date:
                qsos = filter_qsos_by_date_range(qsos, args.from_date, args.to_date)
            
            print_qso_summary(qsos, "QSO Data Summary")
            
            handler_results = process_qsos_by_dxcc(qsos, callinfo, qrz_api)
            
            all_qsl_qsos = []
            for key, result in handler_results.items():
                if result:
                    qsos_list, total_count = result
                    if qsos_list:
                        if key == 'other':
                            logger.info(f"Other: {len(qsos_list)} out of {total_count} QSOs to send")
                        else:
                            logger.info(f"{get_dxcc_name(key)}: {len(qsos_list)} out of {total_count} QSOs to send")
                        all_qsl_qsos.extend(qsos_list)
            
            with open(args.output_adif, 'w', encoding='UTF-8') as f:
                f.write("ADI file generated by QSLMaster\n")
                f.write(" <ADIF_VER:5>3.1.6")
                f.write(f" <PROGRAMID:9>QSLMaster")
                f.write(" <EOH>\n")
                for qso in all_qsl_qsos:
                    f.write(adif_io.qso_to_adif(qso))
            logger.info(f"Total {len(all_qsl_qsos)} QSOs to send saved to: {args.output_adif}")
            
            if args.generate_pdf:
                try:
                    if args.verbose:
                        preview_label_data(all_qsl_qsos, limit=3)
                    generate_pdf_labels(all_qsl_qsos, args.generate_pdf, args.debug_labels)
                except Exception as e:
                    logger.error(f"Failed to generate PDF labels: {e}")
                    if args.verbose:
                        import traceback
                        logger.debug(traceback.format_exc())
            
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
