from datetime import datetime
from typing import Any, Dict, List

from .callsign_utils import extract_homecall


def get_qso_call(qso: Dict[str, Any]) -> str:
    return str(qso.get('CALL', '') or '').strip().upper()


def get_qso_homecall(qso: Dict[str, Any]) -> str:
    return extract_homecall(get_qso_call(qso))


def format_qso_datetime(qso: Dict[str, Any]) -> str:
    qso_date_raw = str(qso.get('QSO_DATE', '') or '').strip()
    qso_time_raw = str(qso.get('TIME_ON', '') or '').strip()

    qso_date_text = qso_date_raw or 'unknown-date'
    if qso_date_raw:
        try:
            qso_date_text = datetime.strptime(qso_date_raw, '%Y%m%d').strftime('%Y-%m-%d')
        except ValueError:
            pass

    qso_time_text = qso_time_raw or 'unknown-time'
    time_format = {4: '%H%M', 6: '%H%M%S'}.get(len(qso_time_raw))
    if time_format:
        try:
            qso_time_text = datetime.strptime(qso_time_raw, time_format).strftime('%H:%M:%S')
        except ValueError:
            pass

    return f'{qso_date_text} {qso_time_text}'


def format_qso_log_label(qso: Dict[str, Any]) -> str:
    return f"{get_qso_call(qso) or 'UNKNOWN'} on {format_qso_datetime(qso)}"


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


def mark_qsos_to_send(qsos: List[Dict[str, Any]], sent_via: str, qsl_via: str = '') -> List[Dict[str, Any]]:
    marked = []
    for qso in qsos:
        qso_copy = dict(qso)
        qso_copy['QSL_SENT'] = 'Y'
        qso_copy['QSL_SENT_VIA'] = sent_via
        qso_copy['QSL_VIA'] = qsl_via
        marked.append(qso_copy)
    return marked
