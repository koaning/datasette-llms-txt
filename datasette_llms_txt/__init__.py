from datasette import hookimpl, Response
from datasette.utils import tilde_decode

from .generate import generate_database, generate_index, generate_table


async def _index(datasette):
    return Response.text(await generate_index(datasette))


async def _database(datasette, request):
    db_name = tilde_decode(request.url_vars["db"])
    if db_name not in _visible_databases(datasette):
        return Response.text("Database not found\n", status=404)
    return Response.text(await generate_database(datasette, db_name))


async def _table(datasette, request):
    db_name = tilde_decode(request.url_vars["db"])
    table = tilde_decode(request.url_vars["table"])
    if db_name not in _visible_databases(datasette):
        return Response.text("Database not found\n", status=404)
    db = datasette.databases[db_name]
    if not await db.table_exists(table):
        return Response.text("Table not found\n", status=404)
    return Response.text(await generate_table(datasette, db_name, table))


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
    ]


@hookimpl
def menu_links(datasette, actor):
    return [{"href": datasette.urls.path("/llms.txt"), "label": "llms.txt"}]
