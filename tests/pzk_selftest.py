import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from qslmaster_cli.callsign_utils import extract_homecall
from qslmaster_cli.poland import _fetch_pzk_qsl_list, _lookup_pzk_ot, _parse_pzk_qsl_list


DEFAULT_CALLSIGNS = [
    'sq5jut', 'sp7ivo', 'sp5epd', 'sp5rzw', 'sp8jus', 'sp5cuk', 'sp6ixu', 'sq8ep',
    'sp3mep', 'sq6slm', 'sp2wdx', 'sp5ddf', 'sp2ovq', 'sp5cwc', 'sp5qia', 'sp3cw',
    'sp5sky', 'sp9bp', 'sp5cib', 'sp3hgd', 'sq4fxy', 'sq9mlz', 'sp2ok', 'sq2mb',
    'sp1pt', 'sp1wws', 'sp2kmo', 'sp5eig', 'sq7pfu', 'sp3okj', 'sp7mjx', 'sp2mio',
    'sp8hpc', 'sp5iyd', 'sp8heb', 'sp4gk', 'sp5tze', 'sp1zs', 'sp9wls', 'sq8ray',
    'sq6pod', 'sq0cf', 'sq7c', 'sq9ccw', 'sq8kos', 'sq0vmp', 'sq4hl', 'sp0k', 'sq0m',
    'sp4ozu', 'sq4bc', 'sq9bb', 'sq4f', 'sp5go', 'sq4ufz', 'sp5o', 'sp8g', 'sq2b',
    'sp5lls', 'sq5tla', 'sq5fox', 'sp0fur', 'n0call',
]

PARSER_SAMPLE = (
    b'WYKAZ QSL [2026-11-15 / 16:14:01]\r\n'
    b'SP3AEZ,SP6AEZ;01\r\n'
    b'SP4UEF,SP8UEF.;21\r\n'
    b'SN0S;06\r\n'
    b'SN0S;73\r\n'
    b'ZL/SP5EAQ;25\r\n'
    b'SP5ABB;15\r\n'
    b'\r\n'
)

PARSER_CASES = [
    ('SP3AEZ', '01'),
    ('SP6AEZ', '01'),
    ('SP8UEF', '21'),
    ('SN0S', '06'),
    ('ZL/SP5EAQ', '25'),
    ('SP5ABB/P', '15'),
    ('SP5ABB/9', '15'),
    ('SP5XXX', None),
]


def _run_parser_selftest() -> int:
    qsl_list = _parse_pzk_qsl_list(PARSER_SAMPLE)
    fail = 0
    for call, expected in PARSER_CASES:
        actual = _lookup_pzk_ot(qsl_list, call)
        if actual == expected:
            print(f'✓ parser {call:12} ot={actual!r}')
        else:
            print(f'✗ parser {call:12} ot={actual!r} expected={expected!r}')
            fail += 1
    return fail


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='PZK QSL list lookup self-test')
    parser.add_argument('callsigns', nargs='*', help='Optional callsigns to test (overrides default list)')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    callsigns = args.callsigns if args.callsigns else list(DEFAULT_CALLSIGNS)

    ok = 0
    fail = _run_parser_selftest()

    t0 = time.perf_counter()
    try:
        qsl_list = _fetch_pzk_qsl_list()
    except Exception as e:
        print(f'✗ download error={type(e).__name__}: {e}')
        print(f'\nSummary: ok={ok} fail={fail + 1}')
        return 1
    print(f'✓ download {len(qsl_list)} callsigns ({(time.perf_counter() - t0) * 1000:.0f}ms)')

    for raw_call in callsigns:
        fullcall = str(raw_call).strip()
        if not fullcall:
            continue
        homecall = extract_homecall(fullcall)
        ot = _lookup_pzk_ot(qsl_list, fullcall)
        print(f'✓ {fullcall.upper():12} homecall={homecall:10} member={ot is not None!s:<5} ot={ot or ""!r}')
        ok += 1

    print(f'\nSummary: ok={ok} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())