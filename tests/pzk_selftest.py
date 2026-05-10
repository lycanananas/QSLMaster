import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from qslmaster_cli.callsign_utils import extract_homecall
from qslmaster_cli.poland import _fetch_pzk_member_info


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


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='PZK member lookup self-test')
    parser.add_argument('callsigns', nargs='*', help='Optional callsigns to test (overrides default list)')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    callsigns = args.callsigns if args.callsigns else list(DEFAULT_CALLSIGNS)

    ok = 0
    fail = 0
    for raw_call in callsigns:
        t0 = time.perf_counter()
        fullcall = str(raw_call).strip()
        if not fullcall:
            continue
        homecall = extract_homecall(fullcall)
        try:
            info = _fetch_pzk_member_info(homecall)
            dt_ms = (time.perf_counter() - t0) * 1000
            if not info:
                print(f'✓ {fullcall.upper():12} homecall={homecall:10} member=False ({dt_ms:.0f}ms)')
                ok += 1
                continue
            status_text, ot_text = info
            is_member = 'Jest' in (status_text or '')
            ot_first = (ot_text or '').strip().split()[0] if (ot_text or '').strip() else ''
            print(f'✓ {fullcall.upper():12} homecall={homecall:10} member={is_member!s:<5} ot={ot_first!r} ({dt_ms:.0f}ms)')
            ok += 1
        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000
            print(f'✗ {fullcall.upper():12} homecall={homecall:10} error={type(e).__name__}: {e} ({dt_ms:.0f}ms)')
            fail += 1

    print(f'\nSummary: ok={ok} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())