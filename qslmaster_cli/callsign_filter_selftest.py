import time

from .qslmaster_core import QSLProcessor


def run_case(label, processor, qsos, expected_skipped_total, expected_breakdown, expected_remaining_calls):
    t0 = time.perf_counter()
    filtered, skipped_total, skipped_by_pattern = processor.filter_qsos_by_callsign_patterns(qsos)
    dt_ms = (time.perf_counter() - t0) * 1000

    ok = 0
    fail = 0

    result_calls = [qso.get('CALL') if isinstance(qso, dict) else None for qso in filtered]

    if skipped_total == expected_skipped_total:
        print(f"OK {label} skipped_total={skipped_total} ({dt_ms:.2f}ms)")
        ok += 1
    else:
        print(f"FAIL {label} skipped_total={skipped_total} expected={expected_skipped_total} ({dt_ms:.2f}ms)")
        fail += 1

    if skipped_by_pattern == expected_breakdown:
        print(f"OK {label} skipped_by_pattern={skipped_by_pattern}")
        ok += 1
    else:
        print(f"FAIL {label} skipped_by_pattern={skipped_by_pattern} expected={expected_breakdown}")
        fail += 1

    if result_calls == expected_remaining_calls:
        print(f"OK {label} remaining_calls={result_calls}")
        ok += 1
    else:
        print(f"FAIL {label} remaining_calls={result_calls} expected={expected_remaining_calls}")
        fail += 1

    return ok, fail


def main() -> int:
    ok = 0
    fail = 0

    allow_processor = QSLProcessor({
        'callsign_filter_mode': 'allow',
        'callsign_filter_patterns': ['SQ5AM'],
    })
    allow_qsos = [
        {'CALL': 'HB/SQ5AM/P'},
        {'CALL': 'LZ/SQ5AM'},
        {'CALL': 'SQ5AM/P'},
        {'CALL': 'SQ5AM'},
        {'CALL': 'SQ5AMQ'},
        {'CALL': 'DL/SQ5FOX/P'},
    ]
    case_ok, case_fail = run_case(
        label='allow_homecall_match',
        processor=allow_processor,
        qsos=allow_qsos,
        expected_skipped_total=2,
        expected_breakdown={'<not-listed>': 2},
        expected_remaining_calls=['HB/SQ5AM/P', 'LZ/SQ5AM', 'SQ5AM/P', 'SQ5AM'],
    )
    ok += case_ok
    fail += case_fail

    block_processor = QSLProcessor({
        'callsign_filter_mode': 'block',
        'callsign_filter_patterns': ['SQ5AM'],
    })
    block_qsos = [
        {'CALL': 'HB/SQ5AM/P'},
        {'CALL': 'LZ/SQ5AM'},
        {'CALL': 'SQ5AM/P'},
        {'CALL': 'SQ5AM'},
        {'CALL': 'SQ5AMQ'},
        {'CALL': 'SP5XYZ'},
    ]
    case_ok, case_fail = run_case(
        label='block_homecall_match',
        processor=block_processor,
        qsos=block_qsos,
        expected_skipped_total=4,
        expected_breakdown={'SQ5AM': 4},
        expected_remaining_calls=['SQ5AMQ', 'SP5XYZ'],
    )
    ok += case_ok
    fail += case_fail

    normalized_call = allow_processor.normalize_callsign_filter_target('HB/SQ5AM/P')
    if normalized_call == 'SQ5AM':
        print(f"OK normalized_call={normalized_call}")
        ok += 1
    else:
        print(f"FAIL normalized_call={normalized_call} expected=SQ5AM")
        fail += 1

    print(f"\nSummary: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())