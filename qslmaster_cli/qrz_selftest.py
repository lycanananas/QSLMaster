import argparse
import sys
import time
import re
from typing import List, Optional

import requests

from .config import load_config, validate_config, ConfigError
from .qrz import QRZAPI, QRZAPIError


REQUIRED_CALLSIGNS = [
    "sq5fox",
    "sp5pot",
    "w1aw",
    "k1n",
    "w5xo",
    "w0ai",
    "n4oo",
    "k6ller",
    "vk9ns",
    "zs6sn",
    "n1eoh",
    "iz0tsc",
    "ea4gcw",
    "pw2d",
    "cx9au",
    "vk5zd",
    "jt1co",
    "g3v",
    "yb1hr",
    "f4enk",
    "iu2sln",
    "ii2wog",
    "om2vl",
    "j51a",
    "k3lr",
    "w4an",
    "ea3gke/qrp",
    "wp4bri",
    "yo2kar",
    "g3zbu",
    "dr4w",
    "g4ari",
    "w4gm",
    "g0mfr",
    "w5rme",
    "g3rkf",
    "zw5b",
    "g2f",
    "5x1j",
    "vp5/n5zo",
    "vq9la",
    "oh2bn",
    "pi4cc",
    "k5nd",
    "oe6add",
    "k7ra",
    "df7gb",
    "n8ii",
    "ve1jf",
    "ve3on",
]


def _fetch_random_callsigns(count: int) -> List[str]:
    callsigns: List[str] = []
    seen = set()
    max_attempts = max(count * 10, 20)

    def _print_progress(found: int, attempt: int) -> None:
        print(
            f"\rℹ Fetching random callsigns from QRZ: {found}/{count} (attempt {attempt}/{max_attempts})",
            end="",
            flush=True,
        )

    _print_progress(0, 0)

    with requests.Session() as session:
        session.headers.update({"User-Agent": "QSLMaster/1.2"})
        for attempt in range(1, max_attempts + 1):
            if len(callsigns) >= count:
                break

            try:
                response = session.get("https://www.qrz.com/random-callsign", allow_redirects=False, timeout=10)
            except requests.exceptions.RequestException:
                if attempt == 1 or attempt % 5 == 0:
                    _print_progress(len(callsigns), attempt)
                time.sleep(0.2)
                continue

            if response.status_code not in (301, 302, 303, 307, 308):
                if attempt == 1 or attempt % 5 == 0:
                    _print_progress(len(callsigns), attempt)
                time.sleep(0.1)
                continue

            location = response.headers.get("Location", "")
            match = re.search(r"/db/([A-Z0-9/]+)$", location, flags=re.IGNORECASE)
            if not match:
                if attempt == 1 or attempt % 5 == 0:
                    _print_progress(len(callsigns), attempt)
                time.sleep(0.1)
                continue

            call = match.group(1).upper()
            if call in seen:
                if attempt == 1 or attempt % 5 == 0:
                    _print_progress(len(callsigns), attempt)
                continue

            seen.add(call)
            callsigns.append(call)
            _print_progress(len(callsigns), attempt)
            time.sleep(0.1)

    print()

    return callsigns


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QRZ bureau verification self-test")
    parser.add_argument("--config", required=True, help="Path to config.json with qrz_username/qrz_password")
    parser.add_argument(
        "--random",
        nargs="?",
        const=10,
        type=int,
        metavar="N",
        help="Add N random callsigns from qrz.com/random-callsign (default: 10)",
    )
    parser.add_argument("callsigns", nargs="*", help="Optional extra callsigns to test")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
        validate_config(config)
    except ConfigError as e:
        print(f"✗ Config error: {e}")
        return 2

    username = (config.get("qrz_username") or "").strip()
    password = (config.get("qrz_password") or "").strip()
    if not username or not password:
        print("✗ Missing QRZ credentials in config (qrz_username/qrz_password)")
        return 2

    callsigns = list(REQUIRED_CALLSIGNS)
    callsigns.extend(args.callsigns)

    if args.random is not None:
        if args.random <= 0:
            print("✗ --random must be a positive integer")
            return 2
        try:
            random_callsigns = _fetch_random_callsigns(args.random)
        except requests.exceptions.RequestException as e:
            print(f"⚠ Failed to fetch random callsigns from QRZ: {e}")
            random_callsigns = []

        if not random_callsigns:
            print("⚠ Continuing without random callsigns")

        if len(random_callsigns) < args.random:
            print(f"⚠ Fetched {len(random_callsigns)}/{args.random} random callsigns from QRZ")
        else:
            print(f"ℹ Fetched {len(random_callsigns)} random callsigns from QRZ")
        callsigns.extend(random_callsigns)

    deduped_callsigns: List[str] = []
    seen_callsigns = set()
    for raw_call in callsigns:
        normalized = str(raw_call).strip().upper()
        if not normalized or normalized in seen_callsigns:
            continue
        seen_callsigns.add(normalized)
        deduped_callsigns.append(normalized)

    api = QRZAPI(username, password)
    ok = 0
    fail = 0
    for raw_call in deduped_callsigns:
        t0 = time.perf_counter()
        call = str(raw_call).strip()
        if not call:
            continue
        try:
            data = api.lookup_call(call)
            qslmgr = (data.get("qslmgr") or "").strip()
            has_bureau = api.has_qsl_manager(callsign=call, data=data)
            dt_ms = (time.perf_counter() - t0) * 1000
            print(f"✓ {call.upper():12} bureau={has_bureau!s:<5} qslmgr={qslmgr!r} ({dt_ms:.0f}ms)")
            ok += 1
        except QRZAPIError as e:
            dt_ms = (time.perf_counter() - t0) * 1000
            print(f"✗ {call.upper():12} error={str(e)} ({dt_ms:.0f}ms)")
            fail += 1
        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000
            print(f"✗ {call.upper():12} error={type(e).__name__}: {e} ({dt_ms:.0f}ms)")
            fail += 1

    print(f"\nSummary: ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
