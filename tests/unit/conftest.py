import plistlib
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


COUNTRY_ENTRIES = {
    'SP': ('Poland', 269, False),
    'SN': ('Poland', 269, False),
    'SO': ('Poland', 269, False),
    'SQ': ('Poland', 269, False),
    'HF': ('Poland', 269, False),
    '3Z': ('Poland', 269, False),
    'DL': ('Fed. Rep. of Germany', 230, False),
    'DJ': ('Fed. Rep. of Germany', 230, False),
    'F': ('France', 227, False),
    'G': ('England', 223, False),
    'K': ('United States', 291, False),
    'W': ('United States', 291, False),
    'N': ('United States', 291, False),
    'JA': ('Japan', 339, False),
    'D4': ('Cabo Verde', 409, False),
    'UA': ('European Russia', 54, False),
    'UA9': ('Asiatic Russia', 15, False),
    'R9': ('Asiatic Russia', 15, False),
    'R': ('European Russia', 54, False),
    'JW': ('Svalbard', 259, False),
    'JW5MUA': ('Bear Island', 259, True),
}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b'', headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._json_data is None:
            raise ValueError('No JSON')
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


@pytest.fixture
def country_file(tmp_path):
    data = {
        prefix: {
            'Country': country,
            'Prefix': prefix,
            'ADIF': adif_id,
            'CQZone': 15,
            'ITUZone': 28,
            'Continent': 'EU',
            'Latitude': 0.0,
            'Longitude': 0.0,
            'GMTOffset': 0.0,
            'ExactCallsign': exact,
        }
        for prefix, (country, adif_id, exact) in COUNTRY_ENTRIES.items()
    }
    path = tmp_path / 'cty.plist'
    with open(path, 'wb') as file_handle:
        plistlib.dump(data, file_handle)
    return path


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    cache_dir = tmp_path / 'cache'
    monkeypatch.setenv('QSLMASTER_CACHE_DIR', str(cache_dir))
    return cache_dir
