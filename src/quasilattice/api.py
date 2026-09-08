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
import jwt
import nh3
import pwdlib
import pydantic

import quasilattice
import quasilattice.database
import quasilattice.markup

logger = logging.getLogger("quasilattice")

# code for generating uuids:
# random_uuid = uuid.uuid4() # generate a random uuid
# random_uuid_str = str(random_uuid) # as str
# random_uuid_bytes = random_uuid.bytes
# entry_uuid = uuid.UUID(random_uuid_str) # from str
# entry_uuid = uuid.UUID(bytes=random_uuid_bytes) # from bytes

password_hash = pwdlib.PasswordHash.recommended()
oauth2_scheme = fastapi.security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
)

app = fastapi.FastAPI()

_PBKDF2_ITERATIONS = 400000


class EditorResponse(pydantic.BaseModel):
    content: str


def verify_password_hash(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_password_hash(password: str) -> str:
    return password_hash.hash(password)


def generate_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key_hash(api_key: str, hashed_api_key: str) -> bool:
    return secrets.compare_digest(generate_api_key_hash(api_key), hashed_api_key)


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


@app.get("/api/access/{entry_alias}")
def get_access():
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


@app.get("/api/read_access/{entry_alias}")
def get_read_access():
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


@app.get("/api/write_access/{entry_alias}")
def get_write_access():
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


@app.get("/api/html/{entry_alias}")
def get_entry_html(entry_alias: str, q: str | None = None):
    """Returns the rendered html of an entry. Renders the markup_language specified by the entry to html."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        return fastapi.responses.HTMLResponse(
            quasilattice.markup.render_entry_to_html(cursor, entry_dict)
        )


@app.get("/api/markup/{entry_alias}")
def get_entry_markup_content(entry_alias: str, q: str | None = None):
    """Returns the original markup content of an entry."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        if "content" not in entry_dict or not isinstance(entry_dict["content"], str):
            return quasilattice.database.calculate_canonical_entry_bytes_from_dict(
                entry_dict
            ).decode("utf-8")
        return fastapi.responses.HTMLResponse(html.escape(entry_dict["content"]))


@app.get("/viewer/{entry_alias}")
def get_entry_viewer(entry_alias: str):
    """Returns the rendered html of an entry, with a shortcut to return to the editor. Renders the markup_language specified by the entry to html."""
    original_entry_alias = entry_alias
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        return fastapi.responses.HTMLResponse(
            quasilattice.markup.render_entry_to_html(cursor, entry_dict)
            + """<script>
  const TARGET_URL = "/editor/"""
            + original_entry_alias
            + """";
  document.addEventListener("keydown", async (e) => {
    if (e.key === "Enter" && e.shiftKey) {
      e.preventDefault();
      window.location.href = TARGET_URL;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      window.location.href = "/";
    }
  });
</script>"""
        )


@app.post("/editor/{entry_alias}")  # these should be considered temporary
def post_entry_json(entry_alias: str, response: EditorResponse):
    """Write content to an entry."""
    original_entry_alias = entry_alias
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            entry_dict = {
                "title": original_entry_alias,
                "is_file": False,
                "markup_language": "markdown",
                "uuid": str(uuid.uuid4()),
            }
        if "content" not in entry_dict or (entry_dict["content"] != response.content):
            entry_dict["content"] = response.content
            entry_dict["timestamp"] = time.time()
            quasilattice.database.write_entry_dict(cursor, entry_dict, "http_user")
            if quasilattice.config["quasilattice"]["generate_default_aliases"]:
                quasilattice.database.write_default_alias_by_uuid(
                    cursor,
                    bytes.fromhex(entry_dict["uuid"]),
                    "http_user",
                )

            # add an alias to this title is it doesn't exist (ignoring UUIDs and hashes)
            try:
                original_entry_alias_bytes = bytes.fromhex(
                    "".join(c for c in entry_alias if c in "0123456789abcdefABCDEF")
                )
            except (TypeError, ValueError):
                original_entry_alias_bytes = b""
            if len(original_entry_alias_bytes) not in [16, 32]:
                alias_row = quasilattice.database.read_alias_row(
                    cursor, original_entry_alias
                )
                if alias_row is None or (
                    alias_row["entry_uuid"] is None and alias_row["entry_hash"] is None
                ):
                    quasilattice.database.add_alias_by_uuid(
                        cursor,
                        bytes.fromhex(entry_dict["uuid"]),
                        original_entry_alias,
                        "http_user",
                    )
            connection.commit()
    return 200


@app.get("/editor/{entry_alias}")  # these should be considered temporary
def get_entry_editor(entry_alias: str):
    original_entry_alias = entry_alias
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            entry_dict = {"content": "", "uuid": ""}  # Stupid hack, TODO: remove this
        if "uuid" not in entry_dict:
            return quasilattice.database.calculate_canonical_entry_bytes_from_dict(
                entry_dict
            ).decode("utf-8")
        if "content" not in entry_dict or not isinstance(entry_dict["content"], str):
            entry_dict["content"] = ""

        output = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>"""
        output += original_entry_alias
        output += """</title>
<style>
  html, body {
    margin: 0;
    padding: 0;
  }
  textarea {
    display: block;
    width: 100vw;
    min-height: 100vh;
    border: none;
    outline: none;
    resize: none;
    font-size: 16px;
    padding: 16px;
    box-sizing: border-box;
    font-family: system-ui, sans-serif;
    overflow: hidden;
  }
</style>
</head>
<body>
<textarea id="box" placeholder="Type here… Shift+Enter to save changes" autofocus>"""
        output += html.escape(entry_dict["content"])
        output += """</textarea>

<script>
  const TARGET_URL = "/viewer/"""
        output += original_entry_alias
        output += """";
  const POST_URL = "/editor/"""
        output += original_entry_alias
        output += """";

  const box = document.getElementById("box");

  function autoResize() {
    box.style.height = "auto";
    box.style.height = box.scrollHeight + "px";
  }

  box.addEventListener("input", autoResize);
  autoResize();

  box.addEventListener("keydown", async (e) => {
    if (e.key === "Enter" && e.shiftKey) {
      e.preventDefault();
      const content = box.value;

      try {
        const res = await fetch(POST_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content })
        });

        if (res.ok) {
          window.location.href = TARGET_URL;
        }
      } catch (err) {
        console.log(err)
      }
    }
  });
</script>
</body>
</html>"""
        return fastapi.responses.HTMLResponse(output)


@app.get("/api/json/{entry_alias}")
def get_entry_json(entry_alias: str, q: str | None = None):
    """Returns the canonical json for one or more entries."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        return quasilattice.database.read_entry_by_id(cursor, entry_alias)


@app.get("/api/hash/{entry_alias}")
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


@app.get("/{entry_alias}")
def get_entry(entry_alias: str):
    """Returns the rendered html of an entry or the raw file contents if is_file is true."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, uuid.UUID):
            entry_alias = entry_alias.bytes
        elif isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        entry_dict = quasilattice.database.read_entry_by_id(cursor, entry_alias)
        if entry_dict is None:
            file_dir = os.path.join(
                quasilattice.config["quasilattice"]["files_dir"], entry_alias.hex()[0:3]
            )
            file_path = os.path.join(file_dir, entry_alias.hex() + ".file")
            if os.path.isfile(file_path):
                return fastapi.responses.FileResponse(file_path)
            else:
                raise fastapi.HTTPException(status_code=404, detail="Entry not found")
        if "file_hash" not in entry_dict or not isinstance(
            entry_dict["file_hash"], str
        ):
            return fastapi.responses.HTMLResponse(
                quasilattice.markup.render_entry_to_html(cursor, entry_dict)
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
        description="QuasiLattice (or Lattice for short) is a data analysis, knowledge base, journaling and note taking system built on a simple RESTful API.",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = quasilattice_openapi
