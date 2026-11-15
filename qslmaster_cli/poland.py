import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable
from collections import defaultdict

import requests

from .cache import get_cache_dir, read_cache_metadata, write_cache_metadata
from .callsign_utils import extract_homecall
from .qso_utils import mark_qsos_to_send


logger = logging.getLogger(__name__)

PZK_QSL_LIST_URL = "https://pzk.org.pl/osec_qsl.txt"


class PZKAPIError(Exception):
    pass


def get_pzk_cache_paths() -> Tuple[Path, Path]:
    cache_dir = get_cache_dir()
    return cache_dir / 'pzk_osec_qsl.txt', cache_dir / '.pzk_metadata.json'


def _parse_pzk_qsl_list(content: bytes) -> Dict[str, str]:
    text = content.decode("cp1250", errors="replace")
    qsl_list: Dict[str, str] = {}
    for line in text.splitlines()[1:]:
        line = line.strip()
        if ";" not in line:
            continue
        calls_text, ot_text = line.rsplit(";", 1)
        ot_text = ot_text.strip()
        if not ot_text:
            continue
        for call in calls_text.split(","):
            call = call.strip().strip(".").upper()
            if call:
                qsl_list.setdefault(call, ot_text)
    return qsl_list


def _download_pzk_qsl_list() -> Tuple[bytes, Dict[str, str]]:
    t_start = time.perf_counter()
    try:
        response = requests.get(PZK_QSL_LIST_URL, timeout=30)
    except requests.exceptions.RequestException as e:
        raise PZKAPIError(f"PZK request failed: {e}")
    t_http = time.perf_counter()

    if response.status_code != 200:
        raise PZKAPIError(f"PZK HTTP error: {response.status_code}")

    qsl_list = _parse_pzk_qsl_list(response.content)
    if not qsl_list:
        raise PZKAPIError("PZK QSL list is empty or has an unexpected format")
    t_end = time.perf_counter()

    logger.debug(f"PZK QSL list: {len(qsl_list)} callsigns, total={(t_end - t_start) * 1000:.1f}ms (HTTP={(t_http - t_start) * 1000:.1f}ms, parse={(t_end - t_http) * 1000:.1f}ms)")
    return response.content, qsl_list


def _fetch_pzk_qsl_list(log: Optional[Callable[[str, str], None]] = None) -> Dict[str, str]:
    cache_file, metadata_file = get_pzk_cache_paths()
    try:
        content, qsl_list = _download_pzk_qsl_list()
    except PZKAPIError as e:
        cached_list = _parse_pzk_qsl_list(cache_file.read_bytes()) if cache_file.exists() else {}
        if not cached_list:
            raise
        downloaded_at = read_cache_metadata(metadata_file).get('downloaded_at', 'unknown date')
        if log:
            log('WARNING', f"  PZK QSL list download failed ({e}), using cached copy from {downloaded_at}")
        return cached_list

    try:
        cache_file.write_bytes(content)
        write_cache_metadata(metadata_file, PZK_QSL_LIST_URL, callsigns=len(qsl_list))
    except OSError as e:
        logger.debug(f"Could not write PZK QSL list cache: {e}")
    return qsl_list


def _lookup_pzk_ot(qsl_list: Dict[str, str], fullcall: str) -> Optional[str]:
    fullcall = fullcall.strip().upper()
    if fullcall in qsl_list:
        return qsl_list[fullcall]
    return qsl_list.get(extract_homecall(fullcall))


def process_qsos_poland(qsos: List, include_direct_when_no_bureau: bool = False, log_callback: Optional[Callable[[str, str], None]] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[List, int]:
    def log(level: str, msg: str) -> None:
        if log_callback:
            log_callback(level, msg)
        else:
            getattr(logger, level.lower(), logger.info)(msg)

    def progress(current: int, total: int) -> None:
        if progress_callback:
            progress_callback(current, total)

    log('INFO', f"Processing {len(qsos)} Poland QSOs")
    results = []

    qsos_by_call: Dict[str, List] = defaultdict(list)
    for qso in qsos:
        fullcall = str(qso.get("CALL", "")).strip()
        if fullcall:
            qsos_by_call[fullcall].append(qso)

    unique_calls = len(qsos_by_call)
    log('INFO', f"  Unique callsigns to check: {unique_calls}")

    if not qsos_by_call:
        return results, len(qsos)

    try:
        qsl_list = _fetch_pzk_qsl_list(log)
        log('INFO', f"  PZK QSL list loaded: {len(qsl_list)} callsigns")
    except PZKAPIError as e:
        log('WARNING', f"  PZK result: QSL list lookup error: {e}")
        log('WARNING', "  PZK QSL list unavailable - ignoring PZK lookups for remaining callsigns")
        progress(len(qsos), len(qsos))
        return results, len(qsos)

    processed_qsos = 0
    for fullcall, call_qsos in qsos_by_call.items():
        ot = _lookup_pzk_ot(qsl_list, fullcall)

        if ot:
            log('INFO', f"  PZK result: {fullcall} is a member of PZK via OT-{ot} - {len(call_qsos)} QSO(s)")
            results.extend(mark_qsos_to_send(call_qsos, 'B', f"OT-{ot}"))
        elif include_direct_when_no_bureau:
            log('INFO', f"  PZK result: {fullcall} is not a member of PZK, added as direct - {len(call_qsos)} QSO(s)")
            results.extend(mark_qsos_to_send(call_qsos, 'D'))
        else:
            log('INFO', f"  PZK result: {fullcall} is not a member of PZK - {len(call_qsos)} QSO(s)")

        processed_qsos += len(call_qsos)
        progress(processed_qsos, len(qsos))

    return results, len(qsos)
