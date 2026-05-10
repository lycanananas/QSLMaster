import io
import random
import sys
import zipfile
from pathlib import Path

import requests
from pyhamtools.callinfo import Callinfo
from pyhamtools.lookuplib import LookupLib

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from qslmaster_cli.callsign_utils import extract_homecall
from qslmaster_cli.qslmaster_core import QSLProcessor


COUNTRY_FILE_URL = 'https://www.country-files.com/cty/download/cty_plist.zip'
TEST_DATA_DIR = Path(__file__).resolve().parent / '.data'
COUNTRY_FILE_PATH = TEST_DATA_DIR / 'cty.plist'
SHUFFLE_SEED = 20260413
SUFFIXES = ['AAA', 'AAB', 'AAC', 'AAD', 'AAE', 'AAF', 'AAG', 'AAH', 'AAI', 'AAJ']
DECORATIONS = ['', '/P', '', '/M', '', '/P', '', '/M', '', '/P']
COUNTRY_BASE_CALLSIGNS = {
    'Argentina': 'LU1',
    'Australia': 'VK2',
    'Austria': 'OE1',
    'Brazil': 'PY2',
    'Bulgaria': 'LZ1',
    'Canada': 'VE3',
    'Chile': 'CE3',
    'China': 'BD1',
    'Croatia': '9A1',
    'Czech Republic': 'OK1',
    'Denmark': 'OZ1',
    'Fed. Rep. of Germany': 'DL1',
    'Fiji': '3D2',
    'Finland': 'OH2',
    'France': 'TM2',
    'Greece': 'SV1',
    'India': 'VU2',
    'Japan': 'JA1',
    'Kingdom of Eswatini': '3DA0',
    'Netherlands': 'PA3',
    'Poland': 'SP5',
    'Reunion Island': 'FR4',
    'Romania': 'YO2',
    'South Africa': 'ZS6',
    'United States': 'K1',
}

COUNTRY_SPOT_CHECKS = {
    '3D2AG/P': 'Fiji',
    '3DA0AA': 'Kingdom of Eswatini',
    'SP1AAA': 'Poland',
    'VK2FOX/P': 'Australia',
    'TM2ABC': 'France',
}


def ensure_country_file() -> Path:
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if COUNTRY_FILE_PATH.exists():
        return COUNTRY_FILE_PATH

    response = requests.get(COUNTRY_FILE_URL, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        plist_name = next(name for name in archive.namelist() if name.endswith('.plist'))
        COUNTRY_FILE_PATH.write_bytes(archive.read(plist_name))

    return COUNTRY_FILE_PATH


def build_processor(country_file: Path) -> QSLProcessor:
    processor = QSLProcessor({})
    processor.lookup_library = LookupLib(lookuptype='countryfile', filename=str(country_file))
    processor.callinfo = Callinfo(processor.lookup_library)
    entities = QSLProcessor.list_all_dxcc_entities(country_file=country_file)
    processor.dxcc_name_map = {int(item['id']): str(item['name']) for item in entities}
    return processor


def resolve_country(processor: QSLProcessor, callsign: str) -> str:
    homecall = extract_homecall(callsign.strip().upper())
    return processor.get_dxcc_name(processor.callinfo.get_adif_id(homecall))


def build_generated_callsigns() -> list[str]:
    callsigns = []
    for base_callsign in COUNTRY_BASE_CALLSIGNS.values():
        for index, suffix in enumerate(SUFFIXES):
            decoration = DECORATIONS[index]
            callsigns.append(f'{base_callsign}{suffix}{decoration}')
    callsigns.extend(COUNTRY_SPOT_CHECKS.keys())
    return callsigns


def build_qsos() -> list[dict[str, str]]:
    callsigns = build_generated_callsigns()
    shuffled_callsigns = list(callsigns)
    random.Random(SHUFFLE_SEED).shuffle(shuffled_callsigns)

    qsos = []
    for index, callsign in enumerate(shuffled_callsigns):
        day = (index % 28) + 1
        hour = index % 24
        minute = (index * 7) % 60
        qsos.append({
            'CALL': callsign,
            'QSO_DATE': f'202602{day:02d}',
            'TIME_ON': f'{hour:02d}{minute:02d}00',
        })
    return qsos


def build_expected_order(processor: QSLProcessor, qsos: list[dict[str, str]]) -> list[str]:
    expected_qsos = sorted(
        qsos,
        key=lambda qso: (
            resolve_country(processor, str(qso.get('CALL', ''))).casefold(),
            extract_homecall(str(qso.get('CALL', '')).strip().upper()).casefold(),
            str(qso.get('CALL', '')).strip().upper().casefold(),
            processor.format_qso_datetime(qso),
        ),
    )
    return [str(qso.get('CALL', '')) for qso in expected_qsos]


def main() -> int:
    ok = 0
    fail = 0

    country_file = ensure_country_file()
    processor = build_processor(country_file)
    qsos = build_qsos()
    unique_countries = sorted({resolve_country(processor, str(qso.get('CALL', ''))) for qso in qsos}, key=str.casefold)

    if len(qsos) == 255:
        print(f'✓ qso_count={len(qsos)}')
        ok += 1
    else:
        print(f'✗ qso_count={len(qsos)} expected=255')
        fail += 1

    if len(unique_countries) >= 25:
        print(f'✓ unique_country_count={len(unique_countries)}')
        ok += 1
    else:
        print(f'✗ unique_country_count={len(unique_countries)} expected>=25')
        fail += 1

    for callsign, expected_country in COUNTRY_SPOT_CHECKS.items():
        resolved_country = resolve_country(processor, callsign)
        if resolved_country == expected_country:
            print(f'✓ country {callsign} -> {resolved_country}')
            ok += 1
        else:
            print(f'✗ country {callsign} -> {resolved_country} expected={expected_country}')
            fail += 1

    unresolved_callsigns = [
        str(qso.get('CALL', ''))
        for qso in qsos
        if not resolve_country(processor, str(qso.get('CALL', '')))
    ]

    if not unresolved_callsigns:
        print('✓ all_callsigns_resolved_to_country')
        ok += 1
    else:
        print(f'✗ all_callsigns_resolved_to_country unresolved={unresolved_callsigns}')
        fail += 1

    expected_calls = build_expected_order(processor, qsos)
    sorted_qsos = processor.sort_qsos_for_pdf_labels(qsos)
    sorted_calls = [str(qso.get('CALL', '')) for qso in sorted_qsos]

    if sorted_calls == expected_calls:
        print('✓ pdf_label_sort_country_then_homecall')
        ok += 1
    else:
        print(f'✗ pdf_label_sort_country_then_homecall')
        print(f'  actual={sorted_calls}')
        print(f'  expected={expected_calls}')
        fail += 1

    first_ten = [
        (
            callsign,
            resolve_country(processor, callsign),
            extract_homecall(callsign),
        )
        for callsign in sorted_calls[:10]
    ]
    print(f'Preview first 10 sorted labels: {first_ten}')

    print(f'\nSummary: ok={ok} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())