from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
import time
import typing
import uuid

import tomllib

import quasilattice.database

config = {}
config_path = os.path.expanduser("~/.quasilattice/config.toml")

current_default_alias_length = 1

sync_thread = None
last_sync_time = time.time()

logger = logging.getLogger("quasilattice")


class _LogFormatter(logging.Formatter):
    LEVEL_COLORS: typing.ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[41m",  # red background
    }

    COLOR_RESET = "\033[0m"

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno)
        original_levelname = record.levelname
        if color:
            record.levelname = f"{color}{original_levelname}{self.COLOR_RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


# init fallback logger
logger.setLevel(20)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(_LogFormatter("%(levelname)s %(name)s: \t%(message)s"))
logger.addHandler(stderr_handler)


def init(
    config_path: str | None = None,
    log_level: int | None = None,
    log_path: str | None = None,
    start_background_sync: bool = False,
    config_override: dict[str, typing.Any] | None = None,
):
    if config_path is None:
        if os.path.isdir("/etc/quasilattice") and os.path.isfile(
            "/etc/quasilattice/config.toml"
        ):
            config_path = "/etc/quasilattice/config.toml"
        elif os.path.isdir(
            os.path.expanduser("~/.config/quasilattice")
        ) and os.path.isfile(os.path.expanduser("~/.config/quasilattice/config.toml")):
            config_path = os.path.expanduser("~/.config/quasilattice/config.toml")
        else:
            config_path = os.path.expanduser("~/.quasilattice/config.toml")
    sys.modules[__name__].config_path = config_path

    # load config
    created_default_config = False
    if not os.path.isfile(config_path):
        write_default_config_file()
        created_default_config = True
    global config
    with open(config_path, "rb") as config_file:
        config = tomllib.load(config_file)
        config_file.close()
    if config_override is not None:
        config = config | config_override
    validate_config()
    if log_level is not None:
        config["logging"]["log_level"] = log_level
    if log_path is not None:
        config["logging"]["log_path"] = log_path

    # setup logging
    logger.setLevel(60 - config["logging"]["log_level"] * 10)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            handler.close()
    if config["logging"]["log_to_stderr"]:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(
            _LogFormatter("%(levelname)s %(name)s: \t%(message)s")
        )
        logger.addHandler(stderr_handler)
    if config["logging"]["log_to_file"]:
        log_dir = os.path.dirname(config["logging"]["log_path"])
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            config["logging"]["log_path"],
            maxBytes=config["logging"]["max_log_file_size_bytes"],
            backupCount=config["logging"]["log_file_backup_count"],
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: \t%(message)s")
        )
        logger.addHandler(file_handler)
    for uv_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(uv_logger_name)
        uv_logger.handlers = logger.handlers
        uv_logger.setLevel(logger.level)
        uv_logger.propagate = False
    if created_default_config:
        logger.info(f"No config file found. Created default config at {config_path}")
    else:
        logger.debug(f"Config file successfully loaded from {config_path}")

    # init database
    quasilattice.database.validate_database()

    # create files directory
    os.makedirs(config["quasilattice"]["files_dir"], exist_ok=True)

    # TODO: load plugins here

    # start the sync thread
    if config["sync"]["enabled"] and start_background_sync:
        start_sync_job()


def validate_config():
    global config
    global current_default_alias_length
    if not config:
        config = {}

    if "quasilattice" not in config:
        config["quasilattice"] = {}
    if "database_path" not in config["quasilattice"]:
        config["quasilattice"]["database_path"] = os.path.join(
            os.path.dirname(config_path), "quasilattice.db"
        )
    if "files_dir" not in config["quasilattice"]:
        config["quasilattice"]["files_dir"] = os.path.join(
            os.path.dirname(config_path), "files"
        )
    if "max_file_size_gb" not in config["quasilattice"]:
        config["quasilattice"]["max_file_size_gb"] = 10
    if "case_sensitive_aliases" not in config["quasilattice"]:
        config["quasilattice"]["case_sensitive_aliases"] = False
    if "generate_default_aliases" not in config["quasilattice"]:
        config["quasilattice"]["generate_default_aliases"] = True
    if "default_alias_length" not in config["quasilattice"]:
        config["quasilattice"]["default_alias_length"] = 4
    current_default_alias_length = max(
        current_default_alias_length, config["quasilattice"]["default_alias_length"]
    )
    if "default_alias_characters" not in config["quasilattice"]:
        config["quasilattice"]["default_alias_characters"] = "0123456789acdefhjkmnprtwz"
    if "default_alias_timeout_ms" not in config["quasilattice"]:
        config["quasilattice"]["default_alias_timeout_ms"] = 200
    if "archive_mode" not in config["quasilattice"]:
        config["quasilattice"]["archive_mode"] = False

    if "sync" not in config:
        config["sync"] = {}
    if "enabled" not in config["sync"]:
        config["sync"]["enabled"] = False
    if "sync_interval_sec" not in config["sync"]:
        config["sync"]["sync_interval_sec"] = 300
    if "peers" not in config["sync"]:
        config["sync"]["peers"] = {}

    if "logging" not in config:
        config["logging"] = {}
    if "log_level" not in config["logging"]:
        config["logging"]["log_level"] = 3
    if "log_to_file" not in config["logging"]:
        config["logging"]["log_to_file"] = True
    if "log_to_stderr" not in config["logging"]:
        config["logging"]["log_to_stderr"] = True
    if "max_log_file_size_bytes" not in config["logging"]:
        config["logging"]["max_log_file_size_bytes"] = 10485760
    if "log_file_backup_count" not in config["logging"]:
        config["logging"]["log_file_backup_count"] = 3
    if "log_path" not in config["logging"]:
        config["logging"]["log_path"] = os.path.join(
            os.path.dirname(config_path), "quasilattice.log"
        )

    if "http" not in config:
        config["http"] = {}
    if "enabled" not in config["http"]:
        config["http"]["enabled"] = True
    if "host" not in config["http"]:
        config["http"]["host"] = "127.0.0.1"
    if "port" not in config["http"]:
        config["http"]["port"] = 8312
    if "require_authentication" not in config["http"]:
        config["http"]["require_authentication"] = False
    if "api_key_length" not in config["http"]:
        config["http"]["api_key_length"] = 20


def write_default_config_file():
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as file:
        file.write(f"""# This is the default QuasiLattie config file.
# You may want to modify these settings.

[quasilattice]

# Path to the SQLite database file:
database_path = "{os.path.join(os.path.dirname(config_path), "quasilattice.db")}"

# Directory to store files associated with lattice entries:
files_dir = "{os.path.join(os.path.dirname(config_path), "files")}"

# Max file size in gigabytes (default: 10):
max_file_size_gb = 10

# Use case sensitive aliases (default: false):
case_sensitive_aliases = false

# Generate short default aliases of random characters (default: true):
generate_default_aliases = true

# Length for the auto-generated aliases (default: 4):
default_alias_length = 4

# Set of characters to use for auto-generated aliases:
default_alias_characters = "0123456789acdefhjkmnprtwz"

# Timeout for auto-generating an alias in miliseconds. If the timeout is 
# exceeded and utilization of aliases with the current length is greater 
# than 99%, then the default alias length will be increased (default: 200):
default_alias_timeout_ms = 200

# Archive mode will preserve the old versions of entries. When archive mode
# is enabled deleting an entry simply marks it as deleted without actually
# deleting it and editing creates a copy in the database (default: false):
archive_mode = false


[sync]
# Enable syncthing with other Quasilattice nodes (default: false):
enabled = false

# Time in seconds between syncing the database with peers (default: 300):
sync_interval_sec = 300

  # Other QuasiLattice nodes to sync with. If the other node requires
  # authentication, then you must include either a username and password
  # or an api key to authenticate with the peer. An example is shown below:
  [peers]
    # [Example Local Server]
    #   protocol = "http"
    #   url = "http://192.168.0.11"
    #   username = "admin"
    #   password = "admin"


[logging]
# Log level determines how much information is logged:
#   0: None
#   1: Critical (least ammount of logging)
#   2: Error
#   3: Warning
#   4: Info (default)
#   5: Debug (most ammount of logging)
log_level = 4

# Save logs to a log file (default: true):
log_to_file = true

# Max log file size in bytes (default: 10485760)
max_log_file_size_bytes = 10485760

# Max number of log files
log_file_backup_count = 3

# Write logs to a stderr (default: true):
log_to_stderr = true

# Log path determines where the log file is written to:
log_path = "{os.path.join(os.path.dirname(config_path), "quasilattice.log")}"


[http]
# Enable the http interface (default: true):
enabled = true

# Host to bind to (default: "127.0.0.1"):
host = "127.0.0.1"

# Port to bind to (default: 8312):
port = 8312

# Require authentication for the http interface (default: false):
require_authentication = false

# Number of characters in API keys (default: 20):
api_key_length = 20

""")


def sync_with_peers():
    pass  # TODO: implement syncing


def start_sync_job():
    global sync_thread
    if sync_thread is None:
        sync_thread = threading.Thread(target=_sync_job)
        sync_thread.daemon = True
        sync_thread.start()


def _sync_job():
    global last_sync_time
    while True:
        now = time.time()
        if now > last_sync_time + config["sync"]["sync_interval_sec"]:
            sync_with_peers()
            last_sync_time = time.time()
        time.sleep(min(config["sync"]["sync_interval_sec"], 1800))


def run(
    config_path: str | None = None,
    log_level: str | None = None,
    log_path: str | None = None,
    start_background_sync: bool = True,
):
    init(config_path, log_level, log_path, start_background_sync)
    logger.debug("Running QuasiLattice!")
    if config["http"]["enabled"]:
        import uvicorn

        uvicorn.run(
            "quasilattice.api:app",
            host=config["http"]["host"],
            port=config["http"]["port"],
            log_config=None,
        )
    else:
        while True:
            time.sleep(1800)  # sleep to keep the process running


# region entries
def entry(entry_id: uuid.UUID | str | bytes, include_deleted: bool = False) -> dict | None:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        return quasilattice.database.read_entry_by_id(cursor, entry_id, include_deleted)


def entry_hash(entry_id: uuid.UUID | str | bytes, include_deleted: bool = False) -> bytes | None:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        elif isinstance(entry_id, str):
            entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_id)
        if len(entry_id) == 16:
            return quasilattice.database.read_entry_hash(cursor, entry_id)
    return None


def entries(
    entry_ids: str | typing.Iterable[uuid.UUID | str | bytes] = [],
    limit: int = 500,
    include_deleted: bool = False,
) -> dict[str, dict]:
    """Returns a set of the most recent (not deleted) versions of multiple entries."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()

        # user passed an empty list, read all entries
        if entry_ids is None or len(entry_ids) == 0:
            entries_by_hash = quasilattice.database.read_all_entries(
                cursor, limit, include_deleted
            )
            entry_uuids = set[str]()
            for value in entries_by_hash.values():
                if (
                    "uuid" in value
                    and quasilattice.database.is_entry_property_stored_in_columns(
                        "uuid", value["uuid"]
                    )
                ):
                    try:
                        entry_uuids.add(
                            bytes.fromhex(
                                "".join(
                                    c
                                    for c in value["uuid"]
                                    if c in "0123456789abcdefABCDEF"
                                )
                            )
                        )
                    except (TypeError, ValueError):
                        pass
            return entries_by_hash | quasilattice.database.read_entries_by_uuid(
                cursor, list(entry_uuids), limit, include_deleted
            )

        if isinstance(entry_ids, str):
            entry = quasilattice.database.read_entry_by_id(
                cursor, entry_ids, include_deleted
            )
            if entry:
                return entry
            return quasilattice.database.read_entries_by_filter(
                cursor,
                entry_ids,
                limit,
                False,
                include_deleted,
            )

        entry_uuids: list[bytes] = []
        entry_hashes: list[bytes] = []
        entry_aliases: list[str] = []
        for entry_id in entry_ids:
            if isinstance(entry_id, str):
                entry_aliases.append(entry_id)
            else:
                if isinstance(entry_id, uuid.UUID):
                    entry_id = entry_id.bytes
                if len(entry_id) == 16:
                    entry_uuids.append(entry_id)
                elif len(entry_id) == 32:
                    entry_hashes.append(entry_id)
        alias_rows = quasilattice.database.read_alias_rows_by_alias(
            cursor, entry_aliases, limit
        )

        found_aliases = []
        for alias_row in alias_rows:
            if alias_row["entry_uuid"] is not None:
                entry_uuids.append()
                found_aliases.append(
                    alias_row["alias"]
                    if config["quasilattice"]["case_sensitive_aliases"]
                    else alias_row["alias"].lower()
                )
            elif alias_row["entry_hash"] is not None:
                entry_hashes.append()
                found_aliases.append(alias_row["alias"])

        for entry_alias in entry_aliases:  # process remaining aliases
            if entry_alias.lower() not in found_aliases:
                try:
                    entry_alias = "".join(
                        c for c in entry_alias if c in "0123456789abcdefABCDEF"
                    )
                    entry_alias = bytes.fromhex(entry_alias)
                    if len(entry_alias) == 16:
                        entry_uuids.append(entry_alias)
                    elif len(entry_alias) == 32:
                        entry_hashes.append(entry_alias)
                except (TypeError, ValueError):
                    pass

        return quasilattice.database.read_entries_by_uuid(
            cursor, entry_uuids, limit, include_deleted
        ) | quasilattice.database.read_entries_by_hash(
            cursor, entry_hashes, limit, include_deleted
        )


def entry_versions(
    entry_id: uuid.UUID | str | bytes,
    limit: int = 500,
    include_deleted: bool = True,
) -> dict[str, dict]:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        elif isinstance(entry_id, str):
            entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_id)
        return quasilattice.database.read_entry_versions(
            cursor,
            entry_id,
            limit,
            include_deleted,
        )


def entry_version_hashes(
    entry_id: uuid.UUID | str | bytes,
    limit: int = 500,
    include_deleted: bool = True,
) -> list[bytes]:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        elif isinstance(entry_id, str):
            entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_id)
        return quasilattice.database.read_entry_version_hashes(
            cursor,
            entry_id,
            limit,
            include_deleted,
        )


def entries_by_filter(
    filter: str,
    limit: int = 500,
    include_outdated: bool = False,
    include_deleted: bool = False,
) -> dict[str, dict]:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        return quasilattice.database.read_entries_by_filter(
            cursor,
            filter,
            limit,
            include_outdated,
            include_deleted,
        )


def write_entry(
    entry_dict: dict,
    edited_by: str = "",
    api_key_id: str | None = None,
):
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        entry_id = quasilattice.database.write_entry_dict(
            cursor, entry_dict, edited_by, api_key_id
        )
        if config["quasilattice"]["generate_default_aliases"]:
            if len(entry_id) == 16:
                quasilattice.database.write_default_alias_by_uuid(
                    cursor, entry_id, edited_by, api_key_id
                )
            elif len(entry_id) == 32:
                quasilattice.database.write_default_alias_by_hash(
                    cursor, entry_id, edited_by, api_key_id
                )
        connection.commit()


def delete_entry(
    entry_id: uuid.UUID | str | bytes,
    edited_by: str = "",
    api_key_id: str | None = None,
):
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        if not quasilattice.database.entry_exists(cursor, entry_id):
            raise ValueError("Entry " + str(entry_id) + "does not exist!")
        if isinstance(entry_id, str):
            entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_id)
        if len(entry_id) == 16:
            quasilattice.database.delete_entry_by_uuid(
                cursor, entry_id, edited_by, api_key_id
            )
        elif len(entry_id) == 32:
            quasilattice.database.delete_entry_by_hash(
                cursor, entry_id, edited_by, api_key_id
            )
        connection.commit()


def undelete_entry(entry_id: uuid.UUID | str | bytes, edited_by: str = "",
    api_key_id: str | None = None,) -> bool:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_id, uuid.UUID):
            entry_id = entry_id.bytes
        elif isinstance(entry_id, str):
            entry_id = quasilattice.database.resolve_entry_alias(cursor, entry_id)
        if len(entry_id) == 16:
            success = quasilattice.database.undelete_entry_by_uuid(cursor, entry_id, edited_by, api_key_id)
        elif len(entry_id) == 32:
            success = quasilattice.database.undelete_entry_by_hash(cursor, entry_id, edited_by, api_key_id)
        if success:
            connection.commit()
    return success


# endregion


# region aliases
def aliases(entry_alias: str | bytes | None = None, limit: int = 500) -> list[str]:
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if entry_alias is None:
            return quasilattice.database.read_aliases_before_time(
                cursor, time.time(), limit
            )
        if isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        if len(entry_alias) == 16:
            return quasilattice.database.read_aliases_by_uuid(entry_alias)
        elif len(entry_alias) == 32:
            return quasilattice.database.read_aliases_by_hash(entry_alias)
    return []


def add_alias(
    alias: str,
    entry_alias: str | bytes,
    edited_by: str = "",
    api_key_id: str | None = None,
    allow_deleted_entry: bool = False,
):
    """Adds a new alias to an existing entry identified by entry_alias."""
    with quasilattice.database.connection() as connection:
        cursor = connection.cursor()
        if isinstance(entry_alias, str):
            entry_alias = quasilattice.database.resolve_entry_alias(cursor, entry_alias)
        if not quasilattice.database.entry_exists(
            cursor, entry_alias, allow_deleted_entry
        ):
            raise ValueError("Entry " + str(entry_alias) + "does not exist!")
        if len(entry_alias) == 16:
            quasilattice.database.add_alias_by_uuid(
                cursor, entry_alias, alias, edited_by, api_key_id
            )
        elif len(entry_alias) == 32:
            quasilattice.database.add_alias_by_hash(
                cursor, entry_alias, alias, edited_by, api_key_id
            )
        connection.commit()


# endregion
