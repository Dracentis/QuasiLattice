from __future__ import annotations

import json
import logging
import os
import time
import uuid

import fastapi
import fastapi.templating
import nh3

import quasilattice

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

_TEMPLATE_DIR = os.path.join(_PACKAGE_DIR, "templates")

logger = logging.getLogger("quasilattice")

router = fastapi.APIRouter()

templates = fastapi.templating.Jinja2Templates(directory=_TEMPLATE_DIR)

@router.get("/", response_class=fastapi.responses.HTMLResponse)
@router.get("/editor", response_class=fastapi.responses.HTMLResponse)
def get_index(request: fastapi.Request, q: str | None = None):
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_aliases = quasilattice.database.read_aliases_before_time(
            cursor, time.time(), 10000
        )
        entry_uuids = quasilattice.database.read_entry_uuids(cursor, 10000)
        entry_hashes = quasilattice.database.read_entry_hashes(cursor, 10000)
    long_entry_aliases = [
        f'<li><a href="/{nh3.clean(alias)}">{nh3.clean(alias)}</a>&nbsp;<a href="/editor/{nh3.clean(alias)}">edit</a></li>'
        for alias in entry_aliases
        if len(alias) > quasilattice.current_default_alias_length
    ]
    short_entry_aliases = [
        f'<li><a href="/{nh3.clean(alias)}">{nh3.clean(alias)}</a>&nbsp;<a href="/editor/{nh3.clean(alias)}">edit</a></li>'
        for alias in entry_aliases
        if len(alias) <= quasilattice.current_default_alias_length
    ]
    entry_uuids = [
        f'<li><a href="/{uuid.UUID(bytes=uuid_bytes)!s}">{uuid.UUID(bytes=uuid_bytes)!s}</a>&nbsp;<a href="/editor/{uuid.UUID(bytes=uuid_bytes)!s}">edit</a></li>'
        for uuid_bytes in entry_uuids
    ]
    entry_hashes = [
        f'<li><a href="/{hash.hex()}">{hash.hex()}</a></li>' for hash in entry_hashes
    ]
    return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "version": quasilattice.__version__
            },
        )

@router.get("/editor/{entry_alias:path}")
def get_editor(request: fastapi.Request, entry_alias: str):
    """Returns the rendered html of an entry or the raw file contents if is_file is true."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_id)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        entry_html = quasilattice.markup.render_entry_to_html(cursor, entry_dict)
        return templates.TemplateResponse(
            request=request,
            name="editor.html",
            context={
                "title": entry_dict.get("title", entry_alias),
                "entry_alias": entry_alias,
                "entry_json": json.dumps(entry_dict, indent=4),
                "metadata": entry_dict,
                "entries": {},
                "body": entry_html,
            },
        )