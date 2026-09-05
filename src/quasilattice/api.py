from __future__ import annotations

import hashlib
import secrets
import typing
import uuid

import fastapi
import fastapi.security
import jwt
import pwdlib

import quasilattice

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


def verify_password_hash(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_password_hash(password: str) -> str:
    return password_hash.hash(password)


def generate_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key_hash(api_key: str, hashed_api_key: str) -> bool:
    return secrets.compare_digest(generate_api_key_hash(api_key), hashed_api_key)


# TODO: implement login()
# TODO: logout()
# TODO: get_current_user()
# TODO: is_admin()
# TODO: has_read_permission(entry_uuid)
# TODO: has_write_permission(entry_uuid)


@app.get("/api")
def get_api():
    return app.openapi()


@app.get("/api/login")
def get_login():
    return "TODO: IMPLEMENT LOGIN"


@app.get("/api/logout")
def get_logout():
    return "TODO: IMPLEMENT LOGOUT"


@app.get("/api/users") # MAKE THIS MORE RESTful
def get_users(): # only allowed for admin
    return ["kaedon", "stm1_scanning_computer"]


@app.get("/api/keys")
def get_api_keys():
    return {
        "key_id": {"note": "STM upload system.", "owner": "stm1"},
        "other_key_id": {
            "note": "STM upload system.",
            "owner": "stm1", # note: don't include owner unless the user is admin
        },
    }


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
    return "access"


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
    return "read_access"


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
    return "write_access"


@app.get("/api/html/{entry_alias}")
def get_entry_html(entry_alias: str, q: str | None = None):
    """Returns the rendered html of an entry. Renders the markup_language specified by the entry to html."""
    return "html"


@app.get("/api/markup/{entry_alias}")
def get_entry_markup_content(entry_alias: str, q: str | None = None):
    """Returns the original markup content of an entry."""
    return "md"


@app.get("/api/json/{entry_alias}")
def get_entry_json(entry_alias: str, q: str | None = None):
    """Returns the canonical json for one or more entries."""


@app.get("/api/hash/{entry_alias}")
def get_entry_hash(entry_alias: str, q: str | None = None):
    """Returns the hash of one or more entries in hexidecimal.

    Example for one entry: "1b378cf8139cf3719387c917cf9f1743002568"

    Example for multiple entries:
    {"uuid":"1b378cf8139cf3719387c917cf9f1743002568","uuid":"1b378cf8139cf3719387c917cf9f1743002568"}

    """
    return


@app.get("/api/hash_list")
def get_hash_list():
    """Returns a list of hashes for available entries. A specific range

    Example for one entry: "1b378cf8139cf3719387c917cf9f1743002568"

    Example for multiple entries:
    {"uuid":"1b378cf8139cf3719387c917cf9f1743002568","uuid":"1b378cf8139cf3719387c917cf9f1743002568"}

    """
    return


@app.get("/{entry_alias}")
def get_entry(entry_alias: str, q: str | None = None):
    """Returns the rendered html of an entry or the raw file contents if is_file is true."""
    return {"alias": entry_alias, "q": q}


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
