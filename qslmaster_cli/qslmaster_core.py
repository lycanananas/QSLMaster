import logging
import sys
import json
import plistlib
import adif_io
import fnmatch
import requests
import zipfile
import io
from typing import Optional, List, Dict, Any, Callable, Tuple, Set
from datetime import datetime
from pathlib import Path
from pyhamtools.callinfo import Callinfo
from pyhamtools.lookuplib import LookupLib

from .config import load_config, validate_config, ConfigError
from .wavelog import WavelogAPI, WavelogAPIError
from .qrz import QRZAPI, QRZAPIError
from .poland import process_qsos_poland
from .other import process_qsos_other
from .pdf_labels import generate_pdf_labels, preview_label_data, normalize_pdf_page_specs


logger = logging.getLogger(__name__)
COUNTRY_FILE_MAX_AGE_DAYS = 3


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
        self.dxcc_name_map = {269: 'Poland'}
    
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

    def get_source_type(self) -> str:
        source = str(self.config.get('source', 'wavelog')).strip().lower()
        if source in {'adif', 'file'}:
            return 'adif_file'
        return source

    @staticmethod
    def _get_country_file_paths() -> Tuple[Path, Path]:
        cache_dir = Path.home() / '.cache' / 'qslmaster'
        cache_dir.mkdir(parents=True, exist_ok=True)
        country_file = cache_dir / 'cty.plist'
        metadata_file = cache_dir / '.cty_metadata.json'
        return country_file, metadata_file

    @classmethod
    def ensure_country_file(cls, log_callback: Optional[Callable[[str, str], None]] = None) -> Path:
        def emit(level: str, message: str) -> None:
            if log_callback:
                log_callback(level, message)
            else:
                level_map = {
                    'INFO': logging.INFO,
                    'DEBUG': logging.DEBUG,
                    'WARNING': logging.WARNING,
                    'ERROR': logging.ERROR,
                }
                logger.log(level_map.get(level, logging.INFO), message)

        country_file, metadata_file = cls._get_country_file_paths()
        url = 'https://www.country-files.com/cty/download/cty_plist.zip'

        if country_file.exists():
            try:
                if metadata_file.exists():
                    with open(metadata_file, 'r') as file_handle:
                        metadata = json.load(file_handle)

                    downloaded_at_raw = metadata.get('downloaded_at')
                    if downloaded_at_raw:
                        downloaded_at = datetime.fromisoformat(str(downloaded_at_raw))
                        age = datetime.now() - downloaded_at
                        if age.days < COUNTRY_FILE_MAX_AGE_DAYS:
                            emit('INFO', f'Using cached country file (metadata age: {age.days} day(s))')
                            return country_file
                        emit('INFO', f'Cached country file metadata is older than {COUNTRY_FILE_MAX_AGE_DAYS} days, attempting refresh...')
                    else:
                        emit('INFO', 'Country file metadata missing downloaded_at, attempting refresh...')
                else:
                    emit('INFO', 'Country file metadata not found, attempting refresh...')
            except Exception:
                emit('INFO', 'Could not read country file metadata, attempting refresh...')

        emit('INFO', 'Attempting to download fresh country file (plist)...')
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                plist_files = [f for f in zf.namelist() if f.endswith('.plist')]
                if not plist_files:
                    raise Exception('No .plist file found in ZIP')
                plist_content = zf.read(plist_files[0])
                with open(country_file, 'wb') as file_handle:
                    file_handle.write(plist_content)

            metadata = {
                'downloaded_at': datetime.now().isoformat(),
                'url': url,
                'source': 'https://www.country-files.com/cty/'
            }
            with open(metadata_file, 'w') as file_handle:
                json.dump(metadata, file_handle, indent=2)

            emit('INFO', f'Successfully downloaded country file from {url}')
            return country_file
        except Exception as exc:
            emit('WARNING', f'Failed to download fresh country file: {exc}')
            emit('INFO', 'Attempting to use cached version as fallback...')

            if not country_file.exists():
                raise QSLProcessorError('Country file unavailable - download failed and no cached version found')

            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as file_handle:
                        metadata = json.load(file_handle)
                    download_time = metadata.get('downloaded_at', 'unknown')
                    emit('WARNING', f'Using cached country file from {download_time}')
                except Exception:
                    emit('WARNING', 'Using cached country file (metadata unavailable)')
            else:
                emit('WARNING', 'Using cached country file (download date unknown)')

            return country_file

    @staticmethod
    def _extract_dxcc_name_map_from_plist(data: Any) -> Dict[int, str]:
        dxcc_map: Dict[int, str] = {}

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                adif_raw = None
                name_raw = None

                for key in ('adif', 'adif_id', 'dxcc', 'dxcc_id', 'ADIF'):
                    if key in node:
                        adif_raw = node.get(key)
                        break

                for key in ('entity', 'name', 'country', 'country_name', 'prefix', 'Country'):
                    if key in node:
                        name_raw = node.get(key)
                        break

                if adif_raw is not None and name_raw:
                    try:
                        dxcc_id = int(str(adif_raw).strip())
                        name = str(name_raw).strip()
                        if dxcc_id > 0 and name and dxcc_id not in dxcc_map:
                            dxcc_map[dxcc_id] = name
                    except Exception:
                        pass

                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
        return dxcc_map

    @classmethod
    def list_all_dxcc_entities(
        cls,
        log_callback: Optional[Callable[[str, str], None]] = None,
        country_file: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        if country_file is None:
            country_file = cls.ensure_country_file(log_callback=log_callback)
        with open(country_file, 'rb') as file_handle:
            plist_data = plistlib.load(file_handle)

        dxcc_map = cls._extract_dxcc_name_map_from_plist(plist_data)
        if 269 not in dxcc_map:
            dxcc_map[269] = 'Poland'

        entities = [{'id': dxcc_id, 'name': name} for dxcc_id, name in dxcc_map.items()]
        entities.sort(key=lambda item: (item['name'].lower(), item['id']))
        return entities
    
    def setup_callinfo(self) -> None:
        self._progress("Initializing CallInfo...")

        country_file = self.ensure_country_file(log_callback=self._log)

        try:
            self.lookup_library = LookupLib(lookuptype="countryfile", filename=str(country_file))
            self.callinfo = Callinfo(self.lookup_library)
            entities = self.list_all_dxcc_entities(log_callback=self._log, country_file=country_file)
            self.dxcc_name_map = {int(item['id']): str(item['name']) for item in entities}
            self._log('INFO', f"CallInfo initialized successfully (DXCC entities loaded: {len(self.dxcc_name_map)})")
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

    @staticmethod
    def normalize_station(station: Dict[str, Any]) -> Dict[str, str]:
        station_id = str(station.get('station_id', '')).strip()
        callsign = str(station.get('station_callsign', '')).strip()
        profile = str(station.get('station_profile_name', '')).strip()
        active_raw = str(station.get('station_active', '')).strip()
        active = active_raw == '1' or active_raw.lower() == 'true'

        return {
            'station_id': station_id,
            'station_callsign': callsign,
            'station_profile_name': profile,
            'station_active': '1' if active else '0',
        }

    def list_stations(self) -> List[Dict[str, str]]:
        stations = self.api_client.get_station_info()
        return [self.normalize_station(station) for station in stations]

    def resolve_station_ids(self, stations: List[Dict[str, str]], station_selectors) -> Optional[List[str]]:
        if not station_selectors:
            raise QSLProcessorError(f"Please select at least one station or \"all\" for processing")
        if station_selectors == ['all']:
            return None

        resolved = []
        for selector in station_selectors:
            sel = selector.strip()
            if not sel or sel.lower() == 'all':
                continue
            found = None
            for station in stations:
                if station['station_id'] == sel:
                    found = station['station_id']
                    break
            if not found:
                for station in stations:
                    if station['station_callsign'].lower() == sel.lower():
                        found = station['station_id']
                        break
            if not found:
                raise QSLProcessorError(f"Station not found for selector: {selector}")
            resolved.append(found)
        return resolved if resolved else None
    
    def download_adif(self, station_ids: Optional[List[str]] = None) -> Tuple[str, int]:
        try:
            if station_ids:
                all_qso_records = []
                total_qso_count = 0
                for station_id in station_ids:
                    self._progress(f"Downloading contacts in ADIF format from station_id={station_id}...")
                    adif_content, qso_count = self.api_client.get_contacts_adif(station_id=station_id)
                    self._log('INFO', f"Successfully downloaded {qso_count} QSOs for station {station_id}")
                    if qso_count > 0:
                        all_qso_records.append(adif_content)
                        total_qso_count += qso_count
                combined_adif = '\n'.join(all_qso_records)
                return combined_adif, total_qso_count
            else:
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

    def load_adif_from_file(self, adif_file_path: str) -> str:
        path = Path(str(adif_file_path).strip())
        if not path.exists() or not path.is_file():
            raise QSLProcessorError(f"ADIF file does not exist or is not a file: {adif_file_path}")
        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            raise QSLProcessorError(f"Failed to read ADIF file {adif_file_path}: {e}")
    
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
    
    def filter_qsos_by_mode(self, qsos: List, modes: Optional[str] = None) -> List:
        if not modes:
            return qsos
        
        try:
            mode_list = [m.strip().upper() for m in modes.split(',')]
            
            digi_modes = ['RTTY', 'PSK', 'MFSK', 'OLIVIA', 'HELLSCHREIBER']
            filtered = []
            
            for qso in qsos:
                mode = qso.get('MODE', '').upper()
                submode = qso.get('SUBMODE', '').upper()
                
                matched = False
                for requested_mode in mode_list:
                    if requested_mode == 'DIGI':
                        if mode in digi_modes or any(d in submode for d in digi_modes):
                            matched = True
                            break
                    elif requested_mode == 'SSB':
                        if mode == 'SSB' or submode in ['SSB', 'USB', 'LSB']:
                            matched = True
                            break
                    else:
                        if mode == requested_mode or submode == requested_mode:
                            matched = True
                            break
                
                if matched:
                    filtered.append(qso)
            
            self._log('INFO', f"Filtered to {len(filtered)} QSOs by mode: {', '.join(mode_list)}")
            return filtered
        except Exception as e:
            raise QSLProcessorError(f"Mode filtering error: {e}")
    
    def get_dxcc_name(self, dxcc_id: int) -> str:
        try:
            return self.dxcc_name_map.get(int(dxcc_id), str(dxcc_id))
        except Exception:
            return str(dxcc_id)

    def format_qso_datetime(self, qso: Dict[str, Any]) -> str:
        qso_date_raw = str(qso.get('QSO_DATE', '') or '').strip()
        qso_time_raw = str(qso.get('TIME_ON', '') or '').strip()

        qso_date_text = qso_date_raw or 'unknown-date'
        if qso_date_raw:
            try:
                qso_date_text = datetime.strptime(qso_date_raw, '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                pass

        qso_time_text = qso_time_raw or 'unknown-time'
        if qso_time_raw:
            for time_format in ('%H%M%S', '%H%M'):
                try:
                    qso_time_text = datetime.strptime(qso_time_raw, time_format).strftime('%H:%M:%S')
                    break
                except ValueError:
                    continue

        return f'{qso_date_text} {qso_time_text}'

    def format_qso_log_label(self, qso: Dict[str, Any]) -> str:
        fullcall = str(qso.get('CALL', 'unknown') or 'unknown').strip().upper()
        return f'{fullcall} on {self.format_qso_datetime(qso)}'

    @staticmethod
    def count_qsos_by_delivery_method(qsos: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {
            'bureau': 0,
            'direct': 0,
        }

        for qso in qsos:
            delivery_method = str(qso.get('QSL_SENT_VIA', '') or '').strip().upper()
            if delivery_method == 'B':
                counts['bureau'] += 1
            elif delivery_method == 'D':
                counts['direct'] += 1

        return counts

    def get_ignored_dxcc_set(self) -> Set[int]:
        ignored_values = self.config.get('ignored_dxcc', [])
        if not ignored_values:
            return set()

        ignored_ids: Set[int] = set()
        for value in ignored_values:
            try:
                dxcc_id = int(str(value).strip())
                if dxcc_id > 0:
                    ignored_ids.add(dxcc_id)
            except Exception:
                continue
        return ignored_ids

    def filter_qsos_by_ignored_dxcc(self, qsos: List) -> Tuple[List, int, Dict[int, int]]:
        ignored_dxcc = self.get_ignored_dxcc_set()
        if not ignored_dxcc:
            return qsos, 0, {}

        filtered_qsos = []
        skipped_by_dxcc: Dict[int, int] = {}

        for qso in qsos:
            try:
                fullcall = qso.get('CALL', '')
                if not fullcall:
                    filtered_qsos.append(qso)
                    continue

                homecall = self.callinfo.get_homecall(fullcall)
                adif_id = self.callinfo.get_adif_id(homecall)
                if adif_id in ignored_dxcc:
                    skipped_by_dxcc[adif_id] = skipped_by_dxcc.get(adif_id, 0) + 1
                    dxcc_name = self.get_dxcc_name(adif_id)
                    self._log('INFO', f"Skipping QSO with {self.format_qso_log_label(qso)} - ignored DXCC: {dxcc_name} ({adif_id})")
                    continue
            except Exception:
                pass

            filtered_qsos.append(qso)

        skipped_total = len(qsos) - len(filtered_qsos)
        return filtered_qsos, skipped_total, skipped_by_dxcc

    def get_callsign_filter_mode(self) -> str:
        mode = str(self.config.get('callsign_filter_mode', 'off') or 'off').strip().lower()
        aliases = {
            'allowlist': 'allow',
            'whitelist': 'allow',
            'only': 'allow',
            'blocklist': 'block',
            'blacklist': 'block',
            'skip': 'block',
            'disabled': 'off',
            'none': 'off',
        }
        mode = aliases.get(mode, mode)
        if mode not in {'off', 'allow', 'block'}:
            mode = 'off'
        return mode

    def get_callsign_filter_patterns(self) -> List[str]:
        patterns = self.config.get('callsign_filter_patterns', [])
        if not patterns:
            return []

        normalized = []
        seen = set()
        for value in patterns:
            pattern = str(value or '').strip().upper()
            if not pattern or pattern in seen:
                continue
            normalized.append(pattern)
            seen.add(pattern)
        return normalized

    def filter_qsos_by_callsign_patterns(self, qsos: List) -> Tuple[List, int, Dict[str, int]]:
        mode = self.get_callsign_filter_mode()
        patterns = self.get_callsign_filter_patterns()
        if mode == 'off' or not patterns:
            return qsos, 0, {}

        filtered_qsos = []
        skipped_by_pattern: Dict[str, int] = {}

        for qso in qsos:
            fullcall = str(qso.get('CALL', '') or '').strip().upper()
            matched_pattern = None
            for pattern in patterns:
                if fnmatch.fnmatch(fullcall, pattern):
                    matched_pattern = pattern
                    break

            should_skip = False
            if mode == 'allow':
                should_skip = matched_pattern is None
                if should_skip:
                    skipped_by_pattern['<not-listed>'] = skipped_by_pattern.get('<not-listed>', 0) + 1
            else:
                should_skip = matched_pattern is not None
                if should_skip and matched_pattern is not None:
                    skipped_by_pattern[matched_pattern] = skipped_by_pattern.get(matched_pattern, 0) + 1

            if should_skip:
                if mode == 'allow':
                    self._log('INFO', f"Skipping QSO with {self.format_qso_log_label(qso)} - not in allowlist")
                else:
                    self._log('INFO', f"Skipping QSO with {self.format_qso_log_label(qso)} - matches block pattern \"{matched_pattern}\"")
                continue

            filtered_qsos.append(qso)

        skipped_total = len(qsos) - len(filtered_qsos)
        return filtered_qsos, skipped_total, skipped_by_pattern

    def filter_qsos_by_sent_status(self, qsos: List) -> Tuple[List, int]:
        filtered_qsos = []

        for qso in qsos:
            if str(qso.get('QSL_SENT', '') or '').strip().upper() == 'Y':
                self._log('INFO', f"Skipping QSO with {self.format_qso_log_label(qso)} - already marked as QSL sent")
                continue
            filtered_qsos.append(qso)

        skipped_total = len(qsos) - len(filtered_qsos)
        return filtered_qsos, skipped_total
    
    def process_qsos_by_dxcc(self, qsos: List, include_direct_when_no_bureau: bool = False) -> Dict[int, Any]:
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
                
                result, total = handler(items, include_direct_when_no_bureau=include_direct_when_no_bureau, log_callback=self._log, progress_callback=make_callback(progress_counter))
                if result is not None:
                    handler_results[dxcc] = (result, total)
                progress_counter += len(items)

        if other_qsos:
            self._progress("Processing Other QSOs...")
            
            def make_callback(start_offset):
                def callback(current: int, total_for_handler: int) -> None:
                    self.progress_value_callback(start_offset + current, total_qsos)
                return callback
            
            verified_other, total_other = process_qsos_other(other_qsos, self.qrz_api, include_direct_when_no_bureau=include_direct_when_no_bureau, log_callback=self._log, progress_callback=make_callback(progress_counter))
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
        modes: Optional[str] = None,
        station_selector=None,
        list_stations_only: bool = False,
        output_adif: Optional[str] = None,
        generate_pdf: Optional[str] = None,
        pdf_page_specs=None,
        debug_labels: bool = False,
        preview_pdf: bool = False,
        include_direct_when_no_bureau: bool = False,
    ) -> Dict[str, Any]:
        try:
            self._progress("Starting QSL processing...")
            source = self.get_source_type()
            stations = []
            selected_station_ids = None

            if source == 'wavelog':
                self.api_client = WavelogAPI(
                    base_url=self.config['wavelog_url'],
                    api_key=self.config['api_key']
                )

                if not self.check_api_health():
                    raise QSLProcessorError("Wavelog API health check failed")

                stations = self.list_stations()

                if list_stations_only:
                    self._log('INFO', "Station list mode enabled. Skipping QSO analysis.")
                    for station in stations:
                        status = "(active)" if station['station_active'] == '1' else "(inactive)"
                        self._log('INFO', f"  Station {station['station_id']}: {station['station_callsign']} - {station['station_profile_name']} {status}")
                    return {
                        'success': True,
                        'qsl_qsos': [],
                        'output_adif': None,
                        'output_pdf': None,
                        'stats': {'stations': len(stations), 'source': source},
                        'stations': stations,
                    }

                selected_station_ids = self.resolve_station_ids(stations, station_selector)
                if selected_station_ids:
                    self._log('INFO', f"Selected station_ids={selected_station_ids} for processing")
                else:
                    self._log('INFO', "Selected all stations for processing")
            else:
                if list_stations_only:
                    self._log('INFO', "Station list mode is only available for source=wavelog")
                    return {
                        'success': True,
                        'qsl_qsos': [],
                        'output_adif': None,
                        'output_pdf': None,
                        'stats': {'stations': 0, 'source': source},
                        'stations': [],
                    }
                self._log('INFO', f"Using ADIF file source: {self.config.get('adif_file_path', '')}")
            
            self.qrz_api = None
            if self.config.get('qrz_username') and self.config.get('qrz_password'):
                try:
                    self.qrz_api = QRZAPI(self.config['qrz_username'], self.config['qrz_password'])
                    self._log('INFO', "QRZ API initialized")
                except Exception as e:
                    self._log('WARNING', f"Failed to initialize QRZ API: {e}")
            
            self.setup_callinfo()
            if source == 'wavelog':
                self._progress("Downloading ADIF data...")
                adif_content, qso_count = self.download_adif(station_ids=selected_station_ids)
            else:
                self._progress("Loading ADIF data from file...")
                adif_content = self.load_adif_from_file(self.config.get('adif_file_path', ''))
                qso_count = 0
            self._progress("Parsing ADIF data...")
            qsos = self.parse_adif_content(adif_content)
            if source == 'adif_file':
                qso_count = len(qsos)
            self._log('INFO', f"ADIF data loaded with {qso_count} QSOs, {len(qsos)} parsed successfully")
            
            if from_date or to_date:
                self._progress("Filtering QSOs by date...")
                qsos = self.filter_qsos_by_date_range(qsos, from_date, to_date)
                self._progress(f"Filtered to {len(qsos)} QSOs")
            
            if modes:
                self._progress("Filtering QSOs by mode...")
                qsos = self.filter_qsos_by_mode(qsos, modes)
                self._progress(f"Filtered to {len(qsos)} QSOs")
            
            self.print_qso_summary(qsos)
            
            qsos_to_process = qsos
            callsign_filter_mode = self.get_callsign_filter_mode()
            callsign_filter_patterns = self.get_callsign_filter_patterns()
            callsign_filter_skipped_count = 0

            if callsign_filter_mode != 'off' and callsign_filter_patterns:
                qsos_to_process, callsign_filter_skipped_count, callsign_filter_breakdown = self.filter_qsos_by_callsign_patterns(qsos_to_process)
                if callsign_filter_skipped_count > 0:
                    breakdown_values = [
                        f'"{pattern}"={count}'
                        for pattern, count in callsign_filter_breakdown.items()
                    ]
                    mode_label = 'allowlist' if callsign_filter_mode == 'allow' else 'blocklist'
                    self._log('INFO', f"Skipping {callsign_filter_skipped_count} QSO(s) by callsign {mode_label}: {', '.join(breakdown_values)}")
                else:
                    self._log('INFO', f"Callsign filter active, no matching QSO changes for mode={callsign_filter_mode}")

            ignored_ids = sorted(self.get_ignored_dxcc_set())
            ignored_skipped_count = 0
            if ignored_ids:
                qsos_to_process, ignored_skipped_count, ignored_breakdown = self.filter_qsos_by_ignored_dxcc(qsos_to_process)
                if ignored_skipped_count > 0:
                    breakdown_values = [
                        f"{self.get_dxcc_name(dxcc_id)}({dxcc_id})={count}"
                        for dxcc_id, count in sorted(ignored_breakdown.items(), key=lambda item: item[0])
                    ]
                    self._log('INFO', f"Skipping {ignored_skipped_count} QSO(s) by ignored DXCC: {', '.join(breakdown_values)}")
                else:
                    self._log('INFO', f"Ignored DXCC active, no matching QSOs found: {ignored_ids}")

            sent_skipped_count = 0
            qsos_to_process, sent_skipped_count = self.filter_qsos_by_sent_status(qsos_to_process)
            if sent_skipped_count > 0:
                self._log('INFO', f"Skipping {sent_skipped_count} QSO(s) already marked as sent")
            
            self._progress("Processing QSOs by DXCC...")
            handler_results = self.process_qsos_by_dxcc(qsos_to_process, include_direct_when_no_bureau=include_direct_when_no_bureau)
            
            all_qsl_qsos = []
            stats = {}
            
            for key, result in handler_results.items():
                if result:
                    qsos_list, total_count = result
                    if qsos_list:
                        delivery_stats = self.count_qsos_by_delivery_method(qsos_list)
                        if key == 'other':
                            self._log('INFO', f"Other: {len(qsos_list)} out of {total_count} QSOs to send (bureau={delivery_stats['bureau']}, direct={delivery_stats['direct']})")
                            stats['other'] = {'to_send': len(qsos_list), 'total': total_count, 'bureau': delivery_stats['bureau'], 'direct': delivery_stats['direct']}
                        else:
                            dxcc_name = self.get_dxcc_name(key)
                            self._log('INFO', f"{dxcc_name}: {len(qsos_list)} out of {total_count} QSOs to send (bureau={delivery_stats['bureau']}, direct={delivery_stats['direct']})")
                            stats[dxcc_name] = {'to_send': len(qsos_list), 'total': total_count, 'bureau': delivery_stats['bureau'], 'direct': delivery_stats['direct']}
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
                    normalized_pdf_page_specs = normalize_pdf_page_specs(pdf_page_specs)
                    if preview_pdf:
                        preview_label_data(all_qsl_qsos, limit=3)
                    
                    self._progress(f"Generating PDF labels to {generate_pdf}...")
                    logo_path = self.config.get('logo_path', 'logo.png')
                    generate_pdf_labels(all_qsl_qsos, generate_pdf, debug_labels, logo_path, normalized_pdf_page_specs)
                    output_pdf_path = generate_pdf
                    self._progress(f"PDF labels generated: {generate_pdf}")
                    self._log('INFO', f"PDF labels generated: {generate_pdf}")
                except Exception as e:
                    self._log('ERROR', f"Failed to generate PDF labels: {e}")
                    raise
            
            delivery_method_stats = self.count_qsos_by_delivery_method(all_qsl_qsos)
            self._log('INFO', f"Delivery methods: bureau: {delivery_method_stats['bureau']}, direct: {delivery_method_stats['direct']}")

            stats['total_to_send'] = len(all_qsl_qsos)
            stats['delivery_methods'] = {
                'bureau': delivery_method_stats['bureau'],
                'direct': delivery_method_stats['direct'],
                'include_direct_when_no_bureau': bool(include_direct_when_no_bureau),
            }
            if callsign_filter_mode != 'off' and callsign_filter_patterns:
                stats['callsign_filter'] = {
                    'mode': callsign_filter_mode,
                    'patterns': callsign_filter_patterns,
                    'skipped': callsign_filter_skipped_count,
                }
            if ignored_ids:
                stats['ignored_dxcc'] = {
                    'ids': ignored_ids,
                    'skipped': ignored_skipped_count,
                }
            if sent_skipped_count > 0:
                stats['already_sent'] = {
                    'skipped': sent_skipped_count,
                }
            self.progress_value_callback(len(qsos), len(qsos))
            
            return {
                'success': True,
                'qsl_qsos': all_qsl_qsos,
                'output_adif': output_adif_path,
                'output_pdf': output_pdf_path,
                'stats': stats,
                'stations': stations,
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
                'stations': [],
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
                'stations': [],
            }
