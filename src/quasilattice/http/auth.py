import hashlib
import logging
import os
import secrets

import fastapi
import fastapi.responses
import fastapi.security
import fastapi.templating
import pwdlib

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

_TEMPLATE_DIR = os.path.join(_PACKAGE_DIR, "templates")

logger = logging.getLogger("quasilattice")

password_hash = pwdlib.PasswordHash.recommended()
oauth2_scheme = fastapi.security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
)

router = fastapi.APIRouter()

templates = fastapi.templating.Jinja2Templates(directory=_TEMPLATE_DIR)


def verify_password_hash(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_password_hash(password: str) -> str:
    return password_hash.hash(password)


def generate_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key_hash(api_key: str, hashed_api_key: str) -> bool:
    return secrets.compare_digest(generate_api_key_hash(api_key), hashed_api_key)


# region login
@router.get("/auth/login")
def get_auth_login():
    return "login page"


@router.get("/auth/logout")
def get_auth_logout():
    return "logout then redirect to /"
    return fastapi.responses.RedirectResponse(url="/", status_code=303)


@router.get("/auth/profile")
def get_auth_profile():
    return "render profile page"


@router.post("/api/login")
def post_api_login():
    return "TODO: Implement login api"


@router.post("/api/logout")
def post_api_logout():
    return "TODO: Implement logout api"


# endregion


# region users
@router.get("/api/users")
def get_users():  # only allowed for admin
    return "TODO: Implement get users"


@router.post("/api/users")
def post_user():  # only allowed for admin
    return "TODO: Implement post user"


@router.put("/api/users/{user}")
def put_user(user: str):  # only allowed for admin
    return "TODO: Implement update or create complete user"


@router.patch("/api/users/{user}")
def patch_user(user: str):  # only allowed for admin
    return "TODO: Implement partially update user"


@router.delete("/api/users/{user}")
def delete_user(user: str):  # only allowed for admin
    return "TODO: Implement delete user"


# endregion


# region keys
@router.get("/api/keys")
def get_api_keys():
    return "TODO: Implement get api_keys"
    # return {
    #    "key_id": {"note": "STM upload system.", "owner": "stm1"},
    #    "other_key_id": {
    #        "note": "STM upload system.",
    #        "owner": "stm1", # note: don't include owner unless the user is admin
    #    },
    # }


@router.post("/api/keys")
def post_api_key():
    return "TODO: Implement create new API KEY"


@router.put("/api/keys/{key_id}")
def put_api_key(key_id: str):
    return "TODO: update existing api key"


@router.patch("/api/keys/{user}")
def patch_api_key(user: str):  # only allowed for admin
    return "TODO: Implement partially update api key"


@router.delete("/api/users/{user}")
def delete_api_key(user: str):  # only allowed for admin
    return "TODO: Implement delete api key"


# endregion


# region access


@router.get("/api/access/{entry_alias:path}")
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


@router.post("/api/access/{entry_alias:path}")
@router.put("/api/access/{entry_alias:path}")
def post_access(entry_alias: str):
    return "TODO: Implement set access to entry"


@router.patch("/api/access/{entry_alias:path}")
def patch_access(entry_alias: str):
    return "TODO: Implement add access to entry"


@router.delete("/api/access/{entry_alias:path}")
def delete_access(entry_alias: str):
    return "TODO: Implement remove access to entry"


# endregion


# region read_access


@router.get("/api/read_access/{entry_alias:path}")
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


@router.post("/api/read_access/{entry_alias:path}")
@router.put("/api/read_access/{entry_alias:path}")
def post_read_access(entry_alias: str):
    return "TODO: Implement set read_access to entry"


@router.patch("/api/read_access/{entry_alias:path}")
def patch_read_access(entry_alias: str):
    return "TODO: Implement add read_access to entry"


@router.delete("/api/read_access/{entry_alias:path}")
def delete_read_access(entry_alias: str):
    return "TODO: Implement remove read_access to entry"


# endregion


# region write_access


@router.get("/api/write_access/{entry_alias:path}")
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


@router.post("/api/write_access/{entry_alias:path}")
@router.put("/api/write_access/{entry_alias:path}")
def post_write_access(entry_alias: str):
    return "TODO: Implement set write_access to entry"


@router.patch("/api/write_access/{entry_alias:path}")
def patch_write_access(entry_alias: str):
    return "TODO: Implement add write_access to entry"


@router.delete("/api/write_access/{entry_alias:path}")
def delete_write_access(entry_alias: str):
    return "TODO: Implement remove write_access to entry"


# endregion
