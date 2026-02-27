import time

from .callsign_utils import extract_homecall


DEFAULT_TESTS = [
    ("SP5ABC", "SP5ABC"),
    ("SP/SP5ABC", "SP5ABC"),
    ("SP5ABC/W5", "SP5ABC"),
    ("DL/SQ5FOX/M/DL", "SQ5FOX"),
    ("3z3z3z", "3Z3Z3Z"),
    ("DL/3z3z3z", "3Z3Z3Z"),
    ("DL/3z3z3z/am/m/ok", "3Z3Z3Z"),
    ("N0CALL/P", "N0CALL"),
    ("W5/N0CALL", "N0CALL"),
    ("PJ4/SP0NULL/AM/QRP", "SP0NULL"),
]


def main() -> int:
    ok = 0
    fail = 0
    for input_call, expected in DEFAULT_TESTS:
        t0 = time.perf_counter()
        result = extract_homecall(input_call)
        dt_ms = (time.perf_counter() - t0) * 1000
        if result == expected:
            ok += 1
            status = "✓"
        else:
            fail += 1
            status = "✗"
        print(f"{status} {input_call:20} -> {result:10} (expected: {expected}) ({dt_ms:.2f}ms)")

    print(f"\nSummary: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
