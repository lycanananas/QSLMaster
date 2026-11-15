import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .wavelog import WavelogAPIError, WavelogAuthError, WAVELOG_API_V2_MARK_AS_SENT_SCOPE

QSL_SENT_VIA_VALUES = {'B', 'D', 'E', 'M'}


@dataclass
class MarkSentMatch:
    qso: Dict[str, Any]
    wavelog_id: int
    fields: Dict[str, Any]


@dataclass
class MarkSentPlan:
    matched: List[MarkSentMatch] = field(default_factory=list)
    not_found: List[Dict[str, Any]] = field(default_factory=list)
    ambiguous: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MarkSentResult:
    updated: int = 0
    failed: List[Tuple[Dict[str, Any], str]] = field(default_factory=list)


def _digits(value: Any) -> str:
    return re.sub(r'\D', '', str(value or ''))


def _normalize_text(value: Any) -> str:
    return str(value or '').strip().upper()


def _adif_qso_datetime(qso: Dict[str, Any]) -> str:
    qso_date = _digits(qso.get('QSO_DATE'))[:8]
    time_on = _digits(qso.get('TIME_ON'))
    time_on = (time_on + '000000')[:6] if len(time_on) in (4, 6) else ''
    return f"{qso_date}{time_on}" if len(qso_date) == 8 and time_on else ''


def _wavelog_qso_datetime(qso: Dict[str, Any]) -> str:
    value = _digits(qso.get('qso_date'))
    if len(value) == 12:
        value += '00'
    return value[:14] if len(value) >= 14 else ''


def _match_key(call: str, qso_datetime: str, band: str) -> Tuple[str, str, str]:
    return _normalize_text(call), qso_datetime[:12], str(band or '').strip().lower()


def _mode_matches(adif_qso: Dict[str, Any], wavelog_qso: Dict[str, Any]) -> bool:
    adif_modes = {_normalize_text(adif_qso.get('MODE')), _normalize_text(adif_qso.get('SUBMODE'))} - {''}
    wavelog_modes = {_normalize_text(wavelog_qso.get('mode')), _normalize_text(wavelog_qso.get('submode'))} - {''}
    return not adif_modes or not wavelog_modes or bool(adif_modes & wavelog_modes)


def build_mark_sent_fields(qso: Dict[str, Any], sent_date: Optional[date] = None) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        'qsl_sent': 'Y',
        'qslsdate': (sent_date or date.today()).isoformat(),
    }
    sent_via = _normalize_text(qso.get('QSL_SENT_VIA'))
    if sent_via in QSL_SENT_VIA_VALUES:
        fields['qsl_sent_via'] = sent_via
    qsl_via = str(qso.get('QSL_VIA') or '').strip()
    if qsl_via:
        fields['qsl_via'] = qsl_via
    return fields


def get_qso_date_range(qsos: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    dates = sorted(
        datetime.strptime(qso_datetime[:8], '%Y%m%d').strftime('%Y-%m-%d')
        for qso_datetime in (_adif_qso_datetime(qso) for qso in qsos)
        if qso_datetime
    )
    if not dates:
        return None, None
    return dates[0], dates[-1]


def match_qsos_to_wavelog(qsos: List[Dict[str, Any]], wavelog_qsos: List[Dict[str, Any]], sent_date: Optional[date] = None) -> MarkSentPlan:
    index: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for wavelog_qso in wavelog_qsos:
        qso_datetime = _wavelog_qso_datetime(wavelog_qso)
        if qso_datetime and wavelog_qso.get('id') is not None:
            index[_match_key(wavelog_qso.get('call'), qso_datetime, wavelog_qso.get('band'))].append(wavelog_qso)

    plan = MarkSentPlan()
    used_ids = set()
    for qso in qsos:
        qso_datetime = _adif_qso_datetime(qso)
        candidates = index.get(_match_key(qso.get('CALL'), qso_datetime, qso.get('BAND')), []) if qso_datetime else []
        candidates = [candidate for candidate in candidates if int(candidate['id']) not in used_ids]

        if len(candidates) > 1:
            candidates = [candidate for candidate in candidates if _mode_matches(qso, candidate)]
        if len(candidates) > 1:
            candidates = [candidate for candidate in candidates if _wavelog_qso_datetime(candidate) == qso_datetime]

        if not candidates:
            plan.not_found.append(qso)
        elif len(candidates) > 1:
            plan.ambiguous.append(qso)
        else:
            wavelog_id = int(candidates[0]['id'])
            used_ids.add(wavelog_id)
            plan.matched.append(MarkSentMatch(qso=qso, wavelog_id=wavelog_id, fields=build_mark_sent_fields(qso, sent_date)))

    return plan


def ensure_mark_as_sent_supported(api_client) -> None:
    if getattr(api_client, 'api_version', '') != 'v2':
        raise WavelogAPIError("Mark as sent requires a Wavelog API v2 token (Wavelog 3.2.5 or later)")
    if not api_client.can_mark_as_sent():
        raise WavelogAuthError(f"Wavelog API v2 token is missing required scope: {WAVELOG_API_V2_MARK_AS_SENT_SCOPE}")


def plan_mark_as_sent(api_client, qsos: List[Dict[str, Any]], sent_date: Optional[date] = None) -> MarkSentPlan:
    ensure_mark_as_sent_supported(api_client)
    qso_since, qso_until = get_qso_date_range(qsos)
    if not qso_since:
        return MarkSentPlan(not_found=list(qsos))
    wavelog_qsos = api_client.list_qsos(qso_since=qso_since, qso_until=qso_until)
    return match_qsos_to_wavelog(qsos, wavelog_qsos, sent_date)


def apply_mark_as_sent(
    api_client,
    plan: MarkSentPlan,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> MarkSentResult:
    ensure_mark_as_sent_supported(api_client)
    result = MarkSentResult()
    total = len(plan.matched)
    for position, match in enumerate(plan.matched, start=1):
        if should_stop and should_stop():
            break
        try:
            api_client.update_qso(match.wavelog_id, match.fields)
            result.updated += 1
        except WavelogAuthError:
            raise
        except WavelogAPIError as e:
            result.failed.append((match.qso, str(e)))
        if progress_callback:
            progress_callback(position, total)
    return result
