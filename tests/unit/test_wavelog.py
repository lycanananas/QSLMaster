from unittest import mock

import pytest

from conftest import FakeResponse
from qslmaster_cli.wavelog import (
    WavelogAPI, WavelogAPIv2, WavelogAPIError, WavelogAuthError,
    create_wavelog_api, is_wavelog_api_v2_key,
)

TOKEN_SCOPES = ['qso:read', 'station:read']


class FakeWavelogV2:
    def __init__(self, scopes=None, qso_pages=None, rate_limited_first=False):
        self.scopes = TOKEN_SCOPES if scopes is None else scopes
        self.qso_pages = qso_pages or []
        self.rate_limited_first = rate_limited_first
        self.calls = []

    def __call__(self, method, url, params=None, json=None, timeout=None):
        resource = url.split('/api/v2/', 1)[1]
        self.calls.append((method, url, resource, dict(params or {}), json))
        if resource == 'token':
            return FakeResponse(200, {'data': {'owner': 'SQ5FOX', 'scopes': self.scopes, 'expires_at': None}})
        if resource == 'station':
            return FakeResponse(200, {'data': [
                {'id': 1, 'callsign': 'SQ5FOX', 'name': 'Home', 'active': True},
                {'id': 2, 'callsign': 'SQ5FOX/P', 'name': 'Field', 'active': False},
            ]})
        if resource == 'qso' and method == 'GET':
            if self.rate_limited_first:
                self.rate_limited_first = False
                return FakeResponse(429, {'error': {'code': 'rate_limited', 'details': {'retry_after': 7}}})
            page = int((params or {}).get('page', 1))
            data = self.qso_pages[page - 1]
            return FakeResponse(200, {'data': data, 'meta': {'has_more': page < len(self.qso_pages)}})
        if method == 'PATCH':
            return FakeResponse(200, {'data': {'id': int(resource.split('/')[1]), **(json or {})}})
        return FakeResponse(404, {'error': {'code': 'not_found', 'message': 'Not found'}})


def make_v2(fake, base_url='https://log.example/index.php', sleep=None):
    with mock.patch('requests.Session.request', side_effect=fake):
        api = WavelogAPIv2(base_url, 'wl2_token', sleep=sleep or (lambda seconds: None))
    return api


def test_key_detection_and_factory():
    assert is_wavelog_api_v2_key(' wl2_abc')
    assert not is_wavelog_api_v2_key('wlabc')
    fake = FakeWavelogV2()
    with mock.patch('requests.Session.request', side_effect=fake):
        assert isinstance(create_wavelog_api('https://log.example', 'wl2_x'), WavelogAPIv2)


@pytest.mark.parametrize('base_url, expected', [
    ('https://log.example', 'https://log.example/api/v2/token'),
    ('https://log.example/index.php/', 'https://log.example/index.php/api/v2/token'),
    ('https://log.example/api', 'https://log.example/api/v2/token'),
    ('https://log.example/api/v2', 'https://log.example/api/v2/token'),
])
def test_v2_url_building(base_url, expected):
    fake = FakeWavelogV2()
    make_v2(fake, base_url)
    assert fake.calls[0][1] == expected


def test_v2_missing_scopes_raise_auth_error():
    with pytest.raises(WavelogAuthError, match='missing required scope\\(s\\): qso:read, station:read$'):
        make_v2(FakeWavelogV2(scopes=['club:read']))


def test_v2_mark_as_sent_capability_follows_qso_write_scope():
    assert not make_v2(FakeWavelogV2()).can_mark_as_sent()
    assert make_v2(FakeWavelogV2(scopes=TOKEN_SCOPES + ['qso:write'])).can_mark_as_sent()


@pytest.mark.parametrize('status, error, message', [
    (401, {'code': 'invalid_token', 'message': 'Invalid'}, 'invalid or revoked'),
    (401, {'code': 'token_expired', 'message': 'Expired'}, 'has expired'),
    (403, {'code': 'insufficient_scope', 'message': 'x', 'details': {'required_scope': 'qso:read'}}, 'missing required scope: qso:read$'),
])
def test_v2_auth_errors_are_mapped(status, error, message):
    def fake(method, url, params=None, json=None, timeout=None):
        return FakeResponse(status, {'error': error})
    with mock.patch('requests.Session.request', side_effect=fake):
        with pytest.raises(WavelogAuthError, match=message):
            WavelogAPIv2('https://log.example', 'wl2_token')


def test_v2_station_mapping():
    fake = FakeWavelogV2()
    api = make_v2(fake)
    with mock.patch('requests.Session.request', side_effect=fake):
        stations = api.get_station_info()
    assert stations == [
        {'station_id': '1', 'station_callsign': 'SQ5FOX', 'station_profile_name': 'Home', 'station_active': '1'},
        {'station_id': '2', 'station_callsign': 'SQ5FOX/P', 'station_profile_name': 'Field', 'station_active': '0'},
    ]


def test_v2_adif_download_pages_filters_and_strips_headers():
    fake = FakeWavelogV2(qso_pages=[
        {'exported': 2, 'adif': 'Wavelog\n<EOH>\n<CALL:5>SP5AA<EOR>\n<CALL:5>SP5AB<EOR>\n'},
        {'exported': 1, 'adif': 'Wavelog\n<eoh>\n<CALL:5>SP5AC<EOR>\n'},
    ])
    api = make_v2(fake)
    with mock.patch('requests.Session.request', side_effect=fake):
        adif, count = api.get_contacts_adif(station_ids=['1', '2'], qso_since='2026-11-01', qso_until='2026-11-07')
    assert count == 3
    assert adif == '<CALL:5>SP5AA<EOR>\n<CALL:5>SP5AB<EOR>\n<CALL:5>SP5AC<EOR>'
    qso_params = [call[3] for call in fake.calls if call[2] == 'qso']
    assert qso_params[0] == {'station_id': '1,2', 'qso_since': '2026-11-01', 'qso_until': '2026-11-07', 'format': 'adif', 'per_page': 5000, 'page': 1}
    assert qso_params[1]['page'] == 2


def test_v2_adif_download_with_no_qsos_returns_empty():
    fake = FakeWavelogV2(qso_pages=[{'exported': 0, 'adif': None}])
    api = make_v2(fake)
    with mock.patch('requests.Session.request', side_effect=fake):
        assert api.get_contacts_adif() == ('', 0)


def test_v2_rate_limit_is_retried_with_server_delay():
    slept = []
    fake = FakeWavelogV2(qso_pages=[[{'id': 1}]], rate_limited_first=True)
    api = make_v2(fake, sleep=slept.append)
    with mock.patch('requests.Session.request', side_effect=fake):
        assert api.list_qsos() == [{'id': 1}]
    assert slept == [7.0]


def test_v2_update_qso_sends_patch():
    fake = FakeWavelogV2(scopes=TOKEN_SCOPES + ['qso:write'])
    api = make_v2(fake)
    with mock.patch('requests.Session.request', side_effect=fake):
        api.update_qso(42, {'qsl_sent': 'Y'})
    assert fake.calls[-1][0] == 'PATCH'
    assert fake.calls[-1][2] == 'qso/42'
    assert fake.calls[-1][4] == {'qsl_sent': 'Y'}


def test_v1_rejected_key_raises_auth_error():
    response = FakeResponse(401, {'status': 'failed', 'reason': 'missing or invalid api key'})
    with mock.patch('requests.Session.post', return_value=response):
        with pytest.raises(WavelogAuthError, match='missing or invalid api key'):
            WavelogAPI('https://log.example', 'wlbad')


def test_v1_download_iterates_stations_and_ignores_date_filter():
    def fake_post(url, json=None, timeout=None):
        if url.endswith('/version'):
            return FakeResponse(200, {'version': '2.1.0'})
        station_id = json['station_id']
        return FakeResponse(200, {'exported_qsos': 1, 'adif': f'h<EOH><CALL:5>SP5A{station_id}<EOR>'})

    with mock.patch('requests.Session.post', side_effect=fake_post):
        api = WavelogAPI('https://log.example', 'wlkey')
        adif, count = api.get_contacts_adif(station_ids=['1', '2'], qso_since='2026-11-01')
    assert not api.supports_date_filter
    assert count == 2
    assert adif == '<CALL:5>SP5A1<EOR>\n<CALL:5>SP5A2<EOR>'


def test_v1_old_version_is_rejected():
    with mock.patch('requests.Session.post', return_value=FakeResponse(200, {'version': '1.9.0'})):
        with pytest.raises(WavelogAPIError, match='not supported'):
            WavelogAPI('https://log.example', 'wlkey')
