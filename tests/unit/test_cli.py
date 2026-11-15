import json
import sys
from unittest import mock

import pytest

from qslmaster_cli import main as cli


def run_cli(args, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['qslmaster-cli'] + args)
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    return exit_info.value.code


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'source': 'adif_file', 'adif_file_path': '', 'wavelog_url': 'https://log.example', 'api_key': 'wl2_x'}), encoding='utf-8')
    return str(path)


@pytest.mark.parametrize('args', [
    ['--mark-sent', 'out.adi', '-o', 'x.adi'],
    ['--dry-run', '-o', 'x.adi'],
    ['--mark-sent', 'out.adi', '--sent-date', '20.11.2026'],
    [],
])
def test_invalid_argument_combinations(args, config_path, monkeypatch, capsys):
    assert run_cli(['-c', config_path] + args, monkeypatch) == 2


def test_mark_sent_forces_wavelog_source_and_uses_dry_run(config_path, monkeypatch):
    calls = []

    def fake_run_mark_sent(processor, adif_path, sent_date, dry_run, logger):
        calls.append((processor.config['source'], adif_path, sent_date, dry_run))
        return 0

    monkeypatch.setattr(cli, 'run_mark_sent', fake_run_mark_sent)
    assert run_cli(['-c', config_path, '--mark-sent', 'out.adi', '--dry-run', '--sent-date', '2026-11-20'], monkeypatch) == 0
    assert calls == [('wavelog', 'out.adi', __import__('datetime').date(2026, 11, 20), True)]


def test_run_mark_sent_exit_codes():
    from qslmaster_cli.mark_sent import MarkSentMatch, MarkSentPlan, MarkSentResult
    from qslmaster_cli.adif_files import ADIFFileError
    logger = mock.Mock()
    processor = mock.Mock()
    processor.plan_mark_as_sent_from_adif.return_value = MarkSentPlan(matched=[MarkSentMatch({}, 1, {})])
    processor.apply_mark_as_sent.return_value = MarkSentResult(updated=1)
    assert cli.run_mark_sent(processor, 'out.adi', None, False, logger) == 0
    assert cli.run_mark_sent(processor, 'out.adi', None, True, logger) == 0
    assert processor.apply_mark_as_sent.call_count == 1

    processor.plan_mark_as_sent_from_adif.return_value = MarkSentPlan()
    assert cli.run_mark_sent(processor, 'out.adi', None, False, logger) == 1

    processor.plan_mark_as_sent_from_adif.side_effect = ADIFFileError('not a QSLMaster output file')
    assert cli.run_mark_sent(processor, 'out.adi', None, False, logger) == 1
