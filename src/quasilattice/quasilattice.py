import sys
import os
import time
import threading
import tomllib

config = {}
config_path = os.path.expanduser("~/.quasilattice/config.toml")
log_file = None
last_sync_time = time.time()

def init(config_path: str|None = None, log_level: str|None = None, log_path: str|None = None):    
    if config_path is None: 
        if os.path.isdir("/etc/quasilattice") and os.path.isfile("/etc/quasilattice/config.toml"):
            config_path = "/etc/quasilattice/config.toml"
        elif (os.path.isdir(os.path.expanduser("~/.config/quasilattice")) 
                and os.path.isfile(os.path.expanduser("~/.config/quasilattice/config.toml"))):
            config_path = os.path.expanduser("~/.config/quasilattice/config.toml")
        else:
            config_path = os.path.expanduser("~/.quasilattice/config.toml")
    sys.modules[__name__].config_path = config_path
        
    # load config
    if not os.path.isfile(config_path):
        print("Creating default config file.")
        write_default_config_file()
    with open(config_path, "rb") as config_file:
        config = tomllib.load(config_file)
    validate_config()
    if log_level is not None:
        config["logging"]["log_level"] = log_level
    if log_path is not None:
        config["logging"]["log_path"] = log_path

    if sys.stdout is None or sys.stderr is None:
        os.makedirs(os.path.dirname(config["logging"]["log_path"]), exist_ok=True)
        global log_file
        log_file = open(config["logging"]["log_path"], "a", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file

    if config["sync"]["enabled"]:
        start_sync_job()

def validate_config():
    global config
    if not config:
        config = {}
    
    if "quasilattice" not in config:
        config["quasilattice"] = {}
    if "database_path" not in config["quasilattice"]:
        config["quasilattice"]["database_path"] = os.path.join(os.path.dirname(config_path),"quasilattice.db")
    if "files_dir" not in config["quasilattice"]:
        config["quasilattice"]["files_dir"] = os.path.join(os.path.dirname(config_path),"files")
    if "max_file_size_gb" not in config["quasilattice"]:
        config["quasilattice"]["max_file_size_gb"] = 10
    if "case_sensitive_aliases" not in config["quasilattice"]:
        config["quasilattice"]["case_sensitive_aliases"] = False
    if "generate_default_aliases" not in config["quasilattice"]:
        config["quasilattice"]["generate_default_aliases"] = True
    if "default_alias_length" not in config["quasilattice"]:
        config["quasilattice"]["default_alias_length"] = 4
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
    if "log_dir" not in config["logging"]:
        config["logging"]["log_dir"] = os.path.join(os.path.dirname(config_path),"quasilattice.log")
    
    if "http" not in config:
        config["http"] = {}
    if "enabled" not in config["http"]:
        config["http"]["enabled"] = True
    if "host" not in config["http"]:
        config["http"]["host"] = "0.0.0.0"
    if "port" not in config["http"]:
        config["http"]["port"] = 8312
    if "require_authentication" not in config["http"]:
        config["http"]["require_authentication"] = True
    if "api_key_length" not in config["http"]:
        config["http"]["api_key_length"] = 20

def write_default_config_file():
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as file:
        file.write(f"""# This is the default QuasiLattie config file.
# You may want to modify these settings.

[quasilattice]

# Path to the SQLite database file:
database_path = "{os.path.join(os.path.dirname(config_path),"quasilattice.db")}"

# Directory to store files associated with lattice entries:
files_dir = "{os.path.join(os.path.dirname(config_path),"files")}"

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
    # [Local Host]
    #   protocol = "http"
    #   host = "127.0.0.1"
    #   port = 8312
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
log_level = 3

# Log directory determines where the log file is written to:
log_dir = "{os.path.join(os.path.dirname(config_path),"quasilattice.log")}"


[http]
# Enable the http interface (default: true):
enabled = true

# Host to bind to (default: "0.0.0.0"):
host = "0.0.0.0"

# Port to bind to (default: 8312):
port = 8312

# Require authentication for the http interface (default: true):
require_authentication = true

# Number of characters in API keys (default: 20):
api_key_length = 20

""")

def sync_with_peers():
    pass # TODO: implement syncing

def start_sync_job():
    if sync_thread == None:
        sync_thread = threading.Thread(target=_sync_job)
        sync_thread.daemon = True
        sync_thread.start()

def _sync_job():
    while True:
        now = time.time()
        if now > last_sync_time+config["sync"]["sync_interval_sec"]:
            sync_with_peers()
            last_sync_time = time.time()
        time.sleep(config["sync"]["sync_interval_sec"])
        