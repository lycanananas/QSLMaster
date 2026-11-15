import pytest

from qslmaster_cli.config import normalize_callsign_filter_mode
from qslmaster_cli.qso_filters import (
    count_skipped, filter_qsos_by_callsign_patterns, filter_qsos_by_date_range,
    filter_qsos_by_ignored_dxcc, filter_qsos_by_mode, filter_qsos_by_sent_status,
    normalize_callsign_filter_patterns,
    normalize_callsign_filter_target, normalize_ignored_dxcc, parse_date_arg,
)

DXCC_BY_HOMECALL = {
    'UA1AAA': 54,
    'UA9BBB': 15,
    'R3ZZZ': 54,
    'R9WWW': 15,
    'SP5FOX': 269,
    'K1ABC': 291,
    '3D2AG': 176,
}


def resolve_adif_id(homecall):
    return DXCC_BY_HOMECALL[homecall]


def calls(qsos):
    return [qso.get('CALL') for qso in qsos]


def test_callsign_allowlist_matches_homecall():
    qsos = [{'CALL': call} for call in ['HB/SQ5AM/P', 'LZ/SQ5AM', 'SQ5AM/P', 'SQ5AM', 'SQ5AMQ', 'DL/SQ5FOX/P']]
    filtered, skipped = filter_qsos_by_callsign_patterns(qsos, 'allow', ['SQ5AM'])
    assert calls(filtered) == ['HB/SQ5AM/P', 'LZ/SQ5AM', 'SQ5AM/P', 'SQ5AM']
    assert count_skipped(skipped) == {'<not-listed>': 2}


def test_callsign_blocklist_matches_homecall():
    qsos = [{'CALL': call} for call in ['HB/SQ5AM/P', 'LZ/SQ5AM', 'SQ5AM/P', 'SQ5AM', 'SQ5AMQ', 'SP5XYZ']]
    filtered, skipped = filter_qsos_by_callsign_patterns(qsos, 'block', ['SQ5AM'])
    assert calls(filtered) == ['SQ5AMQ', 'SP5XYZ']
    assert count_skipped(skipped) == {'SQ5AM': 4}


def test_callsign_filter_off_keeps_everything():
    qsos = [{'CALL': 'SP5ABC'}]
    assert filter_qsos_by_callsign_patterns(qsos, 'off', ['SP5ABC']) == (qsos, [])


@pytest.mark.parametrize('value, expected', [
    ('whitelist', 'allow'),
    ('BLOCKLIST', 'block'),
    ('none', 'off'),
    ('garbage', 'off'),
    (None, 'off'),
])
def test_normalize_callsign_filter_mode(value, expected):
    assert normalize_callsign_filter_mode(value) == expected


def test_normalize_callsign_filter_patterns_and_target():
    assert normalize_callsign_filter_patterns([' sp3abc ', 'SP3ABC', '', None, '3z3z3z']) == ['SP3ABC', '3Z3Z3Z']
    assert normalize_callsign_filter_target('HB/SQ5AM/P') == 'SQ5AM'


def test_ignored_dxcc_skips_matching_entities_and_keeps_unknown():
    qsos = [{'CALL': call} for call in ['UA1AAA', 'UA9BBB', 'R3ZZZ', 'R9WWW', 'SP5FOX', 'K1ABC', '3D2AG/P', 'UNKNOWN1', '']] + [{}]
    filtered, skipped = filter_qsos_by_ignored_dxcc(qsos, normalize_ignored_dxcc([15, '54', ' 15 ', 'invalid']), resolve_adif_id)
    assert calls(filtered) == ['SP5FOX', 'K1ABC', '3D2AG/P', 'UNKNOWN1', '', None]
    assert count_skipped(skipped) == {15: 2, 54: 2}


def test_normalize_ignored_dxcc():
    assert normalize_ignored_dxcc([15, '54', ' 15 ', 'invalid', 0, -3, None]) == {15, 54}
    assert normalize_ignored_dxcc(None) == set()


def test_date_range_is_inclusive_and_skips_invalid_dates():
    qsos = [
        {'CALL': 'A', 'QSO_DATE': '20261031', 'TIME_ON': '235959'},
        {'CALL': 'B', 'QSO_DATE': '20261101', 'TIME_ON': '000000'},
        {'CALL': 'C', 'QSO_DATE': '20261102', 'TIME_ON': '235959'},
        {'CALL': 'D', 'QSO_DATE': '20261103', 'TIME_ON': '000000'},
        {'CALL': 'E', 'QSO_DATE': 'bad', 'TIME_ON': '000000'},
        {'CALL': 'F'},
    ]
    assert calls(filter_qsos_by_date_range(qsos, '2026-11-01', '2026-11-02')) == ['B', 'C']
    assert calls(filter_qsos_by_date_range(qsos, None, '2026-10-31')) == ['A']


def test_parse_date_arg_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_date_arg('15.11.2026')


def test_mode_filter_handles_ssb_and_digi_groups():
    qsos = [
        {'CALL': 'A', 'MODE': 'SSB', 'SUBMODE': 'USB'},
        {'CALL': 'B', 'MODE': 'CW'},
        {'CALL': 'C', 'MODE': 'MFSK', 'SUBMODE': 'FT4'},
        {'CALL': 'D', 'MODE': 'FT8'},
        {'CALL': 'E', 'MODE': 'PSK', 'SUBMODE': 'PSK31'},
    ]
    assert calls(filter_qsos_by_mode(qsos, 'SSB')) == ['A']
    assert calls(filter_qsos_by_mode(qsos, 'DIGI')) == ['C', 'E']
    assert calls(filter_qsos_by_mode(qsos, 'cw, ft8')) == ['B', 'D']
    assert filter_qsos_by_mode(qsos, None) is qsos


def test_sent_status_filter():
    qsos = [{'CALL': 'A', 'QSL_SENT': 'Y'}, {'CALL': 'B', 'QSL_SENT': 'N'}, {'CALL': 'C'}]
    filtered, skipped = filter_qsos_by_sent_status(qsos)
    assert calls(filtered) == ['B', 'C']
    assert calls(skipped) == ['A']
