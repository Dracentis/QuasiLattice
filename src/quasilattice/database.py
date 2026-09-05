from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import os
import random
import sqlite3
import time
import typing
import uuid

import rfc8785
import zstandard

import quasilattice

logger = logging.getLogger("quasilattice")

ENTRY_COLUMNS = {
    "uuid": uuid.UUID,
    "timestamp": float,
    "edited_by": str,
    "is_file": bool,
    "file_hash": bytes,
    "markup_language": str,
    "title": str,
    "content": str,
}


def validate_database(db_path=None):
    try:
        if db_path is None:
            db_path = quasilattice.config["quasilattice"]["database_path"]
        logger.debug(f"Validating database at {db_path}")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    except KeyError:
        logger.critical("Config not loaded! You must call quasilattice.init() first")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except PermissionError:
        logger.critical("Permission denied while creating the database directory")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except OSError:
        logger.critical("Failed to create database directory")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    try:
        with sqlite3.connect(db_path) as sql_connection:
            sql_cursor = sql_connection.cursor()

            # enforce foreign key constraints (off by default in sqlite)
            sql_cursor.execute("PRAGMA foreign_keys = ON;")

            # create info table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='info';"""
            )
            if sql_cursor.fetchone() is None:
                sql_cursor.execute(
                    "CREATE TABLE info(key TEXT PRIMARY KEY NOT NULL, value TEXT)"
                )
                sql_cursor.execute(
                    "INSERT OR REPLACE INTO info VALUES(?, ?) ",
                    ("quasilattice_version_when_created", quasilattice.__version__),
                )
                sql_cursor.execute(
                    "INSERT OR REPLACE INTO info VALUES(?, ?) ",
                    ("quasilattice_version", quasilattice.__version__),
                )
                sql_cursor.execute(
                    "INSERT OR REPLACE INTO info VALUES(?, ?) ",
                    ("database_schema_version", "1"),
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
                        can_create_entries INTEGER
                    )""")

            # create api_keys table
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
                        owner TEXT,
                        can_create_entries INTEGER,
                        note TEXT,
                        FOREIGN KEY (owner) REFERENCES users(user)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_api_keys_owner_time ON api_keys(owner, time_edited DESC);
                """)

            # create entries table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='entries';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE entries (
                        hash BLOB PRIMARY KEY NOT NULL,
                        uuid BLOB,
                        timestamp FLOAT,
                        edited_by TEXT,
                        is_file INTEGER,
                        file_hash BLOB,
                        markup_language TEXT,
                        title TEXT,
                        content TEXT,
                        metadata TEXT,
                        metadata_zstd BLOB,
                        CHECK (
                            (metadata IS NOT NULL AND metadata_zstd IS NULL)
                            OR (metadata IS NULL AND metadata_zstd IS NOT NULL)
                        )
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_entries_uuid_time_hash ON entries(uuid, timestamp DESC, hash DESC)
                """)

            # create edit_log table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='edit_log';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE edit_log (
                        entry_hash BLOB NOT NULL,
                        entry_uuid BLOB,
                        is_deletion INTEGER NOT NULL,
                        timestamp FLOAT NOT NULL,
                        edited_by TEXT,
                        api_key_id TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_hash, timestamp)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_edit_log_entry_uuid_time_hash
                    ON edit_log(entry_uuid, timestamp DESC, is_deletion ASC, entry_hash DESC);
                """)
                sql_cursor.execute("""
                    CREATE INDEX index_edit_log_entry_time_hash
                    ON edit_log(timestamp DESC, is_deletion ASC, entry_hash DESC);
                """)

            # create aliases table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='aliases';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE aliases (
                        entry_hash BLOB,
                        entry_uuid BLOB,
                        alias TEXT NOT NULL,
                        time_edited INTEGER NOT NULL,
                        edited_by TEXT,
                        api_key_id TEXT,
                        hash BLOB NOT NULL,
                        PRIMARY KEY (alias, time_edited)
                        CHECK (entry_uuid IS NULL OR entry_hash IS NULL)
                    )""")
                sql_cursor.execute(
                    "CREATE INDEX index_aliases_entry_uuid ON aliases(entry_uuid, time_edited)"
                )
                sql_cursor.execute(
                    "CREATE INDEX index_aliases_entry_hash ON aliases(entry_hash, time_edited)"
                )

            # create read_access table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='read_access';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE read_access (
                        entry_hash BLOB,
                        entry_uuid BLOB,
                        read_access TEXT,
                        time_edited INTEGER NOT NULL,
                        edited_by TEXT,
                        api_key_id TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_hash, entry_uuid, time_edited, read_access),
                        CHECK (
                            (entry_uuid IS NOT NULL AND entry_hash IS NULL)
                            OR (entry_uuid IS NULL AND entry_hash IS NOT NULL)
                        )
                    )""")
                sql_cursor.execute(
                    "CREATE INDEX index_read_access_read_access ON read_access(read_access)"
                )
                sql_cursor.execute(
                    "CREATE INDEX index_read_access_time_edited ON read_access(time_edited)"
                )

            # create write_access table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='write_access';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE write_access (
                        entry_hash BLOB,
                        entry_uuid BLOB,
                        write_access TEXT,
                        time_edited INTEGER NOT NULL,
                        edited_by TEXT,
                        api_key_id TEXT,
                        hash BLOB,
                        PRIMARY KEY (entry_hash, entry_uuid, time_edited, write_access),
                        CHECK (
                            (entry_uuid IS NOT NULL AND entry_hash IS NULL)
                            OR (entry_uuid IS NULL AND entry_hash IS NOT NULL)
                        )
                    )""")
                sql_cursor.execute(
                    "CREATE INDEX index_write_access_write_access ON write_access(write_access)"
                )
                sql_cursor.execute(
                    "CREATE INDEX index_write_access_time_edited ON write_access(time_edited)"
                )

            # create linked_files table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='linked_files';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE linked_files (
                        file_hash BLOB PRIMARY KEY NOT NULL,
                        time_file_modified INTEGER,
                        linked_file_path TEXT
                    )""")

            # create metadata_tree table
            sql_cursor.execute(
                """SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_tree';"""
            )
            if sql_cursor.fetchone() == None:
                sql_cursor.execute("""
                    CREATE TABLE metadata_tree (
                        uuid BLOB PRIMARY KEY,
                        entry_hash BLOB NOT NULL,
                        timestamp FLOAT,
                        key TEXT NOT NULL,
                        value TEXT,
                        parent_uuid BLOB,
                        FOREIGN KEY (parent_uuid) REFERENCES metadata_tree(uuid)
                    )""")
                sql_cursor.execute("""
                    CREATE INDEX index_metadata_tree_entry_hash ON metadata_tree(entry_hash)
                """)

            sql_connection.commit()
            sql_cursor.close()
    except PermissionError:
        logger.critical("Permission denied while validating database")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except OSError:
        logger.critical("Failed to validate database")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    logger.debug("Database validated successfully!")


@contextlib.contextmanager
def connection(db_path=None):
    """Yields an sqlite3 connection to access the quasilattice database."""
    try:
        if db_path is None:
            db_path = quasilattice.config["quasilattice"]["database_path"]
    except KeyError:
        logger.critical("Config not loaded! You must call quasilattice.init() first")
        raise
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON;")
        yield connection
    finally:
        connection.close()


# region info
def update_info(cursor: sqlite3.Cursor):
    """Updates and reads from the info table."""
    cursor.execute(
        "SELECT * FROM info WHERE key = ?",
        ("database_schema_version",),
    )
    database_schema_version_row = cursor.fetchone()
    if (
        database_schema_version_row is None
        or database_schema_version_row["value"] != "1"
    ):  # only accept the first schema (update this in future updates)
        found = (
            None
            if database_schema_version_row is None
            else database_schema_version_row["value"]
        )
        logger.critical(f"Expected database schema version 1, found {found}")
        raise RuntimeError(f"Expected database schema version 1, found {found}")
    cursor.execute(
        "INSERT OR REPLACE INTO info VALUES(?, ?) ",
        ("quasilattice_version", quasilattice.__version__),
    )
    cursor.execute(
        "SELECT * FROM info WHERE key = ?",
        ("current_default_alias_length",),
    )
    new_default_alias_length_row = cursor.fetchone()
    if new_default_alias_length_row is not None:
        quasilattice.current_default_alias_length = max(
            int(new_default_alias_length_row["value"]),
            quasilattice.current_default_alias_length,
        )
    cursor.execute(
        "INSERT OR REPLACE INTO info VALUES(?, ?) ",
        ("current_default_alias_length", quasilattice.current_default_alias_length),
    )
    logger.debug("Database info updated!")


# endregion


# region users
def read_user(cursor: sqlite3.Cursor, user: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM users WHERE user = ?",
        (user,),
    )
    return cursor.fetchone()


def read_users(cursor: sqlite3.Cursor) -> list[sqlite3.Row]:
    cursor.execute("SELECT * FROM users WHERE 1=1")
    return cursor.fetchall()


def write_user(cursor: sqlite3.Cursor, user_data: dict | sqlite3.Row | tuple):
    if isinstance(user_data, dict):
        user_data = convert_user_to_tuple(user_data)
    cursor.execute(
        """
        INSERT INTO users VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user) DO UPDATE SET
           hashed_password = excluded.hashed_password,
           time_edited = excluded.time_edited,
           time_created = excluded.time_created,
           edited_by = excluded.edited_by,
           created_by = excluded.created_by,
           is_admin = excluded.is_admin,
           can_create_entries = excluded.can_create_entries
        """,
        user_data,
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
        user_data["can_create_entries"],
    )


# endregion


# region api_keys
def read_api_key(cursor: sqlite3.Cursor, id: str) -> sqlite3.Row | None:
    cursor.execute(
        "SELECT * FROM api_keys WHERE id = ?",
        (id,),
    )
    return cursor.fetchone()


def read_api_keys(cursor: sqlite3.Cursor) -> list[sqlite3.Row]:
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
    cursor: sqlite3.Cursor, owner: str, max_number_of_rows: int = 500
) -> list[sqlite3.Row]:
    cursor.execute(
        "SELECT * FROM api_keys WHERE owner = ? ORDER BY time_edited DESC LIMIT ?",
        (
            owner,
            max_number_of_rows,
        ),
    )
    return cursor.fetchall()


def write_api_key(cursor: sqlite3.Cursor, api_key_data: dict | sqlite3.Row | tuple):
    if isinstance(api_key_data, dict):
        api_key_data = convert_api_key_to_tuple(api_key_data)
    cursor.execute(
        "INSERT OR REPLACE INTO api_keys VALUES(?, ?, ?, ?, ?, ?, ?) ",
        api_key_data,
    )


def convert_api_key_to_tuple(api_key_data: dict | sqlite3.Row):
    return (
        api_key_data["id"],
        api_key_data["hashed_key"],
        api_key_data["time_edited"],
        api_key_data["time_created"],
        api_key_data["owner"],
        api_key_data["can_create_entries"],
        api_key_data["note"],
    )


# endregion


# region entries
def read_entry_by_uuid(cursor: sqlite3.Cursor, entry_uuid: bytes) -> dict | None:
    """Returns the most recent (not deleted) version of an entry or None."""
    entry_row = read_entry_row_by_uuid(cursor, entry_uuid)
    if entry_row is None:
        return None
    return convert_entry_row_to_dict(entry_row)


def read_entry_row_by_uuid(
    cursor: sqlite3.Cursor, entry_uuid: bytes, include_deleted: bool = False
) -> sqlite3.Row | None:
    """Returns the most recent (not deleted) version of an entry row or None."""
    if include_deleted or (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        cursor.execute(
            """
            SELECT entries.*
            FROM edit_log
            JOIN entries ON entries.hash = edit_log.entry_hash
            WHERE edit_log.entry_uuid = ?
              AND edit_log.is_deletion = 0
            ORDER BY edit_log.timestamp DESC, edit_log.entry_hash DESC
            LIMIT 1
            """,
            (entry_uuid,),
        )
    else:
        cursor.execute(
            """
            SELECT entries.*
            FROM edit_log
            JOIN entries ON entries.hash = edit_log.entry_hash
            WHERE edit_log.entry_uuid = ?
              AND edit_log.is_deletion = 0
              AND edit_log.timestamp = (
                  SELECT MAX(timestamp)
                  FROM edit_log AS latest
                  WHERE latest.entry_hash = edit_log.entry_hash
              )
            ORDER BY edit_log.timestamp DESC, edit_log.entry_hash DESC
            LIMIT 1
            """,
            (entry_uuid,),
        )
    return cursor.fetchone()


def read_entry_by_hash(
    cursor: sqlite3.Cursor, entry_hash: bytes, include_deleted: bool = False
) -> dict | None:
    """Returns a (not deleted) entry by hash or None."""
    entry_row = read_entry_row_by_hash(cursor, entry_hash, include_deleted)
    if entry_row is None:
        return None
    return convert_entry_row_to_dict(entry_row)


def read_entry_row_by_hash(
    cursor: sqlite3.Cursor, entry_hash: bytes, include_deleted: bool = False
) -> sqlite3.Row | None:
    """Returns a (not deleted) entry row by hash or None."""
    if include_deleted or (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        cursor.execute(
            "SELECT * FROM entries WHERE hash = ?",
            (entry_hash,),
        )
    else:
        cursor.execute(
            """
            SELECT *
            FROM entries
            WHERE hash = ?
              AND (
                SELECT is_deletion
                FROM edit_log
                WHERE entry_hash = ?
                ORDER BY timestamp DESC, is_deletion ASC, entry_hash DESC
                LIMIT 1
              ) = 0
            """,
            (entry_hash, entry_hash),
        )
    return cursor.fetchone()


def read_entry_by_alias(
    cursor: sqlite3.Cursor, alias: str, include_deleted: bool = False
) -> dict | None:
    """Returns a (not deleted) entry by alias or None."""
    entry_row = read_entry_row_by_alias(cursor, alias, include_deleted)
    if entry_row is None:
        return None
    return convert_entry_row_to_dict(entry_row)


def read_entry_row_by_alias(
    cursor: sqlite3.Cursor, alias: str, include_deleted: bool = False
) -> sqlite3.Row | None:
    """Returns a (not deleted) entry row by alias or None."""
    alias_row = read_alias_row(cursor, alias)
    if alias_row is None:
        return None
    entry_hash = alias_row[0]
    entry_uuid = alias_row[1]
    if entry_uuid is not None:
        return read_entry_row_by_uuid(cursor, entry_uuid, include_deleted)
    elif entry_hash is not None:
        return read_entry_row_by_hash(cursor, entry_hash, include_deleted)
    return None


def read_entries_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuids: list[bytes],
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[dict]:
    """Returns a list of the most recent (not deleted) versions of multiple entries."""
    return [
        convert_entry_row_to_dict(row)
        for row in read_entry_rows_by_uuid(
            cursor, entry_uuids, limit, include_deleted, order_by_hash
        )
    ]


def read_entry_rows_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuids: list[bytes],
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of the most recent (not deleted) versions of multiple entry rows."""
    if not entry_uuids:
        return []

    if include_deleted or (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        cursor.execute(
            f"""
            SELECT entries.*
            FROM edit_log
            JOIN entries ON entries.hash = edit_log.entry_hash
            WHERE edit_log.entry_uuid IN ({",".join("?" for entry_uuid in entry_uuids)})
              AND edit_log.is_deletion = 0
              AND (edit_log.timestamp, edit_log.entry_hash) = (
                SELECT latest.timestamp, latest.entry_hash
                FROM edit_log AS latest
                WHERE latest.entry_uuid = edit_log.entry_uuid
                  AND latest.is_deletion = 0
                ORDER BY latest.timestamp DESC, latest.entry_hash DESC
                LIMIT 1
              )
            ORDER BY entries.timestamp DESC, entries.hash DESC
            """,
            entry_uuids,
        )
    else:
        cursor.execute(
            f"""
            WITH latest_per_hash AS (
                SELECT entry_hash, entry_uuid, timestamp
                FROM edit_log
                WHERE entry_uuid IN ({",".join("?" for entry_uuid in entry_uuids)})
                  AND is_deletion = 0
                  AND timestamp = (
                      SELECT MAX(timestamp)
                      FROM edit_log AS edit_log2
                      WHERE edit_log2.entry_hash = edit_log.entry_hash
                  )
            )
            SELECT entries.*
            FROM latest_per_hash
            JOIN entries ON entries.hash = latest_per_hash.entry_hash
            WHERE (latest_per_hash.timestamp, latest_per_hash.entry_hash) = (
                SELECT latest.timestamp, latest.entry_hash
                FROM latest_per_hash AS latest
                WHERE latest.entry_uuid = latest_per_hash.entry_uuid
                ORDER BY latest.timestamp DESC, latest.entry_hash DESC
                LIMIT 1
            )
            ORDER BY entries.timestamp DESC, entries.hash DESC
            """,
            entry_uuids,
        )

    return cursor.fetchall()


def read_entries_by_hash(
    cursor: sqlite3.Cursor,
    entry_hashes: list[bytes],
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[dict]:
    """Returns a list of multiple (not deleted) entries by hashes."""
    return [
        convert_entry_row_to_dict(row)
        for row in read_entry_rows_by_hash(
            cursor, entry_hashes, limit, include_deleted, order_by_hash
        )
    ]


def read_entry_rows_by_hash(
    cursor: sqlite3.Cursor,
    entry_hashes: list[bytes],
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of multiple (not deleted) entry rows by hash."""
    if not entry_hashes:
        return []

    if include_deleted or (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        cursor.execute(
            f"""
            SELECT * FROM entries
            WHERE hash IN ({",".join("?" for entry_uuid in entry_hashes)})
            ORDER BY timestamp DESC, hash DESC
            """,
            entry_hashes,
        )
    else:
        cursor.execute(
            f"""
            SELECT entries.*
            FROM edit_log
            JOIN entries ON entries.hash = edit_log.entry_hash
            WHERE edit_log.entry_hash IN ({",".join("?" for entry_uuid in entry_hashes)})
                AND edit_log.is_deletion = 0
                AND (edit_log.timestamp, edit_log.entry_hash) = (
                    SELECT latest.timestamp, latest.entry_hash
                    FROM edit_log AS latest
                    WHERE latest.entry_hash = edit_log.entry_hash
                    ORDER BY latest.timestamp DESC, latest.entry_hash DESC
                    LIMIT 1
                )
            ORDER BY entries.timestamp DESC, entries.hash DESC
            """,
            entry_hashes,
        )

    return cursor.fetchall()


def read_entry_versions(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[dict]:
    """Returns a list of all (not deleted) entry versions."""
    return [
        convert_entry_row_to_dict(row)
        for row in read_entry_version_rows(
            cursor, entry_uuid, limit, include_deleted, order_by_hash
        )
    ]


def read_entry_version_rows(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of all (not deleted) entry version rows."""
    if include_deleted or (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        cursor.execute(
            """
            SELECT * FROM entries
            WHERE uuid = ?
            ORDER BY timestamp DESC, hash DESC
            """,
            (entry_uuid,),
        )
    else:
        cursor.execute(
            """
            SELECT entries.*
            FROM edit_log
            JOIN entries ON entries.hash = edit_log.entry_hash
            WHERE edit_log.entry_uuid = ?
              AND edit_log.is_deletion = 0
              AND (edit_log.timestamp, edit_log.entry_hash) = (
                    SELECT latest.timestamp, latest.entry_hash
                    FROM edit_log AS latest
                    WHERE latest.entry_hash = edit_log.entry_hash
                    ORDER BY latest.timestamp DESC
                    LIMIT 1
              )
            ORDER BY entries.timestamp DESC, entries.hash DESC
            """,
            (entry_uuid,),
        )

    return cursor.fetchall()


def read_entry_hash(cursor: sqlite3.Cursor, entry_uuid: bytes) -> bytes | None:
    """Returns the hash of the most recent (not deleted) version of an entry or None."""
    row = read_entry_row_by_uuid(cursor, entry_uuid)
    return row["hash"] if row is not None else None


def read_entry_version_hashes(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    limit: int = 500,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[bytes]:
    """Returns a list of hashes of all (not deleted) entry versions."""
    return [
        row["hash"]
        for row in read_entry_version_rows(
            cursor, entry_uuid, limit, include_deleted, order_by_hash
        )
    ]


def read_entry_hashes_after_time(
    cursor: sqlite3.Cursor,
    after_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[bytes]:
    pass  # TODO: implement


def read_entry_rows_after_time(
    cursor: sqlite3.Cursor,
    after_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[sqlite3.Row]:
    entry_hashes = read_entry_hashes_after_time(
        cursor, after_timestamp, limit, include_deleted
    )
    return read_entry_rows_by_hash(cursor, entry_hashes, include_deleted)


def read_entries_after_time(
    cursor: sqlite3.Cursor,
    after_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[dict]:
    entry_hashes = read_entry_hashes_after_time(
        cursor, after_timestamp, limit, include_deleted
    )
    return read_entries_by_hash(cursor, entry_hashes, include_deleted)


def read_entry_hashes_before_time(
    cursor: sqlite3.Cursor,
    before_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[bytes]:
    pass  # TODO: implement


def read_entry_rows_before_time(
    cursor: sqlite3.Cursor,
    before_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[sqlite3.Row]:
    entry_hashes = read_entry_hashes_before_time(
        cursor, before_timestamp, limit, include_deleted
    )
    return read_entry_rows_by_hash(cursor, entry_hashes, include_deleted)


def read_entries_before_time(
    cursor: sqlite3.Cursor,
    before_timestamp: float,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[dict]:
    entry_hashes = read_entry_hashes_before_time(
        cursor, before_timestamp, limit, include_deleted
    )
    return read_entries_by_hash(cursor, entry_hashes, include_deleted)


def read_entry_hashes_after_hash(
    cursor: sqlite3.Cursor,
    after_hash: hash,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[bytes]:
    pass  # TODO: implement


def read_entry_rows_after_hash(
    cursor: sqlite3.Cursor,
    after_hash: bytes,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[sqlite3.Row]:
    entry_hashes = read_entry_hashes_after_hash(
        cursor, after_hash, limit, include_deleted
    )
    return read_entry_rows_by_hash(cursor, entry_hashes, include_deleted)


def read_entries_after_hash(
    cursor: sqlite3.Cursor,
    after_hash: bytes,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[dict]:
    entry_hashes = read_entry_hashes_after_hash(
        cursor, after_hash, limit, include_deleted
    )
    return read_entries_by_hash(cursor, entry_hashes, include_deleted)


def read_entry_hashes_before_hash(
    cursor: sqlite3.Cursor,
    before_hash: bytes,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[bytes]:
    pass  # TODO: implement


def read_entry_rows_before_hash(
    cursor: sqlite3.Cursor,
    before_hash: bytes,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[sqlite3.Row]:
    entry_hashes = read_entry_hashes_before_hash(
        cursor, before_hash, limit, include_deleted
    )
    return read_entry_rows_by_hash(cursor, entry_hashes, include_deleted)


def read_entries_before_hash(
    cursor: sqlite3.Cursor,
    before_hash: bytes,
    limit: int = 500,
    include_deleted: bool = False,
) -> list[dict]:
    entry_hashes = read_entry_hashes_before_hash(
        cursor, before_hash, limit, include_deleted
    )
    return read_entries_by_hash(cursor, entry_hashes, include_deleted)


def read_entries_by_filter(
    cursor: sqlite3.Cursor,
    filter: str,
    limit: int = 500,
    include_outdated: bool = False,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of all (not deleted and not outdated) entries that match the filter."""
    return [
        convert_entry_row_to_dict(row)
        for row in read_entry_rows_by_filter(
            cursor,
            filter,
            limit,
            include_outdated,
            include_deleted,
        )
    ]


def read_entry_rows_by_filter(
    cursor: sqlite3.Cursor,
    filter: str,
    limit: int = 500,
    include_outdated: bool = False,
    include_deleted: bool = False,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of all (not deleted and not outdated) entry rows that match the filter.
    Filters are written as a comma separated list with the format: property.path__op=value,

    Here's a few filter strings as examples:
    is_file=True,time_edited__lt=1685728424
    time_edited__lte=1685728424,title__in=["potat","otherpotat"]
    time_edited__gt=1685728424
    time_edited__gte=1685728424
    content__contains="word"
    content__icontains="potato"
    """

# EXAMPLE SQL statement from internet:
    cursor.execute("""
        SELECT c.customer_id
FROM customers c
WHERE c.state = 'MI'
  AND EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
        AND o.money >= 55
  )
  AND EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
        AND o.order_date >= '2026-01-01'
  )
  AND EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
        AND o.last_login_date >= '2025-05-04'
  );

    """)

    # TODO: implement this function

    conditions = _parse_entry_filter(filter)
    if not conditions:
        return candidate_rows

    if include_outdated:
        if include_deleted:
            pass
        else:
            pass
    else:
        if include_deleted:
            pass
        else:
            pass


_FILTER_OPS = {"lt", "lte", "gt", "gte", "in", "contains", "icontains", "eq", "exists"}


def _parse_entry_filter(filter: str) -> list[tuple[list[str], str, typing.Any]]:
    """Parses a filter string into a list of (property_path, op, value) tuples."""
    conditions = []
    if not filter or not filter.strip():
        return conditions
    for condition_str in filter.split(","):
        if "=" in condition_str:
            key_part, value_part = condition_str.split("=", 1)
        else:
            key_part, value_part = condition_str, ""
        key_part = key_part.strip()
        value_part = value_part.strip()

        # extract op
        if "__" in key_part:
            path, op = key_part.rsplit("__", 1)
            if op not in _FILTER_OPS or not path:
                path, op = key_part, "eq"
        else:
            path, op = key_part, "eq"
        path = path.split(".")

        # extract value
        if value_part == "" and op == "eq":
            op = "exists"
        else:
            try:
                value = json.loads(value_part)
                if isinstance(value, (dict, list)):
                    value = value_part
            except (ValueError, SyntaxError):
                value = value_part  # fall back to raw string
        conditions.append((path, op, value))
    return conditions


def write_entry_dict(
    cursor: sqlite3.Cursor,
    entry_dict: dict,
    edited_by: str,
    api_key_id: str | None = None,
):
    entry_uuid = _get_column_property(entry_dict, "uuid")
    new_timestamp = _get_column_property(entry_dict, "timestamp")
    entry_tuple = convert_entry_dict_to_tuple(entry_dict)
    entry_hash = entry_tuple[0]

    if (
        entry_uuid is not None
        and "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        # delete old versions of entry
        entry_version_hashes = read_entry_version_hashes(cursor, entry_uuid)
        if len(entry_version_hashes) > 0:
            cursor.execute(
                "DELETE FROM entries WHERE uuid = ? AND hash != ?",
                (entry_uuid, entry_hash),
            )
            cursor.execute(
                f"""
                DELETE FROM metadata_tree 
                WHERE entry_hash in ({",".join("?" for entry_version_hash in entry_version_hashes)}) 
                AND entry_hash != ?
                """,
                (*entry_version_hashes, entry_hash),
            )

    # write to entries
    cursor.execute(
        "INSERT OR REPLACE INTO entries VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ",
        entry_tuple,
    )

    # write to edit_log
    cursor.execute(
        """
        SELECT is_deletion, timestamp FROM edit_log 
        WHERE entry_hash = ? 
        ORDER BY timestamp DESC, is_deletion ASC
        LIMIT 1
        """,
        (entry_hash,),
    )
    edit_log_row = cursor.fetchone()
    if edit_log_row is None or edit_log_row["is_deletion"]:  # avoid duplicate edits
        validated_timestamp = new_timestamp
        if (
            validated_timestamp is None
            or validated_timestamp > time.time()
            or (
                edit_log_row is not None
                and edit_log_row["timestamp"] > validated_timestamp
            )
        ):
            validated_timestamp = time.time()
        if (
            "archive_mode" in quasilattice.config
            and not quasilattice.config["archive_mode"]
        ):
            # delete outdated entries from edit_log
            if entry_uuid is not None:
                cursor.execute(
                    "DELETE FROM edit_log WHERE entry_uuid = ? AND timestamp < ?",
                    (entry_uuid, validated_timestamp),
                )
            else:
                cursor.execute(
                    "DELETE FROM edit_log WHERE entry_hash = ? AND timestamp < ?",
                    (entry_hash, validated_timestamp),
                )
        write_edit_log(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": entry_uuid,
                "is_deletion": False,
                "timestamp": validated_timestamp,
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )

    # write metadata
    for key, value in entry_dict.items():
        if not is_entry_property_stored_in_columns(key, value):
            write_metadata_tree_rows_by_key_value(
                cursor, entry_hash, new_timestamp, key, value
            )


def delete_entry_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    edited_by: str,
    api_key_id: str | None = None,
):
    if "archive_mode" not in quasilattice.config or quasilattice.config["archive_mode"]:
        entry_version_hashes = read_entry_version_hashes(cursor, entry_uuid)
        current_time = time.time()
        for entry_hash in entry_version_hashes:
            write_edit_log(
                cursor,
                {
                    "entry_hash": entry_hash,
                    "entry_uuid": entry_uuid,
                    "is_deletion": True,
                    "timestamp": current_time,
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )
    else:
        entry_version_hashes = read_entry_version_hashes(cursor, entry_uuid)
        if len(entry_version_hashes) > 0:
            cursor.execute(
                "DELETE FROM entries WHERE uuid = ?",
                (entry_uuid,),
            )
            cursor.execute(
                "DELETE FROM edit_log WHERE entry_uuid = ?",
                (entry_uuid,),
            )
            cursor.execute(
                "DELETE FROM aliases WHERE entry_uuid = ?",
                (entry_uuid,),
            )
            cursor.execute(
                "DELETE FROM read_access WHERE entry_uuid = ?",
                (entry_uuid,),
            )
            cursor.execute(
                "DELETE FROM write_access WHERE entry_uuid = ?",
                (entry_uuid,),
            )
            cursor.execute(
                f"""
                DELETE FROM metadata_tree 
                WHERE entry_hash in ({",".join("?" for entry_version_hash in entry_version_hashes)}) 
                """,
                entry_version_hashes,
            )


def undelete_entry_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    edited_by: str,
    api_key_id: str | None = None,
) -> bool:
    cursor.execute(
        """
        SELECT * FROM edit_log 
        WHERE entry_uuid = ? AND is_deletion = 0 
        ORDER BY timestamp DESC, entry_hash DESC 
        LIMIT 1
        """,
        (entry_uuid,),
    )
    last_write_edit_log_row = cursor.fetchone()
    if last_write_edit_log_row is None:  # no version to restore
        return False
    cursor.execute(
        """
        SELECT * FROM edit_log 
        WHERE entry_uuid = ?
        ORDER BY timestamp DESC, is_deletion ASC, entry_hash DESC 
        LIMIT 1
        """,
        (entry_uuid,),
    )
    last_edit_log_row = cursor.fetchone()
    if last_edit_log_row["is_deletion"]:
        write_edit_log(
            cursor,
            {
                "entry_hash": last_write_edit_log_row["entry_hash"],
                "entry_uuid": last_write_edit_log_row["entry_uuid"],
                "is_deletion": False,
                "timestamp": time.time(),
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    return True


def delete_entry_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    edited_by: str,
    api_key_id: str | None = None,
):
    if "archive_mode" not in quasilattice.config or quasilattice.config["archive_mode"]:
        entry_row = read_entry_row_by_hash(cursor, entry_hash)
        if entry_row is not None:
            write_edit_log(
                cursor,
                {
                    "entry_hash": entry_hash,
                    "entry_uuid": entry_row["uuid"],
                    "is_deletion": True,
                    "timestamp": time.time(),
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )
    else:
        cursor.execute(
            "DELETE FROM entries WHERE hash = ?",
            (entry_hash,),
        )
        cursor.execute(
            "DELETE FROM edit_log WHERE entry_hash = ?",
            (entry_hash,),
        )
        cursor.execute(
            "DELETE FROM aliases WHERE entry_hash = ?",
            (entry_hash,),
        )
        cursor.execute(
            "DELETE FROM read_access WHERE entry_hash = ?",
            (entry_hash,),
        )
        cursor.execute(
            "DELETE FROM write_access WHERE entry_hash = ?",
            (entry_hash,),
        )
        cursor.execute(
            "DELETE FROM metadata_tree WHERE entry_hash = ?",
            (entry_hash,),
        )


def undelete_entry_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    edited_by: str,
    api_key_id: str | None = None,
) -> bool:
    cursor.execute(
        """
        SELECT * FROM edit_log 
        WHERE entry_hash = ? AND is_deletion = 0 
        ORDER BY timestamp DESC 
        LIMIT 1
        """,
        (entry_hash,),
    )
    last_write_edit_log_row = cursor.fetchone()
    if last_write_edit_log_row is None:  # no version to restore
        return False
    cursor.execute(
        """
        SELECT * FROM edit_log 
        WHERE entry_hash = ?
        ORDER BY timestamp DESC, is_deletion ASC
        LIMIT 1
        """,
        (entry_hash,),
    )
    last_edit_log_row = cursor.fetchone()
    if last_edit_log_row["is_deletion"]:
        write_edit_log(
            cursor,
            {
                "entry_hash": last_write_edit_log_row["entry_hash"],
                "entry_uuid": last_write_edit_log_row["entry_uuid"],
                "is_deletion": False,
                "timestamp": time.time(),
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    return True


def convert_entry_row_to_dict(entry_row: sqlite3.Row) -> dict:
    entry_dict = {}
    if entry_row["uuid"] is not None:
        entry_dict["uuid"] = str(uuid.UUID(bytes=entry_row["uuid"]))
    if entry_row["timestamp"] is not None:
        entry_dict["timestamp"] = entry_row["timestamp"]
    if entry_row["edited_by"] is not None:
        entry_dict["edited_by"] = entry_row["edited_by"]
    if entry_row["is_file"] is not None:
        entry_dict["is_file"] = bool(entry_row["is_file"] == 1)
    if entry_row["file_hash"] is not None:
        entry_dict["file_hash"] = bytes(entry_row["file_hash"]).hex()
    if entry_row["markup_language"] is not None:
        entry_dict["markup_language"] = entry_row["markup_language"]
    if entry_row["title"] is not None:
        entry_dict["title"] = entry_row["title"]
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

    # construct tuple
    entry_tuple = (
        calculate_entry_hash_from_dict(entry_dict),
        _get_column_property(entry_dict, "uuid"),
        _get_column_property(entry_dict, "timestamp"),
        _get_column_property(entry_dict, "edited_by"),
        _get_column_property(entry_dict, "is_file"),
        _get_column_property(entry_dict, "file_hash"),
        _get_column_property(entry_dict, "markup_language"),
        _get_column_property(entry_dict, "title"),
        _get_column_property(entry_dict, "content"),
        metadata_text,
        metadata_zstd,
    )
    return entry_tuple


def is_entry_property_stored_in_columns(key: str, value) -> bool:
    if key in ENTRY_COLUMNS and isinstance(value, ENTRY_COLUMNS[key]):
        return True
    if value is None:
        return False
    if key == "timestamp" and isinstance(value, int):
        return True
    if key == "uuid":
        if isinstance(value, bytes):
            try:
                uuid.UUID(bytes=value)
                return True  # uuid bytes are valid
            except (TypeError, ValueError):
                return False
        else:
            try:
                uuid.UUID(value)
                return True  # uuid is valid
            except (TypeError, ValueError):
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
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, bytes):
            value = str(uuid.UUID(bytes=value))
        else:
            value = str(uuid.UUID(value))
    elif key == "file_hash":
        if isinstance(value, bytes):
            value = value.hex()
        try:
            value = bytes.fromhex(value).hex()
        except (TypeError, ValueError):
            pass
    else:
        value = ENTRY_COLUMNS[key](value)
    return value


def calculate_canonical_entry_bytes_from_dict(entry_dict: dict) -> bytes:
    hashable_dict = {
        key: normalize_entry_property_stored_in_columns(key, value)
        if is_entry_property_stored_in_columns(key, value)
        else value
        for key, value in entry_dict.items()
    }
    return rfc8785.dumps(hashable_dict)


def calculate_entry_hash_from_dict(entry_dict: dict) -> bytes:
    hashable_bytes = calculate_canonical_entry_bytes_from_dict(entry_dict)
    return hashlib.sha256(hashable_bytes).digest()


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


# endregion


# region edit_log
def read_edit_log_rows_after_time(
    cursor: sqlite3.Cursor, after_timestamp: float, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of edit_log rows after after_timestamp."""
    cursor.execute(
        """
            SELECT * FROM edit_log
            WHERE timestamp > ?
            ORDER BY timestamp ASC LIMIT ?
            """,
        (after_timestamp, limit),
    )
    return cursor.fetchall()


def read_edit_log_rows_before_time(
    cursor: sqlite3.Cursor, before_timestamp: float, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of edit_log rows before before_timestamp."""
    cursor.execute(
        """
            SELECT * FROM edit_log
            WHERE timestamp < ?
            ORDER BY timestamp DESC LIMIT ?
            """,
        (before_timestamp, limit),
    )
    return cursor.fetchall()


def read_edit_log_rows_after_hash(
    cursor: sqlite3.Cursor, after_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of edit_log rows after after_hash."""
    cursor.execute(
        """
            SELECT * FROM edit_log
            WHERE hash > ?
            ORDER BY hash ASC LIMIT ?
            """,
        (after_hash, limit),
    )
    return cursor.fetchall()


def read_edit_log_rows_before_hash(
    cursor: sqlite3.Cursor, before_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of edit_log rows before before_hash."""
    cursor.execute(
        """
            SELECT * FROM edit_log
            WHERE hash < ?
            ORDER BY hash DESC LIMIT ?
            """,
        (before_hash, limit),
    )
    return cursor.fetchall()


def write_edit_log(cursor: sqlite3.Cursor, edit_log: dict | sqlite3.Row | tuple):
    if isinstance(edit_log, dict):
        edit_log = convert_edit_log_to_tuple(edit_log)
    cursor.execute(
        "INSERT OR REPLACE INTO edit_log VALUES(?, ?, ?, ?, ?, ?, ?) ",
        edit_log,
    )


def normalize_edit_log(edit_log: dict | sqlite3.Row | tuple) -> dict:
    if isinstance(edit_log, tuple):
        return convert_edit_log_to_dict(edit_log)

    if isinstance(edit_log["entry_hash"], str):
        entry_hash_str = bytes.fromhex(edit_log["entry_hash"]).hex()
    else:
        entry_hash_str = bytes(edit_log["entry_hash"]).hex()

    if edit_log["entry_uuid"] is None:
        entry_uuid_str = None
    elif isinstance(edit_log["entry_uuid"], uuid.UUID):
        entry_uuid_str = str(edit_log["entry_uuid"])
    elif isinstance(edit_log["entry_uuid"], bytes):
        entry_uuid_str = str(uuid.UUID(bytes=edit_log["entry_uuid"]))
    else:
        entry_uuid_str = str(uuid.UUID(edit_log["entry_uuid"]))

    return {
        "entry_hash": entry_hash_str,
        "entry_uuid": entry_uuid_str,
        "is_deletion": bool(edit_log["is_deletion"]),
        "timestamp": float(edit_log["timestamp"]),
        "edited_by": str(edit_log["edited_by"]),
        "api_key_id": str(edit_log["api_key_id"])
        if edit_log["api_key_id"] is not None
        else None,
    }


def calculate_edit_log_hash(edit_log: dict | sqlite3.Row) -> bytes:
    hashable_dict = normalize_edit_log(edit_log)
    hashable_bytes = rfc8785.dumps(hashable_dict)
    return hashlib.sha256(hashable_bytes).digest()


def convert_edit_log_to_tuple(edit_log: dict | sqlite3.Row) -> tuple:
    edit_log = normalize_edit_log(edit_log)
    return (
        bytes.fromhex(edit_log["entry_hash"]),
        uuid.UUID(edit_log["entry_uuid"]).bytes
        if edit_log["entry_uuid"] is not None
        else None,
        edit_log["is_deletion"],
        edit_log["timestamp"],
        edit_log["edited_by"],
        edit_log["api_key_id"],
        calculate_edit_log_hash(edit_log),
    )


def convert_edit_log_to_dict(edit_log_tuple: sqlite3.Row | tuple) -> dict:
    alias_dict = {
        "entry_hash": edit_log_tuple[0],
        "entry_uuid": edit_log_tuple[1],
        "is_deletion": edit_log_tuple[2],
        "timestamp": edit_log_tuple[3],
        "edited_by": edit_log_tuple[4],
        "api_key_id": edit_log_tuple[5],
    }
    return normalize_edit_log(alias_dict)


# endregion


# region aliases
def read_aliases_by_uuid(cursor: sqlite3.Cursor, entry_uuid: bytes) -> list[str]:
    return [row["alias"] for row in read_alias_rows_by_uuid(cursor, entry_uuid)]


def read_alias_rows_by_uuid(
    cursor: sqlite3.Cursor, entry_uuid: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current alias rows for an entry by uuid."""
    cursor.execute(
        """
        SELECT * FROM aliases AS aliases1
        WHERE aliases1.entry_uuid = ?
        AND aliases1.time_edited = (
            SELECT MAX(time_edited) FROM aliases WHERE alias = aliases1.alias
        )
        """,
        (entry_uuid,),
    )
    return cursor.fetchall()


def read_aliases_by_hash(cursor: sqlite3.Cursor, entry_hash: bytes) -> list[str]:
    return [row["alias"] for row in read_alias_rows_by_hash(cursor, entry_hash)]


def read_alias_rows_by_hash(
    cursor: sqlite3.Cursor, entry_hash: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current alias rows for an entry by hash."""
    cursor.execute(
        """
        SELECT * FROM aliases AS aliases1
        WHERE aliases1.entry_hash = ?
        AND aliases1.time_edited = (
            SELECT MAX(time_edited) FROM aliases WHERE alias = aliases1.alias
        )
        """,
        (entry_hash,),
    )
    return cursor.fetchall()


def read_alias_row(cursor: sqlite3.Cursor, alias: str) -> sqlite3.Row | None:
    """Returns the most recent alias_row, or None if it doesn't exist."""
    case_sensitive = quasilattice.config["quasilattice"]["case_sensitive_aliases"]
    if case_sensitive:
        cursor.execute(
            """
            SELECT * FROM aliases
            WHERE alias = ?
            ORDER BY time_edited DESC LIMIT 1
            """,
            (alias,),
        )
    else:
        cursor.execute(
            """
            SELECT * FROM aliases
            WHERE LOWER(alias) = ?
            ORDER BY time_edited DESC LIMIT 1
            """,
            (alias.lower(),),
        )
    return cursor.fetchone()


def read_alias_rows_by_alias(
    cursor: sqlite3.Cursor,
    aliases: list[str],
    limit: int = 500,
    order_by_hash: bool = False,
) -> list[sqlite3.Row]:
    """Returns a list of the most up to date rows of aliases."""
    case_sensitive = quasilattice.config["quasilattice"]["case_sensitive_aliases"]
    if case_sensitive:
        cursor.execute(
            f"""
            SELECT * FROM aliases AS aliases1
            WHERE aliases1.alias IN ({",".join("?" for alias in aliases)})
                AND aliases1.time_edited = (
                    SELECT MAX(time_edited) FROM aliases WHERE alias = aliases1.alias
                )
            ORDER BY {"hash DESC" if order_by_hash else "time_edited DESC"}
            LIMIT ?
            """,
            (*aliases, limit),
        )
    else:
        cursor.execute(
            f"""
            SELECT * FROM aliases AS aliases1
            WHERE LOWER(aliases1.alias) IN ({",".join("?" for alias in aliases)})
                AND aliases1.time_edited = (
                    SELECT MAX(time_edited) FROM aliases WHERE alias = aliases1.alias
                )
            ORDER BY {"hash DESC" if order_by_hash else "time_edited DESC"}
            LIMIT ?
            """,
            (*[alias.lower() for alias in aliases], limit),
        )
    return cursor.fetchall()


def read_alias_rows_after_time(
    cursor: sqlite3.Cursor, after_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of alias rows after after_time."""
    cursor.execute(
        """
            SELECT * FROM aliases
            WHERE time_edited > ?
            ORDER BY time_edited ASC LIMIT ?
            """,
        (after_time, limit),
    )
    return cursor.fetchall()


def read_alias_rows_before_time(
    cursor: sqlite3.Cursor, before_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of alias rows before before_time."""
    cursor.execute(
        """
            SELECT * FROM aliases
            WHERE time_edited < ?
            ORDER BY time_edited DESC LIMIT ?
            """,
        (before_time, limit),
    )
    return cursor.fetchall()


def read_alias_rows_after_hash(
    cursor: sqlite3.Cursor, after_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of alias rows after after_hash."""
    cursor.execute(
        """
            SELECT * FROM aliases
            WHERE hash > ?
            ORDER BY hash ASC LIMIT ?
            """,
        (after_hash, limit),
    )
    return cursor.fetchall()


def read_alias_rows_before_hash(
    cursor: sqlite3.Cursor, before_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of alias rows before before_hash."""
    cursor.execute(
        """
            SELECT * FROM aliases
            WHERE hash < ?
            ORDER BY hash DESC LIMIT ?
            """,
        (before_hash, limit),
    )
    return cursor.fetchall()


def write_alias_row(cursor: sqlite3.Cursor, alias_data: dict | sqlite3.Row | tuple):
    if isinstance(alias_data, dict):
        alias_data = convert_alias_to_tuple(alias_data)
    cursor.execute(
        "INSERT OR REPLACE INTO aliases VALUES(?, ?, ?, ?, ?, ?, ?) ", alias_data
    )


def set_aliases_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    aliases: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_uuid(cursor, entry_uuid)
    for existing_alias in existing_aliases:
        if existing_alias not in aliases:  # should remove existing_alias
            if (
                "archive_mode" in quasilattice.config
                and not quasilattice.config["archive_mode"]
            ):
                # delete existing alias
                cursor.execute(
                    "DELETE FROM aliases WHERE alias = ? ", (existing_alias,)
                )
            else:
                # mark alias deleted
                write_alias_row(
                    cursor,
                    {
                        "entry_hash": None,
                        "entry_uuid": None,
                        "alias": existing_alias,
                        "time_edited": int(time.time()),
                        "edited_by": edited_by,
                        "api_key_id": api_key_id,
                    },
                )
    for alias in aliases:
        if alias not in existing_aliases:
            write_alias_row(
                cursor,
                {
                    "entry_hash": None,
                    "entry_uuid": entry_uuid,
                    "alias": alias,
                    "time_edited": int(time.time()),
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )
    _delete_outdated_aliases_if_not_in_archive_mode(cursor)


def add_alias_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    alias: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_uuid(cursor, entry_uuid)
    if alias not in existing_aliases:  # should add alias
        write_alias_row(
            cursor,
            {
                "entry_hash": None,
                "entry_uuid": entry_uuid,
                "alias": alias,
                "time_edited": int(time.time()),
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
        _delete_outdated_aliases_if_not_in_archive_mode(cursor)


def remove_alias_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    alias: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_uuid(cursor, entry_uuid)
    if alias in existing_aliases:  # should remove alias
        if (
            "archive_mode" in quasilattice.config
            and not quasilattice.config["archive_mode"]
        ):
            # delete existing alias
            cursor.execute("DELETE FROM aliases WHERE alias = ? ", (alias,))
        else:
            # mark alias deleted
            write_alias_row(
                cursor,
                {
                    "entry_hash": None,
                    "entry_uuid": None,
                    "alias": alias,
                    "time_edited": int(time.time()),
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )


def set_aliases_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    aliases: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_hash(cursor, entry_hash)
    for existing_alias in existing_aliases:
        if existing_alias not in aliases:  # should remove existing_alias
            if (
                "archive_mode" in quasilattice.config
                and not quasilattice.config["archive_mode"]
            ):
                # delete existing alias
                cursor.execute(
                    "DELETE FROM aliases WHERE alias = ? ", (existing_alias,)
                )
            else:
                # mark alias deleted
                write_alias_row(
                    cursor,
                    {
                        "entry_hash": None,
                        "entry_uuid": None,
                        "alias": existing_alias,
                        "time_edited": int(time.time()),
                        "edited_by": edited_by,
                        "api_key_id": api_key_id,
                    },
                )
    for alias in aliases:
        if alias not in existing_aliases:
            # add alias
            write_alias_row(
                cursor,
                {
                    "entry_hash": entry_hash,
                    "entry_uuid": None,
                    "alias": alias,
                    "time_edited": int(time.time()),
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )
    _delete_outdated_aliases_if_not_in_archive_mode(cursor)


def add_alias_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    alias: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_hash(cursor, entry_hash)
    if alias not in existing_aliases:
        # add alias
        write_alias_row(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": None,
                "alias": alias,
                "time_edited": int(time.time()),
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
        _delete_outdated_aliases_if_not_in_archive_mode(cursor)


def remove_alias_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    alias: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_aliases = read_aliases_by_hash(cursor, entry_hash)
    if alias in existing_aliases:  # should remove alias
        if (
            "archive_mode" in quasilattice.config
            and not quasilattice.config["archive_mode"]
        ):
            # delete existing alias
            cursor.execute("DELETE FROM aliases WHERE alias = ? ", (alias,))
        else:
            # mark alias deleted
            write_alias_row(
                cursor,
                {
                    "entry_hash": None,
                    "entry_uuid": None,
                    "alias": alias,
                    "time_edited": int(time.time()),
                    "edited_by": edited_by,
                    "api_key_id": api_key_id,
                },
            )


def write_default_alias_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    edited_by: str,
    api_key_id: str | None = None,
    ignore_existing_aliases: bool = False,
):
    if ignore_existing_aliases or len(read_aliases_by_uuid(cursor, entry_uuid)) == 0:
        add_alias_by_uuid(
            cursor,
            entry_uuid,
            _generate_unique_default_alias_str(cursor),
            edited_by,
            api_key_id,
        )


def write_default_alias_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    edited_by: str,
    api_key_id: str | None = None,
    ignore_existing_aliases: bool = False,
):
    if ignore_existing_aliases or len(read_aliases_by_hash(cursor, entry_hash)) == 0:
        add_alias_by_hash(
            cursor,
            entry_hash,
            _generate_unique_default_alias_str(cursor),
            edited_by,
            api_key_id,
        )


def _generate_unique_default_alias_str(cursor: sqlite3.Cursor) -> str:
    alias_generation_start = time.time()
    timeout_ms = quasilattice.config["quasilattice"]["default_alias_timeout_ms"]
    chars = quasilattice.config["quasilattice"]["default_alias_characters"]

    if len(chars) != len(set(chars)):
        logger.critical("Duplicate characters in default_alias_characters")
        raise ValueError("Duplicate characters in default_alias_characters")

    if len(chars) < 2:
        logger.critical("To few characters in default_alias_characters")
        raise ValueError("To few characters in default_alias_characters")

    # blindly try to find a unique alias with the current_default_alias_length
    while time.time() - alias_generation_start < timeout_ms / 1000.0:
        default_alias = "".join(
            random.choices(chars, k=quasilattice.current_default_alias_length)
        )
        if read_alias_row(cursor, default_alias) is None:  # found a unique alias!!
            return default_alias

    logger.debug("Default alias generation timed out")

    # recalculate current_default_alias_length
    cursor.execute("SELECT COUNT(DISTINCT alias) FROM aliases")
    count = max(cursor.fetchone()[0], 10)
    quasilattice.current_default_alias_length = max(
        math.ceil(math.log(count * 100 / 99, len(chars))),
        quasilattice.current_default_alias_length,
    )
    update_info(cursor)

    logger.debug(
        "Current default alias length = "
        + str(int(quasilattice.current_default_alias_length))
    )

    # find a unique alias (guaranteed to succeed eventually)
    while True:  # 99.996% chance this completes in less than 1000 iterations
        default_alias = "".join(
            random.choices(chars, k=quasilattice.current_default_alias_length)
        )
        if read_alias_row(cursor, default_alias) is None:
            return default_alias


def normalize_alias(alias_data: dict | sqlite3.Row | tuple) -> dict:
    if isinstance(alias_data, tuple):
        return convert_alias_to_dict(alias_data)

    if alias_data["entry_hash"] is None:
        entry_hash_str = None
    elif isinstance(alias_data["entry_hash"], str):
        entry_hash_str = bytes.fromhex(alias_data["entry_hash"]).hex()
    else:
        entry_hash_str = bytes(alias_data["entry_hash"]).hex()

    if alias_data["entry_uuid"] is None:
        entry_uuid_str = None
    elif isinstance(alias_data["entry_uuid"], uuid.UUID):
        entry_uuid_str = str(alias_data["entry_uuid"])
    elif isinstance(alias_data["entry_uuid"], bytes):
        entry_uuid_str = str(uuid.UUID(bytes=alias_data["entry_uuid"]))
    else:
        entry_uuid_str = str(uuid.UUID(alias_data["entry_uuid"]))

    return {
        "entry_hash": entry_hash_str,
        "entry_uuid": entry_uuid_str,
        "alias": str(alias_data["alias"]),
        "time_edited": int(alias_data["time_edited"]),
        "edited_by": str(alias_data["edited_by"]),
        "api_key_id": str(alias_data["api_key_id"])
        if alias_data["api_key_id"] is not None
        else None,
    }


def calculate_alias_hash(alias_data: dict | sqlite3.Row | tuple) -> bytes:
    hashable_dict = normalize_alias(alias_data)
    hashable_bytes = rfc8785.dumps(hashable_dict)
    return hashlib.sha256(hashable_bytes).digest()


def convert_alias_to_tuple(alias_data: dict | sqlite3.Row):
    alias_dict = normalize_alias(alias_data)
    return (
        bytes.fromhex(alias_dict["entry_hash"])
        if alias_dict["entry_hash"] is not None
        else None,
        uuid.UUID(alias_dict["entry_uuid"]).bytes
        if alias_dict["entry_uuid"] is not None
        else None,
        alias_dict["alias"],
        alias_dict["time_edited"],
        alias_dict["edited_by"],
        alias_dict["api_key_id"],
        calculate_alias_hash(alias_dict),
    )


def convert_alias_to_dict(alias_tuple: sqlite3.Row | tuple) -> dict:
    alias_dict = {
        "entry_hash": alias_tuple[0],
        "entry_uuid": alias_tuple[1],
        "alias": alias_tuple[2],
        "time_edited": alias_tuple[3],
        "edited_by": alias_tuple[4],
        "api_key_id": alias_tuple[5],
    }
    return normalize_alias(alias_dict)


def _delete_outdated_aliases_if_not_in_archive_mode(cursor: sqlite3.Cursor):
    if (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        # delete outdated alias rows
        cursor.execute(
            """
            DELETE FROM aliases AS aliases1
            WHERE aliases1.time_edited < (
                SELECT MAX(time_edited) FROM aliases WHERE alias = aliases1.alias
            )
            """
        )


# endregion


# region read_access
def read_read_accesses_by_uuid(cursor: sqlite3.Cursor, entry_uuid: bytes) -> list[str]:
    read_access_rows = read_read_access_rows_by_uuid(cursor, entry_uuid)
    if len(read_access_rows) == 0:
        # default access
        cursor.execute(
            """
            SELECT edited_by, api_key_id FROM edit_log 
            WHERE entry_uuid = ?
            ORDER BY timestamp ASC, is_deletion ASC, entry_hash ASC 
            LIMIT 1
            """,
            (entry_uuid,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            return []
        else:
            if edit_log_data["api_key_id"] is not None:
                return [edit_log_data["edited_by"], edit_log_data["api_key_id"]]
            return [edit_log_data["edited_by"]]
    elif len(read_access_rows) == 1 and read_access_rows[0]["read_access"] is None:
        return []  # public entry
    return [row["read_access"] for row in read_access_rows]


def read_read_access_rows_by_uuid(
    cursor: sqlite3.Cursor, entry_uuid: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current read_access rows for an entry by uuid."""
    cursor.execute(
        """
        SELECT * FROM read_access
        WHERE entry_uuid = ?
          AND time_edited = (
              SELECT MAX(time_edited) FROM read_access WHERE entry_uuid = ?
          )
        """,
        (entry_uuid, entry_uuid),
    )
    return cursor.fetchall()


def read_read_accesses_by_hash(cursor: sqlite3.Cursor, entry_hash: bytes) -> list[str]:
    read_access_rows = read_read_access_rows_by_hash(cursor, entry_hash)
    if len(read_access_rows) == 0:
        # default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            return []
        else:
            if edit_log_data["entry_uuid"] is not None:
                return read_read_access_rows_by_uuid(
                    cursor, edit_log_data["entry_uuid"]
                )
            if edit_log_data["api_key_id"] is not None:
                return [edit_log_data["edited_by"], edit_log_data["api_key_id"]]
            return [edit_log_data["edited_by"]]
    elif len(read_access_rows) == 1 and read_access_rows[0]["read_access"] is None:
        return []  # public entry
    return [row["read_access"] for row in read_access_rows]


def read_read_access_rows_by_hash(
    cursor: sqlite3.Cursor, entry_hash: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current read_access rows for an entry by hash."""
    cursor.execute(
        """
        SELECT * FROM read_access
        WHERE entry_hash = ?
          AND time_edited = (
              SELECT MAX(time_edited) FROM read_access WHERE entry_hash = ?
          )
        """,
        (entry_hash, entry_hash),
    )
    return cursor.fetchall()


def read_read_access_rows_after_time(
    cursor: sqlite3.Cursor, after_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of read_access rows after after_time."""
    cursor.execute(
        """
            SELECT * FROM read_access
            WHERE time_edited > ?
            ORDER BY time_edited ASC LIMIT ?
            """,
        (after_time, limit),
    )
    return cursor.fetchall()


def read_read_access_rows_before_time(
    cursor: sqlite3.Cursor, before_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of read_access rows before before_time."""
    cursor.execute(
        """
            SELECT * FROM read_access
            WHERE time_edited < ?
            ORDER BY time_edited DESC LIMIT ?
            """,
        (before_time, limit),
    )
    return cursor.fetchall()


def read_read_access_rows_after_hash(
    cursor: sqlite3.Cursor, after_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of read_access rows after after_hash."""
    cursor.execute(
        """
            SELECT * FROM read_access
            WHERE hash > ?
            ORDER BY hash ASC LIMIT ?
            """,
        (after_hash, limit),
    )
    return cursor.fetchall()


def read_read_access_rows_before_hash(
    cursor: sqlite3.Cursor, before_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of read_access rows before before_hash."""
    cursor.execute(
        """
            SELECT * FROM read_access
            WHERE hash < ?
            ORDER BY hash DESC LIMIT ?
            """,
        (before_hash, limit),
    )
    return cursor.fetchall()


def write_read_access_row(
    cursor: sqlite3.Cursor, read_access_data: dict | sqlite3.Row | tuple
):
    if isinstance(read_access_data, dict):
        read_access_data = convert_read_access_to_tuple(read_access_data)
    cursor.execute(
        "INSERT OR REPLACE INTO read_access VALUES(?, ?, ?, ?, ?, ?, ?) ",
        read_access_data,
    )


def set_read_accesses_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    read_accesses: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_read_access_rows = read_read_access_rows_by_uuid(cursor, entry_uuid)
    existing_read_accesses = [row["read_access"] for row in existing_read_access_rows]
    current_time = int(time.time())
    if len(read_accesses) == 0:
        write_read_access_row(
            cursor,
            {
                "entry_hash": None,
                "entry_uuid": entry_uuid,
                "read_access": None,
                "time_edited": current_time,
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    for read_access in read_accesses:
        write_read_access_row(
            cursor,
            {
                "entry_hash": None,
                "entry_uuid": entry_uuid,
                "read_access": read_access,
                "time_edited": current_time,
                "edited_by": edited_by
                if read_access not in existing_read_accesses
                else existing_read_access_rows[
                    existing_read_accesses.index(read_access)
                ]["edited_by"],
                "api_key_id": api_key_id
                if read_access not in existing_read_accesses
                else existing_read_access_rows[
                    existing_read_accesses.index(read_access)
                ]["api_key_id"],
            },
        )
    _delete_outdated_read_access_if_not_in_archive_mode(cursor)


def add_read_access_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    read_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    read_accesses = read_read_accesses_by_uuid(cursor, entry_uuid)
    if read_access not in read_accesses:
        read_accesses.append(read_access)
        set_read_accesses_by_uuid(
            cursor, entry_uuid, read_accesses, edited_by, api_key_id
        )


def remove_read_access_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    read_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    read_accesses = read_read_accesses_by_uuid(cursor, entry_uuid)
    if read_access in read_accesses:
        read_accesses.remove(read_access)
        set_read_accesses_by_uuid(
            cursor, entry_uuid, read_accesses, edited_by, api_key_id
        )


def set_read_accesses_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    read_accesses: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_read_access_rows = read_read_access_rows_by_hash(cursor, entry_hash)
    existing_read_accesses = [row["read_access"] for row in existing_read_access_rows]
    if len(existing_read_access_rows) == 0:
        # check if this hash references a uuid
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            logger.critical(f"Entry with sha256 hash {entry_hash.hex()} does not exist")
            raise LookupError(
                f"Entry with sha256 hash {entry_hash.hex()} does not exist"
            )
        if edit_log_data["entry_uuid"] is not None:
            return set_read_accesses_by_uuid(
                cursor,
                edit_log_data["entry_uuid"],
                read_accesses,
                edited_by,
                api_key_id,
            )
    current_time = int(time.time())
    if len(read_accesses) == 0:
        write_read_access_row(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": None,
                "read_access": None,
                "time_edited": current_time,
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    for read_access in read_accesses:
        write_read_access_row(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": None,
                "read_access": read_access,
                "time_edited": current_time,
                "edited_by": edited_by
                if read_access not in existing_read_accesses
                else existing_read_access_rows[
                    existing_read_accesses.index(read_access)
                ]["edited_by"],
                "api_key_id": api_key_id
                if read_access not in existing_read_accesses
                else existing_read_access_rows[
                    existing_read_accesses.index(read_access)
                ]["api_key_id"],
            },
        )
    _delete_outdated_read_access_if_not_in_archive_mode(cursor)


def add_read_access_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    read_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    read_access_rows = read_read_access_rows_by_hash(cursor, entry_hash)
    read_accesses = [row["read_access"] for row in read_access_rows]
    if len(read_access_rows) == 0:
        # account for default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is not None:
            if edit_log_data["entry_uuid"] is not None:
                return add_read_access_by_uuid(
                    cursor,
                    edit_log_data["entry_uuid"],
                    read_access,
                    edited_by,
                    api_key_id,
                )
            read_accesses.append(edit_log_data["edited_by"])
            if edit_log_data["api_key_id"] is not None:
                read_accesses.append(edit_log_data["api_key_id"])
    if read_access not in read_accesses:
        read_accesses.append(read_access)
        set_read_accesses_by_hash(
            cursor, entry_hash, read_accesses, edited_by, api_key_id
        )


def remove_read_access_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    read_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    read_access_rows = read_read_access_rows_by_hash(cursor, entry_hash)
    read_accesses = [row["read_access"] for row in read_access_rows]
    if len(read_access_rows) == 0:
        # account for default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is not None:
            if edit_log_data["entry_uuid"] is not None:
                return remove_read_access_by_uuid(
                    cursor,
                    edit_log_data["entry_uuid"],
                    read_access,
                    edited_by,
                    api_key_id,
                )
            read_accesses.append(edit_log_data["edited_by"])
            if edit_log_data["api_key_id"] is not None:
                read_accesses.append(edit_log_data["api_key_id"])
    if read_access in read_accesses:
        read_accesses.remove(read_access)
        set_read_accesses_by_hash(
            cursor, entry_hash, read_accesses, edited_by, api_key_id
        )


def normalize_read_access(read_access_data: dict | sqlite3.Row | tuple) -> dict:
    if isinstance(read_access_data, tuple):
        return convert_read_access_to_dict(read_access_data)

    if read_access_data["entry_hash"] is None:
        entry_hash_str = None
    elif isinstance(read_access_data["entry_hash"], str):
        entry_hash_str = bytes.fromhex(read_access_data["entry_hash"]).hex()
    else:
        entry_hash_str = bytes(read_access_data["entry_hash"]).hex()

    if read_access_data["entry_uuid"] is None:
        entry_uuid_str = None
    elif isinstance(read_access_data["entry_uuid"], uuid.UUID):
        entry_uuid_str = str(read_access_data["entry_uuid"])
    elif isinstance(read_access_data["entry_uuid"], bytes):
        entry_uuid_str = str(uuid.UUID(bytes=read_access_data["entry_uuid"]))
    else:
        entry_uuid_str = str(uuid.UUID(read_access_data["entry_uuid"]))

    return {
        "entry_hash": entry_hash_str,
        "entry_uuid": entry_uuid_str,
        "read_access": str(read_access_data["read_access"])
        if read_access_data["read_access"] is not None
        else None,
        "time_edited": int(read_access_data["time_edited"]),
        "edited_by": str(read_access_data["edited_by"]),
        "api_key_id": str(read_access_data["api_key_id"])
        if read_access_data["api_key_id"] is not None
        else None,
    }


def calculate_read_access_hash(read_access_data: dict | sqlite3.Row | tuple) -> bytes:
    hashable_dict = normalize_read_access(read_access_data)
    hashable_bytes = rfc8785.dumps(hashable_dict)
    return hashlib.sha256(hashable_bytes).digest()


def convert_read_access_to_tuple(read_access_data: dict | sqlite3.Row):
    read_access_dict = normalize_read_access(read_access_data)
    return (
        bytes.fromhex(read_access_dict["entry_hash"])
        if read_access_dict["entry_hash"] is not None
        else None,
        uuid.UUID(read_access_dict["entry_uuid"]).bytes
        if read_access_dict["entry_uuid"] is not None
        else None,
        read_access_dict["read_access"],
        read_access_dict["time_edited"],
        read_access_dict["edited_by"],
        read_access_dict["api_key_id"],
        calculate_read_access_hash(read_access_dict),
    )


def convert_read_access_to_dict(read_access_tuple: sqlite3.Row | tuple) -> dict:
    read_access_dict = {
        "entry_hash": read_access_tuple[0],
        "entry_uuid": read_access_tuple[1],
        "read_access": read_access_tuple[2],
        "time_edited": read_access_tuple[3],
        "edited_by": read_access_tuple[4],
        "api_key_id": read_access_tuple[5],
    }
    return normalize_read_access(read_access_dict)


def _delete_outdated_read_access_if_not_in_archive_mode(cursor: sqlite3.Cursor):
    if (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        # delete outdated read_access rows
        cursor.execute(
            """
            DELETE FROM read_access AS read_access1
            WHERE
            (read_access1.entry_uuid IS NOT NULL
                AND entry_hash IS NULL
                AND entry_uuid = read_access1.entry_uuid)
            OR
            (read_access1.entry_hash IS NOT NULL
                AND entry_uuid IS NULL
                AND entry_hash = read_access1.entry_hash)
            )
            """
        )


# endregion


# region write_access
def read_write_accesses_by_uuid(cursor: sqlite3.Cursor, entry_uuid: bytes) -> list[str]:
    write_access_rows = read_write_access_rows_by_uuid(cursor, entry_uuid)
    if len(write_access_rows) == 0:
        # default access
        cursor.execute(
            """
            SELECT edited_by, api_key_id FROM edit_log 
            WHERE entry_uuid = ?
            ORDER BY timestamp ASC, is_deletion ASC, entry_hash ASC 
            LIMIT 1
            """,
            (entry_uuid,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            return []
        else:
            if edit_log_data["api_key_id"] is not None:
                return [edit_log_data["edited_by"], edit_log_data["api_key_id"]]
            return [edit_log_data["edited_by"]]
    elif len(write_access_rows) == 1 and write_access_rows[0]["write_access"] is None:
        return []  # public entry
    return [row["write_access"] for row in write_access_rows]


def read_write_access_rows_by_uuid(
    cursor: sqlite3.Cursor, entry_uuid: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current write_access rows for an entry by uuid."""
    cursor.execute(
        """
        SELECT * FROM write_access
        WHERE entry_uuid = ?
          AND time_edited = (
              SELECT MAX(time_edited) FROM write_access WHERE entry_uuid = ?
          )
        """,
        (entry_uuid, entry_uuid),
    )
    return cursor.fetchall()


def read_write_accesses_by_hash(cursor: sqlite3.Cursor, entry_hash: bytes) -> list[str]:
    write_access_rows = read_write_access_rows_by_hash(cursor, entry_hash)
    if len(write_access_rows) == 0:
        # default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            return []
        else:
            if edit_log_data["entry_uuid"] is not None:
                return read_write_access_rows_by_uuid(
                    cursor, edit_log_data["entry_uuid"]
                )
            if edit_log_data["api_key_id"] is not None:
                return [edit_log_data["edited_by"], edit_log_data["api_key_id"]]
            return [edit_log_data["edited_by"]]
    elif len(write_access_rows) == 1 and write_access_rows[0]["write_access"] is None:
        return []  # public entry
    return [row["write_access"] for row in write_access_rows]


def read_write_access_rows_by_hash(
    cursor: sqlite3.Cursor, entry_hash: bytes
) -> list[sqlite3.Row]:
    """Returns a list of current write_access rows for an entry by hash."""
    cursor.execute(
        """
        SELECT * FROM write_access
        WHERE entry_hash = ?
          AND time_edited = (
              SELECT MAX(time_edited) FROM write_access WHERE entry_hash = ?
          )
        """,
        (entry_hash, entry_hash),
    )
    return cursor.fetchall()


def read_write_access_rows_after_time(
    cursor: sqlite3.Cursor, after_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of write_access rows after after_time."""
    cursor.execute(
        """
            SELECT * FROM write_access
            WHERE time_edited > ?
            ORDER BY time_edited ASC LIMIT ?
            """,
        (after_time, limit),
    )
    return cursor.fetchall()


def read_write_access_rows_before_time(
    cursor: sqlite3.Cursor, before_time: int, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of write_access rows before before_time."""
    cursor.execute(
        """
            SELECT * FROM write_access
            WHERE time_edited < ?
            ORDER BY time_edited DESC LIMIT ?
            """,
        (before_time, limit),
    )
    return cursor.fetchall()


def read_write_access_rows_after_hash(
    cursor: sqlite3.Cursor, after_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of write_access rows after after_hash."""
    cursor.execute(
        """
            SELECT * FROM write_access
            WHERE hash > ?
            ORDER BY hash ASC LIMIT ?
            """,
        (after_hash, limit),
    )
    return cursor.fetchall()


def read_write_access_rows_before_hash(
    cursor: sqlite3.Cursor, before_hash: bytes, limit: int = 500
) -> list[sqlite3.Row]:
    """Returns a list of write_access rows before before_hash."""
    cursor.execute(
        """
            SELECT * FROM write_access
            WHERE hash < ?
            ORDER BY hash DESC LIMIT ?
            """,
        (before_hash, limit),
    )
    return cursor.fetchall()


def write_write_access_row(
    cursor: sqlite3.Cursor, write_access_data: dict | sqlite3.Row | tuple
):
    if isinstance(write_access_data, dict):
        write_access_data = convert_write_access_to_tuple(write_access_data)
    cursor.execute(
        "INSERT OR REPLACE INTO write_access VALUES(?, ?, ?, ?, ?, ?, ?) ",
        write_access_data,
    )


def set_write_accesses_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    write_accesses: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_write_access_rows = read_write_access_rows_by_uuid(cursor, entry_uuid)
    existing_write_accesses = [
        row["write_access"] for row in existing_write_access_rows
    ]
    current_time = int(time.time())
    if len(write_accesses) == 0:
        write_write_access_row(
            cursor,
            {
                "entry_hash": None,
                "entry_uuid": entry_uuid,
                "write_access": None,
                "time_edited": current_time,
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    for write_access in write_accesses:
        write_write_access_row(
            cursor,
            {
                "entry_hash": None,
                "entry_uuid": entry_uuid,
                "write_access": write_access,
                "time_edited": current_time,
                "edited_by": edited_by
                if write_access not in existing_write_accesses
                else existing_write_access_rows[
                    existing_write_accesses.index(write_access)
                ]["edited_by"],
                "api_key_id": api_key_id
                if write_access not in existing_write_accesses
                else existing_write_access_rows[
                    existing_write_accesses.index(write_access)
                ]["api_key_id"],
            },
        )
    _delete_outdated_write_access_if_not_in_archive_mode(cursor)


def add_write_access_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    write_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    write_accesses = read_write_accesses_by_uuid(cursor, entry_uuid)
    if write_access not in write_accesses:
        write_accesses.append(write_access)
        set_write_accesses_by_uuid(
            cursor, entry_uuid, write_accesses, edited_by, api_key_id
        )


def remove_write_access_by_uuid(
    cursor: sqlite3.Cursor,
    entry_uuid: bytes,
    write_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    write_accesses = read_write_accesses_by_uuid(cursor, entry_uuid)
    if write_access in write_accesses:
        write_accesses.remove(write_access)
        set_write_accesses_by_uuid(
            cursor, entry_uuid, write_accesses, edited_by, api_key_id
        )


def set_write_accesses_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    write_accesses: list[str],
    edited_by: str,
    api_key_id: str | None = None,
):
    existing_write_access_rows = read_write_access_rows_by_hash(cursor, entry_hash)
    existing_write_accesses = [
        row["write_access"] for row in existing_write_access_rows
    ]
    if len(existing_write_access_rows) == 0:
        # check if this hash references a uuid
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is None:
            logger.critical(f"Entry with sha256 hash {entry_hash.hex()} does not exist")
            raise LookupError(
                f"Entry with sha256 hash {entry_hash.hex()} does not exist"
            )
        if edit_log_data["entry_uuid"] is not None:
            return set_write_accesses_by_uuid(
                cursor,
                edit_log_data["entry_uuid"],
                write_accesses,
                edited_by,
                api_key_id,
            )
    current_time = int(time.time())
    if len(write_accesses) == 0:
        write_write_access_row(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": None,
                "write_access": None,
                "time_edited": current_time,
                "edited_by": edited_by,
                "api_key_id": api_key_id,
            },
        )
    for write_access in write_accesses:
        write_write_access_row(
            cursor,
            {
                "entry_hash": entry_hash,
                "entry_uuid": None,
                "write_access": write_access,
                "time_edited": current_time,
                "edited_by": edited_by
                if write_access not in existing_write_accesses
                else existing_write_access_rows[
                    existing_write_accesses.index(write_access)
                ]["edited_by"],
                "api_key_id": api_key_id
                if write_access not in existing_write_accesses
                else existing_write_access_rows[
                    existing_write_accesses.index(write_access)
                ]["api_key_id"],
            },
        )
    _delete_outdated_write_access_if_not_in_archive_mode(cursor)


def add_write_access_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    write_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    write_access_rows = read_write_access_rows_by_hash(cursor, entry_hash)
    write_accesses = [row["write_access"] for row in write_access_rows]
    if len(write_access_rows) == 0:
        # account for default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is not None:
            if edit_log_data["entry_uuid"] is not None:
                return add_write_access_by_uuid(
                    cursor,
                    edit_log_data["entry_uuid"],
                    write_access,
                    edited_by,
                    api_key_id,
                )
            write_accesses.append(edit_log_data["edited_by"])
            if edit_log_data["api_key_id"] is not None:
                write_accesses.append(edit_log_data["api_key_id"])
    if write_access not in write_accesses:
        write_accesses.append(write_access)
        set_write_accesses_by_hash(
            cursor, entry_hash, write_accesses, edited_by, api_key_id
        )


def remove_write_access_by_hash(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    write_access: str,
    edited_by: str,
    api_key_id: str | None = None,
):
    write_access_rows = read_write_access_rows_by_hash(cursor, entry_hash)
    write_accesses = [row["write_access"] for row in write_access_rows]
    if len(write_access_rows) == 0:
        # account for default access
        cursor.execute(
            """
            SELECT entry_uuid, edited_by, api_key_id FROM edit_log 
            WHERE entry_hash = ?
            ORDER BY timestamp ASC, is_deletion ASC 
            LIMIT 1
            """,
            (entry_hash,),
        )
        edit_log_data = cursor.fetchone()
        if edit_log_data is not None:
            if edit_log_data["entry_uuid"] is not None:
                return remove_write_access_by_uuid(
                    cursor,
                    edit_log_data["entry_uuid"],
                    write_access,
                    edited_by,
                    api_key_id,
                )
            write_accesses.append(edit_log_data["edited_by"])
            if edit_log_data["api_key_id"] is not None:
                write_accesses.append(edit_log_data["api_key_id"])
    if write_access in write_accesses:
        write_accesses.remove(write_access)
        set_write_accesses_by_hash(
            cursor, entry_hash, write_accesses, edited_by, api_key_id
        )


def normalize_write_access(write_access_data: dict | sqlite3.Row | tuple) -> dict:
    if isinstance(write_access_data, tuple):
        return convert_write_access_to_dict(write_access_data)

    if write_access_data["entry_hash"] is None:
        entry_hash_str = None
    elif isinstance(write_access_data["entry_hash"], str):
        entry_hash_str = bytes.fromhex(write_access_data["entry_hash"]).hex()
    else:
        entry_hash_str = bytes(write_access_data["entry_hash"]).hex()

    if write_access_data["entry_uuid"] is None:
        entry_uuid_str = None
    elif isinstance(write_access_data["entry_uuid"], uuid.UUID):
        entry_uuid_str = str(write_access_data["entry_uuid"])
    elif isinstance(write_access_data["entry_uuid"], bytes):
        entry_uuid_str = str(uuid.UUID(bytes=write_access_data["entry_uuid"]))
    else:
        entry_uuid_str = str(uuid.UUID(write_access_data["entry_uuid"]))

    return {
        "entry_hash": entry_hash_str,
        "entry_uuid": entry_uuid_str,
        "write_access": str(write_access_data["write_access"])
        if write_access_data["write_access"] is not None
        else None,
        "time_edited": int(write_access_data["time_edited"]),
        "edited_by": str(write_access_data["edited_by"]),
        "api_key_id": str(write_access_data["api_key_id"])
        if write_access_data["api_key_id"] is not None
        else None,
    }


def calculate_write_access_hash(write_access_data: dict | sqlite3.Row | tuple) -> bytes:
    hashable_dict = normalize_write_access(write_access_data)
    hashable_bytes = rfc8785.dumps(hashable_dict)
    return hashlib.sha256(hashable_bytes).digest()


def convert_write_access_to_tuple(write_access_data: dict | sqlite3.Row):
    write_access_dict = normalize_write_access(write_access_data)
    return (
        bytes.fromhex(write_access_dict["entry_hash"])
        if write_access_dict["entry_hash"] is not None
        else None,
        uuid.UUID(write_access_dict["entry_uuid"]).bytes
        if write_access_dict["entry_uuid"] is not None
        else None,
        write_access_dict["write_access"],
        write_access_dict["time_edited"],
        write_access_dict["edited_by"],
        write_access_dict["api_key_id"],
        calculate_write_access_hash(write_access_dict),
    )


def convert_write_access_to_dict(write_access_tuple: sqlite3.Row | tuple) -> dict:
    write_access_dict = {
        "entry_hash": write_access_tuple[0],
        "entry_uuid": write_access_tuple[1],
        "write_access": write_access_tuple[2],
        "time_edited": write_access_tuple[3],
        "edited_by": write_access_tuple[4],
        "api_key_id": write_access_tuple[5],
    }
    return normalize_write_access(write_access_dict)


def _delete_outdated_write_access_if_not_in_archive_mode(cursor: sqlite3.Cursor):
    if (
        "archive_mode" in quasilattice.config
        and not quasilattice.config["archive_mode"]
    ):
        # delete outdated write_access rows
        cursor.execute(
            """
            DELETE FROM write_access AS write_access1
            WHERE
            (write_access1.entry_uuid IS NOT NULL
                AND entry_hash IS NULL
                AND entry_uuid = write_access1.entry_uuid)
            OR
            (write_access1.entry_hash IS NOT NULL
                AND entry_uuid IS NULL
                AND entry_hash = write_access1.entry_hash)
            )
            """
        )


# endregion


# region linked_files
def get_linked_file(cursor: sqlite3.Cursor, file_hash: bytes) -> str | None:
    """Return a path to a valid linked file or None."""

    cursor.execute(
        "SELECT time_file_modified, linked_file_path FROM linked_files WHERE file_hash = ?",
        (file_hash,),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    time_file_modified = row["time_file_modified"]
    file_path = row["linked_file_path"]

    if not os.path.isfile(file_path):
        return None

    if (
        int(os.path.getmtime(file_path)) != time_file_modified
    ):  # check if the file was modified
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        except OSError:
            return None  # failed to calcualte hash
        if sha256.digest() == file_hash:
            link_file(cursor, file_hash, file_path, False)
        else:
            return None  # hash doesn't match
    return file_path


def link_file(cursor, file_hash: bytes, path_to_file: str, verify: bool = True) -> bool:
    path_to_file = os.path.abspath(path_to_file)

    if not os.path.isfile(path_to_file):
        return False

    if verify:
        sha256 = hashlib.sha256()
        try:
            with open(path_to_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        except OSError:
            return False  # failed to calcualte hash
        if sha256.digest() != file_hash:
            return False  # hash doesn't match

    cursor.execute(
        "INSERT OR REPLACE INTO linked_files VALUES(?, ?, ?) ",
        (file_hash, int(os.path.getmtime(path_to_file)), path_to_file),
    )

    return True


# endregion


# region metadata_tree
def write_metadata_tree_rows_by_key_value(
    cursor: sqlite3.Cursor,
    entry_hash: bytes,
    timestamp: float | None,
    key: str,
    value: typing.Any,
    parent_uuid: bytes | None = None,
) -> None:
    """Recursively writes key/value pairs to metadata_tree."""
    node_uuid = uuid.uuid4().bytes
    if (
        not isinstance(value, (dict, list))
        or isinstance(value, list)
        and len(value) < 500  # only store small(ish) lists
        and all(
            not isinstance(element, (dict, list)) for element in value
        )  # only simple lists
    ):
        stored_value = rfc8785.dumps(value).decode("utf-8")
    else:
        stored_value = None

    cursor.execute(
        "INSERT INTO metadata_tree VALUES(?, ?, ?, ?, ?, ?)",
        (node_uuid, entry_hash, timestamp, key, stored_value, parent_uuid),
    )

    if isinstance(value, dict):
        for child_key, child_value in value.items():
            write_metadata_tree_rows_by_key_value(
                cursor, entry_hash, timestamp, child_key, child_value, node_uuid
            )


# endregion
