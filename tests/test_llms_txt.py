import pytest
import sqlite_utils
from datasette.app import Datasette

# Datasette 1.0 replaced the sync metadata() method with async getters. Some
# older metadata *input* shapes cannot be loaded into the 1.0 metadata store.
HAS_V1_METADATA = hasattr(Datasette, "get_instance_metadata")


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "demo.db")
    db = sqlite_utils.Database(path)
    db["people"].insert_all(
        [
            {"id": 1, "name": "Ada", "email": "ada@example.com"},
            {"id": 2, "name": "Alan", "email": "alan@example.com"},
            {"id": 3, "name": "Grace", "email": "grace@example.com"},
        ],
        pk="id",
    )
    db["dogs"].insert_all(
        [{"id": 1, "name": "Cleo"}, {"id": 2, "name": "Pancakes"}], pk="id"
    )
    # Full-text search creates hidden companion tables that must be excluded.
    db["people"].enable_fts(["name"])
    return path


@pytest.fixture
def metadata():
    return {
        "title": "My Data",
        "description": "Example instance.",
        "source": "ACME",
        "source_url": "https://example.com",
        "license": "CC0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "databases": {
            "demo": {
                "tables": {
                    "people": {
                        "description": "One row per person.",
                        "columns": {"email": "Contact address."},
                    }
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_index(db_path, metadata):
    ds = Datasette([db_path], metadata=metadata)
    response = await ds.client.get("/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert body.startswith("# My Data")
    assert "> Example instance." in body
    assert "## Databases" in body
    assert "## Tables" in body
    assert "[demo](/demo.md)" in body
    assert "[demo/people](/demo/people.md)" in body
    assert "[demo/dogs](/demo/dogs.md)" in body
    # marimo analysis section with a concrete connection to the first database
    assert "## Analyze in a marimo notebook" in body
    assert 'DatasetteConnection("http://localhost", "demo")' in body
    # source/license surfaced as an About section
    assert "## About" in body
    assert "[ACME](https://example.com)" in body
    assert "CC0" in body


@pytest.mark.asyncio
async def test_database(db_path, metadata):
    ds = Datasette([db_path], metadata=metadata)
    response = await ds.client.get("/demo/llms.txt")
    assert response.status_code == 200
    body = response.text
    assert body.startswith("# demo")
    assert "[people](/demo/people.md)" in body
    assert "[dogs](/demo/dogs.md)" in body
    # metadata table description preferred over the column fallback
    assert "One row per person." in body
    # marimo analysis section with a concrete connection to this database
    assert "## Analyze in a marimo notebook" in body
    assert "from moutils.db.datasette import DatasetteConnection" in body
    assert 'DatasetteConnection("http://localhost", "demo")' in body


@pytest.mark.asyncio
async def test_table(db_path, metadata):
    ds = Datasette([db_path], metadata=metadata)
    response = await ds.client.get("/demo/people/llms.txt")
    assert response.status_code == 200
    body = response.text
    assert body.startswith("# demo/people")
    assert "> One row per person." in body
    # the CREATE TABLE schema is the single source of structure
    assert "CREATE TABLE" in body
    # column notes carry only the human descriptions, not a schema restatement
    assert "## Column notes" in body
    assert "`email` — Contact address." in body
    # types, nullability, and the primary key live only in the schema block
    assert "## Columns" not in body
    assert "Primary key:" not in body
    assert "nullable" not in body
    assert "## Querying" in body
    assert "/demo/people.json" in body
    # CSV export and full-dataset download guidance
    assert "/demo/people.csv" in body
    assert "## Downloading the full dataset" in body
    assert "/demo/people.csv?_stream=on" in body
    # the JSON paging option is not offered; CSV is the lightweight full download
    assert "_size=max" not in body
    assert "next_url" not in body
    # db is mutable in tests, so the whole-file .db download is not advertised
    assert "/demo.db`" not in body
    # sample rows present by default
    assert "## Sample rows" in body
    assert "Ada" in body


@pytest.mark.asyncio
async def test_column_notes_omitted_without_descriptions(db_path):
    """With no column metadata, the schema is enough; add no column notes."""
    ds = Datasette([db_path])
    body = (await ds.client.get("/demo/people/llms.txt")).text
    assert "CREATE TABLE" in body
    assert "## Column notes" not in body


@pytest.mark.asyncio
async def test_description_newlines_do_not_break_layout(db_path):
    """Metadata descriptions with stray newlines must not split bullets or add
    blank lines inside a list. Each description stays on its own single line."""
    metadata = {
        "description": "Instance summary.\n",
        "databases": {
            "demo": {
                "description": "A demo database\nwith a wrapped description.\n",
                "tables": {
                    "people": {"description": "One row per person.\n"},
                    "dogs": {"description": "\n  Good dogs.  \n"},
                },
            }
        },
    }
    ds = Datasette([db_path], metadata=metadata)

    body = (await ds.client.get("/llms.txt")).text
    # No blank line ever opens up inside a list because of a trailing newline.
    assert "\n\n\n" not in body
    # The wrapped database description is collapsed onto the one bullet line.
    assert (
        "- [demo](/demo.md): A demo database with a wrapped description." in body
    )
    # Table bullets stay single-line and keep their row-count prefix.
    assert "- [demo/people](/demo/people.md): 3 rows; One row per person." in body
    assert "- [demo/dogs](/demo/dogs.md): 2 rows; Good dogs." in body

    # The `>` summary blockquote carries no embedded newline either.
    table_body = (await ds.client.get("/demo/people/llms.txt")).text
    assert "> One row per person." in table_body


@pytest.mark.skipif(
    HAS_V1_METADATA,
    reason="dict-form column metadata is a Datasette <1.0 input shape; "
    "the 1.0 metadata store cannot load nested dict column values",
)
@pytest.mark.asyncio
async def test_table_dict_column_metadata(db_path, metadata):
    # Datasette also allows the dict form: columns: {email: {description: ...}}.
    metadata["databases"]["demo"]["tables"]["people"]["columns"] = {
        "email": {"description": "Contact address."}
    }
    ds = Datasette([db_path], metadata=metadata)
    body = (await ds.client.get("/demo/people/llms.txt")).text
    assert "Contact address." in body
    # the raw dict must not leak into the rendered output
    assert "{'description'" not in body


@pytest.mark.asyncio
async def test_db_download_advertised_when_immutable(db_path):
    # An immutable, on-disk database can be downloaded whole; the link should show.
    ds = Datasette(immutables=[db_path])
    body = (await ds.client.get("/demo/people/llms.txt")).text
    assert "/demo.db`" in body
    db_body = (await ds.client.get("/demo/llms.txt")).text
    assert "/demo.db`" in db_body


@pytest.mark.asyncio
async def test_route_precedence(db_path):
    """`/demo/llms.txt` must hit our handler, not a table named 'llms'."""
    ds = Datasette([db_path])
    response = await ds.client.get("/demo/llms.txt")
    assert response.status_code == 200
    assert response.text.startswith("# demo")


@pytest.mark.asyncio
async def test_markdown_endpoints(db_path, metadata):
    """`.md` resource pages serve markdown and match their `llms.txt` twins."""
    ds = Datasette([db_path], metadata=metadata)

    db_md = await ds.client.get("/demo.md")
    assert db_md.status_code == 200
    assert db_md.headers["content-type"].startswith("text/markdown")
    assert db_md.text == (await ds.client.get("/demo/llms.txt")).text

    table_md = await ds.client.get("/demo/people.md")
    assert table_md.status_code == 200
    assert table_md.headers["content-type"].startswith("text/markdown")
    assert table_md.text == (await ds.client.get("/demo/people/llms.txt")).text


@pytest.mark.asyncio
async def test_llms_txt_routes_still_work(db_path):
    """The nested `llms.txt` routes remain for back-compat."""
    ds = Datasette([db_path])
    assert (await ds.client.get("/demo/llms.txt")).status_code == 200
    assert (await ds.client.get("/demo/people/llms.txt")).status_code == 200


@pytest.mark.asyncio
async def test_markdown_not_found(db_path):
    ds = Datasette([db_path])
    assert (await ds.client.get("/nope.md")).status_code == 404
    assert (await ds.client.get("/demo/nope.md")).status_code == 404


@pytest.mark.asyncio
async def test_sample_rows_disabled(db_path):
    ds = Datasette(
        [db_path],
        metadata={"plugins": {"datasette-llms-txt": {"sample_rows": 0}}},
    )
    response = await ds.client.get("/demo/people/llms.txt")
    assert response.status_code == 200
    assert "## Sample rows" not in response.text


@pytest.mark.asyncio
async def test_internal_and_hidden_excluded(db_path):
    ds = Datasette([db_path])
    body = (await ds.client.get("/llms.txt")).text
    assert "_internal" not in body
    # FTS companion tables are hidden and must not appear
    assert "people_fts" not in body


@pytest.mark.asyncio
async def test_not_found(db_path):
    ds = Datasette([db_path])
    assert (await ds.client.get("/nope/llms.txt")).status_code == 404
    assert (await ds.client.get("/demo/nope/llms.txt")).status_code == 404


@pytest.mark.asyncio
async def test_marimo_section_on_table(db_path):
    """The table page explains marimo analysis with a table-specific SQL cell."""
    ds = Datasette([db_path])
    body = (await ds.client.get("/demo/people/llms.txt")).text
    assert "## Analyze in a marimo notebook" in body
    assert "moutils[db]" in body
    assert "from moutils.db.datasette import DatasetteConnection" in body
    # the connection uses the real request host and this database
    assert 'DatasetteConnection("http://localhost", "demo")' in body
    # the SQL cell queries this table, not a placeholder
    assert "SELECT * FROM people LIMIT 10" in body
    assert "<table>" not in body


@pytest.mark.asyncio
async def test_marimo_section_on_database_uses_table_placeholder(db_path):
    """The database page has no single table, so the SQL cell uses a placeholder."""
    ds = Datasette([db_path])
    body = (await ds.client.get("/demo/llms.txt")).text
    assert "## Analyze in a marimo notebook" in body
    assert "from moutils.db.datasette import DatasetteConnection" in body
    assert 'DatasetteConnection("http://localhost", "demo")' in body
    assert "SELECT * FROM <table> LIMIT 10" in body


@pytest.mark.asyncio
async def test_marimo_connection_url_respects_base_url_setting(db_path):
    """The connection URL includes the configured base_url path prefix."""
    ds = Datasette([db_path], settings={"base_url": "/prefix/"})
    body = (await ds.client.get("/demo/people/llms.txt")).text
    assert 'DatasetteConnection("http://localhost/prefix", "demo")' in body


@pytest.mark.asyncio
async def test_plugin_registered(db_path):
    ds = Datasette([db_path])
    response = await ds.client.get("/-/plugins.json")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert "datasette-llms-txt" in names
