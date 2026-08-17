# Changelog

This file records the notable changes for each release. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version numbers
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Write every entry in Simplified Technical English. Apply the
`simplified-technical-english` skill before you add or edit an entry. See
[AGENTS.md](AGENTS.md) for the rule.

## [0.2.0] - 2026-08-17

### Added

- Serve a markdown (`.md`) page for each database and table, at `/<db>.md` and
  `/<db>/<table>.md`. The `/llms.txt` index now links to these `.md` files. This
  follows the [llms.txt](https://llmstxt.org/) convention, which asks the index to
  link to the markdown version of each page.

### Changed

- The `/llms.txt` index and the per-database pages now link to the `.md` pages.
  Before this change, they linked to the `/<db>/llms.txt` and
  `/<db>/<table>/llms.txt` pages. Those pages still work and serve the same
  content.

### Fixed

- Read the metadata on Datasette 1.0. Datasette 1.0 removed the `metadata()`
  method and added async methods to read the metadata. Before this fix, the plugin
  ignored all metadata on Datasette 1.0. The plugin now reads the title,
  description, source, license, and column descriptions on Datasette 0.65 and on
  Datasette 1.0.

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
