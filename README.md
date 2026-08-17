# datasette-llms-txt

[![PyPI](https://img.shields.io/pypi/v/datasette-llms-txt.svg)](https://pypi.org/project/datasette-llms-txt/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/koaning/datasette-llms-txt/blob/main/LICENSE)

This plugin generates [llms.txt](https://llmstxt.org/) documentation for a
Datasette instance. Large language models and people can then find out which data
is available and how to query it.

The plugin reads the schema of your databases when a request arrives. You do not
build or update any files. It serves Markdown that lists every database, table,
column, and primary key. It also gives the JSON and SQL endpoints that query the
data. If you write descriptions in Datasette metadata, the plugin uses them
without change.

## Installation

Install this plugin in the same environment as Datasette:

```bash
datasette install datasette-llms-txt
```

## Usage

After you install the plugin, it adds these endpoints:

| URL | Contents |
| --- | --- |
| `/llms.txt` | Instance overview: every database and table, with links and query instructions |
| `/<db>.md` | A single database and its tables |
| `/<db>/<table>.md` | Full schema, columns, primary keys, query endpoints and sample rows for one table |

The [llms.txt convention](https://llmstxt.org/) asks the index to link to the
markdown (`.md`) version of each page. The `/llms.txt` index links to the `.md`
files above.

The plugin also keeps the earlier `/<db>/llms.txt` and `/<db>/<table>/llms.txt`
endpoints. They serve the same content as the `.md` files.

For example, with a `demo.db` file:

```bash
datasette demo.db
curl http://127.0.0.1:8001/llms.txt
curl http://127.0.0.1:8001/demo.md
curl http://127.0.0.1:8001/demo/people.md
```

The plugin also adds a link to `/llms.txt` in Datasette's top-right menu.

## Downloading data

Each per-table page also shows how to download the data, not only how to
query it:

- **CSV export**: `/<db>/<table>.csv`
- **Full table, streamed**: `/<db>/<table>.csv?_stream=on` — every row, no row limit
- **Full table as JSON**: request `/<db>/<table>.json?_size=max`, then follow the
  `next_url` field in each response
- **Whole database file**: `/<db>.db` — the plugin shows this only when the database
  is immutable and the `allow_download` setting is on

The plugin shows the streamed-CSV and database-file options only when the
Datasette settings `allow_csv_stream` and `allow_download` permit them. Because of
this, the generated docs never link to an endpoint that returns a 403 error.

## Metadata

The plugin prefers descriptions from your Datasette
[metadata](https://docs.datasette.io/en/stable/metadata.html) over text that it
builds from the schema. It shows the instance `title` and `description`, the
per-database and per-table `description`, the per-column descriptions, and the
`source` and `license`.

A table's `description` has two uses. It becomes the summary line for that table
in the index and the per-database listings. It also becomes the blockquote at the
top of the table's own `llms.txt`. If you do not give a description, the plugin
generates a summary like "N rows, columns: …". For example:

```yaml
title: My Data
description: Public records, refreshed nightly.
source: Example Org
source_url: https://example.com
databases:
  demo:
    tables:
      people:
        description: One row per registered person.
        columns:
          email: Primary contact address.
```

## Configuration

Set the options under the plugin's key in your metadata or config file:

```yaml
plugins:
  datasette-llms-txt:
    sample_rows: 5
```

- `sample_rows` (default `5`) — the number of example rows to show in each
  per-table `llms.txt`. Set it to `0` to leave out all sample data. This helps
  when the rows are sensitive.

## Development

```bash
cd datasette-llms-txt
uv venv
uv pip install -e '.[test]'
uv run pytest
```

Or use the Makefile: `make install` then `make test`.

### Datasette compatibility

The plugin works on Datasette 0.65 and on Datasette 1.0. Datasette 1.0 changed the
metadata methods, so the plugin reads the metadata in a way that supports both
versions.

`make test` runs the suite against both versions:

```bash
make test
```

This command builds one environment for each Datasette version and runs the test
suite in each one. It builds the environments one time and then reuses them. The CI
workflow runs the same matrix.
