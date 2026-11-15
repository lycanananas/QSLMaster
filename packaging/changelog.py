import argparse
import re
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
CHANGELOG_PATH = ROOT_DIR / 'CHANGELOG.md'
CONTROL_PATH = ROOT_DIR / 'debian' / 'control'
VERSION_HEADING = re.compile(r'^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$')
SECTION_HEADING = re.compile(r'^### (?P<name>.+?)\s*$')
DEBIAN_REVISION = '1'
DEBIAN_DISTRIBUTION = 'unstable'
DEBIAN_URGENCY = 'medium'


@dataclass
class Release:
    version: str
    date: Optional[str]
    body: List[str] = field(default_factory=list)

    def entries(self) -> List[Tuple[str, str]]:
        entries: List[Tuple[str, str]] = []
        section = ''
        for line in self.body:
            heading = SECTION_HEADING.match(line)
            if heading:
                section = heading.group('name')
            elif line.startswith('- '):
                entries.append((section, line[2:].strip()))
            elif line.startswith('  ') and entries and line.strip():
                previous_section, previous_text = entries[-1]
                entries[-1] = (previous_section, f"{previous_text} {line.strip()}")
        return entries

    def notes(self) -> str:
        return '\n'.join(self.body).strip() + '\n'


def parse_changelog(text: str) -> List[Release]:
    releases: List[Release] = []
    for line in text.splitlines():
        heading = VERSION_HEADING.match(line)
        if heading:
            releases.append(Release(heading.group('version'), heading.group('date')))
        elif line.startswith('## '):
            releases.append(Release(line[3:].strip(), None))
        elif releases:
            releases[-1].body.append(line.rstrip())
    return releases


def find_release(releases: List[Release], version: str) -> Release:
    for release in releases:
        if release.version == version:
            return release
    raise SystemExit(f"CHANGELOG.md has no section for version {version}")


def validate_release(release: Release) -> None:
    if not release.date:
        raise SystemExit(f"CHANGELOG.md section {release.version} has no release date (expected: ## [{release.version}] - YYYY-MM-DD)")
    if not release.entries():
        raise SystemExit(f"CHANGELOG.md section {release.version} has no entries")


def read_maintainer(control_text: str) -> str:
    match = re.search(r'^Maintainer:\s*(.+)$', control_text, flags=re.MULTILINE)
    if not match:
        raise SystemExit('Maintainer not found in debian/control')
    return match.group(1).strip()


def format_debian_date(release_date: str) -> str:
    return format_datetime(datetime.strptime(release_date, '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc))


def format_debian_entry(section: str, text: str) -> List[str]:
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = f"{section}: {text}" if section else text
    return textwrap.wrap(text, width=76, initial_indent='  * ', subsequent_indent='    ')


def build_debian_changelog(releases: List[Release], maintainer: str, up_to_version: Optional[str] = None) -> str:
    blocks = []
    include = up_to_version is None
    for release in releases:
        if not include and release.version == up_to_version:
            include = True
        if not include or not release.date:
            continue
        lines = [f"qslmaster ({release.version}-{DEBIAN_REVISION}) {DEBIAN_DISTRIBUTION}; urgency={DEBIAN_URGENCY}", '']
        for section, text in release.entries():
            lines.extend(format_debian_entry(section, text))
        lines.extend(['', f" -- {maintainer}  {format_debian_date(release.date)}"])
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) + '\n'


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Generate release notes and Debian changelog from CHANGELOG.md')
    parser.add_argument('command', choices=['check', 'notes', 'debian'])
    parser.add_argument('version', help='Release version without the leading v, e.g. 1.6.0')
    parser.add_argument('--changelog', default=str(CHANGELOG_PATH))
    parser.add_argument('--control', default=str(CONTROL_PATH))
    args = parser.parse_args(argv)

    releases = parse_changelog(Path(args.changelog).read_text(encoding='utf-8'))
    release = find_release(releases, args.version)
    validate_release(release)

    if args.command == 'notes':
        sys.stdout.write(release.notes())
    elif args.command == 'debian':
        maintainer = read_maintainer(Path(args.control).read_text(encoding='utf-8'))
        sys.stdout.write(build_debian_changelog(releases, maintainer, up_to_version=args.version))
    else:
        print(f"CHANGELOG.md section {release.version} ({release.date}) is valid with {len(release.entries())} entries")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
