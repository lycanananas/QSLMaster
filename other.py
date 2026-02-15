import logging
from typing import List, Optional

from qrz import QRZAPI, QRZAPIError


logger = logging.getLogger(__name__)


def process_qsos_other(qsos: List, qrz_api: Optional[QRZAPI] = None) -> List:
    logger.info(f"Processing {len(qsos)} Other QSOs")
    
    verified_qsos = []
    
    if not qrz_api:
        logger.warning("QRZ API not available, skipping QSL verification")
        return verified_qsos
    
    for qso in qsos:
        callsign = qso.get('CALL', '').strip()
        if not callsign:
            continue
        
        try:
            has_manager = qrz_api.has_qsl_manager(callsign)
            
            if has_manager:
                verified_qsos.append(qso)
                logger.info(f"  QRZ result: {callsign} has QSL manager")
            else:
                logger.info(f"  QRZ result: {callsign} does not have QSL manager")
        except QRZAPIError as e:
            logger.warning(f"  QRZ result: {callsign} lookup error: {e}")
    
    logger.info(f"Verified {len(verified_qsos)} QSLs with QRZ (out of {len(qsos)})")
    return verified_qsos
