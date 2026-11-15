import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from qslmaster_cli import pdf_labels
from qslmaster_cli.pdf_labels import draw_label, generate_pdf_labels, get_from_callsign, get_label_via

BASE_QSO = {'CALL': 'DL1ABC', 'QSO_DATE': '20261115', 'TIME_ON': '1432', 'RST_SENT': '59', 'MODE': 'SSB', 'BAND': '20m'}


def record_label(qso):
    c = canvas.Canvas('/dev/null', pagesize=A4)
    drawn = []
    original = c.drawString

    def recorder(x, y, text, *args, **kwargs):
        drawn.append((text, y))
        return original(x, y, text, *args, **kwargs)

    c.drawString = recorder
    draw_label(c, qso, 0, A4[1], 70 * mm, 25.4 * mm, logo_path='missing-logo.png')
    return dict(drawn)


def test_from_callsign_is_normalized_station_callsign():
    assert get_from_callsign({'STATION_CALLSIGN': 'lz/sq5fox '}) == 'LZ/SQ5FOX'
    assert get_from_callsign({'STATION_CALLSIGN': ''}) == ''
    assert get_from_callsign({}) == ''


def test_label_via_falls_back_to_sent_via():
    assert get_label_via({'QSL_VIA': ' M0OXO ', 'QSL_SENT_VIA': 'B'}) == 'M0OXO'
    assert get_label_via({'QSL_SENT_VIA': 'b'}) == 'BUREAU'
    assert get_label_via({'QSL_SENT_VIA': 'D'}) == 'DIRECT'
    assert get_label_via({}) == ''


def test_label_without_station_callsign_keeps_default_layout():
    drawn = record_label({**BASE_QSO, 'QSL_SENT_VIA': 'B'})
    assert 'From:' not in drawn
    assert drawn['Via:'] - drawn['Date:'] == pytest.approx(pdf_labels.SPACING_AFTER_VIA + pdf_labels.TOTAL_SEPARATOR_SPACE)
    assert drawn['Date:'] - drawn['Time:'] == pytest.approx(pdf_labels.SPACING_BETWEEN_FIELDS)


def test_label_with_via_puts_from_between_via_and_date():
    drawn = record_label({**BASE_QSO, 'QSL_SENT_VIA': 'B', 'STATION_CALLSIGN': 'LZ/SQ5FOX'})
    assert drawn['LZ/SQ5FOX'] == drawn['From:']
    assert drawn['Via:'] > drawn['From:'] > drawn['Date:']
    assert drawn['Date:'] - drawn['Time:'] == pytest.approx(pdf_labels.SPACING_BETWEEN_FIELDS_WITH_FROM)


def test_label_without_via_puts_from_in_via_row():
    with_from = record_label({**BASE_QSO, 'STATION_CALLSIGN': 'OK/SQ5FOX'})
    reference = record_label({**BASE_QSO, 'QSL_SENT_VIA': 'B'})
    assert with_from['From:'] == reference['Via:']
    assert with_from['Date:'] == reference['Date:']


def test_generated_band_row_stays_inside_label():
    drawn = record_label({**BASE_QSO, 'QSL_VIA': 'M0OXO', 'STATION_CALLSIGN': 'VP2V/SQ5FOX'})
    label_bottom = A4[1] - 25.4 * mm
    assert drawn['Band:'] - label_bottom >= 1 * mm


def test_generate_pdf_labels_with_station_callsign(tmp_path):
    output = tmp_path / 'labels.pdf'
    generate_pdf_labels([{**BASE_QSO, 'STATION_CALLSIGN': 'LZ/SQ5FOX'}], str(output), logo_path='missing-logo.png')
    assert output.read_bytes().startswith(b'%PDF')


def test_home_station_callsign_is_printed_too():
    drawn = record_label({**BASE_QSO, 'QSL_SENT_VIA': 'B', 'STATION_CALLSIGN': 'SQ5FOX'})
    assert drawn['SQ5FOX'] == drawn['From:']
