__version__ = "0.4.0"

from .quasilattice import *
#from . import database
#from . import api
#from . import cli

# TODO: Replace with environment variables?
config = {
                  "SECRET_KEY":"ReplaceThis", # Flask: secret key
                  "MAX_CONTENT_LENGTH": 10000000000, # Flask: 10 GB max file upload size
                  "SESSION_COOKIE_SECURE": True, # Flask: only send session cookie over HTTPS
                  "SESSION_COOKIE_HTTPONLY": True, # Flask: prevent javascript from reading session cookie
                  "SESSION_COOKIE_SAMESITE": "Lax", # Flask: prevent CSRF
                  "REQUIRE_AUTHENTICATION": True, # is authentication required
                  "ALLOW_USER_LOGIN": True, # can users login
                  "DATABASE_FOLDER": "", # path to the folder where database will be stored
                  "FILES_FOLDER": "files", # path to the folder where files will be stored
                  "URL": "http://127.0.0.1:5000", # url of the server
                  "API_KEY_LENGTH": 20, # number of characters to use in an api key
                  "MAX_API_KEYS": 10, # maximum number of api keys that a user can create
                  "MAX_API_ADMIN_KEYS": 200, # maximum number of api keys that an admin can create
                  "VALID_ID_CHARS": "acdefhjkmnprtwz1234567890", # characters to use for auto-generated aliases
                  "INITAL_ID_LENGTH": 4, # starting legth for auto generated aliases
                  "ARCHIVE_MODE": True, # should lattice keep the edit history of entries and files
                  }