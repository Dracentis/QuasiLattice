import uuid
import hashlib
import secrets
import contextlib
import fastapi

import quasilattice
from . import database

# code for generating uuids:
# random_uuid = uuid.uuid4() # generate a random uuid
# random_uuid_str = str(random_uuid) # as str
# random_uuid_bytes = random_uuid.bytes
# entry_uuid = uuid.UUID(random_uuid_str) # from str
# entry_uuid = uuid.UUID(bytes=random_uuid_bytes) # from bytes

app = fastapi.FastAPI()

_PBKDF2_ITERATIONS = 400000

def generate_password_hash(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password_hash(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(expected_digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False

def generate_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

def verify_api_key_hash(api_key: str, api_key_hash: str) -> bool:
    return secrets.compare_digest(generate_api_key_hash(api_key), api_key_hash)

@app.get("/api")
def get_api():
    return app.openapi()

@app.get("/api/users")
def get_users():
    return ["kaedon","stm1_scanning_computer","stm2_scanning_computer"] # only allowed for admin

@app.get("/api/admins")
def get_users():
    return ["kaedon"] # only allowed for admin

@app.put("/api/password/{user}")
def put_password():
    return "passwords" # only allowed for admin

@app.get("/api/keys")
def get_api_keys():
    return {
        "key_id":{"note":"STM upload system.","owner":"stm1"},
        "other_key_id":{"note":"STM upload system.","owner":"stm1"}, # note: don't include owner unless the user is admin
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