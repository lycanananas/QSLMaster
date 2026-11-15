from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .callsign_utils import extract_homecall
from .qso_utils import get_qso_call, get_qso_homecall

QSO = Dict[str, Any]
SkippedQSOs = List[Tuple[QSO, Any]]

DIGI_MODES = ('RTTY', 'PSK', 'MFSK', 'OLIVIA', 'HELLSCHREIBER')
SSB_SUBMODES = ('SSB', 'USB', 'LSB')
NOT_LISTED = '<not-listed>'


def parse_date_arg(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Invalid date format. Use YYYY-MM-DD, got: {date_str}")


def _parse_qso_datetime(qso: QSO) -> Optional[datetime]:
    qso_date = qso.get('QSO_DATE', '')
    time_on = qso.get('TIME_ON', '000000')
    if not qso_date:
        return None
    try:
        return datetime.strptime(f"{qso_date}{time_on}", '%Y%m%d%H%M%S')
    except ValueError:
        return None


def filter_qsos_by_date_range(qsos: List[QSO], from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[QSO]:
    from_datetime = parse_date_arg(from_date)
    to_datetime = parse_date_arg(to_date)
    to_datetime_eod = to_datetime.replace(hour=23, minute=59, second=59) if to_datetime else None

    filtered = []
    for qso in qsos:
        qso_datetime = _parse_qso_datetime(qso)
        if qso_datetime is None:
            continue
        if from_datetime and qso_datetime < from_datetime:
            continue
        if to_datetime_eod and qso_datetime > to_datetime_eod:
            continue
        filtered.append(qso)
    return filtered


def parse_mode_list(modes: Optional[str]) -> List[str]:
    return [mode.strip().upper() for mode in str(modes or '').split(',') if mode.strip()]


def qso_matches_mode(qso: QSO, requested_mode: str) -> bool:
    mode = str(qso.get('MODE', '') or '').upper()
    submode = str(qso.get('SUBMODE', '') or '').upper()
    if requested_mode == 'DIGI':
        return mode in DIGI_MODES or any(digi_mode in submode for digi_mode in DIGI_MODES)
    if requested_mode == 'SSB':
        return mode == 'SSB' or submode in SSB_SUBMODES
    return mode == requested_mode or submode == requested_mode


def filter_qsos_by_mode(qsos: List[QSO], modes: Optional[str] = None) -> List[QSO]:
    mode_list = parse_mode_list(modes)
    if not mode_list:
        return qsos
    return [qso for qso in qsos if any(qso_matches_mode(qso, mode) for mode in mode_list)]


def normalize_ignored_dxcc(values: Optional[Iterable[Any]]) -> Set[int]:
    ignored_ids: Set[int] = set()
    for value in values or []:
        try:
            dxcc_id = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if dxcc_id > 0:
            ignored_ids.add(dxcc_id)
    return ignored_ids


def filter_qsos_by_ignored_dxcc(qsos: List[QSO], ignored_dxcc: Set[int], resolve_adif_id: Callable[[str], int]) -> Tuple[List[QSO], SkippedQSOs]:
    if not ignored_dxcc:
        return qsos, []

    filtered: List[QSO] = []
    skipped: SkippedQSOs = []
    for qso in qsos:
        if get_qso_call(qso):
            try:
                adif_id = resolve_adif_id(get_qso_homecall(qso))
            except Exception:
                adif_id = None
            if adif_id in ignored_dxcc:
                skipped.append((qso, adif_id))
                continue
        filtered.append(qso)
    return filtered, skipped


def normalize_callsign_filter_patterns(values: Optional[Iterable[Any]]) -> List[str]:
    normalized: List[str] = []
    for value in values or []:
        pattern = str(value or '').strip().upper()
        if pattern and pattern not in normalized:
            normalized.append(pattern)
    return normalized


def normalize_callsign_filter_target(value: Any) -> str:
    normalized_value = str(value or '').strip().upper()
    return extract_homecall(normalized_value) if normalized_value else ''


def filter_qsos_by_callsign_patterns(qsos: List[QSO], mode: str, patterns: List[str]) -> Tuple[List[QSO], SkippedQSOs]:
    if mode == 'off' or not patterns:
        return qsos, []

    pattern_set = set(patterns)
    filtered: List[QSO] = []
    skipped: SkippedQSOs = []
    for qso in qsos:
        normalized_call = normalize_callsign_filter_target(get_qso_call(qso))
        matched_pattern = normalized_call if normalized_call in pattern_set else None
        if mode == 'allow' and matched_pattern is None:
            skipped.append((qso, NOT_LISTED))
        elif mode == 'block' and matched_pattern is not None:
            skipped.append((qso, matched_pattern))
        else:
            filtered.append(qso)
    return filtered, skipped


def filter_qsos_by_sent_status(qsos: List[QSO]) -> Tuple[List[QSO], List[QSO]]:
    filtered: List[QSO] = []
    skipped: List[QSO] = []
    for qso in qsos:
        if str(qso.get('QSL_SENT', '') or '').strip().upper() == 'Y':
            skipped.append(qso)
        else:
            filtered.append(qso)
    return filtered, skipped


def count_skipped(skipped: SkippedQSOs) -> Dict[Any, int]:
    counts: Dict[Any, int] = {}
    for _, key in skipped:
        counts[key] = counts.get(key, 0) + 1
    return counts
