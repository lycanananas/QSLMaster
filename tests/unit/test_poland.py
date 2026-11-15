from unittest import mock

import requests

from conftest import FakeResponse
from qslmaster_cli import poland
from qslmaster_cli.poland import _lookup_pzk_ot, _parse_pzk_qsl_list, process_qsos_poland

PZK_SAMPLE = (
    b'WYKAZ QSL [2026-11-15 / 16:14:01]\r\n'
    b'SP3AEZ,SP6AEZ;01\r\n'
    b'SP4UEF,SP8UEF.;21\r\n'
    b'SN0S;06\r\n'
    b'SN0S;73\r\n'
    b'ZL/SP5EAQ;25\r\n'
    b'SP5ABB;15\r\n'
    b'HF0FURRY;37\r\n'
    b'\r\n'
    b'broken line without separator\r\n'
)


def test_parser_handles_multi_call_lines_dots_and_duplicates():
    qsl_list = _parse_pzk_qsl_list(PZK_SAMPLE)
    assert qsl_list['SP3AEZ'] == '01'
    assert qsl_list['SP6AEZ'] == '01'
    assert qsl_list['SP8UEF'] == '21'
    assert qsl_list['SN0S'] == '06'
    assert 'WYKAZ QSL [2026-11-15 / 16:14:01]' not in qsl_list


def test_lookup_prefers_full_call_then_homecall():
    qsl_list = _parse_pzk_qsl_list(PZK_SAMPLE)
    assert _lookup_pzk_ot(qsl_list, 'ZL/SP5EAQ') == '25'
    assert _lookup_pzk_ot(qsl_list, 'sp5abb/p') == '15'
    assert _lookup_pzk_ot(qsl_list, 'SP5XXX') is None


def run_poland(include_direct=False):
    qsos = [
        {'CALL': 'SP5ABB', 'QSO_DATE': '20261101'},
        {'CALL': 'SP5ABB', 'QSO_DATE': '20261102'},
        {'CALL': 'HF0FURRY'},
        {'CALL': 'SP5XXX'},
    ]
    logs = []
    progress = []
    results, total = process_qsos_poland(
        qsos,
        include_direct_when_no_bureau=include_direct,
        log_callback=lambda level, message: logs.append((level, message)),
        progress_callback=lambda current, total_qsos: progress.append((current, total_qsos)),
    )
    return results, total, logs, progress


def test_process_marks_members_as_bureau_via_ot():
    with mock.patch('requests.get', return_value=FakeResponse(200, content=PZK_SAMPLE)):
        results, total, _, progress = run_poland()
    assert total == 4
    assert [(qso['CALL'], qso['QSL_SENT_VIA'], qso['QSL_VIA']) for qso in results] == [
        ('SP5ABB', 'B', 'OT-15'),
        ('SP5ABB', 'B', 'OT-15'),
        ('HF0FURRY', 'B', 'OT-37'),
    ]
    assert progress[-1] == (4, 4)


def test_process_adds_non_members_as_direct_when_enabled():
    with mock.patch('requests.get', return_value=FakeResponse(200, content=PZK_SAMPLE)):
        results, _, _, _ = run_poland(include_direct=True)
    assert ('SP5XXX', 'D', '') in [(qso['CALL'], qso['QSL_SENT_VIA'], qso['QSL_VIA']) for qso in results]


def test_download_failure_uses_cached_list():
    with mock.patch('requests.get', return_value=FakeResponse(200, content=PZK_SAMPLE)):
        run_poland()
    cache_file, _ = poland.get_pzk_cache_paths()
    assert cache_file.exists()

    with mock.patch('requests.get', side_effect=requests.exceptions.ConnectionError('PZK is down')):
        results, _, logs, _ = run_poland()
    assert len(results) == 3
    assert any('using cached copy' in message for _, message in logs)


def test_download_failure_without_cache_reports_lookup_error():
    with mock.patch('requests.get', return_value=FakeResponse(503)):
        results, _, logs, progress = run_poland(include_direct=True)
    assert results == []
    assert any('PZK result: QSL list lookup error' in message for _, message in logs)
    assert any('ignoring PZK lookups for remaining callsigns' in message for _, message in logs)
    assert progress[-1] == (4, 4)
