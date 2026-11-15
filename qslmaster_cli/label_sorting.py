from typing import Any, Callable, Dict, List, Tuple

from .qso_utils import format_qso_datetime, get_qso_call, get_qso_homecall

QSO = Dict[str, Any]


def get_delivery_sort_rank(qso: QSO) -> int:
    return 1 if str(qso.get('QSL_SENT_VIA', '') or '').strip().upper() == 'D' else 0


def get_poland_via_sort_key(qso: QSO, country_name: str) -> Tuple[int, str]:
    if country_name.casefold() != 'poland':
        return (0, '')
    qsl_via = str(qso.get('QSL_VIA', '') or '').strip().upper()
    if qsl_via:
        return (0, qsl_via.casefold())
    return (1, '')


def get_label_sort_key(qso: QSO, resolve_country_name: Callable[[str], str]) -> Tuple[int, int, str, Tuple[int, str], int, str, str, str]:
    homecall = get_qso_homecall(qso)
    country_name = ''
    if homecall:
        try:
            country_name = str(resolve_country_name(homecall) or '').strip()
        except Exception:
            country_name = ''

    return (
        get_delivery_sort_rank(qso),
        0 if country_name else 1,
        country_name.casefold(),
        get_poland_via_sort_key(qso, country_name),
        0 if homecall else 1,
        homecall.casefold(),
        get_qso_call(qso).casefold(),
        format_qso_datetime(qso),
    )


def sort_qsos_for_labels(qsos: List[QSO], resolve_country_name: Callable[[str], str]) -> List[QSO]:
    return sorted(qsos, key=lambda qso: get_label_sort_key(qso, resolve_country_name))
