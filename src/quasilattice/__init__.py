__version__ = "0.4.2"

from . import quasilattice as _quasilattice
from .quasilattice import *

for _name in ("config", "config_path", "current_default_alias_length", "sync_thread", "last_sync_time"):
    globals().pop(_name, None)
del _name

def __getattr__(name):
    return getattr(_quasilattice, name)

_quasilattice.init()