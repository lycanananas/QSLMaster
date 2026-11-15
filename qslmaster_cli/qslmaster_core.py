import logging
import traceback
from datetime import date
from typing import Optional, List, Dict, Any, Callable, Tuple

from .config import ConfigError, normalize_callsign_filter_mode
from .wavelog import create_wavelog_api, WavelogAPIError, WavelogAuthError
from .qrz import QRZAPI
from .country_file import CountryFileLookup, CountryFileError, ensure_country_file, POLAND_DXCC_ID
from .adif_files import ADIFFileError, parse_adif_content, load_adif_file, load_qslmaster_output_file, write_adif_file
from .qso_filters import (
    filter_qsos_by_date_range, filter_qsos_by_mode, parse_mode_list,
    normalize_ignored_dxcc, filter_qsos_by_ignored_dxcc,
    normalize_callsign_filter_patterns, filter_qsos_by_callsign_patterns,
    filter_qsos_by_sent_status, count_skipped, parse_date_arg,
)
from .qso_utils import format_qso_log_label, get_qso_homecall, count_qsos_by_delivery_method
from .label_sorting import sort_qsos_for_labels
from .mark_sent import MarkSentPlan, MarkSentResult, plan_mark_as_sent, apply_mark_as_sent, ensure_mark_as_sent_supported
from .poland import process_qsos_poland
from .other import process_qsos_other
from .pdf_labels import generate_pdf_labels, preview_label_data, normalize_pdf_page_specs


logger = logging.getLogger(__name__)


class QSLProcessorError(Exception):
    pass


def _failure_result(error: Exception) -> Dict[str, Any]:
    return {
        'success': False,
        'error': str(error),
        'permission_error': isinstance(error, WavelogAuthError),
        'qsl_qsos': [],
        'output_adif': None,
        'output_pdf': None,
        'stats': {},
        'stations': [],
    }


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
        self.country_lookup = None
        self.dxcc_name_map = {POLAND_DXCC_ID: 'Poland'}

    def _default_callback(self, message: str) -> None:
        logger.info(message)

    def _default_log_callback(self, level: str, message: str) -> None:
        getattr(logger, level.lower(), logger.info)(message)

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

    def setup_country_lookup(self) -> None:
        self._progress("Loading country file...")
        try:
            country_file = ensure_country_file(log_callback=self._log)
            self.country_lookup = CountryFileLookup(country_file)
        except (CountryFileError, OSError, ValueError) as e:
            raise QSLProcessorError(f"Failed to load country file: {e}")
        self.dxcc_name_map = dict(self.country_lookup.dxcc_names)
        self._log('INFO', f"Country file loaded (DXCC entities: {len(self.dxcc_name_map)})")

    def get_dxcc_name(self, dxcc_id: int) -> str:
        try:
            return self.dxcc_name_map.get(int(dxcc_id), str(dxcc_id))
        except Exception:
            return str(dxcc_id)

    def resolve_adif_id(self, homecall: str) -> int:
        if self.country_lookup is None:
            raise QSLProcessorError("Country file is not loaded")
        return self.country_lookup.get_adif_id(homecall)

    def resolve_country_name(self, homecall: str) -> str:
        adif_id = self.resolve_adif_id(homecall)
        return self.get_dxcc_name(adif_id) if adif_id else ''

    def connect_wavelog(self) -> List[Dict[str, str]]:
        self._progress("Checking Wavelog API availability...")
        try:
            self.api_client = create_wavelog_api(
                base_url=self.config['wavelog_url'],
                api_key=self.config['api_key']
            )
            return self.check_api_health()
        except WavelogAuthError:
            raise
        except WavelogAPIError as e:
            raise QSLProcessorError(f"Wavelog API health check failed: {e}")

    def check_api_health(self) -> List[Dict[str, str]]:
        version_data = self.api_client.get_version()
        self._log('INFO', "Wavelog API is available!")
        self._log('INFO', f"Wavelog Version: {version_data.get('version', 'N/A')}")
        if version_data.get('owner'):
            self._log('INFO', f"Wavelog API v2 token owner: {version_data.get('owner')}, scopes: {', '.join(version_data.get('scopes', []))}, expires: {version_data.get('expires_at') or 'never'}")

        stations = self.list_stations()
        self._log('INFO', f"Found {len(stations)} station(s):")
        for station in stations:
            status = "(active)" if station['station_active'] == '1' else "(inactive)"
            self._log('INFO', f"  Station {station['station_id']}: {station['station_callsign']} - {station['station_profile_name']} {status}")
        return stations

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

    def download_adif(self, station_ids: Optional[List[str]] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Tuple[str, int]:
        station_text = f"station_id={','.join(station_ids)}" if station_ids else "all stations"
        qso_since, qso_until = (from_date, to_date) if self.api_client.supports_date_filter else (None, None)
        if qso_since or qso_until:
            self._log('INFO', f"Requesting QSOs from Wavelog between {qso_since or 'start'} and {qso_until or 'today'} (server-side filter)")
        try:
            self._progress(f"Downloading contacts in ADIF format from {station_text}...")
            adif_content, qso_count = self.api_client.get_contacts_adif(station_ids=station_ids, qso_since=qso_since, qso_until=qso_until)
        except WavelogAuthError:
            raise
        except WavelogAPIError as e:
            raise QSLProcessorError(f"API error while downloading ADIF: {e}")
        self._log('INFO', f"Successfully downloaded {qso_count} QSOs from {station_text}")
        return adif_content, qso_count

    def apply_filters(self, qsos: List, from_date: Optional[str], to_date: Optional[str], modes: Optional[str]) -> Tuple[List, Dict[str, Any]]:
        stats: Dict[str, Any] = {}

        if from_date or to_date:
            self._progress("Filtering QSOs by date...")
            qsos = filter_qsos_by_date_range(qsos, from_date, to_date)
            range_text = f" between {from_date}" if from_date else ""
            if to_date:
                range_text += f" and {to_date}" if range_text else f" until {to_date}"
            self._log('INFO', f"Filtered to {len(qsos)} QSOs{range_text}")

        if modes:
            self._progress("Filtering QSOs by mode...")
            qsos = filter_qsos_by_mode(qsos, modes)
            self._log('INFO', f"Filtered to {len(qsos)} QSOs by mode: {', '.join(parse_mode_list(modes))}")

        self.print_qso_summary(qsos)

        callsign_filter_mode = normalize_callsign_filter_mode(self.config.get('callsign_filter_mode'))
        callsign_filter_patterns = normalize_callsign_filter_patterns(self.config.get('callsign_filter_patterns'))
        if callsign_filter_mode != 'off' and callsign_filter_patterns:
            qsos, skipped = filter_qsos_by_callsign_patterns(qsos, callsign_filter_mode, callsign_filter_patterns)
            for qso, pattern in skipped:
                reason = "not in allowlist" if callsign_filter_mode == 'allow' else f"matches block pattern \"{pattern}\""
                self._log('INFO', f"Skipping QSO with {format_qso_log_label(qso)} - {reason}")
            if skipped:
                breakdown = ', '.join(f'"{pattern}"={count}' for pattern, count in count_skipped(skipped).items())
                mode_label = 'allowlist' if callsign_filter_mode == 'allow' else 'blocklist'
                self._log('INFO', f"Skipping {len(skipped)} QSO(s) by callsign {mode_label}: {breakdown}")
            else:
                self._log('INFO', f"Callsign filter active, no matching QSO changes for mode={callsign_filter_mode}")
            stats['callsign_filter'] = {
                'mode': callsign_filter_mode,
                'patterns': callsign_filter_patterns,
                'skipped': len(skipped),
            }

        ignored_ids = sorted(normalize_ignored_dxcc(self.config.get('ignored_dxcc')))
        if ignored_ids:
            qsos, skipped = filter_qsos_by_ignored_dxcc(qsos, set(ignored_ids), self.resolve_adif_id)
            for qso, dxcc_id in skipped:
                self._log('INFO', f"Skipping QSO with {format_qso_log_label(qso)} - ignored DXCC: {self.get_dxcc_name(dxcc_id)} ({dxcc_id})")
            if skipped:
                breakdown = ', '.join(
                    f"{self.get_dxcc_name(dxcc_id)}({dxcc_id})={count}"
                    for dxcc_id, count in sorted(count_skipped(skipped).items())
                )
                self._log('INFO', f"Skipping {len(skipped)} QSO(s) by ignored DXCC: {breakdown}")
            else:
                self._log('INFO', f"Ignored DXCC active, no matching QSOs found: {ignored_ids}")
            stats['ignored_dxcc'] = {
                'ids': ignored_ids,
                'skipped': len(skipped),
            }

        qsos, already_sent = filter_qsos_by_sent_status(qsos)
        for qso in already_sent:
            self._log('INFO', f"Skipping QSO with {format_qso_log_label(qso)} - already marked as QSL sent")
        if already_sent:
            self._log('INFO', f"Skipping {len(already_sent)} QSO(s) already marked as sent")
            stats['already_sent'] = {
                'skipped': len(already_sent),
            }

        return qsos, stats

    def process_qsos_by_dxcc(self, qsos: List, include_direct_when_no_bureau: bool = False) -> Dict[Any, Any]:
        dxcc_handlers = {
            POLAND_DXCC_ID: process_qsos_poland,
        }

        buckets = {dxcc: [] for dxcc in dxcc_handlers}
        other_qsos = []
        handler_results = {}

        for qso in qsos:
            if not qso.get('CALL', ''):
                continue
            try:
                adif_id = self.resolve_adif_id(get_qso_homecall(qso))
            except Exception as e:
                self._log('WARNING', f"Could not determine DXCC for {qso.get('CALL', 'unknown')}: {e}")
                adif_id = None
            buckets.get(adif_id, other_qsos).append(qso)

        counts = [f"{self.get_dxcc_name(dxcc)}={len(items)}" for dxcc, items in buckets.items()]
        counts.append(f"Other={len(other_qsos)}")
        self._log('INFO', f"QSOs by DXCC: {', '.join(counts)}")

        total_qsos = len(qsos)
        progress_counter = 0

        def make_callback(start_offset: int) -> Callable[[int, int], None]:
            def callback(current: int, total_for_handler: int) -> None:
                self.progress_value_callback(start_offset + current, total_qsos)
            return callback

        for dxcc, handler in dxcc_handlers.items():
            items = buckets.get(dxcc, [])
            if items:
                self._progress(f"Processing {self.get_dxcc_name(dxcc)} QSOs...")
                result, total = handler(items, include_direct_when_no_bureau=include_direct_when_no_bureau, log_callback=self._log, progress_callback=make_callback(progress_counter))
                if result is not None:
                    handler_results[dxcc] = (result, total)
                progress_counter += len(items)

        if other_qsos:
            self._progress("Processing Other QSOs...")
            verified_other, total_other = process_qsos_other(other_qsos, self.qrz_api, include_direct_when_no_bureau=include_direct_when_no_bureau, log_callback=self._log, progress_callback=make_callback(progress_counter))
            if verified_other:
                handler_results['Other'] = (verified_other, total_other)

        return handler_results

    def sort_qsos_for_pdf_labels(self, qsos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sort_qsos_for_labels(qsos, self.resolve_country_name)

    def print_qso_summary(self, qsos: List) -> None:
        if not qsos:
            self._log('INFO', "QSO Summary: No QSOs")
            return

        countries = {qso.get('DXCC') for qso in qsos if qso.get('DXCC')}
        valid_dates = sorted(
            str(qso.get('QSO_DATE'))
            for qso in qsos
            if len(str(qso.get('QSO_DATE') or '')) == 8
        )

        self._log('INFO', "QSO Data Summary:")
        self._log('INFO', f"  Total QSOs: {len(qsos)}")
        if valid_dates:
            first_date, last_date = valid_dates[0], valid_dates[-1]
            self._log('INFO', f"  Date range: {first_date[:4]}-{first_date[4:6]}-{first_date[6:]} to {last_date[:4]}-{last_date[4:6]}-{last_date[6:]}")
        if countries:
            self._log('INFO', f"  Countries/DXCC: {len(countries)}")

    def _init_qrz(self) -> None:
        self.qrz_api = None
        if self.config.get('qrz_username') and self.config.get('qrz_password'):
            try:
                self.qrz_api = QRZAPI(self.config['qrz_username'], self.config['qrz_password'])
                self._log('INFO', "QRZ API initialized")
            except Exception as e:
                self._log('WARNING', f"Failed to initialize QRZ API: {e}")

    def _collect_handler_results(self, handler_results: Dict[Any, Any]) -> Tuple[List, Dict[str, Any]]:
        all_qsl_qsos = []
        stats: Dict[str, Any] = {}
        for key, (qsos_list, total_count) in handler_results.items():
            if not qsos_list:
                continue
            delivery_stats = count_qsos_by_delivery_method(qsos_list)
            name = self.get_dxcc_name(key) if key != 'Other' else 'Other'
            self._log('INFO', f"{name}: {len(qsos_list)} out of {total_count} QSOs to send (bureau={delivery_stats['bureau']}, direct={delivery_stats['direct']})")
            stats[name] = {'to_send': len(qsos_list), 'total': total_count, 'bureau': delivery_stats['bureau'], 'direct': delivery_stats['direct']}
            all_qsl_qsos.extend(qsos_list)
        return all_qsl_qsos, stats

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
            parse_date_arg(from_date)
            parse_date_arg(to_date)
            source = self.get_source_type()
            stations = []
            selected_station_ids = None

            if source == 'wavelog':
                stations = self.connect_wavelog()

                if list_stations_only:
                    self._log('INFO', "Station list mode enabled. Skipping QSO analysis.")
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

            self._init_qrz()
            self.setup_country_lookup()

            if source == 'wavelog':
                self._progress("Downloading ADIF data...")
                download_station_ids = selected_station_ids or [station['station_id'] for station in stations if station['station_id']]
                adif_content, qso_count = self.download_adif(station_ids=download_station_ids, from_date=from_date, to_date=to_date)
            else:
                self._progress("Loading ADIF data from file...")
                adif_content = load_adif_file(self.config.get('adif_file_path', ''))
                qso_count = None
            self._progress("Parsing ADIF data...")
            qsos = parse_adif_content(adif_content) if adif_content.strip() else []
            self._log('INFO', f"ADIF data loaded with {len(qsos) if qso_count is None else qso_count} QSOs, {len(qsos)} parsed successfully")

            qsos_to_process, filter_stats = self.apply_filters(qsos, from_date, to_date, modes)

            self._progress("Processing QSOs by DXCC...")
            handler_results = self.process_qsos_by_dxcc(qsos_to_process, include_direct_when_no_bureau=include_direct_when_no_bureau)
            all_qsl_qsos, stats = self._collect_handler_results(handler_results)

            output_adif_path = output_adif or 'qsl_output.adif'
            self._progress(f"Writing ADIF to {output_adif_path}...")
            write_adif_file(output_adif_path, all_qsl_qsos)
            self._log('INFO', f"Total {len(all_qsl_qsos)} QSOs to send saved to: {output_adif_path}")

            output_pdf_path = None
            if generate_pdf:
                try:
                    normalized_pdf_page_specs = normalize_pdf_page_specs(pdf_page_specs)
                    pdf_qsos = self.sort_qsos_for_pdf_labels(all_qsl_qsos)
                    if preview_pdf:
                        preview_label_data(pdf_qsos, limit=3)

                    self._progress(f"Generating PDF labels to {generate_pdf}...")
                    logo_path = self.config.get('logo_path', 'logo.png')
                    generate_pdf_labels(pdf_qsos, generate_pdf, debug_labels, logo_path, normalized_pdf_page_specs)
                    output_pdf_path = generate_pdf
                    self._progress(f"PDF labels generated: {generate_pdf}")
                    self._log('INFO', f"PDF labels generated: {generate_pdf}")
                except Exception as e:
                    self._log('ERROR', f"Failed to generate PDF labels: {e}")
                    raise

            delivery_method_stats = count_qsos_by_delivery_method(all_qsl_qsos)
            self._log('INFO', f"Delivery methods: bureau: {delivery_method_stats['bureau']}, direct: {delivery_method_stats['direct']}")

            stats.update(filter_stats)
            stats['total_to_send'] = len(all_qsl_qsos)
            stats['delivery_methods'] = {
                'bureau': delivery_method_stats['bureau'],
                'direct': delivery_method_stats['direct'],
                'include_direct_when_no_bureau': bool(include_direct_when_no_bureau),
            }
            stats['can_mark_as_sent'] = bool(self.api_client is not None and self.api_client.can_mark_as_sent())
            self.progress_value_callback(len(qsos), len(qsos))

            return {
                'success': True,
                'qsl_qsos': all_qsl_qsos,
                'output_adif': output_adif_path,
                'output_pdf': output_pdf_path,
                'stats': stats,
                'stations': stations,
            }

        except (ConfigError, QSLProcessorError, WavelogAPIError, ADIFFileError, ValueError) as e:
            self._log('ERROR', f"Processing error: {e}")
            return _failure_result(e)
        except Exception as e:
            self._log('ERROR', f"Unexpected error: {e}")
            self._log('DEBUG', traceback.format_exc())
            return _failure_result(e)

    def plan_mark_as_sent_from_adif(self, adif_file_path: str, sent_date: Optional[date] = None) -> MarkSentPlan:
        self._progress(f"Loading QSOs from {adif_file_path}...")
        qsos = [qso for qso in load_qslmaster_output_file(adif_file_path) if str(qso.get('QSL_SENT', '') or '').strip().upper() == 'Y']
        self._log('INFO', f"Loaded {len(qsos)} QSO(s) marked as sent from {adif_file_path}")
        self.connect_wavelog()
        ensure_mark_as_sent_supported(self.api_client)
        self._progress("Matching QSOs with Wavelog...")
        plan = plan_mark_as_sent(self.api_client, qsos, sent_date)
        self._log('INFO', f"Mark as sent: matched={len(plan.matched)}, not found={len(plan.not_found)}, ambiguous={len(plan.ambiguous)}")
        for qso in plan.not_found:
            self._log('WARNING', f"  Not found in Wavelog: {format_qso_log_label(qso)} {qso.get('BAND', '')}")
        for qso in plan.ambiguous:
            self._log('WARNING', f"  Ambiguous match in Wavelog (skipped): {format_qso_log_label(qso)} {qso.get('BAND', '')}")
        return plan

    def apply_mark_as_sent(self, plan: MarkSentPlan, should_stop: Optional[Callable[[], bool]] = None) -> MarkSentResult:
        self._progress(f"Marking {len(plan.matched)} QSO(s) as sent in Wavelog...")
        result = apply_mark_as_sent(self.api_client, plan, progress_callback=self.progress_value_callback, should_stop=should_stop)
        for qso, error in result.failed:
            self._log('WARNING', f"  Failed to mark {format_qso_log_label(qso)}: {error}")
        self._log('INFO', f"Marked {result.updated} QSO(s) as sent in Wavelog ({len(result.failed)} failed)")
        return result
