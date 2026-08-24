from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sqlite3
import typing
import uuid

import rfc8785
import zstandard

import quasilattice

logger = logging.getLogger("quasilattice")

ENTRY_COLUMNS = {
    "uuid": uuid.UUID,
    "time_edited": int,
    "time_created": int,
    "edited_by": str,
    "is_file": bool,
    "file_hash": bytes,
    "markup_language": str,
    "content": str,
}


def validate_database():
    try:
        db_path = quasilattice.config["quasilattice"]["database_path"]
        logger.debug(f"Validating database at {db_path}")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except KeyError:
        logger.critical("Config not loaded! You must call quasilattice.init() first.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except PermissionError:
        logger.critical("Permission denied while creating the database directory.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except OSError:
        logger.critical("Failed to create database directory.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except Exception:
        raise
    try:
        with sqlite3.connect(db_path) as sql_connection:
            sql_cursor = sql_connection.cursor()

            # enforce foreign key constraints (off by default in sqlite)
            sql_cursor.execute("PRAGMA foreign_keys = ON;")

            # create info table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='info';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute(
                    "CREATE TABLE info(name TEXT PRIMARY KEY NOT NULL, content TEXT)"
                )

            # create users table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='users';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE users (
                        user TEXT PRIMARY KEY NOT NULL,
                        hashed_password TEXT,
                        time_edited INTEGER,
                        time_created INTEGER,
                        edited_by TEXT,
                        created_by TEXT,
                        is_admin INTEGER,
                        has_write_access INTEGER,
                        has_read_access INTEGER
                    )""")

            # create keys table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE api_keys (
                        id TEXT PRIMARY KEY NOT NULL,
                        hashed_key TEXT NOT NULL,
                        time_edited INTEGER,
                        time_created INTEGER,
                        note TEXT,
                        owner TEXT,
                        FOREIGN KEY (owner) REFERENCES users(user)
                    )""")

            # create entries table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='entries';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE entries (
                        uuid BLOB NOT NULL,
                        time_edited INTEGER,
                        time_created INTEGER,
                        edited_by TEXT,
                        is_file INTEGER,
                        file_hash BLOB,
                        markup_language TEXT,
                        content TEXT,
                        metadata TEXT,
                        metadata_zstd BLOB,
                        hash BLOB,
                        PRIMARY KEY (uuid, time_edited),
                        FOREIGN KEY (edited_by) REFERENCES users(user),
                        CHECK (
                            (metadata IS NOT NULL AND metadata_zstd IS NULL)
                            OR (metadata IS NULL AND metadata_zstd IS NOT NULL)
                        )
                    )""")

            # create aliases table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='aliases';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE aliases (
                        entry_uuid BLOB NOT NULL,
                        alias TEXT NOT NULL,
                        time_edited INTEGER,
                        edited_by TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_uuid, alias, time_edited),
                        FOREIGN KEY (edited_by) REFERENCES users(user)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_aliases_entry_uuid ON aliases(entry_uuid)
                """)

            # create read_access table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='read_access';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE read_access (
                        entry_uuid BLOB NOT NULL,
                        read_access TEXT NOT NULL,
                        time_edited INTEGER,
                        edited_by TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_uuid, read_access, time_edited),
                        FOREIGN KEY (edited_by) REFERENCES users(user)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_read_access_entry_uuid ON read_access(entry_uuid)
                """)

            # create write_access table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='write_access';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE write_access (
                        entry_uuid BLOB NOT NULL,
                        write_access TEXT NOT NULL,
                        time_edited INTEGER,
                        edited_by TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_uuid, write_access, time_edited),
                        FOREIGN KEY (edited_by) REFERENCES users(user)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_write_access_entry_uuid ON write_access(entry_uuid)
                """)

            # create linked_files table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='linked_files';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE linked_files (
                        entry_uuid BLOB NOT NULL,
                        linked_file_hash BLOB NOT NULL,
                        time_edited INTEGER,
                        linked_file_path TEXT,
                        edited_by TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_uuid, linked_file_hash, time_edited),
                        FOREIGN KEY (edited_by) REFERENCES users(user)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_linked_files_entry_uuid ON linked_files(entry_uuid)
                """)

            # create metadata_tree table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_tree';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE metadata_tree (
                        uuid BLOB PRIMARY KEY,
                        entry_uuid BLOB NOT NULL,
                        time_edited INTEGER,
                        name TEXT NOT NULL,
                        value TEXT,
                        parent_uuid BLOB,
                        FOREIGN KEY (parent_uuid) REFERENCES metadata_tree(uuid)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_metadata_tree_entry_uuid ON metadata_tree(entry_uuid)
                """)

            sql_connection.commit()
            sql_cursor.close()
    except PermissionError:
        logger.critical("Permission denied while validating database.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except OSError as e:
        logger.critical("Failed to validate database.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except Exception:
        raise
    logger.debug("Database validated successfully!")


@contextlib.contextmanager
def connection():
    """Yields an sqlite3 connection to access the quasilattice database."""
    db_path = quasilattice.config["quasilattice"]["database_path"]
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON;")
        yield connection
    finally:
        connection.close()

# region info
# TODO: version
# TODO: curent_default_alias_length


# endregion

# region users
def read_user(cursor: sqlite3.Cursor, user: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM users WHERE user = ?",
        (user,),
    )
    return cursor.fetchone()


def read_users(cursor: sqlite3.Cursor) -> sqlite3.Row | None:
    cursor.execute("SELECT * FROM users WHERE 1=1")
    return cursor.fetchall()


def write_user(cursor: sqlite3.Cursor, user_data: dict | sqlite3.Row | tuple):
    if isinstance(user_data, dict):
        user_data = convert_user_to_tuple(user_data)
    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) ", user_data
    )


def convert_user_to_tuple(user_data: dict | sqlite3.Row):
    return (
        user_data["user"],
        user_data["hashed_password"],
        user_data["time_edited"],
        user_data["time_created"],
        user_data["edited_by"],
        user_data["created_by"],
        user_data["is_admin"],
        user_data["has_write_access"],
        user_data["has_read_access"],
    )


# endregion


# region api_keys
def read_api_key(cursor: sqlite3.Cursor, id: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM api_keys WHERE id = ?",
        (id,),
    )
    return cursor.fetchone()


def read_api_keys(cursor: sqlite3.Cursor) -> sqlite3.Row | None:
    cursor.execute("SELECT * FROM api_keys WHERE 1=1")
    return cursor.fetchall()


def read_api_key_by_hashed_key(
    cursor: sqlite3.Cursor, hashed_key: str
) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM api_keys WHERE hashed_key = ?",
        (hashed_key,),
    )
    return cursor.fetchone()


def read_api_keys_by_owner(
    cursor: sqlite3.Cursor,
    owner: str,
    max_number_of_rows: int = 500,
    descending: bool = True,
) -> list[sqlite3.Row]:
    cursor.execute(
        f"SELECT * FROM api_keys WHERE owner = ? ORDER BY time_edited {'DESC' if descending else 'ASC'} LIMIT ?",
        (
            owner,
            max_number_of_rows,
        ),
    )
    return cursor.fetchall()


def write_api_key(cursor: sqlite3.Cursor, api_key_data: dict | sqlite3.Row | tuple):
    if not isinstance(api_key_data, tuple):
        api_key_data = convert_api_key_to_tuple(api_key_data)
    cursor.execute(
        "INSERT OR REPLACE INTO api_keys VALUES(?, ?, ?, ?, ?, ?) ",
        api_key_data,
    )


def convert_api_key_to_tuple(api_key_data: dict | sqlite3.Row):
    return (
        api_key_data["id"],
        api_key_data["hashed_key"],
        api_key_data["time_edited"],
        api_key_data["time_created"],
        api_key_data["note"],
        api_key_data["owner"],
    )


# endregion


# region entries
def read_entry_row(cursor: sqlite3.Cursor, entry_uuid: bytes) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM entries WHERE uuid = ? ORDER BY time_edited DESC LIMIT 1",
        (entry_uuid,),
    )
    return cursor.fetchone()


def read_entry_rows(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    max_number_of_rows: int = 500,
    descending: bool = True,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    cursor.execute(
        f"SELECT * FROM entries WHERE uuid = ? ORDER BY {'hash' if order_by_hash else 'time_edited'} {'DESC' if descending else 'ASC'} LIMIT ?",
        (
            entry_uuid,
            max_number_of_rows,
        ),
    )
    return cursor.fetchall()


def read_entry_hash(cursor: sqlite3.Cursor, entry_uuid: bytes) -> bytes | None:
    cursor.execute(
        "SELECT hash FROM entries WHERE uuid = ? ORDER BY time_edited DESC LIMIT 1",
        (entry_uuid,),
    )
    return cursor.fetchone()


def read_entry_hashes(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    max_number_of_rows: int = 500,
    descending: bool = True,
    order_by_hash: bool = False,
) -> list[bytes]:
    cursor.execute(
        f"SELECT hash FROM entries WHERE uuid = ? ORDER BY {'hash' if order_by_hash else 'time_edited'} {'DESC' if descending else 'ASC'} LIMIT ?",
        (
            entry_uuid,
            max_number_of_rows,
        ),
    )
    return cursor.fetchall()


def is_entry_property_stored_in_columns(key: str, value) -> bool:
    if key == "uuid" or (
        key in ENTRY_COLUMNS and isinstance(value, ENTRY_COLUMNS[key])
    ):
        return True
    if value is None:
        return False
    if key == "file_hash":
        try:
            bytes.fromhex(value)
            return True
        except (TypeError, ValueError):
            return False
    return False


def normalize_entry_property_stored_in_columns(key: str, value):
    if key == "uuid":
        value = str(uuid.UUID(value))
    elif key == "file_hash":
        if isinstance(value, bytes):
            value = value.hex()
        try:
            value = bytes.fromhex(value).hex()
        except (TypeError, ValueError):
            value = ""
    else:
        value = ENTRY_COLUMNS[key](value)
    return value


def read_entry_rows_by_property(
    cursor: sqlite3.Cursor,
    property_name: str,
    property_value: typing.Any,
    max_number_of_rows: int = 500,
    descending: bool = True,
) -> list[sqlite3.Row]:
    if is_entry_property_stored_in_columns(property_name, property_value):
        property_value = normalize_entry_property_stored_in_columns(
            property_name, property_value
        )
        if property_name == "uuid":  # convert to bytes for lookup
            property_value = uuid.UUID(property_value).bytes
        if property_name == "file_hash":  # convert to bytes for lookup
            property_value = bytes.fromhex(property_value)
        cursor.execute(
            f"SELECT * FROM entries WHERE {property_name} = ? "
            f"ORDER BY time_edited {'DESC' if descending else 'ASC'} LIMIT ?",
            (property_value, max_number_of_rows),
        )
    else:
        cursor.execute(
            f"SELECT DISTINCT entry_uuid FROM metadata_tree "
            f"WHERE name = ? AND value = ? AND parent_uuid IS NULL "
            f"ORDER BY time_edited {'DESC' if descending else 'ASC'} LIMIT ?",
            (
                property_name,
                rfc8785.dumps(property_value).decode("utf-8"),
                max_number_of_rows,
            ),
        )
        uuids = [row[0] for row in cursor.fetchall()]
        if uuids:
            cursor.execute(
                f"SELECT * FROM entries WHERE uuid IN ({', '.join('?' * len(uuids))}) "
                f"ORDER BY time_edited {'DESC' if descending else 'ASC'} LIMIT ?",
                (*uuids, max_number_of_rows),
            )
        else:
            return []
    return cursor.fetchall()


def read_entry_rows_by_properties(
    cursor: sqlite3.Cursor,
    properties: dict,
    max_number_of_rows: int = 500,
    descending: bool = True,
) -> list[sqlite3.Row]:

    column_filters = {}
    metadata_filters = {}

    for name, value in properties.items():
        if is_entry_property_stored_in_columns(name, value):
            column_filters[name] = normalize_entry_property_stored_in_columns(
                name, value
            )
            if name == "uuid":  # convert to bytes for lookup
                column_filters[name] = uuid.UUID(column_filters[name]).bytes
            if name == "file_hash":  # convert to bytes for lookup
                column_filters[name] = bytes.fromhex(column_filters[name])
        else:
            metadata_filters[name] = value

    # metadata-based filters
    candidate_uuids = None  # None = no metadata filter applied yet
    for name, value in metadata_filters.items():
        cursor.execute(
            "SELECT DISTINCT entry_uuid FROM metadata_tree "
            "WHERE name = ? AND value = ? AND parent_uuid IS NULL",
            (name, rfc8785.dumps(value).decode("utf-8")),
        )
        matched = {row[0] for row in cursor.fetchall()}
        candidate_uuids = (
            matched if candidate_uuids is None else (candidate_uuids & matched)
        )
        if not candidate_uuids:
            return []  # no entries found

    query = "SELECT * FROM entries WHERE 1=1"
    params: list[typing.Any] = []

    for name, value in column_filters.items():
        query += f" AND {name} = ?"
        params.append(value)

    if candidate_uuids is not None:
        query += f" AND uuid IN ({', '.join('?' * len(candidate_uuids))})"
        params.extend(candidate_uuids)

    query += f" ORDER BY time_edited {'DESC' if descending else 'ASC'} LIMIT ?"
    params.append(max_number_of_rows)

    cursor.execute(query, params)
    return cursor.fetchall()


def convert_entry_row_to_dict(entry_row: sqlite3.Row) -> dict:
    entry_dict = {"uuid": str(uuid.UUID(bytes=entry_row["uuid"]))}
    if entry_row["time_edited"] is not None:
        entry_dict["time_edited"] = entry_row["time_edited"]
    if entry_row["time_created"] is not None:
        entry_dict["time_created"] = entry_row["time_created"]
    if entry_row["edited_by"] is not None:
        entry_dict["edited_by"] = entry_row["edited_by"]
    if entry_row["is_file"] is not None:
        entry_dict["is_file"] = bool(entry_row["is_file"] == 1)
    if entry_row["file_hash"] is not None:
        entry_dict["file_hash"] = bytes(entry_row["file_hash"]).hex()
    if entry_row["markup_language"] is not None:
        entry_dict["markup_language"] = entry_row["markup_language"]
    if entry_row["content"] is not None:
        entry_dict["content"] = entry_row["content"]

    # extract metadata
    if entry_row["metadata"] is not None:
        metadata_json = entry_row["metadata"]
    elif entry_row["metadata_zstd"] is not None:
        decompressor = zstandard.ZstdDecompressor()
        raw_bytes = decompressor.decompress(entry_row["metadata_zstd"])
        metadata_json = raw_bytes.decode("utf-8")
    else:
        metadata_json = None

    # parse metadata
    if metadata_json is not None:
        parsed_metadata = json.loads(metadata_json)
        for key, value in parsed_metadata.items():
            if key not in entry_dict:
                entry_dict[key] = value

    return entry_dict


def _get_column_property(entry_dict: dict, column_property: str):
    if is_entry_property_stored_in_columns(
        column_property, entry_dict.get(column_property)
    ):
        value = normalize_entry_property_stored_in_columns(
            column_property, entry_dict.get(column_property)
        )
        if column_property == "uuid":  # convert to bytes for storage in database
            value = uuid.UUID(value).bytes
        if column_property == "file_hash":  # convert to bytes for storage in database
            value = bytes.fromhex(value)
        return value
    return None


def convert_entry_dict_to_tuple(entry_dict: dict) -> tuple:
    # store metadata (and compress if it saves space)
    metadata = {
        key: value
        for key, value in entry_dict.items()
        if not is_entry_property_stored_in_columns(key, value)
    }
    canonical_metadata_bytes = rfc8785.dumps(metadata)
    compressor = zstandard.ZstdCompressor()
    compressed_metadata_bytes = compressor.compress(canonical_metadata_bytes)
    if len(compressed_metadata_bytes) < len(canonical_metadata_bytes):
        metadata_text = None
        metadata_zstd = compressed_metadata_bytes
    else:
        metadata_text = canonical_metadata_bytes.decode("utf-8")
        metadata_zstd = None

    # compute hash
    hashable_dict = {
        key: normalize_entry_property_stored_in_columns(key, value)
        if is_entry_property_stored_in_columns(key, value)
        else value
        for key, value in entry_dict.items()
    }
    hashable_bytes = rfc8785.dumps(hashable_dict)
    entry_hash = hashlib.sha256(hashable_bytes).digest()

    entry_tuple = (
        uuid.UUID(entry_dict["uuid"]).bytes,
        _get_column_property(entry_dict, "time_edited"),
        _get_column_property(entry_dict, "time_created"),
        _get_column_property(entry_dict, "edited_by"),
        _get_column_property(entry_dict, "is_file"),
        _get_column_property(entry_dict, "file_hash"),
        _get_column_property(entry_dict, "markup_language"),
        _get_column_property(entry_dict, "content"),
        metadata_text,
        metadata_zstd,
        entry_hash,
    )
    return entry_tuple


# TODO: write entry
# TODO: delete entry


# endregion


# region aliases
def read_alias(cursor: sqlite3.Cursor, entry_uuid: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM aliases WHERE entry_uuid = ? ORDER BY time_edited DESC LIMIT 1",
        (entry_uuid,),
    )
    return cursor.fetchone()

def get_entry_uuid_from_alias(cursor: sqlite3.Cursor, entry_alias: str) -> bytes | None:
    """Returns the entry uuid for an alias, or None if no entry has it."""
    case_sensitive = quasilattice.config["quasilattice"]["case_sensitive_aliases"]
    if case_sensitive:
        cursor.execute(
            "SELECT entry_uuid FROM aliases WHERE alias = ? ORDER BY time_edited DESC LIMIT 1",
            (entry_alias,),
        )
    else:
        cursor.execute(
            "SELECT entry_uuid FROM aliases WHERE LOWER(alias) = ? ORDER BY time_edited DESC LIMIT 1",
            (entry_alias.lower(),),
        )
    row = cursor.fetchone()
    if row is None:
        return None
    return bytes(row["entry_uuid"])

# TODO: write alias
# TODO: delete alias
# TODO: delete aliases (for an entry by uuid)

# endregion


# region read_access
# TODO: read read_access (by uuid and read_access)
# TODO: read read_accesses (for an entry by uuid)
# TODO: write read_accesses
# TODO: add read_access
# TODO: remove read_access
# TODO: delete read_accesses (for an entry by uuid)


# endregion


# region write_access
# TODO: read write_access (by uuid and write_access)
# TODO: read write_accesses (for an entry by uuid)
# TODO: write write_accesses
# TODO: add write_access
# TODO: remove write_access
# TODO: delete write_accesses (for an entry by uuid)


# endregion


# region linked_files
# TODO: read, write, delete


# endregion


# region metadata_tree
# TODO: implement the metadata_tree


# endregion