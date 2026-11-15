from datetime import date

import pytest

from qslmaster_cli.mark_sent import (
    apply_mark_as_sent, build_mark_sent_fields, get_qso_date_range,
    match_qsos_to_wavelog, plan_mark_as_sent,
)
from qslmaster_cli.wavelog import WavelogAPIError, WavelogAuthError

SENT_DATE = date(2026, 11, 20)


def adif_qso(call, qso_date='20261101', time_on='1210', band='40m', mode='CW', **extra):
    return {'CALL': call, 'QSO_DATE': qso_date, 'TIME_ON': time_on, 'BAND': band, 'MODE': mode, 'QSL_SENT': 'Y', 'QSL_SENT_VIA': 'B', **extra}


def wavelog_qso(qso_id, call, qso_date='2026-11-01 12:10:00', band='40m', mode='CW', submode=None):
    return {'id': qso_id, 'call': call, 'qso_date': qso_date, 'band': band, 'mode': mode, 'submode': submode}


class FakeApi:
    api_version = 'v2'

    def __init__(self, wavelog_qsos=None, can_write=True, failing_ids=()):
        self.wavelog_qsos = wavelog_qsos or []
        self.can_write = can_write
        self.failing_ids = set(failing_ids)
        self.list_calls = []
        self.updates = []

    def can_mark_as_sent(self):
        return self.can_write

    def list_qsos(self, station_ids=None, qso_since=None, qso_until=None):
        self.list_calls.append((qso_since, qso_until))
        return self.wavelog_qsos

    def update_qso(self, qso_id, fields):
        if qso_id in self.failing_ids:
            raise WavelogAPIError('HTTP error 400 (validation_error): qsl_sent')
        self.updates.append((qso_id, fields))


def test_fields_include_via_and_sent_date():
    fields = build_mark_sent_fields(adif_qso('SP5ABC', QSL_VIA='OT-25'), SENT_DATE)
    assert fields == {'qsl_sent': 'Y', 'qslsdate': '2026-11-20', 'qsl_sent_via': 'B', 'qsl_via': 'OT-25'}
    assert 'qsl_via' not in build_mark_sent_fields(adif_qso('DL1AA'), SENT_DATE)
    assert 'qsl_sent_via' not in build_mark_sent_fields(adif_qso('DL1AA', QSL_SENT_VIA='X'), SENT_DATE)


def test_match_by_call_datetime_and_band():
    plan = match_qsos_to_wavelog(
        [adif_qso('SP5ABC'), adif_qso('dl1aa', time_on='121500', band='20M')],
        [wavelog_qso(1, 'SP5ABC'), wavelog_qso(2, 'DL1AA', '2026-11-01 12:15:00', '20m'), wavelog_qso(3, 'SP5ABC', band='20m')],
        SENT_DATE,
    )
    assert [match.wavelog_id for match in plan.matched] == [1, 2]
    assert plan.not_found == [] and plan.ambiguous == []


def test_same_call_band_minute_is_disambiguated_by_mode_then_seconds():
    wavelog_qsos = [
        wavelog_qso(1, 'SP5ABC', '2026-11-01 12:10:05', mode='CW'),
        wavelog_qso(2, 'SP5ABC', '2026-11-01 12:10:05', mode='MFSK', submode='FT4'),
        wavelog_qso(3, 'SP5ABC', '2026-11-01 12:10:40', mode='MFSK', submode='FT4'),
    ]
    plan = match_qsos_to_wavelog(
        [adif_qso('SP5ABC', time_on='121005', mode='CW'), adif_qso('SP5ABC', time_on='121040', mode='MFSK', SUBMODE='FT4')],
        wavelog_qsos,
    )
    assert [match.wavelog_id for match in plan.matched] == [1, 3]


def test_duplicates_in_wavelog_are_reported_as_ambiguous():
    plan = match_qsos_to_wavelog([adif_qso('SP5ABC')], [wavelog_qso(1, 'SP5ABC'), wavelog_qso(2, 'SP5ABC')])
    assert plan.matched == [] and len(plan.ambiguous) == 1


def test_missing_and_invalid_qsos_are_not_found():
    plan = match_qsos_to_wavelog([adif_qso('SP5ABC'), adif_qso('SP5XYZ', qso_date='bad')], [wavelog_qso(1, 'SP5ABC', band='20m')])
    assert len(plan.not_found) == 2


def test_each_wavelog_qso_is_used_once():
    plan = match_qsos_to_wavelog([adif_qso('SP5ABC'), adif_qso('SP5ABC')], [wavelog_qso(1, 'SP5ABC')])
    assert [match.wavelog_id for match in plan.matched] == [1]
    assert len(plan.not_found) == 1


def test_date_range_and_plan_use_server_side_filter():
    qsos = [adif_qso('SP5ABC', '20261103'), adif_qso('DL1AA', '20261101')]
    assert get_qso_date_range(qsos) == ('2026-11-01', '2026-11-03')
    api = FakeApi([wavelog_qso(1, 'DL1AA')])
    plan = plan_mark_as_sent(api, qsos, SENT_DATE)
    assert api.list_calls == [('2026-11-01', '2026-11-03')]
    assert [match.wavelog_id for match in plan.matched] == [1]


def test_plan_requires_v2_with_write_scope():
    with pytest.raises(WavelogAuthError, match='qso:write'):
        plan_mark_as_sent(FakeApi(can_write=False), [adif_qso('SP5ABC')])
    v1_api = FakeApi()
    v1_api.api_version = 'v1'
    with pytest.raises(WavelogAPIError, match='API v2'):
        plan_mark_as_sent(v1_api, [adif_qso('SP5ABC')])


def test_apply_reports_failures_progress_and_stop():
    api = FakeApi([wavelog_qso(1, 'SP5ABC'), wavelog_qso(2, 'DL1AA'), wavelog_qso(3, 'F4ABC')], failing_ids={2})
    plan = plan_mark_as_sent(api, [adif_qso('SP5ABC'), adif_qso('DL1AA'), adif_qso('F4ABC')], SENT_DATE)
    progress = []
    result = apply_mark_as_sent(api, plan, progress_callback=lambda current, total: progress.append((current, total)))
    assert result.updated == 2
    assert [qso['CALL'] for qso, _ in result.failed] == ['DL1AA']
    assert progress == [(1, 3), (2, 3), (3, 3)]

    stopped = apply_mark_as_sent(api, plan, should_stop=lambda: True)
    assert stopped.updated == 0
