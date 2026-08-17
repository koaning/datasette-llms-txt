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


@pytest.mark.asyncio
async def test_table(db_path, metadata):
    ds = Datasette([db_path], metadata=metadata)
    response = await ds.client.get("/demo/people/llms.txt")
    assert response.status_code == 200
    body = response.text
    assert body.startswith("# demo/people")
    assert "> One row per person." in body
    assert "CREATE TABLE" in body
    assert "Primary key: `id`" in body
    assert "## Columns" in body
    assert "`name`" in body
    # column description from metadata appears on the email line
    assert "`email`" in body
    assert "Contact address." in body
    assert "## Querying" in body
    assert "/demo/people.json" in body
    # CSV export and full-dataset download guidance
    assert "/demo/people.csv" in body
    assert "## Downloading the full dataset" in body
    assert "/demo/people.csv?_stream=on" in body
    # db is mutable in tests, so the whole-file .db download is not advertised
    assert "/demo.db`" not in body
    # sample rows present by default
    assert "## Sample rows" in body
    assert "Ada" in body


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
async def test_plugin_registered(db_path):
    ds = Datasette([db_path])
    response = await ds.client.get("/-/plugins.json")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert "datasette-llms-txt" in names
