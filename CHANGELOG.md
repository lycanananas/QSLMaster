# Changelog

All notable changes to QSLMaster are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).
This file is the single source for GitHub release notes and the Debian package changelog, see [RELEASING.md](RELEASING.md).

## [1.6.0] - 2026-11-15

### Added
- Wavelog API v2 support. Tokens starting with `wl2_` are detected automatically, API v1 keys keep working.
- Server-side Wavelog filters for API v2: the selected date range and stations are sent with the request, so only the needed QSOs are downloaded. Rate limit responses are retried automatically.
- Mark as Sent in Wavelog: QSOs from a QSLMaster output ADIF file are matched with the Wavelog log and updated with QSL sent status, sent via, QSL via and sent date. Available in the GUI (with preview, sent date selection and cancel) and with `--mark-sent`, `--sent-date` and `--dry-run` in the CLI. Only files created by QSLMaster are accepted, so a regular Wavelog export cannot overwrite existing sent dates by mistake. Requires an API v2 token with the `qso:write` scope.
- Test Key button and API Key Help in the settings dialog, including the required API v2 scopes.
- Clear Wavelog permission errors: missing scopes, invalid or expired tokens are shown in the station list, in Test Key and when downloading the log.
- Local cache of the PZK QSL bureau list, used automatically when the PZK server is unavailable.
- Offline unit test suite (pytest) and a CI workflow running it on every push and pull request.
- `CHANGELOG.md` and an automated Debian changelog and GitHub release notes generated from it.

### Changed
- PZK lookup uses the official QSL bureau list `https://pzk.org.pl/osec_qsl.txt` instead of scraping the member search page. Club and special callsigns are covered by the same list.
- Network calls in the GUI (station list, Test Key, Mark as Sent) run in the background, so the window no longer freezes on a slow server.
- An empty result from Wavelog is no longer an error, the run finishes with an empty output.
- Wavelog connection errors are reported with the actual reason instead of a generic health check failure, and the station list is requested only once per run.
- Minimum supported Python version is 3.9.
- The processing core is split into smaller modules (filters, label sorting, ADIF files, country file, Wavelog, mark as sent).
- README commands use `python -m qslmaster_cli.main` and `python -m qslmaster_gui.main`.

### Removed
- `pyhamtools` dependency. The country file (`cty.plist`) is read directly using its ADIF entity numbers.
- `lxml` dependency.

### Fixed
- Processing failed with `Failed to initialize CallInfo: 'Cabo Verde'` after country-files.com renamed the entity.
- PZK lookups stopped working after the PZK website change.
- QSO times in `HHMM` format were shown with wrong minutes in logs and label sorting.
- ADIF data without a header failed to parse when it started with an empty line.
- An empty logo path produced a warning for every PDF label.
- Closing the GUI or pressing Ctrl+C during processing raised an error.

## Earlier releases

Release notes for versions up to 1.5.4 are available on the [GitHub Releases](https://github.com/lycanananas/QSLMaster/releases) page.
