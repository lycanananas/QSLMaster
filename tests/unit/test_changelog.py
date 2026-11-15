import importlib.util
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('changelog', ROOT_DIR / 'packaging' / 'changelog.py')
changelog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changelog)

SAMPLE = """# Changelog

## [Unreleased]

### Added
- Not released yet.

## [1.1.0] - 2026-11-15

### Added
- New `feature` with a long description that needs to be wrapped because it is longer than one Debian changelog line.
  Continued on the next line.

### Fixed
- A bug.

## [1.0.0] - 2026-01-02

### Added
- First release.

## Earlier releases

See GitHub.
"""

MAINTAINER = 'Test Maintainer <maintainer@example.invalid>'


def test_parse_and_entries():
    releases = changelog.parse_changelog(SAMPLE)
    release = changelog.find_release(releases, '1.1.0')
    assert release.date == '2026-11-15'
    assert release.entries() == [
        ('Added', 'New `feature` with a long description that needs to be wrapped because it is longer than one Debian changelog line. Continued on the next line.'),
        ('Fixed', 'A bug.'),
    ]
    assert release.notes().startswith('### Added\n- New `feature`')


def test_debian_changelog_lists_selected_and_older_releases():
    releases = changelog.parse_changelog(SAMPLE)
    output = changelog.build_debian_changelog(releases, MAINTAINER, up_to_version='1.1.0')
    assert output.startswith('qslmaster (1.1.0-1) unstable; urgency=medium\n\n  * Added: New feature with a long')
    assert 'qslmaster (1.0.0-1) unstable' in output
    assert 'Not released yet' not in output
    assert ' -- Test Maintainer <maintainer@example.invalid>  Sun, 15 Nov 2026 12:00:00 +0000' in output
    assert all(len(line) <= 80 for line in output.splitlines() if not line.startswith(' -- '))


def test_validation_rejects_missing_date_and_unknown_version():
    releases = changelog.parse_changelog(SAMPLE)
    with pytest.raises(SystemExit):
        changelog.validate_release(changelog.find_release(releases, 'Unreleased'))
    with pytest.raises(SystemExit):
        changelog.find_release(releases, '9.9.9')


def test_repository_changelog_has_current_version():
    import re
    source_version = re.search(r'SOURCE_VERSION = "([^"]+)"', (ROOT_DIR / 'qslmaster_version.py').read_text(encoding='utf-8')).group(1)
    releases = changelog.parse_changelog((ROOT_DIR / 'CHANGELOG.md').read_text(encoding='utf-8'))
    changelog.validate_release(changelog.find_release(releases, source_version))
    assert changelog.read_maintainer((ROOT_DIR / 'debian' / 'control').read_text(encoding='utf-8'))
