import logging
import time
from typing import List, Optional, Tuple, Dict, Callable
from collections import defaultdict

from .qrz import QRZAPI, QRZAPIError
from .qso_utils import mark_qsos_to_send


logger = logging.getLogger(__name__)


def process_qsos_other(qsos: List, qrz_api: Optional[QRZAPI] = None, include_direct_when_no_bureau: bool = False, log_callback: Optional[Callable[[str, str], None]] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[List, int]:
    def log(level: str, msg: str) -> None:
        if log_callback:
            log_callback(level, msg)
        else:
            getattr(logger, level.lower(), logger.info)(msg)

    def progress(current: int, total: int) -> None:
        if progress_callback:
            progress_callback(current, total)

    log('INFO', f"Processing {len(qsos)} Other QSOs")

    verified_qsos = []

    if not qrz_api:
        log('WARNING', "QRZ API not available, skipping QSL verification")
        return verified_qsos, len(qsos)

    qsos_by_call: Dict[str, List] = defaultdict(list)
    for qso in qsos:
        callsign = qso.get('CALL', '').strip()
        if callsign:
            qsos_by_call[callsign].append(qso)

    unique_calls = len(qsos_by_call)
    log('INFO', f"  Unique callsigns to check: {unique_calls}")

    qrz_cache: Dict[str, Tuple[dict, bool]] = {}
    qrz_error_count = 0
    qrz_disabled = False

    checked_count = 0
    processed_qsos = 0
    for callsign, call_qsos in qsos_by_call.items():
        checked_count += 1
        if checked_count % 10 == 0:
            log('INFO', f"  Progress: {checked_count}/{unique_calls} callsigns checked")

        if not qrz_disabled:
            try:
                if callsign not in qrz_cache:
                    t_api_start = time.perf_counter()
                    data = qrz_api.lookup_call(callsign)
                    has_bureau = qrz_api.has_qsl_manager(callsign=callsign, data=data)
                    qrz_cache[callsign] = (data, has_bureau)
                    logger.debug(f"  {callsign}: total={(time.perf_counter() - t_api_start) * 1000:.1f}ms")
                data, has_bureau = qrz_cache[callsign]

                if has_bureau:
                    qslmgr = data.get('qslmgr', '').strip()
                    via_text = f" (VIA: {qslmgr})" if qslmgr else ""
                    log('INFO', f"  QRZ result: {callsign} has QSL bureau{via_text} - {len(call_qsos)} QSO(s)")
                    verified_qsos.extend(mark_qsos_to_send(call_qsos, 'B'))
                elif include_direct_when_no_bureau:
                    log('INFO', f"  QRZ result: {callsign} does not have QSL bureau, added as direct - {len(call_qsos)} QSO(s)")
                    verified_qsos.extend(mark_qsos_to_send(call_qsos, 'D'))
                else:
                    log('INFO', f"  QRZ result: {callsign} does not have QSL bureau - {len(call_qsos)} QSO(s)")
            except QRZAPIError as e:
                qrz_error_count += 1
                log('WARNING', f"  QRZ result: {callsign} lookup error: {e}")
                if qrz_error_count >= 3:
                    qrz_disabled = True
                    log('WARNING', "  QRZ API returned errors 3 times - ignoring QRZ lookups for remaining callsigns")

        processed_qsos += len(call_qsos)
        progress(processed_qsos, len(qsos))

    return verified_qsos, len(qsos)
