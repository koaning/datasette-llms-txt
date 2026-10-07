"""Deterministic llms.txt generation from Datasette schema introspection.

Each ``generate_*`` coroutine returns a markdown string following the
https://llmstxt.org/ convention. Human-written descriptions from Datasette
metadata (``metadata.yaml``/``metadata.json``) are preferred over
schema-derived text; this is the designed insertion point for a future,
opt-in LLM-enrichment step.
"""

from datasette.utils import escape_sqlite

DEFAULT_SAMPLE_ROWS = 5

# Databases Datasette manages internally that we never document.
HIDDEN_DATABASES = ("_internal", "_memory")

QUERY_HELP = (
    "Datasette exposes this data over an HTTP API. Append `.json` or `.csv` to "
    "any table, database or SQL-query URL, or run SQL via `/<db>.json?sql=<query>`. "
    "To download a whole table cleanly, stream it as CSV with `?_stream=on` (no row "
    "limit). Per-database and per-table markdown (`.md`) files, with full-download "
    "instructions, are linked below."
)


def _clean(value):
    """Collapse whitespace (including newlines) so metadata descriptions stay
    on a single line inside bullets and blockquotes.

    Datasette metadata is human-authored and often carries trailing or embedded
    newlines. Left as-is, those newlines survive the final ``"\\n".join(out)``
    and turn into stray blank lines inside a list, or split one bullet across
    two lines.
    """
    if not value:
        return ""
    return " ".join(str(value).split())


def _plugin_config(datasette):
    return datasette.plugin_config("datasette-llms-txt") or {}


def _sample_rows(datasette):
    config = _plugin_config(datasette)
    try:
        return max(0, int(config.get("sample_rows", DEFAULT_SAMPLE_ROWS)))
    except (TypeError, ValueError):
        return DEFAULT_SAMPLE_ROWS


def _supports_async_metadata(datasette):
    """Datasette 1.0 removed the synchronous ``metadata()`` method and replaced
    it with per-scope async getters (``get_instance_metadata`` and friends)."""
    return hasattr(datasette, "get_instance_metadata")


def _legacy_metadata(datasette):
    """Full metadata dict on Datasette < 1.0.

    Only the callers' ``< 1.0`` branch reaches this, so ``metadata()`` is always
    present here (Datasette 1.0 removed it; that path uses the async getters).
    """
    return datasette.metadata() or {}


async def _instance_metadata(datasette):
    """Instance-level metadata (title, description, source, license)."""
    if _supports_async_metadata(datasette):
        return await datasette.get_instance_metadata() or {}
    return _legacy_metadata(datasette)


async def _db_metadata(datasette, db_name):
    if _supports_async_metadata(datasette):
        return await datasette.get_database_metadata(db_name) or {}
    return (_legacy_metadata(datasette).get("databases") or {}).get(db_name) or {}


async def _table_metadata(datasette, db_name, table):
    if _supports_async_metadata(datasette):
        return await datasette.get_resource_metadata(db_name, table) or {}
    db_meta = (_legacy_metadata(datasette).get("databases") or {}).get(db_name) or {}
    return (db_meta.get("tables") or {}).get(table) or {}


def _visible_databases(datasette):
    return [
        (name, db)
        for name, db in datasette.databases.items()
        if name not in HIDDEN_DATABASES
    ]


def _can_stream_csv(datasette):
    """CSV streaming (`?_stream=on`) is gated by the allow_csv_stream setting."""
    return bool(datasette.setting("allow_csv_stream"))


def _can_download_db(datasette, db):
    """Whole-file `.db` download requires an immutable, on-disk database and the
    allow_download setting (Datasette returns 403 for mutable/in-memory ones)."""
    return bool(
        datasette.setting("allow_download")
        and not db.is_mutable
        and not db.is_memory
    )


async def _documented_tables(db):
    """Table names in ``db``, excluding Datasette's hidden/FTS/internal tables."""
    hidden = set(await db.hidden_table_names())
    return [name for name in await db.table_names() if name not in hidden]


async def _row_count(db, table):
    try:
        result = await db.execute(
            "select count(*) from {}".format(escape_sqlite(table))
        )
        return result.single_value()
    except Exception:
        return None


def _about_lines(meta):
    """Render source/license metadata as an llms.txt 'Optional' About section."""
    lines = []
    source = meta.get("source")
    source_url = meta.get("source_url")
    if source or source_url:
        if source and source_url:
            lines.append(f"- Source: [{source}]({source_url})")
        else:
            lines.append(f"- Source: {source or source_url}")
    license_ = meta.get("license")
    license_url = meta.get("license_url")
    if license_ or license_url:
        if license_ and license_url:
            lines.append(f"- License: [{license_}]({license_url})")
        else:
            lines.append(f"- License: {license_ or license_url}")
    if not lines:
        return []
    return ["## About", "", *lines, ""]


def _normalise_column_description(value):
    """Datasette allows a column's metadata to be a plain string or a dict
    with a ``description``/``title`` key. Normalise both to a display string."""
    if isinstance(value, dict):
        return _clean(value.get("description") or value.get("title"))
    return _clean(value)


async def _column_description(datasette, db_name, table, column, table_meta):
    """Human-written description for a single column, across Datasette versions.

    On Datasette 1.0 column metadata lives behind ``get_column_metadata``. On
    older versions it is nested under the table's ``columns`` key (``table_meta``).
    """
    if _supports_async_metadata(datasette):
        value = await datasette.get_column_metadata(db_name, table, column) or {}
    else:
        value = (table_meta.get("columns") or {}).get(column)
    return _normalise_column_description(value)


def _cell(value):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|")


def _markdown_table(columns, rows):
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row[c]) for c in columns) + " |")
    return lines


def _instance_base_url(datasette, request):
    """Absolute instance root (scheme + host, including any ``base_url`` prefix).

    This is the first argument to ``moutils`` ``DatasetteConnection``. It uses the
    same request-based mechanism as every other absolute link Datasette builds.
    """
    return datasette.absolute_url(request, datasette.urls.path("/")).rstrip("/")


def _marimo_lines(base_url, db_name, table=None):
    """A ``## Analyze in a marimo notebook`` section.

    It shows a ``moutils`` ``DatasetteConnection`` and a SQL-cell example. When a
    table is given, the SQL example queries that table; otherwise it uses a
    ``<table>`` placeholder.
    """
    return [
        "## Analyze in a marimo notebook",
        "",
        "You can query this data in a [marimo](https://marimo.io) notebook with a "
        "SQL cell. Install `moutils[db]`, then open a Python cell and connect:",
        "",
        "```python",
        "from moutils.db.datasette import DatasetteConnection",
        "",
        f'datasette = DatasetteConnection("{base_url}", "{db_name}")',
        "```",
        "",
        "marimo shows `datasette` as a SQL engine. Add a SQL cell and query the "
        "data:",
        "",
        "```sql",
        f"SELECT * FROM {table if table else '<table>'} LIMIT 10",
        "```",
        "",
    ]


async def generate_index(datasette, request):
    metadata = await _instance_metadata(datasette)
    databases = _visible_databases(datasette)

    title = _clean(metadata.get("title")) or "Datasette"
    description = _clean(metadata.get("description")) or (
        f"A Datasette instance serving {len(databases)} "
        f"database{'s' if len(databases) != 1 else ''} as queryable data."
    )

    out = [f"# {title}", "", f"> {description}", "", QUERY_HELP, ""]

    out += ["## Databases", ""]
    table_index = []  # (db_name, table) collected for the flat table list below
    for db_name, db in databases:
        tables = await _documented_tables(db)
        db_meta = await _db_metadata(datasette, db_name)
        note = _clean(db_meta.get("description")) or (
            f"{len(tables)} table{'s' if len(tables) != 1 else ''}"
        )
        url = datasette.urls.database(db_name) + ".md"
        out.append(f"- [{db_name}]({url}): {note}")
        table_index += [(db_name, db, t) for t in tables]
    out.append("")

    if table_index:
        out += ["## Tables", ""]
        for db_name, db, table in table_index:
            columns = await db.table_columns(table)
            tbl_meta = await _table_metadata(datasette, db_name, table)
            count = await _row_count(db, table)
            bits = []
            if count is not None:
                bits.append(f"{count} rows")
            if _clean(tbl_meta.get("description")):
                bits.append(_clean(tbl_meta["description"]))
            elif columns:
                bits.append("columns: " + ", ".join(columns))
            url = datasette.urls.table(db_name, table) + ".md"
            note = "; ".join(bits)
            out.append(f"- [{db_name}/{table}]({url}){': ' + note if note else ''}")
        out.append("")

    if databases:
        base_url = _instance_base_url(datasette, request)
        out += _marimo_lines(base_url, databases[0][0])

    out += _about_lines(metadata)
    return "\n".join(out).rstrip() + "\n"


async def generate_database(datasette, db_name, request):
    instance_meta = await _instance_metadata(datasette)
    db = datasette.databases[db_name]
    db_meta = await _db_metadata(datasette, db_name)
    tables = await _documented_tables(db)

    description = _clean(db_meta.get("description")) or (
        f"Database `{db_name}` with {len(tables)} "
        f"table{'s' if len(tables) != 1 else ''}."
    )
    out = [f"# {db_name}", "", f"> {description}", ""]

    out += ["## Tables", ""]
    for table in tables:
        columns = await db.table_columns(table)
        tbl_meta = await _table_metadata(datasette, db_name, table)
        count = await _row_count(db, table)
        bits = []
        if count is not None:
            bits.append(f"{count} rows")
        if _clean(tbl_meta.get("description")):
            bits.append(_clean(tbl_meta["description"]))
        elif columns:
            bits.append("columns: " + ", ".join(columns))
        url = datasette.urls.table(db_name, table) + ".md"
        note = "; ".join(bits)
        out.append(f"- [{table}]({url}){': ' + note if note else ''}")
    out.append("")

    out += ["## Downloading", ""]
    if _can_stream_csv(datasette):
        out.append(
            f"- Any table as streamed CSV (no row limit): "
            f"`{datasette.urls.database(db_name)}/<table>.csv?_stream=on`"
        )
    if _can_download_db(datasette, db):
        out.append(
            f"- The entire SQLite database as a single file: "
            f"`{datasette.urls.database(db_name)}.db`"
        )
    out.append("")

    base_url = _instance_base_url(datasette, request)
    out += _marimo_lines(base_url, db_name)

    out += _about_lines({**instance_meta, **db_meta})
    return "\n".join(out).rstrip() + "\n"


async def generate_table(datasette, db_name, table, request):
    db = datasette.databases[db_name]
    tbl_meta = await _table_metadata(datasette, db_name, table)

    columns = await db.table_column_details(table)
    count = await _row_count(db, table)

    description = _clean(tbl_meta.get("description")) or (
        f"Table `{table}` with "
        + (f"{count} rows and " if count is not None else "")
        + f"{len(columns)} column{'s' if len(columns) != 1 else ''}."
    )
    out = [f"# {db_name}/{table}", "", f"> {description}", ""]

    schema = await db.get_table_definition(table)
    if schema:
        out += ["## Schema", "", "```sql", schema.strip(), "```", ""]

    # The schema block already lists column names, types, and keys. Only add
    # per-column notes for the human descriptions the schema cannot carry.
    notes = []
    for col in columns:
        col_desc = await _column_description(
            datasette, db_name, table, col.name, tbl_meta
        )
        if col_desc:
            notes.append(f"- `{col.name}` — {col_desc}")
    if notes:
        out += ["## Column notes", "", *notes, ""]

    table_url = datasette.urls.table(db_name, table)
    db_url = datasette.urls.database(db_name)
    example_col = columns[0].name if columns else "id"
    out += [
        "## Querying",
        "",
        f"- JSON rows: `{table_url}.json` (add `?_shape=array` for a plain array)",
        f"- CSV export: `{table_url}.csv`",
        f"- Filtered: `{table_url}.json?{example_col}=<value>`",
        f"- SQL: `{db_url}.json?sql=select * from {escape_sqlite(table)} limit 10`",
        "",
    ]

    base_url = _instance_base_url(datasette, request)
    out += _marimo_lines(base_url, db_name, table)

    downloads = []
    if _can_stream_csv(datasette):
        downloads.append(
            f"- All rows as CSV, streamed with no row limit: `{table_url}.csv?_stream=on`"
        )
    if _can_download_db(datasette, db):
        downloads.append(
            f"- The entire SQLite database as a single file: `{db_url}.db`"
        )
    if downloads:
        out += ["## Downloading the full dataset", "", *downloads, ""]

    sample_rows = _sample_rows(datasette)
    if sample_rows and columns:
        try:
            result = await db.execute(
                "select * from {} limit {}".format(
                    escape_sqlite(table), sample_rows
                )
            )
            rows = list(result.rows)
            if rows:
                col_names = result.columns
                out += ["## Sample rows", ""]
                out += _markdown_table(col_names, rows)
                out.append("")
        except Exception:
            pass

    return "\n".join(out).rstrip() + "\n"
