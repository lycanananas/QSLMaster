from unittest import mock

import pytest

from conftest import FakeResponse
from qslmaster_cli import qslmaster_core
from qslmaster_cli.adif_files import load_qsos_from_adif_file
from qslmaster_cli.qslmaster_core import QSLProcessor

INPUT_ADIF = """test <EOH>
<CALL:5>D44AC <QSO_DATE:8>20261101 <TIME_ON:4>1200 <BAND:3>20m <MODE:3>SSB <EOR>
<CALL:6>SP5ABB <QSO_DATE:8>20261101 <TIME_ON:4>1210 <BAND:3>40m <MODE:2>CW <EOR>
<CALL:8>HF0FURRY <QSO_DATE:8>20261102 <TIME_ON:4>1220 <BAND:3>40m <MODE:2>CW <EOR>
<CALL:6>SQ5JUT <QSO_DATE:8>20261102 <TIME_ON:4>1230 <BAND:3>40m <MODE:2>CW <EOR>
<CALL:6>SP5XXX <QSO_DATE:8>20261102 <TIME_ON:4>1235 <BAND:3>40m <MODE:2>CW <EOR>
<CALL:6>SP5OLD <QSO_DATE:8>20261102 <TIME_ON:4>1236 <BAND:3>40m <MODE:2>CW <QSL_SENT:1>Y <EOR>
<CALL:5>DL1AA <QSO_DATE:8>20261103 <TIME_ON:4>1240 <BAND:3>20m <MODE:3>FT8 <EOR>
<CALL:6>SP5ABC <QSO_DATE:8>20261120 <TIME_ON:4>1240 <BAND:3>20m <MODE:2>CW <EOR>
"""

PZK_LIST = b'WYKAZ QSL\r\nSP5ABB;15\r\nHF0FURRY;37\r\nSQ5JUT;37\r\nSP5OLD;25\r\nSP5ABC;25\r\n'


@pytest.fixture
def processor_files(tmp_path, country_file, monkeypatch):
    monkeypatch.setattr(qslmaster_core, 'ensure_country_file', lambda log_callback=None: country_file)
    input_path = tmp_path / 'input.adi'
    input_path.write_text(INPUT_ADIF, encoding='utf-8')
    return input_path, tmp_path / 'output.adi'


def run_processor(config, output_path, **kwargs):
    logs = []
    processor = QSLProcessor(config, progress_callback=lambda message: None, log_callback=lambda level, message: logs.append((level, message)))
    with mock.patch('requests.get', return_value=FakeResponse(200, content=PZK_LIST)):
        result = processor.process(output_adif=str(output_path), **kwargs)
    return result, logs


def test_adif_file_processing_end_to_end(processor_files):
    input_path, output_path = processor_files
    config = {
        'source': 'adif_file',
        'adif_file_path': str(input_path),
        'ignored_dxcc': [230],
        'callsign_filter_mode': 'block',
        'callsign_filter_patterns': ['SQ5JUT'],
    }
    result, logs = run_processor(config, output_path, from_date='2026-11-01', to_date='2026-11-10', include_direct_when_no_bureau=True)

    assert result['success'], result.get('error')
    written = [(qso['CALL'], qso['QSL_SENT_VIA'], qso.get('QSL_VIA', '')) for qso in load_qsos_from_adif_file(str(output_path))]
    assert written == [('SP5ABB', 'B', 'OT-15'), ('HF0FURRY', 'B', 'OT-37'), ('SP5XXX', 'D', '')]
    stats = result['stats']
    assert stats['total_to_send'] == 3
    assert stats['callsign_filter']['skipped'] == 1
    assert stats['ignored_dxcc']['skipped'] == 1
    assert stats['already_sent']['skipped'] == 1
    assert stats['delivery_methods']['direct'] == 1
    assert stats['can_mark_as_sent'] is False
    assert any('QRZ API not available' in message for _, message in logs)


def test_invalid_date_fails_cleanly(processor_files):
    input_path, output_path = processor_files
    result, _ = run_processor({'source': 'adif_file', 'adif_file_path': str(input_path)}, output_path, from_date='01.11.2026')
    assert not result['success']
    assert 'Invalid date format' in result['error']
    assert not output_path.exists()


def test_missing_adif_file_fails_cleanly(processor_files, tmp_path):
    _, output_path = processor_files
    result, _ = run_processor({'source': 'adif_file', 'adif_file_path': str(tmp_path / 'missing.adi')}, output_path)
    assert not result['success']
    assert 'does not exist' in result['error']


def test_wavelog_download_passes_server_side_date_filter(processor_files):
    _, output_path = processor_files

    class FakeApi:
        api_version = 'v2'
        supports_date_filter = True

        def __init__(self):
            self.requests = []

        def get_version(self):
            return {'version': 'API v2 (3.1.0 or later)'}

        def get_station_info(self):
            return [{'station_id': '1', 'station_callsign': 'SQ5FOX', 'station_profile_name': 'Home', 'station_active': '1'}]

        def get_contacts_adif(self, station_ids=None, qso_since=None, qso_until=None):
            self.requests.append((station_ids, qso_since, qso_until))
            return INPUT_ADIF.split('<EOH>', 1)[1], 8

        def can_mark_as_sent(self):
            return True

    fake_api = FakeApi()
    with mock.patch.object(qslmaster_core, 'create_wavelog_api', return_value=fake_api):
        result, _ = run_processor(
            {'source': 'wavelog', 'wavelog_url': 'https://log.example', 'api_key': 'wl2_x'},
            output_path,
            from_date='2026-11-01',
            to_date='2026-11-02',
            station_selector=['1'],
        )
    assert result['success'], result.get('error')
    assert fake_api.requests == [(['1'], '2026-11-01', '2026-11-02')]
    assert result['stats']['can_mark_as_sent'] is True

    fake_api.requests.clear()
    with mock.patch.object(qslmaster_core, 'create_wavelog_api', return_value=fake_api):
        result, _ = run_processor(
            {'source': 'wavelog', 'wavelog_url': 'https://log.example', 'api_key': 'wl2_x'},
            output_path,
            station_selector=['all'],
        )
    assert result['success'], result.get('error')
    assert fake_api.requests == [(['1'], None, None)]


class FakeMarkSentApi:
    api_version = 'v2'
    supports_date_filter = True

    def __init__(self):
        self.updates = []

    def get_version(self):
        return {'version': 'API v2 (3.1.0 or later)', 'owner': 'SQ5FOX', 'scopes': ['qso:read', 'station:read', 'qso:write']}

    def get_station_info(self):
        return [{'station_id': '1', 'station_callsign': 'SQ5FOX', 'station_profile_name': 'Home', 'station_active': '1'}]

    def can_mark_as_sent(self):
        return True

    def list_qsos(self, station_ids=None, qso_since=None, qso_until=None):
        return [
            {'id': 101, 'call': 'SP5ABB', 'qso_date': '2026-11-01 12:10:00', 'band': '40m', 'mode': 'CW'},
            {'id': 102, 'call': 'HF0FURRY', 'qso_date': '2026-11-02 12:20:00', 'band': '40m', 'mode': 'CW'},
        ]

    def update_qso(self, qso_id, fields):
        self.updates.append((qso_id, fields))


def test_processing_output_can_be_marked_as_sent(processor_files):
    input_path, output_path = processor_files
    result, _ = run_processor({'source': 'adif_file', 'adif_file_path': str(input_path)}, output_path, from_date='2026-11-01', to_date='2026-11-02')
    assert result['success'], result.get('error')

    fake_api = FakeMarkSentApi()
    processor = QSLProcessor({'source': 'wavelog', 'wavelog_url': 'https://log.example', 'api_key': 'wl2_x'}, progress_callback=lambda message: None, log_callback=lambda level, message: None)
    with mock.patch.object(qslmaster_core, 'create_wavelog_api', return_value=fake_api):
        plan = processor.plan_mark_as_sent_from_adif(str(output_path))
        mark_result = processor.apply_mark_as_sent(plan)
    assert mark_result.updated == 2
    assert [qso_id for qso_id, _ in fake_api.updates] == [101, 102]
    assert fake_api.updates[0][1]['qsl_via'] == 'OT-15'
    assert [qso['CALL'] for qso in plan.not_found] == ['SQ5JUT']


def test_wavelog_connection_error_is_reported_with_details(processor_files):
    _, output_path = processor_files
    from qslmaster_cli.wavelog import WavelogAPIError
    with mock.patch.object(qslmaster_core, 'create_wavelog_api', side_effect=WavelogAPIError('Connection error: refused')):
        result, _ = run_processor({'source': 'wavelog', 'wavelog_url': 'https://log.example', 'api_key': 'wl2_x'}, output_path)
    assert not result['success']
    assert result['error'] == 'Wavelog API health check failed: Connection error: refused'
    assert result['permission_error'] is False
