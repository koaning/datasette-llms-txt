# Changelog

This file records the notable changes for each release. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version numbers
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Write every entry in Simplified Technical English. Apply the
`simplified-technical-english` skill before you add or edit an entry. See
[AGENTS.md](AGENTS.md) for the rule.

## [0.1.1] - 2026-08-14

### Fixed

- Render a clean column description when the Datasette metadata uses the dict
  form (`columns: {name: {description: ...}}`). Before this fix, the plugin wrote
  the raw dict into the `llms.txt` output. The plugin now shows the same text for
  the dict form and the string form.

## [0.1]

### Added

- First release. The plugin generates `llms.txt` documentation for a Datasette
  instance. It serves an index file, one file for each database, and one file for
  each table.
