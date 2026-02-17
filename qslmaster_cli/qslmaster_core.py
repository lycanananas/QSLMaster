import logging
import sys
import json
import adif_io
import requests
import zipfile
import io
from typing import Optional, List, Dict, Any, Callable, Tuple
from datetime import datetime
from pathlib import Path
from pyhamtools.callinfo import Callinfo
from pyhamtools.lookuplib import LookupLib

from .config import load_config, validate_config, ConfigError
from .wavelog import WavelogAPI, WavelogAPIError
from .qrz import QRZAPI, QRZAPIError
from .poland import process_qsos_poland
from .other import process_qsos_other
from .pdf_labels import generate_pdf_labels, preview_label_data


logger = logging.getLogger(__name__)


class QSLProcessorError(Exception):
    pass


class QSLProcessor:
    def __init__(
        self,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_value_callback: Optional[Callable[[int, int], None]] = None,
    ):
        self.config = config
        self.progress_callback = progress_callback or self._default_callback
        self.log_callback = log_callback or self._default_log_callback
        self.progress_value_callback = progress_value_callback or self._default_progress_value_callback
        
        self.api_client = None
        self.qrz_api = None
        self.callinfo = None
        self.lookup_library = None
    
    def _default_callback(self, message: str) -> None:
        logger.info(message)
    
    def _default_log_callback(self, level: str, message: str) -> None:
        level_map = {
            'INFO': logging.INFO,
            'DEBUG': logging.DEBUG,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
        }
        logger.log(level_map.get(level, logging.INFO), message)
    
    def _default_progress_value_callback(self, current: int, total: int) -> None:
        pass
    
    def _progress(self, message: str, current: Optional[int] = None, total: Optional[int] = None) -> None:
        self.progress_callback(message)
        if current is not None and total is not None:
            self.progress_value_callback(current, total)
    
    def _log(self, level: str, message: str) -> None:
        self.log_callback(level, message)
    
    def setup_callinfo(self) -> None:
        self._progress("Initializing CallInfo...")
        
        cache_dir = Path.home() / '.cache' / 'qslmaster'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        country_file = cache_dir / 'cty.plist'
        metadata_file = cache_dir / '.cty_metadata.json'
        
        url = 'https://www.country-files.com/cty/download/cty_plist.zip'
        download_success = False
        
        self._log('INFO', "Attempting to download fresh country file (plist)...")
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
                
                self._log('INFO', f"Successfully downloaded country file from {url}")
                download_success = True
                
        except Exception as e:
            self._log('WARNING', f"Failed to download fresh country file: {e}")
            self._log('INFO', "Attempting to use cached version as fallback...")
            
            if not country_file.exists():
                raise QSLProcessorError("Country file unavailable - download failed and no cached version found")
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        download_time = metadata.get('downloaded_at', 'unknown')
                        self._log('WARNING', f"Using cached country file from {download_time}")
                except:
                    self._log('WARNING', "Using cached country file (metadata unavailable)")
            else:
                self._log('WARNING', "Using cached country file (download date unknown)")
        
        try:
            self.lookup_library = LookupLib(lookuptype="countryfile", filename=str(country_file))
            self.callinfo = Callinfo(self.lookup_library)
            status = "fresh" if download_success else "cached"
            self._log('INFO', f"CallInfo initialized successfully (using {status} country file)")
        except Exception as e:
            raise QSLProcessorError(f"Failed to initialize CallInfo: {e}")
    
    def check_api_health(self) -> bool:
        try:
            self._progress("Checking Wavelog API availability...")
            version_data = self.api_client.get_version()
            self._log('INFO', "Wavelog API is available!")
            
            self._log('INFO', f"Wavelog Version: {version_data.get('version', 'N/A')}")
            
            stations = self.api_client.get_station_info()
            self._log('INFO', f"Found {len(stations)} station(s):")
            for station in stations:
                station_id = station.get('station_id')
                callsign = station.get('station_callsign')
                profile = station.get('station_profile_name')
                active = station.get('station_active')
                status = "(active)" if active == "1" else "(inactive)"
                self._log('INFO', f"  Station {station_id}: {callsign} - {profile} {status}")
            
            return True
        except WavelogAPIError as e:
            self._log('ERROR', f"API error: {e}")
            return False
    
    def download_adif(self) -> Tuple[str, int]:
        try:
            self._progress("Downloading contacts in ADIF format from all stations...")
            adif_content, qso_count = self.api_client.get_contacts_adif()
            self._log('INFO', f"Successfully downloaded {qso_count} QSOs")
            return adif_content, qso_count
        except WavelogAPIError as e:
            raise QSLProcessorError(f"API error while downloading ADIF: {e}")
    
    def parse_adif_content(self, adif_content: str) -> List:
        try:
            qsos, headers = adif_io.read_from_string(adif_content)
            self._log('INFO', f"Parsed {len(qsos)} QSO records from ADIF")
            return qsos
        except Exception as e:
            raise QSLProcessorError(f"ADIF parsing error: {e}")
    
    @staticmethod
    def parse_date_arg(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD, got: {date_str}")
    
    def filter_qsos_by_date_range(
        self,
        qsos: List,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List:
        try:
            from_datetime = self.parse_date_arg(from_date) if from_date else None
            to_datetime = self.parse_date_arg(to_date) if to_date else None
            
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
                self._log('INFO', f"Filtered to {len(filtered)} QSOs{range_str}")
            
            return filtered
        except ValueError as e:
            raise QSLProcessorError(f"Date parsing error: {e}")
    
    @staticmethod
    def get_dxcc_name(dxcc_id: int) -> str:
        dxcc_names = {
            269: "Poland",
        }
        try:
            return dxcc_names.get(int(dxcc_id), str(dxcc_id))
        except Exception:
            return str(dxcc_id)
    
    def process_qsos_by_dxcc(self, qsos: List) -> Dict[int, Any]:
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

                homecall = self.callinfo.get_homecall(fullcall)
                adif_id = self.callinfo.get_adif_id(homecall)

                if adif_id in buckets:
                    buckets[adif_id].append(qso)
                else:
                    other_qsos.append(qso)
            except Exception as e:
                self._log('WARNING', f"Could not determine DXCC for {qso.get('CALL', 'unknown')}: {e}")
                other_qsos.append(qso)

        counts = [f"{self.get_dxcc_name(dxcc)}={len(items)}" for dxcc, items in buckets.items()]
        counts.append(f"Other={len(other_qsos)}")
        self._log('INFO', f"QSOs by DXCC: {', '.join(counts)}")
        
        total_qsos = len(qsos)
        progress_counter = 0

        for dxcc, handler in dxcc_handlers.items():
            items = buckets.get(dxcc, [])
            if items:
                self._progress(f"Processing {self.get_dxcc_name(dxcc)} QSOs...")
                
                def make_callback(start_offset):
                    def callback(current: int, total_for_handler: int) -> None:
                        self.progress_value_callback(start_offset + current, total_qsos)
                    return callback
                
                result, total = handler(items, log_callback=self._log, progress_callback=make_callback(progress_counter))
                if result is not None:
                    handler_results[dxcc] = (result, total)
                progress_counter += len(items)

        if other_qsos:
            self._progress("Processing Other QSOs...")
            
            def make_callback(start_offset):
                def callback(current: int, total_for_handler: int) -> None:
                    self.progress_value_callback(start_offset + current, total_qsos)
                return callback
            
            verified_other, total_other = process_qsos_other(other_qsos, self.qrz_api, log_callback=self._log, progress_callback=make_callback(progress_counter))
            if verified_other:
                handler_results['Other'] = (verified_other, total_other)

        return handler_results
    
    def print_qso_summary(self, qsos: List) -> None:
        if not qsos:
            self._log('INFO', "QSO Summary: No QSOs")
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
        
        self._log('INFO', "QSO Data Summary:")
        self._log('INFO', f"  Total QSOs: {len(qsos)}")
        
        if valid_dates:
            self._log('INFO', f"  Date range: {min(valid_dates).strftime('%Y-%m-%d %H:%M:%S')} to {max(valid_dates).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if countries:
            self._log('INFO', f"  Countries/DXCC: {len(countries)}")
    
    def process(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        output_adif: Optional[str] = None,
        generate_pdf: Optional[str] = None,
        debug_labels: bool = False,
        preview_pdf: bool = False,
    ) -> Dict[str, Any]:
        try:
            self._progress("Starting QSL processing...")
            self.api_client = WavelogAPI(
                base_url=self.config['wavelog_url'],
                api_key=self.config['api_key']
            )
            
            if not self.check_api_health():
                raise QSLProcessorError("Wavelog API health check failed")
            
            self.qrz_api = None
            if self.config.get('qrz_username') and self.config.get('qrz_password'):
                try:
                    self.qrz_api = QRZAPI(self.config['qrz_username'], self.config['qrz_password'])
                    self._log('INFO', "QRZ API initialized")
                except Exception as e:
                    self._log('WARNING', f"Failed to initialize QRZ API: {e}")
            
            self.setup_callinfo()
            
            self._progress("Downloading ADIF data...")
            adif_content, qso_count = self.download_adif()
            self._progress("Parsing ADIF data...")
            qsos = self.parse_adif_content(adif_content)
            self._log('INFO', f"ADIF data loaded with {qso_count} QSOs, {len(qsos)} parsed successfully")
            
            if from_date or to_date:
                self._progress("Filtering QSOs by date...")
                qsos = self.filter_qsos_by_date_range(qsos, from_date, to_date)
                self._progress(f"Filtered to {len(qsos)} QSOs")
            
            self.print_qso_summary(qsos)
            
            qsos_to_process = [qso for qso in qsos if qso.get('QSL_SENT', '').strip().upper() != 'Y']
            skipped_count = len(qsos) - len(qsos_to_process)
            if skipped_count > 0:
                self._log('INFO', f"Skipping {skipped_count} QSO(s) that already have QSL_SENT marked")
            
            self._progress("Processing QSOs by DXCC...")
            handler_results = self.process_qsos_by_dxcc(qsos_to_process)
            
            all_qsl_qsos = []
            stats = {}
            
            for key, result in handler_results.items():
                if result:
                    qsos_list, total_count = result
                    if qsos_list:
                        if key == 'other':
                            self._log('INFO', f"Other: {len(qsos_list)} out of {total_count} QSOs to send")
                            stats['other'] = {'to_send': len(qsos_list), 'total': total_count}
                        else:
                            dxcc_name = self.get_dxcc_name(key)
                            self._log('INFO', f"{dxcc_name}: {len(qsos_list)} out of {total_count} QSOs to send")
                            stats[dxcc_name] = {'to_send': len(qsos_list), 'total': total_count}
                        all_qsl_qsos.extend(qsos_list)
            
            output_adif_path = output_adif or 'qsl_output.adif'
            self._progress(f"Writing ADIF to {output_adif_path}...")
            
            with open(output_adif_path, 'w', encoding='UTF-8') as f:
                f.write("ADI file generated by QSLMaster\n")
                f.write(" <ADIF_VER:5>3.1.6")
                f.write(f" <PROGRAMID:9>QSLMaster")
                f.write(" <EOH>\n")
                for qso in all_qsl_qsos:
                    f.write(adif_io.qso_to_adif(qso))
            
            self._log('INFO', f"Total {len(all_qsl_qsos)} QSOs to send saved to: {output_adif_path}")
            
            output_pdf_path = None
            if generate_pdf:
                try:
                    if preview_pdf:
                        preview_label_data(all_qsl_qsos, limit=3, log_callback=self._log)
                    
                    self._progress(f"Generating PDF labels to {generate_pdf}...")
                    logo_path = self.config.get('logo_path', 'logo.png')
                    generate_pdf_labels(all_qsl_qsos, generate_pdf, debug_labels, logo_path, log_callback=self._log)
                    output_pdf_path = generate_pdf
                    self._progress(f"PDF labels generated: {generate_pdf}")
                    self._log('INFO', f"PDF labels generated: {generate_pdf}")
                except Exception as e:
                    self._log('ERROR', f"Failed to generate PDF labels: {e}")
                    raise
            
            stats['total_to_send'] = len(all_qsl_qsos)
            self.progress_value_callback(len(qsos), len(qsos))
            
            return {
                'success': True,
                'qsl_qsos': all_qsl_qsos,
                'output_adif': output_adif_path,
                'output_pdf': output_pdf_path,
                'stats': stats,
            }
            
        except (ConfigError, QSLProcessorError, WavelogAPIError, ValueError) as e:
            self._log('ERROR', f"Processing error: {e}")
            return {
                'success': False,
                'error': str(e),
                'qsl_qsos': [],
                'output_adif': None,
                'output_pdf': None,
                'stats': {},
            }
        except Exception as e:
            self._log('ERROR', f"Unexpected error: {e}")
            import traceback
            self._log('DEBUG', traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'qsl_qsos': [],
                'output_adif': None,
                'output_pdf': None,
                'stats': {},
            }
