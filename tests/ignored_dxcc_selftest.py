import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from qslmaster_cli.qslmaster_core import QSLProcessor


class FakeCallinfo:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_adif_id(self, homecall):
        return int(self.mapping.get(homecall, 0))


def run_case(label, processor, qsos, expected_skipped_total, expected_breakdown, expected_remaining_calls):
    t0 = time.perf_counter()
    filtered, skipped_total, skipped_by_dxcc = processor.filter_qsos_by_ignored_dxcc(qsos)
    dt_ms = (time.perf_counter() - t0) * 1000

    ok = 0
    fail = 0

    result_calls = [qso.get('CALL') if isinstance(qso, dict) else None for qso in filtered]

    if skipped_total == expected_skipped_total:
        print(f'✓ {label} skipped_total={skipped_total} ({dt_ms:.2f}ms)')
        ok += 1
    else:
        print(f'✗ {label} skipped_total={skipped_total} expected={expected_skipped_total} ({dt_ms:.2f}ms)')
        fail += 1

    if skipped_by_dxcc == expected_breakdown:
        print(f'✓ {label} skipped_by_dxcc={skipped_by_dxcc}')
        ok += 1
    else:
        print(f'✗ {label} skipped_by_dxcc={skipped_by_dxcc} expected={expected_breakdown}')
        fail += 1

    if result_calls == expected_remaining_calls:
        print(f'✓ {label} remaining_calls={result_calls}')
        ok += 1
    else:
        print(f'✗ {label} remaining_calls={result_calls} expected={expected_remaining_calls}')
        fail += 1

    return ok, fail


def main() -> int:
    config = {
        'api_key': 'dummy',
        'wavelog_url': 'https://example.test',
        'qrz_username': '',
        'qrz_password': '',
        'ignored_dxcc': [15, '54', ' 15 ', 'invalid'],
    }

    processor = QSLProcessor(config)
    processor.callinfo = FakeCallinfo({
        'UA1AAA': 54,
        'UA9BBB': 15,
        'R3ZZZ': 54,
        'R9WWW': 15,
        'SP5FOX': 269,
        'SQ9P': 269,
        'K1ABC': 291,
        'W6OP': 291,
        'DL1AAA': 230,
        'F4ABC': 227,
        'G3XYZ': 223,
        'JA1NUT': 339,
        'VK2AAA': 150,
        'ZS6TEST': 462,
        'PY2ZZ': 108,
        'LU1ABC': 100,
        'YO2ZZ': 275,
        'YB1HR': 327,
        '3D2AG': 176,
        'FR8XYZ': 453,
    })
    processor.dxcc_name_map = {
        15: 'Asiatic Russia',
        54: 'European Russia',
        269: 'Poland',
        291: 'United States',
        230: 'Germany',
        227: 'France',
        223: 'England',
        339: 'Japan',
        150: 'Australia',
        462: 'South Africa',
        108: 'Brazil',
        100: 'Argentina',
        275: 'Romania',
        327: 'Indonesia',
        176: 'Fiji',
        453: 'Reunion Island',
    }

    qsos = [
        {'CALL': 'UA1AAA'},
        {'CALL': 'UA9BBB'},
        {'CALL': 'R3ZZZ'},
        {'CALL': 'R9WWW'},
        {'CALL': 'SP5FOX'},
        {'CALL': 'SQ9P'},
        {'CALL': 'K1ABC'},
        {'CALL': 'W6OP'},
        {'CALL': 'DL1AAA'},
        {'CALL': 'F4ABC'},
        {'CALL': 'G3XYZ'},
        {'CALL': 'JA1NUT'},
        {'CALL': 'VK2AAA'},
        {'CALL': 'ZS6TEST'},
        {'CALL': 'PY2ZZ'},
        {'CALL': 'LU1ABC'},
        {'CALL': 'YO2ZZ'},
        {'CALL': 'YB1HR'},
        {'CALL': '3D2AG/P'},
        {'CALL': 'FR8XYZ'},
        {'CALL': 'UNKNOWN1'},
        {'CALL': ''},
        {},
    ]

    ok = 0
    fail = 0

    expected_calls_case_1 = [
        'SP5FOX', 'SQ9P', 'K1ABC', 'W6OP', 'DL1AAA', 'F4ABC', 'G3XYZ',
        'JA1NUT', 'VK2AAA', 'ZS6TEST', 'PY2ZZ', 'LU1ABC', 'YO2ZZ', 'YB1HR',
        '3D2AG/P', 'FR8XYZ', 'UNKNOWN1', '', None,
    ]
    expected_breakdown_case_1 = {15: 2, 54: 2}
    case_ok, case_fail = run_case(
        label='case_ignore_russia',
        processor=processor,
        qsos=qsos,
        expected_skipped_total=4,
        expected_breakdown=expected_breakdown_case_1,
        expected_remaining_calls=expected_calls_case_1,
    )
    ok += case_ok
    fail += case_fail

    normalized = processor.get_ignored_dxcc_set()
    if normalized == {15, 54}:
        print(f'✓ normalized_ignored_dxcc={sorted(normalized)}')
        ok += 1
    else:
        print(f'✗ normalized_ignored_dxcc={sorted(normalized)} expected=[15, 54]')
        fail += 1

    processor.config['ignored_dxcc'] = []
    expected_calls_case_2 = [
        'UA1AAA', 'UA9BBB', 'R3ZZZ', 'R9WWW', 'SP5FOX', 'SQ9P', 'K1ABC', 'W6OP',
        'DL1AAA', 'F4ABC', 'G3XYZ', 'JA1NUT', 'VK2AAA', 'ZS6TEST', 'PY2ZZ',
        'LU1ABC', 'YO2ZZ', 'YB1HR', '3D2AG/P', 'FR8XYZ', 'UNKNOWN1', '', None,
    ]
    case_ok, case_fail = run_case(
        label='case_no_ignored_dxcc',
        processor=processor,
        qsos=qsos,
        expected_skipped_total=0,
        expected_breakdown={},
        expected_remaining_calls=expected_calls_case_2,
    )
    ok += case_ok
    fail += case_fail

    print(f'\nSummary: ok={ok} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())