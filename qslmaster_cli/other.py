import logging
import time
from typing import List, Optional, Tuple, Dict, Callable
from collections import defaultdict

from .qrz import QRZAPI, QRZAPIError


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

        if qrz_disabled:
            for _ in call_qsos:
                processed_qsos += 1
                progress(processed_qsos, len(qsos))
            continue
        
        t_call_start = time.perf_counter()
        try:
            if callsign not in qrz_cache:
                t_api_start = time.perf_counter()
                data = qrz_api.lookup_call(callsign)
                t_api_end = time.perf_counter()
                api_time = (t_api_end - t_api_start) * 1000
                
                t_proc_start = time.perf_counter()
                has_bureau = qrz_api.has_qsl_manager(callsign=callsign, data=data)
                t_proc_end = time.perf_counter()
                proc_time = (t_proc_end - t_proc_start) * 1000
                
                qrz_cache[callsign] = (data, has_bureau)
                
                t_call_end = time.perf_counter()
                total_time = (t_call_end - t_call_start) * 1000
                logger.debug(f"  {callsign}: total={total_time:.1f}ms (API={api_time:.1f}ms, processing={proc_time:.1f}ms)")
            else:
                data, has_bureau = qrz_cache[callsign]
            
            if has_bureau:
                qslmgr = data.get('qslmgr', '').strip()
                if qslmgr:
                    log('INFO', f"  QRZ result: {callsign} has QSL bureau (VIA: {qslmgr}) - {len(call_qsos)} QSO(s)")
                else:
                    log('INFO', f"  QRZ result: {callsign} has QSL bureau - {len(call_qsos)} QSO(s)")
                
                for qso in call_qsos:
                    qso_copy = dict(qso)
                    qso_copy['QSL_SENT'] = 'Y'
                    qso_copy['QSL_SENT_VIA'] = 'B'
                    qso_copy['QSL_VIA'] = ''
                    verified_qsos.append(qso_copy)
                    processed_qsos += 1
                    progress(processed_qsos, len(qsos))
            else:
                if include_direct_when_no_bureau:
                    log('INFO', f"  QRZ result: {callsign} does not have QSL bureau, added as direct - {len(call_qsos)} QSO(s)")
                    for qso in call_qsos:
                        qso_copy = dict(qso)
                        qso_copy['QSL_SENT'] = 'Y'
                        qso_copy['QSL_SENT_VIA'] = 'D'
                        qso_copy['QSL_VIA'] = ''
                        verified_qsos.append(qso_copy)
                        processed_qsos += 1
                        progress(processed_qsos, len(qsos))
                else:
                    log('INFO', f"  QRZ result: {callsign} does not have QSL bureau - {len(call_qsos)} QSO(s)")
                    for _ in call_qsos:
                        processed_qsos += 1
                        progress(processed_qsos, len(qsos))
        except QRZAPIError as e:
            qrz_error_count += 1
            log('WARNING', f"  QRZ result: {callsign} lookup error: {e}")
            if qrz_error_count >= 3 and not qrz_disabled:
                qrz_disabled = True
                log('WARNING', "  QRZ API returned errors 3 times - ignoring QRZ lookups for remaining callsigns")
            for _ in call_qsos:
                processed_qsos += 1
                progress(processed_qsos, len(qsos))
    
    return verified_qsos, len(qsos)
