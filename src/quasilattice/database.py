import sqlite3 # sqlite database

def databasefunc():
    print("database function1!")

def createDatabase():
    try:
        os.makedirs(config["DATABASE_FOLDER"], exist_ok=True)
    except:
        pass
    try:
        os.makedirs(config["FILES_FOLDER"], exist_ok=True)
    except:
        pass
    sqlConnection = sqlite3.connect(os.path.join(config["DATABASE_FOLDER"],"quasilatticedata.db"))
    sqlCursor = sqlConnection.cursor()
    # create info table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='info';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE info(name TEXT PRIMARY KEY, content TEXT)")
    # create users table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='users';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE users(username TEXT PRIMARY KEY, passwordHash TEXT, isAdmin INTEGER)")
        sqlCursor.execute("INSERT OR REPLACE INTO users VALUES(?, ?, ?) ", ("admin",werkzeug.security.generate_password_hash("admin"),True))
    # create keys table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='keys';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE keys(id TEXT PRIMARY KEY, key TEXT, note TEXT, owner TEXT)")
    # create entries table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='entries';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE entries(uuid BLOB, timeedited INTEGER, timecreated INTEGER, editedBy TEXT, readaccess TEXT, writeaccess TEXT, isfile INTEGER, content TEXT, PRIMARY KEY (uuid, timeedited))")
    # create files table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='files';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE files(uuid BLOB PRIMARY KEY, entry BLOB, timeedited INTEGER, editedBy TEXT)")
    # create aliases table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='aliases';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE aliases(alias TEXT, timeedited INTEGER, uuid BLOB, PRIMARY KEY (alias, timeedited))")
    # create data table
    sqlCursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='data';""")
    if (sqlCursor.fetchone() == None):
        sqlCursor.execute("CREATE TABLE data(uuid BLOB, name TEXT, timeedited INTEGER, data TEXT, PRIMARY KEY (uuid, name, timeedited))")
    sqlConnection.commit()
    sqlCursor.close()
    sqlConnection.close()
