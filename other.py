import logging
import time
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from qrz import QRZAPI, QRZAPIError


logger = logging.getLogger(__name__)


def process_qsos_other(qsos: List, qrz_api: Optional[QRZAPI] = None) -> Tuple[List, int]:
    logger.info(f"Processing {len(qsos)} Other QSOs")
    
    verified_qsos = []
    
    if not qrz_api:
        logger.warning("QRZ API not available, skipping QSL verification")
        return verified_qsos, len(qsos)
    
    qsos_by_call: Dict[str, List] = defaultdict(list)
    for qso in qsos:
        callsign = qso.get('CALL', '').strip()
        if callsign:
            qsos_by_call[callsign].append(qso)
    
    unique_calls = len(qsos_by_call)
    logger.info(f"  Unique callsigns to check: {unique_calls}")
    
    qrz_cache: Dict[str, Tuple[dict, bool]] = {}
    
    checked_count = 0
    for callsign, call_qsos in qsos_by_call.items():
        checked_count += 1
        if checked_count % 10 == 0:
            logger.info(f"  Progress: {checked_count}/{unique_calls} callsigns checked")
        
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
                    logger.info(f"  QRZ result: {callsign} has QSL bureau (VIA: {qslmgr}) - {len(call_qsos)} QSO(s)")
                else:
                    logger.info(f"  QRZ result: {callsign} has QSL bureau - {len(call_qsos)} QSO(s)")
                
                for qso in call_qsos:
                    qso_copy = dict(qso)
                    qso_copy['QSL_SENT'] = 'Y'
                    qso_copy['QSL_SENT_VIA'] = 'B'
                    qso_copy['QSL_VIA'] = ''
                    verified_qsos.append(qso_copy)
            else:
                logger.info(f"  QRZ result: {callsign} does not have QSL bureau - {len(call_qsos)} QSO(s)")
        except QRZAPIError as e:
            logger.warning(f"  QRZ result: {callsign} lookup error: {e}")
    
    return verified_qsos, len(qsos)
