# Changelog

This file records the notable changes for each release. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The version numbers
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Write every entry in Simplified Technical English. Apply the
`simplified-technical-english` skill before you add or edit an entry. See
[AGENTS.md](AGENTS.md) for the rule.

## [Unreleased]

### Fixed

- Remove the extra blank lines and broken bullets in the generated output. The
  plugin now removes the newlines from a metadata description before it puts the
  description on a bullet or a summary line. A description with a trailing or an
  embedded newline no longer adds a blank line to a list or splits a bullet
  across two lines.

## [0.3.0] - 2026-08-25

### Added

- Add an "Analyze in a marimo notebook" section to the index, database, and table
  pages. The section shows how to query the data in a
  [marimo](https://marimo.io) notebook. It gives a `moutils[db]`
  `DatasetteConnection` example and a SQL cell example. The connection example
  uses the absolute URL of the instance.

### Changed

- Replace the "Columns" section on the table page with a shorter "Column notes"
  section. The "Schema" section already shows the column names, the types, and the
  keys. The new section shows only the human-written column descriptions. If no
  column has a description, the plugin does not add the section.

### Removed

- Remove the JSON download option from the "Downloading the full dataset" section
  on the table page. The section now shows the CSV download. CSV is a lighter
  format for a full download.
- Remove the "Primary key" line from the table page. The "Schema" section already
  shows the primary key.

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
