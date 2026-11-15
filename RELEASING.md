# Releasing QSLMaster

This document describes how a new QSLMaster version is prepared and published.
Releases are built and published by GitHub Actions from a version tag. Nothing is uploaded from a local machine.

## Versioning

QSLMaster uses [Semantic Versioning](https://semver.org/) with tags in the form `vMAJOR.MINOR.PATCH`, for example `v1.6.0`.

- `MAJOR` for incompatible changes in configuration or CLI behaviour.
- `MINOR` for new features.
- `PATCH` for bug fixes only.

The version is defined in one place: `SOURCE_VERSION` in `qslmaster_version.py`.

## Changelog

`CHANGELOG.md` is the single source of release information:

- GitHub release notes are taken from the version section.
- The Debian package changelog (`/usr/share/doc/qslmaster/changelog.Debian.gz`) is generated from all dated sections.

Rules:

- Add entries while working, under `### Added`, `### Changed`, `### Removed` or `### Fixed`.
- Write entries for users, in English, one line per change.
- A section header must have the form `## [1.6.0] - 2026-11-15`. A section without a date cannot be released.

Preview the generated output locally:

```bash
python packaging/changelog.py check 1.6.0
python packaging/changelog.py notes 1.6.0
python packaging/changelog.py debian 1.6.0
```

## Release procedure

1. Create a release branch from `master`:
   ```bash
   git checkout master && git pull
   git checkout -b release/v1.6
   ```
2. Set `SOURCE_VERSION` in `qslmaster_version.py`, for example `1.6.0`.
3. Update `CHANGELOG.md`: add or complete the version section and set the release date.
4. Run the checks:
   ```bash
   pip install -r requirements-dev.txt
   python -m pytest
   python packaging/changelog.py check 1.6.0
   ```
   Optional live checks against external services:
   ```bash
   python tests/pzk_selftest.py
   python tests/qrz_selftest.py --config config.json
   ```
5. Test the GUI manually: `python -m qslmaster_gui.main` (processing with Wavelog and ADIF, Test Key, Mark as Sent on a test log).
6. Push the branch and open a pull request to `master`. The `ci` workflow must pass.
7. Merge the pull request.
8. Create and push an annotated tag on `master`:
   ```bash
   git checkout master && git pull
   git tag -a v1.6.0 -m "Release v1.6.0"
   git push origin v1.6.0
   ```
9. The `release` workflow then:
   - checks that the tag matches `SOURCE_VERSION`, points to a commit on `master` and has a dated `CHANGELOG.md` section,
   - runs the unit tests,
   - builds the Debian packages (Ubuntu 22.04 and 24.04), the Arch Linux package and the Windows installer and ZIP,
   - publishes a GitHub release with the changelog section as release notes and `SHA256SUMS` for all files.
10. Check the published release: all assets are present, the release notes are correct, and at least one package installs and starts.

If the workflow fails before publishing, fix the problem on `master`, delete the tag locally and remotely (`git tag -d v1.6.0`, `git push origin :refs/tags/v1.6.0`) and tag again.
Never move or reuse a tag of a published release. Publish a new patch version instead.

## Hotfix releases

1. Create a branch from the release tag: `git checkout -b hotfix/v1.6.1 v1.6.0`.
2. Fix the problem, bump `SOURCE_VERSION` to the next patch version and add a changelog section.
3. Follow steps 4 to 10 of the release procedure.

## Public repository checklist

This repository is public. Before every commit and release:

- Never commit `config.json`, API keys, Wavelog tokens, QRZ credentials or real ADIF logs. The `.gitignore` excludes `/*.json` (except `config.example.json`), `*.adi`, `*.adif` and `*.pdf`, but check `git status` before committing.
- Use example values only in documentation and tests (`wavelog.example.com`, `wl2_your_token_here`, test callsigns).
- If a secret was committed or pasted anywhere public, revoke it immediately in Wavelog or QRZ. Removing it from history is not enough.
- The release workflow uses only the built-in `GITHUB_TOKEN`. No additional repository secrets are required.
