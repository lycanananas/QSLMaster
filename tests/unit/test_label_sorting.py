from qslmaster_cli.label_sorting import sort_qsos_for_labels
from qslmaster_cli.qso_utils import count_qsos_by_delivery_method, format_qso_datetime, format_qso_log_label, mark_qsos_to_send

COUNTRY_BY_HOMECALL = {
    'SP5ABC': 'Poland',
    'SQ9XYZ': 'Poland',
    'SP3AAA': 'Poland',
    'DL1AA': 'Fed. Rep. of Germany',
    'F4ABC': 'France',
    'K1ABC': 'United States',
}


def resolve_country_name(homecall):
    return COUNTRY_BY_HOMECALL[homecall]


def test_labels_sorted_by_delivery_country_via_and_homecall():
    qsos = [
        {'CALL': 'K1ABC', 'QSL_SENT_VIA': 'D'},
        {'CALL': 'SP5ABC', 'QSL_SENT_VIA': 'B', 'QSL_VIA': 'OT-25'},
        {'CALL': 'F4ABC', 'QSL_SENT_VIA': 'B'},
        {'CALL': 'SQ9XYZ', 'QSL_SENT_VIA': 'B', 'QSL_VIA': 'OT-09'},
        {'CALL': 'SP3AAA', 'QSL_SENT_VIA': 'B'},
        {'CALL': 'XX1UNKNOWN', 'QSL_SENT_VIA': 'B'},
        {'CALL': 'DL/SP5ABC/P', 'QSL_SENT_VIA': 'B', 'QSL_VIA': 'OT-25'},
        {'CALL': 'DL1AA', 'QSL_SENT_VIA': 'B'},
    ]
    sorted_calls = [qso['CALL'] for qso in sort_qsos_for_labels(qsos, resolve_country_name)]
    assert sorted_calls == ['DL1AA', 'F4ABC', 'SQ9XYZ', 'DL/SP5ABC/P', 'SP5ABC', 'SP3AAA', 'XX1UNKNOWN', 'K1ABC']


def test_format_helpers():
    qso = {'CALL': 'sp5abc', 'QSO_DATE': '20261101', 'TIME_ON': '1210'}
    assert format_qso_datetime(qso) == '2026-11-01 12:10:00'
    assert format_qso_log_label(qso) == 'SP5ABC on 2026-11-01 12:10:00'
    assert format_qso_datetime({}) == 'unknown-date unknown-time'


def test_mark_qsos_to_send_copies_and_counts():
    original = [{'CALL': 'SP5ABC'}, {'CALL': 'DL1AA'}]
    bureau = mark_qsos_to_send(original[:1], 'B', 'OT-25')
    direct = mark_qsos_to_send(original[1:], 'D')
    assert original == [{'CALL': 'SP5ABC'}, {'CALL': 'DL1AA'}]
    assert bureau == [{'CALL': 'SP5ABC', 'QSL_SENT': 'Y', 'QSL_SENT_VIA': 'B', 'QSL_VIA': 'OT-25'}]
    assert count_qsos_by_delivery_method(bureau + direct) == {'bureau': 1, 'direct': 1}


def test_format_qso_datetime_accepts_hhmm_and_hhmmss():
    assert format_qso_datetime({'QSO_DATE': '20261101', 'TIME_ON': '121005'}) == '2026-11-01 12:10:05'
    assert format_qso_datetime({'QSO_DATE': '20261101', 'TIME_ON': '99'}) == '2026-11-01 99'
