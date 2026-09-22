from __future__ import annotations

import html
import json
import logging
import os
import time
import typing
import uuid

import fastapi
import fastapi.responses
import fastapi.templating
import nh3
import pwdlib

import quasilattice
import quasilattice.database
import quasilattice.markup

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

_THEMES_DIR = os.path.join(_PACKAGE_DIR, "themes")

_KATEX_DIR = os.path.join(_PACKAGE_DIR, "katex")

_TEMPLATE_DIR = os.path.join(_PACKAGE_DIR, "templates")

logger = logging.getLogger("quasilattice")

router = fastapi.APIRouter()

templates = fastapi.templating.Jinja2Templates(directory=_TEMPLATE_DIR)


def _is_full_html_document(markup: str) -> bool:
    prefix = markup.lstrip().lstrip("\ufeff")[:512].lower()
    return prefix.startswith(("<!doctype html", "<html"))


@router.get("/api/entry/json")
@router.get("/api/entries/json")
@router.get("/api/entry/json/{entry_alias:path}")
@router.get("/api/entries/json/{entry_alias:path}")
def get_entry_json(entry_alias: str | None = None, q: str | None = None):
    """Returns the canonical json for an entry."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found.")
        return entry_dict

@router.post("/api/entry/json")
@router.post("/api/entries/json")
@router.post("/api/entry/json/{entry_alias:path}")
@router.post("/api/entries/json/{entry_alias:path}")
@router.put("/api/entry/json")
@router.put("/api/entries/json")
@router.put("/api/entry/json/{entry_alias:path}")
@router.put("/api/entries/json/{entry_alias:path}")
def put_entry_json(request: fastapi.Request, entry_alias: str | None = None):
    # TODO: check write access
    return "TODO: implement create entry"

@router.patch("/api/entry/json/{entry_alias:path}")
@router.patch("/api/entries/json/{entry_alias:path}")
def patch_entry_json(request: fastapi.Request, entry_alias: str | None = None):
    return "TODO: implement patch entry"

@router.delete("/api/entry/json/{entry_alias:path}")
@router.delete("/api/entries/json/{entry_alias:path}")
def delete_entry_json(request: fastapi.Request, entry_alias: str | None = None):
    return "TODO: implement delete entry"


@router.get("/api/entry/html")
@router.get("/api/entries/html")
@router.get("/api/entry/html/{entry_alias:path}")
@router.get("/api/entries/html/{entry_alias:path}")
def get_entry_html(request: fastapi.Request, entry_alias: str | None = None, q: str | None = None):
    """Returns the rendered html of an entry. Renders the markup_language specified by the entry to html."""
    if entry_alias is None:
        # TODO: check the request body for an entry alias
        raise fastapi.HTTPException(status_code=404, detail="Entry not found")
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_id)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        entry_html = quasilattice.markup.render_entry_to_html(cursor, entry_dict)
        if _is_full_html_document(entry_html):
            return fastapi.responses.HTMLResponse(
                quasilattice.markup.html_cleaner(entry_html)
            )
        else:
            return templates.TemplateResponse(
                request=request,
                name="viewer.html",
                context={
                    "title": entry_dict.get("title", entry_alias),
                    "metadata": entry_dict,
                    "body": entry_html,
                },
            )


@router.get("/api/entry/hash")
@router.get("/api/entries/hash")
@router.get("/api/entry/hash/{entry_alias:path}")
@router.get("/api/entries/hash/{entry_alias:path}")
def get_entry_hash(entry_alias: str | None = None, q: str | None = None):
    """Returns the hash of one or more entries in hexidecimal.

    Example for one entry: "1b378cf8139cf3719387c917cf9f1743002568"

    Example for multiple entries:
    {"uuid":"1b378cf8139cf3719387c917cf9f1743002568","uuid":"1b378cf8139cf3719387c917cf9f1743002568"}

    """
    return "TODO: Implement get entry hash"


@router.get("/api/hash_list")
def get_hash_list():
    """Returns a list of hashes for available entries. A specific range ordered by timestamp or hash
    """
    return "TODO: Implement get hash list"


@router.get("/themes/default.css")
async def css_default():
    return fastapi.responses.FileResponse(os.path.join(_THEMES_DIR, "default.css"))


@router.get("/themes/default-light.css")
async def css_default_light():
    return fastapi.responses.FileResponse(os.path.join(_THEMES_DIR, "default-light.css"))


@router.get("/themes/default-dark.css")
async def css_default_dark():
    return fastapi.responses.FileResponse(os.path.join(_THEMES_DIR, "default-dark.css"))


@router.get("/katex/katex.min.js")
async def katex_js():
    return fastapi.responses.FileResponse(os.path.join(_KATEX_DIR, "katex.min.js"))


@router.get("/katex/katex.min.css")
async def katex_css():
    return fastapi.responses.FileResponse(os.path.join(_KATEX_DIR, "katex.min.css"))


@router.get("/katex/contrib/auto-render.min.js")
async def katex_auto_render():
    return fastapi.responses.FileResponse(
        os.path.join(_KATEX_DIR, "contrib", "auto-render.min.js")
    )


@router.get("/{entry_alias:path}")
def get_entry(request: fastapi.Request, entry_alias: str):
    """Returns the rendered html of an entry or the raw file contents if is_file is true."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_id)
        print(entry_alias)
        if entry_dict is None:
            file_dir = os.path.join(
                quasilattice.config["quasilattice"]["files_dir"], entry_id.hex()[0:3]
            )
            file_path = os.path.join(file_dir, entry_id.hex() + ".file")
            if os.path.isfile(file_path):  # TODO: check access
                return fastapi.responses.FileResponse(file_path)
            else:
                raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        if "file_hash" not in entry_dict or not isinstance(
            entry_dict["file_hash"], str
        ):
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
        else:
            file_dir = os.path.join(
                quasilattice.config["quasilattice"]["files_dir"],
                entry_dict["file_hash"][
                    0:3
                ],  # TODO: fix arbitrary file path vulnerability (restrict file_hash to hex characters)
            )
            file_path = os.path.join(
                file_dir, entry_dict["file_hash"] + ".file"
            )  # TODO: fix arbitrary file path vulnerability (restrict file_hash to hex characters)
            if os.path.isfile(file_path):
                if "file_name" in entry_dict and isinstance(
                    entry_dict["file_name"], str
                ):
                    return fastapi.responses.FileResponse(
                        file_path,
                        filename=entry_dict["file_name"],
                    )
                else:
                    return fastapi.responses.FileResponse(
                        file_path,
                    )
