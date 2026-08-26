from datasette import hookimpl, Response
from datasette.utils import tilde_decode

from .generate import generate_database, generate_index, generate_table


def _markdown(body):
    return Response(body, content_type="text/markdown; charset=utf-8")


async def _index(datasette, request):
    return Response.text(await generate_index(datasette, request))


async def _database_body(datasette, request):
    """Resolve the database and return its markdown body, or a 404 Response."""
    db_name = tilde_decode(request.url_vars["db"])
    if db_name not in _visible_databases(datasette):
        return Response.text("Database not found\n", status=404)
    return await generate_database(datasette, db_name, request)


async def _table_body(datasette, request):
    """Resolve the table and return its markdown body, or a 404 Response."""
    db_name = tilde_decode(request.url_vars["db"])
    table = tilde_decode(request.url_vars["table"])
    if db_name not in _visible_databases(datasette):
        return Response.text("Database not found\n", status=404)
    db = datasette.databases[db_name]
    if not await db.table_exists(table):
        return Response.text("Table not found\n", status=404)
    return await generate_table(datasette, db_name, table, request)


async def _database(datasette, request):
    body = await _database_body(datasette, request)
    return body if isinstance(body, Response) else Response.text(body)


async def _table(datasette, request):
    body = await _table_body(datasette, request)
    return body if isinstance(body, Response) else Response.text(body)


async def _database_md(datasette, request):
    body = await _database_body(datasette, request)
    return body if isinstance(body, Response) else _markdown(body)


async def _table_md(datasette, request):
    body = await _table_body(datasette, request)
    return body if isinstance(body, Response) else _markdown(body)


def _visible_databases(datasette):
    return {
        name
        for name in datasette.databases
        if name not in ("_internal", "_memory")
    }


@hookimpl
def register_routes():
    return [
        (r"^/llms\.txt$", _index),
        (r"^/(?P<db>[^/]+)/llms\.txt$", _database),
        (r"^/(?P<db>[^/]+)/(?P<table>[^/]+)/llms\.txt$", _table),
        (r"^/(?P<db>[^/]+)\.md$", _database_md),
        (r"^/(?P<db>[^/]+)/(?P<table>[^/]+)\.md$", _table_md),
    ]


@hookimpl
def menu_links(datasette, actor):
    return [{"href": datasette.urls.path("/llms.txt"), "label": "llms.txt"}]
