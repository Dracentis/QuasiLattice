from __future__ import annotations

import hashlib
import html
import logging
import os
import secrets
import time
import typing
import uuid

import fastapi
import fastapi.responses
import fastapi.security
import fastapi.templating
import jwt
import nh3
import pwdlib
import pydantic

import quasilattice
import quasilattice.database
import quasilattice.markup

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

_KATEX_DIR = os.path.join(_PACKAGE_DIR, "katex")

_TEMPLATE_DIR = os.path.join(_PACKAGE_DIR, "templates")

logger = logging.getLogger("quasilattice")

password_hash = pwdlib.PasswordHash.recommended()
oauth2_scheme = fastapi.security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
)

app = fastapi.FastAPI()

templates = fastapi.templating.Jinja2Templates(directory=_TEMPLATE_DIR)


def verify_password_hash(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_password_hash(password: str) -> str:
    return password_hash.hash(password)


def generate_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key_hash(api_key: str, hashed_api_key: str) -> bool:
    return secrets.compare_digest(generate_api_key_hash(api_key), hashed_api_key)


def _is_full_html_document(markup: str) -> bool:
    prefix = markup.lstrip().lstrip("\ufeff")[:512].lower()
    return prefix.startswith(("<!doctype html", "<html"))


# TODO: login()
# TODO: logout()
# TODO: get_current_user()
# TODO: is_admin()
# TODO: enforce read and write access


@app.get("/api")
def get_api():
    return app.openapi()


@app.get("/api/login")
def get_login():
    return "TODO: Implement login"


@app.get("/api/logout")
def get_logout():
    return "TODO: Implement logout"


@app.get("/api/users")
def get_users():  # only allowed for admin
    return "TODO: Implement get users"


@app.get("/api/keys")
def get_api_keys():
    return "TODO: Implement get api_keys"
    # return {
    #    "key_id": {"note": "STM upload system.", "owner": "stm1"},
    #    "other_key_id": {
    #        "note": "STM upload system.",
    #        "owner": "stm1", # note: don't include owner unless the user is admin
    #    },
    # }


@app.get("/api/access/{entry_alias:path}")
def get_access(entry_alias: str):
    """Returns a dictionary of read_access and write_access for one or more entries.

    Example for one entry:
    {
        "read_access":{
            "read_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        },
        "write_access":{
            "write_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        }
    }

    Example for multiple entries:
    {
        "fa859ba85-498223aa2-46239236-5y3573753":{
            "read_access":{
                "read_access":["kaedon","thz"],
                "time_edited":[156462236,161636234]
            },
            "write_access":{
                "write_access":["kaedon","thz"],
                "time_edited":[156462236,161636234]
            }
        }
        "ab7920626-4316af326-2624309ed-473254ce1":{
            "read_access":{
                "read_access":["kaedon","thz"],
                "time_edited":[156462236,161636234]
            },
            "write_access":{
                "write_access":["kaedon","thz"],
                "time_edited":[156462236,161636234]
            }
        }
    }
    """
    return "TODO: Implement get access"


@app.get("/api/read_access/{entry_alias:path}")
def get_read_access(entry_alias: str):
    """Returns a dictionary of read_access for one or more entries.

    Example for one entry:
    {
        "read_access":["kaedon","thz"],
        "time_edited":[156462236,161636234]
    }

    Example for multiple entries:
    {
        "fa859ba85-498223aa2-46239236-5y3573753":{
            "read_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        },
        "ab7920626-4316af326-2624309ed-473254ce1":{
            "read_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        }
    }
    """
    return "TODO: Implement get read_access"


@app.get("/api/write_access/{entry_alias:path}")
def get_write_access(entry_alias: str):
    """Returns a dictionary of write_access for one or more entries.

    Example for one entry:
    {
        "write_access":["kaedon","thz"],
        "time_edited":[156462236,161636234]
    }

    Example for multiple entries:
    {
        "fa859ba85-498223aa2-46239236-5y3573753":{
            "write_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        },
        "ab7920626-4316af326-2624309ed-473254ce1":{
            "write_access":["kaedon","thz"],
            "time_edited":[156462236,161636234]
        }
    }
    """
    return "TODO: Implement get write_access"


@app.get("/api/html/{entry_alias:path}")
def get_entry_html(request: fastapi.Request, entry_alias: str, q: str | None = None):
    """Returns the rendered html of an entry. Renders the markup_language specified by the entry to html."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_id)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        return templates.TemplateResponse(
            request=request,
            name="viewer.html",
            context={
                "title": entry_dict.get("title", entry_alias),
                "body": quasilattice.markup.render_entry_to_html(cursor, entry_dict),
            },
        )


@app.get("/api/json/{entry_alias:path}")
def get_entry_json(entry_alias: str, q: str | None = None):
    """Returns the canonical json for one or more entries."""
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


@app.get("/api/hash/{entry_alias:path}")
def get_entry_hash(entry_alias: str, q: str | None = None):
    """Returns the hash of one or more entries in hexidecimal.

    Example for one entry: "1b378cf8139cf3719387c917cf9f1743002568"

    Example for multiple entries:
    {"uuid":"1b378cf8139cf3719387c917cf9f1743002568","uuid":"1b378cf8139cf3719387c917cf9f1743002568"}

    """
    return "TODO: Implement get entry hash"


@app.get("/api/hash_list")
def get_hash_list():
    """Returns a list of hashes for available entries. A specific range

    Example for one entry: "1b378cf8139cf3719387c917cf9f1743002568"

    Example for multiple entries:
    {"uuid":"1b378cf8139cf3719387c917cf9f1743002568","uuid":"1b378cf8139cf3719387c917cf9f1743002568"}

    """
    return "TODO: Implement get hash list"


@app.get("/", response_class=fastapi.responses.HTMLResponse)
def get_index(q: str | None = None):
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
    return f"""
    <html>
        <head>
            <title>Welcome to QuasiLattice</title>
        </head>
        <body>
            <h1>Welcome to QuasiLattice</h1>
            You've successfully setup QuasiLattice!
            <h2>Entries by Aliases</h2>
            <ul>
            {"".join(long_entry_aliases)}
            </ul>
            <br/>
            <ul>
            {"".join(short_entry_aliases)}
            </ul>
            <br/>
            <h2>Entries by UUID</h2>
            <ul>
            {"".join(entry_uuids)}
            </ul>
            <br/>
            <h2>Entries by Hash</h2>
            <ul>
            {"".join(entry_hashes)}
            </ul>
            <br/>
        </body>
    </html>
    """


@app.get("/katex/katex.min.js")
async def katex_js():
    return fastapi.responses.FileResponse(os.path.join(_KATEX_DIR, "katex.min.js"))


@app.get("/katex/katex.min.css")
async def katex_css():
    return fastapi.responses.FileResponse(os.path.join(_KATEX_DIR, "katex.min.css"))


@app.get("/katex/contrib/auto-render.min.js")
async def katex_auto_render():
    return fastapi.responses.FileResponse(
        os.path.join(_KATEX_DIR, "contrib", "auto-render.min.js")
    )


@app.get("/{entry_alias:path}")
def get_entry(request: fastapi.Request, entry_alias: str):
    """Returns the rendered html of an entry or the raw file contents if is_file is true."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_id)
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
            return templates.TemplateResponse(
                request=request,
                name="viewer.html",
                context={
                    "title": entry_dict.get("title", entry_alias),
                    "body": quasilattice.markup.render_entry_to_html(
                        cursor, entry_dict
                    ),
                },
            )
        else:
            file_dir = os.path.join(
                quasilattice.config["quasilattice"]["files_dir"],
                entry_dict["file_hash"][0:3],
            )
            file_path = os.path.join(file_dir, entry_dict["file_hash"] + ".file")
            if os.path.isfile(file_path):
                if "file_name" in entry_dict:
                    file_name = entry_dict["file_name"]
                    return fastapi.responses.FileResponse(
                        file_path,
                        filename=file_name,
                    )
                else:
                    return fastapi.responses.FileResponse(
                        file_path,
                    )


def quasilattice_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = fastapi.openapi.utils.get_openapi(
        title="QuasiLattice",
        version=quasilattice.__version__,
        summary="A data analysis, knowledge base, journaling and note taking system.",
        description="""QuasiLattice (or Lattice for short) is a data analysis, knowledge base, journaling and note taking system built on a simple specification. This repository will contain a reference implementation written in Python, but it should be possible to build compatible QuasiLattice nodes in other languages or protocols other than HTTP.

QuasiLattice organizes data into "entries". Any file or JSON object is a valid QuasiLattice entry. Entries can contain a “content” string written in any markup language, which will be dynamically rendered when viewed.

Each QuasiLattice node maintains a list of entries and controls who has access to read and write to that list of entries.

Nodes can be configured to sync data with other nodes. This allows anybody to archive data from other QuasiLattice nodes. In protocols that support it, these mirrors provide bandwidth to reduce to load on the original source node and if the original source node fails then the data is still accessible. Every entry is canonically stored according to the JSON [RFC8785] subset, so hashes of entries can be compared between nodes.

QuasiLattice can also be configured in "archive_mode", where all changes to the entries are timestamped and nothing is deleted. In this mode, QuasiLattice can be used as an archival lab notebook for experimental research. Hashes of these entries could be proactively published online, cryptographically proving the timeline of scholarly work to third parties.""",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = quasilattice_openapi
