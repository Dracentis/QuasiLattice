import os
import logging
import sqlite3 # sqlite database

import quasilattice

logger = logging.getLogger("quasilattice")

def create_database():
    try:
        logging.debug(f"Creating database at {quasilattice.config['quasilattice']['database_path']}")
        os.makedirs(os.path.dirname(quasilattice.config["quasilattice"]["database_path"]), exist_ok=True)
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
    except OSError as e:
        logger.critical("Failed to create database directory.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except Exception:
        raise
    try:
        with sqlite3.connect(quasilattice.config["quasilattice"]["database_path"]) as sql_connection:
            sql_cursor = sql_connection.cursor()

            # create info table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='info';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("CREATE TABLE info(name TEXT PRIMARY KEY NOT NULL, content TEXT)")

            # create users table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='users';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE users (
                        user TEXT PRIMARY KEY NOT NULL,
                        password_hash TEXT,
                        is_admin INTEGER
                    )""")

            # create keys table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE api_keys (
                        id TEXT PRIMARY KEY NOT NULL,
                        key TEXT NOT NULL,
                        note TEXT,
                        owner TEXT
                    )""")

            # create entries table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='entries';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE entries (
                        uuid BLOB NOT NULL,
                        time_edited INTEGER NOT NULL,
                        time_created INTEGER,
                        edited_by TEXT,
                        is_file INTEGER,
                        file_hash BLOB,
                        markup_language TEXT,
                        content TEXT,
                        metadata TEXT,
                        metadata_zstd BLOB,
                        PRIMARY KEY (uuid, time_edited),
                        CHECK (
                            (metadata IS NOT NULL AND metadata_zstd IS NULL)
                            OR (metadata IS NULL AND metadata_zstd IS NOT NULL)
                        )
                    )""")

            # create read_access table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='read_access';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE read_access (
                        entry_uuid BLOB NOT NULL,
                        access TEXT NOT NULL,
                        time_edited INTEGER NOT NULL,
                        edited_by TEXT,
                        PRIMARY KEY (entry_uuid, access, time_edited)
                    )""")

            # create write access table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='write_access';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE write_access (
                        entry_uuid BLOB NOT NULL,
                        access TEXT NOT NULL,
                        time_edited INTEGER NOT NULL,
                        edited_by TEXT,
                        PRIMARY KEY (entry_uuid, access, time_edited)
                    )""")

            # create metadata_tree table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='metadata_tree';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE metadata_tree (
                        uuid BLOB PRIMARY KEY,
                        entry_uuid BLOB NOT NULL,
                        time_edited INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        value TEXT,
                        parent_uuid BLOB
                    )""")

            # create hashes table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='hashes';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE hashes (
                        entry_uuid BLOB,
                        time_edited INTEGER,
                        hash BLOB,
                        PRIMARY KEY (entry_uuid, time_edited)
                    )""")

            # create hash_checksum_time_blocks table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='hash_checksum_time_blocks';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE hash_checksum_time_blocks (
                        block_start_time INTEGER,
                        hash BLOB,
                        PRIMARY KEY (block_start_time)
                    )""")

            # create hash_checksum_hash_blocks table
            sql_cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='hash_checksum_hash_blocks';""")
            if (sql_cursor.fetchone() == None):
                sql_cursor.execute("""
                    CREATE TABLE hash_checksum_hash_blocks (
                        block_start_hash BLOB,
                        hash BLOB,
                        PRIMARY KEY (block_start_hash)
                    )""")

            sql_connection.commit()
            sql_cursor.close()
    except PermissionError:
        logger.critical("Permission denied while creating database.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except OSError as e:
        logger.critical("Failed to create database.")
        if logger.getEffectiveLevel() <= 10:
            raise
        return
    except Exception:
        raise
