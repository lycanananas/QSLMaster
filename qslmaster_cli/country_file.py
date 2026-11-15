import io
import logging
import plistlib
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .cache import get_cache_dir, read_cache_metadata, write_cache_metadata, get_cache_age_days


logger = logging.getLogger(__name__)

COUNTRY_FILE_URL = 'https://www.country-files.com/cty/download/cty_plist.zip'
COUNTRY_FILE_SOURCE = 'https://www.country-files.com/cty/'
COUNTRY_FILE_MAX_AGE_DAYS = 3
POLAND_DXCC_ID = 269


class CountryFileError(Exception):
    pass


def get_country_file_paths() -> Tuple[Path, Path]:
    cache_dir = get_cache_dir()
    return cache_dir / 'cty.plist', cache_dir / '.cty_metadata.json'


def _emit(log_callback: Optional[Callable[[str, str], None]], level: str, message: str) -> None:
    if log_callback:
        log_callback(level, message)
    else:
        getattr(logger, level.lower(), logger.info)(message)


def _download_country_file(country_file: Path, metadata_file: Path) -> None:
    response = requests.get(COUNTRY_FILE_URL, timeout=30)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        plist_files = [name for name in archive.namelist() if name.endswith('.plist')]
        if not plist_files:
            raise CountryFileError('No .plist file found in ZIP')
        country_file.write_bytes(archive.read(plist_files[0]))
    write_cache_metadata(metadata_file, COUNTRY_FILE_URL, source=COUNTRY_FILE_SOURCE)


def ensure_country_file(log_callback: Optional[Callable[[str, str], None]] = None) -> Path:
    country_file, metadata_file = get_country_file_paths()
    metadata = read_cache_metadata(metadata_file)
    age_days = get_cache_age_days(metadata)

    if country_file.exists():
        if age_days is not None and age_days < COUNTRY_FILE_MAX_AGE_DAYS:
            _emit(log_callback, 'INFO', f'Using cached country file (metadata age: {age_days} day(s))')
            return country_file
        if age_days is None:
            _emit(log_callback, 'INFO', 'Country file metadata not found or unreadable, attempting refresh...')
        else:
            _emit(log_callback, 'INFO', f'Cached country file is older than {COUNTRY_FILE_MAX_AGE_DAYS} days, attempting refresh...')

    _emit(log_callback, 'INFO', 'Attempting to download fresh country file (plist)...')
    try:
        _download_country_file(country_file, metadata_file)
        _emit(log_callback, 'INFO', f'Successfully downloaded country file from {COUNTRY_FILE_URL}')
        return country_file
    except Exception as exc:
        _emit(log_callback, 'WARNING', f'Failed to download fresh country file: {exc}')

    if not country_file.exists():
        raise CountryFileError('Country file unavailable - download failed and no cached version found')

    _emit(log_callback, 'WARNING', f"Using cached country file from {metadata.get('downloaded_at', 'unknown date')}")
    return country_file


class CountryFileLookup:

    def __init__(self, country_file: Path):
        with open(country_file, 'rb') as file_handle:
            data = plistlib.load(file_handle)

        self.exact_callsigns: Dict[str, int] = {}
        self.prefixes: Dict[str, int] = {}
        self.dxcc_names: Dict[int, str] = {}
        for key, entry in data.items():
            if not isinstance(entry, dict) or entry.get('ADIF') is None:
                continue
            adif_id = int(entry['ADIF'])
            target = self.exact_callsigns if entry.get('ExactCallsign') else self.prefixes
            target[str(key).strip().upper()] = adif_id
            country = str(entry.get('Country') or '').strip()
            if adif_id > 0 and country:
                self.dxcc_names.setdefault(adif_id, country)

        if not self.prefixes:
            raise CountryFileError(f"Country file {country_file} contains no prefixes")
        self.dxcc_names.setdefault(POLAND_DXCC_ID, 'Poland')
        self.max_prefix_length = max(len(prefix) for prefix in self.prefixes)

    def get_adif_id(self, callsign: str) -> int:
        callsign = str(callsign or '').strip().upper()
        if callsign in self.exact_callsigns:
            return self.exact_callsigns[callsign]
        for length in range(min(len(callsign), self.max_prefix_length), 0, -1):
            adif_id = self.prefixes.get(callsign[:length])
            if adif_id is not None:
                return adif_id
        raise KeyError(f"No DXCC entity found for callsign {callsign}")

    def list_dxcc_entities(self) -> List[Dict[str, Any]]:
        entities = [{'id': dxcc_id, 'name': name} for dxcc_id, name in self.dxcc_names.items()]
        entities.sort(key=lambda item: (item['name'].lower(), item['id']))
        return entities


def list_all_dxcc_entities(
    log_callback: Optional[Callable[[str, str], None]] = None,
    country_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if country_file is None:
        country_file = ensure_country_file(log_callback=log_callback)
    return CountryFileLookup(country_file).list_dxcc_entities()
