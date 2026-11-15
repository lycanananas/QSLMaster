import os

import pytest

pytest.importorskip('PyQt6.QtWidgets')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from qslmaster_cli.mark_sent import MarkSentMatch, MarkSentPlan


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_mark_sent_dialog_lists_matches(app):
    from qslmaster_gui.dialogs.mark_sent_dialog import MarkSentDialog, describe_match_fields
    plan = MarkSentPlan(
        matched=[MarkSentMatch(qso={'CALL': 'SP5ABC', 'QSO_DATE': '20261101', 'TIME_ON': '1210', 'BAND': '40m'}, wavelog_id=1, fields={'qsl_sent': 'Y', 'qsl_sent_via': 'B', 'qsl_via': 'OT-25'})],
        not_found=[{'CALL': 'DL1AA'}],
    )
    dialog = MarkSentDialog(plan, '/tmp/out.adi')
    assert dialog.get_sent_date() is not None
    assert describe_match_fields(plan.matched[0].fields) == 'bureau, via OT-25'


def test_processing_tab_without_wavelog_config_disables_wavelog_actions(app):
    from qslmaster_gui.widgets.processing_tab import ProcessingTab
    tab = ProcessingTab()
    tab.set_config({'source': 'adif_file'})
    assert not tab.mark_sent_button.isEnabled()
    assert not tab.refresh_station_btn.isEnabled()
    assert tab.station_list.item(1).text() == 'Available only for Wavelog'
    tab.shutdown()


def test_api_key_test_summary_escapes_values(app):
    from qslmaster_gui.dialogs.config_dialog import build_api_key_test_summary
    summary = build_api_key_test_summary({'api': 'v2', 'owner': '<script>', 'scopes': ['a&b'], 'stations': 1})
    assert '<script>' not in summary
    assert '&lt;script&gt;' in summary and 'a&amp;b' in summary


def test_api_key_test_summary_lists_feature_availability(app):
    from qslmaster_gui.dialogs.config_dialog import build_api_key_test_summary
    v2_read_only = build_api_key_test_summary({'api': 'v2', 'owner': 'SQ5FOX', 'scopes': ['qso:read', 'station:read'], 'stations': 12, 'can_mark_as_sent': False})
    assert 'date filter</td><td style=\'white-space:nowrap;\'><span style=\'color:#2ea043' in v2_read_only
    assert 'not available</span> <span style=\'color:gray;\'>(add the qso:write scope)' in v2_read_only
    assert 'Wavelog version' not in v2_read_only

    v2_write = build_api_key_test_summary({'api': 'v2', 'owner': 'SQ5FOX', 'scopes': ['qso:read', 'station:read', 'qso:write'], 'stations': 12, 'can_mark_as_sent': True})
    assert v2_write.count('>available</span>') == 4

    v1 = build_api_key_test_summary({'api': 'v1', 'version': '2.1.2', 'stations': 3, 'can_mark_as_sent': False})
    assert '<b>v1</b> (legacy)' in v1
    assert v1.count('(requires an API v2 token)') == 2


def test_mark_sent_button_has_no_tooltip_or_ellipsis(app):
    from qslmaster_gui.widgets.processing_tab import ProcessingTab
    tab = ProcessingTab()
    assert tab.mark_sent_button.text() == 'Mark as Sent in Wavelog'
    assert tab.mark_sent_button.toolTip() == ''
    tab.shutdown()
