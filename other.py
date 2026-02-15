import logging
from typing import List, Optional, Tuple

from qrz import QRZAPI, QRZAPIError


logger = logging.getLogger(__name__)


def process_qsos_other(qsos: List, qrz_api: Optional[QRZAPI] = None) -> Tuple[List, int]:
    logger.info(f"Processing {len(qsos)} Other QSOs")
    
    verified_qsos = []
    
    if not qrz_api:
        logger.warning("QRZ API not available, skipping QSL verification")
        return verified_qsos, len(qsos)
    
    for qso in qsos:
        callsign = qso.get('CALL', '').strip()
        if not callsign:
            continue
        
        try:
            has_bureau = qrz_api.has_qsl_manager(callsign)
            
            if has_bureau:
                qso_copy = dict(qso)
                qso_copy['QSL_SENT'] = 'Y'
                verified_qsos.append(qso_copy)
                logger.info(f"  QRZ result: {callsign} has QSL bureau")
            else:
                logger.info(f"  QRZ result: {callsign} does not have QSL bureau")
        except QRZAPIError as e:
            logger.warning(f"  QRZ result: {callsign} lookup error: {e}")
    
    return verified_qsos, len(qsos)
