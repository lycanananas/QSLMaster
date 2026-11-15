import pytest

from qslmaster_cli.callsign_utils import extract_homecall
from qslmaster_cli.country_file import CountryFileLookup, CountryFileError, list_all_dxcc_entities


@pytest.mark.parametrize('callsign, expected', [
    ('SP5ABC', 'SP5ABC'),
    ('SP/SP5ABC', 'SP5ABC'),
    ('SP5ABC/W5', 'SP5ABC'),
    ('DL/SQ5FOX/M/DL', 'SQ5FOX'),
    ('3z3z3z', '3Z3Z3Z'),
    ('DL/3z3z3z', '3Z3Z3Z'),
    ('DL/3z3z3z/am/m/ok', '3Z3Z3Z'),
    ('N0CALL/P', 'N0CALL'),
    ('W5/N0CALL', 'N0CALL'),
    ('PJ4/SP0NULL/AM/QRP', 'SP0NULL'),
])
def test_extract_homecall(callsign, expected):
    assert extract_homecall(callsign) == expected


@pytest.mark.parametrize('callsign, expected', [
    ('SP5ABC', 269),
    ('sq9p', 269),
    ('HF0FURRY', 269),
    ('3Z0TECH', 269),
    ('DL1AA', 230),
    ('F4ABC', 227),
    ('K1ABC', 291),
    ('D44AC', 409),
    ('UA1AAA', 54),
    ('UA9BBB', 15),
    ('R9WWW', 15),
    ('R3ZZZ', 54),
    ('JW5MUA', 259),
    ('JW7XX', 259),
])
def test_country_lookup_longest_prefix_and_exact_callsign(country_file, callsign, expected):
    assert CountryFileLookup(country_file).get_adif_id(callsign) == expected


def test_country_lookup_unknown_callsign_raises_key_error(country_file):
    with pytest.raises(KeyError):
        CountryFileLookup(country_file).get_adif_id('XX1XX')


def test_country_lookup_uses_adif_field_not_country_name(country_file):
    lookup = CountryFileLookup(country_file)
    assert lookup.dxcc_names[409] == 'Cabo Verde'
    assert lookup.dxcc_names[269] == 'Poland'


def test_list_all_dxcc_entities_is_sorted_and_unique(country_file):
    entities = list_all_dxcc_entities(country_file=country_file)
    names = [entity['name'] for entity in entities]
    assert names == sorted(names, key=str.lower)
    assert len({entity['id'] for entity in entities}) == len(entities)
    assert {'id': 259, 'name': 'Svalbard'} in entities


def test_country_file_without_prefixes_is_rejected(tmp_path):
    import plistlib
    path = tmp_path / 'empty.plist'
    with open(path, 'wb') as file_handle:
        plistlib.dump({}, file_handle)
    with pytest.raises(CountryFileError):
        CountryFileLookup(path)
